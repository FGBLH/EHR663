# -*- coding: utf-8 -*-
import json
import re
import urllib.parse
import requests

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        pass

class Spider(BaseSpider):
    BASE_URL = "https://x3av.com"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Referer": "https://x3av.com/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }

    def __init__(self):
        self.siteUrl = self.BASE_URL
        self.extend = {}

    def init(self, extend=""):
        if extend:
            try:
                self.extend = json.loads(extend) if isinstance(extend, str) else extend
                self.siteUrl = self.extend.get("siteUrl", self.BASE_URL).rstrip("/")
            except Exception:
                self.siteUrl = self.BASE_URL

    def getName(self):
        return "樱花传媒"

    def isVideoFormat(self, url):
        return bool(re.search(r"\.(m3u8|mp4|flv|avi|mkv)(\?|$)", url or "", re.I))

    def manualVideoCheck(self):
        return True

    def homeContent(self, filter):
        classes = [
            {"type_id": "1", "type_name": "有码"},
            {"type_id": "2", "type_name": "无码"},
            {"type_id": "3", "type_name": "素人"},
            {"type_id": "4", "type_name": "中文字幕"}
        ]
        filters = {}
        for i in [x["type_id"] for x in classes]:
            filters[i] = [
                {"key": "by", "name": "排序", "value": [
                    {"n": "最新", "v": "time"},
                    {"n": "热门", "v": "hits"},
                    {"n": "评分", "v": "score"}
                ]}
            ]
        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        html = self._get(self.siteUrl)
        return {"list": self._parse_list(html)}

    def categoryContent(self, tid, pg, filter, extend):
        pg = str(pg or "1")
        by = (extend or {}).get("by", "")
        if by and by != "time":
            url = self.siteUrl + "/vshow/by/{}/id/{}/page/{}.html".format(by, tid, pg)
        else:
            url = self.siteUrl + "/category/{}.html".format(tid) if pg == "1" else self.siteUrl + "/category/{}/page/{}.html".format(tid, pg)
        html = self._get(url)
        videos = self._parse_list(html)
        return {"page": int(pg), "pagecount": int(pg) + 1 if videos else int(pg), "limit": 24, "total": 999999, "list": videos}

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) else ids
        url = self._full_url(vid)
        html = self._get(url)
        name = self._clean(self._match(html, r"<h1[^>]*>(.*?)</h1>") or self._match(html, r"<title[^>]*>(.*?)</title>") or "")
        pic = self._match(html, r'background\s*:\s*url\((.*?)\)') or self._match(html, r'<img[^>]+data-original=["\']([^"\']+)') or self._match(html, r'<img[^>]+data-src=["\']([^"\']+)') or self._match(html, r'<img[^>]+src=["\']([^"\']+)')
        desc = self._clean(self._match(html, r'<div[^>]+class=["\'][^"\']*(?:desc|content|video-info)[^"\']*["\'][^>]*>(.*?)</div>') or "")
        actor = self._clean(self._match(html, r"主演[:：&nbsp;\s]*([^<]+)") or "")
        remarks = self._clean(self._match(html, r"番号[:：&nbsp;\s]*([^<]+)") or "")
        play_items = []
        for m in re.finditer(r'<a[^>]+id=["\']playerserver["\'][^>]*>', html, re.I):
            tag = m.group(0)
            vodid = self._attr(tag, "data-vodid")
            sid = self._attr(tag, "data-sid") or "1"
            nid = self._attr(tag, "data-nid") or "1"
            title = self._clean(self._match(html[m.end():m.end()+200], r"([^<]+)</a>") or "播放{}".format(len(play_items) + 1))
            if vodid:
                play_items.append("{}${}|{}|{}".format(title, vodid, sid, nid))
        if not play_items:
            mid = self._match(url, r"/videos/(\d+)")
            if mid:
                play_items.append("播放${}|1|1".format(mid))
        vod = {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": self._real_pic(pic),
            "type_name": "",
            "vod_year": "",
            "vod_area": "",
            "vod_remarks": remarks,
            "vod_actor": actor,
            "vod_director": "",
            "vod_content": desc,
            "vod_play_from": "樱花传媒",
            "vod_play_url": "#".join(play_items)
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        wd = urllib.parse.quote(key)
        url = self.siteUrl + "/search.html?wd={}".format(wd) if str(pg) == "1" else self.siteUrl + "/search.html?wd={}&page={}".format(wd, pg)
        html = self._get(url)
        return {"list": self._parse_list(html)}

    def playerContent(self, flag, id, vipFlags):
        pp = str(id).split("|")
        if len(pp) < 3:
            return {"parse": 1, "playUrl": "", "url": id, "header": self.HEADERS}
        data = {"ids": pp[0], "flag": "player", "sid": pp[1], "nid": pp[2]}
        headers = dict(self.HEADERS)
        headers["X-Requested-With"] = "XMLHttpRequest"
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        try:
            res = requests.post(self.siteUrl + "/api.php/post/urlget/", data=data, headers=headers, timeout=15, verify=False)
            text = res.text
        except requests.RequestException:
            text = ""
        iframe = ""
        try:
            obj = json.loads(text)
            iframe = self._match(obj.get("player", ""), r'<iframe[^>]+src=["\']([^"\']+)')
        except Exception:
            iframe = self._match(text, r'<iframe[^>]+src=["\']([^"\']+)')
        iframe = self._full_url(iframe)
        real = self._extract_player_url(iframe)
        if real:
            return {"parse": 0, "playUrl": "", "url": real, "header": {"User-Agent": self.HEADERS["User-Agent"], "Referer": iframe}}
        return {"parse": 1, "playUrl": "", "url": iframe, "header": {"User-Agent": self.HEADERS["User-Agent"], "Referer": self.siteUrl + "/"}}

    def localProxy(self, param):
        return [404, "text/plain", ""]

    def _parse_list(self, html):
        html = re.sub(r"<!--[\s\S]*?-->", "", html or "")
        arr = []
        blocks = re.findall(r'<div[^>]+class=["\'][^"\']*video-elem[^"\']*["\'][\s\S]*?(?=<div[^>]+class=["\'][^"\']*video-elem|<ul[^>]+class=["\'][^"\']*pagination|</body>|$)', html, re.I)
        if not blocks:
            blocks = re.findall(r'<a[^>]+href=["\'][^"\']*/videos/\d+\.html[^"\']*["\'][\s\S]*?</a>', html, re.I)
        for block in blocks:
            href = self._match(block, r'href=["\']([^"\']*/videos/\d+\.html[^"\']*)')
            name = self._clean(self._match(block, r'<a[^>]+class=["\'][^"\']*title[^"\']*["\'][^>]*>(.*?)</a>') or self._match(block, r'title=["\']([^"\']+)') or self._match(block, r'alt=["\']([^"\']+)'))
            img_tag = self._match(block, r'(<img[\s\S]*?>)')
            pic = self._attr(img_tag, "data-original") or self._attr(img_tag, "data-src") or self._attr(img_tag, "src")
            remark = self._clean(self._match(block, r'<span[^>]+class=["\'][^"\']*(?:duration|remarks|time)[^"\']*["\'][^>]*>(.*?)</span>') or "")
            pic = self._real_pic(pic)
            if href and name:
                arr.append({"vod_id": self._full_url(href), "vod_name": name, "vod_pic": pic, "vod_remarks": remark})
        return arr

    def _extract_player_url(self, iframe):
        if not iframe:
            return ""
        html = self._get(iframe, {"Referer": self.siteUrl + "/"})
        code = self._unpack(html) or html
        p = {}
        m = re.search(r"var\s+p\s*=\s*(\{.*?\})\s*;", code, re.S)
        if m:
            for k, v in re.findall(r'["\']?(hls\d+|mp4|file)["\']?\s*:\s*["\']([^"\']+)["\']', m.group(1), re.I):
                p[k.lower()] = v.replace("\\/", "/")
        url = p.get("hls2") or p.get("hls3") or p.get("hls4") or p.get("file") or p.get("mp4")
        if not url:
            sm = re.search(r'sources\s*:\s*\[\s*\{\s*file\s*:\s*(p\.(hls\d+|file|mp4)|["\']([^"\']+)["\'])', code, re.I)
            if sm:
                url = p.get((sm.group(2) or "").lower()) or sm.group(3) or ""
        if not url:
            urls = re.findall(r'https?://[^"\']+?\.(?:m3u8|mp4)(?:\?[^"\']*)?|/[A-Za-z0-9_./-]+/(?:master|index)\.(?:m3u8|mp4)(?:\?[^"\']*)?', code, re.I)
            for u in urls:
                if "jpg" not in u.lower() and "png" not in u.lower():
                    url = u
                    break
        return self._join(iframe, url)

    def _unpack(self, html):
        m = re.search(r"eval\(function\(p,a,c,k,e,d\).*?\}\('(.+?)',(\d+),(\d+),'(.+?)'\.split\('\|'\)\)\)", html or "", re.S)
        if not m:
            return ""
        p, a, c, k = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4).split("|")
        for i in range(c - 1, -1, -1):
            if i < len(k) and k[i]:
                p = re.sub(r"\b" + re.escape(self._base_n(i, a)) + r"\b", k[i], p)
        return p

    def _get(self, url, headers=None):
        if not url:
            return ""
        h = dict(self.HEADERS)
        if headers:
            h.update(headers)
        try:
            r = requests.get(url, headers=h, timeout=15, verify=False)
            if r.encoding == "ISO-8859-1":
                r.encoding = r.apparent_encoding
            return r.text
        except requests.RequestException:
            return ""

    def _full_url(self, url):
        url = (url or "").replace("&amp;", "&").strip()
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("http"):
            return url
        if url.startswith("/"):
            return self.siteUrl + url
        return self.siteUrl + "/" + url

    def _join(self, base, url):
        url = (url or "").replace("\\/", "/").replace("&amp;", "&").strip()
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("http"):
            return url
        return urllib.parse.urljoin(base, url)

    def _real_pic(self, url):
        url = self._full_url(url or "")
        url = url.replace("&amp;", "&").strip()
        if not url or "noimage" in url.lower() or url.endswith("/"):
            return ""
        if "getimages.php" in url and "src=" in url:
            m = re.search(r"src=([^&]+)", url)
            if m:
                src = urllib.parse.unquote(m.group(1)).replace("&amp;", "&")
                if src.startswith("http") and "noimage" not in src.lower():
                    return src
        m = re.search(r"(https?://[^&'\"]+\.(?:jpg|jpeg|png|webp))", url, re.I)
        if m:
            return urllib.parse.unquote(m.group(1))
        return url

    def _match(self, text, pattern):
        m = re.search(pattern, text or "", re.S | re.I)
        return m.group(1).strip() if m else ""

    def _attr(self, tag, key):
        return self._match(tag, key + r'=["\']([^"\']+)')

    def _clean(self, text):
        text = re.sub(r"<[^>]+>", " ", text or "")
        text = urllib.parse.unquote(text)
        text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")
        return re.sub(r"\s+", " ", text).strip()

    def _base_n(self, num, base):
        chars = "0123456789abcdefghijklmnopqrstuvwxyz"
        if num == 0:
            return "0"
        s = ""
        while num:
            s = chars[num % base] + s
            num //= base
        return s