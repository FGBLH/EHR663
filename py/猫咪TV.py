# -*- coding: utf-8 -*-
import re
import urllib.parse
import requests
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def __init__(self):
            return None
class Spider(BaseSpider):
    BASE_URL = "https://maomi66.cc"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 12; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36",
        "Referer": "https://maomi66.cc/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
    }
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self._class_cache = []
    def getName(self):
        return "猫咪AV"
    def init(self, extend=""):
        return None
    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|flv|avi|mkv|mov)(\?|$)', url or '', re.I))
    def manualVideoCheck(self):
        return True
    def homeContent(self, filter):
        html = self._get(self.BASE_URL)
        classes = self._classes(html)
        return {"class": classes, "list": self._parse_list(html), "filters": {}, "parse": 0, "jx": 0}
    def homeVideoContent(self):
        return {"list": self._parse_list(self._get(self.BASE_URL))}
    def categoryContent(self, tid, pg, filter, extend):
        page = self._to_int(pg, 1)
        html = self._get(self.BASE_URL + "/list/%s-%s.html" % (tid, page))
        data = self._parse_list(html)
        return {"list": data, "page": page, "pagecount": page + 1 if data else page, "limit": len(data) or 20, "total": (page + 1) * (len(data) or 20)}
    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) and ids else str(ids)
        url = vid if str(vid).startswith("http") else self.BASE_URL + "/video/%s.html" % vid
        html = self._get(url)
        title = self._clean(self._match(html, r'<h1[^>]*>(.*?)</h1>') or self._match(html, r'<h2[^>]*>(.*?)</h2>') or self._match(html, r'<title[^>]*>(.*?)</title>'))
        if not title:
            title = "视频%s" % re.sub(r'\D+', '', str(vid))
        pic = self._fix(self._match(html, r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)') or self._match(html, r'<video[^>]+poster=["\']([^"\']+)') or self._match(html, r'(?:data-original|data-src|src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp|gif)[^"\']*)'))
        play = self._extract_play(html)
        tags = []
        for x in re.findall(r'<a[^>]+href=["\']/list/\d+-1\.html["\'][^>]*>(.*?)</a>', html, re.S):
            t = self._clean(x)
            if t and t not in tags:
                tags.append(t)
        content = self._clean(self._match(html, r'<div[^>]+class=["\'][^"\']*(?:des|intro|content|info)[^"\']*["\'][^>]*>(.*?)</div>')) or title
        vod = {
            "vod_id": str(vid).split("/")[-1].replace(".html", ""),
            "vod_name": title,
            "vod_pic": pic,
            "type_name": "/".join(tags[:3]),
            "vod_year": "",
            "vod_area": "",
            "vod_remarks": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": content,
            "vod_play_from": "默认",
            "vod_play_url": "播放$%s" % (play or url)
        }
        return {"list": [vod]}
    def searchContent(self, key, quick, pg="1"):
        q = urllib.parse.quote(str(key or ""))
        page = self._to_int(pg, 1)
        html = self._get(self.BASE_URL + "/search.php?content=%s&type=1&page=%s" % (q, page))
        data = self._parse_list(html)
        if not data:
            html = self._get(self.BASE_URL + "/search.php?content=%s&type=1" % q)
            data = self._parse_list(html)
        return {"list": data, "page": page, "pagecount": page + 1 if data else page, "limit": len(data) or 20, "total": (page + 1) * (len(data) or 20)}
    def playerContent(self, flag, id, vipFlags):
        url = urllib.parse.unquote(str(id or ""))
        if "/video/" in url or re.fullmatch(r'\d+', url):
            page = url if url.startswith("http") else self.BASE_URL + "/video/%s.html" % url
            play = self._extract_play(self._get(page))
            url = play or page
        return {"parse": 0, "playUrl": "", "url": self._fix(url), "header": self.HEADERS}
    def _classes(self, html):
        arr = []
        for tid, name in re.findall(r'href=["\']/list/(\d+)-1\.html["\'][^>]*>(.*?)</a>', html or "", re.S):
            name = self._clean(name)
            if tid and name and not any(x["type_id"] == tid for x in arr):
                arr.append({"type_id": tid, "type_name": name})
        if not arr:
            arr = [
                {"type_id": "69829818", "type_name": "国产精品"},
                {"type_id": "71188148", "type_name": "国产自拍"},
                {"type_id": "43659662", "type_name": "日本精品"},
                {"type_id": "37440125", "type_name": "欧美极品"},
                {"type_id": "19211697", "type_name": "中文字幕"},
                {"type_id": "77777777", "type_name": "动漫精品"}
            ]
        self._class_cache = arr
        return arr
    def _parse_list(self, html):
        out = []
        blocks = re.findall(r'<li[\s\S]*?</li>', html or "", re.I)
        if not blocks:
            blocks = re.findall(r'<a[^>]+href=["\']/video/\d+\.html["\'][\s\S]*?</a>', html or "", re.I)
        for item in blocks:
            vid = self._match(item, r'href=["\'][^"\']*/video/(\d+)\.html["\']')
            if not vid:
                continue
            name = self._clean(self._match(item, r'<h5[^>]*>\s*<a[^>]*>(.*?)</a>') or self._match(item, r'title=["\']([^"\']+)') or self._match(item, r'alt=["\']([^"\']+)'))
            pic = self._fix(self._match(item, r'data-original=["\']([^"\']+)') or self._match(item, r'data-src=["\']([^"\']+)') or self._match(item, r'<img[^>]+src=["\']([^"\']+)'))
            remark = self._clean(self._match(item, r'<span[^>]*>(.*?)</span>') or self._match(item, r'<em[^>]*>(.*?)</em>'))
            if not name:
                name = "视频%s" % vid
            vod = {"vod_id": vid, "vod_name": name, "vod_pic": pic, "vod_remarks": remark}
            if not any(x["vod_id"] == vid for x in out):
                out.append(vod)
        return out
    def _extract_play(self, html):
        play = self._match(html, r'hls\.loadSource\(["\']([^"\']+)["\']\)') or self._match(html, r'video\.src\s*=\s*["\']([^"\']+)["\']') or self._match(html, r'<source[^>]+src=["\']([^"\']+)["\']') or self._match(html, r'["\'](https?://[^"\']+play\.php\?[^"\']+)["\']') or self._match(html, r'["\'](/play\.php\?[^"\']+)["\']')
        return self._fix(play)
    def _get(self, url):
        if not url:
            return ""
        url = self._fix(url)
        headers = dict(self.HEADERS)
        headers["Referer"] = self.BASE_URL + "/"
        try:
            r = self.session.get(url, headers=headers, timeout=12, verify=False)
            if not r.encoding or r.encoding.lower() == "iso-8859-1":
                r.encoding = r.apparent_encoding or "utf-8"
            return r.text
        except requests.RequestException:
            return ""
    def _match(self, text, pattern, default=""):
        m = re.search(pattern, text or "", re.S | re.I)
        if not m:
            return default
        return m.group(1) if m.lastindex else m.group(0)
    def _clean(self, text):
        text = re.sub(r'<script[\s\S]*?</script>|<style[\s\S]*?</style>', ' ', text or '', flags=re.I)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = text.replace('&nbsp;', ' ').replace('&amp;amp;', '&').replace('&amp;', '&').replace('&#038;', '&').replace('&quot;', '"').replace('&#39;', "'").replace('&lt;', '<').replace('&gt;', '>')
        return re.sub(r'\s+', ' ', text).strip()
    def _fix(self, url):
        url = (url or "").strip().replace("\\/", "/")
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.BASE_URL + url
        return url
    def _to_int(self, value, default=1):
        try:
            return int(value)
        except Exception:
            return default