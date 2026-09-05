# -*- coding: utf-8 -*-
"""
《追影》- 全网最新蓝光高清影视 | TVBox/影视仓 dr_py Python 源 (HKL兼容版)
站点: https://zhuiying8.cc/
类型: MacCMS 变体 (服务端直出)
"""
import sys
import re
import json
import html as ihtml
from urllib.parse import quote, urljoin, unquote

try:
    import requests
except ImportError:
    requests = None

try:
    sys.path.append('..')
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider:
        def init(self, extend=""): pass
        def getName(self): return ""
        def homeContent(self, filter): return {'class': [], 'filters': {}}
        def homeVideoContent(self): return {'list': []}
        def categoryContent(self, tid, pg, filter, extend): return {'list': []}
        def detailContent(self, ids): return {'list': []}
        def searchContent(self, key, quick, pg='1'): return {'list': []}
        def playerContent(self, flag, id, vipFlags=None): return {'parse': 0, 'url': id, 'header': {}}


class Spider(BaseSpider):
    name = '追影'
    HOST = 'https://zhuiying8.cc'

    def __init__(self):
        try:
            super().__init__()
        except Exception:
            pass
        self.host = self.HOST
        self.timeout = 20
        self.headers = {
            'User-Agent': ('Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36 '
                           'Chrome/120.0 Mobile Safari/537.36'),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        }
        self.s = requests.Session() if requests else None
        if self.s:
            self.s.headers.update(self.headers)
        self.CATEGORIES = (
            ('电影', 'dianying'), ('电视剧', 'dianshiju'), ('动漫', 'dongman'),
            ('综艺', 'zongyi'), ('短剧', 'duanju'),
        )

    def init(self, extend=''):
        cfg = extend if isinstance(extend, dict) else {}
        if not cfg and extend:
            try:
                cfg = json.loads(extend) if isinstance(extend, str) else {}
            except Exception:
                cfg = {}
        h = str(cfg.get('host') or cfg.get('siteUrl') or '').strip().rstrip('/')
        if h.startswith(('http://', 'https://')):
            self.host = h
        return None

    def getName(self):
        return self.name

    def getDependence(self):
        return []

    def destroy(self):
        try:
            if self.s:
                self.s.close()
        except Exception:
            pass

    def isVideoFormat(self, url):
        v = str(url or '').lower()
        return any(x in v for x in ('.m3u8', '.mp4', '.m4v', '.mpd', '.flv', '.webm', '.ts'))

    def _request(self, url, params=None, referer=None, data=None, post=False, retry=2):
        headers = dict(self.headers)
        if referer:
            headers['Referer'] = referer
        fetch = getattr(self, 'fetch', None)
        if callable(fetch) and not post:
            try:
                r = fetch(url, headers=headers, params=params, timeout=self.timeout)
                if r is not None and getattr(r, 'text', ''):
                    return r
            except Exception:
                pass
        if self.s is None:
            return None
        for att in range(max(1, retry)):
            try:
                if post:
                    r = self.s.post(url, data=data, headers=headers, params=params,
                                    timeout=self.timeout, allow_redirects=True, verify=False)
                else:
                    r = self.s.get(url, headers=headers, params=params,
                                   timeout=self.timeout, allow_redirects=True, verify=False)
                if r.status_code in (403, 503, 429):
                    continue
                try:
                    r.encoding = r.apparent_encoding or 'utf-8'
                except Exception:
                    pass
                return r
            except Exception:
                pass
        return None

    @staticmethod
    def clean(s):
        return re.sub(r'\s+', ' ', ihtml.unescape(re.sub(r'<[^>]+>', '', s or ''))).strip()

    def _cards(self, html, base):
        """解析 video 卡片。结构：<a href="/video/{id}.html" ... title="标题"> + img 封面"""
        vods, seen = [], set()

        def add(vod):
            k = vod['vod_id']
            if k not in seen and vod['vod_name']:
                seen.add(k)
                vods.append(vod)

        # 模式1: 分类卡片（card js-card-item）——含 card-status/card-title/card-cover，信息最全
        card_pat = (r'<a[^>]+class="[^"]*card js-card-item[^"]*"[^>]*href="([^"]*/video/([^.\s]+)\.html)"[^>]*>(.*?)</a>'
                    r'|'
                    r'<a[^>]+href="([^"]*/video/([^.\s]+)\.html)"[^>]*class="[^"]*card js-card-item[^"]*"[^>]*>(.*?)</a>')
        any_card = False
        for m in re.finditer(card_pat, html or '', re.S):
            any_card = True
            # 取出若干分组中的实际 href/vid/内容
            href = m.group(1) or m.group(4) or ''
            vid = m.group(2) or m.group(5) or ''
            body = m.group(3) if m.group(3) is not None else (m.group(6) or '')
            block = m.group(0)
            if not vid:
                continue
            tm = re.search(r'<div[^>]+class="card-title[^"]*"[^>]*>\s*([^<]+?)\s*<', body)
            title = tm.group(1) if tm else ''
            if not title:
                tm2 = re.search(r'title="([^"]*)"', block)
                title = tm2.group(1) if tm2 else ''
            im = re.search(r'<img[^>]+src="([^"]+)"', body) or re.search(r'<img[^>]+src="([^"]+)"', block)
            rem = ''
            rm = re.findall(r'class="card-status"[^>]*>\s*([^<]*?)\s*<', body)
            if rm:
                rem = self.clean(rm[0])
            if not rem:
                rm2 = re.search(r'class="[^"]*card-status[^"]*"[^>]*>\s*([^<]*?)\s*<', body)
                rem = self.clean(rm2.group(1)) if rm2 else ''
            add({'vod_id': vid, 'vod_name': self.clean(title),
                 'vod_pic': urljoin(base, im.group(1)) if im else '',
                 'vod_remarks': rem})
        if any_card:
            return vods

        # 模式2: 首页卡片（hotsearch/hero/list 等）——用 title 属性，过滤 Top N 占位图
        for m in re.finditer(r'<a[^>]+href="([^"]*/video/([^.\s]+)\.html)"[^>]*>(.*?)</a>', html or '', re.S):
            href, vid = m.group(1), m.group(2)
            block = m.group(0)
            title_m = re.search(r'title="([^"]*)"', block)
            title = title_m.group(1) if title_m else ''
            img = re.search(r'<img[^>]+class="hotsearch_item_img"[^>]+src="([^"]+)"', block)
            if not img:
                imgs = re.findall(r'<img[^>]+(?:src|data-src|data-original)="([^"]+)"', block)
                for u in imgs:
                    if 'alicdn' in u or 'Top' in u or 'rang_img' in u or len(u) < 20:
                        continue
                    _pic_override = u
                    break
                else:
                    _pic_override = ''
            else:
                _pic_override = ''
            add({'vod_id': vid, 'vod_name': self.clean(title),
                 'vod_pic': urljoin(base, img.group(1)) if img else (_pic_override and urljoin(base, _pic_override) or ''),
                 'vod_remarks': ''})
        return vods

    def homeContent(self, filter=False):
        return {'class': [{'type_id': t, 'type_name': n} for n, t in self.CATEGORIES], 'filters': {}}

    def homeVideoContent(self):
        r = self._request(self.host + '/')
        base = getattr(r, 'url', '') or self.host + '/'
        return {'list': self._cards(r.text, base) if r and r.text else []}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        try:
            page = int(pg)
        except (ValueError, TypeError):
            page = 1
        if page < 1:
            page = 1
        url = '%s/vodtype/%s.html' % (self.host, tid)
        if page > 1:
            url = '%s/vodshow/%s--------%s---.html' % (self.host, tid, page)
        r = self._request(url)
        if not r or not r.text:
            return {'list': [], 'page': page, 'pagecount': 1, 'limit': 24, 'total': 0}
        vods = self._cards(r.text, r.url)
        pc = self._pagecount(r.text)
        return {'list': vods, 'page': page, 'pagecount': pc, 'limit': 24, 'total': 0}

    def _pagecount(self, html):
        # 统一取 /vodshow/xxx-----...+N---.html 或 ...---N---.html 里的分页数字
        alln = [int(n) for n in re.findall(r'\.html[^>]*>(\d+)</a>', html)][:0]  # noqa: placeholder
        alln = [int(n) for n in re.findall(r'---(\d+)---\.html', html) if n.isdigit()]
        if not alln:
            # 当前/总页 形如 x/y
            m = re.search(r'>\s*(\d+)\s*/\s*(\d+)\s*<', html)
            if m:
                try:
                    return max(1, int(m.group(2)))
                except ValueError:
                    pass
        return max(alln) if alln else 1

    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, (list, tuple)) and ids else ids or '').strip()
        if not vid:
            return {'list': []}
        r = self._request('%s/video/%s.html' % (self.host, vid))
        if not r or not r.text:
            return {'list': []}
        return {'list': [self._detail(r.text, vid, getattr(r, 'url', self.host))]}

    def _detail(self, html, vid, base_url):
        title = ''
        tm = re.search(r'<h1[^>]*>([\s\S]*?)</h1>', html) or re.search(r'<title>([\s\S]*?)</title>', html)
        if tm:
            title = self.clean(tm.group(1))
        title = re.split(r'\s*[-_|]\s*(?:追影|免费在线观看)', title)[0].strip()
        img = re.search(r'<img[^>]+(?:src|data-original|data-src)="([^"]+\.(?:jpg|jpeg|png|webp))"', html)
        # 剧集 /play/{id}-{sid}-{nid}.html
        eps, seen = [], set()
        for m in re.finditer(r'href="([^"]*/play/%s-(\d+)-(\d+)\.html)"[^>]*>([^<]*)<' % re.escape(vid), html, re.I):
            href, sid, nid, txt = m.group(1), m.group(2), m.group(3), self.clean(m.group(4))
            key = (sid, nid)
            if key in seen:
                continue
            seen.add(key)
            name = txt.strip() or '第%s集' % nid
            eps.append((sid, '%s$%s' % (name, href)))
        bysid = {}
        for sid, e in eps:
            bysid.setdefault(sid, []).append(e)
        if not bysid:
            return {'vod_id': vid, 'vod_name': title or vid, 'vod_pic': urljoin(base_url, img.group(1)) if img else '',
                    'vod_play_from': '', 'vod_play_url': ''}
        play_from = '$$$'.join(['在线播放'] * len(bysid))
        play_url = '$$$'.join('#'.join(v) for v in bysid.values())
        return {'vod_id': vid, 'vod_name': title or vid,
                'vod_pic': urljoin(base_url, img.group(1)) if img else '',
                'vod_content': '',
                'vod_play_from': play_from, 'vod_play_url': play_url}

    def searchContent(self, key, quick=False, pg='1'):
        kw = str(key or '').strip()
        try:
            page = int(pg)
        except (ValueError, TypeError):
            page = 1
        if not kw:
            return {'list': [], 'page': page, 'pagecount': 1, 'limit': 24, 'total': 0}
        r = self._request(self.host + '/vod/search/wd/%s/' % quote(kw))
        vods = self._cards(r.text, r.url) if r and r.text else []
        return {'list': vods, 'page': page, 'pagecount': 1, 'limit': 24, 'total': 0}

    def _get_play_cfg(self, html, base_url):
        """从播放页提取 MAC_PLAY_CONFIG 并调用 player_api.php 解密真实地址。"""
        cfg = {}
        m = re.search(r'MAC_PLAY_CONFIG\s*=\s*\{(.*?)\}\s*;', html or '', re.S)
        if m:
            body = m.group(1)
            for k in ('vod_id', 'sid', 'nid', 'baseKey', 'requestUrl', 'videoTitle'):
                km = re.search(r'"%s"\s*:\s*"([^"]*)"' % k, body)
                if not km:
                    km = re.search(r'%s\s*:\s*"([^"]*)"' % k, body)
                if km:
                    cfg[k] = km.group(1)
        ru = cfg.get('requestUrl', '')
        bk = cfg.get('baseKey', '')
        if not ru:
            return {'src': '', 'type': ''}
        import base64 as _b64, hashlib as _hl, time as _tm
        ts = int(_tm.time())
        ua = self.headers.get('User-Agent', 'Mozilla/5.0')
        token = _hl.md5((bk + str(ts) + ua).encode()).hexdigest()
        hd = dict(self.headers)
        hd['X-Requested-With'] = 'XMLHttpRequest'
        r = self.s.post(self.host + '/player_api.php',
                        data={'url': ru, 'timestamp': str(ts), 'token': token},
                        headers=hd, timeout=self.timeout) if self.s else None
        if r is None:
            return {'src': '', 'type': ''}
        try:
            j = r.json()
        except Exception:
            j = {}
        data = j.get('data', '')
        if not data:
            return {'src': '', 'type': ''}
        try:
            dec = _b64.b64decode(data[::-1])
            try:
                dec = dec.decode('utf-8')
            except Exception:
                dec = dec.decode('latin-1')
            dec = re.sub(r'\\/', '/', dec)
            pj = json.loads(dec)
            return {'src': pj.get('jmurl', ''), 'type': pj.get('urltype', ''), 'raw': dec}
        except Exception:
            return {'src': '', 'type': ''}

    def playerContent(self, flag, id, vipFlags=None):
        url = str(id or '').strip()
        # 兼容运行端误传整条线路：只取当前播放地址
        if '$$$' in url:
            url = url.split('$$$', 1)[0]
        if '$' in url and not re.match(r'^https?://', url):
            url = url.rsplit('$', 1)[-1].strip()
        if not url:
            return {'parse': 0, 'url': '', 'header': {}}
        if self.isVideoFormat(url):
            return {'parse': 0, 'url': url, 'header': {'User-Agent': self.headers.get('User-Agent', 'Mozilla/5.0'),
                                                       'Referer': self.host + '/'}}
        if re.search(r'/play/', url):
            furl = url if url.startswith('http') else self.host + url
            r = self._request(furl)
            if r and r.text:
                # 页面中已存在的直链
                m2 = re.search(r'(https?://[^\s\x22\x27]+\.(?:m3u8|mp4|mpd|flv)[^\s\x22\x27]*)', r.text)
                if m2:
                    return {'parse': 0, 'url': m2.group(1),
                            'header': {'User-Agent': 'Mozilla/5.0', 'Referer': self.host + '/'}}
                # MAC_PLAY_CONFIG 解密接口
                cfg = self._get_play_cfg(r.text, getattr(r, 'url', self.host))
                src = cfg.get('src', '')
                if src.startswith('http'):
                    rv = {'parse': 0, 'url': src,
                          'header': {'User-Agent': self.headers.get('User-Agent', 'Mozilla/5.0'),
                                     'Referer': self.host + '/'}}
                    if cfg.get('type', '') == 'hls':
                        rv['type'] = 'm3u8'
                    return rv
                # 兼容遗留 player_data 直链结构
                start = r.text.find('player_data')
                text = r.text[start:] if start >= 0 else r.text
                m = re.search(r'"url"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
                if m:
                    pu = m.group(1).replace('\\/', '/')
                    try:
                        pu = pu.encode().decode('unicode_escape')
                    except Exception:
                        pass
                    if pu.startswith('http'):
                        return {'parse': 0, 'url': pu,
                                'header': {'User-Agent': self.headers.get('User-Agent', 'Mozilla/5.0'),
                                           'Referer': self.host + '/'}}
        return {'parse': 1, 'url': url, 'header': {}}


if __name__ == '__main__':
    s = Spider()
    v = s.categoryContent('dianying', 1, False, {})
    print('电影:', len(v.get('list', [])), '条 | 总页:', v.get('pagecount'))
    if v.get('list'):
        d = s.detailContent([v['list'][0]['vod_id']])
        print('详情:', d['list'][0]['vod_name'], '|', d['list'][0]['vod_play_url'][:90])
