#coding=utf-8
#!/usr/bin/python
import sys, re, json, time, base64
from urllib.parse import urlencode, quote, unquote, urlsplit, parse_qs

try:
    from curl_cffi import requests as _curl_requests
    _USE_CURL = True
except Exception:
    _curl_requests = None
    _USE_CURL = False

import requests as _requests

sys.path.append('..')
from base.spider import Spider

# =============================================================================
# 配置
# =============================================================================
BASE_URL = 'https://www.jibcmjp.com:2087'
API_BASE = BASE_URL + '/v1'
BRANCH = 't1'

PLAY_FROM = '一起草'          

PUBKEY = ('MIIBVAIBADANBgkqhkiG9w0BAQEFAASCAT4wggE6AgEAAkEA0E9Nsuz6jYF+JeLqKaL1LkZyg0Wl4xP'
          'IwEzlDrO4UOMYGX1WG+nqf9ovpplgThgLcyoRM1YFshGFOrkAiHEZqwIDAQABAkABvEdncDX+K9ADPMq6ohLs2cV'
          'mdpQVOjr37ywRXUnx0o6skjM3Yg45uw3lpobrkckep0NxqrINeSsrY29hA3ZBAiEA8rnQiqs6hXw8tLIBk0i2i7'
          'tqai9xew/lD/wDGQdtvdECIQDbs6kkuEs9us9avgF/JO7F13OmlDzR0lzrIzujxvLSuwIgW+BX/tVXnoVrWR50GD'
          'MS3gt/+VeiBen7U7SZ25SDRrECIBhIx41zgX2VRI43KlsvbeUYZ4QmJoLaycKD5ne36ec5AiEA44AwFDoD1qf1wI'
          'Z152QxrkZgGMyKG6c836lRB5VdiME=')

XOR_COVER = True
PAGE_SIZE = 20

_IMPERSONATES = ['chrome136', 'chrome131', 'chrome124', 'chrome120', 'chrome110', 'edge101', 'safari15_3']


