# -*- coding: utf-8 -*-
import sys, re, json, base64, threading, time
import requests, urllib3
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import unquote, quote, urljoin, parse_qs

urllib3.disable_warnings()
sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider: pass

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

# ===== 图片代理（解决防盗链） =====
_proxy_port = 0
_proxy_started = False
_proxy_session = requests.Session()
_proxy_session.verify = False

class _ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class _ProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            real_url = unquote(self.path[1:])
            if not real_url or not real_url.startswith('http'):
                self.send_response(404)
                self.end_headers()
                return
            r = _proxy_session.get(real_url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://wknd.sjzstv.sbs/'
            }, timeout=20, verify=False)
            ct = r.headers.get('Content-Type', 'image/jpeg')
            self.send_response(200)
            self.send_header('Content-Type', ct)
            self.send_header('Content-Length', len(r.content))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(r.content)
        except Exception:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass

def _start_proxy():
    global _proxy_port, _proxy_started
    if _proxy_started:
        return
    import socket
    sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sk.bind(('127.0.0.1', 0))
    _proxy_port = sk.getsockname()[1]
    sk.close()
    server = _ThreadedHTTPServer(('127.0.0.1', _proxy_port), _ProxyHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _proxy_started = True

# ===== Spider =====
class Spider(BaseSpider):
    session = requests.Session()
    HOST = 'https://wknd.sjzstv.sbs'
    # 若域名失效，可通过 extend 参数传入新域名，例如: {"host":"https://新域名.com"}
    
    # 对应源码 <nav class="ploughs"> 中的分类
    DEFAULT_CATEGORIES = [
        {'type_id': '480', 'type_name': '日韩有码'},
        {'type_id': '481', 'type_name': '日韩无码'},
        {'type_id': '483', 'type_name': '中文字幕'},
        {'type_id': '482', 'type_name': '欧美情色'},
        {'type_id': '479', 'type_name': '国产情色'},
        {'type_id': '484', 'type_name': '网红主播'},
        {'type_id': '1505', 'type_name': '卡通动漫'},
    ]

    # 源码底部 jsjiami 混淆使用的字符映射表（用于扩展解密）
    DECODE_MAP = {
        'e': 'P', 'w': 'D', 'T': 'y', '+': 'J', 'l': '!', 't': 'L', 'E': 'E',
        '@': '2', 'd': 'a', 'b': '%', 'q': 'l', 'X': 'v', '~': 'R', '5': 'r',
        '&': 'X', 'C': 'j', ']': 'F', 'a': ')', '^': 'm', ',': '~', '}': '1',
        'x': 'C', 'c': '(', 'G': '@', 'h': 'h', '.': '*', 'L': 's', '=': ',',
        'p': 'g', 'I': 'Q', '1': '7', '_': 'u', 'K': '6', 'F': 't', '2': 'n',
        '8': '=', 'k': 'G', 'Z': ']', ')': 'b', 'P': '}', 'B': 'U', 'S': 'k',
        '6': 'i', 'g': ':', 'N': 'N', 'i': 'S', '%': '+', '-': 'Y', '?': '|',
        '4': 'z', '*': '-', '3': '^', '[': '{', '(': 'c', 'u': 'B', 'y': 'M',
        'U': 'Z', 'H': '[', 'z': 'K', '9': 'H', '7': 'f', 'R': 'x', 'v': '&',
        '!': ';', 'M': '_', 'Q': '9', 'Y': 'e', 'o': '4', 'r': 'A', 'm': '.',
        'O': 'o', 'V': 'W', 'J': 'p', 'f': 'd', ':': 'q', '{': '8', 'W': 'I',
        'j': '?', 'n': '5', 's': '3', '|': 'T', 'A': 'V', 'D': 'w', ';': 'O'
    }

    def __init__(self):
        super().__init__()
        self._debug = True
        self._categories_cache = list(self.DEFAULT_CATEGORIES)
        self._log(f'当前域名: {self.HOST}')

    def _log(self, msg):
        if self._debug:
            print(f'[sjzstv] {msg}')

    def getName(self):
        return 'sjzstv'

    def isVideoFormat(self, url):
        return '.m3u8' in url or '.mp4' in url or '.ts' in url or url.startswith('magnet:')

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def localProxy(self, param):
        return [404, 'text/plain', '']

    def init(self, extend=''):
        if extend:
            try:
                ext = json.loads(extend) if isinstance(extend, str) else extend
                if ext.get('host'):
                    self.HOST = ext['host'].rstrip('/')
                    self._log(f'通过 extend 切换域名: {self.HOST}')
            except Exception as e:
                self._log(f'extend 解析失败: {e}')
        self.session.verify = False
        self.session.headers.update(self._get_headers())
        _start_proxy()

    def _get_headers(self, referer=None):
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': referer or (self.HOST + '/')
        }

    def _proxy_url(self, url):
        if not url:
            return ''
        if url.startswith('http://127.0.0.1'):
            return url
        if url.startswith('//'):
            url = 'https:' + url
        return f'http://127.0.0.1:{_proxy_port}/{quote(url, safe="")}'

    # ===== 解码解密（对应源码底部 jsjiami 混淆逻辑） =====
    def _decode(self, cipher_text):
        """字符替换解码，若网站视频地址采用此类混淆可自动还原"""
        try:
            return ''.join(self.DECODE_MAP.get(ch, ch) for ch in cipher_text)
        except Exception as e:
            self._log(f'解码失败: {e}')
            return cipher_text

    def _try_base64_decode(self, s):
        """尝试 Base64 解码"""
        try:
            if re.match(r'^[A-Za-z0-9+/=]+$', s) and len(s) % 4 == 0:
                return base64.b64decode(s).decode('utf-8')
        except Exception:
            pass
        return ''

    # ===== HTML 请求 =====
    def _fetch_html(self, path='', params=None):
        url = self.HOST
        if path:
            url = f'{self.HOST}{path}' if path.startswith('/') else f'{self.HOST}/{path}'
        try:
            r = self.session.get(url, params=params, headers=self._get_headers(), timeout=15)
            r.raise_for_status()
            return r.text
        except Exception as e:
            self._log(f'请求失败: {url} - {e}')
            return ''

    # ===== 列表解析（适配源码 .small.likes 结构） =====
    def _parse_list(self, html):
        items = []
        if not html:
            return items, {}

        page_info = {'page': 1, 'pages': 1, 'total': 0}

        if HAS_BS4:
            soup = BeautifulSoup(html, 'html.parser')
            container = soup.find('div', class_='enslave')
            if not container:
                container = soup

            videos = container.find_all('div', class_='small likes')
            self._log(f'BS4 解析到 {len(videos)} 个视频项')

            for v in videos:
                a = v.find('a', class_='depraved')
                if not a:
                    continue
                href = a.get('href', '')
                title = a.get('title', '')
                m = re.search(r'detail=(\d+)', href)
                if not m:
                    continue
                vid = m.group(1)

                img = a.find('img', class_='lazy')
                pic = img.get('original', '') if img else ''
                if not pic and img:
                    pic = img.get('src', '')

                chicks = a.find('span', class_='chicks')
                hits = chicks.get_text(strip=True).replace(' ', '') if chicks else ''

                shoving = a.find('div', class_='shoving')
                if shoving and not title:
                    title = shoving.get_text(strip=True)

                items.append({
                    'vod_id': vid,
                    'vod_name': title or f'视频_{vid}',
                    'vod_pic': self._proxy_url(pic),
                    'vod_remarks': hits
                })

            # 分页解析
            pager = soup.find('div', class_='chode')
            if pager:
                cur = pager.find('a', class_='dqy')
                if cur:
                    try:
                        page_info['page'] = int(cur.get_text(strip=True))
                    except Exception:
                        pass
                last = pager.find('a', class_='wyym')
                if last:
                    try:
                        page_info['pages'] = int(last.get_text(strip=True))
                    except Exception:
                        pass
                else:
                    nums = []
                    for a in pager.find_all('a', class_='fyym'):
                        try:
                            nums.append(int(a.get_text(strip=True)))
                        except Exception:
                            pass
                    if nums:
                        page_info['pages'] = max(nums)
        else:
            # 无 BS4 回退到正则
            self._log('未安装 BeautifulSoup，使用正则回退解析')
            for block in re.findall(r'<div class="small likes">(.*?)</div>\s*</div>', html, re.S):
                m_id = re.search(r'detail=(\d+)', block)
                if not m_id:
                    continue
                vid = m_id.group(1)

                m_title = re.search(r'title="([^"]+)"', block)
                title = m_title.group(1) if m_title else ''

                m_pic = re.search(r'original="([^"]+)"', block)
                if not m_pic:
                    m_pic = re.search(r'src="([^"]+)"', block)
                pic = m_pic.group(1) if m_pic else ''

                m_hits = re.search(r'<span class="chicks">.*?(\d+)</span>', block)
                hits = m_hits.group(1) + '次播放' if m_hits else ''

                if not title:
                    m_shoving = re.search(r'<div class="shoving">(.*?)</div>', block, re.S)
                    title = re.sub(r'<[^>]+>', '', m_shoving.group(1)).strip() if m_shoving else ''

                items.append({
                    'vod_id': vid,
                    'vod_name': title or f'视频_{vid}',
                    'vod_pic': self._proxy_url(pic),
                    'vod_remarks': hits
                })

            m_pages = re.findall(r'page=(\d+)', html)
            if m_pages:
                page_info['pages'] = max(int(p) for p in m_pages)

        page_info['total'] = len(items)
        return items, page_info

    # ===== 首页 / 分类 =====
    def homeContent(self, filter):
        cats = self._categories_cache
        html = self._fetch_html('/', {'mod': 'videos', 'cateid': cats[0]['type_id'], 'page': 1})
        items, page_info = self._parse_list(html) if html else ([], {})
        return {
            'class': cats,
            'filters': {},
            'type': '影视',
            'list': items,
            'page': 1,
            'pagecount': page_info.get('pages', 1),
            'limit': len(items),
            'total': page_info.get('total', len(items))
        }

    def homeVideoContent(self):
        html = self._fetch_html('/')
        items, _ = self._parse_list(html) if html else ([], {})
        return {'list': items}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        html = self._fetch_html('/', {'mod': 'videos', 'cateid': tid, 'page': page})
        items, page_info = self._parse_list(html) if html else ([], {})
        return {
            'list': items,
            'page': page,
            'pagecount': page_info.get('pages', page + 1),
            'limit': len(items),
            'total': page_info.get('total', len(items))
        }

    # ===== 详情页（多策略提取播放地址 + 解密扩展） =====
    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, list) else ids)
        html = self._fetch_html('/', {'mod': 'videos', 'detail': vid})

        if not html:
            return {'list': [{
                'vod_id': vid,
                'vod_name': f'视频_{vid}',
                'vod_pic': '',
                'vod_play_from': '在线播放',
                'vod_play_url': f'线路1${self.HOST}/?mod=videos&detail={vid}',
                'vod_content': ''
            }]}

        title = f'视频_{vid}'
        pic = ''
        play_url = ''

        # 1. 提取标题
        m_title = re.search(r'<title>(.*?)</title>', html, re.S)
        if m_title:
            title = m_title.group(1).split('-')[0].strip()

        # 2. 提取封面
        m_og_img = re.search(r'<meta[^>]+og:image[^>]+content="([^"]+)"', html, re.S)
        if m_og_img:
            pic = m_og_img.group(1)

        # 3. 多策略提取视频地址
        # 3.1 video / source 标签
        m_video = re.search(r'<video[^>]*>.*?<source[^>]+src="([^"]+)"', html, re.S)
        if not m_video:
            m_video = re.search(r'<video[^>]+src="([^"]+)"', html, re.S)
        if m_video:
            play_url = m_video.group(1)

        # 3.2 iframe 嵌入
        if not play_url:
            m_iframe = re.search(r'<iframe[^>]+src="([^"]+)"', html, re.S)
            if m_iframe:
                src = m_iframe.group(1)
                play_url = src if src.startswith('http') else urljoin(self.HOST, src)

        # 3.3 直链匹配 m3u8 / mp4
        if not play_url:
            m_m3u8 = re.search(r'(https?://[^\s"\'<>]+\.m3u8)', html)
            if m_m3u8:
                play_url = m_m3u8.group(1)

        if not play_url:
            m_mp4 = re.search(r'(https?://[^\s"\'<>]+\.mp4)', html)
            if m_mp4:
                play_url = m_mp4.group(1)

        # 3.4 JS 变量中常见的 url / video_url
        if not play_url:
            m_jsurl = re.search(r'var\s+(?:video_)?url\s*=\s*["\']([^"\']+)["\']', html)
            if m_jsurl:
                cand = m_jsurl.group(1)
                if cand.startswith('http'):
                    play_url = cand

        # 3.5 Base64 编码的地址
        if not play_url:
            for b64 in re.findall(r'["\']([A-Za-z0-9+/=]{20,})["\']', html):
                decoded = self._try_base64_decode(b64)
                if decoded and (decoded.startswith('http') or '.m3u8' in decoded):
                    play_url = decoded
                    self._log(f'Base64 解码出地址: {play_url}')
                    break

        # 3.6 字符映射解密（对应源码底部混淆）
        if not play_url:
            # 若页面存在类似源码中的混淆字符串，尝试解码
            for cipher in re.findall(r'["\']([a-zA-Z0-9_+\-~!@#$%^&*(){}\[\]|\\:;<>,.?/]{30,})["\']', html):
                decoded = self._decode(cipher)
                if decoded.startswith('http') and ('.m3u8' in decoded or '.mp4' in decoded):
                    play_url = decoded
                    self._log(f'映射解码出地址: {play_url}')
                    break

        # 兜底：返回详情页让壳子解析
        if not play_url or not self.isVideoFormat(play_url):
            play_url = f'{self.HOST}/?mod=videos&detail={vid}'

        detail = {
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': self._proxy_url(pic),
            'vod_play_from': '在线播放',
            'vod_play_url': f'线路1${play_url}',
            'vod_content': title,
        }
        return {'list': [detail]}

    # ===== 播放器 =====
    def playerContent(self, flag, id, vipFlags=None):
        self._log(f'playerContent: {id[:150] if len(id) > 150 else id}')

        # 已经是直链
        if '.m3u8' in id or '.mp4' in id or '.ts' in id:
            return {
                'parse': 0,
                'url': id,
                'header': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Referer': self.HOST + '/'
                }
            }

        # 若传入的是详情页链接，重新提取
        if 'detail=' in id:
            vid_match = re.search(r'detail=(\d+)', id)
            if vid_match:
                vid = vid_match.group(1)
                data = self.detailContent([vid])
                if data and data.get('list'):
                    info = data['list'][0]
                    pu = info.get('vod_play_url', '')
                    if '$' in pu:
                        pu = pu.split('$')[1]
                    if pu and self.isVideoFormat(pu):
                        return {
                            'parse': 0,
                            'url': pu,
                            'header': {
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                                'Referer': self.HOST + '/'
                            }
                        }

        # 兜底：让壳子解析
        return {
            'parse': 1,
            'url': id,
            'header': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': self.HOST + '/'
            }
        }

    # ===== 搜索 =====
    def searchContent(self, key, quick, pg='1'):
        page = int(pg) if pg else 1
        html = self._fetch_html('/', {'mod': 'videos', 'wd': key, 'page': page})
        items, page_info = self._parse_list(html) if html else ([], {})
        return {
            'list': items,
            'page': page,
            'pagecount': page_info.get('pages', page + 1),
            'limit': len(items),
            'total': page_info.get('total', len(items))
        }
