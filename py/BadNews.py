# -*- coding: utf-8 -*-
# //@name:BadNews直播放
# //@id:badnews_direct
# //@version:7

import hashlib
import html as html_lib
import json
import re
import time
from urllib.parse import quote, unquote, urljoin, urlsplit

import requests
from lxml import html

from base.spider import Spider as BaseSpider

try:
    from com.github.catvod import Proxy as CatVodProxy
except Exception:
    CatVodProxy = None


class Spider(BaseSpider):
    name = "BadNews直播放"
    host = "https://bad.news"
    backend_parse = False
    category_mode = False
    categoryMode = False

    PLAY_PREFIX = "badnews-play:"
    ERROR_PREFIX = "badnews-error:"
    DEFAULT_PIC = "https://bad.news/favicon.ico"

    CATEGORY_SPECS = (
        ("hot", "热门视频", "entry", "/sort-hot"),
        ("new", "最新视频", "entry", "/sort-new"),
        ("short", "短视频", "entry", "/tag/porn"),
        ("long", "长视频", "entry", "/tag/long-porn"),
        ("dm", "H动漫", "dm", "/dm"),
        ("dm_3d", "3D动画", "dm", "/dm/type/q-3D"),
        ("dm_doujin", "同人作品", "dm", "/dm/type/q-同人"),
        ("dm_cosplay", "Cosplay", "dm", "/dm/type/q-Cosplay"),
        ("better", "精选视频", "entry", "/sort-better"),
        ("score", "高分视频", "entry", "/sort-score"),
    )

    BLOCKED_HOSTS = frozenset(
        {
            "script-center.bad.news",
            "portalfluently.com",
            "vivodemisrentas.net",
            "secretlygoatsarrangement.com",
            "ri1.xlfn.cc",
            "static.cloudflareinsights.com",
            "www.google-analytics.com",
            "www.googletagmanager.com",
            "www.statcounter.com",
        }
    )
    MEDIA_HOSTS = frozenset({"video.twimg.com", "static.bad.news"})
    CHALLENGE_MARKERS = (
        "just a moment",
        "/cdn-cgi/challenge-platform",
        "_cf_chl_opt",
        "cf-turnstile",
        "turnstile",
    )
    CONTENT_MARKERS = (
        'class="entry',
        "class='entry",
        "<article",
        "<video",
        "data-source=",
        "/dm/play/id-",
    )
    VIDEO_URL_RE = re.compile(r"\.(?:m3u8|mp4)(?:$|[?#])", re.I)
    PAGE_RE = re.compile(r"/page-(\d+)(?:$|[/?#])", re.I)
    TOPIC_ID_RE = re.compile(r"/t/(\d+)(?:$|[/?#])", re.I)
    DM_ID_RE = re.compile(r"/dm/play/id-(\d+)(?:$|[/?#])", re.I)

    def __init__(self):
        try:
            super().__init__()
        except Exception:
            pass
        self.timeout = 15
        self.verify_tls = True
        self.trust_env = True
        self.proxy = ""
        self.cache_ttl = 30
        self.prefer_progressive_mp4 = True
        self.lock_hls_highest = True
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        )
        self._session = None
        self._cache = {}
        self._proxy_manifests = {}
        self._reset_session()

    def getName(self):
        return self.name

    def init(self, extend=""):
        config = self._parse_config(extend)
        configured_host = str(config.get("host") or self.host).strip().rstrip("/")
        if configured_host.startswith(("http://", "https://")):
            self.host = configured_host
        self.timeout = self._bounded_int(config.get("timeout"), self.timeout, 5, 45)
        self.cache_ttl = self._bounded_int(config.get("cache_ttl"), self.cache_ttl, 0, 300)
        self.verify_tls = self._bool_value(config.get("verify_tls"), self.verify_tls)
        self.trust_env = self._bool_value(config.get("trust_env"), self.trust_env)
        self.prefer_progressive_mp4 = self._bool_value(
            config.get("prefer_progressive_mp4", config.get("prefer_mp4")),
            self.prefer_progressive_mp4,
        )
        self.lock_hls_highest = self._bool_value(
            config.get("lock_hls_highest"), self.lock_hls_highest
        )
        self.proxy = str(config.get("proxy") or "").strip()
        configured_ua = str(config.get("user_agent") or "").strip()
        if configured_ua:
            self.user_agent = configured_ua
        self._cache.clear()
        self._proxy_manifests.clear()
        self._reset_session()

    def destroy(self):
        if self._session is not None:
            try:
                self._session.close()
            except Exception:
                pass
        self._session = None
        self._cache.clear()
        self._proxy_manifests.clear()

    def isVideoFormat(self, url):
        return bool(self.VIDEO_URL_RE.search(str(url or "")))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        data = param if isinstance(param, dict) else self._parse_config(param)
        token = str(data.get("token") or "").strip()
        cached = self._proxy_manifests.get(token)
        if not cached or time.time() - cached[0] > 1800:
            return [404, "text/plain; charset=utf-8", b"manifest not found"]
        return [
            200,
            "application/vnd.apple.mpegurl",
            cached[1],
            {"Cache-Control": "no-store", "Access-Control-Allow-Origin": "*"},
        ]

    def homeContent(self, filter):
        return {
            "class": [
                {"type_id": type_id, "type_name": type_name}
                for type_id, type_name, _, _ in self.CATEGORY_SPECS
            ],
            "filters": {},
        }

    def homeVideoContent(self):
        result = self.categoryContent("new", "1", False, {})
        return {"list": result.get("list", [])}

    def categoryContent(self, tid, pg, filter, extend):
        self._parse_config(extend)
        page = self._page_number(pg)
        spec = self._category_spec(tid)
        if spec is None:
            return self._empty_page(page, "未知分类")
        _, _, parser_kind, base_path = spec
        paths = [self._paged_path(base_path, page)]
        if str(tid) == "hot":
            paths.append("/" if page == 1 else "/page-%d" % page)

        last_error = None
        for path in paths:
            try:
                source, page_url = self._request_text(path)
                if parser_kind == "dm":
                    return self._parse_dm_page(source, page, page_url)
                return self._parse_entry_page(source, page, page_url)
            except Exception as exc:
                last_error = exc
                print("[badnews-probe] category path=%s error=%s" % (path, exc))
        return self._empty_page(page, "分类读取失败: %s" % last_error)

    def searchContent(self, key, quick, pg="1"):
        keyword = self._clean_text(key)
        page = self._page_number(pg)
        if not keyword:
            return self._empty_page(page)

        encoded = quote(keyword, safe="")
        main_path = "/search/q-%s/type-porn" % encoded
        dm_path = "/dm/search/q-%s" % encoded
        if page > 1:
            main_path += "/page-%d" % page
            dm_path += "/page-%d" % page

        items = []
        pagecount = page
        errors = []
        for parser_kind, path in (("entry", main_path), ("dm", dm_path)):
            try:
                source, page_url = self._request_text(path)
                parsed = (
                    self._parse_dm_page(source, page, page_url)
                    if parser_kind == "dm"
                    else self._parse_entry_page(source, page, page_url)
                )
                items.extend(parsed.get("list", []))
                pagecount = max(pagecount, self._page_number(parsed.get("pagecount")))
            except Exception as exc:
                errors.append(str(exc))

        deduped = []
        seen = set()
        for item in items:
            vod_id = str(item.get("vod_id") or "")
            if not vod_id or vod_id in seen:
                continue
            seen.add(vod_id)
            deduped.append(item)
        return {
            "list": deduped,
            "page": page,
            "pagecount": pagecount,
            "limit": len(deduped),
            "total": pagecount * max(len(deduped), 1),
            "msg": "; ".join(errors) if errors and not deduped else "",
        }

    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
        value = str(raw_id or "").strip()
        if value.startswith("atvp_detail:"):
            value = value[len("atvp_detail:") :].strip()
        if value.startswith(self.PLAY_PREFIX):
            value = value[len(self.PLAY_PREFIX) :].strip()
        kind, item_id = self._split_vod_id(value)
        if not kind or not item_id:
            return {"list": []}

        path = "/t/%s" % item_id if kind == "t" else "/dm/play/id-%s" % item_id
        try:
            source, page_url = self._request_text(path, fresh=(kind == "dm"))
            vod, _ = self._parse_detail_page(source, kind, item_id, page_url)
            return {"list": [vod]}
        except Exception as exc:
            return {"list": [self._detail_error(value, str(exc))]}

    def playerContent(self, flag, id, vipFlags):
        value = str(id or "").strip()
        if value.startswith(self.ERROR_PREFIX):
            return self._player_error(unquote(value[len(self.ERROR_PREFIX) :]))
        if value.startswith(("http://", "https://")):
            if not self._is_allowed_media_url(value):
                return self._player_error("播放地址域名不在媒体白名单")
            return self._player_for_media(value, self._media_type(value))
        if not value.startswith(self.PLAY_PREFIX):
            return self._player_error("无法识别播放 ID")

        kind, item_id = self._split_vod_id(value[len(self.PLAY_PREFIX) :])
        if not kind or not item_id:
            return self._player_error("播放 ID 不完整")
        path = "/t/%s" % item_id if kind == "t" else "/dm/play/id-%s" % item_id
        try:
            source, page_url = self._request_text(path, fresh=(kind == "dm"))
            _, media = self._parse_detail_page(source, kind, item_id, page_url)
            return self._player_for_media(
                media["url"], media["type"], media.get("source", "primary")
            )
        except Exception as exc:
            return self._player_error("播放地址刷新失败: %s" % exc)

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
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
                "Cache-Control": "no-cache",
            }
        )
        if self.proxy:
            session.proxies.update({"http": self.proxy, "https": self.proxy})
        self._session = session

    def _request_text(self, path, fresh=False):
        url = self._absolute_url(path)
        if not self._is_allowed_html_url(url):
            raise RuntimeError("已阻止非站点 HTML 请求")
        now = time.time()
        if not fresh and self.cache_ttl > 0:
            cached = self._cache.get(url)
            if cached and now - cached[0] <= self.cache_ttl:
                return cached[1], cached[2]

        last_error = None
        for attempt in range(2):
            try:
                response = self._session.get(
                    url,
                    timeout=(min(self.timeout, 10), self.timeout),
                    allow_redirects=True,
                    verify=self.verify_tls,
                )
                final_url = str(response.url or url)
                if not self._is_allowed_html_url(final_url):
                    raise RuntimeError("已阻止外域跳转: %s" % urlsplit(final_url).hostname)
                text = self._response_text(response)
                if self._looks_like_challenge(response.status_code, text):
                    raise RuntimeError("blocked_by_waf: 页面返回挑战或验证码")
                if response.status_code == 429 and attempt == 0:
                    retry_after = self._bounded_int(
                        response.headers.get("Retry-After"), 1, 1, 3
                    )
                    time.sleep(retry_after)
                    continue
                response.raise_for_status()
                if not fresh and self.cache_ttl > 0:
                    self._cache[url] = (time.time(), text, final_url)
                return text, final_url
            except requests.RequestException as exc:
                last_error = exc
                if attempt == 0:
                    time.sleep(0.4)
                    continue
                break
            except RuntimeError:
                raise
        raise RuntimeError("网络请求失败: %s" % last_error)

    def _parse_entry_page(self, source, page, page_url):
        tree = self._tree(source)
        items = []
        entries = tree.xpath(
            '//div[contains(concat(" ", normalize-space(@class), " "), " entry ")]'
        )
        for entry in entries:
            videos = entry.xpath('.//video[@data-source or @data-id]')
            if not videos:
                continue
            video = videos[0]
            item_id = self._digits(video.get("data-id"))
            if not item_id:
                item_id = self._first_matching_id(entry.xpath('.//a/@href'), self.TOPIC_ID_RE)
            if not item_id:
                continue
            title = self._first_text(
                entry.xpath(
                    './/h3[contains(concat(" ", normalize-space(@class), " "), " title ")]'
                    '/a[contains(concat(" ", normalize-space(@class), " "), " title ")][1]'
                )
            )
            if not title:
                title = "视频 %s" % item_id
            pic = self._absolute_media_url(
                video.get("data-poster") or video.get("poster") or "", page_url
            )
            duration = self._clean_text(
                " ".join(entry.xpath('.//*[contains(@class,"ct-time")]//text()'))
            )
            tag = self._first_text(entry.xpath('.//h4[contains(@class,"label")]'))
            media_type = str(video.get("data-type") or "").upper()
            remarks = duration or tag or media_type
            items.append(
                {
                    "vod_id": "t:%s" % item_id,
                    "vod_name": title,
                    "vod_pic": pic or self.DEFAULT_PIC,
                    "vod_remarks": remarks,
                }
            )
        return self._page_result(items, tree, page, 25)

    def _parse_dm_page(self, source, page, page_url):
        tree = self._tree(source)
        items = []
        articles = tree.xpath('//article[.//a[contains(@href,"/dm/play/id-")]]')
        for article in articles:
            title_links = article.xpath(
                './/a[contains(concat(" ", normalize-space(@class), " "), " title ")][1]'
            )
            links = title_links or article.xpath('.//a[contains(@href,"/dm/play/id-")][1]')
            if not links:
                continue
            link = links[0]
            href = str(link.get("href") or "")
            item_id = self._first_matching_id([href], self.DM_ID_RE)
            if not item_id:
                continue
            title = self._clean_text(link.get("title") or link.text_content())
            images = article.xpath('.//img[1]')
            pic = ""
            if images:
                image = images[0]
                pic = self._absolute_media_url(
                    image.get("data-echo")
                    or image.get("data-src")
                    or image.get("src")
                    or "",
                    page_url,
                )
            items.append(
                {
                    "vod_id": "dm:%s" % item_id,
                    "vod_name": title or "动漫 %s" % item_id,
                    "vod_pic": pic or self.DEFAULT_PIC,
                    "vod_remarks": "MP4",
                }
            )
        return self._page_result(items, tree, page, 30)

    def _parse_detail_page(self, source, kind, item_id, page_url):
        tree = self._tree(source)
        if kind == "t":
            videos = tree.xpath('//video[@data-id="%s"]' % item_id)
            if not videos:
                videos = tree.xpath('//video[@data-source][1]')
        else:
            videos = tree.xpath('//video[@data-source][1]')
        if not videos:
            raise RuntimeError("详情页没有 video[data-source]")
        video = videos[0]
        media_url = self._absolute_media_url(
            video.get("data-source") or video.get("src") or "", page_url
        )
        if not self._is_allowed_media_url(media_url):
            raise RuntimeError("详情媒体域名不在白名单")
        detected_type = self._media_type(media_url)
        declared_type = str(video.get("data-type") or "").lower()
        media_type = (
            detected_type
            if detected_type in ("mp4", "m3u8")
            else declared_type
        )
        media_source = "primary-%s" % media_type
        if self.prefer_progressive_mp4 and media_type == "m3u8":
            for meta_property in ("og:video:secure_url", "og:video"):
                progressive_url = self._absolute_media_url(
                    self._meta_content(tree, "property", meta_property), page_url
                )
                if (
                    self._media_type(progressive_url) == "mp4"
                    and self._is_allowed_media_url(progressive_url)
                ):
                    media_url = progressive_url
                    media_type = "mp4"
                    media_source = "target-og-progressive-mp4"
                    break
        title = self._meta_content(tree, "property", "og:title")
        if not title:
            title = self._meta_content(tree, "name", "headline")
        if not title:
            headings = tree.xpath('//h1[1] | //h2[1]')
            title = self._first_text(headings)
        if not title:
            title = ("动漫 " if kind == "dm" else "视频 ") + item_id
        pic = self._meta_content(tree, "property", "og:image")
        if not pic:
            pic = video.get("data-poster") or video.get("poster") or ""
        pic = self._absolute_media_url(pic, page_url) or self.DEFAULT_PIC
        content = self._meta_content(tree, "name", "Description")
        if not content:
            content = self._meta_content(tree, "property", "og:description")
        vod_id = "%s:%s" % (kind, item_id)
        play_target = self.PLAY_PREFIX + vod_id
        vod = {
            "vod_id": vod_id,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": media_type.upper(),
            "vod_content": content,
            "vod_play_from": "BadNews动漫" if kind == "dm" else "BadNews直连",
            "vod_play_url": "播放$%s" % play_target,
        }
        return vod, {"url": media_url, "type": media_type, "source": media_source}

    def _page_result(self, items, tree, page, default_limit):
        pagecount = page
        for href in tree.xpath('//a/@href'):
            match = self.PAGE_RE.search(str(href or ""))
            if match:
                pagecount = max(pagecount, self._page_number(match.group(1)))
        limit = len(items) or default_limit
        return {
            "list": items,
            "page": page,
            "pagecount": pagecount,
            "limit": limit,
            "total": pagecount * limit,
        }

    def _player_result(self, media_url, media_type):
        result = {
            "parse": 0,
            "jx": 0,
            "playUrl": "",
            "url": media_url,
            "header": {"User-Agent": self.user_agent},
            "type": media_type,
        }
        if media_type == "m3u8":
            result["format"] = "application/x-mpegURL"
        return result

    def _player_for_media(self, media_url, media_type, media_source="primary"):
        self._probe_log(
            "media_selected type=%s source=%s host=%s"
            % (media_type, media_source, urlsplit(media_url).hostname or "")
        )
        if media_type == "m3u8" and self.lock_hls_highest:
            try:
                locked_url = self._prepare_locked_hls(media_url)
                if locked_url:
                    self._probe_log("hls_highest_locked source=%s" % media_source)
                    return self._player_result(locked_url, "m3u8")
            except Exception as exc:
                self._probe_log("hls_lock_failed url=%s error=%s" % (media_url, exc))
                self._probe_log("hls_original_fallback source=%s" % media_source)
        return self._player_result(media_url, media_type)

    def _prepare_locked_hls(self, master_url):
        source = self._request_media_text(master_url)
        manifest = self._highest_hls_manifest(source, master_url)
        if not manifest:
            return ""
        token = hashlib.sha256(
            (master_url + "\n" + manifest).encode("utf-8")
        ).hexdigest()[:24]
        self._proxy_manifests[token] = (time.time(), manifest.encode("utf-8"))
        if len(self._proxy_manifests) > 16:
            oldest = min(self._proxy_manifests, key=lambda key: self._proxy_manifests[key][0])
            self._proxy_manifests.pop(oldest, None)
        site_key = quote(str(getattr(self, "siteKey", "") or "badnews"), safe="")
        return "%s?siteKey=%s&token=%s" % (
            self._proxy_base_url(),
            site_key,
            token,
        )

    def _request_media_text(self, url):
        if not self._is_allowed_media_url(url) or self._media_type(url) != "m3u8":
            raise RuntimeError("媒体列表地址不在白名单")
        last_error = None
        for attempt in range(3):
            try:
                response = self._session.get(
                    url,
                    headers={
                        "User-Agent": self.user_agent,
                        "Accept": "application/vnd.apple.mpegurl,application/x-mpegURL,*/*",
                    },
                    timeout=(min(self.timeout, 10), self.timeout),
                    verify=self.verify_tls,
                    allow_redirects=True,
                )
                if not 200 <= response.status_code < 300:
                    raise RuntimeError("HLS HTTP %s" % response.status_code)
                source = response.content.decode("utf-8", errors="replace")
                if "#EXTM3U" not in source:
                    raise RuntimeError("HLS 响应缺少 EXTM3U")
                return source
            except Exception as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(0.15 * (attempt + 1))
        raise RuntimeError("HLS 主列表读取失败: %s" % last_error)

    def _highest_hls_manifest(self, source, master_url):
        lines = [line.strip() for line in str(source or "").splitlines() if line.strip()]
        streams = []
        media_lines = {}
        for index, line in enumerate(lines):
            if line.startswith("#EXT-X-MEDIA:"):
                attrs = self._hls_attrs(line.split(":", 1)[1])
                if attrs.get("TYPE") == "AUDIO" and attrs.get("GROUP-ID"):
                    media_lines[attrs["GROUP-ID"]] = (line, attrs)
            elif line.startswith("#EXT-X-STREAM-INF:"):
                attrs = self._hls_attrs(line.split(":", 1)[1])
                uri = ""
                for candidate in lines[index + 1 :]:
                    if candidate.startswith("#"):
                        continue
                    uri = candidate
                    break
                if uri:
                    resolution = attrs.get("RESOLUTION", "0x0").lower().split("x")
                    try:
                        pixels = int(resolution[0]) * int(resolution[1])
                    except Exception:
                        pixels = 0
                    try:
                        bandwidth = int(attrs.get("AVERAGE-BANDWIDTH") or attrs.get("BANDWIDTH") or 0)
                    except Exception:
                        bandwidth = 0
                    streams.append((pixels, bandwidth, line, attrs, uri))
        if not streams:
            return ""
        _, _, stream_line, stream_attrs, stream_uri = max(
            streams, key=lambda item: (item[0], item[1])
        )
        audio_group = stream_attrs.get("AUDIO", "")
        output = ["#EXTM3U", "#EXT-X-VERSION:6", "#EXT-X-INDEPENDENT-SEGMENTS"]
        if audio_group in media_lines:
            audio_line, audio_attrs = media_lines[audio_group]
            audio_uri = audio_attrs.get("URI", "")
            if audio_uri:
                absolute_audio = urljoin(master_url, audio_uri)
                audio_line = re.sub(
                    r'URI=(?:"[^"]*"|[^,]*)', 'URI="%s"' % absolute_audio, audio_line
                )
            output.append(audio_line)
        output.append(stream_line)
        output.append(urljoin(master_url, stream_uri))
        return "\n".join(output) + "\n"

    @staticmethod
    def _hls_attrs(text):
        attrs = {}
        for match in re.finditer(r'([A-Z0-9-]+)=("[^"]*"|[^,]*)', str(text or "")):
            value = match.group(2).strip()
            if len(value) >= 2 and value[0] == value[-1] == '"':
                value = value[1:-1]
            attrs[match.group(1)] = value
        return attrs

    @staticmethod
    def _proxy_base_url():
        if CatVodProxy is not None:
            return str(CatVodProxy.getUrl(True))
        return "http://127.0.0.1:9978/proxy"

    def _player_error(self, message):
        text = self._clean_text(message) or "播放失败"
        return {
            "parse": 0,
            "jx": 0,
            "playUrl": "",
            "url": "",
            "header": {},
            "msg": text,
            "content": text,
            "error": text,
        }

    @staticmethod
    def _probe_log(message):
        print("[badnews-probe] %s" % message)

    def _detail_error(self, vod_id, message):
        text = self._clean_text(message) or "详情读取失败"
        return {
            "vod_id": vod_id or "error",
            "vod_name": "详情读取失败",
            "vod_pic": self.DEFAULT_PIC,
            "vod_content": text,
            "vod_play_from": "错误",
            "vod_play_url": "查看错误$%s%s" % (self.ERROR_PREFIX, quote(text, safe="")),
        }

    def _category_spec(self, tid):
        value = str(tid or "hot").strip()
        for spec in self.CATEGORY_SPECS:
            if spec[0] == value:
                return spec
        return None

    @staticmethod
    def _paged_path(base_path, page):
        if page <= 1:
            return base_path
        return base_path.rstrip("/") + "/page-%d" % page

    def _absolute_url(self, path):
        return urljoin(self.host.rstrip("/") + "/", str(path or "").lstrip("/"))

    @staticmethod
    def _absolute_media_url(value, page_url):
        text = str(value or "").strip()
        if not text:
            return ""
        return urljoin(page_url, text)

    def _is_allowed_html_url(self, url):
        parsed = urlsplit(str(url or ""))
        host = (parsed.hostname or "").lower()
        configured_host = (urlsplit(self.host).hostname or "").lower()
        return (
            parsed.scheme in ("http", "https")
            and bool(host)
            and host == configured_host
            and host not in self.BLOCKED_HOSTS
        )

    def _is_allowed_media_url(self, url):
        parsed = urlsplit(str(url or ""))
        host = (parsed.hostname or "").lower()
        return (
            parsed.scheme in ("http", "https")
            and host in self.MEDIA_HOSTS
            and host not in self.BLOCKED_HOSTS
            and self.isVideoFormat(url)
        )

    def _looks_like_challenge(self, status_code, source):
        sample = str(source or "")[:200000].lower()
        status = int(status_code or 0)
        if 200 <= status < 300 and any(
            marker in sample for marker in self.CONTENT_MARKERS
        ):
            return False
        if any(marker in sample for marker in self.CHALLENGE_MARKERS):
            return True
        return status in (403, 503) and "cloudflare" in sample

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
            text = content.decode(chosen, errors="replace")
        except (LookupError, UnicodeError):
            chosen = "utf-8"
            text = content.decode(chosen, errors="replace")
        if chosen.lower() != normalized:
            print(
                "[badnews-probe] encoding declared=%s chosen=%s bytes=%d content_type=%s"
                % (
                    declared or "none",
                    chosen,
                    len(content),
                    response.headers.get("Content-Type", ""),
                )
            )
        return text

    @staticmethod
    def _tree(source):
        if isinstance(source, bytes):
            payload = source
        else:
            payload = str(source or "<html></html>").encode("utf-8", errors="replace")
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

    def _split_vod_id(self, value):
        text = str(value or "").strip()
        if ":" not in text:
            return ("t", self._digits(text)) if self._digits(text) else ("", "")
        kind, item_id = text.split(":", 1)
        kind = kind.strip().lower()
        item_id = self._digits(item_id)
        if kind not in ("t", "dm") or not item_id:
            return "", ""
        return kind, item_id

    @staticmethod
    def _first_matching_id(values, pattern):
        for value in values or []:
            match = pattern.search(str(value or ""))
            if match:
                return match.group(1)
        return ""

    @staticmethod
    def _digits(value):
        match = re.search(r"\d+", str(value or ""))
        return match.group(0) if match else ""

    def _media_type(self, url):
        text = str(url or "").lower()
        if ".m3u8" in text:
            return "m3u8"
        if ".mp4" in text:
            return "mp4"
        return ""

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
