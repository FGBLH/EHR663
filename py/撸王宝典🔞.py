# -*- coding: utf-8 -*-
import sys, re, json, base64, threading, time
import requests, urllib3
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import unquote, quote, urljoin

urllib3.disable_warnings()
sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider: pass

# ===== 图片代理（解决防盗链） =====
_proxy_port = 0; _proxy_started = False
_proxy_session = requests.Session()
_proxy_session.verify = False
class _ThreadedHTTPServer(ThreadingMixIn, HTTPServer): daemon_threads = True
class _ProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            real_url = unquote(self.path[1:])
            if not real_url or not real_url.startswith('http'):
                self.send_response(404); self.end_headers(); return
            r = _proxy_session.get(real_url, headers={
                'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer':'https://s7t8u9v0.luwangi.cc/'
            }, timeout=20, verify=False)
            ct = r.headers.get('Content-Type','image/jpeg')
            self.send_response(200); self.send_header('Content-Type',ct)
            self.send_header('Content-Length',len(r.content))
            self.send_header('Access-Control-Allow-Origin','*')
            self.end_headers(); self.wfile.write(r.content)
        except:
            self.send_response(404); self.end_headers()
    def log_message(self, format, *args): pass

def _start_proxy():
    global _proxy_port, _proxy_started
    if _proxy_started: return
    import socket
    sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sk.bind(('127.0.0.1',0)); _proxy_port = sk.getsockname()[1]; sk.close()
    server = _ThreadedHTTPServer(('127.0.0.1',_proxy_port), _ProxyHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _proxy_started = True

# ===== Spider =====
class Spider(BaseSpider):
    session = requests.Session()
    HOST = 'https://s7t8u9v0.luwangi.cc'
    API_BASE = '/api'
    # AES 解密参数（从网站 JS 逆向提取）
    AES_KEY = b'a9yX32LpQvUt7wBc'
    AES_IV = b'N7cPk2Bv38hWqFzM'

    DEFAULT_CATEGORIES = [
        {'type_id':'2292','type_name':'日本精品'},{'type_id':'2291','type_name':'日本无码'},
        {'type_id':'2290','type_name':'欧美性爱'},{'type_id':'2289','type_name':'超清系列'},
        {'type_id':'2288','type_name':'异族风情'},{'type_id':'2287','type_name':'女优明星'},
        {'type_id':'2286','type_name':'中文字幕'},{'type_id':'2285','type_name':'成人动漫'},
        {'type_id':'2284','type_name':'SM调教'},{'type_id':'2283','type_name':'精品推荐'},
        {'type_id':'2282','type_name':'国产色情'},{'type_id':'2281','type_name':'自拍偷拍'},
        {'type_id':'2280','type_name':'探花约炮'},{'type_id':'2279','type_name':'丝袜制服'},
        {'type_id':'2278','type_name':'国内换脸'},{'type_id':'2277','type_name':'多人群交'},
        {'type_id':'2276','type_name':'反差母狗'},{'type_id':'2275','type_name':'野战车震'},
        {'type_id':'2274','type_name':'会所技师'},{'type_id':'2273','type_name':'学生嫩穴'},
        {'type_id':'2272','type_name':'淫妻绿帽'},{'type_id':'2271','type_name':'乱伦毁三观'},
        {'type_id':'2270','type_name':'网曝黑料'},{'type_id':'2269','type_name':'主播网红'},
        {'type_id':'2268','type_name':'传媒精品'},{'type_id':'2267','type_name':'麻豆视频'},
        {'type_id':'2266','type_name':'91制片厂'},{'type_id':'2265','type_name':'天美传媒'},
        {'type_id':'2264','type_name':'蜜桃传媒'},{'type_id':'2263','type_name':'皇家华人'},
        {'type_id':'2262','type_name':'星空传媒'},{'type_id':'2261','type_name':'焦点影业'},
        {'type_id':'2260','type_name':'海角社区'},{'type_id':'2259','type_name':'成人头条'},
        {'type_id':'2258','type_name':'乌鸦传媒'},{'type_id':'2257','type_name':'兔子先生'},
        {'type_id':'2256','type_name':'杏吧原创'},{'type_id':'2255','type_name':'玩偶姐姐'},
        {'type_id':'2254','type_name':'MINI传媒'},{'type_id':'2253','type_name':'大象传媒'},
        {'type_id':'2252','type_name':'开心鬼传媒'},{'type_id':'2251','type_name':'psycho'},
        {'type_id':'2250','type_name':'糖心vlog'},{'type_id':'2249','type_name':'萝莉社'},
        {'type_id':'2248','type_name':'性视界'},
    ]

    def __init__(self):
        super().__init__()
        self._debug = True
        self._categories_cache = list(self.DEFAULT_CATEGORIES)
        self._log(f'当前域名: {self.HOST}')

    def _log(self, msg):
        if self._debug: print(f'[luwangi] {msg}')

    def getName(self): return 'luwangi'
    def isVideoFormat(self, url):
        return '.m3u8' in url or '.mp4' in url or '.ts' in url or url.startswith('magnet:')
    def manualVideoCheck(self): return False
    def destroy(self): pass
    def localProxy(self, param): return [404, 'text/plain', '']

    def init(self, extend=''):
        self.session.verify = False
        self.session.headers.update(self._get_headers())
        _start_proxy()

    def _get_headers(self, referer=None):
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': referer or (self.HOST + '/')
        }

    def _proxy_url(self, url):
        if not url: return ''
        if url.startswith('http://127.0.0.1'): return url
        if url.startswith('//'): url = 'https:' + url
        return f'http://127.0.0.1:{_proxy_port}/{quote(url, safe="")}'

    # ===== AES 解密（核心） =====
    def _decrypt(self, cipher_b64):
        try:
            cipher_bytes = base64.b64decode(cipher_b64)
            cipher = AES.new(self.AES_KEY, AES.MODE_CBC, self.AES_IV)
            plaintext = unpad(cipher.decrypt(cipher_bytes), AES.block_size)
            return json.loads(plaintext.decode('utf-8'))
        except Exception as e:
            self._log(f'解密失败: {e}')
            return None

    # ===== API 请求 + 自动解密 =====
    def _api_get(self, path, params=None, referer=None):
        url = f'{self.HOST}{self.API_BASE}{path}'
        try:
            r = self.session.get(url, params=params, headers=self._get_headers(referer), timeout=15)
            if r.status_code != 200:
                self._log(f'API 错误: {r.status_code} {url}')
                return None
            resp = r.json()
            if 'cipher' in resp:
                decrypted = self._decrypt(resp['cipher'])
                if decrypted is None:
                    return None
                if isinstance(decrypted, dict):
                    if 'data' in decrypted:
                        return decrypted['data']
                    return decrypted
                return decrypted
            if isinstance(resp, dict) and 'data' in resp:
                return resp['data']
            return resp
        except Exception as e:
            self._log(f'API 请求失败: {url} - {e}')
            return None

    # ===== 列表解析 =====
    def _parse_api_list(self, data):
        items = []
        if not isinstance(data, dict):
            return items
        video_list = data.get('list', [])
        page_info = {
            'page': data.get('page', 1),
            'ps': data.get('ps', 20),
            'total': data.get('total', 0),
            'pages': data.get('pages', 1)
        }
        self._log(f'API 返回 {len(video_list)} 条视频, 总页数 {page_info["pages"]}, 总数 {page_info["total"]}')

        for v in video_list:
            vid = str(v.get('id', ''))
            if not vid:
                continue
            title = v.get('title', f'视频_{vid}')
            pic = v.get('cover_url', '')
            hits = v.get('hits', 0)
            created = v.get('created_at', '').replace('T', ' ').split('+')[0]
            category = v.get('category', '')
            remarks = f'{hits}次播放' if hits else ''
            if created:
                remarks = f'{remarks} | {created}' if remarks else created
            if category:
                remarks = f'{category} | {remarks}' if remarks else category

            items.append({
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': self._proxy_url(pic),
                'vod_remarks': remarks
            })
        return items, page_info

    # ===== 首页 / 分类 =====
    def homeContent(self, filter):
        cats = self._categories_cache
        # 【修复】参数名改为 category_id
        data = self._api_get('/videos', {'category_id': cats[0]['type_id'], 'page': 1})
        items, page_info = self._parse_api_list(data) if data else ([], {})
        return {
            'class': cats, 'filters': {}, 'type': '影视',
            'list': items, 'page': 1,
            'pagecount': page_info.get('pages', 1),
            'limit': page_info.get('ps', 20),
            'total': page_info.get('total', len(items))
        }

    def homeVideoContent(self):
        if self._categories_cache:
            data = self._api_get('/videos', {'category_id': self._categories_cache[0]['type_id'], 'page': 1})
            items, _ = self._parse_api_list(data) if data else ([], {})
            return {'list': items}
        return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        # 【修复】参数名改为 category_id
        data = self._api_get('/videos', {'category_id': tid, 'page': page})
        items, page_info = self._parse_api_list(data) if data else ([], {})
        return {
            'list': items, 'page': page,
            'pagecount': page_info.get('pages', page + 1),
            'limit': page_info.get('ps', 20),
            'total': page_info.get('total', len(items))
        }

    # ===== 详情 =====
    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, list) else ids)
        data = self._api_get('/movie', {'id': vid})
        if not data or not isinstance(data, dict):
            return {'list': [{
                'vod_id': vid, 'vod_name': f'视频_{vid}',
                'vod_pic': '', 'vod_play_from': '在线播放',
                'vod_play_url': f'线路1${self.HOST}/play/?id={vid}&from_path=/',
                'vod_content': ''
            }]}

        info = data.get('info', {})
        title = info.get('title', f'视频_{vid}')
        pic = info.get('cover_url', '')
        play_url = info.get('play_url', '')
        play_from = info.get('play_from', 'm3u8')
        desc = info.get('title', '')

        # 构造播放地址
        if play_url and self.isVideoFormat(play_url):
            play_url_str = f'{play_from}${play_url}'
        else:
            play_url_str = f'线路1${self.HOST}/play/?id={vid}&from_path=/'

        detail = {
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': self._proxy_url(pic),
            'vod_play_from': play_from if play_from else '在线播放',
            'vod_play_url': play_url_str,
            'vod_content': desc,
            'vod_remarks': f'{info.get("hits", 0)}次播放',
        }
        return {'list': [detail]}

    # ===== 播放器 =====
    def playerContent(self, flag, id, vipFlags=None):
        self._log(f'playerContent: {id[:150] if len(id) > 150 else id}')

        # 已经是直链
        if '.m3u8' in id or '.mp4' in id or '.ts' in id:
            return {'parse': 0, 'url': id, 'header': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': self.HOST + '/'
            }}

        # 如果 id 是详情页链接，提取 vid 重新请求 API
        vid_match = re.search(r'[?&]id=(\d+)', id)
        if vid_match:
            vid = vid_match.group(1)
            data = self._api_get('/movie', {'id': vid})
            if data and isinstance(data, dict):
                info = data.get('info', {})
                play_url = info.get('play_url', '')
                if play_url and self.isVideoFormat(play_url):
                    return {'parse': 0, 'url': play_url, 'header': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Referer': self.HOST + '/'
                    }}

        # 兜底：让壳子解析
        return {'parse': 1, 'url': id, 'header': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': self.HOST + '/'
        }}

    # ===== 搜索 =====
    def searchContent(self, key, quick, pg='1'):
        page = int(pg) if pg else 1
        data = self._api_get('/videos', {'kw': key, 'page': page})
        items, page_info = self._parse_api_list(data) if data else ([], {})
        return {
            'list': items, 'page': page,
            'pagecount': page_info.get('pages', page + 1),
            'limit': page_info.get('ps', 20),
            'total': page_info.get('total', len(items))
        }
