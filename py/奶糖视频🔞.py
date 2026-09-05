# -*- coding: utf-8 -*-
import sys
import re
import json
import requests
from urllib.parse import quote, unquote
sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
    def init(self, extend=""):
        self.host = "https://ewrzka4.naitang8.top"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 11; SAMSUNG SM-G973U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.141 Mobile Safari/537.36",
            "Referer": self.host + "/",
            "Origin": self.host
        }

    def getName(self):
        return "奶糖视频"

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|flv|avi|mkv|mov|ts)(\?|$)', url or "", re.I))

    def manualVideoCheck(self):
        return False

    def homeContent(self, filter):
        return {
            "class": [
                {"type_id": "1", "type_name": "中文字幕"},
                {"type_id": "6", "type_name": "日本有码"},
                {"type_id": "2", "type_name": "cosplay"},
                {"type_id": "7", "type_name": "日本无码"},
                {"type_id": "3", "type_name": "黑丝诱惑"},
                {"type_id": "8", "type_name": "解说专区"}
            ],
            "filters": {}
        }

    def homeVideoContent(self):
        return {"list": self.parseList(self.get(self.host + "/"))}

    def categoryContent(self, tid, pg, filter, extend):
        url = self.host + ("/index.php/vod/type/id/" + str(tid) + ".html" if str(pg) == "1" else "/index.php/vod/show/id/" + str(tid) + "/page/" + str(pg) + ".html")
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
        html = self.get(self.host + "/index.php/vod/detail/id/" + vid + ".html")
        name = self.clean(self.match(html, r'<h1[^>]*>(.*?)</h1>') or self.match(html, r'<meta property="og:title" content="(.*?)"'))
        name = name.replace("在线观看", "").replace("奶糖视频", "").replace("《", "").replace("》", "").strip()
        pic = self.fix(self.match(html, r'<meta property="og:image" content="(.*?)"') or self.match(html, r'<a[^>]+class=["\'][^"\']*video-img[^"\']*["\'][^>]+(?:data-original|data-src)=["\']([^"\']+)') or self.match(html, r'<img[^>]+(?:data-original|data-src)=["\']([^"\']+)'))
        desc = self.clean(self.match(html, r'剧情：([\s\S]*?)</') or self.match(html, r'<meta property="og:description" content="(.*?)"'))
        actor = self.clean(self.match(html, r'演员：</span>([\s\S]*?)</p>') or self.match(html, r'主演：</span>([\s\S]*?)</p>'))
        director = self.clean(self.match(html, r'导演：</span>([\s\S]*?)</p>'))
        year = self.clean(self.match(html, r'年份：</span>([^<]+)'))
        area = self.clean(self.match(html, r'地区：</span>([^<]+)'))
        lang = self.clean(self.match(html, r'语言：</span>([^<]+)'))
        cate = self.clean(self.match(html, r'类型：</span>([\s\S]*?)</p>'))
        remarks = self.clean(self.match(html, r'<span[^>]+class=["\'][^"\']*voddate[^"\']*["\'][^>]*>(.*?)</span>') or self.match(html, r'状态：</span>([^<]+)'))
        tabs = [self.clean(x) for x in re.findall(r'<li[^>]+class=["\'][^"\']*ewave-tab[^"\']*["\'][^>]*[\s\S]*?<a[^>]*>(.*?)</a>', html, re.S)]
        panels = re.findall(r'<ul[^>]+class=["\'][^"\']*playlist[^"\']*["\'][^>]*>([\s\S]*?)</ul>', html, re.S)
        play_from = []
        play_url = []
        for i, p in enumerate(panels):
            eps = []
            for m in re.finditer(r'<a[^>]+href=["\']([^"\']*?/index\.php/vod/play/id/' + vid + r'/sid/\d+/nid/\d+\.html)["\'][^>]*>(.*?)</a>', p, re.S):
                t = self.clean(m.group(2)) or "播放"
                u = self.fix(m.group(1))
                if t and u:
                    eps.append(t + "$" + u)
            if not eps:
                for m in re.finditer(r'<a[^>]+href=["\']([^"\']*?/index\.php/vod/play/[^"\']+)["\'][^>]*>(.*?)</a>', p, re.S):
                    t = self.clean(m.group(2)) or "播放"
                    u = self.fix(m.group(1))
                    if t and u:
                        eps.append(t + "$" + u)
            if eps:
                key = tabs[i] if i < len(tabs) and tabs[i] else "线路" + str(i + 1)
                if key not in play_from:
                    play_from.append(key)
                    play_url.append("#".join(eps))
        if not play_url:
            eps = []
            for m in re.finditer(r'<a[^>]+href=["\']([^"\']*?/index\.php/vod/play/id/' + vid + r'/sid/\d+/nid/\d+\.html)["\'][^>]*>(.*?)</a>', html, re.S):
                t = self.clean(m.group(2)) or "高清"
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

    def searchContent(self, key, quick, pg="1"):
        html = self.get(self.host + "/index.php/vod/search.html?wd=" + quote(key) + "&page=" + str(pg))
        return {"list": self.parseList(html), "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        html = self.get(id)
        url = ""
        m = re.search(r'player_aaaa\s*=\s*(\{[\s\S]*?\})\s*<', html)
        if m:
            try:
                data = json.loads(m.group(1).replace("\\/", "/"))
                url = data.get("url", "")
            except Exception:
                url = ""
        if not url:
            url = self.match(html, r'"url"\s*:\s*"([^"]+)"') or self.match(html, r"'url'\s*:\s*'([^']+)'")
        url = unquote(url.replace("\\/", "/")) if url else id
        return {"parse": 0 if self.isVideoFormat(url) else 1, "playUrl": "", "url": url, "header": self.headers}

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

    def parseList(self, html):
        res = []
        seen = set()
        for m in re.finditer(r'<a[^>]+class=["\'][^"\']*video-img[^"\']*["\'][^>]+href=["\']/index\.php/vod/detail/id/(\d+)\.html["\'][^>]*([\s\S]{0,1600}?)</a>[\s\S]{0,500}?<p[^>]+class=["\'][^"\']*video-name[^"\']*["\'][^>]*>\s*<a[^>]+[^>]*title=["\']([^"\']+)["\']', html or "", re.S):
            vid = m.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            item = m.group(0) + m.group(2)
            name = self.clean(m.group(3))
            pics = re.findall(r'(?:data-original|data-src|data-lazyload|data-lazy-src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp|gif)[^"\']*)["\']', item, re.I)
            if not pics:
                pics = re.findall(r'src=["\']([^"\']+\.(?:jpg|jpeg|png|webp|gif)[^"\']*)["\']', item, re.I)
            pic = ""
            for p in pics:
                if "load.gif" not in p and "nopic" not in p and "logo" not in p and "template" not in p:
                    pic = self.fix(p)
                    break
            remarks = self.clean(self.match(item, r'<span[^>]+class=["\'][^"\']*voddate[^"\']*["\'][^>]*>(.*?)</span>') or self.match(item, r'<span[^>]+class=["\'][^"\']*note[^"\']*["\'][^>]*>(.*?)</span>'))
            if name:
                res.append({
                    "vod_id": vid,
                    "vod_name": name,
                    "vod_pic": pic,
                    "vod_remarks": remarks
                })
        if not res:
            for m in re.finditer(r'href=["\']/index\.php/vod/detail/id/(\d+)\.html["\'][^>]*[\s\S]{0,1000}?title=["\']([^"\']+)["\'][\s\S]{0,1200}?<img[^>]+([^>]+)>', html or "", re.S):
                vid = m.group(1)
                if vid in seen:
                    continue
                seen.add(vid)
                img = m.group(3)
                pic = self.match(img, r'(?:data-original|data-src|data-lazyload|data-lazy-src)=["\']([^"\']+)["\']') or self.match(img, r'src=["\']([^"\']+)["\']')
                if "load.gif" in pic or "template" in pic:
                    pic = ""
                res.append({
                    "vod_id": vid,
                    "vod_name": self.clean(m.group(2)),
                    "vod_pic": self.fix(pic),
                    "vod_remarks": ""
                })
        return res