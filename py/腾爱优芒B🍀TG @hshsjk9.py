# -*- coding: utf-8 -*-
"""
爱优腾芒哔哩聚合 —— 影视聚合 Python 源（OK影视 / 蜂蜜影视 / TVBox 通用）
=====================================================================
适配 OK影视、蜂蜜影视、TVBox 类壳子的标准 Python 源。
"""

import re
import json
import urllib.parse

# 网络请求：优先壳子内置 requests，缺失时降级 urllib（便于本地测试）
try:
    import requests as _requests
    _HAS_REQUESTS = True
except Exception:  # noqa: BLE001
    _requests = None
    _HAS_REQUESTS = False

# 兼容壳子内置基类；本地测试无壳子时回退到空基类
try:
    from base.spider import Spider as _BaseSpider
except Exception:  # noqa: BLE001
    class _BaseSpider:
        pass


def _log(*args):
    try:
        print("腾爱优聚合", *args)
    except Exception:  # noqa: BLE001
        pass


def _enc(value):
    """encodeURIComponent（保留 !'()*-._~ ）。"""
    return urllib.parse.quote(str(value), safe="!'()*-._~")


# 分类：数字 ID -> 接口字母参数 + 名称
_CATEGORY = {
    "1": ("qq",       "腾讯视频"),
    "2": ("qiyi",     "爱奇艺"),
    "3": ("youku",    "优酷视频"),
    "4": ("mgtv",     "芒果TV"),
    "5": ("bilibili", "B站"),
}
_KEY_TO_NUM = {v[0]: k for k, v in _CATEGORY.items()}


