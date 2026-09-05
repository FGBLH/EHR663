# -*- coding: utf-8 -*-
import sys
import re
import json
import base64
import threading
import requests
import urllib3
import os
import time
import random
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import unquote, quote, urljoin, urlparse

urllib3.disable_warnings()
sys.path.append('..')
from base.spider import Spider as BaseSpider

# ==================== 本地代理（解决图片跨域/防盗链） ====================
_proxy_port = 0
_proxy_started = False
_proxy_session = requests.Session()
_proxy_session.verify = False
_proxy_headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://maomi66.cc/',
}

class _ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class _ProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            real_url = unquote(self.path[1:])
            if not real_url or not real_url.startswith('http'):
                self.send_response(404); self.end_headers(); return
            r = _proxy_session.get(real_url, headers=_proxy_headers, timeout=20, verify=False)
            ct = r.headers.get('Content-Type', 'image/jpeg')
            self.send_response(200)
            self.send_header('Content-Type', ct)
            self.send_header('Content-Length', len(r.content))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(r.content)
        except BrokenPipeError:
            pass
        except Exception:
            self.send_response(404); self.end_headers()

    def log_message(self, format, *args):
        pass

def _find_free_port():
    import socket
    sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sk.bind(('127.0.0.1', 0))
    port = sk.getsockname()[1]
    sk.close()
    return port