class Spider(Spider):
    def __init__(self):
        super().__init__()
        self.base = BASE_URL
        self.api_base = API_BASE
        self.branch = BRANCH
        self.ua = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')
        self.headers = {
            'User-Agent': self.ua,
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': self.base,
        }
        self._session = _requests.Session()
        self._session.headers.update(self.headers)
        self._curl = None
        if _USE_CURL:
            try:
                self._curl = _curl_requests.Session()
                self._curl.headers.update(self.headers)
            except Exception:
                self._curl = None
        self._imp = None
        self._warmed = False
        self._init_data = None
        self._cates_cache = None
        self._cate_manual = None
        self._subs = {}
        self.last_debug = {}

        self.config = {"player": {}, "filter": {}}

    def getName(self):
        return "一起草"

    def init(self, extend=""):
        pass

    def isVideoFormat(self, url):
        if not url:
            return False
        url = url.lower()
        return any(ext in url for ext in ['.m3u8', '.mp4', '.flv', '.webm', '.ts'])

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    # ---------------- 解密 ----------------

    def _rsa_decrypt(self, key_b64):
        try:
            from cryptography.hazmat.primitives.serialization import load_der_public_key
            from cryptography.hazmat.primitives.asymmetric import padding as rsa_padding
            pub = load_der_public_key(base64.b64decode(PUBKEY))
            return pub.decrypt(base64.b64decode(key_b64), rsa_padding.PKCS1v15())
        except Exception:
            pass
        try:
            from Crypto.PublicKey import RSA
            from Crypto.Cipher import PKCS1_v1_5
            pub = RSA.import_key(base64.b64decode(PUBKEY))
            sentinel = b''
            return PKCS1_v1_5.new(pub).decrypt(base64.b64decode(key_b64), sentinel)
        except Exception:
            return b''

    def _aes_decrypt(self, data_b64, aes_key):
        key = aes_key.encode('utf-8')
        iv = aes_key[::-1][:16].encode('utf-8')
        ct = base64.b64decode(data_b64)
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            dec = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
            plain = dec.update(ct) + dec.finalize()
        except Exception:
            from Crypto.Cipher import AES
            plain = AES.new(key, AES.MODE_CBC, iv).decrypt(ct)
        if plain:
            pad = plain[-1]
            if 1 <= pad <= 16:
                plain = plain[:-pad]
        return plain

    def _decrypt_response(self, body):
        if isinstance(body, dict) and isinstance(body.get('data'), str) and isinstance(body.get('key'), str):
            try:
                aes_key = self._rsa_decrypt(body['key']).decode('utf-8')
                if aes_key:
                    plain = self._aes_decrypt(body['data'], aes_key)
                    obj = json.loads(plain.decode('utf-8'))
                    return obj.get('data', obj)
            except Exception:
                pass
            return body.get('data')
        return body

    # ---------------- 请求 ----------------

    def _warmup(self):
        if self._warmed:
            return
        self._warmed = True
        try:
            self._session.get(self.base, timeout=15)
        except Exception:
            pass

    def _curl_request(self, method, url, **kw):
        if self._curl is None:
            raise RuntimeError('no curl_cffi')
        imps = [self._imp] if self._imp else _IMPERSONATES
        err = None
        for imp in imps:
            try:
                if method == 'POST':
                    r = self._curl.post(url, impersonate=imp, verify=False, timeout=20, **kw)
                else:
                    r = self._curl.get(url, impersonate=imp, verify=False, timeout=20, **kw)
                if self._imp is None:
                    self._imp = imp
                return r
            except Exception as e:
                err = e
                continue
        raise err if err else RuntimeError('curl_cffi request failed')

    def _api_get(self, path, params=None):
        self._warmup()
        params = dict(params or {})
        params.setdefault('c', self.branch)
        url = self.api_base + '/' + path.lstrip('/')
        rsp = None
        try:
            rsp = self._session.get(url, params=params, timeout=20)
        except Exception:
            rsp = None
        if rsp is None and self._curl is not None:
            try:
                rsp = self._curl_request('GET', url, params=params)
            except Exception:
                rsp = None
        if rsp is None:
            return None
        try:
            body = rsp.json()
        except Exception:
            self.last_debug = {'api': url, 'error': 'not json', 'status': getattr(rsp, 'status_code', 0)}
            return None
        return self._decrypt_response(body)

    # ---------------- 工具 ----------------

    def _fix_url(self, url):
        if not url:
            return ''
        if url.startswith('http'):
            return url
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('/'):
            return self.base + url
        return self.base + '/' + url

    def fixCover(self, url):
        if not url:
            return ''
        if not url.startswith('http'):
            return url
        qs = urlencode({'do': 'py', 'name': self.getName(), 'url': url})
        proxy_base = ''
        if hasattr(self, 'getProxyUrl'):
            try:
                proxy_base = self.getProxyUrl()
            except Exception:
                pass
        if proxy_base:
            try:
                p = urlsplit(proxy_base)
                base = '{0}://{1}/proxy'.format(p.scheme or 'http', p.netloc or '127.0.0.1:9978')
                return '{0}?{1}'.format(base, qs)
            except Exception:
                pass
        return 'http://127.0.0.1:9978/proxy?{0}'.format(qs)

    

    def _get_init_data(self):
        if self._init_data is None:
            self._init_data = self._api_get('/blist') or {}
        return self._init_data

    def _get_cates(self):
        if self._cates_cache is None:
            data = self._api_get('/vod/category') or {}
            self._cates_cache = data.get('cates') or data.get('list') or []
        return self._cates_cache

    def _get_cate_manual(self):
        if self._cate_manual is None:
            self._cate_manual = {}
            cates = self._get_cates()
            for c in cates:
                if isinstance(c, dict) and c.get('id') is not None and c.get('name'):
                    self._cate_manual[str(c['name'])] = str(c['id'])
        return self._cate_manual

    def _get_sub_cates(self):
        if self._subs:
            return self._subs
        init = self._get_init_data()
        for c in (init.get('menu_cates') or []):
            if not isinstance(c, dict) or c.get('id') is None:
                continue
            subs = []
            for s in (c.get('sub_cates') or c.get('sub_menu') or []):
                if isinstance(s, dict) and (s.get('id') is not None or s.get('t')) and s.get('name'):
                    sid = s.get('id') if s.get('id') is not None else s.get('t')
                    subs.append({'type_id': str(sid), 'type_name': str(s['name'])})
            if subs:
                self._subs[str(c['id'])] = subs
        return self._subs

    def _build_filter_config(self):
        cateManual = self._get_cate_manual()
        subs = self._get_sub_cates()
        sort_filter = {
            'key': 'sort', 'name': '排序',
            'value': [
                {'n': '默认', 'v': ''},
                {'n': '最新', 'v': 'time'},
                {'n': '最热', 'v': 'hits'},
                {'n': '评分', 'v': 'score'},
            ]
        }
        f = {}
        for cid in cateManual.values():
            filt = [sort_filter]
            if subs.get(cid):
                sf = {
                    'key': 'sub', 'name': '子分类',
                    'value': [{'n': '全部', 'v': ''}] + [{'n': s['type_name'], 'v': s['type_id']} for s in subs[cid]]
                }
                filt = [sf, sort_filter]
            f[cid] = filt
        self.config['filter'] = f
        return f

    def homeContent(self, filter):
        result = {}
        cateManual = self._get_cate_manual()
        if not cateManual:
            cateManual = {"全部": "0", "最新": "1", "热门": "2"}
        classes = []
        for k in cateManual:
            classes.append({'type_name': k, 'type_id': cateManual[k]})
        result['class'] = classes
        if filter:
            result['filters'] = self._build_filter_config()
        return result

    # ---------------- 列表解析（广告过滤 + 严格视频识别） ----------------

    def _looks_video(self, d):
        if not isinstance(d, dict) or not d.get('name'):
            return False
        if d.get('href'):
            return False
        if d.get('is_yp') or d.get('is_ad') or d.get('ad') is not None or d.get('ad_type') \
           or str(d.get('type', '')).lower() == 'ad':
            return False
        for k in ('videos', 'sub_cates', 'sub_menu', 'children', 'list', 'cates'):
            if isinstance(d.get(k), list):
                return False
        if d.get('enc_img'):
            return True
        t = d.get('time')
        if isinstance(t, str) and re.fullmatch(r'\d{1,3}:\d{2}(?::\d{2})?', t.strip()):
            return True
        if isinstance(d.get('eye'), (int, float)):
            return True
        return False

    def _to_item(self, v):
        if not isinstance(v, dict):
            return None
        if not self._looks_video(v):
            return None
        if v.get('href') or v.get('is_yp'):
            return None
        vid = v.get('id') or v.get('vod_id') or v.get('video_id')
        name = v.get('name') or v.get('title') or v.get('vod_name') or v.get('video_name')
        if vid is None or not name:
            return None
        vod_id = '{0}/{1}.html'.format(self.base, vid)
        pic = v.get('enc_img') or v.get('pic') or v.get('cover') or v.get('img') or v.get('vod_pic') or ''
        pic = self._fix_url(pic)
        remark = v.get('time') or v.get('vod_remarks') or v.get('duration') or v.get('remarks') or ''
        return {
            'vod_id': vod_id,
            'vod_name': str(name)[:200],
            'vod_pic': self.fixCover(pic),
            'vod_remarks': str(remark),
        }

    def _parse_videos(self, data):
        items = []
        seen = set()
        candidates = []
        if isinstance(data, dict):
            for key in ('recommend_videos', 'rank_videos'):
                blk = data.get(key)
                if isinstance(blk, dict) and isinstance(blk.get('videos'), list):
                    for x in blk['videos']:
                        if isinstance(x, dict) and self._looks_video(x):
                            candidates.append(x)
        if not candidates:
            def walk(obj, depth=0):
                if depth > 10 or obj is None:
                    return
                if isinstance(obj, list):
                    for x in obj:
                        walk(x, depth + 1)
                elif isinstance(obj, dict):
                    if self._looks_video(obj):
                        candidates.append(obj)
                    for v in obj.values():
                        walk(v, depth + 1)
            walk(data)
        for it in candidates:
            item = self._to_item(it)
            if item and item['vod_id'] not in seen:
                seen.add(item['vod_id'])
                items.append(item)
        return items

    # ---------------- 分页 ----------------

    @staticmethod
    def _to_int(v):
        try:
            return int(float(v))
        except Exception:
            return 0

    def _extract_pagination(self, data):
        total = 0
        page = 0
        pagecount = 0

        def walk(obj, depth=0):
            nonlocal total, page, pagecount
            if depth > 6 or obj is None:
                return
            if isinstance(obj, dict):
                for k, v in obj.items():
                    kl = str(k).lower().strip()
                    if isinstance(v, (int, float, str)):
                        sv = str(v).strip()
                        if sv.lstrip('-').isdigit():
                            nv = self._to_int(v)
                            if kl in ('total', 'total_count', 'totalcount', 'count',
                                      'record_count', 'records_total', 'sum'):
                                if not total:
                                    total = nv
                            elif kl in ('pagecount', 'page_count', 'pages', 'total_page', 'total_pages'):
                                if not pagecount:
                                    pagecount = nv
                            elif kl in ('page', 'current_page', 'page_no', 'pageno', 'page_num'):
                                if not page:
                                    page = nv
                for v in obj.values():
                    if isinstance(v, (dict, list)):
                        walk(v, depth + 1)
            elif isinstance(obj, list):
                for x in obj:
                    if isinstance(x, (dict, list)):
                        walk(x, depth + 1)

        walk(data)
        return total, page, pagecount

    def _list_result(self, data, pg):
        items = self._parse_videos(data)
        total, page, pagecount = self._extract_pagination(data)
        pg = int(pg) if pg else 1
        if not pagecount:
            if total:
                pagecount = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
            else:
                pagecount = pg + 1 if len(items) >= PAGE_SIZE else pg
        return {
            'list': items,
            'page': pg,
            'pagecount': pagecount,
            'limit': PAGE_SIZE,
            'total': total or len(items),
        }

    # ---------------- 首页 / 分类列表 / 搜索 ----------------

    def homeVideoContent(self):
        data = self._api_get('/relist')
        items = self._parse_videos(data)
        if not items:
            self.last_debug = {'api': '/relist', 'note': 'empty'}
        return {'list': items}

    def categoryContent(self, tid, pg, filter, extend):
        if not pg:
            pg = '1'
        extend = extend or {}
        params = {'page': str(pg), 'limit': PAGE_SIZE}
        if extend.get('sort'):
            params['sort'] = extend['sort']
        if tid:
            params['cate_id'] = tid
        if extend.get('sub'):
            params['cate_pid'] = extend['sub']
        data = self._api_get('/vod', params)
        return self._list_result(data, pg)

    def searchContent(self, key, quick, pg='1'):
        if not pg:
            pg = '1'
        params = {'name': key, 'page': str(pg), 'limit': PAGE_SIZE}
        data = self._api_get('/vod', params)
        return self._list_result(data, pg)

    # ---------------- 详情 / 播放 ----------------

    def _deep_field(self, obj, *keys, depth=0):
        if depth > 10 or obj is None:
            return ''
        if isinstance(obj, dict):
            for k in keys:
                v = obj.get(k)
                if v is not None and str(v).strip():
                    return str(v).strip()
            for v in obj.values():
                if isinstance(v, (dict, list)):
                    r = self._deep_field(v, *keys, depth=depth + 1)
                    if r:
                        return r
        elif isinstance(obj, list):
            for x in obj:
                if isinstance(x, (dict, list)):
                    r = self._deep_field(x, *keys, depth=depth + 1)
                    if r:
                        return r
        return ''

    def _collect_play(self, obj, out, depth=0):
        if depth > 10 or obj is None:
            return
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str) and re.search(r'\.(m3u8|mp4|flv|webm|ts)(\?[^"\']*)?$', v, re.I):
                    if v not in out:
                        out.append(v)
                elif isinstance(v, (dict, list)):
                    self._collect_play(v, out, depth + 1)
        elif isinstance(obj, list):
            for x in obj:
                self._collect_play(x, out, depth + 1)

    def detailContent(self, array):
        vid = array[0]
        m = re.search(r'/(\d+)(?:\.html)?(?:[?&]|$)', vid)
        id_ = m.group(1) if m else re.sub(r'\D', '', vid)
        data = self._api_get('vod/' + str(id_))
        obj = data if isinstance(data, dict) else {}

        name = self._deep_field(obj, 'name', 'title', 'vod_name', 'video_name')
        cover = self._deep_field(obj, 'enc_img', 'pic', 'cover', 'img', 'vod_pic')
        cover = self._fix_url(cover)
        desc = self._deep_field(obj, 'desc', 'description', 'content', 'intro', 'vod_content', 'plot')
        actor = self._deep_field(obj, 'actor', 'actress', 'stars', 'vod_actor')
        director = self._deep_field(obj, 'director', 'vod_director')
        year = self._deep_field(obj, 'year', 'vod_year')
        area = self._deep_field(obj, 'area', 'region', 'vod_area')

        play_urls = []
        self._collect_play(obj, play_urls)
        eps = []
        for u in play_urls:
            u = u.replace('\\/', '/')
            eps.append({'name': '线路%d' % (len(eps) + 1), 'url': u})

        play_from, play_url = [], []
        if eps:
            play_from.append(PLAY_FROM)          # ← 海豚研究院专用
            play_url.append('#'.join(['{0}${1}'.format(e['name'], e['url']) for e in eps]))
        else:
            play_from.append(PLAY_FROM)          # ← 海豚研究院专用
            play_url.append('播放$' + self.base + '/' + str(id_) + '.html')

        detail = {
            'vod_id': vid,
            'vod_name': name or str(id_),
            'vod_pic': self.fixCover(cover),
            'vod_year': year,
            'vod_area': area,
            'vod_actor': actor,
            'vod_director': director,
            'vod_content': desc,
            'vod_play_from': '$$$'.join(play_from),
            'vod_play_url': '$$$'.join(play_url),
        }
        return {'list': [detail]}

    def playerContent(self, flag, id, vipFlags):
        url = id
        if not url.startswith('http'):
            url = self._fix_url(url)
        return {
            'parse': 0,
            'playUrl': '',
            'url': url,
            'header': json.dumps({'Referer': self.base, 'User-Agent': self.ua, 'Origin': self.base})
        }

    # ---------------- 封面代理（XOR 还原） ----------------

    @staticmethod
    def _looks_image(b):
        return (b[:3] == b'\xff\xd8\xff' or b[:4] == b'\x89PNG' or b[:3] == b'GIF'
                or b[:2] == b'BM' or b[:4] == b'RIFF' or b[:3] == b'WEB')

    def _extract_proxy_url(self, param):
        url = ''
        if param is None:
            return ''
        if isinstance(param, str):
            url = param
            if url.startswith('http') and '/proxy?' in url:
                try:
                    qs = parse_qs(urlsplit(url).query)
                    if qs.get('url'):
                        url = qs['url'][0]
                except Exception:
                    pass
        elif isinstance(param, dict):
            for k in ['url', 'pic', 'img', 'target', 'src', 'image', 'href', 'link', 'path', 'uri', 'raw', 'u']:
                v = param.get(k)
                if v:
                    if isinstance(v, list) and v:
                        v = v[0]
                    url = str(v)
                    break
            if not url:
                for vv in param.values():
                    if isinstance(vv, str) and vv.startswith('http'):
                        url = vv
                        break
        elif isinstance(param, (list, tuple)) and param:
            first = param[0]
            if isinstance(first, dict):
                return self._extract_proxy_url(first)
            elif isinstance(first, str):
                url = first
            else:
                url = str(first)
        else:
            url = str(param)
        url = url.strip().strip("\"'").strip()
        try:
            while '%' in url:
                try:
                    decoded = unquote(url)
                    if decoded == url:
                        break
                    url = decoded
                except Exception:
                    break
        except Exception:
            pass
        return url

    def localProxy(self, param):
        try:
            url = self._extract_proxy_url(param)
            if not url:
                return [404, 'text/plain', b'', 'no url']
            if not url.startswith('http'):
                return [404, 'text/plain', b'', 'invalid url']
            headers = {
                'User-Agent': self.ua,
                'Referer': self.base,
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            }
            rsp = None
            try:
                rsp = self._session.get(url, headers=headers, timeout=15)
            except Exception:
                rsp = None
            if rsp is None and self._curl is not None:
                try:
                    rsp = self._curl_request('GET', url, headers=headers)
                except Exception:
                    rsp = None
            if rsp is None:
                return [404, 'text/plain', b'', 'fetch fail']
            body = rsp.content
            if XOR_COVER and body and not self._looks_image(body[:16]):
                xored = bytes([x ^ 0x88 for x in body])
                if self._looks_image(xored[:16]):
                    body = xored
            ctype = 'image/jpeg'
            if rsp.headers.get('content-type'):
                ctype = rsp.headers.get('content-type').split(';')[0].strip()
            if body[:3] == b'\xff\xd8\xff':
                ctype = 'image/jpeg'
            elif body[:4] == b'\x89PNG':
                ctype = 'image/png'
            elif body[:3] == b'GIF':
                ctype = 'image/gif'
            extra_headers = (
                'Content-Type: {0}\r\n'
                'Cache-Control: public, max-age=86400\r\n'
                'Content-Length: {1}\r\n'
            ).format(ctype, len(body))
            return [200, ctype, body, extra_headers]
        except Exception as e:
            return [500, 'text/plain', b'', str(e)]


# ---------------- 本地自测 ----------------
if __name__ == '__main__':
    sp = Spider()
    print('=' * 50)
    print('站点名 getName:', sp.getName())
    r = sp.homeVideoContent()
    print('首页条数:', len(r['list']))
    print('-' * 50)
    if r['list']:
        d = sp.detailContent([r['list'][0]['vod_id']])
        print('详情名称:', d['list'][0]['vod_name'])
        print('播放源:', d['list'][0]['vod_play_from'])   
        print('播放URL:', d['list'][0]['vod_play_url'][:120])