# -*- coding: utf-8 -*-
"""
3av.app 在线观看脚本
基于 maccms 模板架构
支持自动获取分类 / 使用内置分类
新增：排行榜、女优大全（二级分类直接展示在顶部分类条，竖向列表，带随机影片封面）
      首页排行与推荐动态随机
修复：排行榜封面、女优作品列表展示、女优大全子分类、搜索URL格式
新增：Qinav 完整 m3u8 去广告清洗 + 蜜桃式分类结构
"""
import sys, re, json, base64, threading, time, random
import requests, urllib3
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import unquote, quote, urljoin, urlparse

urllib3.disable_warnings()
sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider: pass

# ===== 图片代理 =====
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
            r = _proxy_session.get(
                real_url,
                headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.3av.app/'},
                timeout=20,
                verify=False
            )
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

    # 主域名
    HOST = 'https://www.3av.app'

    # 内置默认分类（女优子分类直接作为独立分类项，不再用 filters 横滑）
    DEFAULT_CATEGORIES = [
        {'type_id': 'rank', 'type_name': '排行榜'},
        {'type_id': 'nvyou', 'type_name': '全部女优'},
        {'type_id': 'nvyou_国产AV女优', 'type_name': '国产AV女优'},
        {'type_id': 'nvyou_国产AV传媒', 'type_name': '国产AV传媒'},
        {'type_id': 'nvyou_香港三级电影女明星', 'type_name': '香港三级电影女明星'},
        {'type_id': 'nvyou_韩国三级电影女明星', 'type_name': '韩国三级电影女明星'},
        {'type_id': 'nvyou_热门分类', 'type_name': '热门分类'},
        {'type_id': 'nvyou_日本女优', 'type_name': '日本女优'},
        {'type_id': '1', 'type_name': '国产福利'},
        {'type_id': '2', 'type_name': '国产自拍'},
        {'type_id': '3', 'type_name': '国产偷拍'},
        {'type_id': '4', 'type_name': '国产探花'},
        {'type_id': '5', 'type_name': '国产主播'},
        {'type_id': '6', 'type_name': '丝袜美腿'},
        {'type_id': '7', 'type_name': '人妻少妇'},
        {'type_id': '8', 'type_name': '港台美女'},
        {'type_id': '9', 'type_name': '明星换脸'},
        {'type_id': '10', 'type_name': '网红黑料'},
        {'type_id': '11', 'type_name': '国产口交'},
        {'type_id': '12', 'type_name': '国产群交'},
        {'type_id': '13', 'type_name': '麻豆传媒'},
        {'type_id': '14', 'type_name': '角色扮演'},
        {'type_id': '15', 'type_name': '国产乱伦'},
        {'type_id': '16', 'type_name': '绿帽换妻'},
        {'type_id': '17', 'type_name': '野战激情'},
        {'type_id': '18', 'type_name': '国产TS'},
        {'type_id': '20', 'type_name': '亚洲福利'},
        {'type_id': '21', 'type_name': '日韩福利'},
        {'type_id': '22', 'type_name': '欧美福利'},
        {'type_id': '23', 'type_name': '中文字幕'},
        {'type_id': '24', 'type_name': '三级伦理'},
        {'type_id': '25', 'type_name': '动漫福利'},
        {'type_id': '26', 'type_name': '制服丝袜'},
        {'type_id': '27', 'type_name': '童颜巨乳'},
        {'type_id': '28', 'type_name': '强奸乱伦'},
        {'type_id': '29', 'type_name': '人妻熟女'},
        {'type_id': '30', 'type_name': '少女萝莉'},
        {'type_id': '31', 'type_name': '口交群交'},
        {'type_id': '32', 'type_name': '另类调教'},
        {'type_id': '33', 'type_name': '男同女同'},
        {'type_id': '34', 'type_name': '名人素人'},
    ]

    def __init__(self):
        super().__init__()
        self._debug = True
        self._categories_cache = list(self.DEFAULT_CATEGORIES)
        self.host = self.HOST
        self._nvyou_cache = []
        self._nvyou_loaded = False
        self._nvyou_cover_cache = {}   # 女优封面缓存
        self._rank_pic_cache = {}
        self._log(f'当前域名: {self.host}')

    def _log(self, msg):
        if self._debug:
            print(f'[3av] {msg}')

    def getName(self):
        return '3av'

    def isVideoFormat(self, url):
        return '.m3u8' in url or '.mp4' in url or '.ts' in url or url.startswith('magnet:')

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    # ---------- 本地代理：清洗 m3u8 ----------
    def localProxy(self, param):
        """处理 type=m3u8 的代理请求，返回清洗后的 m3u8"""
        try:
            if not isinstance(param, dict):
                param = {}
            ptype = param.get('type') or param.get('action') or param.get('do')
            url = param.get('url', '')
            if ptype != 'm3u8' or not url:
                return [404, "text/plain", "not found"]
            referer = param.get('referer', '') or self.host
            if isinstance(url, list):
                url = url[0]
            if isinstance(referer, list):
                referer = referer[0]
            url = unquote(url)
            referer = unquote(referer)
            raw_m3u8 = self._get_m3u8_content(url, referer)
            if not raw_m3u8:
                return [404, "text/plain", "m3u8 download failed"]
            cleaned = self._clean_m3u8(raw_m3u8, url, referer)
            return [200, "application/vnd.apple.mpegurl", cleaned]
        except Exception as e:
            self._log(f'localProxy error: {e}')
            return [404, "text/plain", "proxy error"]

    # ===== 初始化 =====
    def init(self, extend=''):
        self.session.verify = False
        self.session.headers.update(self._get_headers())
        _start_proxy()
        text = self._fetch(self.host + '/')
        if text and len(text) > 2000:
            self._update_categories(text)
        else:
            self._log('首页加载失败，使用默认分类')

    def _get_headers(self, referer=None):
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': referer or (self.host + '/')
        }

    def _proxy_url(self, url):
        if not url:
            return ''
        if url.startswith('http://127.0.0.1'):
            return url
        return f'http://127.0.0.1:{_proxy_port}/{quote(url, safe="")}'

    def _fetch(self, url, referer=None, retries=3):
        if not url.startswith('http'):
            url = urljoin(self.host, url)
        for attempt in range(retries):
            try:
                headers = self._get_headers(referer or self.host + '/')
                r = self.session.get(url, headers=headers, timeout=15, verify=False)
                if r.status_code == 200 and len(r.text) > 500:
                    r.encoding = 'utf-8'
                    self._log(f'请求成功: {url} (长度:{len(r.text)})')
                    return r.text
                else:
                    self._log(f'请求内容过短: {url} 长度:{len(r.text) if r.text else 0}')
            except Exception as e:
                self._log(f'请求失败 [{attempt+1}]: {url} - {e}')
            time.sleep(1)
        return ''

    def _update_categories(self, text):
        seen_ids = {c['type_id'] for c in self._categories_cache}
        seen_names = {c['type_name'] for c in self._categories_cache}

        links = re.findall(
            r'<a[^>]+class="text-333"[^>]+href="/vodtype/(\d+)\.html"[^>]*>([^<]+)</a>',
            text
        )
        links += re.findall(
            r'<a[^>]+href="/vodtype/(\d+)\.html"[^>]*>([^<]+)</a>',
            text
        )

        new_cats = []
        for tid, raw_name in links:
            name = re.sub(r'<[^>]+>', '', raw_name).strip()
            if not name or name in ['首页', '留言', '求片', 'APP', '专题', '排行榜', '最新', '永久网址']:
                continue
            if tid not in seen_ids and name not in seen_names:
                new_cats.append({'type_id': tid, 'type_name': name})
                seen_ids.add(tid)
                seen_names.add(name)

        if new_cats:
            self._categories_cache.extend(new_cats)
            self._log(f'自动获取到 {len(new_cats)} 个新分类')

    def _get_category_name(self, tid):
        for cat in self._categories_cache:
            if cat['type_id'] == str(tid):
                return cat['type_name']
        return f'分类_{tid}'

    # ===== 通用列表解析 =====
    def _parse_list(self, html):
        items, seen_vids = [], set()
        cards = re.findall(r'<li[^>]*class="[^"]*col-[^"]*"[^>]*>(.*?)</li>', html, re.S)
        if not cards:
            cards = re.findall(r'<li[^>]*>(.*?)</li>', html, re.S)

        for card in cards:
            a_match = re.search(r'<a[^>]+href="([^"]+)"[^>]*title="([^"]*)"', card)
            if not a_match:
                a_match = re.search(r'<a[^>]+href="([^"]+)"', card)
                if not a_match:
                    continue
                href = a_match.group(1).strip()
                title = ''
            else:
                href = a_match.group(1).strip()
                title = a_match.group(2).strip()

            if not href.startswith('/vodplay/'):
                continue

            vid_match = re.search(r'/vodplay/(\d+)', href)
            if not vid_match:
                continue
            vid = vid_match.group(1)
            if vid in seen_vids:
                continue
            seen_vids.add(vid)

            if not title:
                h4 = re.search(r'<h4[^>]*>.*?<a[^>]*>(.*?)</a>', card, re.S)
                if h4:
                    title = re.sub(r'<[^>]+>', '', h4.group(1)).strip()
            if not title:
                title = f'视频_{vid}'

            pic = ''
            img = re.search(r'data-original="([^"]+)"', card)
            if img:
                pic = img.group(1)
                if pic.startswith('//'):
                    pic = 'https:' + pic
                elif pic.startswith('/'):
                    pic = self.host + pic

            remarks = ''
            date_match = re.search(r'<span>(\d{2}-\d{2})</span>', card)
            if date_match:
                remarks = date_match.group(1)
            else:
                remark_match = re.search(r'class="pic-text[^"]*">(.*?)</span>', card, re.S)
                if remark_match:
                    remarks = re.sub(r'<[^>]+>', '', remark_match.group(1)).strip()

            items.append({
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': self._proxy_url(pic),
                'vod_remarks': remarks
            })

        self._log(f'解析到 {len(items)} 个视频')
        return items

    def _get_list(self, tid, page):
        url = f'{self.host}/vodtype/{tid}-{page}.html'
        html = self._fetch(url, referer=f'{self.host}/vodtype/{tid}-1.html')
        return self._parse_list(html) if html else []

    # ===== 排行榜解析（修复封面：从style中提取background图片） =====
    def _parse_rank(self, html):
        items, seen_vids = [], set()

        # 方法1：匹配 myui-vodlist__thumb 的 a 标签，从 style 中提取图片
        # 格式: <a class="myui-vodlist__thumb" style="background: url(图片)" href="/vodplay/xxx" title="标题">
        thumb_pattern = r'<a[^>]*class="[^"]*myui-vodlist__thumb[^"]*"[^>]*style="[^"]*background:\s*url\(([^)]+)\)[^"]*"[^>]*href="([^"]+)"[^>]*title="([^"]*)"'
        matches = re.findall(thumb_pattern, html, re.S)

        for pic_url, href, title in matches:
            if not href.startswith('/vodplay/'):
                continue
            vid_match = re.search(r'/vodplay/(\d+)', href)
            if not vid_match:
                continue
            vid = vid_match.group(1)
            if vid in seen_vids:
                continue
            seen_vids.add(vid)

            title = title.strip() if title else f'视频_{vid}'
            pic = pic_url.strip()
            if pic.startswith('//'):
                pic = 'https:' + pic
            elif pic.startswith('/'):
                pic = self.host + pic

            items.append({
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': self._proxy_url(pic) if pic else '',
                'vod_remarks': '排行榜'
            })

        # 方法2：如果方法1没匹配到，尝试 title 在 href 之前的顺序
        if not items:
            thumb_pattern2 = r'<a[^>]*class="[^"]*myui-vodlist__thumb[^"]*"[^>]*title="([^"]*)"[^>]*href="([^"]+)"[^>]*style="[^"]*background:\s*url\(([^)]+)\)[^"]*"'
            matches2 = re.findall(thumb_pattern2, html, re.S)
            for title, href, pic_url in matches2:
                if not href.startswith('/vodplay/'):
                    continue
                vid_match = re.search(r'/vodplay/(\d+)', href)
                if not vid_match:
                    continue
                vid = vid_match.group(1)
                if vid in seen_vids:
                    continue
                seen_vids.add(vid)
                title = title.strip() if title else f'视频_{vid}'
                pic = pic_url.strip()
                if pic.startswith('//'):
                    pic = 'https:' + pic
                elif pic.startswith('/'):
                    pic = self.host + pic
                items.append({
                    'vod_id': vid,
                    'vod_name': title,
                    'vod_pic': self._proxy_url(pic) if pic else '',
                    'vod_remarks': '排行榜'
                })

        # 方法3：如果还是没匹配到，从 <h4> 中提取标题（无图片兜底）
        if not items:
            li_pattern = r'<li[^>]*class="clearfix"[^>]*>.*?<a[^>]*class="[^"]*myui-vodlist__thumb[^"]*"[^>]*href="([^"]+)"[^>]*style="[^"]*background:\s*url\(([^)]+)\)[^"]*"[^>]*>.*?<h4[^>]*class="title[^"]*"[^>]*>.*?<a[^>]*>([^<]+)</a>'
            li_matches = re.findall(li_pattern, html, re.S)
            for href, pic_url, title in li_matches:
                if not href.startswith('/vodplay/'):
                    continue
                vid_match = re.search(r'/vodplay/(\d+)', href)
                if not vid_match:
                    continue
                vid = vid_match.group(1)
                if vid in seen_vids:
                    continue
                seen_vids.add(vid)
                title = title.strip()
                pic = pic_url.strip()
                if pic.startswith('//'):
                    pic = 'https:' + pic
                elif pic.startswith('/'):
                    pic = self.host + pic
                items.append({
                    'vod_id': vid,
                    'vod_name': title,
                    'vod_pic': self._proxy_url(pic) if pic else '',
                    'vod_remarks': '排行榜'
                })

        # 最终兜底：只提取链接和标题（无图片）
        if not items:
            links = re.findall(
                r'<a[^>]+href="(/vodplay/(\d+)-\d+-\d+\.html)"[^>]*>([^<]+)</a>',
                html, re.S
            )
            for href, vid, title in links:
                if vid in seen_vids:
                    continue
                seen_vids.add(vid)
                title = title.strip()
                if not title:
                    continue
                items.append({
                    'vod_id': vid,
                    'vod_name': title,
                    'vod_pic': '',
                    'vod_remarks': '排行榜'
                })

        self._log(f'排行榜解析到 {len(items)} 个视频')
        return items

    def _get_rank_list(self, page=1):
        url = f'{self.host}/index.php/label/rank.html'
        html = self._fetch(url, referer=self.host)
        return self._parse_rank(html) if html else []

    # ===== 女优大全解析（修复：支持子分类分组） =====
    def _parse_nvyou(self, html):
        items = []

        groups = re.findall(
            r'<li class="nvyouzimu">([^<]+)</li>\s*<li class="nvyouliebiao">(.*?)</li>',
            html, re.S
        )

        for group_name, group_html in groups:
            group_name = group_name.strip()
            if not group_name:
                continue

            # 判断是否为日本女优的字母分组 (A-Z)
            is_jp_zimu = bool(re.match(r'^[A-Z]$', group_name))
            if is_jp_zimu:
                display_group = '日本女优'
                remarks = f'日本女优-{group_name}'
            else:
                display_group = group_name
                remarks = group_name

            actresses = re.findall(
                r'<a href="/vodsearch/([^"]+)-\.html"[^>]*>([^<]+)</a>',
                group_html
            )

            for url_name, display_name in actresses:
                display_name = display_name.strip()
                if not display_name:
                    continue
                vid = f'nvyou_{url_name}'
                items.append({
                    'vod_id': vid,
                    'vod_name': display_name,
                    'vod_pic': '',
                    'vod_remarks': remarks,
                    '_group': display_group,      # 内部用于子分类筛选
                })

        self._log(f'女优大全解析到 {len(items)} 个女优，分组已识别')
        return items

    def _get_nvyou_list(self, page=1):
        # 女优大全通常只有一页，使用缓存避免重复请求
        if self._nvyou_loaded and self._nvyou_cache:
            return self._nvyou_cache
        
        url = f'{self.host}/vodtype/35-{page}.html'
        html = self._fetch(url, referer=self.host)
        if html:
            items = self._parse_nvyou(html)
            self._nvyou_cache = items
            self._nvyou_loaded = True
            return items
        return []

    # ===== 女优封面获取（随机抓取一部影片封面） =====
    def _fetch_nvyou_cover(self, item):
        """为单个女优随机获取一部影片的封面"""
        vid = item['vod_id']
        # 先查缓存
        if vid in self._nvyou_cover_cache:
            item['vod_pic'] = self._nvyou_cover_cache[vid]
            return item

        try:
            url_name = vid.replace('nvyou_', '')
            url = f'{self.host}/vodsearch/{quote(url_name)}-.html'
            headers = self._get_headers(self.host)
            r = self.session.get(url, headers=headers, timeout=5, verify=False)
            if r.status_code == 200 and len(r.text) > 500:
                r.encoding = 'utf-8'
                parsed = self._parse_list(r.text)
                if parsed:
                    chosen = random.choice(parsed)
                    pic = chosen.get('vod_pic', '')
                    if pic:
                        self._nvyou_cover_cache[vid] = pic
                        item['vod_pic'] = pic
        except Exception as e:
            self._log(f'获取女优封面失败 {vid}: {e}')
        return item

    def _apply_nvyou_covers(self, items, max_workers=5, limit=24):
        """并发为女优列表获取随机影片封面"""
        target = items[:limit]
        threads = []
        for item in target:
            t = threading.Thread(target=self._fetch_nvyou_cover, args=(item,))
            t.start()
            threads.append(t)
            # 控制并发数，避免同时开太多线程
            while len([t for t in threads if t.is_alive()]) >= max_workers:
                time.sleep(0.1)
        # 等待所有线程完成
        for t in threads:
            t.join(timeout=6)
        return items

    # ===== 首页 / 分类（蜜桃式：一级分类 + 二级筛选下拉） =====
    def homeContent(self, filter):
        text = self._fetch(self.host + '/')
        if text and len(text) > 2000:
            self._update_categories(text)

        cats = self._categories_cache

        # ===== 蜜桃式分类结构：一级分类 + 二级筛选下拉 =====
        classes = [
            {'type_id': 'rank', 'type_name': '排行榜'},
            {'type_id': 'nvyou', 'type_name': '女优大全'},
            {'type_id': 'video', 'type_name': '视频分类'},
        ]

        filters = {}

        # 女优大全二级筛选
        nvyou_subs = [{'n': '全部女优', 'v': ''}]
        for cat in cats:
            tid = str(cat['type_id'])
            if tid.startswith('nvyou_') and tid != 'nvyou':
                nvyou_subs.append({'n': cat['type_name'], 'v': tid.replace('nvyou_', '')})
        if len(nvyou_subs) > 1:
            filters['nvyou'] = [{'key': 'sub', 'name': '女优分类', 'value': nvyou_subs}]

        # 视频分类二级筛选
        video_subs = [{'n': '全部', 'v': ''}]
        for cat in cats:
            tid = str(cat['type_id'])
            if tid.isdigit():
                video_subs.append({'n': cat['type_name'], 'v': tid})
        if len(video_subs) > 1:
            filters['video'] = [{'key': 'sub', 'name': '分类', 'value': video_subs}]

        # 动态随机推荐：先尝试排行榜，有则随机打乱顺序
        items = self._get_rank_list(1)
        if items:
            random.shuffle(items)
        else:
            # 排行榜为空，从普通视频分类中随机抽取推荐
            video_cats = [c for c in cats if str(c['type_id']).isdigit()]
            if video_cats:
                random.shuffle(video_cats)
                for cat in video_cats[:5]:
                    items = self._get_list(cat['type_id'], 1)
                    if items:
                        random.shuffle(items)
                        break
        
        # 保底：再随机挑一个分类
        if not items:
            for c in cats:
                if str(c['type_id']).isdigit():
                    items = self._get_list(c['type_id'], 1)
                    if items:
                        random.shuffle(items)
                        break

        return {
            'class': classes,
            'filters': filters,
            'type': '影视',
            'list': items[:30] if items else [],
            'page': 1,
            'pagecount': 1,
            'limit': len(items[:30]) if items else 0,
            'total': len(items[:30]) if items else 0
        }

    def homeVideoContent(self):
        # 动态随机推荐
        items = self._get_rank_list(1)
        if items:
            random.shuffle(items)
        else:
            video_cats = [c for c in self._categories_cache if str(c['type_id']).isdigit()]
            if video_cats:
                random.shuffle(video_cats)
                for cat in video_cats[:5]:
                    items = self._get_list(cat['type_id'], 1)
                    if items:
                        random.shuffle(items)
                        break
        
        if not items:
            for c in self._categories_cache:
                if str(c['type_id']).isdigit():
                    items = self._get_list(c['type_id'], 1)
                    if items:
                        random.shuffle(items)
                        break
                    
        return {'list': items[:30] if items else []}

    # ===== 分类内容（蜜桃式二级筛选支持） =====
    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1

        # 处理 extend 参数（TVBox 可能传字符串 JSON）
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except:
                extend = {}
        if not isinstance(extend, dict):
            extend = {}

        # ===== 排行榜 =====
        if str(tid) == 'rank':
            items = self._get_rank_list(page)
            return {
                'list': items,
                'page': page,
                'pagecount': 1,
                'limit': len(items),
                'total': len(items)
            }

        # ===== 女优大全（蜜桃式二级筛选） =====
        tid_str = str(tid)
        if tid_str == 'nvyou':
            all_items = self._get_nvyou_list(page)
            sub_val = extend.get('sub', '')
            
            if not sub_val:
                # 全部女优：展示所有
                filtered = all_items
            elif sub_val == '日本女优':
                # 日本女优：所有 A-Z 字母分组的女优
                filtered = [item for item in all_items if item.get('_group') == '日本女优']
            else:
                # 其他子分类，如 '国产AV女优'
                filtered = [item for item in all_items if item.get('_group') == sub_val]
            
            # 为女优列表随机获取影片封面（并发，限制数量避免超时）
            filtered = self._apply_nvyou_covers(filtered, max_workers=5, limit=24)
            
            # 返回时去掉内部字段
            result_items = []
            for item in filtered:
                clean_item = {k: v for k, v in item.items() if not k.startswith('_')}
                result_items.append(clean_item)
                
            return {
                'list': result_items,
                'page': page,
                'pagecount': 1,
                'limit': len(result_items),
                'total': len(result_items)
            }

        # ===== 视频分类（蜜桃式二级筛选） =====
        if tid_str == 'video':
            sub_val = extend.get('sub', '')
            if not sub_val:
                # 默认取第一个数字分类
                for cat in self._categories_cache:
                    if str(cat['type_id']).isdigit():
                        sub_val = cat['type_id']
                        break
            items = self._get_list(sub_val, page)
            return {
                'list': items,
                'page': page,
                'pagecount': page + 1,
                'limit': len(items),
                'total': page + 1
            }

        # 兜底：兼容旧 tid 直接访问（如用户直接输入 type_id）
        if tid_str.startswith('nvyou_'):
            all_items = self._get_nvyou_list(page)
            if tid_str == 'nvyou_日本女优':
                filtered = [item for item in all_items if item.get('_group') == '日本女优']
            else:
                group_name = tid_str.replace('nvyou_', '')
                filtered = [item for item in all_items if item.get('_group') == group_name]
            filtered = self._apply_nvyou_covers(filtered, max_workers=5, limit=24)
            result_items = []
            for item in filtered:
                clean_item = {k: v for k, v in item.items() if not k.startswith('_')}
                result_items.append(clean_item)
            return {
                'list': result_items,
                'page': page,
                'pagecount': 1,
                'limit': len(result_items),
                'total': len(result_items)
            }

        items = self._get_list(tid, page)
        return {
            'list': items,
            'page': page,
            'pagecount': page + 1,
            'limit': len(items),
            'total': page + 1
        }

    # ===== 详情页（核心修复） =====
    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, list) else ids)

        # ===== 女优详情：展示所有作品列表 =====
        if vid.startswith('nvyou_'):
            actress_name = vid.replace('nvyou_', '')
            # 获取该女优的所有作品（搜索）
            search_items = self._do_search(actress_name, 1)

            if not search_items:
                return {
                    'list': [{
                        'vod_id': vid,
                        'vod_name': f'女优: {actress_name}',
                        'vod_pic': '',
                        'vod_play_from': '作品集',
                        'vod_play_url': f'第1集${self.host}/vodsearch/{quote(actress_name)}-1.html',
                        'vod_content': f'{actress_name} 暂无作品',
                        'vod_remarks': '0部作品'
                    }]
                }

            # 构建多集播放列表
            # TVBox格式: 播放源$集名1$url1#集名2$url2#...
            play_parts = []
            for i, item in enumerate(search_items[:50]):  # 最多50部
                idx = i + 1
                title_short = item['vod_name'][:30] if len(item['vod_name']) > 30 else item['vod_name']
                # 清理特殊字符
                title_short = title_short.replace('$', '').replace('#', '')
                play_parts.append(f'{title_short}${self.host}/vodplay/{item["vod_id"]}-1-1.html')

            vod_play_url = '#'.join(play_parts)

            # 获取第一个作品的封面作为女优封面
            first_pic = search_items[0].get('vod_pic', '') if search_items else ''

            return {
                'list': [{
                    'vod_id': vid,
                    'vod_name': f'女优: {actress_name}',
                    'vod_pic': first_pic,
                    'vod_play_from': '作品集',
                    'vod_play_url': vod_play_url,
                    'vod_content': f'{actress_name} 的作品集，共 {len(search_items)} 部作品',
                    'vod_remarks': f'{len(search_items)}部作品'
                }]
            }

        # ===== 普通视频详情 =====
        detail = self._fetch_detail(vid)
        if not detail:
            detail = {
                'vod_id': vid,
                'vod_name': f'视频_{vid}',
                'vod_pic': '',
                'vod_play_from': '在线播放',
                'vod_play_url': f'线路1${self.host}/vodplay/{vid}-1-1.html',
                'vod_content': ''
            }
        else:
            if not detail.get('vod_name'):
                detail['vod_name'] = f'视频_{vid}'
        return {'list': [detail]}

    def _fetch_detail(self, vid):
        url = f'{self.host}/vodplay/{vid}-1-1.html'
        html = self._fetch(url, referer=self.host)
        return self._parse_detail(html, vid) if html else None

    def _parse_detail(self, html, vid):
        title = ''
        m = re.search(r'<title>(.*?)</title>', html, re.S)
        if m:
            full_title = m.group(1).strip()
            parts = full_title.split('_')
            if len(parts) >= 2:
                title = parts[0].strip()
            else:
                title = full_title

        if not title:
            m = re.search(r'<h1[^>]*class="title"[^>]*>(.*?)</h1>', html, re.S)
            if m:
                title = re.sub(r'<[^>]+>', '', m.group(1)).strip()

        if not title:
            m = re.search(r'<h4[^>]*class="title"[^>]*>(.*?)</h4>', html, re.S)
            if m:
                title = re.sub(r'<[^>]+>', '', m.group(1)).strip()

        if not title:
            title = f'视频_{vid}'

        cover = ''
        m = re.search(r'data-original="([^"]+)"', html)
        if m:
            cover = m.group(1)
            if cover.startswith('//'):
                cover = 'https:' + cover
            elif cover.startswith('/'):
                cover = self.host + cover

        content = ''
        desc_match = re.search(r'class="[^"]*desc[^"]*"[^>]*>(.*?)</', html, re.S)
        if desc_match:
            content = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip()
        if not content:
            content = title

        play_url = f'{self.host}/vodplay/{vid}-1-1.html'
        m3u8_url = self._extract_m3u8(html)
        if m3u8_url:
            play_url = m3u8_url

        return {
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': self._proxy_url(cover) if cover else '',
            'vod_play_from': '在线播放',
            'vod_play_url': f'线路1${play_url}',
            'vod_content': content,
        }

    def _extract_m3u8(self, html):
        m = re.search(r'var\s+player_aaaa\s*=\s*({.*?});', html, re.S)
        if not m:
            m = re.search(r'player_aaaa\s*=\s*({.*?});', html, re.S)
        if m:
            try:
                cfg = json.loads(m.group(1).replace('\\/', '/'))
                url = cfg.get('url', '')
                if url and ('.m3u8' in url or '.mp4' in url):
                    if not url.startswith('http'):
                        url = urljoin(self.host, url)
                    return url
            except Exception:
                pass

        m = re.search(r'["\'](https?://[^"\'<>]+\.(?:m3u8|mp4)[^"\'<>]*)["\']', html)
        if m:
            return m.group(1)

        return None

    # ==================== m3u8 广告清洗（Qinav 完整逻辑） ====================
    def _proxy_m3u8_url(self, url, referer=''):
        try:
            if hasattr(self, 'getProxyUrl'):
                base = self.getProxyUrl()
                if '?' not in base:
                    base += '?do=py'
                return base + '&type=m3u8&url=' + quote(url, safe='') + '&referer=' + quote(referer or self.host, safe='')
        except:
            pass
        return url

    def _get_m3u8_content(self, url, referer):
        try:
            headers = self.session.headers.copy()
            headers['Referer'] = referer
            resp = requests.get(url, headers=headers, timeout=15, verify=False)
            if resp.status_code == 200:
                resp.encoding = 'utf-8'
                return resp.text
        except Exception as e:
            self._log(f'下载 m3u8 失败: {e}')
        return None

    def _clean_m3u8(self, m3u8_text, m3u8_url='', referer='', skip_seconds=25):
        """清洗 m3u8：去除广告分片，保留 KEY/MAP/DISCONTINUITY，URI 绝对化"""
        text = (m3u8_text or '').replace('\r', '')
        if '#EXT-X-STREAM-INF' in text:
            # master m3u8，将子 m3u8 的 URL 也替换为代理链接
            out = []
            for raw in text.splitlines():
                line = raw.strip()
                if not line:
                    continue
                if line.startswith('#'):
                    out.append(line)
                else:
                    abs_url = urljoin(m3u8_url, line)
                    if '.m3u8' in line.lower():
                        out.append(self._proxy_m3u8_url(abs_url, referer))
                    else:
                        out.append(abs_url)
            return '\n'.join(out) + '\n'

        header, segments, tail, media_sequence, target_duration = self._parse_m3u8_segments(text)
        if not segments:
            return text

        marker = self._main_path_marker(m3u8_url)
        stat = {}
        for seg in segments:
            key = self._segment_host_key(seg['uri'], m3u8_url)
            stat[key] = stat.get(key, 0.0) + float(seg.get('dur') or 0)
        main_key = max(stat.items(), key=lambda x: x[1])[0] if stat else ('', '')
        total_dur = sum(stat.values()) or 0
        main_dur = stat.get(main_key, 0)

        cleaned = []
        removed = 0
        for idx, seg in enumerate(segments):
            key = self._segment_host_key(seg['uri'], m3u8_url)
            is_front = idx < 12
            abs_uri = urljoin(m3u8_url, seg.get('uri', ''))
            is_ad = self._is_ad_segment(seg['uri'], seg.get('dur'), seg.get('tags'))
            if marker and marker not in urlparse(abs_uri).path.lower():
                is_ad = True
            tags_text = '\n'.join(seg.get('tags') or []).upper()
            if is_front and 'METHOD=NONE' in tags_text and marker and marker not in urlparse(abs_uri).path.lower():
                is_ad = True
            if (not is_ad) and is_front and total_dur > 0 and main_dur >= total_dur * 0.6:
                if key != main_key and stat.get(key, 0) <= 90:
                    is_ad = True
            if is_ad:
                removed += 1
                continue
            seg['_idx'] = idx
            cleaned.append(seg)

        # 若未检测到广告，尝试按累积秒数跳过前置广告段
        if removed == 0 and len(segments) > 4:
            acc = 0.0
            cut = 0
            for idx, seg in enumerate(segments[:12]):
                key = self._segment_host_key(seg['uri'], m3u8_url)
                if key == main_key and acc >= 3:
                    break
                acc += float(seg.get('dur') or target_duration or 3)
                cut = idx + 1
                if acc >= skip_seconds:
                    break
            if cut > 0 and cut < len(segments):
                first_key = self._segment_host_key(segments[0]['uri'], m3u8_url)
                if first_key != main_key:
                    cleaned = segments[cut:]
                    removed = cut

        if not cleaned:
            cleaned = segments
            removed = 0

        new_lines = []
        has_m3u = False
        for line in header:
            if line.startswith('#EXTM3U'): has_m3u = True
            if line.startswith('#EXT-X-MEDIA-SEQUENCE') or line.startswith('#EXT-X-START'):
                continue
            if line.startswith('#EXT-X-KEY') and 'METHOD=NONE' in line.upper() and removed > 0:
                continue
            new_lines.append(line)
        if not has_m3u:
            new_lines.insert(0, '#EXTM3U')
        first_idx = cleaned[0].get('_idx', removed) if cleaned else removed
        new_lines.append(f'#EXT-X-MEDIA-SEQUENCE:{media_sequence + first_idx}')
        for seg in cleaned:
            for tag in seg.get('tags') or []:
                if tag.startswith('#EXT-X-KEY') or tag.startswith('#EXT-X-MAP'):
                    def _fix_uri(m):
                        return 'URI="' + urljoin(m3u8_url, m.group(1)) + '"'
                    tag = re.sub(r'URI="([^"]+)"', _fix_uri, tag)
                new_lines.append(tag)
            new_lines.append(urljoin(m3u8_url, seg.get('uri', '')))
        if tail:
            for line in tail:
                if line.startswith('#EXT-X-ENDLIST'):
                    new_lines.append(line)
        elif '#EXT-X-ENDLIST' in text:
            new_lines.append('#EXT-X-ENDLIST')
        self._log(f'm3u8清洗: 原{len(segments)}片 → 删除{removed}片广告，保留{len(cleaned)}片')
        return '\n'.join(new_lines) + '\n'

    def _parse_m3u8_segments(self, text):
        lines = [x.strip() for x in (text or '').replace('\r', '').split('\n') if x.strip()]
        header, segments, tail = [], [], []
        pending_tags = []
        media_sequence = 0
        target_duration = 0
        started = False
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith('#EXT-X-MEDIA-SEQUENCE'):
                try:
                    media_sequence = int(line.split(':', 1)[1])
                except:
                    pass
                if not started:
                    header.append(line)
                else:
                    pending_tags.append(line)
            elif line.startswith('#EXT-X-TARGETDURATION'):
                try:
                    target_duration = float(line.split(':', 1)[1])
                except:
                    pass
                if not started:
                    header.append(line)
                else:
                    pending_tags.append(line)
            elif line.startswith('#EXTINF'):
                started = True
                dur = target_duration or 3.0
                m = re.search(r'#EXTINF:\s*([\d.]+)', line)
                if m:
                    try:
                        dur = float(m.group(1))
                    except:
                        pass
                tags = pending_tags + [line]
                pending_tags = []
                uri = ''
                j = i + 1
                while j < len(lines):
                    if lines[j].startswith('#'):
                        tags.append(lines[j])
                        j += 1
                        continue
                    uri = lines[j]
                    break
                if uri:
                    segments.append({'tags': tags, 'uri': uri, 'dur': dur})
                    i = j
                else:
                    tail.extend(tags)
            elif line.startswith('#EXT-X-ENDLIST'):
                tail.append(line)
            elif line.startswith('#'):
                if started:
                    pending_tags.append(line)
                else:
                    header.append(line)
            else:
                started = True
                dur = target_duration or 3.0
                segments.append({'tags': pending_tags, 'uri': line, 'dur': dur})
                pending_tags = []
            i += 1
        return header, segments, tail, media_sequence, target_duration

    def _is_ad_segment(self, uri, dur=0, prev_tags=None):
        u = (uri or '').strip().lower()
        if not u:
            return False
        ad_words = [
            'ad', 'ads', 'advert', 'advertise', 'advertisement', 'sponsor',
            'pre', 'preroll', '片头', '广告', '/gg/', '_gg', 'gg_', '/adv/',
            '/ad/', '/ads/', 'banner', 'promo', 'commercial'
        ]
        if any(w in u for w in ad_words):
            return True
        try:
            if 0 < float(dur) <= 1.2:
                return True
        except:
            pass
        return False

    def _segment_host_key(self, uri, base_url):
        try:
            full = urljoin(base_url, uri)
            p = urlparse(full)
            path = re.sub(r'/[^/]*$', '/', p.path or '/')
            return (p.netloc.lower(), path.lower())
        except:
            return ('', '')

    def _main_path_marker(self, m3u8_url):
        try:
            p = urlparse(m3u8_url).path
            m = re.search(r'(/\d{8}/[^/]+/\d+kb/hls/)', p)
            if m:
                return m.group(1).lower()
            m = re.search(r'(/\d{8}/[^/]+/)', p)
            if m:
                return m.group(1).lower()
        except:
            pass
        return ''

    # ===== 播放器（m3u8 自动走清洗代理） =====
    def playerContent(self, flag, id, vipFlags=None):
        self._log(f'playerContent: id={id[:120] if len(id) > 120 else id}')

        if '.m3u8' in id or '.mp4' in id or id.startswith('magnet:'):
            url = id
            if '.m3u8' in url:
                url = self._proxy_m3u8_url(url, self.host)
            return {
                'parse': 0,
                'url': url,
                'header': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Referer': self.host
                }
            }

        html = ''
        if id.startswith(self.host):
            html = self._fetch(id, referer=self.host)

        if html:
            m3u8 = self._extract_m3u8(html)
            if m3u8:
                return {
                    'parse': 0,
                    'url': self._proxy_m3u8_url(m3u8, self.host),
                    'header': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Referer': self.host
                    }
                }

            all_urls = re.findall(r'(https?://[^\s"\'<>]+\.(?:m3u8|mp4|ts)[^\s"\'<>]*)', html)
            if all_urls:
                url = all_urls[0]
                if '.m3u8' in url:
                    url = self._proxy_m3u8_url(url, self.host)
                return {
                    'parse': 0,
                    'url': url,
                    'header': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Referer': self.host
                    }
                }

        return {
            'parse': 1,
            'url': id,
            'header': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': self.host
            }
        }

    # ===== 搜索 =====
    def searchContent(self, key, quick, pg='1'):
        page = int(pg) if pg else 1
        items = self._do_search(key, page)
        return {
            'list': items,
            'page': page,
            'pagecount': page + 1,
            'limit': len(items),
            'total': len(items)
        }

    def _do_search(self, key, page=1):
        """
        修复：适配该站点实际的搜索URL格式
        第1页: /vodsearch/{关键词}-.html
        第2页+: /vodsearch/{关键词}-/page/{页码}.html
        """
        encoded_key = quote(key)
        if page == 1:
            url = f'{self.host}/vodsearch/{encoded_key}-.html'
        else:
            url = f'{self.host}/vodsearch/{encoded_key}-/page/{page}.html'
        html = self._fetch(url, referer=self.host)
        return self._parse_list(html) if html else []
