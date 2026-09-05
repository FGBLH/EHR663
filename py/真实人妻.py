# -*- coding: utf-8 -*-
import sys
import re
import json
import base64
import threading
import requests
import urllib3
import time
import random
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import unquote, quote, urljoin, urlparse

urllib3.disable_warnings()
sys.path.append('..')
from base.spider import Spider as BaseSpider

# ===== 本地代理（用于图片防盗链）=====
_proxy_port = 0
_proxy_started = False
_proxy_session = requests.Session()
_proxy_session.verify = False
_proxy_headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://zsrqab03.zsrenqi.xyz/',
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
        except BrokenPipeError: pass
        except Exception:
            self.send_response(404); self.end_headers()
    def log_message(self, format, *args): pass
def _find_free_port():
    import socket
    sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sk.bind(('127.0.0.1', 0))
    port = sk.getsockname()[1]
    sk.close()
    return port
def _start_proxy():
    global _proxy_port, _proxy_started
    if _proxy_started: return
    _proxy_port = _find_free_port()
    server = _ThreadedHTTPServer(('127.0.0.1', _proxy_port), _ProxyHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _proxy_started = True

# ===== Spider =====
class Spider(BaseSpider):
    session = requests.Session()
    host = 'https://zsrqab03.zsrenqi.xyz'

    def __init__(self):
        super().__init__()
        self._categories_cache = None
        self._debug = True

    def _log(self, msg):
        if self._debug:
            print(f'[zsrenqi] {msg}')

    def getName(self):
        return '真实人妻'
    
    def isVideoFormat(self, url):
        if not url or not isinstance(url, str):
            return False
        # 只认明确的视频扩展名，且必须是 http 开头
        return url.startswith('http') and any(ext in url for ext in ['.m3u8', '.mp4', '.ts', '.flv', '.mkv'])
    
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
                    return r.text
                elif r.status_code in [403, 429, 503]:
                    self._log(f'请求被拦截 [{r.status_code}]，重试 {i+1}/{retries}')
                else:
                    return ''
            except Exception as e:
                self._log(f'请求异常 [{e}]，重试 {i+1}/{retries}')
        return ''

    # ===== 分类加载（完整版）=====
    def _load_categories(self, text):
        if not text:
            return
        cats = []
        seen = set()
        cats.append({'type_id': 'home', 'type_name': '首页'})
        seen.add('home')

        pattern = r'<div class="row-item[^"]*">\s*<div class="row-item-title[^"]*">\s*<a href="(/index\.php/vod/type/id/(\d+)\.html)"[^>]*>([^<]+)</a>'
        for href, tid, name in re.findall(pattern, text, re.S):
            if tid in seen:
                continue
            seen.add(tid)
            cats.append({'type_id': tid, 'type_name': name.strip()})

        if len(cats) <= 2:
            alt_pattern = r'<a[^>]+href="(/index\.php/vod/type/id/(\d+)\.html)"[^>]*>([^<]+)</a>'
            for href, tid, name in re.findall(alt_pattern, text, re.S):
                if tid in seen or 'https' in href or '外链' in name:
                    continue
                seen.add(tid)
                cats.append({'type_id': tid, 'type_name': name.strip()})

        self._categories_cache = cats
        self._log(f'加载分类: {len(cats)} 个')

    # ===== 列表解析 =====
    def _parse_items(self, html):
        items = []
        pattern = r'<li\s+class="content-item">\s*<a[^>]+href="(/index\.php/vod/detail/id/(\d+)\.html)"[^>]*>.*?<img[^>]+data-original="([^"]+)"[^>]*>.*?</a>\s*<div\s+class="title">\s*<h5[^>]*>\s*<a[^>]*>([^<]+)</a>'
        for href, vid, pic, title in re.findall(pattern, html, re.S):
            items.append({
                'vod_id': vid,
                'vod_name': title.strip(),
                'vod_pic': self._proxy_url(pic) if pic.startswith('http') else pic,
                'vod_remarks': '',
            })
        return items

    def _get_list(self, tid, page):
        if page == 1:
            url = f'{self.host}/index.php/vod/type/id/{tid}.html'
        else:
            url = f'{self.host}/index.php/vod/type/id/{tid}.html?page={page}'
        html = self._fetch(url, referer=f'{self.host}/index.php/vod/type/id/{tid}.html')
        if not html and page > 1:
            url = f'{self.host}/index.php/vod/type/id/{tid}/page/{page}.html'
            html = self._fetch(url, referer=f'{self.host}/index.php/vod/type/id/{tid}.html')
        if not html:
            return []
        return self._parse_items(html)

    # ===== 详情解析（提取线路播放页）=====
    def _fetch_detail(self, vid):
        url = f'{self.host}/index.php/vod/detail/id/{vid}.html'
        self._log(f'获取详情: {url}')
        html = self._fetch(url, referer=self.host)
        if not html:
            return None
        return self._parse_detail(html, vid, url)

    def _parse_detail(self, html, vid, base_url):
        # 标题
        title = ''
        m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
        if m:
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if not title:
            m = re.search(r'<title>([^<]+)</title>', html)
            if m:
                raw_title = m.group(1).strip()
                title = re.split(r'\s*[-–|]\s*', raw_title)[0].strip()
        if not title:
            title = vid

        # 封面
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

        # 提取所有线路播放页链接（如 /index.php/vod/play/id/xxx/sid/1/nid/1.html）
        play_links = []
        pattern = r'href=["\'](/index\.php/vod/play/id/\d+/sid/\d+/nid/\d+\.html)["\']'
        for link in set(re.findall(pattern, html)):
            full = urljoin(base_url, link)
            if full.startswith('http'):
                play_links.append(full)

        # 若没有，尝试构造默认线路
        if not play_links:
            play_links.append(f'{self.host}/index.php/vod/play/id/{vid}/sid/1/nid/1.html')

        # 组装播放串（线路名以“线路一、线路二”命名）
        sources = []
        urls = []
        for idx, play_url in enumerate(play_links, 1):
            label = f'线路{idx}'
            sources.append(label)
            urls.append(f'{label}${play_url}')

        play_from = '$$$'.join(sources)
        play_url = '#'.join(urls)

        return {
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': self._proxy_url(cover) if cover else '',
            'vod_play_from': play_from,
            'vod_play_url': play_url,
            'vod_content': title,
        }

    # ===== 首页、分类、详情、搜索 =====
    def homeContent(self, filter):
        try:
            text = self._fetch(self.host)
            if text and self._categories_cache is None:
                self._load_categories(text)
            cats = self._categories_cache or []
            home_list = self._parse_items(text) if text else []
            return {
                'class': cats,
                'filters': {},
                'type': '影视',
                'list': home_list,
                'page': 1,
                'pagecount': 1,
                'limit': len(home_list),
                'total': len(home_list)
            }
        except Exception as e:
            self._log(f'homeContent 异常: {e}')
            return {'class': [], 'filters': {}, 'type': '影视', 'list': [], 'page': 1, 'pagecount': 1, 'limit': 0, 'total': 0}

    def homeVideoContent(self):
        return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            if tid.startswith('search_'):
                keyword = tid[7:]
                return self.searchContent(keyword, False, pg)
            if tid == 'home':
                html = self._fetch(self.host)
                items = self._parse_items(html) if html else []
                return {'list': items, 'page': 1, 'pagecount': 1, 'limit': len(items), 'total': len(items)}
            else:
                page = int(pg) if pg else 1
                items = self._get_list(tid, page)
                total_page = page + 1
                if page == 1:
                    first_html = self._fetch(f'{self.host}/index.php/vod/type/id/{tid}.html')
                    if first_html:
                        pages = re.findall(r'/page/(\d+)\.html', first_html)
                        if not pages:
                            pages = re.findall(r'[?&]page=(\d+)', first_html)
                        if pages:
                            total_page = max(int(p) for p in pages)
                return {'list': items, 'page': page, 'pagecount': total_page, 'limit': len(items), 'total': total_page * len(items)}
        except Exception as e:
            self._log(f'categoryContent 异常: {e}')
            return {'list': [], 'page': 1, 'pagecount': 1, 'limit': 0, 'total': 0}

    def detailContent(self, ids):
        try:
            vid = str(ids[0] if isinstance(ids, list) else ids)
            detail = self._fetch_detail(vid)
            if not detail:
                detail = {'vod_id': vid, 'vod_name': vid, 'vod_pic': '', 'vod_play_from': '无', 'vod_play_url': '无$'}
            return {'list': [detail]}
        except Exception as e:
            self._log(f'detailContent 异常: {e}')
            return {'list': []}

    # ===== 播放器（关键：返回 parse=1 让 TVBox 解析播放页）=====
    def playerContent(self, flag, id, vipFlags=None):
        try:
            if not id:
                return {'parse': 0, 'url': '', 'header': {}}
            # 如果 id 是数字，则取第一个线路播放页
            if id.isdigit():
                detail = self._fetch_detail(id)
                if detail and detail.get('vod_play_url'):
                    first_line = detail['vod_play_url'].split('#')[0]
                    if '$' in first_line:
                        play_url = first_line.split('$', 1)[1]
                    else:
                        play_url = first_line
                    id = play_url
            # 如果 id 是播放页（以 .html 结尾），则让 TVBox 解析
            if id.endswith('.html') and id.startswith('http'):
                # 返回 parse=1，让 TVBox 自动解析该播放页
                return {
                    'parse': 1,
                    'url': id,
                    'header': {
                        'Referer': self.host,
                        'User-Agent': 'Mozilla/5.0',
                    }
                }
            # 否则直接播放（可能是视频地址）
            referer = self.host
            if id.startswith('http'):
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

    def searchContent(self, key, quick, pg='1'):
        try:
            page = int(pg) if pg else 1
            url = f'{self.host}/index.php/vod/search.html?wd={quote(key)}&page={page}'
            html = self._fetch(url, referer=self.host)
            items = self._parse_items(html) if html else []
            return {'list': items, 'page': page, 'pagecount': page + 1, 'limit': len(items), 'total': page * len(items)}
        except Exception as e:
            self._log(f'searchContent 异常: {e}')
            return {'list': [], 'page': 1, 'pagecount': 1, 'limit': 0, 'total': 0}