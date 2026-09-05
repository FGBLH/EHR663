#!/usr/bin/python
# -*- coding: utf-8 -*-
import re, base64, requests
from urllib.parse import quote
from base.spider import Spider

class Spider(Spider):
    def getName(self): return "低端影视"
    def init(self, extend=""):
        self.host = "https://ddysx.cc"
        self.headers = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36","Referer":self.host + "/"}
        self.s = requests.Session()
        self.s.headers.update(self.headers)
        self.play_headers = {"User-Agent":self.headers["User-Agent"],"Referer":self.host + "/","Origin":self.host,"Accept":"*/*","Connection":"keep-alive"}
        self.pic_cache = {}
        self.classes = [{"type_id":"12028759","type_name":"一区-日韩无码"},{"type_id":"12198759","type_name":"一区-中文字幕"},{"type_id":"12208759","type_name":"一区-动漫精品"},{"type_id":"12218759","type_name":"一区-极骚萝莉"},{"type_id":"12248759","type_name":"一区-三级自慰"},{"type_id":"12258759","type_name":"一区-强奸乱伦"},{"type_id":"12008759","type_name":"一区-国产自拍"},{"type_id":"12018759","type_name":"一区-欧美极品"},{"type_id":"12228839","type_name":"二区-主播直播"},{"type_id":"12468839","type_name":"二区-91探花"},{"type_id":"12588839","type_name":"二区-传媒出品"},{"type_id":"12338839","type_name":"二区-自拍偷拍"},{"type_id":"12368839","type_name":"二区-日本精品"},{"type_id":"12298839","type_name":"二区-欧美精品"},{"type_id":"12198839","type_name":"二区-精品推荐"},{"type_id":"12218839","type_name":"二区-国产情色"},{"type_id":"12038769","type_name":"三区-国产精品"},{"type_id":"12178769","type_name":"三区-中文字幕"},{"type_id":"12198769","type_name":"三区-动漫精品"},{"type_id":"12228769","type_name":"三区-日韩精品"},{"type_id":"12268769","type_name":"三区-自拍偷拍"},{"type_id":"12418769","type_name":"三区-大秀视频"},{"type_id":"12008769","type_name":"三区-日韩无码"},{"type_id":"12028769","type_name":"三区-欧美精品"}]

    def _get(self, url):
        try:
            r = self.s.get(url, timeout=10, verify=False)
            r.encoding = r.apparent_encoding or "utf-8"
            return r.text
        except requests.RequestException: return ""
    def _fix(self, u): return "https:" + u if u and u.startswith("//") else self.host + u if u and u.startswith("/") else u or ""
    def _dec(self, s):
        try: return base64.b64decode(s + "=" * (-len(s) % 4)).decode("utf-8", "ignore").strip()
        except Exception: return ""
    def _txt(self, html): return re.sub(r"<[^>]+>", "", re.sub(r"<script[^>]*>\s*document\.write\(d\(['\"]([^'\"]+)['\"]\)\);?\s*</script>", lambda m:self._dec(m.group(1)), html or "", flags=re.S)).strip()
    def _pic(self, html):
        key = html or ""
        if key in self.pic_cache: return self.pic_cache[key]
        m = re.search(r"<img[^>]+data-original=['\"]([^'\"]+)['\"]", key) or re.search(r"<img[^>]+data-src=['\"]([^'\"]+)['\"]", key) or re.search(r"<img[^>]+src=['\"]([^'\"]+)['\"]", key)
        u = self._fix(m.group(1)) if m else ""
        if u.startswith("https://pic.892539.xyz//"): u = "https://pic.892539.xyz/" + u.split("https://pic.892539.xyz//", 1)[1]
        self.pic_cache[key] = u
        return u
    def _parse_list(self, html):
        items, seen = [], set()
        for block in re.findall(r"<li\b[\s\S]*?</li>", html or ""):
            m = re.search(r"href=['\"](/video/(\d+)\.html)['\"]", block)
            if not m or m.group(2) in seen: continue
            seen.add(m.group(2))
            name = self._txt(block)
            name = re.sub(r"\s+", " ", name).strip()
            if name: items.append({"vod_id":m.group(2),"vod_name":name,"vod_pic":self._pic(block)})
        return items
    def homeContent(self, filter):
        html = self._get(self.host + "/")
        return {"class":self.classes,"list":self._parse_list(html),"filters":{}}
    def categoryContent(self, tid, pg, filter, extend):
        html = self._get(f"{self.host}/list/{tid}-{pg}.html")
        return {"page":int(pg),"pagecount":999,"limit":24,"total":99999,"list":self._parse_list(html)}
    def detailContent(self, ids):
        data = []
        for vid in ids:
            html = self._get(f"{self.host}/video/{vid}.html")
            name = self._txt("".join(re.findall(r"<h[1-5][^>]*>[\s\S]*?</h[1-5]>", html)[:1])) or vid
            pic = self._pic(html)
            play = re.search(r"<video[^>]+src=['\"]([^'\"]+)['\"]", html) or re.search(r"hls\.loadSource\(['\"]([^'\"]+)['\"]\)", html) or re.search(r"(https?://[^'\"\s<>]+play\.php\?[^'\"\s<>]+)", html)
            url = play.group(1) if play else f"{self.host}/video/{vid}.html"
            data.append({"vod_id":vid,"vod_name":name,"vod_pic":pic,"vod_play_from":"播放","vod_play_url":"播放$" + url})
        return {"list":data}
    def searchContent(self, key, quick, pg="1"):
        html = self._get(f"{self.host}/search.php?content={quote(key)}")
        return {"list":[] if "负载过高" in html else self._parse_list(html),"page":int(pg)}
    def playerContent(self, flag, id, vipFlags):
        url = self._fix(id)
        return {"parse":0,"url":url,"header":self.play_headers}