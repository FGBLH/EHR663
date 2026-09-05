# coding=utf-8
#!/usr/bin/env python3
# @name 咖啡直播
# @author 转自 OmniBox JS
# @description 体育赛事录像回放 + 直播（足球/篮球/NBA）
# @version 2.0.0

import json
import requests


class Spider:

    def getName(self):
        return "咖啡直播"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.host = "https://kafeizhibo.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://kafeizhibo.com/live/all"
        }

    def log(self, msg):
        print("[咖啡直播] " + str(msg))

    # =========================================================
    # 工具
    # =========================================================

    def _normalize_url(self, path):
        if not path:
            return ""
        if path.startswith("http"):
            return path
        if path.startswith("//"):
            return "https:" + path
        return self.host + ("" if path.startswith("/") else "/") + path

    def _get(self, path, params=None, referer=None):
        h = dict(self.headers)
        if referer:
            h["Referer"] = referer
        resp = requests.get(self.host + path, headers=h, params=params, timeout=10)
        return resp.json()

    # =========================================================
    # 直播部分
    # =========================================================

    def _fetch_live_all(self):
        """GET /api/v1/archor — 返回所有正在直播的频道"""
        return self._get("/api/v1/archor", referer=self.host + "/live/all")

    def _parse_live_list(self, items, category_filter=None):
        """
        category: 1=足球, 2=篮球, None=全部
        每个 archor 代表一个独立直播频道（同一场球可能有多个频道）
        合并同 match_id 的频道到一个 vod，多线路在 detail 里处理
        """
        # 按 room_id 去重（同一 room_id 只取第一个，避免重复）
        seen_rooms = set()
        result = []
        for item in items:
            if category_filter and item.get("category") != category_filter:
                continue
            room_id = str(item.get("room_id", ""))
            if room_id in seen_rooms:
                continue
            seen_rooms.add(room_id)

            home = item.get("home_team", "")
            away = item.get("away_team", "")
            league = item.get("league_name", "")
            h_score = item.get("home_score", 0)
            a_score = item.get("away_score", 0)
            title = "{} vs {} ({})".format(home, away, league)

            pic = self._normalize_url(item.get("screenshot", ""))
            if not pic or "default" in pic:
                mi = item.get("match_info") or {}
                pic = mi.get("home_team_logo", "")

            result.append({
                "vod_id": "live_{}".format(room_id),
                "vod_name": "🔴 " + title,
                "vod_pic": pic,
                "vod_remarks": "{} - {} | {}".format(h_score, a_score, item.get("name", "")),
            })
        return result

    def _detail_live(self, room_id):
        """GET /api/v1/room/{room_id} — 获取直播间多线路"""
        try:
            data = self._get(
                "/api/v1/room/{}".format(room_id),
                referer=self.host + "/room/{}".format(room_id)
            )
            if data.get("code") != 200 or not data.get("data"):
                return {"list": []}

            d = data["data"]
            room_info = d.get("room_info", {})
            signals = d.get("signals", [])

            home = room_info.get("home_team", "")
            away = room_info.get("away_team", "")
            league = room_info.get("league", "")
            h_score = room_info.get("home_score", 0)
            a_score = room_info.get("away_score", 0)
            title = "{} vs {} ({})".format(home, away, league)

            teams = d.get("teams", {})
            pic = (teams.get("home") or {}).get("logo", "")

            # 每条 signal 是一个线路（官方直播/原声直播）
            episodes = []
            for sig in signals:
                url = sig.get("stream_url", "")
                if url:
                    name = sig.get("name", "线路")
                    episodes.append("{}${}".format(name, url))

            # 如果 signals 为空，fallback 到 archor
            if not episodes:
                archor = d.get("archor", {})
                url = archor.get("stream_url", "")
                if url:
                    episodes.append("{}${}".format(archor.get("name", "直播"), url))

            vod = {
                "vod_id": "live_{}".format(room_id),
                "vod_name": "🔴 " + title,
                "vod_pic": pic,
                "vod_content": "{} {} vs {}，比分 {} - {}".format(
                    league, home, away, h_score, a_score
                ),
                "vod_play_from": "直播线路",
                "vod_play_url": "#".join(episodes),
            }
            return {"list": [vod]}
        except Exception as e:
            self.log("直播详情失败: " + str(e))
            return {"list": []}

    # =========================================================
    # 录像部分
    # =========================================================

    def _fetch_recordings(self, page=1, size=30, league=None, type_id=None):
        params = {"page": page, "size": size}
        if league:
            params["league"] = league
        elif type_id and type_id not in ("all", "nba", "live_all", "live_1", "live_2"):
            params["type"] = type_id
        h = dict(self.headers)
        h["Referer"] = self.host + "/pc/replay"
        resp = requests.get(self.host + "/api/v1/recordings", headers=h, params=params, timeout=10)
        return resp.json()

    def _parse_video_list(self, items):
        result = []
        for item in items:
            title = "{} vs {} ({})".format(
                item["home_team"], item["away_team"], item["league_name"]
            )
            score = "{} - {}".format(item["home_score"], item["away_score"])
            pic = item.get("cover_image", "")
            if pic and not pic.startswith("http"):
                pic = self._normalize_url(pic)
            if not pic or "default_cover" in pic:
                pic = item.get("home_team_logo", "")
            remarks = "{} | {} | {}个录像".format(
                score, item["start_time"], item.get("recording_count", 0)
            )
            result.append({
                "vod_id": str(item["match_id"]),
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remarks,
            })
        return result

    def _detail_recording(self, vid):
        try:
            h = dict(self.headers)
            h["Referer"] = self.host + "/pc/replay"
            resp = requests.get(
                "{}/api/v1/match/{}/recordings".format(self.host, vid),
                headers=h,
                timeout=10
            )
            data = resp.json()
            if data.get("code") != 200 or not data.get("data"):
                return {"list": []}

            match = data["data"]["match"]
            replays = data["data"].get("replays", [])
            highlights = data["data"].get("highlights", [])

            title = "{} vs {} ({})".format(
                match["home_team"], match["away_team"], match["league_name"]
            )
            pic = match.get("home_team_logo") or match.get("away_team_logo") or ""

            episodes = []
            for idx, rec in enumerate(replays):
                if rec.get("video_url"):
                    name = rec.get("title") or "录像{}".format(idx + 1)
                    episodes.append("{}${}".format(name, rec["video_url"]))
            for idx, rec in enumerate(highlights):
                if rec.get("video_url"):
                    name = rec.get("title") or "集锦{}".format(idx + 1)
                    episodes.append("{}${}".format(name, rec["video_url"]))

            vod = {
                "vod_id": str(vid),
                "vod_name": title,
                "vod_pic": pic,
                "vod_content": "{} {} {} vs {}，比分 {} - {}，比赛时间：{}".format(
                    match["league_name"], match.get("match_round", ""),
                    match["home_team"], match["away_team"],
                    match["home_score"], match["away_score"],
                    match["start_time"]
                ),
                "vod_play_from": "录像源",
                "vod_play_url": "#".join(episodes),
            }
            return {"list": [vod]}
        except Exception as e:
            self.log("录像详情失败: " + str(e))
            return {"list": []}

    # =========================================================
    # FongMi 接口
    # =========================================================

    def homeContent(self, filter):
        categories = [
            # 直播分类
            {"type_id": "live_all", "type_name": "🔴 直播全部"},
            {"type_id": "live_1",   "type_name": "🔴 直播足球"},
            {"type_id": "live_2",   "type_name": "🔴 直播篮球"},
            # 录像分类
            {"type_id": "all",      "type_name": "录像全部"},
            {"type_id": "1",        "type_name": "录像足球"},
            {"type_id": "2",        "type_name": "录像篮球"},
            {"type_id": "nba",      "type_name": "录像NBA"},
        ]
        # 首页展示直播列表
        try:
            data = self._fetch_live_all()
            vod_list = self._parse_live_list(data.get("data", [])) if data.get("code") == 200 else []
        except Exception as e:
            self.log("首页失败: " + str(e))
            vod_list = []
        return {"class": categories, "list": vod_list}

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg) if pg else 1

        # ---- 直播分类 ----
        if tid in ("live_all", "live_1", "live_2"):
            try:
                data = self._fetch_live_all()
                if data.get("code") == 200:
                    cat = None if tid == "live_all" else int(tid.split("_")[1])
                    vod_list = self._parse_live_list(data.get("data", []), category_filter=cat)
                else:
                    vod_list = []
            except Exception as e:
                self.log("直播分类失败: " + str(e))
                vod_list = []
            return {"list": vod_list, "page": 1, "pagecount": 1, "limit": 100, "total": len(vod_list)}

        # ---- 录像分类 ----
        try:
            if tid == "nba":
                data = self._fetch_recordings(pg, 20, league="NBA")
                size = 20
            elif tid == "all":
                data = self._fetch_recordings(pg, 30)
                size = 30
            else:
                data = self._fetch_recordings(pg, 30, type_id=tid)
                size = 30

            vod_list = []
            pagecount = 1
            if data.get("code") == 200 and data.get("data"):
                vod_list = self._parse_video_list(data["data"])
                pagecount = pg + 1 if len(data["data"]) == size else pg
        except Exception as e:
            self.log("录像分类失败: " + str(e))
            vod_list = []
            pagecount = 1

        return {"list": vod_list, "page": pg, "pagecount": pagecount, "limit": 30, "total": len(vod_list)}

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) and ids else str(ids)
        if vid.startswith("live_"):
            room_id = vid[5:]  # 去掉 "live_" 前缀
            return self._detail_live(room_id)
        else:
            return self._detail_recording(vid)

    def searchContent(self, key, quick, pg=1):
        if not key:
            return {"list": []}
        keyword = key.lower()
        result = []

        # 搜索直播
        try:
            data = self._fetch_live_all()
            if data.get("code") == 200:
                for item in data.get("data", []):
                    if (keyword in item.get("home_team", "").lower()
                            or keyword in item.get("away_team", "").lower()
                            or keyword in item.get("league_name", "").lower()
                            or keyword in item.get("title", "").lower()):
                        room_id = str(item.get("room_id", ""))
                        home = item.get("home_team", "")
                        away = item.get("away_team", "")
                        league = item.get("league_name", "")
                        result.append({
                            "vod_id": "live_{}".format(room_id),
                            "vod_name": "🔴 {} vs {} ({})".format(home, away, league),
                            "vod_pic": "",
                            "vod_remarks": "直播中",
                        })
        except Exception as e:
            self.log("搜索直播失败: " + str(e))

        # 搜索录像
        try:
            data = self._fetch_recordings(1, 100)
            if data.get("code") == 200:
                for item in data["data"]:
                    if (keyword in item["home_team"].lower()
                            or keyword in item["away_team"].lower()
                            or keyword in item["league_name"].lower()):
                        title = "{} vs {} ({})".format(
                            item["home_team"], item["away_team"], item["league_name"]
                        )
                        result.append({
                            "vod_id": str(item["match_id"]),
                            "vod_name": title,
                            "vod_pic": "",
                            "vod_remarks": "{} - {}".format(item["home_score"], item["away_score"]),
                        })
        except Exception as e:
            self.log("搜索录像失败: " + str(e))

        return {"list": result, "page": 1, "pagecount": 1}

    def playerContent(self, flag, id, vipFlags):
        return {
            "parse": 0,
            "playUrl": "",
            "url": id,
            "header": json.dumps({
                "User-Agent": self.headers["User-Agent"],
                "Referer": self.host,
                "Origin": self.host,
            })
        }
