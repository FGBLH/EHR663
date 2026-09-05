# -*- coding: utf-8 -*-

import re
import json
from urllib.parse import urlencode

# ---- TVBox 内置基类（部署环境必有）；本地测试时降级为 requests fallback ----
try:
    from base.spider import Spider as _BaseSpider
except ImportError:
    _BaseSpider = None

if _BaseSpider is None:
    import requests

    class _FallbackSpider(object):
        def fetch(self, url, headers=None, **kwargs):
            return requests.get(url, headers=headers, timeout=30)

        def post(self, url, headers=None, data=None, **kwargs):
            return requests.post(url, headers=headers, data=data, timeout=30)

        def log(self, msg):
            print(msg)

    _BaseSpider = _FallbackSpider


class Spider(_BaseSpider):
    # ===== 站点配置（改这里即可换站 / 换源）=====
    HOST = "https://eco.fe-spark.cn"
    API = "/api/provide/vod"          # MacCMS V10 兼容 JSON 接口
    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"

    # ===== 框架必须：返回源名称 =====
    def getName(self):
        return "🌟 EcoHub 影视"

    # ===== 初始化（extend 可传 JSON 覆盖 host / source）=====
    def init(self, extend=""):
        self.host = self.HOST
        self.source = ""              # 可选：限定某个采集源，如 "2470287370"
        self.headers = {
            "User-Agent": self.UA,
            "Referer": self.host + "/",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        # extend 示例：{"host":"https://你的域名","source":"2470287370"}
        if extend:
            try:
                cfg = json.loads(extend)
                if cfg.get("host"):
                    self.host = str(cfg["host"]).rstrip("/")
                if cfg.get("source"):
                    self.source = str(cfg["source"])
            except Exception:
                pass

    # ===================== 工具方法 =====================
    def _api(self, params):
        """拼接接口地址并用基类 fetch 请求，返回 dict（带 2 次重试）"""
        params = {k: v for k, v in params.items() if v not in (None, "")}
        if self.source:
            params.setdefault("source", self.source)
        url = self.host + self.API + "?" + urlencode(params)
        last = {}
        for _ in range(3):
            try:
                resp = self.fetch(url, headers=self.headers)
            except Exception:
                resp = None
            if resp is None:
                continue
            text = resp.text if hasattr(resp, "text") else resp
            try:
                last = json.loads(text)
                if last.get("code") == 1 or "list" in last or "class" in last:
                    return last
            except Exception:
                last = {}
        return last

    @staticmethod
    def _to_int(v, default=0):
        try:
            return int(v)
        except Exception:
            return default

    def _norm_list(self, data):
        """把接口 list 归一化为 TVBox 卡片字段"""
        items = data.get("list") or data.get("vod") or []
        out = []
        for it in items:
            out.append({
                "vod_id": str(it.get("vod_id")),
                "vod_name": it.get("vod_name", ""),
                "vod_pic": it.get("vod_pic", ""),
                "vod_remarks": it.get("vod_remarks", ""),
            })
        return out

    # ===================== 五大接口 =====================
    def homeContent(self, filter):
        """首页分类 + 筛选条件（filter=True 才返回 filters）"""
        data = self._api({"ac": "class"})
        classes = []
        for c in data.get("class") or []:
            classes.append({
                "type_id": str(c.get("type_id")),
                "type_name": c.get("type_name", ""),
            })
        result = {"class": classes}
        if filter:
            filters = {}
            for tid, flist in (data.get("filters") or {}).items():
                fout = []
                for f in flist:
                    vals = [{"n": v.get("n", ""), "v": v.get("v", "")}
                            for v in f.get("value", [])]
                    fout.append({
                        "key": f.get("key", ""),
                        "name": f.get("name", ""),
                        "value": vals,
                    })
                filters[str(tid)] = fout
            result["filters"] = filters
        return result

    def homeVideoContent(self):
        """首页推荐：取 电影/连续剧/动漫 各若干拼成（首页不走分类）"""
        items = []
        for tid in ("8", "26", "1"):
            data = self._api({"ac": "list", "t": tid, "pg": "1"})
            items.extend(self._norm_list(data)[:8])
            if len(items) >= 24:
                break
        return {"list": items[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        """分类列表：t=分类id，extend 里的筛选项直接转发为查询参数"""
        params = {"ac": "list", "t": str(tid),
                  "pg": str(max(1, self._to_int(pg, 1)))}
        extend = extend or {}
        for k, v in extend.items():
            # 跳过空值与 MacCMS 的「其他」占位 __others__
            if v not in (None, "", "__others__"):
                params[str(k)] = str(v)
        data = self._api(params)
        items = self._norm_list(data)
        return {
            "list": items,
            "page": self._to_int(data.get("page"), 1),
            "pagecount": self._to_int(data.get("pagecount"), 1),
            "limit": self._to_int(data.get("limit"), len(items)),
            "total": self._to_int(data.get("total") or data.get("recordcount"), 0),
        }

    def detailContent(self, ids):
        """详情：取播放线路与剧集（vod_play_url 已是直接 m3u8 直链）"""
        vid = str(ids[0])
        data = self._api({"ac": "detail", "ids": vid})
        items = data.get("list") or data.get("vod") or []
        if not items:
            return {"list": []}
        it = items[0]
        return {"list": [{
            "vod_id": str(it.get("vod_id", vid)),
            "vod_name": it.get("vod_name", ""),
            "vod_pic": it.get("vod_pic", ""),
            "vod_play_from": it.get("vod_play_from", ""),
            "vod_play_url": it.get("vod_play_url", ""),
            "vod_remarks": it.get("vod_remarks", ""),
            "vod_year": it.get("vod_year", ""),
        }]}

    def searchContent(self, key, quick, pg="1"):
        """搜索：wd=关键词"""
        data = self._api({"ac": "search", "wd": str(key),
                          "pg": str(max(1, self._to_int(pg, 1)))})
        items = self._norm_list(data)
        return {
            "list": items,
            "page": self._to_int(data.get("page"), 1),
            "pagecount": self._to_int(data.get("pagecount"), 1),
        }

    def playerContent(self, flag, id, vipFlags):
        """播放：id 已是直链（详情接口给的 m3u8/mp4），直接返回 parse=0"""
        url = (id or "").strip()
        if re.match(r"^https?://", url, re.I) and re.search(
                r"\.(m3u8|mp4|flv|mkv|ts|mpd)([?#]|$)", url, re.I):
            return {"parse": 0, "url": url, "header": self.headers}
        # 兜底：从可能带参数的串里正则提取直链
        m = re.search(r"https?://[^\s\"'<>]+?\.(?:m3u8|mp4)[^\s\"'<>]*", url)
        if m:
            return {"parse": 0, "url": m.group(0), "header": self.headers}
        return {"parse": 1, "url": url, "header": self.headers}

    # ===================== 框架辅助方法 =====================
    def isVideoFormat(self, url):
        return bool(re.search(r"\.(m3u8|mp4|flv|mkv|ts|mpd)([?#]|$)",
                              str(url or ""), re.I))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return [404, "text/plain", "", ""]

    def destroy(self):
        pass