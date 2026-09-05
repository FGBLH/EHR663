# -*- coding: utf-8 -*-
# 星梦ASMR (www.asmrzy.top) TVBox 爬虫

import re
import json
import requests
from urllib.parse import quote, urljoin, parse_qs, urlparse

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def init(self, extend=""): pass
        def homeContent(self, filter): return {'class': [], 'filters': {}}
        def homeVideoContent(self): return {'list': []}
        def categoryContent(self, tid, pg, filter, extend): return {'list': [], 'page': 1, 'pagecount': 1}
        def detailContent(self, ids): return {'list': []}
        def playerContent(self, flag, id, vipFlags=None): return {'parse': 0, 'url': '', 'header': {}}
        def searchContent(self, key, quick, pg='1'): return {'list': [], 'page': 1, 'pagecount': 1}

class Spider(BaseSpider):
    BASE_URL = "https://www.asmrzy.top"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    # 分类 slug 与显示名称映射（导航栏顺序）
    CATEGORY_MAP = {
        "cn": "中国",
        "kr": "韩国",
        "jp": "日本",
        "other": "其他",
        "listen": "音频",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.session.verify = False

    def init(self, extend=""):
        if extend and extend.startswith("http"):
            self.BASE_URL = extend.rstrip("/")
        # 支持通过 extend 传入 cookie
        if extend and "cookie=" in extend:
            for part in extend.split("&"):
                if part.startswith("cookie="):
                    cookie_val = part.split("=", 1)[1]
                    self.session.headers.update({"Cookie": cookie_val})
        return None

    def getName(self):
        return "星梦ASMR"

    def homeContent(self, filter):
        classes = []
        for slug, name in self.CATEGORY_MAP.items():
            classes.append({"type_id": slug, "type_name": name})
        return {"class": classes, "filters": {}}

    def homeVideoContent(self):
        # 默认取第一个分类（中国）的最新内容
        return self.categoryContent("cn", "1", False, {})

    def _fetch_html(self, url):
        try:
            resp = self.session.get(url, timeout=15)
            if resp.status_code == 200:
                return resp.text
            return ""
        except Exception:
            return ""

    def _parse_post_item(self, article_html, url_base):
        """
        从文章列表的 HTML 片段中解析单篇文章信息
        传入的 article_html 是包含该文章的完整 li 或 div 块
        """
        # 标题
        title_match = re.search(r'<a[^>]+class="[^"]*title[^"]*"[^>]*>([^<]+)</a>', article_html)
        if not title_match:
            return None
        title = title_match.group(1).strip()

        # 链接（详情页）
        link_match = re.search(r'<a[^>]+href="([^"]+)"[^>]*class="[^"]*thumbnail[^"]*"', article_html)
        if not link_match:
            link_match = re.search(r'<a[^>]+href="([^"]+)"[^>]*>.*?<img', article_html)
        if not link_match:
            return None
        link = link_match.group(1)
        if not link.startswith("http"):
            link = urljoin(self.BASE_URL, link)

        # 提取文章 ID（从链接中取数字）
        vid_match = re.search(r'/(\d+)\.html', link)
        vid = vid_match.group(1) if vid_match else link

        # 图片
        img_match = re.search(r'<img[^>]+data-src="([^"]+)"', article_html)
        if not img_match:
            img_match = re.search(r'<img[^>]+src="([^"]+)"', article_html)
        pic = img_match.group(1) if img_match else ""

        # 日期（在 meta 或 time 标签中）
        date_match = re.search(r'<time[^>]*>([^<]+)</time>', article_html)
        if not date_match:
            date_match = re.search(r'<li>(\d{4}年\d{2}月\d{2}日)</li>', article_html)
        remarks = date_match.group(1).strip() if date_match else ""

        return {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": remarks,
        }

    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = int(pg)
        except:
            pg = 1
        if pg < 1:
            pg = 1

        # 分类页 URL 格式：/category/{slug}/{pg}/
        url = f"{self.BASE_URL}/category/{tid}/{pg}/" if pg > 1 else f"{self.BASE_URL}/category/{tid}/"
        html = self._fetch_html(url)
        if not html:
            return {'list': [], 'page': pg, 'pagecount': 1}

        # 提取文章列表项（每个 li 或 div）
        # 主题使用 <ul class="joe_archive__list joe_list"> 下每个 li.joe_list__item
        items = re.findall(r'<li[^>]*class="[^"]*joe_list__item[^"]*"[^>]*>(.*?)</li>', html, re.S)
        if not items:
            # 尝试匹配更宽泛的列表项
            items = re.findall(r'<li[^>]*>(.*?)</li>', html, re.S)

        videos = []
        for item_html in items:
            post = self._parse_post_item(item_html, url)
            if post:
                videos.append(post)

        # 分页信息：从分页导航中提取总页数
        pagecount = pg
        pagination = re.search(r'<ul[^>]*class="[^"]*joe_pagination[^"]*"[^>]*>(.*?)</ul>', html, re.S)
        if pagination:
            pages = re.findall(r'<a[^>]*>(\d+)</a>', pagination.group(1))
            if pages:
                pagecount = max(int(p) for p in pages)
            # 如果当前页没有更多，可能 pagecount 等于 pg

        return {
            'list': videos,
            'page': pg,
            'pagecount': pagecount,
            'limit': 20,
            'total': 0
        }

    def _extract_video_from_html(self, html):
        """从详情页 HTML 提取视频 URL（iframe/video/smartideo）"""
        if not html:
            return None

        # 1. 提取 iframe（B站/YouTube 最常见）
        iframe_matches = re.findall(r'<iframe[^>]+src="([^"]+)"', html, re.I)
        for src in iframe_matches:
            src = src.strip()
            # 如果是相对路径，补全
            if src.startswith('//'):
                src = 'https:' + src
            elif src.startswith('/'):
                src = urljoin(self.BASE_URL, src)
            # 过滤掉广告或无用的 iframe
            if 'google' in src or 'trustpilot' in src or 'tree-nation' in src:
                continue
            return src

        # 2. smartideo 插件的 data-src 或 data-url
        smartideo = re.search(r'<div[^>]*class="[^"]*smartideo[^"]*"[^>]*data-(?:src|url)="([^"]+)"', html, re.I)
        if smartideo:
            return smartideo.group(1)

        # 3. video 标签
        video_src = re.search(r'<video[^>]+src="([^"]+)"', html, re.I)
        if video_src:
            return video_src.group(1)

        # 4. source 标签
        source_src = re.search(r'<source[^>]+src="([^"]+)"', html, re.I)
        if source_src:
            return source_src.group(1)

        # 5. 直链 mp4/m3u8/webm
        direct = re.search(r'(https?://[^\s"\']+\.(?:mp4|m3u8|webm|flv))', html, re.I)
        if direct:
            return direct.group(1)

        # 6. a 标签中的链接
        a_link = re.search(r'<a[^>]+href="(https?://[^"]+\.(?:mp4|m3u8|webm))"', html, re.I)
        if a_link:
            return a_link.group(1)

        return None

    def _parse_platform(self, url):
        """识别视频平台，返回 (platform, identifier)"""
        if not url:
            return None, None

        # B站：bilibili.com/video/ 或 player.bilibili.com/player.html?bvid= 或 aid=
        bili = re.search(r'(?:bilibili\.com/video/|player\.bilibili\.com/player\.html\?[^"]*bvid=)([a-zA-Z0-9]+)', url, re.I)
        if bili:
            return "bilibili", bili.group(1)
        bili_aid = re.search(r'player\.bilibili\.com/player\.html\?[^"]*aid=(\d+)', url, re.I)
        if bili_aid:
            return "bilibili_aid", bili_aid.group(1)

        # YouTube
        yt = re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})', url, re.I)
        if yt:
            return "youtube", yt.group(1)

        # 直接链接
        return "direct", url

    def _aid_to_bvid(self, aid):
        try:
            resp = self.session.get(f"https://api.bilibili.com/x/web-interface/view?aid={aid}", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0:
                    return data["data"].get("bvid")
        except:
            pass
        return None

    def _get_bilibili_playurl(self, vid, is_aid=False):
        """获取 B站视频直链，支持 bvid 或 aid"""
        try:
            if is_aid:
                bvid = self._aid_to_bvid(vid)
                if not bvid:
                    view_url = f"https://api.bilibili.com/x/web-interface/view?aid={vid}"
                else:
                    view_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
            else:
                view_url = f"https://api.bilibili.com/x/web-interface/view?bvid={vid}"

            headers = {
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://www.bilibili.com",
            }
            resp = self.session.get(view_url, headers=headers, timeout=10)
            if resp.status_code != 200:
                return None
            data = resp.json()
            if data.get("code") != 0:
                return None
            cid = data["data"]["cid"]
            bvid = data["data"]["bvid"]

            play_url = f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&qn=80"
            resp = self.session.get(play_url, headers=headers, timeout=10)
            if resp.status_code != 200:
                return None
            data = resp.json()
            if data.get("code") != 0:
                return None
            durl = data["data"]["durl"]
            if not durl:
                return None
            return durl[0]["url"]
        except:
            return None

    def detailContent(self, ids):
        if not ids or not ids[0]:
            return {'list': []}
        vid = ids[0]

        # 构造详情页 URL：文章 ID 或 slug，但通常就是 /{id}.html
        detail_url = f"{self.BASE_URL}/{vid}.html"
        html = self._fetch_html(detail_url)
        if not html:
            return {'list': []}

        # 提取标题
        title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        title = title_match.group(1).strip() if title_match else "未知"

        # 提取图片（文章特色图或内容第一张）
        pic_match = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)
        if not pic_match:
            pic_match = re.search(r'<img[^>]+class="[^"]*thumbnail[^"]*"[^>]+src="([^"]+)"', html)
        if not pic_match:
            pic_match = re.search(r'<img[^>]+src="([^"]+)"', html)
        pic = pic_match.group(1) if pic_match else ""

        # 提取摘要
        excerpt_match = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]+)"', html)
        excerpt = excerpt_match.group(1) if excerpt_match else ""

        # 提取视频 URL
        video_url = self._extract_video_from_html(html)

        if video_url:
            platform, vid_id = self._parse_platform(video_url)
            if platform == "bilibili":
                play_url = f"bilibili://{vid_id}"
            elif platform == "bilibili_aid":
                play_url = f"bilibili_aid://{vid_id}"
            elif platform == "youtube":
                play_url = f"youtube://{vid_id}"
            else:
                # 直链
                play_url = f"播放${video_url}"

            vod = {
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_content": excerpt,
                "vod_play_from": "视频",
                "vod_play_url": play_url,
            }
        else:
            vod = {
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_content": "未提取到视频地址，可能需手动解析。",
                "vod_play_from": "",
                "vod_play_url": "",
            }

        return {'list': [vod]}

    def playerContent(self, flag, id, vipFlags=None):
        if id and id.startswith("bilibili://"):
            bvid = id.split("://")[-1]
            url = self._get_bilibili_playurl(bvid, is_aid=False)
            if url:
                return {'parse': 0, 'url': url, 'header': {"Referer": "https://www.bilibili.com"}}
            else:
                return {'parse': 0, 'url': f"https://player.bilibili.com/player.html?bvid={bvid}", 'header': {}}
        elif id and id.startswith("bilibili_aid://"):
            aid = id.split("://")[-1]
            url = self._get_bilibili_playurl(aid, is_aid=True)
            if url:
                return {'parse': 0, 'url': url, 'header': {"Referer": "https://www.bilibili.com"}}
            else:
                return {'parse': 0, 'url': f"https://player.bilibili.com/player.html?aid={aid}", 'header': {}}
        elif id and id.startswith("youtube://"):
            yid = id.split("://")[-1]
            return {'parse': 0, 'url': f"https://www.youtube.com/embed/{yid}?autoplay=1", 'header': {}}
        elif id and id.startswith("http"):
            return {'parse': 0, 'url': id, 'header': {}}
        else:
            return {'parse': 0, 'url': '', 'header': {}}

    def searchContent(self, key, quick, pg="1"):
        try:
            pg = int(pg)
        except:
            pg = 1
        if pg < 1:
            pg = 1
        # 网站搜索使用 POST，但支持 GET 参数 ?s=keyword
        search_url = f"{self.BASE_URL}/?s={quote(key)}"
        if pg > 1:
            search_url += f"&page={pg}"
        html = self._fetch_html(search_url)
        if not html:
            return {'list': [], 'page': pg, 'pagecount': 1}

        # 搜索结果可能同样在列表项中，复用解析
        items = re.findall(r'<li[^>]*class="[^"]*joe_list__item[^"]*"[^>]*>(.*?)</li>', html, re.S)
        videos = []
        for item_html in items:
            post = self._parse_post_item(item_html, search_url)
            if post:
                videos.append(post)

        # 简单分页：如果没有下一页，pagecount = pg
        pagecount = pg
        pagination = re.search(r'<ul[^>]*class="[^"]*joe_pagination[^"]*"[^>]*>(.*?)</ul>', html, re.S)
        if pagination:
            pages = re.findall(r'<a[^>]*>(\d+)</a>', pagination.group(1))
            if pages:
                pagecount = max(int(p) for p in pages)

        return {
            'list': videos,
            'page': pg,
            'pagecount': pagecount,
            'limit': 20,
            'total': 0
        }

    def isVideoFormat(self, url):
        return url and any(ext in url for ext in ['.m3u8', '.mp4', '.webm', '.flv'])

    def localProxy(self, param):
        return [404, 'text/plain', b'']