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

# ========================== 全局本地代理服务器 ==========================
# 用于解决图片防盗链、跨域问题，所有外域图片均通过 127.0.0.1 代理访问
_proxy_port = 0
_proxy_started = False
_proxy_session = requests.Session()
_proxy_session.verify = False
_proxy_headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Referer': 'https://dadiao.cc/',
}

class _ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

class _ProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            real_url = unquote(self.path[1:])
            if not real_url or not real_url.startswith('http'):
                self.send_response(404)
                self.end_headers()
                return
            parsed = urlparse(real_url)
            referer = f'{parsed.scheme}://{parsed.netloc}/' if parsed.netloc else 'https://dadiao.cc/'
            headers = dict(_proxy_headers)
            headers['Referer'] = referer
            r = _proxy_session.get(real_url, headers=headers, timeout=20, verify=False, stream=True)
            content_type = r.headers.get('Content-Type', 'image/jpeg')
            content_length = r.headers.get('Content-Length')
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            if content_length:
                self.send_header('Content-Length', content_length)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
            self.end_headers()
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    self.wfile.write(chunk)
        except BrokenPipeError:
            pass
        except Exception as e:
            try:
                self.send_response(404)
                self.end_headers()
            except:
                pass

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

# ========================== Spider 主体 ==========================
class Spider(BaseSpider):
    session = requests.Session()
    host = 'https://dadiao.cc'
    play_host = 'https://m.892539.xyz'

    def __init__(self):
        super().__init__()
        self._categories_cache = None
        self._zone_map = {}
        self._sub_cat_names = {}
        self._debug = True
        self._log('Spider 初始化完成')

    def _log(self, msg):
        if self._debug:
            print(f'[dadiao] {msg}')

    def getName(self):
        return 'dadiao'

    def isVideoFormat(self, url):
        if not url:
            return False
        return '.m3u8' in url or '.mp4' in url or '.ts' in url or url.startswith('magnet:')

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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': referer or self.host + '/',
        }
        return headers

    def _proxy_url(self, url):
        if not url:
            return ''
        if url.startswith('http://127.0.0.1'):
            return url
        if url.startswith('//'):
            url = 'https:' + url
        elif url.startswith('/'):
            url = urljoin(self.host, url)
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
                    self._log(f'请求返回 [{r.status_code}]，终止')
                    return ''
            except Exception as e:
                self._log(f'请求异常 [{e}]，重试 {i+1}/{retries}')
        return ''

    # ========================== 分类加载（蜜桃式：区域为class，子分类为filters） ==========================
    def _load_categories(self, text):
        if not text:
            self._log('首页HTML为空，无法加载分类')
            return []
        self._zone_map = {}
        self._sub_cat_names = {}

        # 按 zone-tag 与 cate-items 顺序配对提取
        zone_names = re.findall(r'<div class="zone-tag">\s*(.*?)\s*</div>', text)
        items_blocks = re.findall(r'<div class="cate-items">(.*?)</div>', text, re.S)

        if len(zone_names) == len(items_blocks) and len(zone_names) > 0:
            self._log(f'区域配对成功: {len(zone_names)} 个区域')
            for i, zone_name in enumerate(zone_names):
                zone_name = zone_name.strip()
                items_html = items_blocks[i]
                tids = []
                for tid, name in re.findall(r'<a href="/list/(\d+)-1\.html"[^>]*>([^<]+)</a>', items_html):
                    name = name.strip()
                    if not name:
                        continue
                    tids.append(tid)
                    self._sub_cat_names[tid] = name
                if tids:
                    self._zone_map[zone_name] = tids
                    self._log(f'区域[{zone_name}]: {len(tids)} 个子分类')
        else:
            self._log('区域配对失败，启用兜底提取')
            seen_tid = set()
            for tid, name in re.findall(r'<a href="/list/(\d+)-1\.html"[^>]*>([^<]+)</a>', text):
                name = name.strip()
                if not name or tid in seen_tid:
                    continue
                seen_tid.add(tid)
                self._sub_cat_names[tid] = name
            if self._sub_cat_names:
                all_tids = list(self._sub_cat_names.keys())
                self._zone_map['全部视频'] = all_tids
                self._log(f'兜底提取: {len(all_tids)} 个分类归入"全部视频"')

        self._categories_cache = list(self._zone_map.keys())
        self._log(f'分类加载完成: 共 {len(self._categories_cache)} 个区域')
        return self._categories_cache

    def _get_zone_tids(self, zone_name):
        return self._zone_map.get(zone_name, [])

    def _get_sub_name(self, tid):
        return self._sub_cat_names.get(tid, tid)

    # ========================== 列表解析（修复封面图片） ==========================
    def _parse_list(self, html):
        items = []
        li_blocks = re.findall(
            r'<li>\s*<a class="thumb-card" href="(/(?:video|torrent)/([^"]+)\.html)"[^>]*>.*?<div class="thumb-desc">.*?</div>\s*</li>',
            html, re.S
        )
        for href, vid in li_blocks:
            li_match = re.search(
                r'<li>\s*<a class="thumb-card" href="' + re.escape(href) + r'"[^>]*>.*?</a>\s*<div class="thumb-desc">.*?</div>\s*</li>',
                html, re.S
            )
            if not li_match:
                continue
            li_html = li_match.group(0)

            title = vid
            h5_match = re.search(r'<h5><a[^>]*>(.*?)</a></h5>', li_html, re.S)
            if h5_match:
                title = re.sub(r'<[^>]+>', '', h5_match.group(1)).strip()

            pic = ''
            pic_match = re.search(r'<img[^>]+data-original="([^"]+)"', li_html, re.S)
            if pic_match:
                pic = pic_match.group(1).strip()
            else:
                pic_match = re.search(r'<img[^>]+src="([^"]+)"', li_html, re.S)
                if pic_match:
                    pic = pic_match.group(1).strip()

            if pic and not pic.endswith('loading.svg') and not pic.endswith('loading.gif'):
                if pic.startswith('//'):
                    pic = 'https:' + pic
                elif pic.startswith('/'):
                    pic = urljoin(self.host, pic)
            else:
                pic = ''

            is_torrent = href.startswith('/torrent/')
            items.append({
                'vod_id': f'torrent_{vid}' if is_torrent else vid,
                'vod_name': title,
                'vod_pic': self._proxy_url(pic),
                'vod_remarks': '磁力' if is_torrent else '',
            })
        return items

    def _get_list(self, tid, page):
        url = f'{self.host}/list/{tid}-{page}.html'
        html = self._fetch(url, referer=f'{self.host}/list/{tid}-1.html')
        if not html:
            return []
        return self._parse_list(html)

    # ========================== 首页（蜜桃式：区域为class + 子分类filters） ==========================
    def homeContent(self, filter):
        try:
            text = self._fetch(self.host)
            if text:
                self._load_categories(text)

            classes = []
            filters = {}

            # 遍历所有区域，构建 class 和 filter
            for zone_name, tids in self._zone_map.items():
                # 区域作为一级分类
                zone_tid = 'zone:' + ','.join(tids)
                classes.append({'type_id': zone_tid, 'type_name': zone_name})

                # 该区域的子分类作为顶部筛选器
                sub_values = []
                for tid in tids:
                    sub_name = self._sub_cat_names.get(tid, tid)
                    sub_values.append({'n': sub_name, 'v': tid})
                if sub_values:
                    filters[zone_tid] = [
                        {
                            'key': 'sub',
                            'name': '子分类',
                            'value': sub_values
                        }
                    ]
                else:
                    filters[zone_tid] = []

            return {
                'class': classes,
                'filters': filters,
                'type': '影视',
                'list': [],
                'page': 1,
                'pagecount': 1,
                'limit': 0,
                'total': 0
            }
        except Exception as e:
            self._log(f'homeContent 异常: {e}')
            return {
                'class': [], 'filters': {}, 'type': '影视', 'list': [],
                'page': 1, 'pagecount': 1, 'limit': 0, 'total': 0
            }

    def homeVideoContent(self):
        return {'list': []}

    # ========================== 分类内容（蜜桃式路由分发） ==========================
    def categoryContent(self, tid, pg, filter, extend):
        try:
            # 兼容 TVBox 不同版本：extend 可能是 JSON 字符串
            if isinstance(extend, str):
                try:
                    extend = json.loads(extend)
                except:
                    extend = {}

            # 路由1：区域分类（tid 以 zone: 开头）
            if tid and tid.startswith('zone:'):
                tids = tid.replace('zone:', '').split(',')
                if extend and isinstance(extend, dict) and 'sub' in extend:
                    target_tid = extend['sub']
                    self._log(f'区域[{tid}] 选择子分类: {target_tid}')
                    return self._do_category(target_tid, pg)
                else:
                    # 默认显示该区域下第一个子分类
                    if tids:
                        self._log(f'区域[{tid}] 默认显示首个子分类: {tids[0]}')
                        return self._do_category(tids[0], pg)
                    return {'list': [], 'page': 1, 'pagecount': 1, 'limit': 0, 'total': 0}

            # 路由2：直接传入子分类ID（数字ID）
            else:
                self._log(f'直接加载子分类: {tid}')
                return self._do_category(tid, pg)

        except Exception as e:
            self._log(f'categoryContent 异常: {e}')
            return {
                'list': [], 'page': 1, 'pagecount': 1,
                'limit': 0, 'total': 0
            }

    def _do_category(self, tid, pg):
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
            'list': items,
            'page': page,
            'pagecount': total_page,
            'limit': len(items),
            'total': total_page * len(items)
        }

    # ========================== 详情页 ==========================
    def _fetch_detail(self, vid):
        if vid.startswith('torrent_'):
            real_id = vid.replace('torrent_', '')
            url = f'{self.host}/torrent/{real_id}.html'
            self._log(f'获取磁力详情: {url}')
            html = self._fetch(url, referer=self.host)
            if html:
                return self._parse_detail(html, vid, url, is_torrent=True)
            return None

        url = f'{self.host}/video/{vid}.html'
        self._log(f'获取视频详情: {url}')
        html = self._fetch(url, referer=self.host)
        if html:
            detail = self._parse_detail(html, vid, url)
            if detail and detail.get('vod_play_url'):
                return detail
        return None

    def _parse_detail(self, html, vid, base_url, is_torrent=False):
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
            cover = m.group(1).strip()
        if not cover:
            m = re.search(r'<img[^>]+class="[^"]*cover[^"]*"[^>]+src="([^"]+)"', html, re.S)
            if m:
                cover = m.group(1).strip()
        if not cover:
            m = re.search(r'<img[^>]+data-original="([^"]+)"', html)
            if m:
                cover = m.group(1).strip()
        if not cover:
            m = re.search(r'<video[^>]+poster="([^"]+)"', html)
            if m:
                cover = m.group(1).strip()

        if cover:
            if cover.startswith('//'):
                cover = 'https:' + cover
            elif cover.startswith('/'):
                cover = urljoin(self.host, cover)

        play_urls = []
        seen = set()

        def add(label, url):
            if not url or url in seen:
                return
            seen.add(url)
            play_urls.append(f'{label}${url}')

        if not is_torrent:
            # ==================== 视频解析逻辑 ====================
            site_id = ''
            source_id = ''

            # 1. 优先从页面底部 HTML 注释提取
            comment_match = re.search(r'<!--\s*source_id:(\d+),\s*site_id:(\d+)', html)
            if comment_match:
                source_id = comment_match.group(1)
                site_id = comment_match.group(2)
                self._log(f'从注释提取参数: site_id={site_id}, source_id={source_id}')

            # 2. 从 HLS.js 初始化脚本中提取
            if not site_id or not source_id:
                hls_match = re.search(
                    r'hls\.loadSource\([\'"](https?://[^\'"]+)[\'"]\)', html
                )
                if hls_match:
                    hls_url = hls_match.group(1)
                    sid_match = re.search(r'site_id=(\d+)', hls_url)
                    src_match = re.search(r'source_id=(\d+)', hls_url)
                    if sid_match and src_match:
                        site_id = sid_match.group(1)
                        source_id = src_match.group(1)
                        self._log(f'从HLS脚本提取: site_id={site_id}, source_id={source_id}')

            # 3. 从页面变量兜底提取
            if not site_id:
                m_sid = re.search(r'site_id[=:]\s*(\d+)', html)
                if m_sid:
                    site_id = m_sid.group(1)
            if not source_id:
                m_src = re.search(r'source_id[=:]\s*(\d+)', html)
                if m_src:
                    source_id = m_src.group(1)

            # 构建真实播放地址
            if site_id and source_id:
                play_url = f'{self.play_host}/play.php?site_id={site_id}&source_id={source_id}'
                add('HLS直链', play_url)

            # 4. 兜底：嗅探页面中直接出现的 m3u8/mp4 媒体链接
            for media in set(re.findall(
                r'https?://[^\s"\'<>]+\.(?:m3u8|mp4|flv|mkv|ts)(?:\?[^\s"\'<>]*)?', html
            )):
                add('媒体直链', media)

            # 5. 嗅探 iframe 嵌入播放器
            for src in set(re.findall(
                r'<iframe[^>]+(?:src|data-src)=["\']([^"\']+)["\']', html
            )):
                if any(k in src for k in ['play.php', 'm3u8', 'mp4', 'embed', 'player']):
                    full_src = src if src.startswith('http') else urljoin(base_url, src)
                    add('外链播放器', full_src)

            # 6. 嗅探 script 中的 Base64 加密链接
            scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.S)
            for script in scripts:
                for b64 in re.findall(r'["\']([A-Za-z0-9+/]{20,}={0,2})["\']', script):
                    try:
                        dec = base64.b64decode(b64).decode('utf-8')
                        if dec.startswith('http') and any(x in dec for x in ['.m3u8', '.mp4', 'play.php']):
                            add('Base64解码', dec)
                    except:
                        pass

            # 7. 最终兜底
            if not play_urls:
                add('默认线路', base_url)
        else:
            # ==================== 磁力解析（核心修复） ====================
            # 1. 优先解析 j_b64 JSON（该站点标准加密方式）
            b64_match = re.search(r"var j_b64\s*=\s*['\"]([A-Za-z0-9+/=]+)['\"]", html)
            if b64_match:
                try:
                    decoded = base64.b64decode(b64_match.group(1)).decode('utf-8')
                    j_data = json.loads(decoded)
                    if 'tm' in j_data and j_data['tm']:
                        add('磁力链接', j_data['tm'])
                        self._log(f'从 j_b64 解析到磁力: {j_data["tm"]}')
                    if 'tt' in j_data and j_data['tt']:
                        add('种子文件', j_data['tt'])
                        self._log(f'从 j_b64 解析到种子: {j_data["tt"]}')
                except Exception as e:
                    self._log(f'解析 j_b64 失败: {e}')

            # 2. 正则兜底匹配页面中的磁力链接
            if not play_urls:
                magnets = set(re.findall(r'magnet:\?xt=urn:btih:[A-Za-z0-9]+[^\s"\'<>]*', html))
                href_magnets = re.findall(r'href=["\'](magnet:\?xt=urn:btih:[^"\']+)["\']', html)
                for hm in href_magnets:
                    decoded = unquote(hm)
                    if decoded.startswith('magnet:'):
                        magnets.add(decoded)
                for mag in magnets:
                    add('磁力链接', mag)

            # 3. 尝试从页面提取 40 位 hash 构造磁力（极端兜底）
            if not play_urls:
                hash_match = re.search(r'[A-Fa-f0-9]{40}', html)
                if hash_match:
                    hash40 = hash_match.group(0)
                    add('磁力链接', f'magnet:?xt=urn:btih:{hash40}')
                    self._log(f'从 hash 构造磁力: {hash40}')

        # ==================== 组装结果 ====================
        sources = []
        urls = []
        for pu in play_urls:
            parts = pu.split('$', 1)
            if len(parts) == 2:
                sn, url = parts
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
            if vid.startswith('magnet:'):
                return {
                    'list': [{
                        'vod_id': vid,
                        'vod_name': '磁力资源',
                        'vod_pic': '',
                        'vod_play_from': '磁力链接',
                        'vod_play_url': f'磁力链接${vid}'
                    }]
                }
            detail = self._fetch_detail(vid)
            if not detail:
                return {'list': []}
            return {'list': [detail]}
        except Exception as e:
            self._log(f'detailContent 异常: {e}')
            return {'list': []}

    # ========================== 播放器 ==========================
    def playerContent(self, flag, id, vipFlags=None):
        try:
            # 磁力链接直接透传，交给 TVBox 内置下载器或第三方 App
            if id.startswith('magnet:'):
                return {
                    'parse': 0,
                    'url': id,
                    'header': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    }
                }

            # 若传入的是纯 vid（非完整 URL），自动解析一次真实播放地址
            if id and not id.startswith('http') and not id.startswith('magnet:'):
                detail = self._fetch_detail(id)
                if detail and detail.get('vod_play_url'):
                    first = detail['vod_play_url'].split('#')[0]
                    if '$' in first:
                        id = first.split('$', 1)[1]
                    else:
                        id = first

            # 根据目标域名动态设置 Referer，降低被拦截概率
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
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
                }
            }
        except Exception as e:
            self._log(f'playerContent 异常: {e}')
            return {
                'parse': 0,
                'url': '',
                'header': {}
            }

    # ========================== 搜索 ==========================
    def searchContent(self, key, quick, pg='1'):
        try:
            page = int(pg) if pg else 1
            all_items = []

            # 先搜索视频（type=1）
            url = f'{self.host}/search.php?content={quote(key)}&type=1&page={page}'
            self._log(f'搜索视频: {url}')
            html = self._fetch(url, referer=self.host)
            if html:
                items = self._parse_list(html)
                all_items.extend(items)

            # 如果视频无结果，再搜索磁力（type=2）
            if not all_items:
                url = f'{self.host}/search.php?content={quote(key)}&type=2&page={page}'
                self._log(f'搜索磁力: {url}')
                html = self._fetch(url, referer=self.host)
                if html:
                    items = self._parse_list(html)
                    all_items.extend(items)

            return {
                'list': all_items,
                'page': page,
                'pagecount': page + 1,
                'limit': len(all_items),
                'total': page * len(all_items)
            }
        except Exception as e:
            self._log(f'searchContent 异常: {e}')
            return {
                'list': [], 'page': 1, 'pagecount': 1,
                'limit': 0, 'total': 0
            }
