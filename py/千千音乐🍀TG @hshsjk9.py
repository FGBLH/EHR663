#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""千千音乐 TVBox Python 单源（music.91q.com Web API 版）。"""

import base64
import gzip
import hashlib
import json
import time
import urllib.parse
import urllib.request

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider(object):
        pass


class Spider(BaseSpider):
    BASE = "https://music.91q.com"
    APPID = "16073360"
    SECRET = "0b50b02fd0d73a9c4c8c3a781c30845f"
    UA = ("Mozilla/5.0 (Linux; Android 10; TVBox) "
          "AppleWebKit/537.36 Chrome/124 Safari/537.36")

    # 首页分类，每项 (显示名, 搜索关键词)。
    CATEGORIES = [
        ("新歌推荐", "新歌"),
        ("经典金曲", "经典"),
        ("怀旧老歌", "老歌"),
        ("英文歌曲", "英文"),
        ("说唱",     "说唱"),
        ("古风",     "古风"),
        ("民谣",     "民谣"),
        ("摇滚",     "摇滚"),
        ("电子音乐", "电子"),
        ("影视原声", "影视"),
        ("轻音乐",   "轻音乐"),
        ("热门歌手", "歌手"),
    ]

    # 音质档位，按码率从高到低，(rate_key, 显示名)。
    RATES = [
        ("3000", "无损FLAC"),
        ("320",  "极高320K"),
        ("128",  "标准128K"),
        ("64",   "省流64K"),
    ]

    # 搜索每页请求量，过滤 VIP 后取前 PAGE_SIZE 条。
    SEARCH_PAGE_SIZE = 50
    PAGE_SIZE = 20

    def __init__(self):
        try:
            super(Spider, self).__init__()
        except Exception:
            pass
        self.timeout = 18
        self.headers = {
            "User-Agent": self.UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate",
            "Referer": "https://music.91q.com/",
            "from": "web",
        }

    def getName(self):
        return "千千音乐"

    def init(self, extend=""):
        try:
            cfg = json.loads(extend) if isinstance(extend, str) and extend.strip() else extend
            if isinstance(cfg, dict):
                self.timeout = max(5, min(60, int(cfg.get("timeout", self.timeout))))
                if cfg.get("user_agent"):
                    self.headers["User-Agent"] = str(cfg["user_agent"])
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    #  签名 & 请求
    # ------------------------------------------------------------------ #

    def _sign(self, params):
        """对请求参数做 MD5 签名，返回含 sign / timestamp / appid 的完整字典。"""
        params = dict(params)
        params["appid"] = self.APPID
        params["timestamp"] = str(int(time.time()))
        keys = sorted(params.keys())
        raw = "&".join("{}={}".format(k, params[k]) for k in keys)
        params["sign"] = hashlib.md5(
            (raw + self.SECRET).encode("utf-8")).hexdigest()
        return params

    def _api(self, path, params=None):
        """发送 GET 请求并返回 JSON。"""
        params = self._sign(params or {})
        url = self.BASE + path + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers=self.headers)
        with urllib.request.urlopen(req, timeout=self.timeout) as res:
            raw = res.read()
            if res.headers.get("Content-Encoding", "").lower() == "gzip":
                raw = gzip.decompress(raw)
            return json.loads(raw.decode("utf-8", "replace"))

    def _fetch_text(self, url):
        """直接获取纯文本内容（如歌词文件）。"""
        req = urllib.request.Request(url, headers={"User-Agent": self.UA})
        with urllib.request.urlopen(req, timeout=self.timeout) as res:
            raw = res.read()
            if res.headers.get("Content-Encoding", "").lower() == "gzip":
                raw = gzip.decompress(raw)
            return raw.decode("utf-8", "replace")

    # ------------------------------------------------------------------ #
    #  辅助方法
    # ------------------------------------------------------------------ #

    @staticmethod
    def _pack(kind, value):
        raw = json.dumps(value, ensure_ascii=False,
                         separators=(",", ":")).encode()
        return kind + ":" + base64.urlsafe_b64encode(raw).decode().rstrip("=")

    @staticmethod
    def _unpack(value, kind):
        text, prefix = str(value or ""), kind + ":"
        if not text.startswith(prefix):
            return None
        raw = text[len(prefix):]
        return json.loads(base64.urlsafe_b64decode(
            (raw + "=" * (-len(raw) % 4)).encode()).decode())

    @staticmethod
    def _result(items, page=1, more=False, size=20):
        page = max(1, int(page))
        return {"list": items, "page": page,
                "pagecount": page + 1 if more else page,
                "limit": size,
                "total": (page - 1) * size + len(items) + (size if more else 0),
                "parse": 0, "jx": 0}

    @staticmethod
    def _safe_name(name):
        return str(name or "播放").replace("$", " ").replace("#", " ")

    def _artists(self, track):
        return " / ".join(
            str(a.get("name") or "")
            for a in track.get("artist") or [] if isinstance(a, dict) and a.get("name"))

    def _track_card(self, track, prefix=""):
        """将 API 返回的单曲对象转为 TVBox 卡片。"""
        if not isinstance(track, dict) or not track.get("TSID"):
            return None
        tsid = str(track["TSID"])
        name = str(track.get("title") or "未知歌曲")
        artists = self._artists(track)
        album = str(track.get("albumTitle") or "")
        remark = prefix + ((" · " + artists) if prefix and artists else artists or album)
        return {
            "vod_id": self._pack("song", {"tsid": tsid, "name": name}),
            "vod_name": name,
            "vod_pic": str(track.get("pic") or ""),
            "vod_remarks": remark,
        }

    def _available_rates(self, track):
        """返回曲目可用码率列表，按从高到低排列。"""
        all_rate = track.get("allRate") or []
        if not isinstance(all_rate, list):
            all_rate = []
        rate_strs = [str(r) for r in all_rate]
        return [(k, label) for k, label in self.RATES if k in rate_strs] or self.RATES

    # ------------------------------------------------------------------ #
    #  搜索（过滤 VIP 歌曲）
    # ------------------------------------------------------------------ #

    def _search_tracks(self, keyword, page=1, size=None):
        """搜索并过滤 VIP 歌曲，返回 (原始响应, 免费曲目列表, 是否还有更多)。"""
        size = size or self.SEARCH_PAGE_SIZE
        payload = {"word": keyword, "type": 1,
                   "pageNo": page, "pageSize": size}
        data = self._api("/v1/search", payload)
        raw_tracks = (data.get("data") or {}).get("typeTrack") or []
        api_more = bool(int((data.get("data") or {}).get("haveMore") or 0))
        # 过滤 VIP 歌曲（isVip=1），只保留免费可播的。
        free_tracks = [t for t in raw_tracks
                       if isinstance(t, dict) and int(t.get("isVip") or 0) == 0]
        return data, free_tracks, api_more

    # ------------------------------------------------------------------ #
    #  TVBox 接口
    # ------------------------------------------------------------------ #

    def homeContent(self, filter):
        classes = [{"type_id": "search_" + kw, "type_name": name}
                   for name, kw in self.CATEGORIES]
        return {"class": classes, "filters": {}}

    def homeVideoContent(self):
        try:
            _, tracks, _ = self._search_tracks("新歌", 1)
            cards = [c for c in (self._track_card(t, "新歌") for t in tracks[:self.PAGE_SIZE]) if c]
            return self._result(cards, 1, False, max(1, len(cards)))
        except Exception:
            return self._result([], 1)

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = max(1, int(pg or 1))
            keyword = str(tid).replace("search_", "", 1) if str(tid).startswith("search_") else str(tid)
            _, tracks, api_more = self._search_tracks(keyword, page)
            page_tracks = tracks[:self.PAGE_SIZE]
            cards = [c for c in (self._track_card(t, keyword) for t in page_tracks) if c]
            # 如果过滤后不足一页但 API 说还有更多，则允许翻页。
            have_more = api_more and len(tracks) >= len(page_tracks)
            return self._result(cards, page, have_more, self.PAGE_SIZE)
        except Exception:
            return self._result([], int(pg or 1))

    def searchContent(self, key, quick, pg="1"):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg="1"):
        try:
            page, keyword = max(1, int(pg or 1)), str(key or "").strip()
            if not keyword:
                return self._result([], 1)
            _, tracks, api_more = self._search_tracks(keyword, page)
            page_tracks = tracks[:self.PAGE_SIZE]
            cards = [c for c in (self._track_card(t) for t in page_tracks) if c]
            have_more = api_more and len(tracks) >= len(page_tracks)
            return self._result(cards, page, have_more, self.PAGE_SIZE)
        except Exception:
            return self._result([], 1)

    # ------------------------------------------------------------------ #
    #  详情 & 播放
    # ------------------------------------------------------------------ #

    def _tracklink(self, tsid, rate=None):
        params = {"TSID": str(tsid)}
        if rate:
            params["rate"] = str(rate)
        return (self._api("/v1/song/tracklink", params) or {}).get("data") or {}

    def _song_detail(self, packed):
        info = self._unpack(packed, "song") or {}
        tsid = info.get("tsid") or packed
        name = info.get("name") or "千千音乐"

        # 调 tracklink 获取曲目完整信息。
        track = self._tracklink(tsid)
        if not track:
            track = {"TSID": tsid, "title": name}

        title = str(track.get("title") or name)
        artists = self._artists(track)
        album = str(track.get("albumTitle") or "未知专辑")
        pic = str(track.get("pic") or "")
        duration = int(track.get("duration") or 0)
        is_vip = int(track.get("isVip") or 0)

        # 获取可用码率。
        rates = self._available_rates(track)

        # 尝试获取歌词。
        lyric_text = ""
        lyric_url = str(track.get("lyric") or "")
        if lyric_url:
            try:
                lyric_text = self._fetch_text(lyric_url)
            except Exception:
                pass

        # 生成多音质播放线路。
        sources, urls = [], []
        if is_vip:
            # VIP 歌曲无法播放，提示用户。
            content_prefix = "[VIP歌曲，暂不支持播放]\n"
        else:
            content_prefix = ""
        for rate_key, rate_label in rates:
            sources.append(rate_label)
            urls.append(
                self._safe_name(title) + "$a:" + tsid + ":" + rate_key)

        vod = {
            "vod_id": packed,
            "vod_name": title + (" [VIP]" if is_vip else ""),
            "vod_pic": pic,
            "type_name": "音乐",
            "vod_actor": artists,
            "vod_remarks": "%02d:%02d" % (duration // 60, duration % 60) if duration else "",
            "vod_content": content_prefix + "专辑：" + album + "\n" + lyric_text,
            "vod_play_from": "$$$".join(sources) if sources else "千千音乐",
            "vod_play_url": "$$$".join(urls) if urls else
                            self._safe_name(title) + "$a:" + tsid + ":128",
        }
        return vod

    def detailContent(self, array):
        value = str(array[0] if isinstance(array, (list, tuple)) else array)
        try:
            return {"list": [self._song_detail(value)], "parse": 0, "jx": 0}
        except Exception:
            tsid = value.split(":")[-1] if ":" in value else value
            return {"list": [{
                "vod_id": value, "vod_name": "千千音乐",
                "vod_play_from": "千千音乐",
                "vod_play_url": "播放$a:" + tsid + ":128",
            }], "parse": 0, "jx": 0}

    def playerContent(self, flag, pid, vipFlags):
        value = str(pid or "")
        try:
            if value.startswith("a:"):
                _, tsid, rate = value.split(":", 2)
            else:
                tsid, rate = value, "128"

            # 1. 先尝试用户选择的码率。
            data = self._tracklink(tsid, rate)
            url = str(data.get("path") or "")

            # 2. 指定码率失败，逐个尝试所有可用码率。
            if not url:
                all_rate = data.get("allRate") or []
                for try_rate in all_rate:
                    if str(try_rate) == str(rate):
                        continue
                    try_data = self._tracklink(tsid, try_rate)
                    try_url = str(try_data.get("path") or "")
                    if try_url:
                        url = try_url
                        break

            # 3. 仍无 URL，尝试不带 rate 参数的默认调用。
            if not url:
                data = self._tracklink(tsid)
                url = str(data.get("path") or "")

            if not url:
                return {"parse": 1, "jx": 0, "url": value, "header": {}}

            return {
                "parse": 0, "jx": 0, "url": url, "music_player": 1,
                "header": {
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": "https://music.91q.com/",
                },
            }
        except Exception:
            return {"parse": 1, "jx": 0, "url": value, "header": {}}

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def localProxy(self, params):
        return [404, "text/plain", b""]


if __name__ == "__main__":
    s = Spider()
    print(json.dumps(s.homeContent(True), ensure_ascii=False, indent=2))
    print("---")
    print(json.dumps(s.homeVideoContent(), ensure_ascii=False, indent=2)[:800])