# -*- coding: utf-8 -*-
# 官网:https://www.fulleroticmovies.net/
import base64
import hashlib
import html
import json
import re
import sys
from urllib.parse import urljoin

sys.path.append('..')
try:
    from base.spider import Spider as _BaseSpider
except ImportError:
    class _BaseSpider:
        pass

try:
    import requests
except ImportError:
    requests = None
try:
    from Crypto.Cipher import AES
except ImportError:
    AES = None

_H = bytes([104,116,116,112,115,58,47,47,119,119,119,46,102,117,108,108,101,114,111,116,105,99,109,111,118,105,101,115,46,110,101,116]).decode()
_OK_API = bytes([104,116,116,112,115,58,47,47,105,109,103,46,100,97,110,109,117,98,107,46,100,112,100,110,115,46,111,114,103,47,102,98,46,100,111]).decode()
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"

_ROOTS = (
    ("最新", "/videos/"),
    ("热门", "/trending/"),
    ("最多观看", "/most-viewed/"),
    ("评分最高", "/top-rated/"),
)
_FEATURED_CATEGORIES = (
    ("90年代", "/category/90s/"),
    ("80年代", "/category/80s/"),
    ("70年代", "/category/70s/"),
    ("经典", "/category/classic/"),
    ("剧情", "/category/plot-oriented/"),
    ("合集", "/category/compilation/"),
    ("大胸", "/category/big-tits/"),
    ("肛交", "/category/anal/"),
)
_FEATURED_STUDIOS = (
    ("Alpha Blue", "/studio/alpha-blue-archives/"),
    ("Vivid", "/studio/vivid/"),
    ("VCA", "/studio/vca/"),
    ("LBO", "/studio/lbo/"),
    ("VCX", "/studio/vcx/"),
)


