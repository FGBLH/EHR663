# -*- coding: utf-8 -*-
# ASMR Online (asmr.one) 音声站 Python Spider

import json
import time

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        pass

try:
    import requests
except ImportError:
    requests = None

API_BASES = [
    "https://api.asmr.one",
    "https://api.asmr-100.com",
    "https://api.asmr-200.com",
    "https://api.asmr-300.com",
]
UA = (
    "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)

# 排序分类：tid = order 值
ORDERS = [
    ("create_date", "最新"),
    ("release", "新发"),
    ("dl_count", "最热"),
    ("rate_average_2dp", "高分"),
    ("review_count", "热议"),
]


class Spider(BaseSpider):
    def init(self, extend=""):
        # extend 可指定 API 域名，例如 extend=https://api.asmr.one
        self.api = (extend or API_BASES[0]).strip().rstrip("/")
        self.session = requests.Session() if requests else None
        if self.session:
            self.session.headers = {
                "User-Agent": UA,
                "Accept": "application/json",
                "Referer": "https://www.asmr.one/",
            }

    def __init__(self):
        try:
            super().__init__()
        except Exception:
            pass
        self.init()

    def getName(self):
        return "ASMR音声"

    # ─────────────────────────── 基础 ───────────────────────────

    def _get(self, path):
        if not self.session:
            return {}
        try:
            r = self.session.get(self.api + path, timeout=20)
            if r.status_code != 200:
                return {}
            return r.json()
        except Exception:
            return {}

    @staticmethod
    def _clean_title(t):
        return (t or "").replace("【", "[").replace("】", "]").replace("$", "").replace("#", "")

    @staticmethod
    def _remark(w):
        parts = []
        if w.get("dl_count") is not None:
            parts.append("%dDL" % w.get("dl_count", 0))
        if w.get("price") is not None:
            parts.append("¥%d" % w.get("price", 0))
        if w.get("duration"):
            parts.append(str(w.get("duration")))
        return " ".join(parts)

    def _rows_to_vods(self, rows):
        out = []
        for w in rows or []:
            wid = str(w.get("id") or "")
            if not wid:
                continue
            out.append({
                "vod_id": wid,
                "vod_name": self._clean_title(w.get("title")),
                "vod_pic": w.get("mainCoverUrl") or w.get("samCoverUrl") or "",
                "vod_remarks": self._remark(w),
            })
        return out

    # ─────────────────────────── TVBox 契约 ───────────────────────────

    def homeContent(self, filter=False):
        classes = [{"type_id": o, "type_name": n} for o, n in ORDERS]
        d = self._get("/api/works?order=create_date&sort=desc&page=1&pageSize=20")
        rows = d.get("works") if isinstance(d, dict) else []
        return {"class": classes, "list": self._rows_to_vods(rows)}

    def homeVideoContent(self):
        d = self._get("/api/works?order=create_date&sort=desc&page=1&pageSize=20")
        rows = d.get("works") if isinstance(d, dict) else []
        return {"list": self._rows_to_vods(rows)}

    def categoryContent(self, tid, pg=1, filter=False, extend=None):
        order = tid if tid in dict(ORDERS) else "create_date"
        d = self._get("/api/works?order=%s&sort=desc&page=%d&pageSize=20" % (order, int(pg)))
        rows = d.get("works") if isinstance(d, dict) else []
        return {"list": self._rows_to_vods(rows), "page": int(pg), "pagecount": 9999}

    def searchContent(self, key, quick=False, pg="1"):
        import urllib.parse
        kw = urllib.parse.quote(key)
        d = self._get("/api/search/%s?order=create_date&sort=desc&page=%s&pageSize=20" % (kw, pg))
        rows = d.get("works") if isinstance(d, dict) else []
        return {"list": self._rows_to_vods(rows)}

    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, list) else ids)
        d = self._get("/api/work/" + vid)
        if not isinstance(d, dict) or not d.get("id"):
            return {"list": []}

        tags = ""
        if isinstance(d.get("tags"), list):
            names = []
            for t in d["tags"]:
                if isinstance(t, dict):
                    nm = t.get("name") or ""
                    if nm:
                        names.append(nm)
            tags = " ".join(names[:12])

        vod = {
            "vod_id": vid,
            "vod_name": self._clean_title(d.get("title")),
            "vod_pic": d.get("mainCoverUrl") or d.get("samCoverUrl") or "",
            "vod_content": "社团: %s | 时长: %s | 价格: ¥%s\n发行: %s\n%s" % (
                d.get("name") or "",
                d.get("duration") or "?",
                d.get("price") or "?",
                d.get("release") or "?",
                tags,
            ),
            "vod_year": (d.get("release") or "")[:4],
            "vod_actor": d.get("name") or "",
            "vod_play_from": "ASMR",
            "vod_play_url": self._build_play_url(vid),
        }
        return {"list": [vod]}

    def _build_play_url(self, vid):
        """tracks 树 -> 收集 audio 节点 -> '第N集 标题$m4a直链#...'"""
        d = self._get("/api/tracks/%s?v=2" % vid)
        audio = []
        if isinstance(d, list):
            audio = self._collect_audio({"children": d})
        if not audio:
            return ""
        parts = []
        for i, a in enumerate(audio, 1):
            title = self._clean_title(a.get("title")) or "音轨%d" % i
            url = a.get("streamLowQualityUrl") or a.get("mediaStreamUrl") or ""
            if not url:
                continue
            # 播放器对 m3u8 期望高；音频直链直接返回，播放器原生播放
            parts.append("%02d %s$%s" % (i, title, url))
        return "#".join(parts)

    def _collect_audio(self, node):
        out = []
        if node.get("type") == "audio":
            out.append(node)
        for c in node.get("children") or []:
            out.extend(self._collect_audio(c))
        return out

    def playerContent(self, flag, id, vipFlags=None):
        # id 即直链 URL，直接返回
        if not id or not str(id).startswith("http"):
            return {"parse": 0, "playUrl": ""}
        return {"parse": 0, "playUrl": str(id), "header": {"User-Agent": UA}}
