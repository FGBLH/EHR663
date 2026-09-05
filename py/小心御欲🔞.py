# -*- coding: utf-8 -*-
import sys
import re
import requests
from urllib.parse import quote
sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
    def init(self, extend=""):
        self.host = "https://xxyy5.cfd"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 11; SAMSUNG SM-G973U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.141 Mobile Safari/537.36",
            "Referer": self.host + "/",
            "Origin": self.host
        }

    def getName(self):
        return "小心御欲"

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|flv|avi|mkv|mov|ts)(\?|$)', url or "", re.I))

    def manualVideoCheck(self):
        return False

    def homeContent(self, filter):
        return {
            "class": [
                {"type_id": "28", "type_name": "国产自拍"},
                {"type_id": "29", "type_name": "主播诱惑"},
                {"type_id": "30", "type_name": "探花约炮"},
                {"type_id": "31", "type_name": "偷拍偷窥"},
                {"type_id": "32", "type_name": "网曝吃瓜"},
                {"type_id": "33", "type_name": "抖阴短片"},
                {"type_id": "34", "type_name": "传媒剧情"},
                {"type_id": "35", "type_name": "日韩主播"},
                {"type_id": "36", "type_name": "日韩无码"},
                {"type_id": "37", "type_name": "中文字幕"},
                {"type_id": "38", "type_name": "AV解说"},
                {"type_id": "39", "type_name": "换脸明星"},
                {"type_id": "40", "type_name": "强奸乱伦"},
                {"type_id": "41", "type_name": "女优明星"},
                {"type_id": "42", "type_name": "欧美激情"},
                {"type_id": "43", "type_name": "重口激情"},
                {"type_id": "44", "type_name": "三级伦理"},
                {"type_id": "45", "type_name": "剧情动漫"},
                {"type_id": "46", "type_name": "SM调教"},
                {"type_id": "47", "type_name": "女同性恋"},
                {"type_id": "48", "type_name": "VR视角"}
            ]
        }

    def homeVideoContent(self):
        return {"list": self.parseList(self.get(self.host + "/"))}

    def categoryContent(self, tid, pg, filter, extend):
        ext = extend or {}
        url = self.host + "/search.php?searchtype=5&tid=" + str(tid) + "&page=" + str(pg)
        for k in ["area", "year", "yuyan", "order"]:
            if ext.get(k):
                url += "&" + k + "=" + quote(str(ext.get(k)))
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
        name = self.clean(self.match(html, r'<h3[^>]*class=["\'][^"\']*title[^"\']*["\'][^>]*>(.*?)</h3>') or self.match(html, r'<h1[^>]*>(.*?)</h1>') or self.match(html, r'<meta property="og:title" content="(.*?)"'))
        pic = self.fix(self.match(html, r'<meta property="og:image" content="(.*?)"') or self.match(html, r'<a[^>]+class=["\'][^"\']*stui-vodlist__thumb[^"\']*["\'][^>]+(?:data-original|data-src|src)=["\']([^"\']+)') or self.match(html, r'<img[^>]+(?:data-original|data-src|src)=["\']([^"\']+)'))
        desc = self.clean(self.match(html, r'<span[^>]*class=["\'][^"\']*detail-content[^"\']*["\'][^>]*>(.*?)</span>') or self.match(html, r'<meta property="og:description" content="(.*?)"') or name)
        play_from = []
        play_url = []
        blocks = re.findall(r'<ul[^>]+class=["\'][^"\']*stui-content__playlist[^"\']*["\'][^>]*>[\s\S]*?</ul>', html or "", re.S)
        for i, p in enumerate(blocks):
            eps = []
            for m in re.finditer(r'<a[^>]+href=["\']([^"\']*?/play/' + re.escape(vid) + r'-[^"\']+)["\'][^>]*>(.*?)</a>', p, re.S):
                t = self.clean(m.group(2)) or self.clean(self.match(m.group(0), r'title=["\']([^"\']+)')) or "播放"
                u = self.fix(m.group(1))
                if t and u:
                    eps.append(t + "$" + u)
            if eps:
                play_from.append("默认" if i == 0 else "线路" + str(i + 1))
                play_url.append("#".join(eps))
        if not play_url:
            eps = []
            for m in re.finditer(r'<a[^>]+href=["\']([^"\']*?/play/' + re.escape(vid) + r'-[^"\']+)["\'][^>]*>(.*?)</a>', html or "", re.S):
                t = self.clean(m.group(2)) or self.clean(self.match(m.group(0), r'title=["\']([^"\']+)')) or "播放"
                u = self.fix(m.group(1))
                if t and u:
                    eps.append(t + "$" + u)
            if eps:
                play_from.append("默认")
                play_url.append("#".join(eps))
        return {
            "list": [{
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic,
                "vod_content": desc,
                "vod_play_from": "$$$".join(play_from),
                "vod_play_url": "$$$".join(play_url)
            }]
        }

    def searchContent(self, key, quick, pg="1"):
        html = ""
        try:
            r = requests.post(self.host + "/search.php", headers=self.headers, data={"searchword": key}, timeout=12, verify=False)
            r.encoding = r.apparent_encoding or "utf-8"
            html = r.text
        except Exception:
            html = ""
        if not html or "/movie/index" not in html:
            html = self.get(self.host + "/search.php?searchword=" + quote(key) + "&page=" + str(pg))
        return {"list": self.parseList(html), "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        url = id if str(id).startswith("http") else self.fix(id)
        if self.isVideoFormat(url):
            return {"parse": 0, "url": url, "header": self.headers}
        html = self.get(url)
        play = self.match(html, r'var\s+now\s*=\s*["\']([^"\']+)["\']') or self.match(html, r'(https?://[^\s"\']+\.(?:m3u8|mp4|flv)[^\s"\']*)')
        if play:
            play = self.fix(play)
            return {"parse": 0 if self.isVideoFormat(play) else 1, "url": play, "header": self.headers}
        return {"parse": 1, "url": url, "header": self.headers}

    def localProxy(self, param):
        return [404, "text/plain", "", ""]

    def destroy(self):
        return "正在Destroy"

    def get(self, url):
        try:
            r = requests.get(url, headers=self.headers, timeout=12, verify=False)
            r.encoding = r.apparent_encoding or "utf-8"
            return r.text
        except Exception:
            return ""

    def match(self, text, rule):
        m = re.search(rule, text or "", re.S)
        return m.group(1) if m else ""

    def clean(self, text):
        return re.sub(r"\s+", " ", re.sub(r"<.*?>", "", text or "")).strip()

    def fix(self, url):
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host + url
        return url

    def parseList(self, html):
        res = []
        seen = set()
        for m in re.finditer(r'<a[^>]+class=["\'][^"\']*stui-vodlist__thumb[^"\']*["\'][^>]+href=["\']/movie/index(\d+)\.html["\'][\s\S]*?(?=<a[^>]+class=["\'][^"\']*stui-vodlist__thumb|</ul>|</body>)', html or "", re.S):
            item = m.group(0)
            vid = m.group(1)
            if not vid or vid in seen:
                continue
            seen.add(vid)
            name = self.clean(self.match(item, r'title=["\']([^"\']+)') or self.match(item, r'alt=["\']([^"\']+)'))
            pic = self.fix(self.match(item, r'(?:data-original|data-src|src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp|gif)[^"\']*)'))
            remarks = self.clean(self.match(item, r'<span[^>]+class=["\'][^"\']*pic-text[^"\']*["\'][^>]*>(.*?)</span>'))
            if name:
                res.append({
                    "vod_id": vid,
                    "vod_name": name,
                    "vod_pic": pic,
                    "vod_remarks": remarks
                })
        if not res:
            for m in re.finditer(r'<a[^>]+href=["\']/movie/index(\d+)\.html["\'][^>]*title=["\']([^"\']+)["\'][\s\S]*?(?:data-original|data-src|src)=["\']([^"\']+)["\']', html or "", re.S):
                vid = m.group(1)
                if vid in seen:
                    continue
                seen.add(vid)
                res.append({
                    "vod_id": vid,
                    "vod_name": self.clean(m.group(2)),
                    "vod_pic": self.fix(m.group(3)),
                    "vod_remarks": ""
                })
        return res