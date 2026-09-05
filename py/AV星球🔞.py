# -*- coding: utf-8 -*-
#!/usr/bin/python
# 目标: https://xqxq1.cc/ (AV星球)

import sys, re, json, base64, html, os, threading, time, hashlib
from urllib.parse import quote, unquote, urljoin, urlparse
try:
    from lxml import etree
except ImportError:
    etree = None
try:
    import requests
except ImportError:
    requests = None
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def init(self, extend=""): pass
        def homeContent(self, filter): pass
        def homeVideoContent(self): pass
        def categoryContent(self, tid, pg, filter, extend): pass
        def detailContent(self, ids): pass
        def playerContent(self, flag, id, vipFlags=None): pass
        def searchContent(self, key, quick, pg='1'): pass
        def isVideoFormat(self, url): pass
        def manualVideoCheck(self): pass
        def localProxy(self, param): pass

def fix_url(url, host):
    if not url: return ""
    if url.startswith("//"): return "https:" + url
    if url.startswith("/"): return urljoin(host, url)
    if url.startswith("http"): return url
    return urljoin(host, "/" + url)

def clean_text(text):
    if not text: return ""
    return html.unescape(re.sub(r"<[^>]+>", "", str(text))).strip()

class Spider(BaseSpider):
    def __init__(self):
        super().__init__()
        self.host = "https://xqxq1.cc"
        self.name = "AV星球"
        self.s = requests.Session() if requests else None
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/",
            "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120"',
        }
        self.cms_type = "v10"
        self.content_type = "video"
        self.seen_ids = set()
        if self.s: self.s.headers.update(self.headers)

    def init(self, extend=""):
        if extend and extend.startswith("http"):
            self.host = extend.rstrip("/")
            self.headers["Referer"] = self.host + "/"
            if self.s: self.s.headers.update(self.headers)

    def getName(self):
        return self.name

    def isVideoFormat(self, url):
        return any(x in url for x in [".m3u8", ".mp4", ".flv", ".ts"])

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return [200, "video/MP2T", b"", {}]

    def _fetch(self, url):
        if not self.s: return ""
        try:
            r = self.s.get(url, timeout=15, headers=self.headers, verify=False)
            r.raise_for_status()
            r.encoding = "utf-8"
            return r.text
        except Exception as e:
            return ""

    def homeContent(self, filter):
        try:
            classes = [
                {"type_name": "学生萝莉", "type_id": "66"},
                {"type_name": "日本av", "type_id": "44"},
                {"type_name": "口交自慰", "type_id": "62"},
                {"type_name": "群交多P", "type_id": "63"},
                {"type_name": "强奸迷奸", "type_id": "67"},
                {"type_name": "丝袜制服", "type_id": "68"},
                {"type_name": "国产AV", "type_id": "46"},
                {"type_name": "乱伦系列", "type_id": "45"},
                {"type_name": "素人特摄", "type_id": "65"},
                {"type_name": "探花约炮", "type_id": "47"},
                {"type_name": "日韩精选", "type_id": "61"},
                {"type_name": "VR专区", "type_id": "64"},
                {"type_name": "主播大秀", "type_id": "48"},
                {"type_name": "反差母狗", "type_id": "70"},
                {"type_name": "国产传媒", "type_id": "50"},
                {"type_name": "网曝吃瓜", "type_id": "49"},
                {"type_name": "异域风情", "type_id": "71"},
                {"type_name": "中文字幕", "type_id": "53"},
                {"type_name": "偷拍偷窥", "type_id": "51"},
                {"type_name": "色情动漫", "type_id": "55"},
            ]
            filters = {}
            return {"class": classes, "filters": filters}
        except Exception as e:
            return {"class": [], "filters": {}}

    def homeVideoContent(self):
        return self.categoryContent("66", "1", False, {})

    def categoryContent(self, tid, pg, filter, extend):
        try:
            result = {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}
            url = f"{self.host}/index.php/vod/type/id/{tid}.html"
            if int(pg) > 1:
                url = f"{self.host}/index.php/vod/type.html?id={tid}&page={pg}"
            html_text = self._fetch(url)
            if not html_text: return result
            items = re.findall(
                r'<a class="poster[^"]*" href="(/index\.php/vod/play/id/(\d+)\.html)" data-url="([^"]+)">\s*<img[^>]+data-src="([^"]+)"[^>]*alt="([^"]*)"',
                html_text, re.S
            )
            if not items:
                items = re.findall(
                    r'href="(/index\.php/vod/play/id/(\d+)\.html)"[^>]*data-url="([^"]+)".*?data-src="([^"]+)"[^>]*alt="([^"]*)"',
                    html_text, re.S
                )
            self.seen_ids.clear()
            for href, vid, data_url, pic, title in items:
                try:
                    if vid in self.seen_ids: continue
                    self.seen_ids.add(vid)
                    pic = fix_url(pic, self.host)
                    title = clean_text(title)
                    duration = ""
                    block_pattern = re.escape(href) + r'"[^>]*>.*?</a>'
                    block_match = re.search(block_pattern, html_text, re.S)
                    if block_match:
                        block = block_match.group(0)
                        dur_match = re.search(r'<span class="text-sm">([^<]+)</span>', block)
                        if dur_match: duration = dur_match.group(1).strip()
                    result["list"].append({
                        "vod_id": vid,
                        "vod_name": title,
                        "vod_pic": pic,
                        "vod_remarks": duration,
                    })
                except Exception:
                    continue
            pc = re.search(r'rel="next" href="[^"]*page=(\d+)"', html_text)
            if pc:
                result["pagecount"] = max(int(pg) + 1, int(pc.group(1)))
            else:
                has_next = re.search(r'href="[^"]*[?&]page=\d+"', html_text)
                if has_next:
                    result["pagecount"] = int(pg) + 1
            return result
        except Exception as e:
            return {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}

    def detailContent(self, ids):
        try:
            vid = ids[0] if isinstance(ids, list) else ids
            result = {"list": []}
            url = f"{self.host}/index.php/vod/play/id/{vid}.html"
            html_text = self._fetch(url)
            if not html_text: return result
            title = ""
            title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html_text)
            if title_match: title = clean_text(title_match.group(1))
            pic = ""
            pic_match = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html_text)
            if pic_match: pic = pic_match.group(1)
            if not pic:
                pic_match = re.search(r"let poster = '([^']+)'", html_text)
                if pic_match: pic = pic_match.group(1)
            pic = fix_url(pic, self.host)
            play_url = ""
            source_match = re.search(r"const source = '([^']+)'", html_text)
            if source_match: play_url = source_match.group(1)
            if not play_url:
                data_match = re.search(rf'href="/index\.php/vod/play/id/{re.escape(vid)}\.html"[^>]*data-url="([^"]+)"', html_text)
                if data_match:
                    du = data_match.group(1)
                    if '$' in du: play_url = du.split('$', 1)[1]
                    else: play_url = du
            if not play_url:
                m3u8_match = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', html_text)
                if m3u8_match: play_url = m3u8_match.group(1)
            play_url = fix_url(play_url, self.host)
            sources = ["正片"] if play_url else []
            play_urls = [f"正片${play_url}"] if play_url else []
            result["list"].append({
                "vod_id": vid,
                "vod_name": title or vid,
                "vod_pic": pic,
                "vod_play_from": "$$$".join(sources) if sources else "默认",
                "vod_play_url": "$$$".join(play_urls) if play_urls else f"播放${vid}",
            })
            return result
        except Exception as e:
            return {"list": []}

    def playerContent(self, flag, id, vipFlags=None):
        try:
            result = {"parse": 0, "playUrl": "", "url": "", "header": ""}
            if self.isVideoFormat(id):
                result["url"] = id
                result["header"] = json.dumps({"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]})
                return result
            if id.startswith("http") and ".m3u8" in id:
                result["url"] = id
                result["header"] = json.dumps({"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]})
                return result
            if id.startswith("http"):
                html_text = self._fetch(id)
                if html_text:
                    source_match = re.search(r"const source = '([^']+)'", html_text)
                    if source_match:
                        result["url"] = source_match.group(1)
                        result["header"] = json.dumps({"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]})
                        return result
            result["url"] = id
            return result
        except Exception as e:
            return {"parse": 0, "playUrl": "", "url": id, "header": ""}

    def searchContent(self, key, quick, pg="1"):
        try:
            result = {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}
            url = f"{self.host}/index.php/vod/search.html?wd={quote(key)}&page={pg}"
            html_text = self._fetch(url)
            if not html_text: return result
            items = re.findall(
                r'<a class="poster[^"]*" href="(/index\.php/vod/play/id/(\d+)\.html)" data-url="([^"]+)">\s*<img[^>]+data-src="([^"]+)"[^>]*alt="([^"]*)"',
                html_text, re.S
            )
            if not items:
                items = re.findall(
                    r'href="(/index\.php/vod/play/id/(\d+)\.html)"[^>]*data-url="([^"]+)".*?data-src="([^"]+)"[^>]*alt="([^"]*)"',
                    html_text, re.S
                )
            self.seen_ids.clear()
            for href, vid, data_url, pic, title in items:
                try:
                    if vid in self.seen_ids: continue
                    self.seen_ids.add(vid)
                    pic = fix_url(pic, self.host)
                    title = clean_text(title)
                    result["list"].append({
                        "vod_id": vid,
                        "vod_name": title,
                        "vod_pic": pic,
                    })
                except Exception:
                    continue
            has_next = re.search(r'href="[^"]*[?&]page=\d+"', html_text)
            if has_next:
                result["pagecount"] = int(pg) + 1
            return result
        except Exception as e:
            return {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}
