# -*- coding: utf-8 -*-
"""VIP兔 (https://www.viptu.com/) - TVBox / dr_py Python Spider."""

import base64
import json
import re
from urllib.parse import unquote

import requests
from base.spider import Spider


class Spider(Spider):
    name = "VIP兔"
    site_url = "https://www.viptu.com"
    base_url = site_url
    timeout = 12
    page_size = 20
    default_pic = "https://a1.boltp.com/2025/04/05/67f10a0195ac9.jpeg"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 12; M2007J3SC) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Referer": site_url + "/",
    }

    # Default values are only used when the website's public configuration is unavailable.
    main_api = "https://tianwei.qzz.io/api.php/provide/vod/"
    category_map = {
        "2": "剧集",
        "1": "电影",
        "3": "综艺",
        "4": "动漫",
        "5": "少儿",
        "6": "纪录片",
        "7": "短剧",
    }
    fallback_search_sources = [
        ("极速", "https://jszyapi.com/api.php/provide/vod/from/jsm3u8/"),
        ("非凡", "https://api.ffzyapi.com/api.php/provide/vod/from/ffm3u8/"),
        ("西瓜", "https://caiji.xgzyapi.com/api.php/provide/vod/from/xiguam3u8/"),
    ]
    media_url_pattern = re.compile(
        r"\.(?:m3u8|mp4|flv|mkv|avi|mov)(?:[?#].*)?$", re.I
    )

    def init(self, extend=""):
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self._config_loaded = False
        self.search_sources = list(self.fallback_search_sources)
        self.site_parser_urls = []
        self._direct_play_cache = {}
        self._load_public_config()

    def _ensure_session(self):
        if not hasattr(self, "session"):
            self.init()

    def _request_json(self, url, params=None, payload=None):
        self._ensure_session()
        try:
            if payload is None:
                response = self.session.get(url, params=params, timeout=self.timeout)
            else:
                response = self.session.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as error:
            print("[{}] 请求失败: {}".format(self.name, error))
            return None

    @staticmethod
    def _decode_config(value):
        """Decode the public enc_* payload used by the website front end."""
        if not isinstance(value, str):
            return None
        try:
            parts = value.split("_")
            if len(parts) >= 3 and parts[0] == "enc":
                raw = base64.b64decode(parts[1])
                plain = bytes((byte - index % 5) % 256 for index, byte in enumerate(raw))
                return unquote(plain.decode("utf-8"))
            return unquote(base64.b64decode(value).decode("utf-8"))
        except Exception:
            return None

    def _load_public_config(self):
        if self._config_loaded:
            return
        self._config_loaded = True

        data = self._request_json(self.site_url + "/api/web")
        decoded = self._decode_config(data)
        if not decoded:
            return
        try:
            config = json.loads(decoded).get("data", {})
        except Exception:
            return

        hot_db = str(config.get("hot_db") or "")
        lines = [line.strip() for line in hot_db.splitlines() if line.strip()]
        if len(lines) >= 2 and lines[0].startswith("http"):
            parsed_categories = {}
            for pair in lines[1].split("|"):
                name, separator, type_id = pair.partition(",")
                if separator and type_id.strip():
                    parsed_categories[type_id.strip()] = name.strip()
            if parsed_categories:
                self.main_api = lines[0]
                self.category_map = parsed_categories

        sources = []
        built_in_parsers = []
        for line in str(config.get("search_api") or "").splitlines():
            fields = [field.strip() for field in line.split(",")]
            if len(fields) < 2 or not fields[1].startswith("http"):
                continue
            source_name, source_api = fields[0], fields[1]
            # The site stores parser routes after the first six comma-separated
            # fields. The first route may be unnamed; subsequent routes use
            # `name,url` chunks separated by `|||`.
            parser_tail = ",".join(fields[6:])
            for parser_index, parser_chunk in enumerate(parser_tail.split("|||"), 1):
                parser_chunk = parser_chunk.strip()
                if not parser_chunk.startswith("http") and "," in parser_chunk:
                    parser_label, parser_chunk = parser_chunk.split(",", 1)
                    parser_label = parser_label.strip() or "内置线路{}".format(parser_index)
                else:
                    parser_label = "内置线路{}".format(parser_index)
                parser_chunk = parser_chunk.strip()
                if parser_chunk.startswith(("https://", "http://")):
                    route = (parser_label, parser_chunk)
                    if route not in built_in_parsers:
                        built_in_parsers.append(route)
            # These are the site's own direct media source entries. Platform-only
            # entries still work from the home page through TVBox parsers.
            if "m3u8" in source_api.lower():
                sources.append((source_name, source_api))
        if sources:
            self.search_sources = self._order_media_sources(sources)[:3]
        if built_in_parsers:
            self.site_parser_urls = built_in_parsers

    def _order_media_sources(self, sources):
        """Keep the known direct media APIs first even if config ordering changes."""
        ordered = []
        for preferred_name, preferred_api in self.fallback_search_sources:
            for source_name, source_api in sources:
                if source_api == preferred_api or source_name == preferred_name:
                    pair = (source_name, source_api)
                    if pair not in ordered:
                        ordered.append(pair)
        for pair in sources:
            if pair not in ordered:
                ordered.append(pair)
        return ordered

    @staticmethod
    def _safe_text(value):
        return str(value or "").replace("$", " ").replace("#", " ").replace("$$$", " ").strip()

    @classmethod
    def _is_direct_url(cls, value):
        return bool(cls.media_url_pattern.search(unquote(str(value or "").strip())))

    @classmethod
    def _normalize_title(cls, value):
        """Normalize harmless display differences without relaxing title matching."""
        text = cls._safe_text(value).lower()
        text = re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE)
        return text

    @staticmethod
    def _year(value):
        match = re.search(r"(?:19|20)\d{2}", str(value or ""))
        return match.group(0) if match else ""

    def _encode_id(self, source_name, source_api, vod_id):
        payload = json.dumps(
            {"name": source_name, "api": source_api, "id": str(vod_id)},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        return "viptu_" + base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")

    def _decode_id(self, value):
        value = str(value or "")
        if not value.startswith("viptu_"):
            return "VIP兔", self.main_api, value
        try:
            encoded = value[6:]
            encoded += "=" * (-len(encoded) % 4)
            data = json.loads(base64.urlsafe_b64decode(encoded).decode("utf-8"))
            source_name = str(data.get("name") or "VIP兔")
            source_api = str(data.get("api") or "")
            vod_id = str(data.get("id") or "")
            if source_api.startswith(("https://", "http://")) and vod_id:
                return source_name, source_api, vod_id
        except Exception:
            pass
        return "VIP兔", self.main_api, value

    def _build_item(self, item, source_name, source_api):
        vod_id = item.get("id", item.get("vod_id", ""))
        name = item.get("title", item.get("vod_name", ""))
        remarks = item.get("vod_remarks", item.get("remarks", ""))
        score = item.get("rate", item.get("vod_douban_score", item.get("vod_score", "")))
        if score and str(score) not in ("0", "0.0"):
            remarks = "{} 评分{}".format(remarks, score).strip()
        return {
            "vod_id": self._encode_id(source_name, source_api, vod_id),
            "vod_name": self._safe_text(name),
            "vod_pic": item.get("cover", item.get("vod_pic", "")) or self.default_pic,
            "vod_remarks": self._safe_text(remarks),
            "vod_year": str(item.get("vod_year", "")),
            "vod_area": self._safe_text(item.get("vod_area", "")),
            "vod_actor": self._safe_text(item.get("vod_actor", "")),
        }

    def _source_list(self, source_name, source_api, tid, page):
        data = self._request_json(
            source_api,
            params={"ac": "list", "t": tid, "pg": page},
        ) or {}
        return data, [self._build_item(item, source_name, source_api) for item in data.get("list", [])]

    def homeContent(self, filter=False):
        self._ensure_session()
        result = {
            "class": [
                {"type_id": tid, "type_name": name}
                for tid, name in self.category_map.items()
            ],
            "filters": {},
            "list": [],
        }
        # The mobile website defaults to the drama category, so mirror that
        # behavior and provide real covers from its hot endpoint.
        default_tid = "2" if "2" in self.category_map else next(iter(self.category_map), "1")
        data = self._request_json(
            self.site_url + "/api/hot",
            payload={"type": default_tid, "page": 1, "api_url": self.main_api},
        ) or {}
        if data.get("success") and data.get("data"):
            result["list"] = [
                self._build_item(item, "VIP兔", self.main_api)
                for item in data.get("data", [])
            ]
        else:
            _, result["list"] = self._source_list("VIP兔", self.main_api, default_tid, 1)
        return result

    def homeVideoContent(self):
        return self.homeContent()

    def categoryContent(self, tid, pg, filter=False, extend=None):
        self._ensure_session()
        try:
            page = max(1, int(pg))
        except Exception:
            page = 1
        type_id = str(tid)
        result = {"page": page, "pagecount": page, "limit": self.page_size, "total": 0, "list": []}
        if type_id not in self.category_map:
            return result

        data = self._request_json(
            self.site_url + "/api/hot",
            payload={"type": type_id, "page": page, "api_url": self.main_api},
        ) or {}
        if data.get("success"):
            result["list"] = [
                self._build_item(item, "VIP兔", self.main_api)
                for item in data.get("data", [])
            ]
            # The web endpoint intentionally returns only the requested slice.
            result["pagecount"] = page + 1 if result["list"] else page
            result["total"] = len(result["list"]) * result["pagecount"]
            return result

        data, result["list"] = self._source_list("VIP兔", self.main_api, type_id, page)
        result["pagecount"] = int(data.get("pagecount") or page)
        result["total"] = int(data.get("total") or len(result["list"]))
        result["limit"] = int(data.get("limit") or self.page_size)
        return result

    def detailContent(self, ids):
        self._ensure_session()
        token = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
        source_name, source_api, vod_id = self._decode_id(token)
        if not vod_id:
            return {"list": []}

        data = self._request_json(
            source_api,
            params={"ac": "detail", "ids": vod_id},
        ) or {}
        movies = data.get("list") or []
        if not movies:
            return {"list": []}
        item = movies[0]
        # Direct m3u8 URLs are suitable for TVBox. Platform pages and parser
        # pages are not media streams and lead to an endless buffering state.
        direct_groups = self._collect_play_groups(item, direct_only=True)
        if not direct_groups:
            direct_groups = self._find_direct_play_sources(item)
        if direct_groups:
            play_from, play_url = self._join_play_groups(direct_groups)
        else:
            # Last-resort compatibility path: hand the original platform URL to
            # TVBox's configured parser. Do not wrap it in this site's parser
            # webpage, because a webpage is not a playable video URL.
            play_from, play_url = self._build_play_list(item)
        vod = {
            "vod_id": str(token),
            "vod_name": self._safe_text(item.get("vod_name", "")),
            "vod_pic": item.get("vod_pic") or self.default_pic,
            "vod_remarks": self._safe_text(item.get("vod_remarks", "")),
            "vod_year": str(item.get("vod_year", "")),
            "vod_area": self._safe_text(item.get("vod_area", "")),
            "vod_actor": self._safe_text(item.get("vod_actor", "")),
            "vod_director": self._safe_text(item.get("vod_director", "")),
            "vod_type": self._safe_text(item.get("type_name", item.get("vod_class", ""))),
            "vod_content": item.get("vod_content", item.get("vod_blurb", "")) or "",
            "vod_play_from": play_from,
            "vod_play_url": play_url,
        }
        return {"list": [vod]}

    def _collect_play_groups(self, item, direct_only=False):
        raw_sources = str(item.get("vod_play_from") or "").split("$$$")
        raw_groups = str(item.get("vod_play_url") or "").split("$$$")
        source_aliases = {
            "ffm3u8": "非凡",
            "xiguam3u8": "西瓜",
            "jsm3u8": "极速",
            "lzm3u8": "量子",
        }
        groups = []
        for index, raw_group in enumerate(raw_groups):
            episodes = []
            contains_non_media_url = False
            for part in raw_group.split("#"):
                if "$" not in part:
                    continue
                episode_name, episode_url = part.rsplit("$", 1)
                episode_url = episode_url.strip()
                if episode_url:
                    episodes.append("{}${}".format(self._safe_text(episode_name), episode_url))
                    if not self._is_direct_url(episode_url):
                        contains_non_media_url = True
            if not episodes or (direct_only and contains_non_media_url):
                continue
            source = raw_sources[index].strip() if index < len(raw_sources) else ""
            line_name = source_aliases.get(source.lower(), self._safe_text(source) or "线路")
            groups.append((line_name, "#".join(episodes)))
        return groups

    @staticmethod
    def _join_play_groups(groups):
        return "$$$".join(pair[0] for pair in groups), "$$$".join(pair[1] for pair in groups)

    def _build_play_list(self, item, direct_only=False):
        return self._join_play_groups(self._collect_play_groups(item, direct_only))

    def _episode_count(self, item, direct_only=False):
        counts = [group.count("#") + 1 for _, group in self._collect_play_groups(item, direct_only)]
        return max(counts) if counts else 0

    def _expected_episode_count(self, item):
        """Prefer the API's explicit total over inconsistent platform lines."""
        for key in ("vod_total", "total"):
            match = re.search(r"\d+", str(item.get(key) or ""))
            if match and int(match.group(0)) > 0:
                return int(match.group(0))
        return self._episode_count(item)

    def _same_media_version(self, original, candidate):
        if self._normalize_title(original.get("vod_name", original.get("title", ""))) != self._normalize_title(
            candidate.get("vod_name", candidate.get("title", ""))
        ):
            return False

        original_year = self._year(original.get("vod_year"))
        candidate_year = self._year(candidate.get("vod_year"))
        if original_year and candidate_year and original_year != candidate_year:
            return False

        original_count = self._expected_episode_count(original)
        candidate_count = self._expected_episode_count(candidate)
        if not candidate_count:
            candidate_count = self._episode_count(candidate, direct_only=True)
        if original_count >= 4:
            if candidate_count < 2:
                return False
            # A small difference is normal for specials, but a different
            # season or a truncated collection must not replace the result.
            if abs(original_count - candidate_count) > max(2, original_count // 8):
                return False
        return candidate_count > 0

    def _find_direct_play_sources(self, original):
        """Find same-title direct streams for items whose own links are webpages."""
        cache_key = "{}|{}|{}".format(
            self._normalize_title(original.get("vod_name", original.get("title", ""))),
            self._year(original.get("vod_year")),
            self._expected_episode_count(original),
        )
        if cache_key in self._direct_play_cache:
            return self._direct_play_cache[cache_key]

        wanted_title = self._normalize_title(original.get("vod_name", original.get("title", "")))
        if not wanted_title:
            return []
        direct_groups = []
        seen_urls = set()
        seen_names = set()
        for source_name, source_api in self.search_sources:
            data = self._request_json(source_api, params={"ac": "list", "wd": original.get("vod_name", ""), "pg": 1}) or {}
            candidates = data.get("list") or []
            for candidate in candidates:
                candidate_title = candidate.get("vod_name", candidate.get("title", ""))
                if self._normalize_title(candidate_title) != wanted_title:
                    continue
                candidate_id = candidate.get("vod_id", candidate.get("id", ""))
                if not candidate_id:
                    continue
                detail = self._request_json(source_api, params={"ac": "detail", "ids": candidate_id}) or {}
                matches = detail.get("list") or []
                if not matches:
                    continue
                candidate_detail = matches[0]
                if not self._same_media_version(original, candidate_detail):
                    continue
                # A provider can expose more than one direct line. Keep its
                # fullest line as a single TVBox playback source.
                source_groups = self._collect_play_groups(candidate_detail, direct_only=True)
                if not source_groups:
                    continue
                _, episode_group = max(source_groups, key=lambda pair: pair[1].count("#"))
                if episode_group in seen_urls:
                    continue
                line_name = self._safe_text(source_name) or "直连"
                base_name = line_name
                duplicate_index = 2
                while line_name in seen_names:
                    line_name = "{}-{}".format(base_name, duplicate_index)
                    duplicate_index += 1
                seen_names.add(line_name)
                seen_urls.add(episode_group)
                direct_groups.append((line_name, episode_group))
                break

        self._direct_play_cache[cache_key] = direct_groups
        return direct_groups

    def searchContent(self, key, quick=False, pg=1):
        self._ensure_session()
        try:
            page = max(1, int(pg))
        except Exception:
            page = 1
        keyword = str(key or "").strip()
        result = {"page": page, "pagecount": page, "limit": self.page_size, "total": 0, "list": []}
        if not keyword:
            return result

        seen, page_counts = set(), []
        # Search three media APIs from the site's public configuration. Their
        # IDs carry the source URL, so detail and playback retain the match.
        for source_name, source_api in self.search_sources:
            data = self._request_json(
                source_api,
                params={"ac": "list", "wd": keyword, "pg": page},
            ) or {}
            try:
                page_counts.append(int(data.get("pagecount") or page))
            except Exception:
                pass
            for item in data.get("list", []):
                name = self._safe_text(item.get("vod_name", item.get("title", "")))
                unique_key = "{}|{}".format(name.lower(), item.get("vod_year", ""))
                if not name or unique_key in seen:
                    continue
                seen.add(unique_key)
                built = self._build_item(item, source_name, source_api)
                built["vod_remarks"] = self._safe_text(
                    "{} [{}]".format(built.get("vod_remarks", ""), source_name)
                )
                result["list"].append(built)
                if len(result["list"]) >= 60:
                    break
            if len(result["list"]) >= 60:
                break

        result["pagecount"] = max(page_counts) if page_counts else page
        result["total"] = len(result["list"])
        return result

    def playerContent(self, flag, id, vipFlags=None):
        url = unquote(str(id or "").strip())
        if url.startswith("//"):
            url = "https:" + url
        if self._is_direct_url(url):
            return {"parse": 0, "playUrl": "", "url": url, "header": {"User-Agent": self.headers["User-Agent"]}}
        # Let the user's TVBox parse configuration handle a platform page. The
        # external parser pages advertised by VIP兔 return HTML/JSON rather than
        # media and must never be passed to the player as a stream URL.
        return {"parse": 1, "playUrl": "", "url": url, "header": {"User-Agent": self.headers["User-Agent"]}}

    def isVideoFormat(self, url):
        return self._is_direct_url(url)

    def manualVideoCheck(self):
        return False

    def localProxy(self, params):
        return None
