# -*- coding: utf-8 -*-
"""
站点：大鸡鸡 dajiji.sbs (ccc.djj88.sbs)
"""

import sys
import re
import json
import base64
import threading
import requests
import urllib3
import time
import random
from urllib.parse import unquote, quote, urljoin, urlparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

urllib3.disable_warnings()
sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def __init__(self): pass

# ═══════════════════════════════════════════════════
# 阵字秘 · 本地图片代理服务器（照搬黄色仓库大阵）
# ═══════════════════════════════════════════════════
_proxy_port = 0
_proxy_started = False
_proxy_session = requests.Session()
_proxy_session.verify = False
_proxy_headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://ccc.djj88.sbs/',
    'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
}

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
            r = _proxy_session.get(real_url, headers=_proxy_headers, timeout=20, verify=False)
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
    if _proxy_started:
        return
    _proxy_port = _find_free_port()
    server = _ThreadedHTTPServer(('127.0.0.1', _proxy_port), _ProxyHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _proxy_started = True

# ═══════════════════════════════════════════════════
# Spider · 道宫境修士
# ═══════════════════════════════════════════════════
class Spider(BaseSpider):
    session = requests.Session()

    HOSTS = [
        'https://ccc.djj88.sbs',
    ]

    # 临字秘 · 兜底分类（从导航菜单提取）
    DEFAULT_CATEGORIES = [
        {'type_id': '91探花', 'type_name': '91探花'},
        {'type_id': '国产色情', 'type_name': '国产色情'},
        {'type_id': '萝莉少女', 'type_name': '萝莉少女'},
        {'type_id': '网曝门', 'type_name': '网曝门'},
        {'type_id': '主播直播', 'type_name': '主播直播'},
        {'type_id': '自拍偷拍', 'type_name': '自拍偷拍'},
        {'type_id': 'cosplay', 'type_name': 'Cosplay'},
        {'type_id': '网红流出', 'type_name': '网红流出'},
        {'type_id': '素人自拍', 'type_name': '素人自拍'},
        {'type_id': '强奸乱伦', 'type_name': '强奸乱伦'},
        {'type_id': '日本精品', 'type_name': '日本精品'},
        {'type_id': '亚洲有码', 'type_name': '亚洲有码'},
        {'type_id': '多人多P', 'type_name': '多人多P'},
    ]

    def __init__(self):
        super().__init__()
        self._debug = True
        self._categories_cache = list(self.DEFAULT_CATEGORIES)
        self.host = self.HOSTS[0]
        self._log(f'【道宫境】初始化完成，当前域名: {self.host}')

    def _log(self, msg):
        if self._debug:
            print(f'[dajiji] {msg}')

    def getName(self):
        return 'dajiji'

    def isVideoFormat(self, url):
        if not url:
            return False
        url = url.lower()
        return any(fmt in url for fmt in ['.m3u8', '.mp4', '.flv', '.ts', 'magnet:', '.mkv'])

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
        # 尝试抓取首页更新分类
        text = self._fetch(self.host + '/')
        if text:
            self._update_categories(text)
        else:
            self._log('警告: 首页无法访问，使用兜底分类')

    def _get_headers(self, referer=None):
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': referer or self.host + '/',
        }

    def _proxy_url(self, url):
        """阵字秘 · 图片走本地代理"""
        if not url:
            return ''
        if url.startswith('http://127.0.0.1'):
            return url
        return f'http://127.0.0.1:{_proxy_port}/{quote(url, safe="")}'

    def _fetch(self, url, referer=None, retries=3):
        """临字秘 · 带重试的请求"""
        if not url.startswith('http'):
            url = urljoin(self.host, url)
        for attempt in range(retries):
            try:
                headers = self._get_headers(referer or self.host + '/')
                r = self.session.get(url, headers=headers, timeout=15, verify=False)
                if r.status_code == 200:
                    r.encoding = 'utf-8'
                    self._log(f'请求成功: {url} (长度:{len(r.text)})')
                    return r.text
                else:
                    self._log(f'状态码异常: {r.status_code} {url}')
            except Exception as e:
                self._log(f'请求失败 [{attempt+1}]: {url} - {e}')
            time.sleep(1)
        return ''

    def _update_categories(self, text):
        """从首页导航提取分类"""
        seen = {c['type_id'] for c in self._categories_cache}
        # 匹配导航菜单
        nav_match = re.search(r'<ul[^>]*class=["\'][^"\']*menu-111[^"\']*["\'][^>]*>(.*?)</ul>', text, re.S)
        if nav_match:
            links = re.findall(
                r'<a[^>]+href=["\']https://ccc\.djj88\.sbs/s/category/([^"\']+)["\'][^>]*>(.*?)</a>',
                nav_match.group(1), re.S
            )
            self._log(f'导航菜单提取到 {len(links)} 个分类')
            for slug, raw_name in links:
                name = re.sub(r'<[^>]+>', '', raw_name).strip()
                # slug 可能是 URL 编码的，解码作为 type_id
                try:
                    tid = unquote(slug)
                except:
                    tid = slug
                if not name or name in ['首页']:
                    continue
                if tid not in seen:
                    self._categories_cache.append({'type_id': tid, 'type_name': name})
                    seen.add(tid)
        self._log(f'当前分类总数: {len(self._categories_cache)}')

    # ═══════════════════════════════════════════════════
    # 斗字秘 · 列表解析
    # ═══════════════════════════════════════════════════
    def _parse_list(self, html):
        """解析文章列表"""
        items = []
        seen_ids = set()

        # WordPress 文章卡片：article.blog-article > div.post-item
        articles = re.findall(r'<article[^>]*class="blog-article[^"]*"[^>]*>(.*?)</article>', html, re.S)
        self._log(f'匹配到 {len(articles)} 个 article')

        if not articles:
            # fallback：直接匹配 post-item
            articles = re.findall(r'<div[^>]*class="post-item[^"]*"[^>]*>(.*?)</div><!-- \.post-item -->', html, re.S)

        for art in articles:
            # 提取文章ID和链接
            id_match = re.search(r'<div[^>]*class="[^"]*post-(\d+)[^"]*"[^>]*>', art)
            href_match = re.search(r'<a[^>]+href="(https://ccc\.djj88\.sbs/s/\d+\.htm)"', art)
            if not href_match:
                continue

            href = href_match.group(1)
            vid = id_match.group(1) if id_match else href.split('/')[-1].replace('.htm', '')

            if vid in seen_ids:
                continue
            seen_ids.add(vid)

            # 标题
            title = ''
            t_match = re.search(r'<h2[^>]*class="entry-title"[^>]*>.*?<a[^>]*>(.*?)</a>', art, re.S)
            if t_match:
                title = re.sub(r'<[^>]+>', '', t_match.group(1)).strip()

            # 封面图（走 img.886345.xyz 代理，需要再走本地代理）
            pic = ''
            img_match = re.search(r'<img[^>]+src="([^"]+)"', art)
            if img_match:
                pic = img_match.group(1)
                # 如果已经是代理地址，直接拿去再走一层本地代理
                if pic.startswith('//'):
                    pic = 'https:' + pic

            # 分类标签作为备注
            remarks = ''
            cat_match = re.search(r'<div[^>]*class="cat-links"[^>]*>.*?<a[^>]*>(.*?)</a>', art, re.S)
            if cat_match:
                remarks = re.sub(r'<[^>]+>', '', cat_match.group(1)).strip()

            items.append({
                'vod_id': vid,
                'vod_name': title or vid,
                'vod_pic': self._proxy_url(pic),
                'vod_remarks': remarks,
            })

        self._log(f'解析出 {len(items)} 个视频条目')
        return items

    def _get_list(self, tid, page):
        """获取分类/首页列表"""
        if tid and tid != '首页':
            # 分类页：/s/category/xxx/page/2
            slug = quote(tid, safe='')
            url = f'{self.host}/s/category/{slug}/'
            if page > 1:
                url += f'page/{page}/'
        else:
            # 首页
            url = self.host + '/'
            if page > 1:
                url += f'page/{page}/'

        html = self._fetch(url, referer=self.host + '/')
        if not html:
            return []
        return self._parse_list(html)

    # ═══════════════════════════════════════════════════
    # TVBox 标准接口
    # ═══════════════════════════════════════════════════
    def homeContent(self, filter):
        text = self._fetch(self.host + '/')
        if text:
            self._update_categories(text)

        cats = self._categories_cache
        items = self._get_list(cats[0]['type_id'] if cats else '首页', 1) if cats else []
        return {
            'class': cats,
            'filters': {},
            'type': '影视',
            'list': items,
            'page': 1,
            'pagecount': 1,
            'limit': len(items),
            'total': len(items)
        }

    def homeVideoContent(self):
        if self._categories_cache:
            return {'list': self._get_list(self._categories_cache[0]['type_id'], 1)}
        return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        items = self._get_list(tid, page)
        # WordPress 分页：有下一页就 pagecount = page + 1
        has_next = len(items) >= 10  # 通常每页10篇
        return {
            'list': items,
            'page': page,
            'pagecount': page + 1 if has_next else page,
            'limit': len(items),
            'total': page + 1 if has_next else page
        }

    # ═══════════════════════════════════════════════════
    # 者字秘 · 详情页多层解析（兜底）
    # ═══════════════════════════════════════════════════
    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, list) else ids)
        detail = self._fetch_detail(vid)
        return {'list': [detail]} if detail else {'list': []}

    def _fetch_detail(self, vid):
        url = f'{self.host}/s/{vid}.htm'
        html = self._fetch(url, referer=self.host + '/')
        if not html:
            return None
        return self._parse_detail(html, vid, url)

    def _parse_detail(self, html, vid, page_url):
        # 标题
        title = ''
        t_match = re.search(r'<h1[^>]*class="entry-title"[^>]*>(.*?)</h1>', html, re.S)
        if not t_match:
            t_match = re.search(r'<h2[^>]*class="entry-title"[^>]*>.*?<a[^>]*>(.*?)</a>', html, re.S)
        if t_match:
            title = re.sub(r'<[^>]+>', '', t_match.group(1)).strip()

        # 封面
        cover = ''
        c_match = re.search(r'<img[^>]+class="[^"]*wp-post-image[^"]*"[^>]+src="([^"]+)"', html)
        if not c_match:
            c_match = re.search(r'<img[^>]+src="([^"]+)"[^>]*class="[^"]*wp-post-image', html)
        if c_match:
            cover = c_match.group(1)
            if cover.startswith('//'):
                cover = 'https:' + cover

        # ═══════════════════════════════════════════════════
        # 兵字秘 · 视频地址提取（13层策略回退）
        # ═══════════════════════════════════════════════════
        play_url = ''
        play_from = '在线播放'

        try:
            # 第1层：直接 video 标签
            v_match = re.search(r'<video[^>]+src="([^"]+\.(?:m3u8|mp4))"', html)
            if v_match:
                play_url = v_match.group(1)

            # 第2层：source 标签
            if not play_url:
                s_match = re.search(r'<source[^>]+src="([^"]+\.(?:m3u8|mp4))"', html)
                if s_match:
                    play_url = s_match.group(1)

            # 第3层：iframe 嵌入（B站、优酷、第三方等）
            if not play_url:
                iframe_match = re.search(r'<iframe[^>]+src="([^"]+)"', html)
                if iframe_match:
                    play_url = iframe_match.group(1)
                    play_from = 'iframe解析'

            # 第4层：script 中找 m3u8/mp4
            if not play_url:
                script_match = re.search(r'["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)["\']', html)
                if script_match:
                    play_url = script_match.group(1)

            # 第5层：a 标签 magnet
            if not play_url:
                magnet_match = re.search(r'href="(magnet:[^"]+)"', html)
                if magnet_match:
                    play_url = magnet_match.group(1)
                    play_from = '磁力链接'

            # 第6层：通用播放器变量（如 player_aaaa）
            if not play_url:
                player_match = re.search(r'var\s+player_[a-zA-Z]+\s*=\s*({.+?});', html)
                if player_match:
                    try:
                        pdata = json.loads(player_match.group(1))
                        if pdata.get('url'):
                            play_url = pdata['url']
                            play_from = 'player变量'
                    except:
                        pass

            # 第7层：Base64 编码的视频地址
            if not play_url:
                b64_match = re.search(r'["\']([A-Za-z0-9+/]{40,}={0,2})["\']', html)
                if b64_match:
                    try:
                        decoded = base64.b64decode(b64_match.group(1)).decode('utf-8')
                        if decoded.startswith('http') and any(fmt in decoded for fmt in ['.m3u8', '.mp4', 'http']):
                            play_url = decoded
                            play_from = 'base64解码'
                    except:
                        pass

        except Exception as e:
            self._log(f'视频提取异常: {e}')

        # 如果什么都没找到，返回文章页本身让TVBox尝试二次解析
        if not play_url:
            play_url = page_url
            play_from = '文章页'

        # 处理相对路径
        if play_url and play_url.startswith('/'):
            play_url = urljoin(self.host, play_url)

        return {
            'vod_id': vid,
            'vod_name': title or vid,
            'vod_pic': self._proxy_url(cover),
            'vod_play_from': play_from,
            'vod_play_url': f'第1集${play_url}',
            'vod_content': title or '',
        }

    def playerContent(self, flag, id, vipFlags=None):
        if not id:
            return {'parse': 1, 'url': '', 'header': ''}

        # 如果是 iframe 或文章页，交给 TVBox 解析
        if 'iframe' in flag or '文章页' in flag:
            return {
                'parse': 1,
                'url': id,
                'header': {'User-Agent': 'Mozilla/5.0', 'Referer': self.host + '/'}
            }

        # 直链直接播放
        if id.startswith('http'):
            return {
                'parse': 0,
                'url': id,
                'header': {'User-Agent': 'Mozilla/5.0', 'Referer': self.host + '/'}
            }

        return {'parse': 1, 'url': id, 'header': ''}

    # ═══════════════════════════════════════════════════
    # 列字秘 · 搜索
    # ═══════════════════════════════════════════════════
    def searchContent(self, key, quick, pg='1'):
        page = int(pg) if pg else 1
        # WordPress 搜索：/?s=关键词
        url = f'{self.host}/?s={quote(key)}'
        if page > 1:
            url += f'&paged={page}'

        html = self._fetch(url, referer=self.host + '/')
        items = self._parse_list(html) if html else []
        has_next = len(items) >= 10
        return {
            'list': items,
            'page': page,
            'pagecount': page + 1 if has_next else page,
            'limit': len(items),
            'total': page + 1 if has_next else page
        }
