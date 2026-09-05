#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
66dpw.vip - 苹果CMS mxpro 模板 Spider
站点: https://www.66dpw.vip
"""
import sys, re, json, base64, html as html_mod
from urllib.parse import quote, unquote, urljoin

try:
    import requests
    import urllib3
    urllib3.disable_warnings()
except ImportError:
    requests = None

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def init(self, extend=""): self.extend = extend
        def homeContent(self, filter): return {"class": [], "filters": {}}
        def homeVideoContent(self): return {"list": []}
        def categoryContent(self, tid, pg, filter, extend):
            return {"list": [], "page": 1, "pagecount": 1, "limit": 24, "total": 0}
        def detailContent(self, ids): return {"list": []}
        def playerContent(self, flag, id, vipFlags=None):
            return {"parse": 0, "playUrl": "", "url": "", "header": {}}
        def searchContent(self, key, quick, pg="1"):
            return {"list": [], "page": 1, "pagecount": 1, "limit": 24, "total": 0}
        def isVideoFormat(self, url): return False
        def manualVideoCheck(self): return False
        def localProxy(self, param): return [404, "text/plain", b""]


def decrypt_enc2(encrypted_url):
    """66dpw播放加密：URL编码 → Base64 → URL编码"""
    if not encrypted_url or not isinstance(encrypted_url, str):
        return encrypted_url
    try:
        step1 = unquote(encrypted_url)
        step2 = base64.b64decode(step1).decode("utf-8", errors="replace")
        step3 = unquote(step2)
        if step3.startswith("http://") or step3.startswith("https://"):
            return step3
        return encrypted_url
    except Exception:
        return encrypted_url


def _page(pg):
    try:
        v = int(str(pg or "").strip())
        return v if v > 0 else 1
    except Exception:
        return 1


def fix_url(url, host):
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return urljoin(host, url)
    if url.startswith("http"):
        return url
    return urljoin(host, url)


class Spider(BaseSpider):
    def __init__(self):
        super().__init__()
        self.host = "https://www.66dpw.vip"
        self.name = "66dpw"
        self.sourceKey = "66dpw"
        self.s = requests.Session() if requests else None
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
        }
        if self.s:
            self.s.headers.update(self.headers)
            self.s.verify = False
        self.timeout = 15

    def setExtendInfo(self, extend):
        if isinstance(extend, dict):
            cfg = dict(extend)
        else:
            try:
                cfg = json.loads(str(extend or "{}"))
            except:
                cfg = {}
        if isinstance(cfg, dict):
            host = cfg.get("host") or cfg.get("HOST") or ""
            if host:
                self.host = host.rstrip("/")
            ua = cfg.get("userAgent") or cfg.get("User-Agent") or cfg.get("ua") or ""
            if ua:
                self.headers["User-Agent"] = ua
            cookie = cfg.get("cookie") or cfg.get("Cookie") or ""
            if cookie:
                self.headers["Cookie"] = cookie
            elif "Cookie" in self.headers:
                self.headers.pop("Cookie", None)
            referer = cfg.get("referer") or cfg.get("Referer") or ""
            self.headers["Referer"] = referer if referer.startswith(("http://", "https://")) else self.host + "/"
            self.timeout = max(3, int(cfg.get("timeout", self.timeout) or self.timeout))
            if self.s:
                self.s.headers.update(self.headers)

    def init(self, extend=""):
        if extend:
            self.setExtendInfo(extend)

    def getName(self):
        return self.name

    def getDependence(self):
        return []

    def homeLayout(self):
        return 0

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def destroy(self):
        try:
            if self.s:
                self.s.close()
        except Exception:
            pass

    def isVideoFormat(self, url):
        if not url:
            return False
        path = str(url).lower()
        return any(x in path for x in [".m3u8", ".mp4", ".m4v", ".flv", ".webm", ".ts"])

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return [404, "text/plain", b""]

    def _fetch(self, url, ref=None):
        """获取页面HTML，与最初版本一致"""
        if not self.s:
            return ""
        merged = dict(self.headers)
        if ref:
            merged["Referer"] = ref
        try:
            r = self.s.get(url, headers=merged, timeout=self.timeout)
            if r.status_code == 200:
                try:
                    r.encoding = r.apparent_encoding or "utf-8"
                except Exception:
                    r.encoding = "utf-8"
                return r.text
        except Exception:
            pass
        return ""

    def homeContent(self, filter):
        try:
            classes = [
                {"type_id": "1", "type_name": "电影"},
                {"type_id": "2", "type_name": "动漫"},
                {"type_id": "3", "type_name": "剧集"},
                {"type_id": "4", "type_name": "短剧"},
                {"type_id": "5", "type_name": "综艺"},
            ]
            return {"class": classes, "filters": {}}
        except Exception:
            return {"class": [], "filters": {}}

    def homeVideoContent(self):
        return self.categoryContent("1", "1", False, {})

    def categoryContent(self, tid, pg, filter, extend):
        page = _page(pg)
        result = {"list": [], "page": page, "pagecount": 1, "limit": 24, "total": 0}
        url = f"{self.host}/vodtype/{tid}.html" if page == 1 else f"{self.host}/vodtype/{tid}-{page}.html"
        html = self._fetch(url)
        if not html:
            return result

        items = re.findall(
            r'<a[^>]*href="/voddetail/(\d+)\.html"[^>]*title="([^"]*)"[^>]*>.*?'
            r'<img[^>]*data-original="([^"]*)"',
            html, re.S
        )

        seen = set()
        for vid, title, pic in items:
            if vid in seen:
                continue
            seen.add(vid)
            remark = ""
            rm = re.search(
                r'<a[^>]*href="/voddetail/' + re.escape(vid) + r'\.html"[^>]*>.*?'
                r'<div class="module-item-note">([^<]+)</div>',
                html, re.S
            )
            if rm:
                remark = rm.group(1).strip()
            result["list"].append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": fix_url(pic, self.host),
                "vod_remarks": remark,
            })

        all_pages = re.findall(r'href="/vodtype/' + re.escape(str(tid)) + r'-(\d+)\.html"', html)
        if all_pages:
            result["pagecount"] = max(int(p) for p in all_pages)
        else:
            all_pages = re.findall(r'[?&]page=(\d+)', html)
            if all_pages:
                result["pagecount"] = max(int(p) for p in all_pages)
        return result

    def detailContent(self, ids):
        raw_ids = ids if isinstance(ids, (list, tuple)) else [ids]
        vid = str(raw_ids[0] if raw_ids else "").strip()
        if not vid:
            return {"list": []}
        result = {"list": []}
        html = self._fetch(f"{self.host}/voddetail/{vid}.html")
        if not html:
            return result

        title = ""
        tm = re.search(r"<h1[^>]*>([^<]+)</h1>", html)
        if tm:
            title = html_mod.unescape(tm.group(1).strip())

        pic = ""
        pm = re.search(r'<img[^>]*class="[^\"]*lazyload[^\"]*"[^>]*data-original="([^\"]*)"', html)
        if not pm:
            pm = re.search(r'class="[^\"]*video-cover[^\"]*"[^>]*data-original="([^\"]*)"', html)
        if pm:
            pic = fix_url(pm.group(1), self.host)

        source_names = re.findall(r'data-dropdown-value="([^"]*)"', html)
        if not source_names:
            source_names = re.findall(r'<span[^>]*class="[^\"]*module-tab-name[^\"]*"[^>]*>([^<]+)</span>', html)

        play_blocks = re.findall(
            r'<div class="module-play-list">(.*?)</div>\s*</div>',
            html, re.S
        )

        play_from_list = []
        play_url_list = []

        if play_blocks:
            for idx, block in enumerate(play_blocks):
                source_name = source_names[idx].strip() if idx < len(source_names) else f"线路{idx+1}"
                play_from_list.append(source_name)
                hrefs = re.findall(
                    r'href="/vodplay/' + re.escape(vid) + r'-(\d+)-(\d+)\.html"', block
                )
                spans = re.findall(r'<span>([^<]+)</span>', block)
                ep_parts = []
                for i, (sid, nid) in enumerate(hrefs):
                    ep_name = spans[i].strip() if i < len(spans) else f"第{i+1}集"
                    ep_parts.append(f"{ep_name}${vid}-{sid}-{nid}")
                if ep_parts:
                    play_url_list.append("#".join(ep_parts))
        else:
            hrefs = re.findall(
                r'href="/vodplay/' + re.escape(vid) + r'-(\d+)-(\d+)\.html"', html
            )
            if hrefs:
                play_from_list.append(source_names[0].strip() if source_names else "默认")
                list_span = re.findall(
                    r'class="module-play-list-link"[^>]*>.*?<span>([^<]+)</span>', html, re.S
                )
                ep_parts = []
                for i, (sid, nid) in enumerate(hrefs):
                    ep_name = list_span[i].strip() if i < len(list_span) else f"第{i+1}集"
                    ep_parts.append(f"{ep_name}${vid}-{sid}-{nid}")
                play_url_list.append("#".join(ep_parts))
            else:
                play_from_list.append("默认")
                play_url_list.append(f"正片${vid}")

        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_play_from": "$$$".join(play_from_list),
            "vod_play_url": "$$$".join(play_url_list),
        }
        result["list"].append(vod)
        return result

    def playerContent(self, flag, id, vipFlags=None):
        result = {"parse": 0, "playUrl": "", "url": "", "header": {}}
        pid = str(id or "").strip()
        if not pid:
            return result

        # 媒体直链直接返回
        if self.isVideoFormat(pid):
            result["url"] = pid
            result["header"] = {
                "User-Agent": self.headers.get("User-Agent", ""),
                "Referer": self.host + "/"
            }
            return result

        # 让 TVBox 自己从播放页提取视频地址（parse=1），不走Python中转解密
        # 苹果CMS标准格式，TVBox/CatVod内置支持解析 player_aaaa 中的加密地址
        result["parse"] = 1
        result["url"] = f"{self.host}/vodplay/{pid}.html"
        return result

    def searchContent(self, key, quick, pg="1"):
        page = _page(pg)
        result = {"list": [], "page": page, "pagecount": 1, "limit": 24, "total": 0}

        # XML API
        api_html = self._fetch(f"{self.host}/api.php/provide/vod/at/xml/?wd={quote(key)}")
        if api_html and ("<?xml" in api_html or "<list>" in api_html):
            items = re.findall(
                r'<vod[^>]*>.*?<id>(\d+)</id>.*?<name>([^<]+)</name>.*?<pic>([^<]+)</pic>.*?</vod>',
                api_html, re.S
            )
            if items:
                for vid, name, pic in items:
                    result["list"].append({
                        "vod_id": vid.strip(),
                        "vod_name": html_mod.unescape(name.strip()),
                        "vod_pic": pic.strip(),
                    })
                return result

        # JSON API
        for api_url in [
            f"{self.host}/api.php/provide/vod/at/json/?wd={quote(key)}",
            f"{self.host}/api.php/provide/vod/?wd={quote(key)}",
        ]:
            api_json = self._fetch(api_url)
            if api_json:
                try:
                    data = json.loads(api_json)
                    items = data if isinstance(data, list) else data.get("list", [])
                    if items:
                        for v in items:
                            _id = v.get("vod_id") or v.get("id") or ""
                            _name = v.get("vod_name") or v.get("name") or ""
                            _pic = v.get("vod_pic") or v.get("pic") or ""
                            if _id and _name:
                                result["list"].append({
                                    "vod_id": str(_id),
                                    "vod_name": _name,
                                    "vod_pic": _pic,
                                })
                        return result
                except Exception:
                    continue

        # HTML搜索
        html = self._fetch(f"{self.host}/vodsearch/-------------.html?wd={quote(key)}")
        if not html or "验证码" in html or "verify" in html.lower():
            return result

        items = re.findall(
            r'<a[^>]*href="/voddetail/(\d+)\.html"[^>]*title="([^"]*)"[^>]*>.*?'
            r'<img[^>]*data-original="([^"]*)"',
            html, re.S
        )
        seen = set()
        for vid, title, pic in items:
            if vid in seen:
                continue
            seen.add(vid)
            result["list"].append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": fix_url(pic, self.host),
            })
        return result