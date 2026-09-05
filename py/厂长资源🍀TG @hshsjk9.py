# -*- coding: utf-8 -*-

import re
import json
import html as _html
import urllib.request
import urllib.parse
import ssl

try:
    import requests as _requests
except Exception:
    _requests = None


class Spider:

    def __init__(self):
        self.site = "https://czzytv77.com"
        self.name = "厂长资源"
        self.header = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Referer": self.site,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        self.s = self.session = self.sess = (_requests.Session() if _requests else None)
        self._extend = {}
        self._home_html = None

    def getDependence(self):
        return []

    def manualVideoCheck(self):
        return False

    def isVideoFormat(self, url):
        if not url:
            return False
        u = str(url).lower()
        return any(u.endswith(ext) for ext in (".m3u8", ".mp4", ".flv", ".mkv", ".ts", ".avi")) or "m3u8" in u

    def destroy(self):
        pass

    def action(self, action):
        return {}

    def init(self, extend=""):
        self._extend = {}
        if isinstance(extend, dict):
            self._extend = extend
        elif isinstance(extend, str) and extend.strip():
            try:
                e = json.loads(extend)
                if isinstance(e, dict):
                    self._extend = e
            except Exception:
                pass

        if self._extend.get("host"):
            self.site = self._extend["host"].rstrip("/")
            self.header["Referer"] = self.site
        if self._extend.get("ua"):
            self.header["User-Agent"] = self._extend["ua"]
        if self._extend.get("cookie"):
            self.header["Cookie"] = self._extend["cookie"]
        if self._extend.get("referer"):
            self.header["Referer"] = self._extend["referer"]

    def homeContent(self, filter=None):
        html = self._get_home()
        if not html:
            return {"class": [], "list": []}
        cats = self._extract_cats(html)
        vods = self._extract_list(html)
        return {"class": cats, "list": vods}

    def homeVideoContent(self):
        html = self._get_home()
        return {"list": self._extract_list(html) if html else []}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        pg = self._safe_page(pg)
        url = self._cat_url(tid, pg)
        html = self._get(url)
        if not html:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 36, "total": 0}
        vods = self._extract_list(html)
        pagecount = self._extract_pagecount(html) or 999
        return {
            "list": vods,
            "page": pg,
            "pagecount": pagecount,
            "limit": 36,
            "total": pagecount * 36,
        }

    def detailContent(self, ids):
        vid = self._norm_id(ids)
        if not vid:
            return {"list": []}

        if vid.startswith(("http", "/")):
            url = self._u(vid)
        else:
            url = f"{self.site}/cdvoddetail/{vid}.html"

        html = self._get(url)
        if not html:
            return {"list": []}

        title = self._extract_title(html)
        pic = self._extract_detail_pic(html)
        desc = self._extract_desc(html)
        year = self._extract_detail_meta(html, "年份")
        area = self._extract_detail_meta(html, "地区")
        type_name = self._extract_detail_meta(html, "类型")
        director = self._extract_detail_meta(html, "导演")
        actor = self._extract_detail_meta(html, "主演")

        play_from, play_url = self._extract_play(html)

        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_content": desc,
            "vod_year": year,
            "vod_area": area,
            "vod_director": director,
            "vod_actor": actor,
            "type_name": type_name,
            "vod_play_from": play_from,
            "vod_play_url": play_url,
        }
        return {"list": [vod]}

    def searchContent(self, key, quick=False, pg="1"):
        q = urllib.parse.quote(str(key))
        url = f"{self.site}/cdvodsearch/-------------.html?wd={q}"
        html = self._get(url)
        if not html:
            return {"list": []}
        vods = self._extract_list(html)
        return {"list": vods, "page": 1, "pagecount": 1, "limit": 36, "total": len(vods)}

    def playerContent(self, flag, ids, vipFlags=None):
        url = self._norm_id(ids)
        if not url:
            return {"parse": 0, "url": "", "header": dict(self.header)}

        if not url.startswith("http"):
            url = self._u(url)

        if self.isVideoFormat(url):
            return {"parse": 0, "url": url, "header": dict(self.header)}

        html = self._get(url, referer=self.site)
        if not html:
            return {"parse": 0, "url": "", "header": dict(self.header)}

        # 1. iframe 提取
        m = re.search(r'<iframe[^>]+src="([^"]+)"', html)
        if m:
            iframe_src = m.group(1)
            if iframe_src.startswith("//"):
                iframe_src = "https:" + iframe_src
            elif not iframe_src.startswith("http"):
                iframe_src = self._u(iframe_src)
            m2 = re.search(r'[?&]url=([^&]+)', iframe_src)
            if m2:
                m3u8 = urllib.parse.unquote(m2.group(1))
                if self.isVideoFormat(m3u8):
                    h = dict(self.header)
                    h["Referer"] = iframe_src
                    return {"parse": 0, "url": m3u8, "header": h}
            return {"parse": 1, "url": iframe_src, "header": dict(self.header)}

        # 2. script 变量
        for pat in (
            r'var\s+url\s*=\s*["\']([^"\']+)',
            r'var\s+urls\s*=\s*["\']([^"\']+)',
            r'var\s+player\s*=\s*["\']([^"\']+)',
            r'var\s+video\s*=\s*["\']([^"\']+)',
            r'"url"\s*:\s*"([^"]+)"',
            r'"video"\s*:\s*"([^"]+)"',
        ):
            mm = re.search(pat, html, re.I)
            if mm:
                found = mm.group(1)
                if self.isVideoFormat(found):
                    if found.startswith("//"):
                        found = "https:" + found
                    elif not found.startswith("http"):
                        found = self._u(found)
                    return {"parse": 0, "url": found, "header": dict(self.header)}

        # 3. video/source
        for pat in (
            r'<video[^>]+src=["\']([^"\']+)',
            r'<source[^>]+src=["\']([^"\']+)',
        ):
            mm = re.search(pat, html, re.I)
            if mm:
                found = mm.group(1)
                if found.startswith("//"):
                    found = "https:" + found
                return {"parse": 0, "url": self._u(found), "header": dict(self.header)}

        # 4. 全局 m3u8/mp4
        mm = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html, re.I)
        if mm:
            return {"parse": 0, "url": mm.group(1), "header": dict(self.header)}

        mm = re.search(r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*)', html, re.I)
        if mm:
            return {"parse": 0, "url": mm.group(1), "header": dict(self.header)}

        return {"parse": 1, "url": url, "header": dict(self.header)}

    def localProxy(self, param):
        u = param.get("url", "") if isinstance(param, dict) else ""
        if not u:
            return [403, "text/plain", b"", None]
        h = dict(self.header)
        if self.s is not None:
            try:
                r = self.s.get(u, headers=h, timeout=15, verify=False)
                return [200, r.headers.get("Content-Type", "application/octet-stream"), r.content, None]
            except Exception:
                pass
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(u, headers=h)
            with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                return [200, resp.headers.get("Content-Type", "application/octet-stream"), resp.read(), None]
        except Exception:
            return [403, "text/plain", b"", None]

    def _get_home(self):
        if self._home_html is None:
            self._home_html = self._get(self.site + "/")
        return self._home_html

    def _get(self, url, referer=None, timeout=15):
        h = dict(self.header)
        if referer:
            h["Referer"] = referer
        if self.s is not None:
            try:
                r = self.s.get(url, headers=h, timeout=timeout, verify=False, allow_redirects=True)
                if r.status_code < 400:
                    return r.content.decode("utf-8", "ignore")
            except Exception:
                pass
        return self._get_raw(url, headers=h, timeout=timeout)

    def _get_raw(self, url, headers=None, timeout=15):
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            h = dict(headers) if headers else {}
            if "User-Agent" not in h:
                h["User-Agent"] = self.header["User-Agent"]
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                return resp.read().decode("utf-8", "ignore")
        except Exception:
            return ""

    def _u(self, u):
        if not u:
            return u
        u = u.strip()
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("http"):
            return u
        if u.startswith("/"):
            m = re.match(r"(https?://[^/]+)", self.site)
            return (m.group(1) if m else self.site) + u
        return self.site.rstrip("/") + "/" + u.lstrip("/")

    def _safe_page(self, pg):
        try:
            p = int(pg)
            return p if p > 0 else 1
        except Exception:
            return 1

    def _norm_id(self, ids):
        if isinstance(ids, (list, tuple)):
            return str(ids[0]) if ids else ""
        return str(ids).strip()

    def _cat_url(self, tid, pg):
        t = str(tid).strip().rstrip("/")
        if t.startswith("http"):
            return t
        base = self.site.rstrip("/")
        if t.endswith(".html"):
            t = t[:-5]
        if not t.startswith("/"):
            t = "/" + t
        if pg == 1:
            return f"{base}{t}.html"
        return f"{base}{t}-{pg}.html"

    def _extract_list(self, html):
        out = []
        seen = set()
        pat = r'<a[^>]*class="[^"]*stui-vodlist__thumb[^"]*"[^>]*href="([^"]+)"[^>]*title="([^"]+)"[^>]*data-original="([^"]+)"[^>]*>([\s\S]*?)</a>'
        for m in re.finditer(pat, html):
            href, title, img, inner = m.group(1), m.group(2), m.group(3), m.group(4)
            vid = self._u(href)
            if vid in seen:
                continue
            seen.add(vid)
            rm = re.search(r'<span[^>]*class="[^"]*pic-text[^"]*"[^>]*>([^<]+)</span>', inner)
            remark = rm.group(1).strip() if rm else ""
            out.append({
                "vod_id": vid,
                "vod_name": _html.unescape(title).strip(),
                "vod_pic": self._u(img),
                "vod_remarks": remark,
            })
        return out

    def _extract_cats(self, html):
        out = []
        seen = set()
        nav_m = re.search(r'<ul[^>]*class="stui-header__menu[^"]*"[^>]*>([\s\S]*?)</ul>', html)
        if nav_m:
            for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>', nav_m.group(1)):
                href, name = m.group(1).strip(), m.group(2).strip()
                if not name or name in ("首页",):
                    continue
                tid = href.lstrip("/").replace(".html", "")
                if tid in seen:
                    continue
                seen.add(tid)
                out.append({"type_id": tid, "type_name": name})
        if out:
            return out
        fallback = [
            ("cdvodtype/1", "电影"),
            ("cdvodtype/2", "电视剧"),
            ("cdvodtype/3", "综艺"),
            ("cdvodtype/4", "动漫大全"),
            ("cdvodtype/40", "豆瓣电影Top250"),
        ]
        for tid, name in fallback:
            out.append({"type_id": tid, "type_name": name})
        return out

    def _extract_title(self, html):
        m = re.search(r'<h1[^>]*class="title"[^>]*>([^<]+)</h1>', html)
        if m:
            return _html.unescape(m.group(1)).strip()
        m = re.search(r'<h1[^>]*>([\s\S]*?)</h1>', html, re.S)
        if m:
            t = _html.unescape(re.sub(r'<[^>]+>', '', m.group(1))).strip()
            if t:
                return t
        m = re.search(r'<title[^>]*>([^<]{2,60})</title>', html)
        return _html.unescape(m.group(1)).strip() if m else ""

    def _extract_detail_pic(self, html):
        for pat in (
            r'<img[^>]+class="[^"]*pic[^"]*"[^>]+data-original="([^"]+)"',
            r'<img[^>]+data-original="([^"]+)"[^>]+class="[^"]*pic[^"]*"',
            r'property="og:image" content="([^"]+)"',
        ):
            m = re.search(pat, html, re.I)
            if m:
                return self._u(m.group(1))
        return ""

    def _extract_desc(self, html):
        m = re.search(r'<p[^>]*class="desc[^"]*"[^>]*>([\s\S]*?)</p>', html)
        if m:
            return _html.unescape(re.sub(r'<[^>]+>', '', m.group(1))).strip()
        m = re.search(r'class="stui-content__desc[^"]*"[^>]*>([\s\S]*?)</div>', html)
        if m:
            return _html.unescape(re.sub(r'<[^>]+>', '', m.group(1))).strip()
        m = re.search(r'property="og:description" content="([^"]+)"', html)
        return _html.unescape(m.group(1)).strip() if m else ""

    def _extract_meta(self, html, pattern):
        m = re.search(pattern, html)
        return _html.unescape(m.group(1)).strip() if m else ""

    def _extract_detail_meta(self, html, field_name):
        patterns = [
            r'<span[^>]*>(?:\s*' + re.escape(field_name) + r'\s*[：:]\s*)</span>\s*<a[^>]*>([^<]+)</a>',
            r'<span[^>]*>(?:\s*' + re.escape(field_name) + r'\s*[：:]\s*)</span>\s*([^<\n]+)',
            r'(?:^|>|\s)' + re.escape(field_name) + r'\s*[：:]\s*<a[^>]*>([^<]+)</a>',
            r'(?:^|>|\s)' + re.escape(field_name) + r'\s*[：:]\s*([^<\n]+)',
            r'(?:^|>|\s)' + re.escape(field_name) + r'\s*[：:]\s*([\s\S]*?)(?:<br|<p|</p|<div|</div|$)',
        ]

        for pat in patterns:
            m = re.search(pat, html, re.I)
            if m:
                val = m.group(1).strip()
                val = re.sub(r'<[^>]+>', '', val).strip()
                val = _html.unescape(val)
                val = re.sub(r'\s+', ' ', val).strip()
                if val:
                    return val

        data_blocks = re.findall(r'<p[^>]*class="[^"]*data[^"]*"[^>]*>([\s\S]*?)</p>', html, re.I)
        for block in data_blocks:
            field_pat = r'(?:^|>|\s)' + re.escape(field_name) + r'\s*[：:]\s*([\s\S]*?)(?=<span|<a|</p|$)'
            m = re.search(field_pat, block, re.I)
            if m:
                val = m.group(1).strip()
                val = re.sub(r'<[^>]+>', '', val).strip()
                val = _html.unescape(val)
                val = re.sub(r'\s+', ' ', val).strip()
                if val:
                    return val
            span_pat = r'<span[^>]*>(?:\s*' + re.escape(field_name) + r'\s*[：:]\s*)</span>\s*<a[^>]*>([^<]+)</a>'
            m = re.search(span_pat, block, re.I)
            if m:
                val = _html.unescape(m.group(1)).strip()
                if val:
                    return val

        detail_m = re.search(r'<div[^>]*class="[^"]*stui-content__detail[^"]*"[^>]*>([\s\S]*?)</div>\s*(?:<div|<p|<h)', html, re.I)
        if detail_m:
            detail_html = detail_m.group(1)
            for pat in patterns:
                m = re.search(pat, detail_html, re.I)
                if m:
                    val = m.group(1).strip()
                    val = re.sub(r'<[^>]+>', '', val).strip()
                    val = _html.unescape(val)
                    val = re.sub(r'\s+', ' ', val).strip()
                    if val:
                        return val

        return ""

    def _extract_play(self, html):
        lines = []
        line_urls = []

        for ul_m in re.finditer(r'<ul[^>]*class="stui-content__playlist[^"]*"[^>]*>([\s\S]*?)</ul>', html):
            ul_block = ul_m.group(1)
            pre = html[:ul_m.start()]
            h3_matches = list(re.finditer(r'<h3[^>]*class="title"[^>]*>([\s\S]*?)</h3>', pre))
            line_name = "厂长资源"
            if h3_matches:
                line_name = _html.unescape(re.sub(r'<[^>]+>', '', h3_matches[-1].group(1))).strip() or "厂长资源"

            eps = []
            seen = set()
            for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>', ul_block):
                href, name = m.group(1).strip(), m.group(2).strip()
                if not href or href in seen or "javascript" in href:
                    continue
                seen.add(href)
                name = name or "播放"
                eps.append(f"{name}${self._u(href)}")

            if eps:
                lines.append(line_name)
                line_urls.append("#".join(eps))

        if lines:
            return "$$$".join(lines), "$$$".join(line_urls)
        return "", ""

    def _extract_pagecount(self, html):
        pages = re.findall(r'href="[^"]*-(\d+)\.html"', html)
        if pages:
            try:
                return max(int(p) for p in pages)
            except ValueError:
                pass
        m = re.search(r'共\s*(\d+)\s*页', html)
        if m:
            return int(m.group(1))
        return 1


def _html_unescape(s):
    return _html.unescape(s) if s else s