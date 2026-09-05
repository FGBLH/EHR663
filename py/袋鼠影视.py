# -*- coding: utf-8 -*-
import sys
import re
import requests
from urllib.parse import quote, unquote
sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    def init(self, extend=""):
        self.host = "https://dsystv.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 11; SAMSUNG SM-G973U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.141 Mobile Safari/537.36",
            "Referer": self.host + "/",
            "Origin": self.host
        }

    def getName(self):
        return "袋鼠影视"

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|flv|avi|mkv|mov|ts)(\?|$)', url or "", re.I))

    def manualVideoCheck(self):
        return False

    def homeContent(self, filter):
        return {
            "class": [
                {"type_id": "1", "type_name": "电影"},
                {"type_id": "2", "type_name": "电视剧"},
                {"type_id": "3", "type_name": "综艺"},
                {"type_id": "4", "type_name": "动漫"},
                {"type_id": "44", "type_name": "短剧"}
            ]
        }

    def homeVideoContent(self):
        return {"list": self.parseList(self.get(self.host + "/"))}

    def categoryContent(self, tid, pg, filter, extend):
        url = self.host + ("/frim/index" + str(tid) + ".html" if str(pg) == "1" else "/search.php?searchtype=5&tid=" + str(tid) + "&page=" + str(pg))
        html = self.get(url)
        return {
            "page": int(pg),
            "pagecount": 999,
            "limit": 24,
            "total": 999999,
            "list": self.parseList(html)
        }

    def detailContent(self, ids):
        vid = ids[0]
        html = self.get(self.host + "/movie/index" + vid + ".html")

        name = self.clean(
            self.match(html, r'<h1[^>]*>(.*?)</h1>') or
            self.match(html, r'<meta property="og:title" content="(.*?)"')
        )
        name = name.replace("全集在线观看 - 国产剧 | 袋鼠影视", "").replace("全集在线观看 - 袋鼠影视", "").replace("《", "").replace("》", "").strip()

        pic = self.fix(
            self.match(html, r'<meta property="og:image" content="(.*?)"') or
            self.match(html, r'<a[^>]+class="[^"]*videopic[^"]*"[\s\S]*?<img[^>]+(?:data-original|data-src)=["\']([^"\']+)') or
            self.match(html, r'<a[^>]+class="[^"]*videopic[^"]*"[\s\S]*?<img[^>]+src=["\']([^"\']+)')
        )

        desc = self.clean(
            self.match(html, r'<div[^>]*class=["\'][^"\']*video-plot[^"\']*["\'][^>]*>([\s\S]*?)</div>') or
            self.match(html, r'<div class="plot"[^>]*>\s*<p>(.*?)</p>') or
            self.match(html, r'<meta property="og:description" content="(.*?)"')
        )

        actor = self.match(html, r'<li[^>]+data-video-meta=["\']([^"\']*)["\'][^>]*><span class="text-muted">主演：')
        director = self.match(html, r'<li[^>]+data-video-meta=["\']([^"\']*)["\'][^>]*><span class="text-muted">导演：')
        year = self.clean(self.match(html, r'年份：</span>([^<]+)'))
        area = self.clean(self.match(html, r'地区：</span>([^<]+)'))
        lang = self.clean(self.match(html, r'语言：</span>([^<]+)'))
        cate = self.clean(self.match(html, r'类型：</span><a[^>]*>(.*?)</a>'))
        remarks = self.clean(self.match(html, r'<span class="note textbg">(.*?)</span>'))

        play_from, play_url = self.extractPlaySources(html, vid)

        return {
            "list": [{
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": remarks,
                "type_name": cate,
                "vod_year": year,
                "vod_area": area,
                "vod_lang": lang,
                "vod_actor": actor,
                "vod_director": director,
                "vod_content": desc,
                "vod_play_from": "$$$".join(play_from),
                "vod_play_url": "$$$".join(play_url)
            }]
        }

    # ==================== 多线路播放解析 ====================

    def extractPlaySources(self, html, vid):
        """
        从详情页提取多条播放线路。
        网站结构: 每个 panel div 带 data-playlist-name 属性，
        内部包含 <a class="option"> 标签(线路名)和 <ul>(剧集列表)。
        """
        play_from = []
        play_url = []

        # 方法1: 按 data-playlist-name 切分，逐个解析 panel 块
        panel_sections = re.split(
            r'(?=<div[^>]+class=["\'][^"\']*panel[^"\']*["\'][^>]+data-playlist-name=)',
            html
        )
        for section in panel_sections:
            name = self.match(section, r'data-playlist-name=["\']([^"\']+)["\']')
            if not name:
                continue
            name = self.clean(name)

            # 优先匹配带 playlistlink class 的 ul，再回退到任意 ul
            ul_content = (
                self.match(section, r'<ul[^>]+class=["\'][^"\']*playlistlink[^"\']*["\'][^>]*>([\s\S]*?)</ul>') or
                self.match(section, r'<ul[^>]*>([\s\S]*?)</ul>')
            )
            eps = self.extractEpisodes(ul_content, vid) if ul_content else []

            # 如果 HTML 中没有剧集(懒加载)，通过 data-playlist-url 异步获取
            if not eps:
                playlist_url = self.match(section, r'data-playlist-url=["\']([^"\']+)["\']')
                if playlist_url:
                    playlist_url = self.fix(playlist_url.replace('&amp;', '&'))
                    eps = self.extractEpisodes(self.get(playlist_url), vid)

            if eps:
                key = name if name not in play_from else name + str(len(play_from) + 1)
                play_from.append(key)
                play_url.append("#".join(eps))

        # 方法2: 回退 - 按 playlist class div 切分
        if not play_url:
            playlist_sections = re.split(
                r'(?=<div[^>]+class=["\'][^"\']*playlist[^"\']*["\'][^>]*>)',
                html
            )
            for i, section in enumerate(playlist_sections):
                ul_content = self.match(section, r'<ul[^>]*>([\s\S]*?)</ul>')
                if not ul_content:
                    continue
                eps = self.extractEpisodes(ul_content, vid)
                if not eps:
                    continue
                name = self.clean(
                    self.match(section, r'data-playlist-name=["\']([^"\']+)["\']') or
                    self.match(section, r'<a[^>]+class=["\'][^"\']*option[^"\']*["\'][^>]*title=["\']([^"\']+)["\']') or
                    self.match(section, r'<span class="playlist-line-name">([^<]+)</span>')
                ) or ("线路" + str(i + 1))
                key = name if name not in play_from else name + str(len(play_from) + 1)
                play_from.append(key)
                play_url.append("#".join(eps))

        # 方法3: 最终回退 - 按 vid 搜索所有 play 链接
        if not play_url:
            eps = []
            seen = set()
            for m in re.finditer(r'<a[^>]+href=["\']([^"\']*?/play/' + vid + r'-[^"\']+)["\'][^>]*>(.*?)</a>', html, re.S):
                u = self.fix(m.group(1))
                t = self.clean(m.group(2)) or "播放"
                if u and u not in seen:
                    seen.add(u)
                    eps.append(t + "$" + u)
            if eps:
                play_from.append("默认")
                play_url.append("#".join(eps))

        return play_from, play_url

    def extractEpisodes(self, html, vid=""):
        """从包含 <a> 标签的 HTML 中提取剧集列表，自动去重。"""
        eps = []
        seen = set()
        if not html:
            return eps

        # 模式1: <a title="第01集" href="/play/xxx.html">
        for m in re.finditer(r'<a[^>]+title=["\']([^"\']+)["\'][^>]+href=["\']([^"\']*?/play/[^"\']+)["\']', html, re.S):
            t = self.clean(m.group(1))
            u = self.fix(m.group(2))
            if t and u and u not in seen:
                seen.add(u)
                eps.append(t + "$" + u)

        # 模式2: <a href="/play/xxx.html" ...>第01集</a>
        if not eps:
            for m in re.finditer(r'<a[^>]+href=["\']([^"\']*?/play/[^"\']+)["\'][^>]*>(.*?)</a>', html, re.S):
                t = self.clean(m.group(2))
                u = self.fix(m.group(1))
                if t and u and u not in seen:
                    seen.add(u)
                    eps.append(t + "$" + u)

        return eps

    # ==================== 搜索 & 播放 ====================

    def searchContent(self, key, quick, pg="1"):
        html = ""
        try:
            r = requests.post(self.host + "/search.php", headers=self.headers, data={"searchword": key}, timeout=15)
            r.encoding = r.apparent_encoding or "utf-8"
            html = r.text
        except Exception:
            html = ""
        data = self.parseList(html)
        if not data:
            html = self.get(self.host + "/search.php?searchword=" + quote(key) + "&page=" + str(pg))
            data = self.parseList(html)
        return {"list": data, "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        html = self.get(id)

        # 多模式提取视频地址
        url = self.match(html, r'var\s+now\s*=\s*["\']([^"\']+)["\']')

        if not url:
            url = self.match(html, r'player_aaaa\s*=\s*\{[^}]*"url"\s*:\s*"([^"]+)"')

        if not url:
            url = self.match(html, r'["\']([^"\']+(?:m3u8|mp4|flv|avi|mkv|mov|ts)[^"\']*)["\']')

        if not url:
            url = self.match(html, r'<(?:iframe|embed|source|video)[^>]+src=["\']([^"\']+)["\']')

        url = unquote(url) if url else id

        return {
            "parse": 0 if self.isVideoFormat(url) else 1,
            "playUrl": "",
            "url": url,
            "header": self.headers
        }

    # ==================== 列表解析 ====================

    def parseList(self, html):
        res = []
        seen = set()
        for m in re.finditer(r'<a[^>]+class=["\'][^"\']*videopic[^"\']*["\'][^>]+href=["\']/movie/index(\d+)\.html["\'][^>]*title=["\']([^"\']+)["\']([\s\S]{0,1200}?)</a>', html or "", re.S):
            vid = m.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            item = m.group(0)
            name = self.clean(m.group(2))
            pics = re.findall(r'(?:data-original|data-src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp|gif)[^"\']*)["\']', item, re.I)
            if not pics:
                pics = re.findall(r'src=["\']([^"\']+\.(?:jpg|jpeg|png|webp|gif)[^"\']*)["\']', item, re.I)
            pic = ""
            for p in pics:
                if "load.gif" not in p and "nopic" not in p and "logo" not in p and "templets" not in p:
                    pic = self.fix(p)
                    break
            remarks = self.clean(self.match(item, r'<span[^>]+class=["\'][^"\']*note[^"\']*["\'][^>]*>(.*?)</span>') or self.match(item, r'<span[^>]+class=["\'][^"\']*textbg[^"\']*["\'][^>]*>(.*?)</span>'))
            if name:
                res.append({
                    "vod_id": vid,
                    "vod_name": name,
                    "vod_pic": pic,
                    "vod_remarks": remarks
                })
        if not res:
            for m in re.finditer(r'href=["\']/movie/index(\d+)\.html["\'][^>]*title=["\']([^"\']+)["\'][\s\S]{0,1200}?<img[^>]+([^>]+)>', html or "", re.S):
                vid = m.group(1)
                if vid in seen:
                    continue
                seen.add(vid)
                img = m.group(3)
                pic = self.match(img, r'(?:data-original|data-src)=["\']([^"\']+)["\']') or self.match(img, r'src=["\']([^"\']+)["\']')
                if "load.gif" in pic or "templets" in pic:
                    pic = ""
                res.append({
                    "vod_id": vid,
                    "vod_name": self.clean(m.group(2)),
                    "vod_pic": self.fix(pic),
                    "vod_remarks": ""
                })
        return res

    # ==================== 工具方法 ====================

    def localProxy(self, param):
        return [404, "text/plain", "", ""]

    def destroy(self):
        return "正在Destroy"

    def get(self, url):
        try:
            r = requests.get(url, headers=self.headers, timeout=15, verify=False)
            r.encoding = r.apparent_encoding or "utf-8"
            return r.text
        except Exception:
            return ""

    def match(self, text, rule):
        m = re.search(rule, text or "", re.S)
        return m.group(1) if m else ""

    def clean(self, text):
        return re.sub(r"\s+", " ", re.sub(r"<.*?>", "", text or "").replace("&nbsp;", " ")).strip()

    def fix(self, url):
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host + url
        return url