class Spider(_BaseSpider):
    """腾爱优聚合 —— 影视聚合源。"""

    name = "腾爱优聚合"

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def init(self, extend=""):
        """初始化：创建带 UA 的会话。extend 可传自定义解析站（JSON 或裸 URL）。"""
        _log("init ->", extend)
        self.host = "http://cj.tianwe.cn"
        self.header = {
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/150.0.0.0 Safari/537.36"),
        }
        # 直链解析站（kptv 后端已不稳定，仅作快速尝试；命中即直链播放）
        self.parse_api = "https://jx.kptv.us/?url="
        # WebView 解析站列表：壳子用内置浏览器打开这些页面完成解析播放。
        # （2026 年主流解析站已全部转浏览器端 JS 解析，纯 HTTP 无法取直链，
        #   由壳子 WebView 打开解析站播放页是当前唯一通用方案）
        self.parse_sites = [
            "https://jx.xmflv.com/?url=",
            "https://jx.playerjy.com/?url=",
            "https://jx.2s0.cn/?url=",
            "https://jx.m3u8.tv/jiexi/?url=",
            "https://www.daga.cc/vip1/?url=",
            "https://jx.xmflv.cc/?url=",
        ]
        # 用户自定义解析站（extend 传入时优先使用）
        self.custom_jx = self._parse_extend(extend)
        self.timeout = 10
        if _HAS_REQUESTS:
            self.session = _requests.Session()
            self.session.headers.update(self.header)

    @staticmethod
    def _parse_extend(extend):
        """从 extend 解析自定义解析站前缀。支持 JSON 字典或裸字符串。"""
        if not extend:
            return ""
        s = str(extend).strip()
        try:
            d = json.loads(s)
            if isinstance(d, dict):
                return str(d.get("parse", "") or d.get("jx", "")).strip()
        except Exception:  # noqa: BLE001
            pass
        if "url=" in s or "?" in s:
            return s
        return ""

    def getName(self):
        return self.name

    def destroy(self):
        pass

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        pass

    def localProxy(self, param):
        return None

    # ------------------------------------------------------------------
    # 网络请求
    # ------------------------------------------------------------------
    def _http_get(self, url):
        """GET 请求，返回文本；失败返回空字符串。"""
        try:
            if _HAS_REQUESTS:
                sess = getattr(self, "session", None) or _requests
                r = sess.get(url, timeout=getattr(self, "timeout", 15),
                             verify=False)
                r.encoding = "utf-8"
                return r.text
            # 降级 urllib
            import urllib.request
            req = urllib.request.Request(url, headers=self.header)
            with urllib.request.urlopen(req,
                                        timeout=getattr(self, "timeout", 15)) as resp:
                data = resp.read()
                try:
                    return data.decode("utf-8")
                except Exception:  # noqa: BLE001
                    return data.decode("latin-1")
        except Exception as exc:  # noqa: BLE001
            _log("myfetch err ", exc)
            return ""

    def _get_json(self, url):
        """GET 并解析 JSON。"""
        try:
            return json.loads(self._http_get(url))
        except Exception:  # noqa: BLE001
            return None

    # ------------------------------------------------------------------
    # 首页
    # ------------------------------------------------------------------
    def homeContent(self, filter=False):
        """首页：分类 + 筛选。"""
        try:
            classes = [
                {"type_id": "1", "type_pid": "0", "type_name": "腾讯视频"},
                {"type_id": "2", "type_pid": "0", "type_name": "爱奇艺"},
                {"type_id": "3", "type_pid": "0", "type_name": "优酷视频"},
                {"type_id": "4", "type_pid": "0", "type_name": "芒果TV"},
                {"type_id": "5", "type_pid": "0", "type_name": "B站"},
            ]

            type_filter = {
                "key": "class",
                "name": "类型",
                "value": [
                    {"n": "全部", "v": ""},
                    {"n": "电视剧", "v": "2"},
                    {"n": "电影", "v": "1"},
                    {"n": "动漫", "v": "4"},
                    {"n": "综艺", "v": "3"},
                    {"n": "少儿", "v": "5"},
                    {"n": "纪录片", "v": "6"},
                    {"n": "短剧", "v": "7"},
                ],
            }
            year_filter = {
                "key": "year",
                "name": "年份",
                "value": [
                    {"n": "全部", "v": ""},
                    {"n": "2026", "v": "2026"},
                    {"n": "2025", "v": "2025"},
                    {"n": "2024", "v": "2024"},
                    {"n": "2023", "v": "2023"},
                    {"n": "2022", "v": "2022"},
                ],
            }
            filters = {}
            for c in classes:
                filters[c["type_id"]] = [type_filter, year_filter]

            result = {"class": classes, "list": []}
            if filter:
                result["filters"] = filters
            return result
        except Exception as exc:  # noqa: BLE001
            _log("homeContent err", exc)
            return {"class": [], "list": []}

    def homeVideoContent(self):
        """首页推荐（原脚本无，返回空）。"""
        return {"list": []}

    # ------------------------------------------------------------------
    # 分类
    # ------------------------------------------------------------------
    def categoryContent(self, tid, pg, filter=False, extend=None):
        """
        分类列表。
        tid   : 数字分类 id（1-5）
        pg    : 页码
        extend: 筛选 {class, year, ...}
        """
        extend = extend or {}
        key = self._to_key(tid) or "qq"
        try:
            page = int(pg) if pg else 1
        except Exception:  # noqa: BLE001
            page = 1

        params = ["from=" + key, "ac=detail", "limit=24", "pg=" + str(page)]
        t = extend.get("class") or "2"
        params.append("t=" + t)
        if extend.get("year"):
            params.append("year=" + _enc(extend["year"]))

        url = self.host + "/api.php/provide/vod/?" + "&".join(params)
        _log("api category url ->", url)

        data = self._get_json(url)
        if not data:
            return {"list": [], "page": page, "pagecount": 1, "limit": 0,
                    "total": 0}

        vod_list = []
        if isinstance(data.get("list"), list):
            vod_list = [
                {
                    "vod_id": str(v.get("vod_id", "")),
                    "vod_name": v.get("vod_name", ""),
                    "vod_pic": v.get("vod_pic", ""),
                    "vod_remarks": v.get("vod_remarks", ""),
                }
                for v in data["list"]
            ]

        pc = data.get("pagecount") or 1
        try:
            pc = int(pc)
        except Exception:  # noqa: BLE001
            pc = 1

        return {
            "list": vod_list,
            "page": page,
            "pagecount": pc,
            "limit": len(vod_list),
            "total": pc * len(vod_list) if vod_list else 0,
        }

    # ------------------------------------------------------------------
    # 详情
    # ------------------------------------------------------------------
    def detailContent(self, ids):
        """详情。ids 可能为列表或 '1$xx' 字符串，取 id 最后一段。"""
        if not ids:
            return {"list": []}
        vid = str(ids)
        if isinstance(ids, (list, tuple)):
            vid = str(ids[0])
        vid = vid.split("$")[-1].strip()

        url = (self.host + "/api.php/provide/vod/?" +
               "&".join(["ac=detail", "ids=" + vid]))
        _log("detailurl", url)

        data = self._get_json(url)
        if not data:
            return {"list": []}

        vod_list = []
        if isinstance(data.get("list"), list):
            for item in data["list"]:
                if not item.get("vod_id"):
                    continue
                vod_list.append({
                    "vod_id": str(item.get("vod_id", "")),
                    "vod_name": item.get("vod_name", ""),
                    "vod_pic": item.get("vod_pic", ""),
                    "vod_remarks": item.get("vod_remarks", ""),
                    "vod_year": item.get("vod_year", ""),
                    "type_name": item.get("type_name", ""),
                    "vod_area": item.get("vod_area", ""),
                    "vod_lang": item.get("vod_lang", ""),
                    "vod_content": item.get("vod_content", ""),
                    "vod_play_from": item.get("vod_play_from", ""),
                    "vod_play_url": item.get("vod_play_url", ""),
                })
        return {"list": vod_list}

    # ------------------------------------------------------------------
    # 搜索
    # ------------------------------------------------------------------
    def searchContent(self, key, quick, pg="1"):
        """搜索。key 关键词，quick 是否快速搜索，pg 页码。"""
        if not key:
            return {"list": []}
        url = (self.host + "/api.php/provide/vod/?ac=detail&wd=" +
               _enc(key) + "&pg=" + str(pg))
        _log("api searchUrl:", url)

        data = self._get_json(url)
        if not data:
            return {"list": [], "page": str(pg), "pagecount": 1}

        vod_list = []
        if isinstance(data.get("list"), list):
            vod_list = [
                {
                    "vod_id": str(v.get("vod_id", "")),
                    "vod_name": v.get("vod_name") or v.get("name") or "",
                    "vod_pic": v.get("vod_pic") or v.get("pic") or "",
                    "vod_remarks": v.get("vod_remarks") or "",
                }
                for v in data["list"]
                if v.get("vod_id")
            ]

        pc = data.get("pagecount") or 1
        try:
            pc = int(pc)
        except Exception:  # noqa: BLE001
            pc = 1
        return {"list": vod_list, "page": str(pg), "pagecount": pc}

    # ------------------------------------------------------------------
    # 播放解析
    # ------------------------------------------------------------------
    def playerContent(self, flag, id, vipFlags):
        """播放：直链直接返回；自定义解析站优先；否则直链尝试 + WebView 兜底。"""
        _log("开始获取播放地址: ", id)
        try:
            if self._is_direct(id):
                return {"parse": 0, "url": id, "header": dict(self.header),
                        "playUrl": ""}

            # 1) 用户自定义解析站（extend 配置），壳子 WebView 打开解析
            if getattr(self, "custom_jx", ""):
                _log("使用自定义解析:", self.custom_jx + id)
                return {"parse": 1, "url": self.custom_jx + id,
                        "header": dict(self.header), "playUrl": ""}

            # 2) 尝试直链解析（kptv，快速失败；命中即直链播放体验最佳）
            play_url = self._parse_video_url(id)
            if play_url:
                return {"parse": 0, "url": play_url,
                        "header": dict(self.header), "playUrl": ""}

            # 3) WebView 解析站兜底：壳子用内置浏览器打开解析站播放
            web_url = self._webview_jx(id)
            if web_url:
                return {"parse": 1, "url": web_url,
                        "header": dict(self.header), "playUrl": ""}
        except Exception as exc:  # noqa: BLE001
            _log("play失败: ", exc)
        return {"parse": 1, "url": id, "header": dict(self.header),
                "playUrl": ""}

    def _webview_jx(self, video_url):
        """取第一个可用的 WebView 解析站地址。"""
        for site in (getattr(self, "parse_sites", None) or []):
            if site:
                return site + video_url
        return ""

    def _is_direct(self, url):
        s = str(url)
        return any(k in s for k in ("m3u", "mp4"))

    def _parse_video_url(self, video_url):
        """解析播放地址：请求解析源取 token，再请求 resolve 接口。"""
        parse_api = self.parse_api
        resolve_url = parse_api + video_url
        _log("正在请求解析地址:", resolve_url)

        try:
            text1 = self._http_get(resolve_url)
            token = self._extract_token(text1)
            if not token:
                raise Exception("解析源无 token")

            host = parse_api.split("//")[1].split("/")[0]
            api_url = ("https://" + host + "/api/resolve.php?token=" +
                       _enc(token))
            text2 = self._http_get(api_url)
            data = json.loads(text2) if text2 else {}
            play_url = self._format_url(data.get("url"))

            if not play_url:
                raise Exception("解析源链接为空")

            _log("解析成功并返回 ->", play_url)
            return play_url
        except Exception as exc:  # noqa: BLE001
            _log("解析失败: ", exc)
            return ""

    @staticmethod
    def _extract_token(text):
        m = re.search(r'apiToken\s*:\s*["\']([^"\']+)["\']', text or "")
        return m.group(1) if m else None

    @staticmethod
    def _format_url(url):
        if not url:
            return ""
        url = str(url).replace("\\", "")
        url = re.sub(r"^(https?:\/)((?!\/))", r"\1/", url,
                     flags=re.IGNORECASE)
        return url

    @staticmethod
    def _to_key(tid):
        """把数字 type_id 映射回接口字母参数；字母原样返回。"""
        if tid is None:
            return None
        s = str(tid).strip()
        if s in _CATEGORY:
            return _CATEGORY[s][0]
        if s in _KEY_TO_NUM:
            return s
        return s
