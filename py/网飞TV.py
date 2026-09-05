# -*- coding: utf-8 -*-
"""Wangfei TVBox source with dynamic playback-line discovery."""

import ast
import base64
import html as html_module
import json
import re
import time
from urllib.parse import parse_qs, quote, unquote, urljoin, urlparse

import requests

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    cffi_requests = None

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        """Small fallback used by offline tests outside TVBox."""

        def __init__(self):
            pass

        def getProxyUrl(self):
            return ""


class Spider(BaseSpider):
    DEFAULT_HOST = "https://www.wangfei.tv"
    DEFAULT_UA = (
        "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"
    )
    CLASSES = [
        {"type_name": "\u7535\u5f71", "type_id": "1"},
        {"type_name": "\u7535\u89c6\u5267", "type_id": "2"},
        {"type_name": "\u7efc\u827a", "type_id": "3"},
        {"type_name": "\u52a8\u6f2b", "type_id": "4"},
        {"type_name": "\u7eaa\u5f55\u7247", "type_id": "5"},
        {"type_name": "\u77ed\u5267", "type_id": "47"},
    ]
    MEDIA_EXTENSIONS = (
        ".m3u8", ".mp4", ".mkv", ".flv", ".ts", ".webm", ".avi", ".mov"
    )
    PLAY_PATH_RE = re.compile(
        r"/(?:vodplay|play)/[^\"'?#<>\s]+|/vod-play-[^\"'?#<>\s]+",
        re.I,
    )
    DETAIL_PATH_RE = re.compile(r"/voddetail/[^\"'?#<>\s]+\.html", re.I)
    CF_SIGNS = (
        "just a moment", "checking your browser",
        "attention required! | cloudflare",
    )
    CF_SOFT_SIGNS = ("challenge-platform", "cf-chl-", "cf_chl_")
    CONTENT_SIGNS = (
        "/voddetail/", "/vodplay/", "player_aaaa", ".m3u8",
        "module-poster", "module-info", "module-play-list",
        "anthology-list", "playlist",
    )
    AD_KEYWORDS = (
        "/ad/", "/ads/", "advert", "commercial", "promotion", "_ad_",
        "/gg/", "/gg", "-ad-", "adsegment", "adservice",
    )

    def __init__(self):
        try:
            super().__init__()
        except Exception:
            pass
        self.host = self.DEFAULT_HOST
        self.ua = self.DEFAULT_UA
        self.cookie = ""
        self.timeout = 15
        self.use_cffi = False
        self.proxy_enabled = False
        self.session = requests.Session()
        self.headers = {}
        self._refresh_headers()

    def init(self, extend=""):
        config = self._parse_extend(extend)
        self.host = str(config.get("host") or self.DEFAULT_HOST).strip().rstrip("/")
        self.ua = str(config.get("ua") or self.DEFAULT_UA).strip()
        self.cookie = str(config.get("cookie") or "").strip()
        self.timeout = self._safe_int(config.get("timeout"), 15, 5, 60)
        self.use_cffi = self._as_bool(config.get("use_cffi"), False)
        self.proxy_enabled = self._as_bool(config.get("proxy"), False)
        self.session = requests.Session()
        self._refresh_headers()
        return True

    def getName(self):
        return "\u7f51\u98deTV"

    def destroy(self):
        try:
            self.session.close()
        except Exception:
            pass

    @staticmethod
    def _safe_int(value, default, minimum=None, maximum=None):
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = default
        if minimum is not None:
            number = max(minimum, number)
        if maximum is not None:
            number = min(maximum, number)
        return number

    @staticmethod
    def _as_bool(value, default=False):
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {
            "1", "true", "yes", "on", "y", "\u5f00\u542f", "\u662f"
        }

    def _parse_extend(self, extend):
        if isinstance(extend, dict):
            return dict(extend)
        if not extend:
            return {}
        text = str(extend).strip()
        try:
            value = json.loads(text)
            return value if isinstance(value, dict) else {}
        except Exception:
            pass
        try:
            parsed = parse_qs(text, keep_blank_values=True)
            return {key: values[-1] for key, values in parsed.items()}
        except Exception:
            return {}

    def _refresh_headers(self):
        self.headers = {
            "User-Agent": self.ua,
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
        if self.cookie:
            self.headers["Cookie"] = self.cookie
        self.session.headers.clear()
        self.session.headers.update(self.headers)

    def _request_headers(self, referer="", accept=""):
        headers = dict(self.headers)
        if referer:
            headers["Referer"] = referer
        if accept:
            headers["Accept"] = accept
        return headers

    @classmethod
    def _is_cloudflare_text(cls, text):
        lower = (text or "")[:100000].lower()
        if any(sign in lower for sign in cls.CF_SIGNS):
            return True
        if not any(sign in lower for sign in cls.CF_SOFT_SIGNS):
            return False
        return not any(sign in lower for sign in cls.CONTENT_SIGNS)

    def _blocked_response(self, response, text=""):
        if response is None:
            return True
        if getattr(response, "status_code", 0) in (401, 403, 429, 503):
            return True
        return self._is_cloudflare_text(text)

    def _request_raw(self, url, referer="", binary=False):
        if not url:
            return None
        target = self._absolute(url, referer or self.host)
        headers = self._request_headers(
            referer,
            "*/*" if binary else "text/html,application/xhtml+xml,*/*;q=0.8",
        )
        response = None
        text = ""
        for attempt in range(2):
            try:
                response = self.session.get(
                    target, headers=headers, timeout=self.timeout, allow_redirects=True
                )
                if not binary:
                    response.encoding = response.apparent_encoding or "utf-8"
                    text = response.text
                if not self._blocked_response(response, text):
                    return response
                break
            except Exception:
                response = None
                if attempt == 0:
                    time.sleep(0.25)

        if self.use_cffi and cffi_requests is not None:
            try:
                response = cffi_requests.get(
                    target,
                    headers=headers,
                    timeout=self.timeout,
                    allow_redirects=True,
                    impersonate="chrome131",
                )
                if not binary:
                    response.encoding = getattr(response, "apparent_encoding", None) or "utf-8"
                    text = response.text
                if not self._blocked_response(response, text):
                    return response
            except Exception:
                return None
        return None

    def _get_text(self, url, referer=""):
        response = self._request_raw(url, referer=referer, binary=False)
        if response is None:
            return ""
        try:
            text = response.text or ""
            return "" if self._is_cloudflare_text(text) else text
        except Exception:
            return ""

    @staticmethod
    def _absolute(url, base):
        if not url:
            return ""
        value = html_module.unescape(str(url).strip()).replace("\\/", "/")
        if value.startswith("//"):
            return (urlparse(base).scheme or "https") + ":" + value
        return urljoin(base, value)

    @staticmethod
    def _clean_text(value):
        if value is None:
            return ""
        text = html_module.unescape(str(value)).replace("\xa0", " ")
        text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
        text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
        text = re.sub(r"<[^>]+>", " ", text)
        return re.sub(r"\s+", " ", text).strip(" \t\r\n/|\u00b7")

    @staticmethod
    def _safe_label(value, fallback="\u7ebf\u8def"):
        label = Spider._clean_text(value) or fallback
        return label.replace("$", "_").replace("#", "_")[:80]

    @staticmethod
    def _attr_first(node, names):
        if node is None:
            return ""
        for name in names:
            value = node.get(name)
            if value and not str(value).lower().startswith("data:image"):
                return str(value).strip()
        return ""

    def _first_text(self, node, selectors):
        if node is None or not hasattr(node, "select_one"):
            return ""
        for selector in selectors:
            found = node.select_one(selector)
            if found:
                text = self._clean_text(found.get_text(" ", strip=True))
                if text:
                    return text
        return ""

    @staticmethod
    def _log(message):
        try:
            print(f"[\u7f51\u98deTV] {message}")
        except Exception:
            pass
    def homeContent(self, filter=False):
        return {"class": list(self.CLASSES), "filters": {}}

    def homeVideoContent(self):
        source = self._get_text(self.host + "/", referer=self.host + "/")
        return {"list": self._parse_video_list(source, self.host)[:80]}

    def _parse_video_list(self, source, page_url=""):
        if not source:
            return []
        if BeautifulSoup is None:
            return self._parse_video_list_regex(source, page_url)

        soup = BeautifulSoup(source, "html.parser")
        records = {}
        order = []
        for anchor in soup.select('a[href*="/voddetail/"]'):
            href = anchor.get("href", "")
            if not self.DETAIL_PATH_RE.search(href):
                continue
            absolute = self._absolute(href, page_url or self.host)
            path_match = self.DETAIL_PATH_RE.search(urlparse(absolute).path)
            vod_id = path_match.group(0) if path_match else absolute
            image = anchor.find("img")
            title = (
                anchor.get("title")
                or self._attr_first(image, ("alt", "title"))
                or self._first_text(anchor, (
                    ".module-item-title", ".module-poster-item-title", ".video-name",
                    ".vod-name", ".title", "h3", "h4", "strong",
                ))
            )
            title = self._clean_text(title)
            if title.lower() in {"play", "detail", "more"}:
                title = ""
            pic = self._attr_first(
                image, ("data-original", "data-src", "data-lazy", "data-echo", "src")
            )
            pic = self._absolute(pic, page_url or self.host) if pic else ""

            card = anchor
            for _ in range(4):
                if card is None:
                    break
                classes = " ".join(card.get("class", [])) if hasattr(card, "get") else ""
                if re.search(r"item|card|list|module|poster|video", classes, re.I):
                    break
                card = card.parent
            remarks = self._first_text(card, (
                ".module-item-note", ".module-poster-item-info", ".pic-text",
                ".video-serial", ".remarks", ".remark", ".note", ".hdtag",
                ".text-right", ".module-item-caption", ".module-item-text",
            ))

            record = records.get(vod_id)
            if record is None:
                record = {
                    "vod_id": vod_id,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": self._clean_text(remarks),
                }
                records[vod_id] = record
                order.append(vod_id)
            else:
                if not record["vod_name"] and title:
                    record["vod_name"] = title
                if not record["vod_pic"] and pic:
                    record["vod_pic"] = pic
                if not record["vod_remarks"] and remarks:
                    record["vod_remarks"] = self._clean_text(remarks)
        return [records[key] for key in order if records[key].get("vod_name")]

    def _parse_video_list_regex(self, source, page_url):
        records = []
        seen = set()
        pattern = re.compile(
            r"<a\b([^>]*href=[\"']([^\"']*/voddetail/[^\"']+\.html)[\"'][^>]*)>",
            re.I,
        )
        for match in pattern.finditer(source):
            href = match.group(2)
            path_match = self.DETAIL_PATH_RE.search(href)
            vod_id = path_match.group(0) if path_match else href
            if vod_id in seen:
                continue
            seen.add(vod_id)
            snippet = source[match.start():match.start() + 1600]
            title_match = re.search(r"(?:title|alt)=[\"']([^\"']+)[\"']", snippet, re.I)
            pic_match = re.search(
                r"(?:data-original|data-src|data-lazy|data-echo|src)=[\"']([^\"']+)[\"']",
                snippet,
                re.I,
            )
            title = self._clean_text(title_match.group(1) if title_match else "")
            if not title:
                continue
            records.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": self._absolute(pic_match.group(1), page_url or self.host)
                if pic_match else "",
                "vod_remarks": "",
            })
        return records

    def _parse_pagecount(self, source, current_page):
        if not source:
            return current_page
        values = [int(value) for value in re.findall(r"/page/(\d+)", source)]
        values += [int(value) for value in re.findall(r"[?&]page=(\d+)", source)]
        total_match = re.search(r"\u5171\s*(\d+)\s*\u9875", self._clean_text(source))
        if total_match:
            values.append(int(total_match.group(1)))
        return max(values + [current_page + 1])

    @staticmethod
    def _is_homepage_source(source):
        canonical = re.search(
            r'<link\b[^>]*rel=["\']canonical["\'][^>]*href=["\']([^"\']+)',
            source or "",
            re.I,
        )
        if not canonical or urlparse(html_module.unescape(canonical.group(1))).path.rstrip("/"):
            return False
        title = re.search(r"<title\b[^>]*>(.*?)</title>", source or "", re.I | re.S)
        title_text = Spider._clean_text(title.group(1)) if title else ""
        return not re.search(r"\u641c\u7d22|search", title_text, re.I)

    def _fetch_first_list(self, paths, reject_home=False):
        last_source = ""
        for path in paths:
            url = self._absolute(path, self.host)
            source = self._get_text(url, referer=self.host + "/")
            if source:
                last_source = source
                if reject_home and self._is_homepage_source(source):
                    continue
                videos = self._parse_video_list(source, url)
                if videos:
                    return videos, source
        return [], last_source

    def categoryContent(self, tid, pg, filter=False, extend=None):
        page = self._safe_int(pg, 1, 1)
        tid = str(tid or "1")
        if page == 1:
            paths = [f"/vodshow/id/{tid}.html", f"/vodtype/{tid}.html"]
        else:
            paths = [
                f"/vodshow/page/{page}/id/{tid}.html",
                f"/vodshow/id/{tid}/page/{page}.html",
                f"/vodtype/{tid}.html?page={page}",
            ]
        videos, source = self._fetch_first_list(paths)
        pagecount = self._parse_pagecount(source, page) if videos else page
        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": len(videos),
            "total": pagecount * max(len(videos), 1),
        }

    def searchContent(self, key, quick, pg="1"):
        page = self._safe_int(pg, 1, 1)
        keyword = quote(unquote(str(key or "").strip()), safe="")
        if not keyword:
            return {"list": [], "page": page, "pagecount": page, "limit": 0, "total": 0}
        current = f"/vod/search?wd={keyword}"
        if page > 1:
            current += f"&page={page}"
        rewritten = f"/vodsearch/wd/{keyword}.html"
        query_style = f"/vodsearch/-------------.html?wd={keyword}&page={page}"
        paths = [current, rewritten, query_style] if page == 1 else [current, query_style, rewritten]
        videos, source = self._fetch_first_list(paths, reject_home=True)
        pagecount = self._parse_pagecount(source, page) if videos else page
        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": len(videos),
            "total": pagecount * max(len(videos), 1),
        }
    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
        raw_id = str(raw_id or "").strip()
        if not raw_id:
            return {"list": []}
        if raw_id.isdigit():
            raw_id = f"/voddetail/{raw_id}.html"
        detail_url = self._absolute(raw_id, self.host)
        source = self._get_text(detail_url, referer=self.host + "/")
        metadata = self._parse_detail_metadata(source, detail_url)
        line_links = self._extract_line_links(source, detail_url)
        parsed_lines = self._fetch_provider_lines(line_links, detail_url)
        metadata.update({
            "vod_id": raw_id,
            "vod_play_from": "$$$".join(item[0] for item in parsed_lines),
            "vod_play_url": "$$$".join(item[1] for item in parsed_lines),
        })
        if not parsed_lines and source:
            self._log("detail found but no provider line could be parsed")
        return {"list": [metadata]}

    def _parse_detail_metadata(self, source, detail_url):
        result = {
            "vod_name": "\u672a\u77e5\u5f71\u7247",
            "vod_pic": "",
            "type_name": "",
            "vod_year": "",
            "vod_area": "",
            "vod_remarks": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": "",
        }
        if not source:
            id_match = re.search(r"/voddetail/([^/.]+)", detail_url)
            result["vod_name"] = "\u5f71\u7247" + (id_match.group(1) if id_match else "")
            return result

        if BeautifulSoup is None:
            title_match = re.search(r"<h1\b[^>]*>(.*?)</h1>", source, re.I | re.S)
            if title_match:
                result["vod_name"] = self._clean_text(title_match.group(1))
            pic_match = re.search(
                r"<meta\b[^>]*(?:property|name)=[\"']og:image[\"'][^>]*content=[\"']([^\"']+)",
                source,
                re.I,
            )
            if pic_match:
                result["vod_pic"] = self._absolute(pic_match.group(1), detail_url)
            return result

        soup = BeautifulSoup(source, "html.parser")
        title_node = soup.select_one(
            ".module-info-heading h1, .module-info-heading h2, .detail-title h1, "
            ".vod-detail h1, h1"
        )
        if title_node:
            result["vod_name"] = self._clean_text(title_node.get_text(" ", strip=True))
        else:
            og_title = soup.select_one('meta[property="og:title"]')
            if og_title and og_title.get("content"):
                result["vod_name"] = self._clean_text(og_title.get("content"))

        pic_node = soup.select_one('meta[property="og:image"]')
        pic = pic_node.get("content", "") if pic_node else ""
        if not pic:
            image = soup.select_one(
                ".module-info-poster img, .detail-pic img, .vod-detail img, "
                ".module-item-pic img, img.poster, img.cover"
            )
            pic = self._attr_first(
                image, ("data-original", "data-src", "data-lazy", "data-echo", "src")
            )
        result["vod_pic"] = self._absolute(pic, detail_url) if pic else ""

        labels = self._extract_detail_labels(soup)
        result["type_name"] = labels.get("\u7c7b\u578b", "") or labels.get("\u5206\u7c7b", "")
        result["vod_year"] = labels.get("\u5e74\u4efd", "") or labels.get("\u5e74\u4ee3", "")
        result["vod_area"] = labels.get("\u5730\u533a", "") or labels.get("\u56fd\u5bb6", "")
        result["vod_actor"] = labels.get("\u4e3b\u6f14", "") or labels.get("\u6f14\u5458", "")
        result["vod_director"] = labels.get("\u5bfc\u6f14", "")
        result["vod_remarks"] = (
            labels.get("\u8fdb\u5ea6", "") or labels.get("\u66f4\u65b0", "")
            or labels.get("\u72b6\u6001", "") or labels.get("\u9996\u64ad", "")
        )
        result["vod_content"] = self._first_text(soup, (
            ".module-info-introduction-content", ".module-info-introduction",
            ".vod_content", ".detail-content", ".detail-con", ".content-desc",
            "[class*='introduction']", "[class*='summary']",
        ))
        if not result["vod_content"]:
            meta_desc = soup.select_one('meta[name="description"]')
            if meta_desc:
                result["vod_content"] = self._clean_text(meta_desc.get("content", ""))
        return result

    def _extract_detail_labels(self, soup):
        labels = {}
        wanted = {
            "\u7c7b\u578b", "\u5206\u7c7b", "\u5e74\u4efd", "\u5e74\u4ee3",
            "\u5730\u533a", "\u56fd\u5bb6", "\u4e3b\u6f14", "\u6f14\u5458",
            "\u5bfc\u6f14", "\u7f16\u5267", "\u8bed\u8a00", "\u9996\u64ad",
            "\u4e0a\u6620", "\u8fdb\u5ea6", "\u66f4\u65b0", "\u72b6\u6001",
            "\u539f\u540d", "\u522b\u540d",
        }
        for text in soup.stripped_strings:
            cleaned = self._clean_text(text)
            match = re.match(r"^([^\uff1a:]{1,8})[\uff1a:]\s*(.+)$", cleaned)
            if match and match.group(1).strip() in wanted:
                key = match.group(1).strip()
                value = self._clean_text(match.group(2))
                if value and key not in labels:
                    labels[key] = value
        return labels

    def _extract_line_links(self, source, detail_url):
        if not source:
            return []
        if BeautifulSoup is None:
            return self._extract_line_links_regex(source, detail_url)

        soup = BeautifulSoup(source, "html.parser")
        candidates = []
        line_pattern = re.compile(
            r"(?:\u7ebf\u8def|\u8def\u7ebf|\u5728\u7ebf|\u4e91\u64ad|\u64ad\u653e\u6e90)\s*\d*"
        )
        for anchor in soup.find_all("a", href=True):
            text = self._clean_text(anchor.get_text(" ", strip=True))
            href = anchor.get("href", "").strip()
            if not href or href.startswith(("#", "javascript:", "mailto:")):
                continue
            classes = " ".join(anchor.get("class", []))
            if not line_pattern.search(text) and not re.search(r"play|source|line|route", classes, re.I):
                continue
            absolute = self._absolute(href, detail_url)
            if absolute != detail_url:
                candidates.append((self._safe_label(text), absolute))

        if not candidates:
            heading = soup.find(string=re.compile(r"\u89c2\u770b\u65b9\u5f0f|\u5728\u7ebf\u89c2\u770b|\u64ad\u653e\u7ebf\u8def"))
            container = heading.parent if heading else None
            for _ in range(4):
                if container is None:
                    break
                anchors = container.find_all("a", href=True)
                for anchor in anchors:
                    href = anchor.get("href", "")
                    if href and not href.startswith(("#", "javascript:")):
                        candidates.append((
                            self._safe_label(anchor.get_text(" ", strip=True)),
                            self._absolute(href, detail_url),
                        ))
                if candidates:
                    break
                container = container.parent

        result = []
        seen = set()
        generic = {
            "\u5728\u7ebf\u89c2\u770b", "\u64ad\u653e", "\u89c2\u770b\u65b9\u5f0f", "\u7ebf\u8def"
        }
        for index, (label, url) in enumerate(candidates, 1):
            if url in seen:
                continue
            seen.add(url)
            if label in generic:
                label = "\u7ebf\u8def" + str(index)
            result.append((label, url))
        return result[:30]

    def _extract_line_links_regex(self, source, detail_url):
        result = []
        seen = set()
        line_pattern = re.compile(
            r"(?:\u7ebf\u8def|\u8def\u7ebf|\u5728\u7ebf|\u4e91\u64ad|\u64ad\u653e\u6e90)\s*\d*"
        )
        for match in re.finditer(
            r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
            source,
            re.I | re.S,
        ):
            label = self._clean_text(match.group(2))
            if not line_pattern.search(label):
                continue
            url = self._absolute(match.group(1), detail_url)
            if url in seen:
                continue
            seen.add(url)
            result.append((self._safe_label(label, "\u7ebf\u8def" + str(len(result) + 1)), url))
        return result
    def _fetch_provider_lines(self, line_links, detail_url):
        if not line_links:
            return []

        for main_label, provider_url in line_links:
            try:
                groups = self._parse_provider_detail(main_label, provider_url, detail_url)
            except Exception:
                groups = []
            if not groups:
                continue

            merged = []
            used_labels = set()
            for label, episodes in groups:
                unique_label = label
                suffix = 2
                while unique_label in used_labels:
                    unique_label = f"{label}-{suffix}"
                    suffix += 1
                used_labels.add(unique_label)
                merged.append((unique_label, episodes))
            if merged:
                return merged[:20]
        return []

    def _parse_provider_detail(self, main_label, provider_url, detail_url):
        if self.PLAY_PATH_RE.search(urlparse(provider_url).path):
            return [(main_label, f"\u64ad\u653e${provider_url}")]
        source = self._get_text(provider_url, referer=detail_url)
        if not source:
            return []
        if re.search(r"module-play-list", source, re.I):
            groups = self._provider_groups_regex(source, provider_url, main_label)
            if groups:
                return groups
        if BeautifulSoup is None:
            return self._provider_groups_regex(source, provider_url, main_label)

        soup = BeautifulSoup(source, "html.parser")
        episode_anchors = [
            anchor for anchor in soup.find_all("a", href=True)
            if self.PLAY_PATH_RE.search(anchor.get("href", ""))
        ]
        if not episode_anchors:
            return []

        playlist_anchors = [
            anchor for anchor in episode_anchors
            if not re.search(
                r"(?:^|\s)(?:main-btn|play-btn(?:-[\w-]+)?)\b",
                " ".join(anchor.get("class", [])), re.I,
            )
        ]
        episode_anchors = playlist_anchors or episode_anchors

        block_re = re.compile(
            r"module-play-list|anthology-list|playlist|play-list|"
            r"stui-content__playlist|myui-content__list|numList|episode-list",
            re.I,
        )
        block_nodes = []
        block_keys = set()
        for anchor in episode_anchors:
            block = anchor.find_parent(class_=block_re)
            if block is None:
                block = anchor.find_parent(["ul", "ol", "div"])
            key = id(block) if block is not None else 0
            if key not in block_keys:
                block_keys.add(key)
                block_nodes.append(block)

        if len(block_nodes) <= 1:
            episodes = self._episodes_from_anchors(episode_anchors, provider_url)
            return [(main_label, "#".join(episodes))] if episodes else []

        groups = []
        tab_names = self._extract_provider_tab_names(soup)
        for index, block in enumerate(block_nodes):
            anchors = block.find_all("a", href=True) if block is not None else episode_anchors
            anchors = [
                anchor for anchor in anchors
                if self.PLAY_PATH_RE.search(anchor.get("href", ""))
            ]
            episodes = self._episodes_from_anchors(anchors, provider_url)
            if not episodes:
                continue
            sub_name = tab_names[index] if index < len(tab_names) else "\u6e90" + str(index + 1)
            groups.append((self._safe_label(f"{main_label}-{sub_name}"), "#".join(episodes)))
        return groups

    def _extract_provider_tab_names(self, soup):
        selectors = (
            ".module-tab-item", ".anthology-tab a", ".anthology-tab li",
            ".play_source_tab li", ".nav-tabs li", "[data-from]",
            "[data-dropdown-value]", ".source-tab", ".playlist-tab",
        )
        names = []
        seen = set()
        for selector in selectors:
            for node in soup.select(selector):
                text = self._clean_text(node.get_text(" ", strip=True))
                if not text or len(text) > 50 or re.fullmatch(r"\u7b2c?\d+[\u96c6\u671f]?", text):
                    continue
                text = re.sub(r"\s+\d+$", "", text)
                if text not in seen:
                    seen.add(text)
                    names.append(self._safe_label(text))
            if names:
                break
        return names

    def _episodes_from_anchors(self, anchors, page_url):
        episodes = []
        seen = set()
        for anchor in anchors:
            href = anchor.get("href", "")
            if not self.PLAY_PATH_RE.search(href):
                continue
            absolute = self._absolute(href, page_url)
            if absolute in seen:
                continue
            seen.add(absolute)
            name = self._clean_text(
                anchor.get_text(" ", strip=True) or anchor.get("data-title")
                or anchor.get("title")
            )
            if not name:
                path_match = re.search(r"-(\d+)\.html", urlparse(absolute).path)
                name = ("\u7b2c" + path_match.group(1) + "\u96c6") if path_match else "\u64ad\u653e"
            name = re.sub(r"\u7b2c0+(\d+)([\u96c6\u671f])", lambda match: "\u7b2c" + str(int(match.group(1))) + match.group(2), name)
            episodes.append(f"{self._safe_label(name, chr(0x64ad) + chr(0x653e))}${absolute}")
        return episodes

    def _provider_groups_regex(self, source, page_url, main_label):
        panel_re = re.compile(
            r'<div\b(?=[^>]*class=["\'][^"\']*\bmodule-list\b[^"\']*["\'])'
            r'(?=[^>]*\bid=["\']panel\d+["\'])[^>]*>',
            re.I,
        )
        panels = list(panel_re.finditer(source or ""))
        if panels:
            tab_re = re.compile(
                r'<div\b(?=[^>]*class=["\'][^"\']*\bmodule-tab-item\b[^"\']*["\'])'
                r'(?=[^>]*data-dropdown-value=["\']([^"\']+))[^>]*>',
                re.I,
            )
            names = [
                self._safe_label(self._clean_text(match.group(1)))
                for match in tab_re.finditer(source)
            ]
            groups = []
            for index, panel in enumerate(panels):
                end = panels[index + 1].start() if index + 1 < len(panels) else len(source)
                episodes = self._provider_episodes_regex(source[panel.start():end], page_url)
                if not episodes:
                    continue
                sub_name = names[index] if index < len(names) else "\u6e90" + str(index + 1)
                label = self._safe_label(f"{main_label}-{sub_name}")
                groups.append((label, "#".join(episodes)))
            if groups:
                return groups

        episodes = self._provider_episodes_regex(source, page_url)
        return [(main_label, "#".join(episodes))] if episodes else []

    def _provider_episodes_regex(self, source, page_url):
        episodes = []
        seen = set()
        for match in re.finditer(
            r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
            source,
            re.I | re.S,
        ):
            if not self.PLAY_PATH_RE.search(match.group(1)):
                continue
            absolute = self._absolute(match.group(1), page_url)
            if absolute in seen:
                continue
            seen.add(absolute)
            name = self._clean_text(match.group(2))
            name = re.sub(r"\u7b2c0+(\d+)([\u96c6\u671f])", lambda match: "\u7b2c" + str(int(match.group(1))) + match.group(2), name)
            name = self._safe_label(name, "\u64ad\u653e")
            episodes.append(f"{name}${absolute}")
        return episodes
    def playerContent(self, flag, id, vipFlags=None):

        play_url = self._absolute(str(id or ""), self.host)
        headers = self._play_headers(play_url)
        if self._is_media_url(play_url):
            return self._direct_result(play_url, headers)

        source = self._get_text(play_url, referer=self._origin_root(play_url))
        if not source:
            return {"parse": 1, "jx": 0, "url": play_url, "header": headers}

        config_urls = []
        for variable in ("player_aaaa", "player_data", "MacPlayer"):
            config = self._extract_js_object(source, variable)
            if not config:
                continue
            raw_url = self._find_url_in_config(config)
            decoded = self._decode_player_url(raw_url, config.get("encrypt"), play_url)
            if decoded:
                config_urls.append(decoded)
                if self._is_media_url(decoded):
                    return self._direct_result(decoded, self._play_headers(play_url))

        direct = self._extract_direct_media(source, play_url)
        if direct:
            return self._direct_result(direct, self._play_headers(play_url))

        iframe = self._extract_iframe(source, play_url)
        if iframe:
            if self._is_media_url(iframe):
                return self._direct_result(iframe, self._play_headers(play_url))
            return {"parse": 1, "jx": 0, "url": iframe, "header": headers}

        for candidate in config_urls:
            if candidate.startswith(("http://", "https://")):
                return {"parse": 1, "jx": 0, "url": candidate, "header": headers}
        return {"parse": 1, "jx": 0, "url": play_url, "header": headers}

    def _play_headers(self, referer):
        headers = {"User-Agent": self.ua, "Referer": referer}
        if self.cookie:
            headers["Cookie"] = self.cookie
        return headers

    def _direct_result(self, media_url, headers):
        final_url = media_url
        if self.proxy_enabled and ".m3u8" in media_url.lower():
            proxied = self._proxy_url(media_url, headers.get("Referer", ""), "m3u8")
            if proxied:
                final_url = proxied
                headers = {}
        return {"parse": 0, "jx": 0, "url": final_url, "header": headers}

    @classmethod
    def _is_media_url(cls, value):
        if not value:
            return False
        lower = html_module.unescape(str(value)).lower()
        return lower.startswith(("http://", "https://")) and any(
            extension in lower for extension in cls.MEDIA_EXTENSIONS
        )

    def _extract_js_object(self, source, variable):
        match = re.search(
            rf"(?:var\s+|let\s+|const\s+|window\.)?{re.escape(variable)}\s*=\s*",
            source,
            re.I,
        )
        if not match:
            return {}
        start = source.find("{", match.end())
        if start < 0:
            return {}
        depth = 0
        quote_char = ""
        escaped = False
        for index in range(start, min(len(source), start + 200000)):
            char = source[index]
            if quote_char:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote_char:
                    quote_char = ""
                continue
            if char in ("'", '"'):
                quote_char = char
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    text = source[start:index + 1]
                    try:
                        value = json.loads(text)
                        return value if isinstance(value, dict) else {}
                    except Exception:
                        try:
                            value = ast.literal_eval(text)
                            return value if isinstance(value, dict) else {}
                        except Exception:
                            return {}
        return {}

    def _find_url_in_config(self, config):
        for key in ("url", "play_url", "playUrl", "src", "m3u8"):
            value = config.get(key)
            if value:
                return str(value)
        for value in config.values():
            if isinstance(value, dict):
                nested = self._find_url_in_config(value)
                if nested:
                    return nested
        return ""

    def _decode_player_url(self, raw_url, encrypt, page_url):
        if raw_url is None:
            return ""
        raw = html_module.unescape(str(raw_url)).replace("\\/", "/").strip()
        candidates = [raw]
        try:
            mode = int(encrypt or 0)
        except (TypeError, ValueError):
            mode = 0
        if mode == 1:
            candidates.insert(0, unquote(raw))
        elif mode == 2:
            decoded = self._decode_base64(raw)
            if decoded:
                candidates.insert(0, unquote(decoded))
        else:
            unquoted = unquote(raw)
            if unquoted != raw:
                candidates.insert(0, unquoted)
            decoded = self._decode_base64(raw)
            if decoded:
                candidates.insert(0, unquote(decoded))
        for candidate in candidates:
            candidate = html_module.unescape(candidate).replace("\\/", "/").strip()
            if candidate.startswith(("http://", "https://", "//", "/")):
                return self._absolute(candidate, page_url)
        return ""

    @staticmethod
    def _decode_base64(value):
        text = str(value).strip()
        if not text or not re.fullmatch(r"[A-Za-z0-9_+/=-]+", text):
            return ""
        try:
            padded = text + "=" * (-len(text) % 4)
            return base64.urlsafe_b64decode(padded.encode()).decode("utf-8", "ignore")
        except Exception:
            return ""

    def _extract_direct_media(self, source, page_url):
        text = html_module.unescape(source).replace("\\/", "/")
        text = re.sub(
            r"\\u([0-9a-fA-F]{4})",
            lambda match: chr(int(match.group(1), 16)),
            text,
        )
        patterns = (
            r"https?://[^\"'<>\s]+?\.m3u8(?:\?[^\"'<>\s]*)?",
            r"https?://[^\"'<>\s]+?\.(?:mp4|flv|mkv|webm)(?:\?[^\"'<>\s]*)?",
            r"(?:src|url)\s*[:=]\s*[\"']([^\"']+?\.(?:m3u8|mp4|flv|mkv|webm)(?:\?[^\"']*)?)[\"']",
        )
        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                value = match.group(1) if match.lastindex else match.group(0)
                return self._absolute(value, page_url)
        return ""

    def _extract_iframe(self, source, page_url):
        match = re.search(r"<iframe\b[^>]*src=[\"']([^\"']+)[\"']", source, re.I)
        return self._absolute(match.group(1), page_url) if match else ""

    @staticmethod
    def _origin_root(url):
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}/" if parsed.scheme and parsed.netloc else url
    def _proxy_url(self, real_url, referer, mode):
        try:
            base = self.getProxyUrl()
        except Exception:
            base = ""
        if not base:
            return ""
        separator = "&" if "?" in base else "?"
        params = {
            "mode": mode,
            "url": self._b64_encode(real_url),
            "ref": self._b64_encode(referer or real_url),
        }
        query = "&".join(f"{key}={quote(value, safe='')}" for key, value in params.items())
        return base + separator + query

    @staticmethod
    def _b64_encode(value):
        return base64.urlsafe_b64encode(str(value).encode()).decode().rstrip("=")

    @staticmethod
    def _b64_decode(value):
        try:
            text = str(value or "")
            return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4)).decode()
        except Exception:
            return ""

    def localProxy(self, param):
        params = param or {}
        mode = self._param_value(params, "mode") or "segment"
        real_url = self._b64_decode(self._param_value(params, "url"))
        referer = self._b64_decode(self._param_value(params, "ref")) or real_url
        if not real_url:
            return [400, "text/plain", {}, b"missing url"]
        response = self._request_raw(real_url, referer=referer, binary=True)
        if response is None:
            return [502, "text/plain", {}, b"upstream request failed"]
        content_type = response.headers.get("Content-Type", "application/octet-stream")
        if mode == "m3u8" or ".m3u8" in real_url.lower() or "mpegurl" in content_type.lower():
            try:
                response.encoding = response.apparent_encoding or "utf-8"
                playlist = response.text
            except Exception:
                playlist = response.content.decode("utf-8", "ignore")
            rewritten = self._rewrite_m3u8(playlist, real_url)
            return [200, "application/vnd.apple.mpegurl", {}, rewritten]
        headers = {}
        if response.headers.get("Content-Length"):
            headers["Content-Length"] = response.headers.get("Content-Length")
        return [response.status_code, content_type, headers, response.content]

    @staticmethod
    def _param_value(params, key):
        value = params.get(key, "") if isinstance(params, dict) else ""
        if isinstance(value, (list, tuple)):
            return value[-1] if value else ""
        return value

    def _rewrite_m3u8(self, playlist, playlist_url):
        output = []
        for raw_line in (playlist or "").splitlines():
            line = raw_line.strip()
            if not line:
                output.append(raw_line)
                continue
            if not line.startswith("#"):
                absolute = self._absolute(line, playlist_url)
                if self._is_ad_url(absolute):
                    while output and output[-1].strip().startswith(("#EXTINF", "#EXT-X-BYTERANGE")):
                        output.pop()
                    continue
                mode = "m3u8" if ".m3u8" in urlparse(absolute).path.lower() else "segment"
                output.append(self._proxy_url(absolute, playlist_url, mode) or absolute)
                continue
            if "URI=" in line.upper():
                line = re.sub(
                    r"URI=([\"'])(.*?)\1",
                    lambda match: self._rewrite_m3u8_uri(match, playlist_url, line),
                    line,
                    flags=re.I,
                )
            output.append(line)
        return "\n".join(output) + "\n"

    def _rewrite_m3u8_uri(self, match, playlist_url, whole_line):
        absolute = self._absolute(match.group(2), playlist_url)
        upper = whole_line.upper()
        if "#EXT-X-KEY" in upper:
            mode = "key"
        elif ".m3u8" in urlparse(absolute).path.lower():
            mode = "m3u8"
        else:
            mode = "segment"
        proxied = self._proxy_url(absolute, playlist_url, mode) or absolute
        return f'URI="{proxied}"'

    def _is_ad_url(self, url):
        lower = unquote(str(url or "")).lower()
        return any(keyword in lower for keyword in self.AD_KEYWORDS)

    def isVideoFormat(self, url):
        return self._is_media_url(url)

    def manualVideoCheck(self):
        return False


if __name__ == "__main__":
    spider = Spider()
    spider.init("")
    print(json.dumps(spider.homeContent(False), ensure_ascii=False, indent=2))