class Spider(_BaseSpider):
    def init(self, extend=""):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": _UA, "Accept-Language": "en-US,en;q=0.9"})
        self.cache = {}
        self.cache_signing_args = None

    def getName(self):
        return "Full Erotic Movies"

    def isVideoFormat(self, url):
        return ".mp4" in url or ".m3u8" in url

    def manualVideoCheck(self):
        return False

    def _get(self, path):
        try:
            url = path if path.startswith("http") else urljoin(_H, path)
            response = self.session.get(url, timeout=30)
            response.encoding = "utf-8"
            return response.text if response.status_code == 200 else ""
        except Exception as exc:
            print("[FEM] get:", exc)
            return ""

    def _classes(self):
        classes = []
        classes.extend({"type_id": "root:%d" % i, "type_name": name} for i, (name, _) in enumerate(_ROOTS))
        classes.extend({"type_id": "cat:%d" % i, "type_name": name} for i, (name, _) in enumerate(_FEATURED_CATEGORIES))
        classes.extend({"type_id": "studio:%d" % i, "type_name": name} for i, (name, _) in enumerate(_FEATURED_STUDIOS))
        return classes

    def homeContent(self, filter=False):
        return {"class": self._classes()}

    def homeVideoContent(self):
        return self.categoryContent("root:0", 1)

    def _route(self, tid):
        try:
            kind, raw = str(tid).split(":", 1)
            index = int(raw)
            if kind == "root":
                return _ROOTS[index][1]
            if kind == "cat":
                return _FEATURED_CATEGORIES[index][1]
            if kind == "studio":
                return _FEATURED_STUDIOS[index][1]
        except Exception:
            pass
        return _ROOTS[0][1]

    def _page_url(self, base, page):
        base = base.rstrip("/") + "/"
        return base if page <= 1 else base + str(page) + "/"

    def _cards(self, source):
        cards = []
        pattern = r'<a\s+class="item-video[^>]+href="([^"]+)"[^>]*title="([^"]*)"[^>]*>(.*?)</a>'
        for match in re.finditer(pattern, source, re.S | re.I):
            href, title, inner = match.groups()
            image = re.search(r'data-original="([^"]+)"', inner, re.I)
            if not image:
                image = re.search(r'src="([^"]+\.(?:webp|jpe?g|png)(?:\?[^\"]*)?)"', inner, re.I)
            rating = re.search(r'class="[^" ]*rating[^" ]*"[^>]*>\s*([^<]+)', inner, re.I)
            url = urljoin(_H, html.unescape(href))
            cards.append({
                "vod_id": url,
                "vod_name": html.unescape(title).strip(),
                "vod_pic": urljoin(_H, html.unescape(image.group(1))) if image else "",
                "vod_remarks": rating.group(1).strip() if rating else "",
            })
        return cards

    def _page_count(self, source):
        pages = [int(x) for x in re.findall(r'href="[^"]+/(\d+)/"[^>]*>\s*\1\s*<', source)]
        return max(pages or [1])

    def categoryContent(self, tid, pg=1, filter=False, extend=None):
        page = max(1, int(pg))
        source = self._get(self._page_url(self._route(tid), page))
        cards = self._cards(source) if source else []
        for card in cards:
            self.cache[card["vod_id"]] = card
        return {"list": cards, "page": page, "pagecount": self._page_count(source), "limit": len(cards), "total": 0}

    def _source_args(self, source):
        match = re.search(r"generate_mp4\('([^']+)',\s*'([^']+)',\s*'([^']+)',\s*'([^']+)'\)", source)
        return match.groups() if match else None

    def _ok_urls(self, encrypted, password, ok_video_id):
        try:
            info = json.loads(base64.b64decode(encrypted))
            salt = bytes.fromhex(info["salt"])
            iv = bytes.fromhex(info["iv"])
            key = hashlib.pbkdf2_hmac("sha512", password.encode(), salt, int(info.get("iterations") or 999), 32)
            plain = AES.new(key, AES.MODE_CBC, iv).decrypt(base64.b64decode(info["ciphertext"]))
            session_key = plain[:-plain[-1]].decode("utf-8")
            fields = "video.url_tiny,video.url_low,video.url_high,video.url_medium,video.url_quadhd,video.url_mobile,video.url_ultrahd,video.url_fullhd"
            response = self.session.get(_OK_API, params={
                "application_key": "CBAFJIICABABABABA", "fields": fields,
                "method": "video.get", "session_key": session_key, "vids": ok_video_id,
            }, timeout=30)
            video = response.json().get("videos", [{}])[0]
            quality = ("url_ultrahd", "url_fullhd", "url_quadhd", "url_high", "url_medium", "url_low", "url_mobile", "url_tiny")
            return [(key[4:], video[key]) for key in quality if video.get(key)]
        except Exception as exc:
            print("[FEM] resolve:", exc)
            return []

    def detailContent(self, ids):
        detail_url = str(ids[0]) if ids else ""
        source = self._get(detail_url)
        args = self._source_args(source)
        if not source or not args:
            return {"list": []}
        encrypted, password, ok_video_id, _ = args
        self.cache_signing_args = (encrypted, password, ok_video_id)
        streams = self._ok_urls(encrypted, password, ok_video_id)
        cached = self.cache.get(detail_url, {})
        title = cached.get("vod_name") or html.unescape(re.search(r'<h1[^>]*>(.*?)</h1>', source, re.S).group(1)).strip()
        cover = cached.get("vod_pic")
        if not cover:
            image = re.search(r"preview_url:\s*'([^']+)'", source)
            cover = image.group(1) if image else ""
        description = re.search(r'<div[^>]*class="[^" ]*description[^" ]*"[^>]*>(.*?)</div>', source, re.S | re.I)
        plays = [label + "$" + url for label, url in streams]
        return {"list": [{
            "vod_id": detail_url, "vod_name": title, "vod_pic": cover,
            "vod_content": re.sub(r"<[^>]+>", "", description.group(1)).strip() if description else "",
            "vod_play_from": "官方线路" if plays else "",
            "vod_play_url": "#".join(plays),
        }]}

    def playerContent(self, flag, id, vipFlags=None):
        if id and id.startswith("http"):
            return {"url": id, "header": json.dumps({"User-Agent": _UA, "Referer": _H + "/"})}
        # quality label passed as flag; lookup the fresh CDN URL from the OK API
        if flag and self.cache_signing_args:
            try:
                enc, pwd, ok_vid = self.cache_signing_args
                urls = dict(self._ok_urls(enc, pwd, ok_vid))
                url = urls.get(flag)
                if url:
                    return {"url": url, "header": json.dumps({"User-Agent": _UA, "Referer": _H + "/"})}
            except Exception as exc:
                print("[FEM] player:", exc)
        return {"url": ""}

    def searchContent(self, key, quick=False, pg=1):
        return {"list": []}

    def localProxy(self, param):
        try:
            url = (param or {}).get("url", "")
            if not url.startswith("http"):
                return [404, "text/plain", b""]
            headers = {"User-Agent": _UA, "Referer": _H + "/"}
            if "vkuser.net" in url or "mycdn.me" in url:
                headers.pop("Referer", None)
            response = self.session.get(url, headers=headers, stream=True, timeout=30)
            if response.status_code != 200:
                return [response.status_code, "text/plain", b""]
            content_type = response.headers.get("Content-Type", "video/mp4")
            return [200, content_type, response.iter_content(chunk_size=1048576)]
        except Exception as exc:
            print("[FEM] proxy:", exc)
            return [500, "text/plain", b""]
