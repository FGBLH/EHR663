# -*- coding: utf-8 -*-
# //@name:Catemby多播放
# //@id:catemby_multi
# //@version:8

import base64
import hashlib
import ipaddress
import json
import re
import struct
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from urllib.parse import quote, unquote, urlsplit

import requests

try:
    from com.github.catvod import Proxy as CatVodProxy
except Exception:
    CatVodProxy = None

from base.spider import Spider as BaseSpider


class WafBlockedError(RuntimeError):
    pass


class Spider(BaseSpider):
    name = "Catemby多播放"
    backend_parse = False
    category_mode = False
    categoryMode = False

    API_BASE = "https://jdforrepam.com/api"
    SOURCE_BASE = "https://catembylegacy.fastcdn.dpdns.org"
    SOURCE_ORIGIN = SOURCE_BASE + "/"
    SIGNATURE_TOKEN = "lpw6vgqzsp"
    SIGNATURE_SALT = (
        "71cf27bb3c0bcdf207b64abecddc970098c7421ee7203b9cdae54478478a199e7"
        "d5a6e1a57691123c1a931c057842fb73ba3b3c83bcd69c17ccf174081e3d8aa"
    )

    PLAY_PREFIX = "catemby-play:"
    DEFAULT_PIC = SOURCE_BASE + "/favicon.ico"
    CATEGORY_SPECS = (
        ("censored", "有码", "0"),
        ("uncensored", "无码", "1"),
        ("western", "欧美", "2"),
        ("fc2", "FC2", "3"),
    )
    TYPE_BY_CATEGORY = {
        item[0]: item[2] for item in CATEGORY_SPECS if item[2] is not None
    }
    PERIODS = (
        ("日榜", "daily"),
        ("周榜", "weekly"),
        ("月榜", "monthly"),
    )
    RESOURCE_FILTERS = (
        ("全部可用", "all"),
        ("可播放", "can_play"),
        ("含磁链", "magnets"),
        ("含字幕", "subtitle"),
    )
    SORTS = (
        ("热度", "watched_count"),
        ("最新", "release"),
        ("评分", "score"),
        ("想看", "want_watch_count"),
        ("磁链", "magnets_count"),
    )
    VIDEO_EXTS = (
        ".mp4",
        ".mkv",
        ".avi",
        ".mov",
        ".wmv",
        ".flv",
        ".ts",
        ".m2ts",
        ".webm",
        ".mpg",
        ".mpeg",
        ".m4v",
    )
    CHALLENGE_MARKERS = (
        "just a moment",
        "/cdn-cgi/challenge-platform",
        "_cf_chl_opt",
        "cf-turnstile",
        "attention required",
    )

    def __init__(self):
        try:
            super().__init__()
        except Exception:
            pass
        self.timeout = 20
        self.speed_probe_timeout = 3
        self.speed_probe = True
        self.dynamic_tags = True
        self.strict_direct_cards = True
        self.direct_probe_limit = 12
        self.min_direct_minutes = 30
        self.full_probe_cache_ttl = 1800
        self.show_unplayable = False
        self.native_magnet_fallback = True
        self.verify_tls = True
        self.trust_env = True
        self.proxy = ""
        self.list_cache_ttl = 120
        self.detail_cache_ttl = 21600
        self.tag_cache_ttl = 21600
        self.resolver_cache_ttl = 300
        self.health_cache_ttl = 900
        self.image_cache_ttl = 1800
        self.max_variants = 12
        self.max_magnets = 50
        self.max_json_bytes = 2 * 1024 * 1024
        self.max_image_bytes = 4 * 1024 * 1024
        self.max_playlist_bytes = 1024 * 1024
        self.user_agent = (
            "Mozilla/5.0 (Linux; Android 10; TV) AppleWebKit/537.36 "
            "Chrome/120.0 Safari/537.36"
        )
        self.alist_api = ""
        self.alist_token = ""
        self.alist_api_key = ""
        self.alist_source = "catemby"
        self.proxy_site_key = "catemby"
        self.alist_timeout = 120
        self._session = None
        self._cache = {}
        self._health = {}
        self._playlist_cache = {}
        self._image_cache = {}
        self._media_meta_cache = {}
        self._lock = threading.RLock()
        self._reset_session()

    def getName(self):
        return self.name

    def init(self, extend=""):
        config = self._parse_dict(extend)
        self.timeout = self._bounded_int(config.get("timeout"), self.timeout, 5, 45)
        self.speed_probe_timeout = self._bounded_int(
            config.get("speed_probe_timeout"), self.speed_probe_timeout, 1, 8
        )
        self.speed_probe = self._bool(config.get("speed_probe"), self.speed_probe)
        self.dynamic_tags = self._bool(
            config.get("dynamic_tags"), self.dynamic_tags
        )
        self.strict_direct_cards = self._bool(
            config.get("strict_direct_cards"), self.strict_direct_cards
        )
        self.direct_probe_limit = self._bounded_int(
            config.get("direct_probe_limit"), self.direct_probe_limit, 4, 24
        )
        self.min_direct_minutes = self._bounded_int(
            config.get("min_direct_minutes"), self.min_direct_minutes, 1, 240
        )
        self.full_probe_cache_ttl = self._bounded_int(
            config.get("full_probe_cache_ttl"),
            self.full_probe_cache_ttl,
            60,
            86400,
        )
        self.show_unplayable = self._bool(
            config.get("show_unplayable"), self.show_unplayable
        )
        self.native_magnet_fallback = self._bool(
            config.get("native_magnet_fallback"), self.native_magnet_fallback
        )
        self.verify_tls = self._bool(config.get("verify_tls"), self.verify_tls)
        self.trust_env = self._bool(config.get("trust_env"), self.trust_env)
        self.list_cache_ttl = self._bounded_int(
            config.get("list_cache_ttl"), self.list_cache_ttl, 0, 1800
        )
        self.detail_cache_ttl = self._bounded_int(
            config.get("detail_cache_ttl"), self.detail_cache_ttl, 0, 86400
        )
        self.tag_cache_ttl = self._bounded_int(
            config.get("tag_cache_ttl"), self.tag_cache_ttl, 0, 86400
        )
        self.resolver_cache_ttl = self._bounded_int(
            config.get("resolver_cache_ttl"), self.resolver_cache_ttl, 0, 1800
        )
        self.health_cache_ttl = self._bounded_int(
            config.get("health_cache_ttl"), self.health_cache_ttl, 30, 7200
        )
        self.max_variants = self._bounded_int(
            config.get("max_variants"), self.max_variants, 1, 20
        )
        self.max_magnets = self._bounded_int(
            config.get("max_magnets"), self.max_magnets, 1, 100
        )
        self.proxy = str(config.get("proxy") or "").strip()
        user_agent = str(config.get("user_agent") or "").strip()
        if user_agent:
            self.user_agent = user_agent
        self.alist_api = str(
            config.get("alist_tvbox_api") or config.get("offline_api") or ""
        ).strip().rstrip("/")
        self.alist_token = str(
            config.get("alist_tvbox_token") or config.get("offline_token") or ""
        ).strip()
        self.alist_api_key = str(
            config.get("alist_tvbox_api_key") or config.get("offline_api_key") or ""
        ).strip()
        self.alist_source = str(
            config.get("alist_tvbox_source") or self.alist_source
        ).strip() or "catemby"
        self.proxy_site_key = str(
            config.get("proxy_site_key") or self.proxy_site_key
        ).strip() or "catemby"
        self.alist_timeout = self._bounded_int(
            config.get("alist_tvbox_timeout"), self.alist_timeout, 15, 300
        )
        with self._lock:
            self._cache.clear()
            self._health.clear()
            self._playlist_cache.clear()
            self._image_cache.clear()
            self._media_meta_cache.clear()
        self._reset_session()

    def destroy(self):
        if self._session is not None:
            try:
                self._session.close()
            except Exception:
                pass
        self._session = None
        with self._lock:
            self._cache.clear()
            self._health.clear()
            self._playlist_cache.clear()
            self._image_cache.clear()
            self._media_meta_cache.clear()

    def isVideoFormat(self, url):
        text = str(url or "").lower()
        return bool(
            re.search(r"\.(?:m3u8|mp4|mkv|webm)(?:$|[?#])", text)
            or "kind=hls" in text
        )

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        data = param if isinstance(param, dict) else self._parse_dict(param)
        kind = str(data.get("kind") or "").strip().lower()
        token = str(data.get("token") or "").strip()
        try:
            if kind == "image":
                source_url = self._unpack_text(token)
                decoded, mime = self._decoded_image(source_url)
                return [
                    200,
                    mime,
                    decoded,
                    {
                        "Cache-Control": "public, max-age=1800",
                        "Access-Control-Allow-Origin": "*",
                        "Content-Length": str(len(decoded)),
                        "X-Content-Type-Options": "nosniff",
                    },
                ]
            if kind == "hls":
                cached = self._playlist_cache_get(token)
                if cached is None:
                    return [404, "text/plain; charset=utf-8", b"playlist expired"]
                return [
                    200,
                    "application/vnd.apple.mpegurl",
                    cached,
                    {
                        "Cache-Control": "no-store",
                        "Access-Control-Allow-Origin": "*",
                    },
                ]
        except Exception as exc:
            return [
                502,
                "text/plain; charset=utf-8",
                ("proxy error: %s" % exc).encode("utf-8", errors="replace"),
            ]
        return [404, "text/plain; charset=utf-8", b"not found"]

    def homeContent(self, filter):
        classes = [
            {"type_id": item[0], "type_name": item[1]}
            for item in self.CATEGORY_SPECS
        ]
        filters = {}
        tag_map = self._load_all_tags() if self.dynamic_tags else {}
        for type_id, _, content_type in self.CATEGORY_SPECS:
            if content_type is None:
                continue
            rows = [self._filter("sort", "排序", self.SORTS)]
            tags = tag_map.get(content_type) or []
            if tags:
                values = [("全部", "")]
                for group in tags:
                    group_name = self._clean_text(
                        group.get("category") or group.get("category_id")
                    )
                    for tag in group.get("tags") or []:
                        tag_id = self._safe_filter_value(tag.get("id"))
                        tag_name = self._clean_text(tag.get("name") or tag_id)
                        if tag_id and tag_name:
                            values.append((group_name + "·" + tag_name, tag_id))
                if len(values) > 1:
                    rows.append(self._filter("tag", "标签", values[:240]))
            filters[type_id] = rows
        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        result = self.categoryContent("censored", "1", False, {})
        return {"list": result.get("list", []), "msg": result.get("msg", "")}

    def categoryContent(self, tid, pg, filter, extend):
        page = self._page(pg)
        type_id = str(tid or "").strip()
        selected = self._parse_dict(extend)
        try:
            content_type = self.TYPE_BY_CATEGORY.get(type_id)
            if content_type is None:
                return self._empty_page(page, "未知分类")
            sort_by = self._choice(
                selected.get("sort"), self.SORTS, "watched_count"
            )
            tag_id = self._safe_filter_value(selected.get("tag"))
            filter_by = (
                content_type + ":t:" + tag_id + "::::"
                if tag_id
                else content_type + ":t:::::"
            )
            data = self._api(
                "/v1/movies/tags",
                {
                    "filter_by": filter_by,
                    "sort_by": sort_by,
                    "order_by": "desc",
                    "page": page,
                    "limit": 24,
                },
                self.list_cache_ttl,
            )
            return self._page_result(
                data.get("movies") or [], page, 24, True, self.strict_direct_cards
            )
        except Exception as exc:
            return self._empty_page(page, "分类读取失败: %s" % exc)

    def searchContent(self, key, quick, pg="1"):
        keyword = self._clean_text(key)
        page = self._page(pg)
        if not keyword:
            return self._empty_page(page)
        try:
            data = self._api(
                "/v2/search",
                {"q": keyword, "page": page, "type": "movie", "limit": 24},
                self.list_cache_ttl,
            )
            return self._page_result(
                data.get("movies") or [], page, 24, True, self.strict_direct_cards
            )
        except Exception as exc:
            return self._empty_page(page, "搜索失败: %s" % exc)

    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
        movie_id = self._normalize_detail_id(raw_id)
        if not movie_id:
            return {"list": []}
        try:
            detail = self._api(
                "/v4/movies/" + quote(movie_id, safe=""),
                {},
                self.detail_cache_ttl,
            )
            movie = detail.get("movie") or {}
            if not movie:
                raise RuntimeError("详情响应缺少 movie")
        except Exception as exc:
            return {"list": [self._detail_error(movie_id, str(exc))]}

        magnets = []
        magnet_error = ""
        try:
            magnet_data = self._api(
                "/v1/movies/%s/magnets" % quote(movie_id, safe=""),
                {},
                self.detail_cache_ttl,
            )
            magnets = self._sort_magnets(magnet_data.get("magnets") or [])
        except Exception as exc:
            magnet_error = self._clean_text(exc)

        variants = []
        resolver_error = ""
        number = self._clean_text(
            movie.get("number") or movie.get("number_letter") or movie_id
        )
        if movie.get("can_play") and number:
            try:
                variants = self._full_direct_variants(
                    self._resolve_variants(number), movie.get("duration")
                )
            except Exception as exc:
                resolver_error = self._clean_text(exc)

        vod = self._build_detail_vod(
            movie_id, movie, variants, magnets, resolver_error, magnet_error
        )
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags):
        payload = self._unpack_play_id(id)
        if not payload:
            return self._player_error("invalid_play_id", "无法识别播放 ID")
        kind = str(payload.get("kind") or "")
        try:
            if kind in ("auto", "variant"):
                code = self._clean_text(payload.get("code"))
                if not code:
                    return self._player_error("missing_code", "播放 ID 缺少番号")
                variants = self._full_direct_variants(
                    self._resolve_variants(code, fresh=True),
                    payload.get("declared_duration"),
                )
                if not variants:
                    return self._player_error("resolver_empty", "解析器未返回播放变体")
                if kind == "auto":
                    mode = str(payload.get("mode") or "quality")
                    if self.speed_probe:
                        self._measure_variants(variants)
                    ordered = self._sort_variants(variants, mode)
                    healthy = [
                        item
                        for item in ordered
                        if (self._health_for_variant(item) or {}).get("ok")
                    ]
                    unknown = [
                        item
                        for item in ordered
                        if self._health_for_variant(item) is None
                    ]
                    candidates = healthy or unknown or ordered
                    selected = candidates[0] if candidates else None
                else:
                    selected = self._find_variant(variants, payload)
                    if selected and self.speed_probe:
                        self._measure_variants(variants)
                        health = self._health_for_variant(selected)
                        if health and not health.get("ok"):
                            mode = str(payload.get("mode") or "quality")
                            ordered = self._sort_variants(variants, mode)
                            healthy = [
                                item
                                for item in ordered
                                if (self._health_for_variant(item) or {}).get("ok")
                            ]
                            if healthy:
                                selected = healthy[0]
                if not selected:
                    return self._player_error("variant_missing", "目标播放变体已失效")
                return self._variant_player(selected)
            if kind == "preview":
                return self._player_error("preview_rejected", "预览视频已被完整版门禁过滤")
            if kind == "push":
                url = str(payload.get("url") or "").strip()
                if not self._is_public_http_url(url):
                    return self._player_error("push_rejected", "分享地址无效")
                return {
                    "parse": 0,
                    "jx": 0,
                    "playUrl": "",
                    "url": "push://" + url,
                    "header": {},
                }
            if kind == "magnet":
                magnet = self._normalize_magnet(payload.get("magnet"))
                if not magnet:
                    return self._player_error("magnet_invalid", "磁力哈希无效")
                return self._magnet_player(magnet)
            if kind == "error":
                return self._player_error(
                    str(payload.get("code") or "no_resources"),
                    payload.get("message") or "源站暂无可播放资源",
                )
        except WafBlockedError as exc:
            return self._player_error("blocked_by_waf", str(exc))
        except Exception as exc:
            return self._player_error("playback_failed", str(exc))
        return self._player_error("unsupported_play_kind", "不支持的播放方式")

    def _build_detail_vod(
        self, movie_id, movie, variants, magnets, resolver_error, magnet_error
    ):
        number = self._clean_text(
            movie.get("number") or movie.get("number_letter") or movie_id
        )
        title = self._clean_text(
            movie.get("title") or movie.get("origin_title") or number
        )
        display_title = (number + " " + title).strip()
        pic = self._image_proxy_url(
            movie.get("cover_url")
            or movie.get("thumb_url")
            or self._first_preview_image(movie)
            or ""
        )
        groups = []
        content = []
        declared_duration = self._number(movie.get("duration"))

        if variants:
            smart_items = [
                (
                    "画质自动",
                    self._pack_play_id(
                        {
                            "kind": "auto",
                            "code": number,
                            "mode": "quality",
                            "declared_duration": declared_duration,
                        }
                    ),
                ),
                (
                    "极速自动",
                    self._pack_play_id(
                        {
                            "kind": "auto",
                            "code": number,
                            "mode": "speed",
                            "declared_duration": declared_duration,
                        }
                    ),
                ),
            ]
            groups.append(("智能线路", smart_items))
            groups.append(
                (
                    "画质优先",
                    self._variant_entries(
                        self._sort_variants(variants, "quality"),
                        number,
                        "quality",
                        declared_duration,
                    ),
                )
            )
            groups.append(
                (
                    "极速优先",
                    self._variant_entries(
                        self._sort_variants(variants, "speed"),
                        number,
                        "speed",
                        declared_duration,
                    ),
                )
            )
        push_items = []
        magnet_items = []
        for item in magnets[: self.max_magnets]:
            label = self._magnet_label(item)
            magnet = self._normalize_magnet(item.get("hash") or item.get("magnet"))
            if magnet:
                magnet_items.append(
                    (
                        label,
                        self._pack_play_id(
                            {"kind": "magnet", "magnet": magnet, "title": label}
                        ),
                    )
                )
            push_url = str(item.get("pikpak_url") or "").strip()
            if self._is_public_http_url(push_url):
                push_items.append(
                    (
                        label,
                        self._pack_play_id({"kind": "push", "url": push_url}),
                    )
                )
        if push_items:
            groups.append(("PikPak分享", push_items))
        if magnet_items:
            groups.append(("磁力完整版", magnet_items))

        if not groups:
            no_resource_message = (
                "源站当前没有直连、磁力或预览资源；请使用客户端全局搜索番号 %s"
                % number
            )
            groups.append(
                (
                    "资源状态",
                    [
                        (
                            "暂无资源 · 搜索 " + number,
                            self._pack_play_id(
                                {
                                    "kind": "error",
                                    "code": "no_resources",
                                    "message": no_resource_message,
                                }
                            ),
                        )
                    ],
                )
            )
            content.append(no_resource_message)

        play_from = []
        play_url = []
        for group_name, entries in groups:
            valid = [(self._safe_play_name(n), value) for n, value in entries if value]
            if not valid:
                continue
            play_from.append(group_name)
            play_url.append("#".join("%s$%s" % item for item in valid))

        summary = self._clean_text(movie.get("summary"))
        if summary:
            content.append(summary)
        maker = self._clean_text(movie.get("maker_name"))
        director = self._clean_text(movie.get("director_name"))
        series = self._clean_text(movie.get("series_name"))
        metadata = " · ".join(item for item in (maker, director, series) if item)
        if metadata:
            content.append(metadata)
        if resolver_error:
            content.append("直连解析暂不可用: " + resolver_error)
        if magnet_error:
            content.append("磁力列表暂不可用: " + magnet_error)
        tags = [
            self._clean_text(item.get("name") if isinstance(item, dict) else item)
            for item in movie.get("tags") or []
        ]
        actors = [
            self._clean_text(item.get("name") if isinstance(item, dict) else item)
            for item in movie.get("actors") or []
        ]
        duration = self._duration(movie.get("duration"))
        score = self._number(movie.get("score"))
        remarks = []
        if variants:
            remarks.append("完整版直连")
        if magnets:
            remarks.append("磁力%d" % len(magnets))
        if movie.get("has_cnsub") or self._number(movie.get("play_subtitle")) > 0:
            remarks.append("中字")
        return {
            "vod_id": movie_id,
            "vod_name": display_title,
            "vod_pic": pic or self.DEFAULT_PIC,
            "vod_remarks": " · ".join(remarks) or number,
            "vod_content": "\n".join(content),
            "vod_actor": ", ".join(item for item in actors if item),
            "vod_class": ", ".join(item for item in tags if item),
            "vod_director": director,
            "vod_year": str(movie.get("release_date") or "")[:4],
            "vod_area": self._area_name(movie.get("type")),
            "vod_duration": duration,
            "vod_score": score,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }

    def _variant_entries(self, variants, code, mode, declared_duration=0):
        entries = []
        for variant in variants[: self.max_variants]:
            payload = {
                "kind": "variant",
                "code": code,
                "fingerprint": variant.get("fingerprint"),
                "index": variant.get("index"),
                "variant": variant.get("variant"),
                "transport": variant.get("transport"),
                "mode": mode,
                "declared_duration": self._number(declared_duration),
            }
            entries.append((self._variant_label(variant), self._pack_play_id(payload)))
        return entries

    def _resolve_variants(self, code, fresh=False, isolated=False):
        cache_key = "resolver:" + code
        cached = self._cache_get(cache_key)
        if not fresh and cached is not None:
            return cached
        errors = []
        client = self._new_session() if isolated else None
        for resolver_code in self._resolver_code_candidates(code):
            url = (
                self.SOURCE_BASE
                + "/api/v/resolve?code="
                + quote(resolver_code, safe="")
                + "&lang=zh"
            )
            try:
                body = self._request_json_url(
                    url,
                    {
                        "Accept": "application/json",
                        "Referer": self.SOURCE_ORIGIN,
                        "User-Agent": self.user_agent,
                    },
                    self.max_json_bytes,
                    session=client,
                )
            except Exception as exc:
                errors.append("%s: %s" % (resolver_code, self._clean_text(exc)))
                continue
            raw_variants = body.get("variants")
            if raw_variants is None and isinstance(body.get("data"), dict):
                raw_variants = body["data"].get("variants")
            if raw_variants is None and isinstance(body.get("result"), dict):
                raw_variants = body["result"].get("variants")
            variants = []
            for index, item in enumerate(raw_variants or []):
                normalized = self._normalize_variant(item, index)
                if normalized:
                    normalized["resolver_code"] = resolver_code
                    variants.append(normalized)
            variants = variants[: self.max_variants]
            if variants:
                self._cache_set(cache_key, variants, self.resolver_cache_ttl)
                if client is not None:
                    client.close()
                return variants
            errors.append(resolver_code + ": empty_variants")

        usable = self._usable_cached_variants(cached)
        if client is not None:
            client.close()
        if usable:
            return usable
        if errors:
            raise RuntimeError("解析器候选均失败: " + " | ".join(errors))
        return []

    def _full_direct_variants(self, variants, declared_duration=0):
        candidates = [
            item
            for item in variants or []
            if item.get("transport") == "progressive"
            and self._is_public_http_url(item.get("url"))
        ]
        if not candidates:
            return []
        accepted = []
        with ThreadPoolExecutor(max_workers=min(4, len(candidates))) as executor:
            jobs = {
                executor.submit(self._probe_full_progressive, item): item
                for item in candidates
            }
            for future in as_completed(jobs):
                item = jobs[future]
                try:
                    meta = future.result()
                except Exception:
                    continue
                if not meta.get("ok"):
                    continue
                enriched = dict(item)
                enriched["duration_seconds"] = meta.get("duration_seconds")
                enriched["bytes_total"] = meta.get("bytes_total")
                enriched["full_probe"] = meta
                accepted.append(enriched)
        order = {item.get("fingerprint"): index for index, item in enumerate(candidates)}
        accepted.sort(key=lambda item: order.get(item.get("fingerprint"), 9999))
        return accepted

    def _probe_full_progressive(self, variant):
        url = str(variant.get("url") or "").strip()
        if not self._is_public_http_url(url):
            return {"ok": False, "reason": "invalid_url"}
        cache_key = hashlib.sha256(url.encode("utf-8")).hexdigest()
        now = time.time()
        with self._lock:
            cached = self._media_meta_cache.get(cache_key)
            if cached and now - cached[0] <= self.full_probe_cache_ttl:
                return dict(cached[1])

        client = self._new_session()
        response = None
        result = {"ok": False, "reason": "probe_failed"}
        try:
            headers = self._media_headers(variant.get("page_url"))
            head_headers = dict(headers)
            head_headers["Range"] = "bytes=0-131071"
            response = client.get(
                url,
                headers=head_headers,
                timeout=(self.speed_probe_timeout, max(self.speed_probe_timeout, 8)),
                allow_redirects=True,
                verify=self.verify_tls,
                stream=True,
            )
            final_url = str(response.url or url)
            if not self._is_public_http_url(final_url):
                raise RuntimeError("媒体跳转到非公网地址")
            content_type = str(response.headers.get("Content-Type") or "").lower()
            head = self._read_prefix(response, 131072)
            status = int(response.status_code)
            total = self._response_total_bytes(response.headers, len(head))
            duration = self._mp4_duration_seconds(head)
            has_ftyp = b"ftyp" in head[:64]
            if (
                duration is None
                and total > 1048576
                and 200 <= status < 400
                and "image/" not in content_type
            ):
                response.close()
                response = None
                tail_headers = dict(headers)
                tail_headers["Range"] = "bytes=%d-%d" % (
                    max(0, total - 1048576),
                    total - 1,
                )
                response = client.get(
                    final_url,
                    headers=tail_headers,
                    timeout=(self.speed_probe_timeout, max(self.speed_probe_timeout, 8)),
                    allow_redirects=True,
                    verify=self.verify_tls,
                    stream=True,
                )
                tail_url = str(response.url or final_url)
                if not self._is_public_http_url(tail_url):
                    raise RuntimeError("媒体尾部跳转到非公网地址")
                duration = self._mp4_duration_seconds(
                    self._read_prefix(response, 1048576)
                )
            minimum = float(self.min_direct_minutes * 60)
            result = {
                "ok": bool(
                    200 <= status < 400
                    and has_ftyp
                    and not content_type.startswith(("image/", "text/html"))
                    and duration is not None
                    and duration >= minimum
                ),
                "status": status,
                "content_type": content_type,
                "bytes_total": total,
                "duration_seconds": duration,
                "duration_minutes": round(duration / 60.0, 2) if duration else 0,
                "minimum_minutes": self.min_direct_minutes,
                "has_ftyp": has_ftyp,
            }
            if duration is None:
                result["reason"] = "duration_unknown"
            elif duration < minimum:
                result["reason"] = "preview_too_short"
            elif not has_ftyp:
                result["reason"] = "not_mp4"
        except Exception as exc:
            result = {"ok": False, "reason": self._clean_text(exc) or "probe_failed"}
        finally:
            if response is not None:
                response.close()
            client.close()
        with self._lock:
            self._media_meta_cache[cache_key] = (time.time(), dict(result))
            self._trim_timed_cache(self._media_meta_cache, 128)
        return result

    @staticmethod
    def _read_prefix(response, maximum):
        body = bytearray()
        for chunk in response.iter_content(16384):
            if not chunk:
                continue
            remaining = maximum - len(body)
            if remaining <= 0:
                break
            body.extend(chunk[:remaining])
            if len(body) >= maximum:
                break
        return bytes(body)

    @staticmethod
    def _response_total_bytes(headers, fallback=0):
        content_range = str(headers.get("Content-Range") or "")
        match = re.search(r"/([0-9]+)$", content_range)
        if match:
            return int(match.group(1))
        try:
            return int(headers.get("Content-Length") or fallback or 0)
        except (TypeError, ValueError):
            return int(fallback or 0)

    @staticmethod
    def _mp4_duration_seconds(raw):
        body = raw or b""
        offset = 0
        while True:
            marker = body.find(b"mvhd", offset)
            if marker < 0:
                return None
            start = marker + 4
            if start + 20 > len(body):
                return None
            version = body[start]
            try:
                if version == 0:
                    timescale = struct.unpack(">I", body[start + 12 : start + 16])[0]
                    duration = struct.unpack(">I", body[start + 16 : start + 20])[0]
                elif version == 1 and start + 32 <= len(body):
                    timescale = struct.unpack(">I", body[start + 20 : start + 24])[0]
                    duration = struct.unpack(">Q", body[start + 24 : start + 32])[0]
                else:
                    offset = marker + 4
                    continue
            except struct.error:
                return None
            if timescale and duration:
                return float(duration) / float(timescale)
            offset = marker + 4

    @staticmethod
    def _resolver_code_candidates(code):
        value = re.sub(r"\s+", "", str(code or "")).upper()
        candidates = []
        match = re.match(r"^FC2[-_]?([0-9]{5,})$", value)
        if match:
            candidates.append("FC2PPV-" + match.group(1))
        candidates.append(str(code or "").strip())
        result = []
        for item in candidates:
            if item and item not in result:
                result.append(item)
        return result

    @staticmethod
    def _usable_cached_variants(cached):
        now = time.time() + 5
        return [
            item
            for item in cached or []
            if not item.get("expires_at") or item.get("expires_at") > now
        ]

    def _normalize_variant(self, raw, index):
        if not isinstance(raw, dict):
            return None
        url = str(
            raw.get("sourceUrl")
            or raw.get("source_url")
            or raw.get("playUrl")
            or raw.get("url")
            or ""
        ).strip()
        is_data_hls = url.lower().startswith(
            "data:application/vnd.apple.mpegurl"
        )
        if not is_data_hls and not self._is_public_http_url(url):
            return None
        source_type = self._clean_text(raw.get("sourceType")).lower()
        variant_name = self._clean_text(raw.get("variant")).lower()
        quality = self._clean_text(raw.get("quality"))
        label = self._clean_text(raw.get("label") or variant_name or "线路")
        transport = "hls" if is_data_hls or "mpegurl" in source_type else "progressive"
        container = "mp4" if "mp4" in source_type or re.search(r"\.mp4(?:$|[?#])", url, re.I) else ("hls" if transport == "hls" else "unknown")
        height = self._quality_height(quality + " " + label)
        bitrate = self._number(raw.get("bitrate"))
        expires_at = self._expiry_epoch(raw.get("expiresAt") or raw.get("expires_at"))
        if expires_at and expires_at <= time.time() + 5:
            return None
        fingerprint_source = "|".join(
            (variant_name, label, source_type, quality, str(index))
        )
        fingerprint = hashlib.sha256(
            fingerprint_source.encode("utf-8")
        ).hexdigest()[:16]
        return {
            "url": url,
            "source_type": source_type,
            "variant": variant_name,
            "quality": quality,
            "label": label,
            "transport": transport,
            "container": container,
            "height": height,
            "bitrate": bitrate,
            "expires_at": expires_at,
            "page_url": str(raw.get("pageUrl") or raw.get("page_url") or ""),
            "index": index,
            "fingerprint": fingerprint,
        }

    def _sort_variants(self, variants, mode):
        if mode == "speed":
            return sorted(variants, key=self._speed_sort_key)
        return sorted(variants, key=self._quality_sort_key)

    def _quality_sort_key(self, item):
        name = str(item.get("variant") or "").lower()
        original = 2 if name == "original" else (1 if "original" in name else 0)
        transport = 1 if item.get("container") == "mp4" else 0
        return (
            -original,
            -int(item.get("height") or 0),
            -int(item.get("bitrate") or 0),
            -transport,
            int(item.get("index") or 0),
        )

    def _speed_sort_key(self, item):
        health = self._health_for_variant(item)
        state = 0 if health and health.get("ok") else (1 if not health else 2)
        rtt = int(health.get("rtt_ms") or 999999) if health else 999999
        transport = 0 if item.get("container") == "mp4" else 1
        return (
            state,
            rtt,
            transport,
            int(item.get("index") or 0),
        )

    def _measure_variants(self, variants):
        targets = []
        seen = set()
        for item in variants:
            target = self._probe_target(item)
            if not target:
                continue
            key = self._health_key(item, target)
            if key in seen or self._health_get(key) is not None:
                continue
            seen.add(key)
            targets.append((item, target, key))
            if len(targets) >= 4:
                break
        if not targets:
            return
        with ThreadPoolExecutor(max_workers=min(4, len(targets))) as executor:
            jobs = {
                executor.submit(self._probe_media_target, item, target): key
                for item, target, key in targets
            }
            for future in as_completed(jobs):
                key = jobs[future]
                try:
                    result = future.result()
                except Exception:
                    result = {
                        "ok": False,
                        "rtt_ms": 999999,
                        "checked_at": time.time(),
                    }
                self._health_set(key, result)

    def _probe_media_target(self, item, target):
        started = time.monotonic()
        result = {"ok": False, "rtt_ms": 999999, "checked_at": time.time()}
        client = self._new_session()
        response = None
        try:
            headers = self._media_headers(item.get("page_url"))
            if item.get("transport") == "hls":
                range_headers = dict(headers)
                range_headers["Range"] = "bytes=0-1503"
                response = client.get(
                    target,
                    headers=range_headers,
                    timeout=(self.speed_probe_timeout, self.speed_probe_timeout),
                    allow_redirects=True,
                    verify=self.verify_tls,
                    stream=True,
                )
                final_url = str(response.url or target)
                if not self._is_public_http_url(final_url):
                    raise RuntimeError("HLS 分片探测跳转到非公网地址")
                prefix = b""
                for chunk in response.iter_content(512):
                    if chunk:
                        prefix += chunk
                    if len(prefix) >= 1504:
                        prefix = prefix[:1504]
                        break
                content_type = str(response.headers.get("Content-Type") or "")
                segment_kind = self._hls_segment_kind(prefix, content_type)
                result.update(
                    {
                        "method": "GET_RANGE_HLS",
                        "rtt_ms": int((time.monotonic() - started) * 1000),
                        "ok": 200 <= response.status_code < 400 and bool(segment_kind),
                        "status": int(response.status_code),
                        "content_type": content_type,
                        "segment_kind": segment_kind,
                    }
                )
                return result
            response = client.head(
                target,
                headers=headers,
                timeout=(self.speed_probe_timeout, self.speed_probe_timeout),
                allow_redirects=True,
                verify=self.verify_tls,
            )
            if response.status_code in (400, 403, 405, 501):
                response.close()
                response = None
                range_headers = dict(headers)
                range_headers["Range"] = "bytes=0-0"
                response = client.get(
                    target,
                    headers=range_headers,
                    timeout=(self.speed_probe_timeout, self.speed_probe_timeout),
                    allow_redirects=True,
                    verify=self.verify_tls,
                    stream=True,
                )
                result["method"] = "GET_RANGE"
            else:
                result["method"] = "HEAD"
            final_url = str(response.url or target)
            if not self._is_public_http_url(final_url):
                raise RuntimeError("媒体探测跳转到非公网地址")
            result["rtt_ms"] = int((time.monotonic() - started) * 1000)
            result["ok"] = 200 <= response.status_code < 400
            result["status"] = int(response.status_code)
            result["accept_ranges"] = str(
                response.headers.get("Accept-Ranges") or ""
            )
        except Exception:
            result["rtt_ms"] = int((time.monotonic() - started) * 1000)
        finally:
            if response is not None:
                response.close()
            client.close()
        return result

    @staticmethod
    def _hls_segment_kind(raw, content_type=""):
        body = raw or b""
        mime = str(content_type or "").lower()
        if not body or mime.startswith("image/"):
            return ""
        if body.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF87a", b"GIF89a")):
            return ""
        maximum = min(188, len(body))
        for offset in range(maximum):
            if offset + 376 < len(body):
                if (
                    body[offset] == 0x47
                    and body[offset + 188] == 0x47
                    and body[offset + 376] == 0x47
                ):
                    return "mpeg-ts"
        if any(marker in body[:64] for marker in (b"ftyp", b"styp", b"moof")):
            return "fmp4"
        return ""

    def _probe_target(self, variant):
        url = str(variant.get("url") or "")
        if self._is_public_http_url(url):
            return url
        if variant.get("transport") == "hls":
            try:
                playlist = self._decode_data_playlist(url).decode("utf-8")
                for line in playlist.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and self._is_public_http_url(line):
                        return line
            except Exception:
                return ""
        return ""

    def _health_for_variant(self, variant):
        target = self._probe_target(variant)
        if not target:
            return None
        return self._health_get(self._health_key(variant, target))

    def _health_key(self, variant, target):
        return "%s:%s" % (
            variant.get("transport") or "unknown",
            (urlsplit(target).hostname or "").lower(),
        )

    def _find_variant(self, variants, payload):
        fingerprint = str(payload.get("fingerprint") or "")
        for item in variants:
            if fingerprint and item.get("fingerprint") == fingerprint:
                return item
        variant_name = str(payload.get("variant") or "")
        transport = str(payload.get("transport") or "")
        if variant_name:
            for item in variants:
                if item.get("variant") != variant_name:
                    continue
                if transport and item.get("transport") != transport:
                    continue
                return item
        index = self._bounded_int(payload.get("index"), -1, -1, 1000)
        for item in variants:
            if item.get("index") == index:
                return item
        return None

    def _variant_player(self, variant):
        url = str(variant.get("url") or "")
        referer = str(variant.get("page_url") or self.SOURCE_ORIGIN)
        if variant.get("transport") == "hls" and url.lower().startswith("data:"):
            playlist = self._decode_data_playlist(url)
            token = hashlib.sha256(playlist).hexdigest()[:24]
            with self._lock:
                self._playlist_cache[token] = (time.time(), playlist)
                self._trim_timed_cache(self._playlist_cache, 16)
            proxy_url = self._local_proxy_url("hls", token)
            return self._direct_player(proxy_url, "m3u8", referer)
        if not self._is_public_http_url(url):
            return self._player_error("media_rejected", "媒体地址无效")
        media_type = "m3u8" if variant.get("transport") == "hls" else "mp4"
        return self._direct_player(url, media_type, referer)

    def _direct_player(self, url, media_type, referer):
        result = {
            "parse": 0,
            "jx": 0,
            "playUrl": "",
            "url": url,
            "header": self._media_headers(referer),
            "type": media_type,
        }
        if media_type == "m3u8":
            result["format"] = "application/x-mpegURL"
        return result

    def _media_headers(self, referer=""):
        value = str(referer or self.SOURCE_ORIGIN).strip()
        if not self._is_public_http_url(value):
            value = self.SOURCE_ORIGIN
        return {
            "User-Agent": self.user_agent,
            "Referer": value,
            "Origin": self._origin(value),
        }

    def _sort_magnets(self, raw_items):
        items = []
        seen = set()
        for index, raw in enumerate(raw_items or []):
            if not isinstance(raw, dict):
                continue
            magnet = self._normalize_magnet(raw.get("hash") or raw.get("magnet"))
            btih = self._extract_btih(magnet)
            if not btih or btih in seen:
                continue
            seen.add(btih)
            item = dict(raw)
            name = self._clean_text(item.get("name"))
            item["magnet"] = magnet
            item["is_subtitle"] = bool(item.get("cnsub")) or self._has_subtitle(name)
            item["is_hd"] = bool(item.get("hd")) or self._has_hd(name)
            item["size_value"] = self._number(item.get("size"))
            item["date_value"] = self._date_value(item.get("created_at"))
            item["files_value"] = int(self._number(item.get("files_count")))
            item["source_index"] = index
            items.append(item)
        return sorted(
            items,
            key=lambda item: (
                0 if item.get("is_subtitle") else 1,
                0 if item.get("is_hd") else 1,
                -float(item.get("size_value") or 0),
                -int(item.get("date_value") or 0),
                -int(item.get("files_value") or 0),
                int(item.get("source_index") or 0),
            ),
        )

    def _magnet_label(self, item):
        flags = []
        if item.get("is_subtitle"):
            flags.append("中字")
        if item.get("is_hd"):
            flags.append("HD")
        size = self._format_source_size(item.get("size_value"))
        date = self._clean_text(item.get("created_at"))
        files = int(item.get("files_value") or 0)
        meta = [item for item in (size, date, "%d文件" % files if files else "") if item]
        name = self._clean_text(item.get("name")) or "磁力资源"
        prefix = " ".join("[%s]" % item for item in flags)
        return " | ".join(item for item in (prefix, " · ".join(meta), name) if item)

    def _magnet_player(self, magnet):
        if not self.alist_api or not self.alist_token:
            if self.native_magnet_fallback:
                return {
                    "parse": 0,
                    "jx": 0,
                    "playUrl": "",
                    "url": "push://" + magnet,
                    "header": {},
                }
            return self._player_error(
                "magnet_offline_not_configured",
                "磁力已收录；客户端原生磁力兜底已关闭，且未配置 AList 离线服务",
            )
        endpoint = self.alist_api + "/offline_download/" + quote(
            self.alist_token, safe=""
        )
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.alist_api_key:
            headers["X-API-KEY"] = self.alist_api_key
        response = self._session.post(
            endpoint,
            params={"ac": "gui"},
            json={"url": magnet, "type": "magnet", "source": self.alist_source},
            headers=headers,
            timeout=(10, self.alist_timeout),
            verify=self.verify_tls,
        )
        try:
            body = response.json()
        except Exception:
            body = {}
        if response.status_code >= 400:
            detail = self._clean_text(
                body.get("detail") or body.get("message") or response.text
            )
            return self._player_error("offline_http_%d" % response.status_code, detail)
        items = self._offline_video_items(body)
        if not items:
            detail = self._clean_text(
                body.get("detail") or body.get("message") or "离线任务尚未返回视频文件"
            )
            return self._player_error("offline_pending", detail)
        chosen = items[0]
        return {
            "parse": 0,
            "jx": 0,
            "playUrl": "",
            "url": chosen.get("url") or "",
            "header": chosen.get("header") if isinstance(chosen.get("header"), dict) else {},
        }

    def _offline_video_items(self, body):
        items = []
        seen = set()
        for group in body.get("list") or []:
            if not isinstance(group, dict):
                continue
            for raw in group.get("items") or []:
                if not isinstance(raw, dict):
                    continue
                url = str(raw.get("url") or "").strip()
                if not self._is_public_http_url(url) or url in seen:
                    continue
                name = self._clean_text(
                    raw.get("title") or raw.get("name") or raw.get("path")
                )
                low = name.lower()
                if name and not any(ext in low for ext in self.VIDEO_EXTS):
                    continue
                seen.add(url)
                bad = bool(
                    re.search(
                        r"sample|preview|trailer|广告|廣告|预告|預告|样片|樣片|试看|試看",
                        name,
                        re.I,
                    )
                )
                items.append(
                    {
                        "url": url,
                        "name": name,
                        "size": self._number(raw.get("size")),
                        "subtitle": self._has_subtitle(name),
                        "bad": bad,
                        "header": raw.get("header") or {},
                    }
                )
        return sorted(
            items,
            key=lambda item: (
                0 if item.get("subtitle") else 1,
                1 if item.get("bad") else 0,
                -float(item.get("size") or 0),
                item.get("name") or "",
            ),
        )

    def _api(self, path, query, ttl, isolated=False):
        url = self.API_BASE.rstrip("/") + "/" + str(path or "").lstrip("/")
        pairs = []
        for key in sorted((query or {}).keys()):
            value = query.get(key)
            if value is None or value == "":
                continue
            pairs.append("%s=%s" % (quote(str(key), safe=""), quote(str(value), safe="")))
        if pairs:
            url += "?" + "&".join(pairs)
        cache_key = "api:" + url
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        headers = {
            "Accept": "application/json",
            "jdsignature": self._signature(),
            "Referer": self.SOURCE_ORIGIN,
        }
        client = self._new_session() if isolated else self._session
        try:
            body = self._request_json_url(
                url, headers, self.max_json_bytes, session=client
            )
        finally:
            if isolated:
                client.close()
        if body.get("success") != 1:
            raise RuntimeError(self._clean_text(body.get("message")) or "API 返回失败")
        data = body.get("data") or {}
        self._cache_set(cache_key, data, ttl)
        return data

    def _request_json_url(self, url, headers, max_bytes, session=None):
        if not self._is_public_http_url(url):
            raise RuntimeError("已阻止非公网请求")
        client = session or self._session
        last_error = None
        for attempt in range(2):
            response = None
            try:
                response = client.get(
                    url,
                    headers=headers,
                    timeout=(min(self.timeout, 10), self.timeout),
                    allow_redirects=True,
                    verify=self.verify_tls,
                    stream=True,
                )
                final_url = str(response.url or url)
                if not self._is_public_http_url(final_url):
                    raise RuntimeError("已阻止外域私网跳转")
                raw = self._read_bounded(response, max_bytes)
                text = raw.decode("utf-8", errors="replace")
                if self._looks_like_challenge(response.status_code, text):
                    raise WafBlockedError(
                        "Cloudflare 挑战需要可见浏览器或站点授权接口"
                    )
                if response.status_code == 429:
                    raise RuntimeError("rate_limited")
                if response.status_code >= 500 and attempt == 0:
                    time.sleep(0.2)
                    continue
                response.raise_for_status()
                parsed = json.loads(text)
                if not isinstance(parsed, dict):
                    raise RuntimeError("JSON 顶层不是对象")
                return parsed
            except WafBlockedError:
                raise
            except (requests.RequestException, ValueError, RuntimeError) as exc:
                last_error = exc
                if attempt == 0 and "rate_limited" not in str(exc):
                    time.sleep(0.15)
                    continue
            finally:
                if response is not None:
                    response.close()
        raise RuntimeError("网络请求失败: %s" % last_error)

    def _load_all_tags(self):
        cached = self._cache_get("all-tags")
        if cached is not None:
            return cached
        result = {}
        with ThreadPoolExecutor(max_workers=4) as executor:
            jobs = {
                executor.submit(
                    self._api, "/v1/tags", {"type": content_type}, self.tag_cache_ttl, True
                ): content_type
                for content_type in ("0", "1", "2", "3")
            }
            for future in as_completed(jobs):
                content_type = jobs[future]
                try:
                    result[content_type] = future.result().get("tags") or []
                except Exception:
                    result[content_type] = []
        self._cache_set("all-tags", result, self.tag_cache_ttl)
        return result

    def _page_result(
        self, raw_movies, page, expected_limit, pageable, direct_check=False
    ):
        items = []
        seen = set()
        raw_movies = raw_movies or []
        source_count = len(raw_movies)
        if direct_check:
            raw_movies = self._filter_direct_movies(raw_movies)
        for raw in raw_movies:
            if not isinstance(raw, dict):
                continue
            movie_id = self._clean_text(raw.get("id"))
            if not movie_id or movie_id in seen:
                continue
            if not self.show_unplayable and not self._has_declared_resource(raw):
                continue
            seen.add(movie_id)
            items.append(self._movie_card(raw))
        pagecount = (
            page + 1
            if pageable and source_count >= expected_limit
            else page
        )
        if not pageable:
            pagecount = 1
            page = 1
        limit = expected_limit or len(items) or 1
        return {
            "list": items,
            "page": page,
            "pagecount": pagecount,
            "limit": limit,
            "total": pagecount * limit,
        }

    def _filter_direct_movies(self, raw_movies):
        rows = [item for item in raw_movies if isinstance(item, dict)]
        if not rows:
            return []
        accepted = {}
        candidates = []
        for item in rows:
            movie_id = self._clean_text(item.get("id"))
            if not movie_id:
                continue
            if self._number(item.get("magnets_count")) > 0:
                kept = dict(item)
                kept["_resource_gate"] = "magnet"
                accepted[movie_id] = kept
            elif len(candidates) < self.direct_probe_limit:
                candidates.append(item)
        if not candidates:
            return [accepted[mid] for mid in [self._clean_text(x.get("id")) for x in rows] if mid in accepted]
        with ThreadPoolExecutor(max_workers=min(4, len(candidates))) as executor:
            jobs = {
                executor.submit(self._raw_has_progressive_direct, item): self._clean_text(
                    item.get("id")
                )
                for item in candidates
            }
            for future in as_completed(jobs):
                movie_id = jobs[future]
                try:
                    if movie_id and future.result():
                        kept = next(
                            item
                            for item in candidates
                            if self._clean_text(item.get("id")) == movie_id
                        )
                        kept = dict(kept)
                        kept["_resource_gate"] = "full_direct"
                        kept["_full_direct_verified"] = True
                        accepted[movie_id] = kept
                except Exception:
                    pass
        return [
            accepted[mid]
            for mid in [self._clean_text(item.get("id")) for item in rows]
            if mid in accepted
        ]

    def _raw_has_progressive_direct(self, raw):
        if not raw.get("can_play"):
            return False
        code = self._clean_text(
            raw.get("number") or raw.get("number_letter") or raw.get("id")
        )
        if not code:
            return False
        variants = self._resolve_variants(code, isolated=True)
        return bool(self._full_direct_variants(variants, raw.get("duration")))

    def _movie_card(self, raw):
        movie_id = self._clean_text(raw.get("id"))
        number = self._clean_text(
            raw.get("number") or raw.get("number_letter") or movie_id
        )
        title = self._clean_text(
            raw.get("title") or raw.get("origin_title") or number
        )
        remarks = []
        if raw.get("_full_direct_verified"):
            remarks.append("完整版直连")
        magnets = int(self._number(raw.get("magnets_count")))
        if magnets:
            remarks.append("磁力%d" % magnets)
        if raw.get("has_cnsub") or self._number(raw.get("play_subtitle")) > 0:
            remarks.append("中字")
        if not self._has_declared_resource(raw):
            remarks.append("无资源")
        score = self._number(raw.get("score"))
        if score:
            remarks.append("%.1f分" % score)
        return {
            "vod_id": movie_id,
            "vod_name": (number + " " + title).strip(),
            "vod_pic": self._image_proxy_url(
                raw.get("thumb_url")
                or raw.get("cover_url")
                or self._first_preview_image(raw)
                or ""
            )
            or self.DEFAULT_PIC,
            "vod_remarks": " · ".join(remarks) or self._duration(raw.get("duration")),
        }

    @staticmethod
    def _has_declared_resource(raw):
        if not isinstance(raw, dict):
            return False
        magnets_count = Spider._number(raw.get("magnets_count"))
        return bool(
            raw.get("can_play")
            or raw.get("has_preview_video")
            or raw.get("preview_video_url")
            or raw.get("play_sources")
            or magnets_count > 0
        )

    @staticmethod
    def _first_preview_image(raw):
        if not isinstance(raw, dict):
            return ""
        for item in raw.get("preview_images") or []:
            if isinstance(item, dict):
                value = item.get("large_url") or item.get("thumb_url") or item.get("url")
            else:
                value = item
            value = str(value or "").strip()
            if value:
                return value
        return ""

    def _decoded_image(self, url):
        if not self._is_public_http_url(url):
            raise RuntimeError("图片地址无效")
        key = hashlib.sha256(url.encode("utf-8")).hexdigest()
        with self._lock:
            cached = self._image_cache.get(key)
            if cached and time.time() - cached[0] <= self.image_cache_ttl:
                return cached[1], cached[2]
        response = self._session.get(
            url,
            headers={
                "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                "Referer": self.SOURCE_ORIGIN,
                "User-Agent": self.user_agent,
            },
            timeout=(min(self.timeout, 10), self.timeout),
            allow_redirects=True,
            verify=self.verify_tls,
            stream=True,
        )
        try:
            if not 200 <= response.status_code < 300:
                raise RuntimeError("图片 HTTP %d" % response.status_code)
            raw = self._read_bounded(response, self.max_image_bytes)
        finally:
            response.close()
        decoded, mime = self._decode_image_bytes(raw)
        with self._lock:
            self._image_cache[key] = (time.time(), decoded, mime)
            self._trim_timed_cache(self._image_cache, 32)
        return decoded, mime

    def _decode_image_bytes(self, raw):
        mime = self._image_mime(raw)
        if mime:
            return raw, mime
        candidates = []
        if raw:
            key = raw[0]
            candidates.append(bytes(value ^ key for value in raw[1:]))
        for skip in (0, 1, 2):
            if len(raw) > skip:
                candidates.append(bytes(value ^ 0x7F for value in raw[skip:]))
        for candidate in candidates:
            mime = self._image_mime(candidate)
            if mime:
                return candidate, mime
        raise RuntimeError("未知图片编码")

    @staticmethod
    def _image_mime(raw):
        if raw.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if raw.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if raw.startswith((b"GIF87a", b"GIF89a")):
            return "image/gif"
        if raw.startswith(b"BM"):
            return "image/bmp"
        if len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
            return "image/webp"
        return ""

    def _decode_data_playlist(self, value):
        text = str(value or "")
        comma = text.find(",")
        if comma <= 0:
            raise RuntimeError("HLS data URI 缺少 payload")
        meta = text[:comma].lower()
        payload = text[comma + 1 :]
        if len(payload) > self.max_playlist_bytes * 2:
            raise RuntimeError("HLS data URI 超过上限")
        if ";base64" in meta:
            raw = base64.b64decode(payload)
        else:
            raw = unquote(payload).encode("utf-8")
        if len(raw) > self.max_playlist_bytes:
            raise RuntimeError("HLS 播放列表超过上限")
        source = raw.decode("utf-8", errors="strict")
        if not source.lstrip().startswith("#EXTM3U"):
            raise RuntimeError("HLS 播放列表缺少 EXTM3U")
        for line in source.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if not self._is_public_http_url(line):
                raise RuntimeError("HLS 含非公网或相对分片地址")
        return source.encode("utf-8")

    def _image_proxy_url(self, url):
        value = str(url or "").strip()
        if not self._is_public_http_url(value):
            return ""
        return self._local_proxy_url("image", self._pack_text(value))

    def _local_proxy_url(self, kind, token):
        site_key = quote(
            str(getattr(self, "siteKey", "") or self.proxy_site_key or "catemby"),
            safe="",
        )
        base = self._proxy_base_url()
        separator = "&" if "?" in base else "?"
        return "%s%ssiteKey=%s&kind=%s&token=%s" % (
            base,
            separator,
            site_key,
            quote(kind, safe=""),
            quote(token, safe=""),
        )

    def _proxy_base_url(self):
        inherited = getattr(super(), "getProxyUrl", None)
        if callable(inherited):
            try:
                value = str(inherited(True) or "").strip()
                if value:
                    return value
            except Exception:
                pass
        if CatVodProxy is not None:
            return str(CatVodProxy.getUrl(True)) + "?do=py"
        return "http://127.0.0.1:9978/proxy?do=py"

    def _new_session(self):
        session = requests.Session()
        session.trust_env = self.trust_env
        session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept-Language": "zh-CN,zh;q=0.9,zh-TW;q=0.8,en;q=0.5",
            }
        )
        if self.proxy:
            session.proxies.update({"http": self.proxy, "https": self.proxy})
        return session

    def _reset_session(self):
        if self._session is not None:
            try:
                self._session.close()
            except Exception:
                pass
        self._session = self._new_session()

    @staticmethod
    def _signature_static(token, salt):
        timestamp = str(int(time.time()))
        digest = hashlib.md5((timestamp + salt).encode("utf-8")).hexdigest()
        return timestamp + "." + token + "." + digest

    def _signature(self):
        return self._signature_static(self.SIGNATURE_TOKEN, self.SIGNATURE_SALT)

    @staticmethod
    def _read_bounded(response, maximum):
        content_length = response.headers.get("Content-Length")
        if content_length:
            try:
                if int(content_length) > maximum:
                    raise RuntimeError("响应体超过上限")
            except ValueError:
                pass
        chunks = []
        total = 0
        for chunk in response.iter_content(65536):
            if not chunk:
                continue
            total += len(chunk)
            if total > maximum:
                raise RuntimeError("响应体超过上限")
            chunks.append(chunk)
        return b"".join(chunks)

    def _looks_like_challenge(self, status, text):
        if int(status or 0) not in (403, 429, 503):
            return False
        lower = str(text or "").lower()
        return any(marker in lower for marker in self.CHALLENGE_MARKERS)

    def _cache_get(self, key):
        with self._lock:
            item = self._cache.get(key)
            if not item:
                return None
            if item[0] < time.time():
                self._cache.pop(key, None)
                return None
            return item[1]

    def _cache_set(self, key, value, ttl):
        if ttl <= 0:
            return
        with self._lock:
            self._cache[key] = (time.time() + ttl, value, time.time())
            if len(self._cache) > 128:
                oldest = min(self._cache, key=lambda item: self._cache[item][2])
                self._cache.pop(oldest, None)

    def _health_get(self, key):
        with self._lock:
            item = self._health.get(key)
            if not item or time.time() - item[0] > self.health_cache_ttl:
                self._health.pop(key, None)
                return None
            return item[1]

    def _health_set(self, key, value):
        with self._lock:
            self._health[key] = (time.time(), value)
            self._trim_timed_cache(self._health, 24)

    def _playlist_cache_get(self, token):
        with self._lock:
            item = self._playlist_cache.get(token)
            proxy_ttl = max(30, self.resolver_cache_ttl)
            if not item or time.time() - item[0] > proxy_ttl:
                self._playlist_cache.pop(token, None)
                return None
            return item[1]

    @staticmethod
    def _trim_timed_cache(cache, maximum):
        while len(cache) > maximum:
            oldest = min(cache, key=lambda key: cache[key][0])
            cache.pop(oldest, None)

    @staticmethod
    def _pack_text(value):
        raw = str(value or "").encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    @staticmethod
    def _unpack_text(value):
        token = str(value or "").strip()
        token += "=" * (-len(token) % 4)
        try:
            return base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
        except Exception:
            return ""

    def _pack_play_id(self, payload):
        raw = json.dumps(
            payload or {}, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        return self.PLAY_PREFIX + base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    def _unpack_play_id(self, value):
        text = str(value or "").strip()
        if not text.startswith(self.PLAY_PREFIX):
            return {}
        token = text[len(self.PLAY_PREFIX) :]
        token += "=" * (-len(token) % 4)
        try:
            data = json.loads(base64.urlsafe_b64decode(token).decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _filter(key, name, values):
        return {
            "key": key,
            "name": name,
            "value": [{"n": item[0], "v": item[1]} for item in values],
        }

    @staticmethod
    def _parse_dict(value):
        if isinstance(value, dict):
            return value
        if not value:
            return {}
        try:
            parsed = json.loads(str(value))
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _choice(value, options, default):
        allowed = {item[1] for item in options}
        text = str(value or "").strip()
        return text if text in allowed else default

    @staticmethod
    def _safe_filter_value(value):
        text = str(value or "").strip()
        return text if re.match(r"^[A-Za-z0-9._:-]{1,80}$", text) else ""

    @staticmethod
    def _safe_play_name(value, limit=120):
        text = re.sub(r"\s+", " ", str(value or ""))
        text = text.replace("#", " ").replace("$", " ").strip()
        return text[:limit] or "播放"

    @staticmethod
    def _clean_text(value):
        return re.sub(r"\s+", " ", str(value or "")).strip()

    @staticmethod
    def _number(value):
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _bounded_int(value, default, minimum, maximum):
        try:
            number = int(value)
        except (TypeError, ValueError):
            return default
        return max(minimum, min(maximum, number))

    @staticmethod
    def _bool(value, default=False):
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() not in ("0", "false", "no", "off", "")

    @staticmethod
    def _page(value):
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            return 1

    def _normalize_detail_id(self, value):
        text = str(value or "").strip()
        if text.startswith("atvp_detail:"):
            text = text[len("atvp_detail:") :]
        return text if re.match(r"^[A-Za-z0-9._:-]{1,120}$", text) else ""

    @staticmethod
    def _quality_height(value):
        numbers = [int(item) for item in re.findall(r"(?<!\d)(2160|1440|1080|720|540|480)(?:p)?", str(value or ""), re.I)]
        return max(numbers) if numbers else 0

    @staticmethod
    def _expiry_epoch(value):
        if value is None or value == "":
            return 0
        try:
            number = float(value)
            if number > 100000000000:
                number /= 1000.0
            return number
        except (TypeError, ValueError):
            pass
        text = str(value).strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(text).timestamp()
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _date_value(value):
        digits = re.sub(r"\D", "", str(value or ""))[:14]
        try:
            return int(digits.ljust(14, "0"))
        except ValueError:
            return 0

    @staticmethod
    def _has_subtitle(value):
        text = re.sub(r"\s+", "", str(value or ""))
        return bool(re.search(r"中文字幕|简体中文|繁体中文|中字|字幕|CHS|CHT|SUB", text, re.I))

    @staticmethod
    def _has_hd(value):
        return bool(re.search(r"(?:^|[^A-Z0-9])(HD|FHD|UHD|4K|2160P|1080P|720P)(?:[^A-Z0-9]|$)", str(value or ""), re.I))

    @staticmethod
    def _extract_btih(value):
        text = str(value or "")
        match = re.search(r"btih:([A-F0-9]{40}|[A-Z2-7]{32})", text, re.I)
        if match:
            return match.group(1).upper()
        if re.match(r"^(?:[A-F0-9]{40}|[A-Z2-7]{32})$", text.strip(), re.I):
            return text.strip().upper()
        return ""

    def _normalize_magnet(self, value):
        btih = self._extract_btih(value)
        return "magnet:?xt=urn:btih:" + btih if btih else ""

    @staticmethod
    def _format_source_size(value):
        size_mb = float(value or 0)
        if size_mb <= 0:
            return ""
        if size_mb >= 1024:
            return "%.2fGB" % (size_mb / 1024.0)
        return "%dMB" % int(size_mb)

    @staticmethod
    def _duration(value):
        try:
            number = float(value or 0)
            return "%d分钟" % int(round(number)) if number > 0 else ""
        except (TypeError, ValueError):
            return ""

    @staticmethod
    def _area_name(value):
        return {"0": "日本", "1": "日本", "2": "欧美", "3": "FC2"}.get(str(value), "")

    def _variant_label(self, item):
        parts = []
        if item.get("height"):
            parts.append("%dP" % int(item["height"]))
        variant = str(item.get("variant") or "").lower()
        if "original" in variant:
            parts.append("原版")
        elif "reducing_mosaic" in variant:
            parts.append("处理版")
        parts.append("HLS" if item.get("transport") == "hls" else "MP4")
        duration_seconds = self._number(item.get("duration_seconds"))
        if duration_seconds:
            parts.append("%d分钟" % int(round(duration_seconds / 60.0)))
        health = self._health_for_variant(item)
        if health and health.get("ok"):
            parts.append("%dms" % int(health.get("rtt_ms") or 0))
        label = self._clean_text(item.get("label"))
        if label and label not in parts:
            parts.append(label)
        return " ".join(item for item in parts if item)

    @staticmethod
    def _origin(url):
        parsed = urlsplit(str(url or ""))
        if not parsed.scheme or not parsed.hostname:
            return ""
        port = ":%d" % parsed.port if parsed.port else ""
        return "%s://%s%s" % (parsed.scheme, parsed.hostname, port)

    @staticmethod
    def _is_public_http_url(value):
        try:
            parsed = urlsplit(str(value or ""))
            if parsed.scheme not in ("http", "https") or not parsed.hostname:
                return False
            host = parsed.hostname.strip("[]")
            try:
                address = ipaddress.ip_address(host)
                return not (
                    address.is_private
                    or address.is_loopback
                    or address.is_link_local
                    or address.is_multicast
                    or address.is_unspecified
                )
            except ValueError:
                return host.lower() != "localhost"
        except Exception:
            return False

    def _empty_page(self, page, message=""):
        result = {
            "list": [],
            "page": page,
            "pagecount": page,
            "limit": 24,
            "total": 0,
        }
        if message:
            result["msg"] = self._clean_text(message)
        return result

    def _detail_error(self, movie_id, message):
        text = self._clean_text(message) or "详情读取失败"
        error_id = self._pack_play_id({"kind": "error", "message": text})
        return {
            "vod_id": movie_id or "error",
            "vod_name": "详情读取失败",
            "vod_pic": self.DEFAULT_PIC,
            "vod_content": text,
            "vod_play_from": "错误",
            "vod_play_url": "查看错误$" + error_id,
        }

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
