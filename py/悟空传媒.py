# -*- coding: utf-8 -*-
import sys
import re
import json
import base64
import requests
import urllib3
from urllib.parse import quote

urllib3.disable_warnings()
sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    session = requests.Session()
    host = 'https://a4j665s.bingyu4.sbs'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Referer': 'https://a4j665s.bingyu4.sbs/',
    }

    # ==================== 分类映射 ====================
    VIDEO_CATS = [
        {'type_id': 'shipin/1',  'type_name': '国产'},
        {'type_id': 'shipin/6',  'type_name': '自拍'},
        {'type_id': 'shipin/7',  'type_name': '乱伦'},
        {'type_id': 'shipin/8',  'type_name': '强奸'},
        {'type_id': 'shipin/9',  'type_name': '传媒'},
        {'type_id': 'shipin/10', 'type_name': '反差婊'},
        {'type_id': 'shipin/11', 'type_name': '网爆门'},
        {'type_id': 'shipin/12', 'type_name': '偷拍'},
        {'type_id': 'shipin/30', 'type_name': '兄弟姐妹'},
        {'type_id': 'shipin/31', 'type_name': '禁忌母子'},
        {'type_id': 'shipin/32', 'type_name': '狂操小姨'},
        {'type_id': 'shipin/33', 'type_name': '猛干嫂子'},
        {'type_id': 'shipin/34', 'type_name': '野外车震'},
        {'type_id': 'shipin/35', 'type_name': '夫妻交换'},
        {'type_id': 'shipin/36', 'type_name': '淫荡儿媳'},
        {'type_id': 'shipin/37', 'type_name': '学生下海'},
        {'type_id': 'shipin/2',  'type_name': '网红'},
        {'type_id': 'shipin/3',  'type_name': '萝莉'},
        {'type_id': 'shipin/13', 'type_name': '福利姬'},
        {'type_id': 'shipin/14', 'type_name': '吃瓜'},
        {'type_id': 'shipin/15', 'type_name': '大学生'},
        {'type_id': 'shipin/16', 'type_name': '人兽'},
        {'type_id': 'shipin/5',  'type_name': '探花'},
        {'type_id': 'shipin/4',  'type_name': '大秀'},
        {'type_id': 'shipin/38', 'type_name': '瑜伽裤'},
        {'type_id': 'shipin/39', 'type_name': '兽耳系列'},
        {'type_id': 'shipin/40', 'type_name': '多人群P'},
        {'type_id': 'shipin/41', 'type_name': 'Cosplay'},
        {'type_id': 'shipin/17', 'type_name': '人妖'},
        {'type_id': 'shipin/18', 'type_name': 'OnlyFans'},
        {'type_id': 'shipin/20', 'type_name': '喷水'},
        {'type_id': 'shipin/21', 'type_name': '裸贷'},
        {'type_id': 'shipin/22', 'type_name': '性虐'},
        {'type_id': 'shipin/23', 'type_name': 'AI换脸'},
        {'type_id': 'shipin/24', 'type_name': '无码'},
        {'type_id': 'shipin/25', 'type_name': '中字'},
        {'type_id': 'shipin/26', 'type_name': '欧美'},
        {'type_id': 'shipin/27', 'type_name': '动漫'},
        {'type_id': 'shipin/28', 'type_name': '三级片'},
        {'type_id': 'shipin/29', 'type_name': 'AV解说'},
    ]

    NOVEL_CATS = [
        {'type_id': 'wenzhang/42', 'type_name': '都市小说'},
        {'type_id': 'wenzhang/43', 'type_name': '乱伦小说'},
        {'type_id': 'wenzhang/44', 'type_name': '学生小说'},
        {'type_id': 'wenzhang/45', 'type_name': '仙侠小说'},
    ]

    IMAGE_CATS = [
        {'type_id': 'wenzhang/46', 'type_name': '自拍图片'},
        {'type_id': 'wenzhang/47', 'type_name': '亚洲色图'},
        {'type_id': 'wenzhang/48', 'type_name': '欧美色图'},
        {'type_id': 'wenzhang/49', 'type_name': '卡通色图'},
    ]

    # ==================== 基类方法 ====================
    def getName(self): return "wukong"

    def isVideoFormat(self, url):
        if not url: return False
        return '.m3u8' in url or '.mp4' in url or '.ts' in url

    def manualVideoCheck(self): return False
    def destroy(self): pass

    def localProxy(self, param):
        return [404, 'text/plain', '']

    def init(self, extend=""):
        self.session.verify = False

    # ==================== 私有工具 ====================
    def _fetch(self, url, timeout=20):
        try:
            if not url.startswith('http'):
                url = self.host + url
            r = self.session.get(url, headers=self.headers, timeout=timeout, verify=False)
            r.encoding = 'utf-8'
            return r.text if r.status_code == 200 else ''
        except Exception:
            return ''

    def _img_url(self, url):
        if not url: return ''
        if url.startswith('http'): return url
        return self.host + url if url.startswith('/') else self.host + '/' + url

    def _is_novel(self, tid):
        return tid in [c['type_id'] for c in self.NOVEL_CATS]

    def _is_image(self, tid):
        return tid in [c['type_id'] for c in self.IMAGE_CATS]

    def _is_video(self, tid):
        return tid in [c['type_id'] for c in self.VIDEO_CATS]

    # ==================== 列表解析 ====================
    def _parse_video_list(self, text):
        items = []
        cards = re.findall(r'<div class="card">(.*?)</div>\s*</div>', text, re.S)
        for card in cards:
            m = re.search(r'<a class="pic" href="([^"]+)" title="([^"]*)"[^>]*style="background-image:url\(([^)]+)\)"', card, re.S)
            if not m: continue
            href, title, pic = m.groups()
            m2 = re.search(r'<a class="title"[^>]*>([^<]+)</a>', card)
            title2 = m2.group(1).strip() if m2 else title
            m3 = re.search(r'<div class="sub">([^<]+)</div>', card)
            sub = m3.group(1).strip() if m3 else ''
            mm = re.search(r'/shipinnr/(\d+)\.html', href)
            if not mm: continue
            vid = mm.group(1)
            items.append({
                'vod_id': f'video#{vid}',
                'vod_name': title.strip() or title2,
                'vod_pic': self._img_url(pic.strip()),
                'vod_remarks': sub,
            })
        return items

    def _parse_text_list(self, text, tid):
        items = []
        prefix = 'novel' if self._is_novel(tid) else 'image'
        lis = re.findall(r'<li>\s*<a href="([^"]+)" title="([^"]*)">\s*<span class="art-title">([^<]+)</span>\s*<span class="art-time">([^<]+)</span>\s*</a>\s*</li>', text, re.S)
        for href, title, title2, date in lis:
            mm = re.search(r'/wenzhangs-(\d+)\.html', href)
            if not mm: continue
            vid = mm.group(1)
            items.append({
                'vod_id': f'{prefix}#{vid}',
                'vod_name': title.strip() or title2.strip(),
                'vod_pic': '',
                'vod_remarks': date.strip(),
            })
        return items

    def _build_cat_url(self, tid, page):
        if page == 1:
            return f'/{tid}.html'
        return f'/{tid}-{page}.html'

    def _get_type_name(self, tid):
        for cat in self.VIDEO_CATS + self.NOVEL_CATS + self.IMAGE_CATS:
            if cat['type_id'] == tid:
                return cat['type_name']
        return tid

    # ==================== 接口实现 ====================
    def homeContent(self, filter):
        classes = []
        # 视频取前 12 个放首页
        for cat in self.VIDEO_CATS[:12]:
            classes.append(cat)
        # 小说 + 图片
        classes.extend(self.NOVEL_CATS)
        classes.extend(self.IMAGE_CATS)
        return {'class': classes, 'filters': {}, 'type': '影视'}

    def homeVideoContent(self):
        text = self._fetch('/shipin/1.html')
        items = self._parse_video_list(text)
        return {'list': items}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            return self._categoryContent_inner(tid, pg, filter, extend)
        except Exception:
            return {'list': [], 'page': int(pg) if pg else 1, 'pagecount': 1, 'limit': 0, 'total': 0}

    def _categoryContent_inner(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        url = self._build_cat_url(tid, page)
        text = self._fetch(url)

        if self._is_video(tid):
            items = self._parse_video_list(text)
        else:
            items = self._parse_text_list(text, tid)

        # 提取总页数（如：共31179条，1/2228页）
        pagecount = page + 1
        m = re.search(r'共\d+条，\d+/(\d+)页', text)
        if m:
            pagecount = int(m.group(1))

        return {
            'list': items,
            'page': page,
            'pagecount': pagecount,
            'limit': len(items),
            'total': page * len(items) + 1
        }

    # ==================== 详情解析 ====================
    def detailContent(self, ids):
        try:
            return self._detailContent_inner(ids)
        except Exception:
            return {'list': []}

    def _detailContent_inner(self, ids):
        vid = str(ids[0] if isinstance(ids, list) else ids)
        prefix, num = vid.split('#', 1)
        if prefix == 'video':
            return self._video_detail(num)
        elif prefix == 'novel':
            return self._novel_detail(num)
        elif prefix == 'image':
            return self._image_detail(num)
        return {'list': []}

    def _video_detail(self, vid):
        url = f'/shipinnr/{vid}.html'
        text = self._fetch(url)
        if not text: return {'list': []}

        title = ''
        m = re.search(r'<h1[^>]*>(.*?)</h1>', text, re.S)
        if m: title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if not title:
            m = re.search(r'<title>([^<]+)</title>', text)
            if m: title = m.group(1).strip()

        cover = ''
        m = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', text)
        if m: cover = m.group(1)
        if not cover:
            m = re.search(r'<div class="post"[^>]*>.*?<img[^>]*src="([^"]+)"', text, re.S)
            if m: cover = m.group(1)

        # ===== 优先提取 shipinlay 多线路播放页链接 =====
        play_links = re.findall(r'<a[^>]*href="(/shipinlay/\d+-\d+-\d+\.html)"[^>]*>([^<]+)</a>', text)
        urls = []
        vod_play_from = '悟空视频'

        if play_links:
            seen = set()
            for link, name in play_links:
                if link in seen:
                    continue
                seen.add(link)
                clean_name = re.sub(r'<[^>]+>', '', name).strip()
                if not clean_name:
                    clean_name = f'线路{len(seen)}'
                full_url = self.host + link
                urls.append(f'{clean_name}${full_url}')
            vod_play_from = '悟空视频多线'
        else:
            # 原有逻辑：从 player_data 提取单线路 m3u8
            m3u8 = ''
            m = re.search(r'var\s+player_data\s*=\s*(\{.*?\});', text, re.S)
            if m:
                try:
                    player_data = json.loads(m.group(1))
                    m3u8 = player_data.get('url', '')
                except Exception:
                    pass

            # 备用：通用正则兜底
            if not m3u8:
                m = re.search(r'(https?://[^\s"<>\']+?\.(?:m3u8|mp4))', text)
                if m: m3u8 = m.group(1)
            if not m3u8:
                m = re.search(r'var\s+(?:url|src|video|play|source)\s*=\s*["\']([^"\']+)', text, re.I)
                if m:
                    u = m.group(1)
                    if '.m3u8' in u or '.mp4' in u:
                        m3u8 = u
            if not m3u8:
                m = re.search(r'<(?:video|source)[^>]*src="([^"]+)"', text, re.S)
                if m: m3u8 = m.group(1)
            if not m3u8:
                m = re.search(r'data-(?:src|url|video)="([^"]+)"', text, re.S)
                if m: m3u8 = m.group(1)

            # ★ 修复反斜杠转义 ★
            if m3u8:
                m3u8 = m3u8.replace('\/', '/')
                urls.append(f'正片${m3u8}')
            else:
                # 未提取到则回退页面地址，由播放器尝试嗅探
                urls.append(f'正片${self.host}/shipinnr/{vid}.html')

        vod = {
            'vod_id': f'video#{vid}',
            'vod_name': title,
            'vod_pic': self._img_url(cover),
            'vod_content': '',
            'vod_remarks': '',
            'vod_play_from': vod_play_from,
            'vod_play_url': '#'.join(urls),
        }
        return {'list': [vod]}

    def _novel_detail(self, vid):
        url = f'/wenzhangs-{vid}.html'
        text = self._fetch(url)
        if not text: return {'list': []}

        title = ''
        m = re.search(r'<h1[^>]*>(.*?)</h1>', text, re.S)
        if m: title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if not title:
            m = re.search(r'<title>([^<]+)</title>', text)
            if m: title = m.group(1).strip()

        content = ''
        # 按常见容器优先级匹配正文
        for pattern in [
            r'<div class="content[^"]*">(.*?)</div>',
            r'<div class="article[^"]*">(.*?)</div>',
            r'<article[^>]*>(.*?)</article>',
            r'<div class="txt[^"]*">(.*?)</div>',
            r'<div class="novel[^"]*">(.*?)</div>',
            r'<div class="detail[^"]*">(.*?)</div>',
            r'<div[^>]*class="[^"]*(?:text|body|main)[^"]*"[^>]*>(.*?)</div>',
        ]:
            m = re.search(pattern, text, re.S)
            if m:
                raw = m.group(1)
                content = re.sub(r'<[^>]+>', '', raw)
                content = content.replace('&nbsp;', ' ').replace('&quot;', '"').replace('&lt;', '<').replace('&gt;', '>')
                content = re.sub(r'\s+', ' ', content).strip()
                if len(content) > 100:
                    break

        if len(content) > 8000:
            content = content[:8000] + '...'

        novel_json = json.dumps({'title': title, 'content': content}, ensure_ascii=False)
        play_url = f'阅读$novel://{novel_json}'

        vod = {
            'vod_id': f'novel#{vid}',
            'vod_name': title,
            'vod_pic': '',
            'vod_content': content[:300] if content else '',
            'vod_remarks': '',
            'vod_play_from': '小说',
            'vod_play_url': play_url,
            'vod_tag': 'text',
            'vod_player': '书',
        }
        return {'list': [vod]}

    def _image_detail(self, vid):
        url = f'/wenzhangs-{vid}.html'
        text = self._fetch(url)
        if not text: return {'list': []}

        title = ''
        m = re.search(r'<h1[^>]*>(.*?)</h1>', text, re.S)
        if m: title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if not title:
            m = re.search(r'<title>([^<]+)</title>', text)
            if m: title = m.group(1).strip()

        # 提取所有大图，过滤掉无关小图标
        imgs = re.findall(r'<img[^>]*src="([^"]+)"[^>]*>', text, re.S)
        big_imgs = []
        seen = set()
        for img in imgs:
            img = img.strip()
            if not img or img in seen:
                continue
            seen.add(img)
            low = img.lower()
            if any(x in low for x in ['logo', 'icon', 'avatar', 'emoji', 'advert', 'ad.', 'banner', 'button']):
                continue
            big_imgs.append(self._img_url(img))

        if not big_imgs:
            return {'list': []}

        pics = '&&'.join(big_imgs)
        play_url = f'查看$pics://{pics}'

        vod = {
            'vod_id': f'image#{vid}',
            'vod_name': title,
            'vod_pic': big_imgs[0] if big_imgs else '',
            'vod_content': f'共 {len(big_imgs)} 张图片',
            'vod_remarks': str(len(big_imgs)) + 'P',
            'vod_play_from': '图片',
            'vod_play_url': play_url,
            'vod_tag': 'image',
            'vod_player': '画',
        }
        return {'list': [vod]}

    # ==================== 搜索 ====================
    def searchContent(self, key, quick, pg="1"):
        try:
            return self._searchContent_inner(key, quick, pg)
        except Exception:
            return {'list': [], 'page': int(pg) if pg else 1, 'pagecount': 1, 'limit': 0, 'total': 0}

    def _searchContent_inner(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        # 搜索默认走视频；小说/图片如需搜索可在此扩展
        url = f'/vodsearch/-------------.html?wd={quote(key)}'
        if page > 1:
            url = f'/vodsearch/{quote(key)}-{page}.html'
        text = self._fetch(url)
        items = self._parse_video_list(text)
        return {
            'list': items,
            'page': page,
            'pagecount': page + 1,
            'limit': len(items),
            'total': page * len(items) + 1
        }

    # ==================== 播放器（全功能解析 + 流媒体捕获兜底）====================
    def playerContent(self, flag, id, vipFlags=None):
        try:
            return self._playerContent_inner(flag, id, vipFlags)
        except Exception:
            return {'parse': 0, 'url': '', 'header': {}, 'position': '0'}

    def _playerContent_inner(self, flag, id, vipFlags=None):
        if id.startswith('novel://'):
            return {'parse': 0, 'url': id, 'header': '', 'vod_player': '书'}
        if id.startswith('pics://'):
            return {'parse': 0, 'playUrl': '', 'url': id, 'header': self.headers}

        # ===== 最强视频提取引擎（13种策略）=====
        def deep_extract_video(html, base_referer=''):
            if not html:
                return ''
            # 1. 直链 m3u8 / mp4
            m = re.search(r'(https?://[^\s"<>\']+?\.(?:m3u8|mp4)[^\s"<>\']*)', html, re.I)
            if m: return m.group(1).replace('\/', '/')

            # 2. player_data JSON（处理 \/ 转义）
            m = re.search(r'var\s+player_data\s*=\s*(\{.*?\});', html, re.S)
            if m:
                try:
                    data = json.loads(m.group(1).replace('\/', '/'))
                    for key in ['url', 'url_next', 'link', 'video']:
                        u = data.get(key, '')
                        if u and ('.m3u8' in u or '.mp4' in u):
                            return u.replace('\/', '/')
                except:
                    pass

            # 3. 常见变量赋值
            var_patterns = [
                r'(?:url|src|video|play|source|m3u8|mp4)\s*=\s*["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)',
                r'var\s+(?:vid|v_url|vsrc|movie|stream)\s*=\s*["\']([^"\']+\.(?:m3u8|mp4))',
            ]
            for p in var_patterns:
                m = re.search(p, html, re.I)
                if m: return m.group(1).replace('\/', '/')

            # 4. video / source 标签
            m = re.search(r'<(?:video|source)[^>]+src=["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)', html, re.I)
            if m: return m.group(1).replace('\/', '/')

            # 5. iframe 递归（一层）
            m = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html, re.I)
            if m:
                iframe_url = m.group(1).replace('\/', '/')
                if not iframe_url.startswith('http'):
                    if iframe_url.startswith('//'):
                        iframe_url = 'https:' + iframe_url
                    elif iframe_url.startswith('/'):
                        iframe_url = self.host + iframe_url
                try:
                    resp = self.session.get(iframe_url, headers=self.headers, timeout=10, verify=False)
                    if resp.status_code == 200:
                        return deep_extract_video(resp.text, base_referer=iframe_url)
                except:
                    pass

            # 6. data-src / data-url / data-video
            m = re.search(r'data-(?:src|url|video)=["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)', html, re.I)
            if m: return m.group(1).replace('\/', '/')

            # 7. meta og:video / twitter:player
            m = re.search(r'<meta[^>]+(?:property|name)=["\'](?:og:video|twitter:player)[^>]+content=["\']([^"\']+\.(?:m3u8|mp4))', html, re.I)
            if m: return m.group(1).replace('\/', '/')

            # 8. JavaScript 跳转 / document.write
            m = re.search(r'(?:window\.location\.href|document\.write)\s*=\s*["\']([^"\']+\.(?:m3u8|mp4))', html, re.I)
            if m: return m.group(1).replace('\/', '/')

            # 9. Base64 编码链接
            m = re.search(r'(?:eval|atob)\s*\(\s*["\']([^"\']+)["\']', html, re.I)
            if m:
                try:
                    decoded = base64.b64decode(m.group(1)).decode('utf-8', errors='ignore')
                    sub_url = deep_extract_video(decoded, base_referer)
                    if sub_url: return sub_url.replace('\/', '/')
                except:
                    pass

            # 10. 注释中的链接
            m = re.search(r'<!--.*?(https?://[^\s]+?\.(?:m3u8|mp4)).*?-->', html, re.S)
            if m: return m.group(1).replace('\/', '/')

            # 11. JSON.parse 内嵌
            m = re.search(r'JSON\.parse\([\'"](\{.*?\})[\'"]', html, re.S)
            if m:
                try:
                    data = json.loads(m.group(1).replace('\/', '/'))
                    for k in data:
                        if isinstance(data[k], str) and ('.m3u8' in data[k] or '.mp4' in data[k]):
                            return data[k].replace('\/', '/')
                except:
                    pass

            # 12. 全局匹配所有引号内视频链接
            all_urls = re.findall(r'["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)', html)
            for u in all_urls:
                u = u.replace('\/', '/')
                if 'http' in u:
                    return u

            # 13. 相对路径补全（如果 base_referer 存在）
            if base_referer:
                m = re.search(r'["\']([^"\']+\.(?:m3u8|mp4))', html)
                if m:
                    path = m.group(1).replace('\/', '/')
                    return base_referer.rstrip('/') + '/' + path.lstrip('/')

            return ''

        # ===== 处理播放页链接 =====
        if id.startswith('http') and '/shipinlay/' in id:
            vid_match = re.search(r'/shipinlay/(\d+)-\d+-\d+\.html', id)
            referer = f'{self.host}/shipinnr/{vid_match.group(1)}.html' if vid_match else self.host + '/'
            req_headers = self.headers.copy()
            req_headers['Referer'] = referer

            try:
                # 禁止重定向，优先捕获 302 到 m3u8
                resp = self.session.get(id, headers=req_headers, timeout=15,
                                       allow_redirects=False, verify=False)
                if resp.status_code in (301, 302, 303, 307, 308):
                    loc = resp.headers.get('Location', '')
                    if loc and self.isVideoFormat(loc):
                        return {'parse': 0, 'url': loc.replace('\/', '/'), 'header': {'Referer': referer}, 'position': '0'}

                text = ''
                if resp.status_code == 200:
                    text = resp.text
                else:
                    resp2 = self.session.get(id, headers=req_headers, timeout=15, verify=False)
                    if resp2.status_code == 200:
                        text = resp2.text

                # 深度提取视频
                video_url = deep_extract_video(text, base_referer=id)
                if self.isVideoFormat(video_url):
                    return {'parse': 0, 'url': video_url.replace('\/', '/'), 'header': {'Referer': referer}, 'position': '0'}

            except:
                pass

            # 若本地解析全部失败，启用流媒体捕获模式（让播放器自行嗅探）
            return {
                'parse': 1,
                'url': id,
                'header': {'Referer': referer},
                'position': '0'
            }

        # 其他 http 链接直接返回（通常是 m3u8 直链或详情页兜底）
        if id.startswith('http'):
            return {'parse': 0, 'url': id.replace('\/', '/'), 'header': {'Referer': self.host + '/'}, 'position': '0'}

        return {'parse': 0, 'url': id.replace('\/', '/'), 'header': {'Referer': self.host + '/'}, 'position': '0'}