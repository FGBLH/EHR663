# -*- coding: utf-8 -*-
import re
import urllib.parse
import requests

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        pass

class Spider(BaseSpider):
    BASE_URL = "https://madou.club"
    DASH_URL = "https://dash.madou.club"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": BASE_URL + "/",
    }

    def __init__(self):
        super().__init__()
        self.name = "麻豆社"
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self._class_cache = None

    def init(self, extend="{}"):
        return None

    def getName(self):
        return self.name

    def homeContent(self, filter):
        html = self._get(self.BASE_URL + "/")
        return {"class": self._classes(html), "filters": {}, "list": self._parse_list(html), "parse": 0, "jx": 0}

    def homeVideoContent(self):
        return {"list": self._parse_list(self._get(self.BASE_URL + "/"))}

    def categoryContent(self, tid, pg, filter, extend):
        page = self._to_int(pg, 1)
        base = tid if str(tid).startswith("http") else self.BASE_URL + "/category/" + str(tid).strip("/")
        url = base.rstrip("/") if page <= 1 else base.rstrip("/") + "/page/" + str(page)
        data = self._parse_list(self._get(url))
        return {"page": page, "pagecount": page if len(data) < 10 else page + 1, "limit": 20, "total": 99999, "list": data, "parse": 0, "jx": 0}

    def detailContent(self, ids):
        result = {"list": [], "parse": 0, "jx": 0}
        if not ids:
            return result
        url = ids[0]
        html = self._get(url)
        name = self._clean(self._match(html, r'<h1[^>]*class=["\']article-title["\'][^>]*>(.*?)</h1>') or self._match(html, r'<title>(.*?)</title>').split("-")[0])
        pic = self._match(html, r'shareimage\s*:\s*["\']([^"\']+)') or self._match(html, r'<img[^>]+data-src=["\']([^"\']+)') or self._match(html, r'<img[^>]+src=["\']([^"\']+)')
        cate = self._clean(self._match(html, r'分类：\s*<a[^>]*>(.*?)</a>'))
        remarks = self._clean(self._match(html, r'观看\((.*?)\)'))
        tag_block = self._match(html, r'<div[^>]+class=["\']article-tags["\'][^>]*>(.*?)</div>')
        tags = ",".join([self._clean(x) for x in re.findall(r'<a[^>]*>(.*?)</a>', tag_block, re.S)])
        iframe = self._match(html, r'<iframe[^>]+src=["\']?([^"\'\s>]+)')
        play_id = urllib.parse.urljoin(self.BASE_URL, iframe or url)
        result["list"].append({"vod_id": url, "vod_name": name, "vod_pic": urllib.parse.urljoin(self.BASE_URL, pic), "type_name": cate, "vod_year": "", "vod_area": "", "vod_remarks": remarks, "vod_actor": tags, "vod_director": "", "vod_content": name, "vod_play_from": "DPlayer", "vod_play_url": name + "$" + play_id})
        return result

    def searchContent(self, key, quick, pg="1"):
        page = self._to_int(pg, 1)
        q = urllib.parse.quote(str(key))
        url = self.BASE_URL + "/?s=" + q if page <= 1 else self.BASE_URL + "/page/" + str(page) + "?s=" + q
        data = self._parse_list(self._get(url))
        return {"page": page, "pagecount": page if len(data) < 10 else page + 1, "limit": 20, "total": 99999, "list": data, "parse": 0, "jx": 0}

    def playerContent(self, flag, id, vipFlags):
        result = {"parse": 0, "playUrl": "", "url": id or "", "jx": 0, "header": {"User-Agent": self.HEADERS["User-Agent"], "Referer": self.BASE_URL + "/"}}
        if not id:
            return result
        play_page = id
        if "dash.madou.club/share/" not in play_page:
            html = self._get(play_page)
            play_page = urllib.parse.urljoin(self.BASE_URL, self._match(html, r'<iframe[^>]+src=["\']?([^"\'\s>]+)') or play_page)
        html = self._get(play_page, {"Referer": self.BASE_URL + "/"})
        token = self._match(html, r'var\s+token\s*=\s*["\']([^"\']*)')
        m3u8 = self._match(html, r'var\s+m3u8\s*=\s*["\']([^"\']+\.m3u8)["\']')
        if m3u8:
            url = urllib.parse.urljoin(self.DASH_URL, m3u8)
            result["url"] = url + (("&" if "?" in url else "?") + "token=" + token if token else "")
            result["header"] = {"User-Agent": self.HEADERS["User-Agent"], "Referer": play_page, "Origin": self.BASE_URL}
        return result

    def _classes(self, html=None):
        if self._class_cache:
            return self._class_cache
        html = html or self._get(self.BASE_URL + "/")
        classes, seen = [], set()
        for href, name in re.findall(r'<a[^>]+href=["\'](https://madou\.club/category/[^"\']+)["\'][^>]*>(.*?)</a>', html, re.S):
            name = self._clean(name)
            key = href.rstrip("/")
            if key not in seen and name:
                seen.add(key)
                classes.append({"type_id": href, "type_name": name})
        self._class_cache = classes
        return classes

    def _parse_list(self, html):
        data = []
        blocks = re.findall(r'<article\b.*?</article>', html, re.S) or re.findall(r'<li>.*?</li>', html, re.S)
        for item in blocks:
            href = self._match(item, r'<a[^>]+href=["\']([^"\']+\.html)["\']')
            name = self._clean(self._match(item, r'<h2[^>]*>.*?<a[^>]*>(.*?)</a>') or self._match(item, r'<a[^>]*>(?:<span.*?</span>)?\s*(.*?)</a>'))
            pic = self._match(item, r'<img[^>]+data-src=["\']([^"\']+)') or self._match(item, r'<img[^>]+src=["\']([^"\']+)')
            remarks = self._clean(self._match(item, r'<time[^>]*>(.*?)</time>') or self._match(item, r'观看\((.*?)\)'))
            if href and name:
                data.append({"vod_id": urllib.parse.urljoin(self.BASE_URL, href), "vod_name": name, "vod_pic": urllib.parse.urljoin(self.BASE_URL, pic), "vod_remarks": remarks})
        return data

    def _get(self, url, headers=None):
        h = dict(self.HEADERS)
        if headers:
            h.update(headers)
        try:
            return self.session.get(url, headers=h, timeout=15, verify=False).text
        except Exception:
            return ""

    def _match(self, text, pattern):
        m = re.search(pattern, text or "", re.S | re.I)
        return m.group(1).strip() if m else ""

    def _clean(self, text):
        text = re.sub(r'<.*?>', '', text or '')
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&#038;', '&').replace('"', '"')
        return re.sub(r'\s+', ' ', text).strip()

    def _to_int(self, value, default=0):
        try:
            return int(value)
        except Exception:
            return default