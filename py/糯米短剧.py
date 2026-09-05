# -*- coding: utf-8 -*-
import json
from urllib.parse import urljoin
from urllib.request import Request, urlopen

try:
    import requests
except Exception:
    requests = None

from base.spider import Spider


class Spider(Spider):
    name = "糯米短剧"
    host = "https://8728.mrsvj.com"
    api_host = "https://4gf56465fg112.hongjiuchang.com"
    api = api_host + "/api/web/v1"
    page_size = 24
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36",
        "Origin": host,
        "Referer": host + "/h5/",
        "Content-Type": "application/json",
    }

    def __init__(self):
        self.video_host = ""
        self.static_host = ""
        self.night_video_host = ""
        self.night_static_host = ""
        self.night_categories = []
        self.tag_map = {}
        self.session = requests.Session() if requests else None
        if self.session:
            self.session.headers.update(self.headers)

    def getName(self):
        return self.name

    def init(self, extend=""):
        if isinstance(extend, dict):
            data = extend
        else:
            try:
                data = json.loads(extend) if extend else {}
            except Exception:
                data = {}
        if isinstance(data, dict):
            self.api_host = str(data.get("api_host") or self.api_host).rstrip("/")
            self.api = self.api_host + "/api/web/v1"
            self.video_host = str(data.get("video_host") or "").rstrip("/")
            self.static_host = str(data.get("static_host") or "").rstrip("/")
            self.night_video_host = str(data.get("night_video_host") or "").rstrip("/")
            self.night_static_host = str(data.get("night_static_host") or "").rstrip("/")

    @staticmethod
    def _page(pg):
        try:
            return max(1, int(pg))
        except Exception:
            return 1

    @staticmethod
    def _response_text(response):
        if response is None:
            return ""
        if isinstance(response, str):
            return response
        if isinstance(response, bytes):
            return response.decode("utf-8", "ignore")
        if isinstance(response, dict):
            for key in ("body", "text", "content", "data"):
                value = response.get(key)
                if isinstance(value, bytes):
                    return value.decode("utf-8", "ignore")
                if isinstance(value, str):
                    return value
            return json.dumps(response, ensure_ascii=True)
        text = getattr(response, "text", None)
        if isinstance(text, str):
            return text
        content = getattr(response, "content", None)
        if isinstance(content, bytes):
            return content.decode("utf-8", "ignore")
        return ""

    def _post(self, path, data=None):
        url = self.api + path
        payload = json.dumps(data or {}, ensure_ascii=True).encode("utf-8")
        responses = []
        if self.session:
            try:
                responses.append(self.session.post(url, data=payload, timeout=15))
            except Exception:
                pass
        post_fn = getattr(self, "post", None)
        if callable(post_fn):
            try:
                responses.append(post_fn(url, data=payload, headers=self.headers))
            except Exception:
                pass
        try:
            responses.append(self.fetch(url, headers=self.headers, data=payload, method="POST"))
        except Exception:
            pass
        if not responses:
            try:
                request = Request(url, data=payload, headers=self.headers, method="POST")
                responses.append(urlopen(request, timeout=15).read())
            except Exception:
                pass
        for response in responses:
            try:
                obj = json.loads(self._response_text(response) or "{}")
                if isinstance(obj, dict) and obj.get("code") == 10000:
                    return obj.get("data") or {}
            except Exception:
                continue
        return {}

    def _load_config(self):
        data = self._post("/config/load")
        config = data.get("config") or {}
        self.video_host = str(config.get("video_domain") or self.video_host).rstrip("/")
        self.static_host = str(config.get("static_domain") or self.static_host or self.api_host).rstrip("/")
        self.night_video_host = str(config.get("wy_video_domain") or self.night_video_host).rstrip("/")
        self.night_static_host = str(config.get("wy_static_domain") or self.night_static_host).rstrip("/")
        tags = config.get("tags") or []
        self.tag_map = {str(x.get("id")): str(x.get("t") or "") for x in tags if x.get("id") is not None}
        return config

    def _pic(self, value):
        value = str(value or "").strip()
        if not value:
            return ""
        if value.startswith("http"):
            return value
        if not self.static_host:
            self._load_config()
        return urljoin((self.static_host or self.api_host) + "/", value)

    def _load_night_categories(self):
        data = self._post("/night/topic/category")
        self.night_categories = data.get("list") or []
        return self.night_categories

    def _night_category(self, cate):
        for item in self.night_categories or self._load_night_categories():
            if str(item.get("i") or "") == str(cate):
                return item
        return {}

    def _night_tag_folders(self, cate, pg, order="0"):
        item = self._night_category(cate)
        tags = [{"i": 0, "n": "全部视频"}] + list(item.get("t") or [])
        start = (pg - 1) * self.page_size
        current = tags[start:start + self.page_size]
        logo = "https://n5nn56n5n6n.foshanshow.com/h5/logo.png"
        videos = []
        for tag in current:
            tag_id = str(tag.get("i") if tag.get("i") is not None else "0")
            videos.append({
                "vod_id": "folder_nighttag_{}_{}_{}".format(cate, tag_id, order),
                "vod_name": str(tag.get("n") or "标签"),
                "vod_pic": logo,
                "vod_remarks": "进入标签",
                "vod_tag": "folder",
            })
        total = len(tags)
        pagecount = max(1, (total + self.page_size - 1) // self.page_size)
        return {"list": videos, "page": pg, "pagecount": pagecount, "limit": self.page_size, "total": total, "filters": {}}

    def _night_pic(self, value):
        value = str(value or "").strip()
        if not value:
            return ""
        if value.startswith("http"):
            return value
        if not self.night_static_host:
            self._load_config()
        base = (self.night_static_host or self.static_host or self.api_host).rstrip("/")
        return base + "/" + value.lstrip("/")

    def _list_result(self, data, pg, night=False):
        videos = []
        for item in data.get("list") or []:
            videos.append({
                "vod_id": ("night_" if night else "") + str(item.get("id") or ""),
                "vod_name": str(item.get("title") or ""),
                "vod_pic": self._night_pic(item.get("pic")) if night else self._pic(item.get("cover") or item.get("pic")),
                "vod_remarks": "全{}集".format(item.get("sets")) if item.get("sets") else str(item.get("times") or ""),
            })
        total = int(data.get("total") or 0)
        size = int(data.get("pageSize") or self.page_size)
        pagecount = max(pg, (total + size - 1) // size) if total else pg + (1 if data.get("hasMore") else 0)
        return {"list": videos, "page": pg, "pagecount": max(1, pagecount), "limit": size, "total": total}

    def homeContent(self, filter=False):
        if not self.tag_map:
            self._load_config()
        tag_items = [{"n": name, "v": tag_id} for tag_id, name in list(self.tag_map.items())[:72] if name]
        tag_groups = [{
            "key": "tag",
            "name": "标签",
            "value": [{"n": "全部", "v": ""}] + tag_items,
        }]
        classes = [
            {"type_id": "hot", "type_name": "热播剧"},
            {"type_id": "new", "type_name": "新剧"},
            {"type_id": "vip", "type_name": "VIP专享"},
            {"type_id": "night", "type_name": "午夜全部"},
        ]
        filters = {key: tag_groups for key in ("hot", "new", "vip")}
        order_filter = {"key": "order", "name": "排序", "value": [
            {"n": "最新发布", "v": "0"},
            {"n": "最高热度", "v": "hot"},
            {"n": "最高收藏", "v": "collect"},
        ]}
        filters["night"] = [order_filter]
        night_categories = self.night_categories or self._load_night_categories()
        for item in night_categories:
            cate = str(item.get("i") or "")
            name = str(item.get("n") or "")
            if not cate or not name:
                continue
            tid = "nightcate_" + cate
            classes.append({"type_id": tid, "type_name": name})
            current = []
            tags = item.get("t") or []
            if 0 < len(tags) <= 15:
                current.append({
                    "key": "night_tag",
                    "name": "标签",
                    "value": [{"n": "全部", "v": "0"}] + [
                        {"n": str(tag.get("n") or ""), "v": str(tag.get("i") or "")}
                        for tag in tags if tag.get("i") is not None and tag.get("n")
                    ],
                })
            elif len(tags) > 15:
                current.append({
                    "key": "night_tag",
                    "name": "标签",
                    "value": [{"n": "全部视频", "v": "0"}],
                })
            current.append(order_filter)
            filters[tid] = current
        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        data = self._post("/video/list", {"pageNum": 1, "pageSize": self.page_size})
        return {"list": self._list_result(data, 1)["list"]}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        page = self._page(pg)
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        extend = extend or {}
        tid = str(tid or "")

        if tid.startswith("folder_nighttag_"):
            parts = tid.split("_")
            if len(parts) >= 5:
                cate, tag, order = parts[2], parts[3], parts[4]
                data = self._post("/night/video/video-list", {
                    "pageNum": page,
                    "pageSize": self.page_size,
                    "cate": cate,
                    "tag": tag,
                    "order": order,
                })
                result = self._list_result(data, page, night=True)
                result["filters"] = {}
                return result

        if tid == "night" or tid.startswith("nightcate_"):
            cate = tid.replace("nightcate_", "") if tid.startswith("nightcate_") else "0"
            order = str(extend.get("order") or "0")
            cate_info = self._night_category(cate) if cate != "0" else {}
            tags = cate_info.get("t") or []
            if cate != "0" and len(tags) > 15:
                return self._night_tag_folders(cate, page, order)
            payload = {
                "pageNum": page,
                "pageSize": self.page_size,
                "cate": cate,
                "tag": str(extend.get("night_tag") or "0"),
                "order": order,
            }
            data = self._post("/night/video/video-list", payload)
            return self._list_result(data, page, night=True)

        tag = str(extend.get("tag") or "")
        if tag:
            data = self._post("/tags/video", {"tag": int(tag), "pageNum": page, "pageSize": self.page_size})
        else:
            payload = {"pageNum": page, "pageSize": self.page_size}
            if tid in ("new", "vip"):
                payload["type"] = tid
            data = self._post("/video/list", payload)
        return self._list_result(data, page)

    def detailContent(self, ids):
        vod_id = ids[0] if isinstance(ids, list) and ids else ids
        if not vod_id:
            return {"list": []}
        vod_id = str(vod_id)
        if vod_id.startswith("folder_nighttag_"):
            parts = vod_id.split("_")
            if len(parts) >= 5:
                cate, tag, order = parts[2], parts[3], parts[4]
                cate_info = self._night_category(cate)
                tag_name = "全部视频" if tag == "0" else next((str(t.get("n") or "") for t in cate_info.get("t") or [] if str(t.get("i")) == tag), "标签")
                vod = {
                    "vod_id": vod_id,
                    "vod_name": "{} - {}".format(str(cate_info.get("n") or "午夜剧场"), tag_name),
                    "vod_pic": "https://n5nn56n5n6n.foshanshow.com/h5/logo.png",
                    "vod_remarks": "标签目录",
                    "vod_content": "目录入口，点击播放进入视频列表",
                    "vod_play_from": "目录",
                    "vod_play_url": "打开$" + vod_id,
                }
                return {"list": [vod]}
        if vod_id.startswith("night_"):
            real_id = vod_id[6:]
            data = self._post("/night/video/info", {"id": int(real_id)})
            info = data.get("info") or {}
            if not info:
                return {"list": []}
            vod = {
                "vod_id": vod_id,
                "vod_name": str(info.get("title") or ""),
                "vod_pic": self._night_pic(info.get("pic")),
                "vod_remarks": str(info.get("times") or ""),
                "vod_content": "播放量：{}".format(info.get("views") or 0),
                "vod_play_from": "午夜剧场",
                "vod_play_url": "播放$nightplay_{}".format(real_id),
            }
            return {"list": [vod]}
        data = self._post("/video/play-info", {"id": vod_id, "setIndex": 0})
        info = data.get("info") or {}
        if not info:
            return {"list": []}
        episodes = []
        for item in info.get("setList") or []:
            index = item.get("i")
            if index is not None:
                episodes.append("第{}集${}|{}".format(index, vod_id, index))
        tags = []
        if not self.tag_map:
            self._load_config()
        for tag_id in str(info.get("tags") or "").split(","):
            if self.tag_map.get(tag_id):
                tags.append(self.tag_map[tag_id])
        vod = {
            "vod_id": str(vod_id),
            "vod_name": str(info.get("title") or ""),
            "vod_pic": self._pic(info.get("cover")),
            "vod_remarks": "全{}集".format(info.get("sets") or len(episodes)),
            "vod_content": str(info.get("summary") or ""),
            "vod_type": ",".join(tags),
            "vod_play_from": "糯米短剧",
            "vod_play_url": "#".join(episodes),
        }
        return {"list": [vod]}

    def searchContent(self, key, quick=False, pg=1):
        page = self._page(pg)
        if not key:
            return {"list": [], "page": page, "pagecount": 1, "limit": self.page_size, "total": 0}
        data = self._post("/search/list", {"text": str(key), "pageNum": page, "pageSize": self.page_size})
        return self._list_result(data, page)

    def playerContent(self, flag, id, vipFlags=None):
        text = str(id or "")
        if text.startswith("folder_nighttag_"):
            return {"parse": 1, "url": text, "header": {}}
        if text.startswith("nightplay_"):
            real_id = text[10:]
            data = self._post("/night/video/info", {"id": int(real_id)})
            info = data.get("info") or {}
            path = str(info.get("url_m3u8") or "").strip()
            if not path:
                return {"parse": 0, "url": "", "header": {}}
            if not self.night_video_host:
                self._load_config()
            base = (self.night_video_host or self.video_host).rstrip("/")
            url = path if path.startswith("http") else base + "/" + path.lstrip("/")
            return {"parse": 0, "url": url, "header": {"User-Agent": self.headers["User-Agent"], "Referer": self.host + "/h5/", "Origin": self.host}}
        if "|" not in text:
            return {"parse": 0, "url": "", "header": {}}
        vod_id, set_no = text.rsplit("|", 1)
        data = self._post("/video/set-info", {"id": vod_id, "set": self._page(set_no)})
        info = data.get("info") or {}
        path = str(info.get("url_m3u8") or "").strip()
        if not path:
            return {"parse": 0, "url": "", "header": {}}
        if not self.video_host:
            self._load_config()
        url = path if path.startswith("http") else urljoin((self.video_host or self.api_host) + "/", path)
        return {"parse": 0, "url": url, "header": {"User-Agent": self.headers["User-Agent"], "Referer": self.host + "/h5/", "Origin": self.host}}

    def isVideoFormat(self, url):
        return ".m3u8" in str(url or "").lower() or ".mp4" in str(url or "").lower()

    def localProxy(self, param):
        return [404, "text/plain", ""]
