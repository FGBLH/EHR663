# -*- coding: utf-8 -*-
# //@name:Jable直播放
# //@id:jable_direct
# //@version:3

import html as html_lib
import json
import re
import time
from urllib.parse import quote, unquote, urljoin, urlsplit

import requests
from lxml import html

from base.spider import Spider as BaseSpider


class WafBlockedError(RuntimeError):
    pass


class Spider(BaseSpider):
    name = "Jable直播放"
    host = "https://jable.sbs"
    backend_parse = False
    category_mode = False
    categoryMode = False

    DEFAULT_HOSTS = (
        "https://jable.sbs",
        "https://91jable.sbs",
        "https://jable.tv",
    )

    PLAY_PREFIX = "jable-play:"
    ERROR_PREFIX = "jable-error:"
    CATEGORY_ERROR_PREFIX = "jable-category-error:"
    DEFAULT_PIC = "https://jable.sbs/favicon.ico"

    CATEGORY_SPECS = (
        ("latest-updates", "最近更新", "/latest-updates/"),
        ("hot", "热门影片", "/hot/"),
        ("new-release", "最新上市", "/new-release/"),
        ("chinese-subtitle", "中文字幕", "/categories/chinese-subtitle/"),
        ("roleplay", "角色剧情", "/categories/roleplay/"),
        ("uniform", "制服诱惑", "/categories/uniform/"),
        ("pantyhose", "丝袜美腿", "/categories/pantyhose/"),
        ("sex-only", "直接开啪", "/categories/sex-only/"),
        ("bdsm", "主奴调教", "/categories/bdsm/"),
        ("groupsex", "多P群交", "/categories/groupsex/"),
        ("pov", "男友视角", "/categories/pov/"),
        ("insult", "凌辱快感", "/categories/insult/"),
        ("private-cam", "盗摄偷拍", "/categories/private-cam/"),
        ("uncensored", "无码解放", "/categories/uncensored/"),
        ("lesbian", "女同欢愉", "/categories/lesbian/"),
    )
    GLOBAL_CATEGORY_IDS = frozenset({"latest-updates", "hot", "new-release"})
    SORTS = (
        ("近期最佳", "post_date_and_popularity"),
        ("最近更新", "post_date"),
        ("最多观看", "video_viewed"),
        ("最高收藏", "most_favourited"),
    )
    SORT_VALUES = frozenset(value for _, value in SORTS)

    BLOCKED_HOSTS = frozenset(
        {
            "go.mayzaent.com",
            "go.mnaspm.com",
            "a.labadena.com",
            "ads.adxadserv.com",
            "static.adxadserv.com",
            "cdn.tapioni.com",
            "cdn2.tapioni.com",
            "t.fluxtrck.site",
            "s.zline0.com",
            "imasdk.googleapis.com",
            "www.googletagmanager.com",
            "a.magsrv.com",
            "syndication.exosrv.com",
            "go.stripchat.cam",
            "141jj.com",
            "theporndude.com",
            "fuu78.com",
            "fuu79.com",
        }
    )
    ASSET_HOSTS = frozenset({"assets.jable.tv", "assets-cdn.jable.tv"})
    IMAGE_HOST_SUFFIXES = (".piccdn2.cfd",)
    CHALLENGE_MARKERS = (
        "just a moment",
        "/cdn-cgi/challenge-platform",
        "_cf_chl_opt",
        "cf-turnstile",
        "turnstile",
        "attention required",
    )
    CONTENT_MARKERS = (
        'class="video-img-box',
        "class='video-img-box",
        "var hlsurl",
        'id="player"',
        "list_videos_common_videos_list",
    )

    VIDEO_LINK_RE = re.compile(r"/(?:s0/)?videos/([^/?#]+)/?", re.I)
    HLS_RE = re.compile(
        r"\b(?:var|let|const)\s+hlsUrl\s*=\s*(['\"])(https?://.+?)\1",
        re.I | re.S,
    )
    HLS_FALLBACK_RE = re.compile(
        r"(['\"])(https?://[^'\"]+?\.m3u8(?:\?[^'\"]*)?)\1", re.I
    )
    PAGE_RE = re.compile(r"/(\d+)/?(?:[?#]|$)")
    DATE_RE = re.compile(r"上市於\s*(\d{4}-\d{2}-\d{2})")
    CODE_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,79}$", re.I)
    VIDEO_URL_RE = re.compile(r"\.m3u8(?:$|[?#])", re.I)

    def __init__(self):
        try:
            super().__init__()
        except Exception:
            pass
        self.timeout = 15
        self.manifest_timeout = 10
        self.cache_ttl = 30
        self.verify_tls = True
        self.trust_env = True
        self.proxy = ""
        self.fallback_hosts = list(self.DEFAULT_HOSTS)
        self._active_host = self.host
        self.expose_stable_line = True
        self.diagnostic_card = False
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        )
        self._session = None
        self._cache = {}
        self._reset_session()

    def getName(self):
        return self.name

    def init(self, extend=""):
        config = self._parse_config(extend)
        configured_host = str(config.get("host") or self.host).strip().rstrip("/")
        if configured_host.startswith(("http://", "https://")):
            self.host = configured_host
        if "fallback_hosts" in config:
            self.fallback_hosts = self._parse_hosts(config.get("fallback_hosts"))
        else:
            self.fallback_hosts = list(self.DEFAULT_HOSTS)
        self._active_host = self.host
        self.timeout = self._bounded_int(config.get("timeout"), self.timeout, 5, 45)
        self.manifest_timeout = self._bounded_int(
            config.get("manifest_timeout"), self.manifest_timeout, 3, 20
        )
        self.cache_ttl = self._bounded_int(
            config.get("cache_ttl"), self.cache_ttl, 0, 300
        )
        self.verify_tls = self._bool_value(config.get("verify_tls"), self.verify_tls)
        self.trust_env = self._bool_value(config.get("trust_env"), self.trust_env)
        self.expose_stable_line = self._bool_value(
            config.get("expose_stable_line"), self.expose_stable_line
        )
        self.diagnostic_card = self._bool_value(
            config.get("diagnostic_card"), self.diagnostic_card
        )
        self.proxy = str(config.get("proxy") or "").strip()
        configured_ua = str(config.get("user_agent") or "").strip()
        if configured_ua:
            self.user_agent = configured_ua
        self._cache.clear()
        self._reset_session()

    def destroy(self):
        if self._session is not None:
            try:
                self._session.close()
            except Exception:
                pass
        self._session = None
        self._cache.clear()

    def isVideoFormat(self, url):
        return bool(self.VIDEO_URL_RE.search(str(url or "")))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return [404, "text/plain; charset=utf-8", b"not found"]

    def homeContent(self, filter):
        classes = [
            {"type_id": type_id, "type_name": type_name}
            for type_id, type_name, _ in self.CATEGORY_SPECS
        ]
        sort_filter = [
            {
                "key": "sort",
                "name": "排序",
                "value": [{"n": label, "v": value} for label, value in self.SORTS],
            }
        ]
        filters = {
            type_id: sort_filter
            for type_id, _, _ in self.CATEGORY_SPECS
            if type_id not in self.GLOBAL_CATEGORY_IDS
        }
        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        result = self.categoryContent("latest-updates", "1", False, {})
        return {"list": result.get("list", []), "msg": result.get("msg", "")}

    def categoryContent(self, tid, pg, filter, extend):
        page = self._page_number(pg)
        spec = self._category_spec(tid)
        if spec is None:
            return self._empty_page(page, "未知分类")
        type_id, _, base_path = spec
        path = self._paged_path(base_path, page)
        if type_id not in self.GLOBAL_CATEGORY_IDS:
            sort_value = self._selected_sort(extend)
            if sort_value:
                path += "?sort_by=" + quote(sort_value, safe="")
        try:
            source, page_url = self._request_text(path)
            result = self._parse_list_page(source, page, page_url)
            if self.diagnostic_card and not result.get("list"):
                return self._category_failure(
                    page, "selector_mismatch: HTTP 页面未匹配到视频卡片"
                )
            return result
        except Exception as exc:
            return self._category_failure(page, "分类读取失败: %s" % exc)

    def searchContent(self, key, quick, pg="1"):
        keyword = self._clean_text(key)
        page = self._page_number(pg)
        if not keyword:
            return self._empty_page(page)
        segment = re.sub(r"[\\/\s]+", "-", keyword).strip("-").lower()
        segment = quote(segment, safe="-._~")
        path = "/search/%s/" % segment
        if page > 1:
            path += "%d/" % page
        try:
            source, page_url = self._request_text(path)
            return self._parse_list_page(source, page, page_url)
        except Exception as exc:
            return self._empty_page(page, "搜索失败: %s" % exc)

    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
        if str(raw_id or "").startswith(self.CATEGORY_ERROR_PREFIX):
            message = unquote(str(raw_id)[len(self.CATEGORY_ERROR_PREFIX) :])
            return {
                "list": [
                    self._detail_error("category-diagnostic", message)
                ]
            }
        code = self._normalize_code(raw_id)
        if not code:
            return {"list": []}
        try:
            source, page_url = self._request_text(self._detail_path(code))
            vod, _ = self._parse_detail_page(source, code, page_url)
            return {"list": [vod]}
        except Exception as exc:
            return {"list": [self._detail_error(code, str(exc))]}

    def playerContent(self, flag, id, vipFlags):
        value = str(id or "").strip()
        if value.startswith(self.ERROR_PREFIX):
            return self._player_error("detail_error", unquote(value[len(self.ERROR_PREFIX) :]))
        parsed = self._parse_play_id(value)
        if parsed is None:
            if value.startswith(("http://", "https://")):
                if not self._is_allowed_media_url(value):
                    return self._player_error("media_host_rejected", "播放地址不在媒体白名单")
                return self._player_result(value, "")
            return self._player_error("invalid_play_id", "无法识别播放 ID")

        mode, code = parsed
        last_error = None
        for attempt in range(2):
            try:
                source, page_url = self._request_text(
                    self._detail_path(code), fresh=True
                )
                _, media = self._parse_detail_page(source, code, page_url)
                media_url = media["url"]
                if self._signed_url_expired(media_url):
                    raise RuntimeError("signed_url_expired")
                if mode == "stable":
                    self._probe_manifest(media_url, media["referer"])
                return self._player_result(media_url, media["referer"])
            except WafBlockedError as exc:
                return self._player_error("blocked_by_waf", str(exc))
            except Exception as exc:
                last_error = exc
                if attempt == 0:
                    time.sleep(0.25)
                    continue
        code_name = self._player_error_code(last_error)
        return self._player_error(
            code_name,
            "%s播放地址解析失败: %s"
            % ("稳定" if mode == "stable" else "快速", last_error),
        )

    def _reset_session(self):
        if self._session is not None:
            try:
                self._session.close()
            except Exception:
                pass
        session = requests.Session()
        session.trust_env = self.trust_env
        session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,zh-TW;q=0.8,en;q=0.5",
                "Cache-Control": "no-cache",
            }
        )
        if self.proxy:
            session.proxies.update({"http": self.proxy, "https": self.proxy})
        self._session = session

    def _request_text(self, path, fresh=False):
        urls = self._request_urls(path)
        if not urls:
            raise RuntimeError("已阻止非站点 HTML 请求")
        now = time.time()
        if not fresh and self.cache_ttl > 0:
            for url in urls:
                cached = self._cache.get(url)
                if cached and now - cached[0] <= self.cache_ttl:
                    return cached[1], cached[2]

        request_errors = []
        waf_hosts = []
        for url in urls:
            try:
                response = self._session.get(
                    url,
                    timeout=(min(self.timeout, 10), self.timeout),
                    allow_redirects=True,
                    verify=self.verify_tls,
                )
                final_url = str(response.url or url)
                if not self._is_allowed_html_url(final_url):
                    raise RuntimeError(
                        "已阻止外域跳转: %s" % (urlsplit(final_url).hostname or "")
                    )
                source = self._response_text(response)
                if self._looks_like_challenge(
                    response.status_code, source, response.headers
                ):
                    waf_hosts.append(urlsplit(final_url).hostname or "unknown")
                    continue
                response.raise_for_status()
                self._active_host = self._origin(final_url)
                if not fresh and self.cache_ttl > 0:
                    self._cache[url] = (time.time(), source, final_url)
                return source, final_url
            except requests.RequestException as exc:
                request_errors.append(
                    "%s: %s" % (urlsplit(url).hostname or "unknown", exc)
                )
        if waf_hosts:
            raise WafBlockedError(
                "blocked_by_waf: %s 挑战需要可见浏览器或站点授权接口"
                % ",".join(dict.fromkeys(waf_hosts))
            )
        raise RuntimeError("网络请求失败: %s" % "; ".join(request_errors))

    def _probe_manifest(self, media_url, referer):
        if not self._is_allowed_media_url(media_url):
            raise RuntimeError("media_host_rejected")
        response = self._session.get(
            media_url,
            headers=self._player_headers(referer, manifest=True),
            timeout=(min(self.manifest_timeout, 8), self.manifest_timeout),
            verify=self.verify_tls,
            allow_redirects=True,
        )
        final_url = str(response.url or media_url)
        if not self._is_allowed_media_redirect(media_url, final_url):
            raise RuntimeError("media_redirect_rejected")
        if not 200 <= response.status_code < 300:
            raise RuntimeError("manifest_http_%s" % response.status_code)
        source = bytes(response.content or b"").decode("utf-8", errors="replace")
        if "#EXTM3U" not in source[:262144]:
            raise RuntimeError("manifest_invalid")
        return True

    def _parse_list_page(self, source, page, page_url):
        tree = self._tree(source)
        cards = tree.xpath(
            '//div[contains(concat(" ", normalize-space(@class), " "), " video-img-box ")]'
            '[.//h6[contains(concat(" ", normalize-space(@class), " "), " title ")]'
            '/a[contains(@href,"/videos/")]]'
        )
        if not cards:
            cards = tree.xpath(
                '//div[contains(concat(" ", normalize-space(@class), " "), " video-img-box ")]'
                '[.//a[contains(@href,"/videos/")]]'
            )
        items = []
        seen = set()
        for card in cards:
            links = card.xpath(
                './/h6[contains(concat(" ", normalize-space(@class), " "), " title ")]'
                '/a[contains(@href,"/videos/")][1]'
            )
            if not links:
                links = card.xpath('.//a[contains(@href,"/videos/")][1]')
            if not links:
                continue
            link = links[0]
            code = self._code_from_url(link.get("href"))
            if not code or code in seen:
                continue
            seen.add(code)
            images = card.xpath(
                './/img[@data-src or @data-original or @data-lazy-src or '
                '@data-lazyload or @src][1]'
            )
            title = self._clean_text(link.text_content())
            if not title:
                title = self._clean_text(link.get("title"))
            if not title and images:
                title = self._clean_text(images[0].get("alt"))
            title = title or code.upper()
            pic = ""
            if images:
                image = images[0]
                candidate = urljoin(
                    page_url,
                    image.get("data-src")
                    or image.get("data-original")
                    or image.get("data-lazy-src")
                    or image.get("data-lazyload")
                    or image.get("src")
                    or "",
                )
                if self._is_allowed_image_url(candidate):
                    pic = candidate
            duration = self._first_text(
                card.xpath(
                    './/*[contains(concat(" ", normalize-space(@class), " "), " absolute-bottom-right ")]'
                    '//*[contains(concat(" ", normalize-space(@class), " "), " label ")]'
                )
            )
            items.append(
                {
                    "vod_id": code,
                    "vod_name": title,
                    "vod_pic": pic or self.DEFAULT_PIC,
                    "vod_remarks": duration or "HLS",
                }
            )

        pagecount = page
        pagination_links = tree.xpath(
            '//a[@data-container-id="list_videos_common_videos_list_pagination"]/@href'
        )
        for href in pagination_links:
            match = self.PAGE_RE.search(str(href or ""))
            if match:
                pagecount = max(pagecount, self._page_number(match.group(1)))
        limit = len(items) or 24
        return {
            "list": items,
            "page": page,
            "pagecount": pagecount,
            "limit": limit,
            "total": pagecount * limit,
        }

    def _parse_detail_page(self, source, code, page_url):
        tree = self._tree(source)
        title = self._meta_content(tree, "property", "og:title")
        if not title:
            title = self._first_text(tree.xpath('//section[contains(@class,"video-info")]//h4[1]'))
        title = title or code.upper()

        pic = self._meta_content(tree, "property", "og:image")
        if not pic:
            posters = tree.xpath('//video[@id="player"]/@poster | //video[1]/@poster')
            pic = posters[0] if posters else ""
        pic = urljoin(page_url, pic) if pic else ""
        if not self._is_allowed_image_url(pic):
            pic = self.DEFAULT_PIC

        description = self._meta_content(tree, "name", "description")
        if not description:
            description = self._meta_content(tree, "property", "og:description")
        actors = self._unique_texts(
            tree.xpath(
                '//a[contains(concat(" ", normalize-space(@class), " "), " model ")]'
                '//*[@data-original-title]/@data-original-title | '
                '//a[contains(concat(" ", normalize-space(@class), " "), " model ")]/@title'
            )
        )
        categories = self._unique_texts(
            tree.xpath('//a[contains(@href,"/categories/") and contains(@class,"cat")]/text()')
        )
        tags = self._unique_texts(
            tree.xpath('//h5[contains(@class,"tags")]//a[contains(@href,"/tags/")]/text()')
        )
        body_text = self._clean_text(
            " ".join(tree.xpath('//section[contains(@class,"video-info")]//text()'))
        )
        release_match = self.DATE_RE.search(body_text)
        release_date = release_match.group(1) if release_match else ""

        hls_url = self._extract_hls_url(source)
        referer = (
            str(page_url)
            if self._is_allowed_html_url(page_url)
            else self._canonical_detail_url(code)
        )
        content_parts = [description]
        if actors:
            content_parts.append("演员: " + ", ".join(actors))
        if categories:
            content_parts.append("分类: " + ", ".join(categories))
        if tags:
            content_parts.append("标签: " + ", ".join(tags))
        content = "\n".join(part for part in content_parts if part)

        fast_id = self.PLAY_PREFIX + "fast:" + code
        play_from = "Jable快速"
        play_url = "快速播放$" + fast_id
        if self.expose_stable_line:
            stable_id = self.PLAY_PREFIX + "stable:" + code
            play_from += "$$$Jable稳定"
            play_url += "$$$稳定校验$" + stable_id
        vod = {
            "vod_id": code,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": "签名HLS",
            "vod_content": content,
            "vod_actor": ", ".join(actors),
            "vod_class": ", ".join(categories + tags),
            "vod_year": release_date[:4] if release_date else "",
            "vod_play_from": play_from,
            "vod_play_url": play_url,
        }
        return vod, {"url": hls_url, "referer": referer}

    def _extract_hls_url(self, source):
        match = self.HLS_RE.search(str(source or ""))
        candidates = [match.group(2)] if match else []
        candidates.extend(
            item.group(2) for item in self.HLS_FALLBACK_RE.finditer(str(source or ""))
        )
        for value in candidates:
            url = html_lib.unescape(value.strip())
            if self._is_allowed_media_url(url):
                return url
        if candidates:
            raise RuntimeError("media_host_rejected")
        raise RuntimeError("missing_hls_url")

    def _player_result(self, media_url, referer):
        return {
            "parse": 0,
            "jx": 0,
            "playUrl": "",
            "url": media_url,
            "header": self._player_headers(referer),
            "type": "m3u8",
            "format": "application/x-mpegURL",
        }

    def _player_headers(self, referer, manifest=False):
        referer = referer or self._active_host.rstrip("/") + "/"
        headers = {
            "User-Agent": self.user_agent,
            "Referer": referer,
            "Origin": self._origin(referer),
        }
        if manifest:
            headers["Accept"] = (
                "application/vnd.apple.mpegurl,application/x-mpegURL,*/*"
            )
        return headers

    def _player_error(self, code, message):
        text = self._clean_text(message) or "播放失败"
        return {
            "parse": 0,
            "jx": 0,
            "playUrl": "",
            "url": "",
            "header": {},
            "code": code,
            "msg": text,
            "content": text,
            "error": text,
        }

    def _detail_error(self, code, message):
        text = self._clean_text(message) or "详情读取失败"
        return {
            "vod_id": code or "error",
            "vod_name": "详情读取失败",
            "vod_pic": self.DEFAULT_PIC,
            "vod_content": text,
            "vod_play_from": "错误",
            "vod_play_url": "查看错误$%s%s"
            % (self.ERROR_PREFIX, quote(text, safe="")),
        }

    def _category_spec(self, tid):
        value = str(tid or "latest-updates").strip()
        for spec in self.CATEGORY_SPECS:
            if spec[0] == value:
                return spec
        return None

    def _selected_sort(self, extend):
        data = self._parse_config(extend)
        value = str(data.get("sort") or data.get("sort_by") or "").strip()
        return value if value in self.SORT_VALUES else ""

    def _parse_play_id(self, value):
        if not value.startswith(self.PLAY_PREFIX):
            return None
        payload = value[len(self.PLAY_PREFIX) :]
        if ":" not in payload:
            return None
        mode, raw_code = payload.split(":", 1)
        if mode not in ("fast", "stable"):
            return None
        code = self._normalize_code(raw_code)
        return (mode, code) if code else None

    def _normalize_code(self, value):
        text = str(value or "").strip()
        if text.startswith("atvp_detail:"):
            text = text[len("atvp_detail:") :].strip()
        if text.startswith(self.PLAY_PREFIX):
            parsed = self._parse_play_id(text)
            return parsed[1] if parsed else ""
        if text.startswith(("http://", "https://", "/")):
            code = self._code_from_url(text)
            return code
        text = unquote(text).strip().lower()
        return text if self.CODE_RE.fullmatch(text) else ""

    def _code_from_url(self, value):
        match = self.VIDEO_LINK_RE.search(str(value or ""))
        if not match:
            return ""
        code = unquote(match.group(1)).strip().lower()
        return code if self.CODE_RE.fullmatch(code) else ""

    def _signed_url_expired(self, url):
        parts = [part for part in urlsplit(str(url or "")).path.split("/") if part]
        for index, part in enumerate(parts):
            if part.lower() != "hls":
                continue
            for candidate in parts[index + 1 : index + 4]:
                if candidate.isdigit() and len(candidate) >= 9:
                    return int(candidate) <= int(time.time()) + 5
        return False

    def _player_error_code(self, error):
        text = str(error or "").lower()
        if "signed_url_expired" in text:
            return "signed_url_expired"
        if "manifest_http_" in text or "manifest_invalid" in text:
            return "hls_manifest_failed"
        if "media_host" in text or "media_redirect" in text:
            return "media_host_unreachable"
        if "missing_hls_url" in text:
            return "hls_resolve_failed"
        return "hls_resolve_failed"

    def _paged_path(self, base_path, page):
        if page <= 1:
            return base_path
        return base_path.rstrip("/") + "/%d/" % page

    def _detail_path(self, code):
        return "/videos/%s/" % code

    def _canonical_detail_url(self, code):
        return self._absolute_url(self._detail_path(code))

    def _absolute_url(self, path):
        text = str(path or "").strip()
        if text.startswith(("http://", "https://")):
            return text
        return urljoin(self._active_host.rstrip("/") + "/", text.lstrip("/"))

    def _origin(self, url=""):
        parsed = urlsplit(str(url or self._active_host))
        return "%s://%s" % (parsed.scheme, parsed.netloc)

    def _request_urls(self, path):
        text = str(path or "").strip()
        parsed = urlsplit(text)
        if parsed.scheme and parsed.netloc:
            if not self._is_allowed_html_url(text):
                return []
            relative = parsed.path or "/"
            if parsed.query:
                relative += "?" + parsed.query
            origins = [self._origin(text)] + self._host_candidates()
        else:
            relative = "/" + text.lstrip("/")
            origins = self._host_candidates()
        output = []
        for origin in origins:
            url = urljoin(origin.rstrip("/") + "/", relative.lstrip("/"))
            if self._is_allowed_html_url(url) and url not in output:
                output.append(url)
        return output

    def _host_candidates(self):
        output = []
        for value in [self._active_host] + list(self.fallback_hosts) + [self.host]:
            text = str(value or "").strip().rstrip("/")
            parsed = urlsplit(text)
            if (
                parsed.scheme in ("http", "https")
                and parsed.hostname
                and not parsed.username
                and not parsed.password
                and text not in output
            ):
                output.append(text)
        return output

    def _html_hostnames(self):
        return {
            (urlsplit(value).hostname or "").lower()
            for value in self._host_candidates()
            if urlsplit(value).hostname
        }

    def _is_allowed_html_url(self, url):
        parsed = urlsplit(str(url or ""))
        host = (parsed.hostname or "").lower()
        return (
            parsed.scheme in ("http", "https")
            and bool(host)
            and not parsed.username
            and not parsed.password
            and host in self._html_hostnames()
            and host not in self.BLOCKED_HOSTS
        )

    def _is_allowed_image_url(self, url):
        parsed = urlsplit(str(url or ""))
        host = (parsed.hostname or "").lower()
        return (
            parsed.scheme in ("http", "https")
            and host not in self.BLOCKED_HOSTS
            and (
                host in self._html_hostnames()
                or host in self.ASSET_HOSTS
                or any(host.endswith(suffix) for suffix in self.IMAGE_HOST_SUFFIXES)
            )
        )

    def _is_allowed_media_url(self, url):
        parsed = urlsplit(str(url or ""))
        host = (parsed.hostname or "").lower()
        path = parsed.path or ""
        if (
            parsed.scheme != "https"
            or not host
            or parsed.username
            or parsed.password
            or host in self.BLOCKED_HOSTS
            or not path.lower().endswith(".m3u8")
        ):
            return False
        if host.endswith(".mushroomtrack.com") and path.startswith("/hls/"):
            return True
        return (
            host in self._html_hostnames()
            and path.startswith("/pumpres/")
            and "/hls/" in path
        )

    def _is_allowed_media_redirect(self, source_url, final_url):
        if self._is_allowed_media_url(final_url):
            return True
        if not self._is_allowed_media_url(source_url):
            return False
        source = urlsplit(str(source_url or ""))
        final = urlsplit(str(final_url or ""))
        return (
            (source.hostname or "").lower() in self._html_hostnames()
            and source.path.startswith("/pumpres/")
            and final.scheme == "https"
            and bool(final.hostname)
            and not final.username
            and not final.password
            and (final.hostname or "").lower() not in self.BLOCKED_HOSTS
            and final.path.lower().endswith(".m3u8")
        )

    def _looks_like_challenge(self, status_code, source, headers=None):
        sample = str(source or "")[:200000].lower()
        status = int(status_code or 0)
        if 200 <= status < 300 and any(
            marker in sample for marker in self.CONTENT_MARKERS
        ):
            return False
        if any(marker in sample for marker in self.CHALLENGE_MARKERS):
            return True
        server = ""
        if headers is not None:
            try:
                server = str(headers.get("Server") or "").lower()
            except Exception:
                server = ""
        return status in (403, 503) and "cloudflare" in server

    @staticmethod
    def _response_text(response):
        content = bytes(response.content or b"")
        declared = str(response.encoding or "").strip()
        normalized = declared.lower().replace("_", "-")
        if not normalized or normalized in {
            "iso-8859-1",
            "utf-32",
            "utf-32le",
            "utf-32be",
            "usc4 little endian",
            "usc4 big endian",
        }:
            chosen = "utf-8"
        else:
            chosen = declared
        try:
            return content.decode(chosen, errors="replace")
        except (LookupError, UnicodeError):
            return content.decode("utf-8", errors="replace")

    @staticmethod
    def _tree(source):
        payload = (
            source
            if isinstance(source, bytes)
            else str(source or "<html></html>").encode("utf-8", errors="replace")
        )
        parser = html.HTMLParser(encoding="utf-8", recover=True)
        return html.fromstring(payload, parser=parser)

    def _meta_content(self, tree, attr_name, attr_value):
        nodes = tree.xpath(
            '//meta[translate(@%s,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz")="%s"]/@content'
            % (attr_name, attr_value.lower())
        )
        return self._clean_text(nodes[0]) if nodes else ""

    def _first_text(self, nodes):
        for node in nodes or []:
            try:
                value = node.text_content()
            except Exception:
                value = str(node or "")
            value = self._clean_text(value)
            if value:
                return value
        return ""

    def _unique_texts(self, values):
        output = []
        seen = set()
        for value in values or []:
            text = self._clean_text(value)
            if text and text not in seen:
                seen.add(text)
                output.append(text)
        return output

    @staticmethod
    def _parse_config(extend):
        if isinstance(extend, dict):
            return dict(extend)
        text = str(extend or "").strip()
        if not text:
            return {}
        if text.startswith(("http://", "https://")):
            return {"host": text}
        try:
            value = json.loads(text)
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _parse_hosts(value):
        if isinstance(value, (list, tuple, set)):
            values = value
        else:
            values = re.split(r"[,|\s]+", str(value or ""))
        output = []
        for item in values:
            text = str(item or "").strip().rstrip("/")
            parsed = urlsplit(text)
            if (
                parsed.scheme in ("http", "https")
                and parsed.hostname
                and not parsed.username
                and not parsed.password
                and text not in output
            ):
                output.append(text)
        return output

    @staticmethod
    def _bool_value(value, default=False):
        if isinstance(value, bool):
            return value
        if value is None:
            return bool(default)
        return str(value).strip().lower() in ("1", "true", "yes", "on")

    @staticmethod
    def _bounded_int(value, default, minimum=1, maximum=999999):
        try:
            number = int(value)
        except Exception:
            number = int(default)
        return max(minimum, min(maximum, number))

    def _page_number(self, value):
        return self._bounded_int(value, 1, 1, 999999)

    @staticmethod
    def _clean_text(value):
        text = html_lib.unescape(str(value or ""))
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _empty_page(page, message=""):
        return {
            "list": [],
            "page": page,
            "pagecount": page,
            "limit": 0,
            "total": 0,
            "msg": message,
        }

    def _category_failure(self, page, message):
        result = self._empty_page(page, message)
        if not self.diagnostic_card:
            return result
        text = self._clean_text(message) or "分类读取失败"
        result["list"] = [
            {
                "vod_id": self.CATEGORY_ERROR_PREFIX + quote(text, safe=""),
                "vod_name": "Jable 分类诊断",
                "vod_pic": self.DEFAULT_PIC,
                "vod_remarks": "诊断",
                "vod_content": text,
            }
        ]
        result["limit"] = 1
        result["total"] = 1
        return result
