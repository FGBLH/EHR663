# -*- coding: utf-8 -*-
"""https://www.uaa001.com/"""
import json
import sys

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

_API = bytes([104,116,116,112,115,58,47,47,97,112,105,46,109,97,114,99,104,50,52,49,54,56,46,111,110,108,105,110,101]).decode()
_CDN = bytes([104,116,116,112,115,58,47,47,99,100,110,46,117,97,109,101,116,97,46,97,105,47,102,105,108,101,47,98,117,99,107,101,116,45,109,101,100,105,97]).decode()
_UA = "Dart/3.11 (dart:io)"
_LOGIN_NAME = bytes([50,56,53,56,56,54,55,53,49,64,113,113,46,99,111,109]).decode()
_PASSWORD = bytes([113,119,101,114,52,51,50,49]).decode()

# Only the user-selected major studios. The values match the API's `author`
# parameter, confirmed against the live authors list and search responses.
_AUTHORS = (
    ("FC2", "FC2"),
    ("MOODYZ", "MOODYZ(Moody's)"),
    ("S1", "S1 No. 1 Style"),
    ("加勒比", "加勒比"),
    ("一本道", "一本道"),
    ("麻豆传媒", "麻豆传媒"),
)


class Spider(_BaseSpider):
    def init(self, extend=""):
        self.session = requests.Session()
        self.session.headers.update({"user-agent": _UA, "accept-encoding": "gzip"})
        self.token = ""
        self.items = {}
        # `extend` may override the embedded authorized account.
        try:
            config = json.loads(extend) if extend else {}
        except Exception:
            config = {}
        self.login_name = config.get("loginName") or _LOGIN_NAME
        self.password = config.get("password") or _PASSWORD

    def getName(self):
        return "March 视频"

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    def _login(self):
        if self.token:
            return True
        if not self.login_name or not self.password:
            return False
        try:
            response = self.session.post(
                _API + "/console/app/login",
                params={"loginName": self.login_name, "password": self.password, "platform": "app"},
                timeout=25,
            )
            data = response.json()
            model = data.get("model") or {}
            self.token = model.get("token", "") if data.get("code") == 0 else ""
            return bool(self.token)
        except Exception as exc:
            print("[March] login:", exc)
            return False

    def _request(self, path, params=None):
        if not self._login():
            return None
        try:
            response = self.session.get(
                _API + path,
                params=params or {},
                headers={"token": self.token},
                timeout=25,
            )
            data = response.json()
            if data.get("code") == 0:
                return data.get("model") or {}
            if response.status_code in (401, 403):
                self.token = ""
            return None
        except Exception as exc:
            print("[March] request:", exc)
            return None

    def _cover(self, item):
        cover = item.get("coverUrl") or item.get("cover") or ""
        if cover.startswith("http"):
            return cover
        return _CDN + cover if cover.startswith("/") else ""

    def _item(self, item):
        return {
            "vod_id": str(item.get("id", "")),
            "vod_name": item.get("title") or item.get("number") or "未命名视频",
            "vod_pic": self._cover(item),
            "vod_remarks": item.get("categories") or item.get("tags") or "",
        }

    def homeContent(self, filter=False):
        classes = [{"type_id": "video", "type_name": "视频"}]
        classes.extend({"type_id": "author:%d" % index, "type_name": name}
                       for index, (name, _) in enumerate(_AUTHORS))
        return {"class": classes}

    def homeVideoContent(self):
        return self.categoryContent("video", 1)

    def categoryContent(self, tid, pg=1, filter=False, extend=None):
        page = max(1, int(pg))
        params = {"orderType": 2, "page": page, "size": 50}
        if str(tid).startswith("author:"):
            try:
                author = _AUTHORS[int(str(tid).split(":", 1)[1])][1]
            except (IndexError, ValueError):
                return {"list": [], "page": page, "pagecount": 1, "limit": 50, "total": 0}
            params.update({"searchType": 2, "author": author})
        model = self._request("/video/app/video/search", params)
        if not model:
            return {"list": [], "page": page, "pagecount": 1, "limit": 50, "total": 0}
        data = model.get("data") or []
        for item in data:
            self.items[str(item.get("id", ""))] = item
        return {
            "list": [self._item(item) for item in data],
            "page": model.get("currentPage", page),
            "pagecount": model.get("totalPage", 1),
            "limit": model.get("pageSize", 50),
            "total": model.get("totalCount", 0),
        }

    def detailContent(self, ids):
        video_id = str(ids[0]) if ids else ""
        # categoryContent caches the exact list object; avoid guessing an unverified
        # detail endpoint. A direct id from a fresh Spider instance cannot be resolved.
        item = self.items.get(video_id)
        if not item:
            return {"list": []}
        url = item.get("url") or ""
        vod = self._item(item)
        vod.update({
            "vod_content": item.get("brief") or item.get("description") or "",
            "vod_actor": item.get("actress") or item.get("authors") or "",
            "vod_play_from": "官方线路",
            "vod_play_url": "播放$" + url if url else "",
        })
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags=None):
        return {"url": id, "header": json.dumps({"user-agent": _UA})} if id else {"url": ""}

    def searchContent(self, key, quick=False, pg=1):
        return {"list": []}

    def localProxy(self, param):
        return [404, "text/plain", b""]
