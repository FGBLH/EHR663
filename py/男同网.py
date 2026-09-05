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
    BASE_URL = "https://91nt.com"
    FALLBACK_URLS = ["https://91nt.com"]
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": BASE_URL + "/",
    }

    def __init__(self):
        super().__init__()
        self.name = "91NT"
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self._class_cache = None

    def init(self, extend="{}"):
        return None

    def getName(self):
        return self.name

    def homeContent(self, filter):
        html = self._get(self.BASE_URL + "/videos")
        return {"class": self._classes(), "filters": {}, "list": self._parse_list(html), "parse": 0, "jx": 0}

    def homeVideoContent(self):
        return {"list": self._parse_list(self._get(self.BASE_URL + "/videos"))}

    def categoryContent(self, tid, pg, filter, extend):
        page = self._to_int(pg, 1)
        path = str(tid or "/videos").strip()
        url = self._fix_url(path if path.startswith("http") else self.BASE_URL + (path if path.startswith("/") else "/" + path))
        url = url if page <= 1 else url + ("&page=" if "?" in url else "?page=") + str(page)
        data = self._parse_list(self._get(url))
        return {"page": page, "pagecount": page if len(data) < 12 else page + 1, "limit": 24, "total": 99999, "list": data, "parse": 0, "jx": 0}

    def detailContent(self, ids):
        result = {"list": [], "parse": 0, "jx": 0}
        if not ids:
            return result
        url = self._fix_url(ids[0] if str(ids[0]).startswith("http") else self.BASE_URL + "/" + str(ids[0]).strip("/"))
        html = self._get(url)
        name = self._clean(self._match(html, r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)') or self._match(html, r'"title"\s*:\s*"([^"]+)') or self._match(html, r'<title>(.*?)</title>').split("-")[0])
        pic = self._match(html, r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)') or self._match(html, r'"poster"\s*:\s*"([^"]+)') or self._match(html, r'<img[^>]+(?:data-original|data-src|data-lazy-src|data-lazyload|src)=["\']([^"\']+)')
        content = self._clean(self._match(html, r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)') or self._match(html, r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)') or name)
        duration = self._match(html, r'<meta[^>]+property=["\']video:duration["\'][^>]+content=["\']([^"\']+)')
        year = self._match(html, r'<meta[^>]+property=["\']video:release_date["\'][^>]+content=["\']([^"\']+)')[:10]
        tags = ",".join([self._clean(x) for x in re.findall(r'<meta[^>]+property=["\']video:tag["\'][^>]+content=["\']([^"\']+)', html, re.S | re.I)])
        play = self._play_url(url, html) or url
        result["list"].append({"vod_id": url, "vod_name": name, "vod_pic": urllib.parse.urljoin(self.BASE_URL, pic), "type_name": tags, "vod_year": year, "vod_area": "", "vod_remarks": self._dur(duration), "vod_actor": tags, "vod_director": "", "vod_content": content, "vod_play_from": "91NT", "vod_play_url": "正片$" + play})
        return result

    def searchContent(self, key, quick, pg="1"):
        page = self._to_int(pg, 1)
        q = urllib.parse.quote(str(key))
        url = self.BASE_URL + "/videos/search/" + q
        url = url if page <= 1 else url + "?page=" + str(page)
        data = self._parse_list(self._get(url))
        return {"page": page, "pagecount": page if len(data) < 12 else page + 1, "limit": 24, "total": 99999, "list": data, "parse": 0, "jx": 0}

    def playerContent(self, flag, id, vipFlags):
        result = {"parse": 0, "playUrl": "", "url": id or "", "jx": 0, "header": {"User-Agent": self.HEADERS["User-Agent"], "Referer": self.BASE_URL + "/"}}
        if not id:
            return result
        if ".m3u8" in id or ".mp4" in id:
            return result
        play_page = self._fix_url(id if str(id).startswith("http") else self.BASE_URL + "/" + str(id).strip("/"))
        html = self._get(play_page)
        play = self._play_url(play_page, html)
        if play:
            result["url"] = play
            result["header"] = {"User-Agent": self.HEADERS["User-Agent"], "Referer": play_page, "Origin": self.BASE_URL}
        else:
            result["url"] = play_page
            result["parse"] = 1
        return result

    def localProxy(self, params):
        return None

    def _classes(self, html=None):
        if self._class_cache:
            return self._class_cache
        self._class_cache = [
            {"type_id": "/videos/all/new", "type_name": "今日更新"},
            {"type_id": "/videos/all/every", "type_name": "全站最热"},
            {"type_id": "/videos/category/rhgv", "type_name": "日韩专区"},
            {"type_id": "/videos/category/omjd", "type_name": "欧美专区"},
            {"type_id": "/videos/all/xiaolan", "type_name": "小蓝原创"},
            {"type_id": "/videos/all/20min", "type_name": "长片专区"},
            {"type_id": "/videos/all/10min", "type_name": "短片速看"},
            {"type_id": "/videos/category/xrbj", "type_name": "薄肌鲜肉"},
            {"type_id": "/videos/category/wtns", "type_name": "无套内射"},
            {"type_id": "/videos/category/kjys", "type_name": "口交颜射"},
            {"type_id": "/videos/category/jrmn", "type_name": "肌肉猛男"},
            {"type_id": "/videos/category/drqp", "type_name": "群交互动"},
            {"type_id": "/videos/category/tjsm", "type_name": "调教SM"},
            {"type_id": "/videos/category/zfyh", "type_name": "制服诱惑"},
        ]
        return self._class_cache

    def _parse_list(self, html):
        data, seen = [], set()
        for block in re.findall(r'(\{[^{}]*"@type"\s*:\s*"VideoObject"[\s\S]*?\})', html or "", re.S | re.I):
            name = self._clean(self._j(block, "name"))
            href = self._j(block, "url") or self._j(block, "embedUrl")
            pic = self._j(block, "thumbnailUrl")
            if href and "/videos/" in href and href not in seen:
                seen.add(href)
                data.append({"vod_id": self._fix_url(href), "vod_name": name, "vod_pic": urllib.parse.urljoin(self.BASE_URL, pic), "vod_remarks": self._dur(self._j(block, "duration"))})
        cards = re.findall(r'(<a[^>]+href=["\'][^"\']*/videos/vd-[^"\']+["\'][\s\S]{0,2500}?</a>)', html or "", re.S | re.I)
        if not cards:
            cards = re.findall(r'(<div[^>]+class=["\'][^"\']*(?:video|item|card|list)[^"\']*["\'][\s\S]{0,3500}?/videos/vd-[\s\S]{0,1200}?</div>)', html or "", re.S | re.I)
        for item in cards:
            href = self._match(item, r'href=["\']([^"\']*/videos/vd-[^"\']+)["\']')
            name = self._clean(self._match(item, r'title=["\']([^"\']+)') or self._match(item, r'alt=["\']([^"\']+)') or self._match(item, r'<h[1-6][^>]*>(.*?)</h[1-6]>') or self._match(item, r'<a[^>]*>(.*?)</a>'))
            pic = self._match(item, r'(?:data-original|data-src|data-lazyload|data-lazy-src)=["\']([^"\']+)') or self._match(item, r'<img[^>]+src=["\']([^"\']+)')
            remarks = self._clean(self._match(item, r'(\d{1,2}:\d{2}(?::\d{2})?)') or self._match(item, r'<span[^>]*>(.*?)</span>'))
            full = self._fix_url(urllib.parse.urljoin(self.BASE_URL, href))
            if full not in seen and name and "/static/web/images/poster_loading" not in pic:
                seen.add(full)
                data.append({"vod_id": full, "vod_name": name, "vod_pic": urllib.parse.urljoin(self.BASE_URL, pic), "vod_remarks": remarks})
        return data

    def _play_url(self, page, html):
        play = self._match(html, r'data-url=["\']([^"\']+\.m3u8[^"\']*)')
        if play:
            return play.replace("&amp;", "&")
        js = self._unpack_first(html)
        src = self._match(js, r'<script\s+src=\\?["\']([^"\']*detail_play\.js[^"\']+)') or self._match(js, r'src=\\?["\']([^"\']*detail_play\.js[^"\']+)')
        if not src:
            src = self._match(html, r'src=["\']([^"\']*detail_play\.js[^"\']+)')
        if not src:
            return ""
        src = src.replace('\\/', '/').replace('\\"', '"').replace("\\'", "'")
        src = re.sub(r'"\s*\+\s*encodeURIComponent\(["\']([^"\']+)["\']\)\s*\+\s*"', urllib.parse.quote(self._last_group(src)), src) if "encodeURIComponent" in src else src
        t = str(int(__import__("time").time() / 1000 / 1800)) if False else ""
        src = re.sub(r'"\s*\+\s*parseInt\(\(new Date\(\)\)\.getTime\(\)/1000/1800\)\s*\+\s*"', str(int(self._now() / 1800)), src)
        src = urllib.parse.urljoin(page, src.replace("&amp;", "&"))
        html2 = self._get(src, {"Referer": page})
        js2 = self._unpack_first(html2)
        return (self._match(js2, r'data-url=\\?["\']([^"\']+\.m3u8[^"\']*)') or self._match(html2, r'data-url=\\?["\']([^"\']+\.m3u8[^"\']*)') or self._match(js2, r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']')).replace("&amp;", "&").replace("\\/", "/")

    def _unpack_first(self, text):
        m = re.search(r'eval\(function\(p,a,c,k,e,d\)[\s\S]*?\)\)', text or "", re.I)
        if not m:
            return text or ""
        code = m.group(0)
        p = self._match(code, r"\}\('([\s\S]*)',\s*(\d+),\s*(\d+),\s*'([^']*)'\.split\('\|'\)")
        m2 = re.search(r"\}\('([\s\S]*)',\s*(\d+),\s*(\d+),\s*'([^']*)'\.split\('\|'\)", code, re.S)
        if not m2:
            return text or ""
        payload, base, count, words = m2.group(1), int(m2.group(2)), int(m2.group(3)), m2.group(4).split("|")
        for i in range(count - 1, -1, -1):
            if i < len(words) and words[i]:
                payload = re.sub(r'\b' + self._base(i, base) + r'\b', words[i], payload)
        return payload.replace("\\'", "'").replace('\\"', '"').replace("\\/", "/")

    def _base(self, n, b):
        chars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
        return chars[n] if n < b and n < len(chars) else self._base(n // b, b) + chars[n % b]

    def _get(self, url, headers=None):
        for real in self._candidate_urls(self._fix_url(url)):
            h = dict(self.HEADERS)
            h["Referer"] = self.BASE_URL + "/"
            if headers:
                h.update(headers)
            try:
                r = self.session.get(real, headers=h, timeout=15, verify=False)
                r.encoding = "utf-8"
                if r.status_code < 400 and "Just a moment" not in r.text and "cf-browser-verification" not in r.text:
                    return r.text
            except Exception:
                continue
        return ""

    def _candidate_urls(self, url):
        urls = [url]
        for host in self.FALLBACK_URLS:
            p = urllib.parse.urlparse(url)
            if p.netloc and host not in url:
                urls.append(host + p.path + ("?" + p.query if p.query else ""))
        return list(dict.fromkeys(urls))

    def _fix_url(self, url):
        return str(url or "").replace("http://91nt.com", self.BASE_URL).replace("https://www.91nt.com", self.BASE_URL)

    def _match(self, text, pattern):
        m = re.search(pattern, text or "", re.S | re.I)
        return m.group(1).strip() if m else ""

    def _j(self, text, key):
        return self._match(text, r'"' + re.escape(key) + r'"\s*:\s*"([^"]*)').replace("\\/", "/")

    def _clean(self, text):
        text = re.sub(r'<.*?>', '', text or '')
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&#038;', '&').replace('&quot;', '"').replace('&#34;', '"')
        return re.sub(r'\s+', ' ', text).strip()

    def _dur(self, value):
        value = str(value or "").strip()
        if value.isdigit():
            s = int(value)
            return "%02d:%02d" % (s // 60, s % 60)
        return value.replace("PT", "").replace("H", ":").replace("M", ":").replace("S", "")

    def _to_int(self, value, default=0):
        try:
            return int(value)
        except Exception:
            return default

    def _last_group(self, text):
        m = re.findall(r'encodeURIComponent\(["\']([^"\']+)["\']\)', text or "", re.S | re.I)
        return m[-1] if m else ""

    def _now(self):
        try:
            import time
            return int(time.time())
        except Exception:
            return 0