def _start_proxy():
    global _proxy_port, _proxy_started
    if _proxy_started:
        return
    _proxy_port = _find_free_port()
    server = _ThreadedHTTPServer(('127.0.0.1', _proxy_port), _ProxyHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _proxy_started = True

# ==================== Spider 主体 ====================
class Spider(BaseSpider):
    session = requests.Session()
    host = 'https://maomi66.cc'
    play_host = 'https://m.892539.xyz'

    def __init__(self):
        super().__init__()
        self._categories_cache = None
        self._debug = True

    def _log(self, msg):
        if self._debug:
            print(f'[maomi66] {msg}')

    def getName(self):
        return 'maomi66'

    def isVideoFormat(self, url):
        if not url:
            return False
        return '.m3u8' in url or '.mp4' in url or '.ts' in url

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def localProxy(self, param):
        return [404, 'text/plain', '']

    def init(self, extend=''):
        self.session.verify = False
        self.session.headers.update(self._get_headers())
        _start_proxy()
        text = self._fetch(self.host)
        if text:
            self._load_categories(text)

    def _get_headers(self, referer=None):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': referer or self.host + '/',
        }
        return headers

    def _proxy_url(self, url):
        if not url:
            return ''
        if url.startswith('http://127.0.0.1'):
            return url
        return f'http://127.0.0.1:{_proxy_port}/{quote(url, safe="")}'

    def _fetch(self, url, referer=None, retries=3):
        for i in range(retries):
            try:
                if referer is None:
                    referer = self.host + '/'
                headers = self._get_headers(referer)
                if i > 0:
                    time.sleep(random.uniform(0.5, 1.5))
                r = self.session.get(url, headers=headers, timeout=30, verify=False)
                r.encoding = 'utf-8'
                if r.status_code == 200:
                    text = r.text
                    if 'location.href' in text and ('请稍后' in text or '数据处理中' in text):
                        jump_match = re.search(r'location\.href\s*=\s*[\'"]([^\'"]+)[\'"]', text)
                        if jump_match:
                            jump_path = jump_match.group(1)
                            jump_url = urljoin(url, jump_path) if not jump_path.startswith('http') else jump_path
                            self._log(f'遇到跳转页，跟随至: {jump_url}')
                            r2 = self.session.get(jump_url, headers=headers, timeout=30, verify=False)
                            r2.encoding = 'utf-8'
                            if r2.status_code == 200:
                                return r2.text
                    return text
                elif r.status_code in [403, 429, 503]:
                    self._log(f'请求被拦截 [{r.status_code}]，重试 {i+1}/{retries}')
                else:
                    return ''
            except Exception as e:
                self._log(f'请求异常 [{e}]，重试 {i+1}/{retries}')
        return ''

    # ==================== 分类加载 ====================
    def _load_categories(self, text):
        if not text:
            return []
        cats = []
        seen = set()
        tid_blacklist = {
            '69799699', '69809699', '69819699', '69829699',
            '69839699', '69849699', '69859699', '69869699'
        }
        pattern = r'<a href="/list/(\d+)-1\.html"(?:[^>]*?)>([^<]+)</a>'
        for tid, name in re.findall(pattern, text):
            name = name.strip()
            if not name or name in seen:
                continue
            if tid in tid_blacklist:
                self._log(f'过滤分类: [{tid}] {name}')
                continue
            seen.add(name)
            cats.append({'type_id': tid, 'type_name': name})
        self._categories_cache = cats
        self._log(f'加载分类: {len(cats)} 个')
        return cats

    def _get_category_name(self, tid):
        for cat in self._categories_cache or []:
            if cat['type_id'] == tid:
                return cat['type_name']
        return tid

    # ==================== 列表解析 ====================
    def _parse_list(self, html):
        items = []
        li_blocks = re.findall(r'<li[^>]*>(.*?)</li>', html, re.S)
        for li in li_blocks:
            a_match = re.search(r'<a class="xx-thumb" href="(/(?:video|torrent)/([^"]+)\.html)"', li)
            if not a_match:
                continue
            href = a_match.group(1)
            vid = a_match.group(2)
            if href.startswith('/torrent/'):
                continue
            img_match = re.search(r'<img[^>]+data-original="([^"]+)"', li)
            pic = img_match.group(1) if img_match else ''
            title = vid
            h5_match = re.search(r'<h5><a[^>]*>(.*?)</a></h5>', li, re.S)
            if h5_match:
                title = re.sub(r'<[^>]+>', '', h5_match.group(1)).strip()
            items.append({
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': self._proxy_url(pic),
                'vod_remarks': '',
            })
        return items

    def _get_list(self, tid, page):
        url = f'{self.host}/list/{tid}-{page}.html'
        html = self._fetch(url, referer=f'{self.host}/list/{tid}-1.html')
        if not html:
            return []
        return self._parse_list(html)

    # ==================== 首页 ====================
    def homeContent(self, filter):
        try:
            text = self._fetch(self.host)
            if text:
                self._load_categories(text)
            cats = self._categories_cache or []
            return {
                'class': cats,
                'filters': {},
                'type': '影视',
                'list': [],
                'page': 1, 'pagecount': 1, 'limit': 0, 'total': 0
            }
        except Exception as e:
            self._log(f'homeContent 异常: {e}')
            return {'class': [], 'filters': {}, 'type': '影视', 'list': [], 'page': 1, 'pagecount': 1, 'limit': 0, 'total': 0}

    def homeVideoContent(self):
        return {'list': []}

    # ==================== 分类内容 ====================
    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg) if pg else 1
            items = self._get_list(tid, page)
            total_page = page + 1
            if page == 1:
                html = self._fetch(f'{self.host}/list/{tid}-1.html')
                if html:
                    pages = re.findall(r'/list/\d+-(\d+)\.html', html)
                    if pages:
                        total_page = max(int(p) for p in pages)
            return {
                'list': items, 'page': page, 'pagecount': total_page,
                'limit': len(items), 'total': total_page * len(items)
            }
        except Exception as e:
            self._log(f'categoryContent 异常: {e}')
            return {'list': [], 'page': 1, 'pagecount': 1, 'limit': 0, 'total': 0}

    # ==================== 详情页 ====================
    def _fetch_detail(self, vid):
        url = f'{self.host}/video/{vid}.html'
        self._log(f'获取详情: {url}')
        html = self._fetch(url, referer=self.host)
        if html:
            detail = self._parse_detail(html, vid, url)
            if detail and detail.get('vod_play_url'):
                return detail
        return None

    def _parse_detail(self, html, vid, base_url):
        title = ''
        m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
        if m:
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if not title:
            m = re.search(r'<title>([^<]+)</title>', html)
            if m:
                title = m.group(1).strip()

        cover = ''
        m = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', html)
        if m:
            cover = m.group(1)
        if not cover:
            m = re.search(r'<img[^>]+class="[^"]*cover[^"]*"[^>]+src="([^"]+)"', html, re.S)
            if m:
                cover = m.group(1)
        if not cover:
            m = re.search(r'data-original="([^"]+)"', html)
            if m:
                cover = m.group(1)

        play_urls = []
        seen = set()

        def add(label, url):
            if url in seen:
                return
            seen.add(url)
            play_urls.append(f'{label}${url}')

        site_id = ''
        source_id = ''

        comment_match = re.search(r'<!--\s*source_id:(\d+),\s*site_id:(\d+)', html)
        if comment_match:
            source_id = comment_match.group(1)
            site_id = comment_match.group(2)
            self._log(f'从注释提取: site_id={site_id}, source_id={source_id}')

        if not site_id or not source_id:
            hls_match = re.search(r'hls\.loadSource\([\'"]([^\'"]+)[\'"]\)', html)
            if hls_match:
                play_url = hls_match.group(1)
                sid_match = re.search(r'site_id=(\d+)', play_url)
                src_match = re.search(r'source_id=(\d+)', play_url)
                if sid_match and src_match:
                    site_id = sid_match.group(1)
                    source_id = src_match.group(1)
                    self._log(f'从HLS脚本提取: site_id={site_id}, source_id={source_id}')

        if not site_id:
            m_sid = re.search(r'site_id[=:]\s*(\d+)', html)
            if m_sid:
                site_id = m_sid.group(1)
        if not source_id:
            m_src = re.search(r'source_id[=:]\s*(\d+)', html)
            if m_src:
                source_id = m_src.group(1)

        if site_id and source_id:
            play_url = f'{self.play_host}/play.php?site_id={site_id}&source_id={source_id}'
            add('HLS直链', play_url)

        for media in set(re.findall(r'https?://[^\s"\'<>]+\.(?:m3u8|mp4|flv|mkv|ts)(?:\?[^\s"\'<>]*)?', html)):
            add('媒体直链', media)

        for src in set(re.findall(r'<iframe[^>]+(?:src|data-src)=["\']([^"\']+)["\']', html)):
            if any(k in src for k in ['play.php', 'm3u8', 'mp4', 'embed', 'player']):
                add('外链', src if src.startswith('http') else urljoin(base_url, src))

        scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.S)
        for script in scripts:
            for b64 in re.findall(r'["\']([A-Za-z0-9+/]{20,}={0,2})["\']', script):
                try:
                    dec = base64.b64decode(b64).decode('utf-8')
                    if dec.startswith('http') and any(x in dec for x in ['.m3u8', '.mp4', 'play.php']):
                        add('Base64', dec)
                except:
                    pass

        if not play_urls:
            add('默认线路', base_url)

        sources = []
        urls = []
        for pu in play_urls:
            sn, url = pu.split('$', 1)
            sources.append(sn)
            urls.append(f'{sn}${url}')

        return {
            'vod_id': vid,
            'vod_name': title or vid,
            'vod_pic': self._proxy_url(cover) if cover else '',
            'vod_play_from': '$$$'.join(sources) if sources else '默认',
            'vod_play_url': '#'.join(urls) if urls else f'默认${base_url}',
            'vod_content': title or '',
        }

    def detailContent(self, ids):
        try:
            vid = str(ids[0] if isinstance(ids, list) else ids)
            detail = self._fetch_detail(vid)
            if not detail:
                return {'list': []}
            return {'list': [detail]}
        except Exception as e:
            self._log(f'detailContent 异常: {e}')
            return {'list': []}

    # ==================== 播放器 ====================
    def playerContent(self, flag, id, vipFlags=None):
        try:
            if id and not id.startswith('http'):
                detail = self._fetch_detail(id)
                if detail and detail.get('vod_play_url'):
                    first = detail['vod_play_url'].split('#')[0]
                    if '$' in first:
                        id = first.split('$', 1)[1]
                    else:
                        id = first
            referer = self.host
            if id and id.startswith('http'):
                parsed = urlparse(id)
                if parsed.netloc:
                    referer = f'{parsed.scheme}://{parsed.netloc}/'
            return {
                'parse': 0,
                'url': id,
                'header': {
                    'Referer': referer,
                    'User-Agent': 'Mozilla/5.0',
                }
            }
        except Exception as e:
            self._log(f'playerContent 异常: {e}')
            return {'parse': 0, 'url': '', 'header': {}}

    # ==================== 搜索 ====================
    def searchContent(self, key, quick, pg='1'):
        try:
            page = int(pg) if pg else 1
            url = f'{self.host}/search.php?content={quote(key)}&type=1&page={page}'
            html = self._fetch(url, referer=self.host)
            items = self._parse_list(html) if html else []
            return {
                'list': items, 'page': page, 'pagecount': page + 1,
                'limit': len(items), 'total': page * len(items)
            }
        except Exception as e:
            self._log(f'searchContent 异常: {e}')
            return {'list': [], 'page': 1, 'pagecount': 1, 'limit': 0, 'total': 0}
