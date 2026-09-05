# -*- coding: utf-8 -*-
"""
青蛙影院 Python Spider — 兼容 FongMi/TV (T3) 与 WebHomeTV / PeekPro (T4)
站点: https://www.xamddegree.com/
"""

import sys
import json
import re
import time
import base64
import hashlib

sys.path.append('..')

# ===== 兼容导入 =====
try:
    from base.spider import Spider
except ImportError:
    class Spider:
        def fetch(self, url, headers=None, **kw):
            import requests as _rq
            timeout = kw.pop('timeout', 15)
            r = _rq.get(url, headers=headers, timeout=timeout, verify=False, **kw)
            r.encoding = 'utf-8'
            return r

try:
    import requests as _rq
    _HAS_RQ = True
except ImportError:
    _HAS_RQ = False

from urllib.parse import quote, unquote, urlencode


# ============================================================
# 常量
# ============================================================

HOST = "https://www.xamddegree.com"
# 注意: 必须使用移动端 UA，桌面 UA 会被站点挂起无响应
UA = "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

# 搜索验证页特征
_SLIDER_MARK = "滑动验证"

# 线路显示名映射（站点tab名无意义，映射为真实资源源名）
# 实测: 线路一=rym3u8(睿映)、线路二=bfzym3u8(暴风)，单线路片仅显示对应tab名
LINE_NAMES = {
    "线路一": "睿映资源",
    "线路二": "暴风资源",
}

# 分类列表（type_id 为站点混淆后的分类ID，取自导航）
CLASSES = [
    {"type_name": "电影", "type_id": "H1111H"},
    {"type_name": "连续剧", "type_id": "s1111H"},
    {"type_name": "综艺", "type_id": "01111H"},
    {"type_name": "动漫", "type_id": "31111H"},
    {"type_name": "短剧", "type_id": "E1111H"},
    {"type_name": "动作片", "type_id": "d1111H"},
    {"type_name": "喜剧片", "type_id": "c1111H"},
    {"type_name": "科幻片", "type_id": "T1111H"},
    {"type_name": "国产剧", "type_id": "j1111H"},
    {"type_name": "港台剧", "type_id": "x1111H"},
    {"type_name": "欧美剧", "type_id": "M1111H"},
    {"type_name": "日韩剧", "type_id": "w1111H"},
]

# 通用年份筛选器
_YEAR_FILTER = {"key": "year", "name": "年份", "value": [
    {"n": "全部", "v": ""},
    {"n": "2026", "v": "2026"},
    {"n": "2025", "v": "2025"},
    {"n": "2024", "v": "2024"},
    {"n": "2023", "v": "2023"},
    {"n": "2022", "v": "2022"},
    {"n": "2021", "v": "2021"},
    {"n": "2020", "v": "2020"},
]}

# 各父级分类的类型子分类（取自站点分类页筛选UI，已验证）
_MOVIE_TYPES = ["喜剧", "爱情", "恐怖", "动作", "科幻", "剧情", "战争",
                "警匪", "犯罪", "动画", "奇幻", "武侠"]
_DRAMA_TYPES = ["古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪",
                "动作", "奇幻", "剧情", "历史"]
_SHOW_TYPES = ["选秀", "情感", "访谈", "播报", "旅游", "音乐",
               "美食", "纪实", "曲艺", "生活"]
_ANIME_TYPES = ["情感", "科幻", "热血", "推理", "搞笑", "冒险",
                "萝莉", "校园", "动作", "机战", "运动", "战争"]
_SHORT_TYPES = ["都市", "现代", "穿越", "年代", "言情", "爱情",
                "重生", "总裁", "反转", "剧情"]

_CLASS_FILTERS = {
    "H1111H": _MOVIE_TYPES, "d1111H": _MOVIE_TYPES, "c1111H": _MOVIE_TYPES, "T1111H": _MOVIE_TYPES,
    "s1111H": _DRAMA_TYPES, "j1111H": _DRAMA_TYPES, "x1111H": _DRAMA_TYPES,
    "M1111H": _DRAMA_TYPES, "w1111H": _DRAMA_TYPES,
    "01111H": _SHOW_TYPES,
    "31111H": _ANIME_TYPES,
    "E1111H": _SHORT_TYPES,
}

# 构建各分类的完整筛选器
FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    types = [{"n": "全部", "v": ""}] + [{"n": t, "v": t} for t in _CLASS_FILTERS.get(tid, [])]
    FILTERS[tid] = [
        {"key": "class", "name": "类型", "value": types},
        _YEAR_FILTER,
    ]


# ============================================================
# Spider 主类
# ============================================================

class Spider(Spider):

    def getName(self):
        return "青蛙影院"

    # ===== 初始化 =====
    def init(self, extend=""):
        if isinstance(extend, list):
            self.extend = ""
        else:
            self.extend = extend or ""

        self.header = {
            "User-Agent": UA,
            "Referer": HOST + "/",
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }

        # requests 会话优先（搜索验证依赖 cookie 持久化）
        self._sess = None
        if _HAS_RQ:
            try:
                import urllib3
                urllib3.disable_warnings()
            except Exception:
                pass
            self._sess = _rq.Session()
            self._sess.headers.update(self.header)
            self._sess.verify = False

        # 首页缓存（5 分钟）
        self._home_cache = []
        self._home_cache_time = 0

        # 详情/分类缓存（LRU，10 分钟，加速二次进入）
        self._detail_cache = {}
        self._detail_cache_time = {}
        self._cat_cache = {}
        self._cat_cache_time = {}

    # ===== 网络工具 =====
    def _get(self, url, referer=None, timeout=8, retry=1):
        """GET 请求返回文本，空响应自动快速重试（移动端 UA 强制）"""
        headers = dict(self.header)
        if referer:
            headers["Referer"] = referer
        text = ""
        for attempt in range(retry + 1):
            try:
                if self._sess is not None:
                    rsp = self._sess.get(url, headers=headers, timeout=timeout)
                    rsp.encoding = "utf-8"
                    text = rsp.text
                else:
                    rsp = self.fetch(url, headers=headers, timeout=timeout)
                    try:
                        text = rsp.text
                    except Exception:
                        text = rsp.content.decode("utf-8", "ignore")
                if text:
                    return text
            except Exception:
                text = ""
            if attempt < retry:
                time.sleep(0.3)
        return text

    def _match(self, pattern, text, flags=0):
        m = re.search(pattern, text, flags)
        return m.group(1) if m else ""

    def _strip_tags(self, s):
        return re.sub(r'<[^>]+>', '', s or '').strip()

    # ===== 滑动验证破解 =====
    # 验证JS逻辑: value 每字符 charCode+1 拼接 → md5 → 请求 yanzheng php 种 cookie
    def _crack_slider(self, html):
        """破解搜索滑动验证，成功返回 True"""
        m = re.search(r'src="(/huadong_[^"]+\.js)\?id=(\d+)"', html)
        if not m:
            return False
        js_path, ts = m.group(1), m.group(2)
        js = self._get(HOST + js_path + "?id=" + ts, referer=HOST + "/search.html")
        if not js:
            return False

        key = js_path.rsplit("_", 1)[-1].replace(".js", "")
        mv = re.search(r'value\s*=\s*"([^"]+)"', js)
        mp = re.search(r'c\.get\("(/[a-z0-9_]+_yanzheng_huadong\.php)\?type=([a-f0-9]+)&key="', js)
        if not (mv and mp):
            return False

        sign_src = "".join(str(ord(c) + 1) for c in mv.group(1))
        sign = hashlib.md5(sign_src.encode("utf-8")).hexdigest()

        verify_url = "%s%s?type=%s&key=%s&value=%s" % (
            HOST, mp.group(1), mp.group(2), key, sign)
        self._get(verify_url, referer=HOST + "/search.html")
        return True

    # ===== 媒体判断 =====
    def _is_direct_media(self, url):
        url = (url or "").lower()
        return ".m3u8" in url or ".mp4" in url or ".flv" in url or ".mkv" in url

    def _fix_pic(self, pic):
        pic = pic or ""
        if pic.startswith("//"):
            pic = "https:" + pic
        return pic

    # ===== 卡片解析 =====
    def _parse_cards(self, html):
        """解析列表页/搜索页/首页的视频卡片 → TVBox 格式"""
        vods = []
        if not html:
            return vods
        for m in re.finditer(r'<a[^>]+class="[^"]*stui-vodlist__thumb[^"]*"[^>]*>.*?</a>', html, re.S):
            block = m.group(0)
            href = self._match(r'href="(/qingwa/(\d+)\.html)"', block)
            if not href:
                continue
            vid = self._match(r'href="/qingwa/(\d+)\.html"', block)
            name = self._match(r'title="([^"]*)"', block)
            pic = self._fix_pic(self._match(r'data-original="([^"]*)"', block))
            remark = self._match(r'pic-text[^>]*>\s*(?:<b>)?([^<]*)', block)
            if not name:
                name = self._strip_tags(self._match(r'title="[^"]*"[^>]*>\s*(?:<[^>]+>\s*)*([^<]+)', block))
            if not remark:
                remark = "HD"
            vods.append({
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": remark.strip() or "HD",
            })
        return vods

    # ===== 分类URL构造 =====
    # 无筛选 → /vodtype/{tid}-{pg}.html（稳定路由）
    # 有筛选 → vodshow 12段式（含tid共12段, 11个分隔符）:
    #   段0=tid 段3=class 段8=page 段11=year → {tid}---{class}----{page}---{year}.html
    def _build_url(self, tid, page, cls="", year=""):
        if not cls and not year:
            return "%s/vodtype/%s-%d.html" % (HOST, tid, page)
        segs = [""] * 12
        segs[0] = tid
        segs[3] = quote(cls) if cls else ""
        segs[8] = str(page) if page and int(page) > 1 else ""
        segs[11] = year or ""
        return HOST + "/vodshow/" + "-".join(segs) + ".html"

    # ============================================================
    # 首页
    # ============================================================

    def homeContent(self, filter):
        return {
            "class": CLASSES,
            "filters": FILTERS,
        }

    def homeVideoContent(self):
        """首页推荐：解析首页全部推荐卡片，带5分钟缓存"""
        now = int(time.time())
        if self._home_cache and now - self._home_cache_time < 300:
            return {"list": self._home_cache[:72]}

        html = self._get(HOST + "/", timeout=12)
        vods = self._parse_cards(html)

        self._home_cache = vods[:72]
        self._home_cache_time = now
        return {"list": self._home_cache}

    # ============================================================
    # 分类列表
    # ============================================================

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg or 1)
            if page < 1:
                page = 1

            # 解析 extend
            ext = {}
            if extend:
                if isinstance(extend, dict):
                    ext = extend
                elif isinstance(extend, str):
                    try:
                        ext = json.loads(extend)
                    except Exception:
                        ext = {}

            # 缓存命中（5 分钟，翻页回退秒回）
            key = "%s|%d|%s|%s" % (tid, page, ext.get("class", ""), ext.get("year", ""))
            now = int(time.time())
            cached = self._cat_cache.get(key)
            if cached and now - self._cat_cache_time.get(key, 0) < 300:
                return dict(cached)

            url = self._build_url(tid, page, ext.get("class", ""), ext.get("year", ""))
            html = self._get(url)

            vods = self._parse_cards(html)
            if not vods:
                return {"page": page, "pagecount": 1, "limit": 20, "total": 0, "list": []}

            # 下一页存在 → pagecount = page+1（支持无限翻页）
            pagecount = page
            if re.search(r'<a[^>]+href="[^"]*"[^>]*>\s*下一页', html):
                pagecount = page + 1

            result = {
                "list": vods,
                "page": page,
                "pagecount": pagecount,
                "limit": len(vods),
                "total": len(vods) * pagecount,
            }

            # 写入缓存（简易淘汰，最多保留 40 个键）
            if len(self._cat_cache) >= 40:
                oldest = min(self._cat_cache_time, key=self._cat_cache_time.get)
                self._cat_cache.pop(oldest, None)
                self._cat_cache_time.pop(oldest, None)
            self._cat_cache[key] = dict(result)
            self._cat_cache_time[key] = now

            return result
        except Exception:
            return {"page": 1, "pagecount": 1, "limit": 20, "total": 0, "list": []}

    # ============================================================
    # 详情页
    # ============================================================

    def _grab(self, html, label):
        """提取 '地区：美国' 这类字段值"""
        return self._strip_tags(
            self._match(label + r'[：:]\s*(?:</?[a-z][^>]*>)*\s*([^<\n&]*)', html)).strip()

    @staticmethod
    def _ep_sort_key(ep):
        """选集排序键：按播放URL中的集数序号(nid)升序

        站点源码选集为倒序渲染（最新集在前），按 nid 排序可稳定恢复正序，
        且对正序页面无副作用。
        """
        m = re.search(r'-(\d+)\.html', ep[0])
        return int(m.group(1)) if m else 0

    def _parse_playlists(self, html):
        """解析线路tab与选集 → (play_from, play_url)

        - tab 名映射为真实资源源名（LINE_NAMES）
        - 选集按 nid 升序（站点默认倒序展示）
        - playlist 按下一个 playlist 边界切分，避免嵌套 div 截断丢集
        """
        tabs = re.findall(r'href="#playlist(\d+)"[^>]*>([^<]+)</a>', html)
        if not tabs:
            return [], []

        positions = {}
        for num, _ in tabs:
            positions[num] = html.find('<div id="playlist%s"' % num)

        play_from = []
        play_url = []
        for num, tab_name in tabs:
            start = positions.get(num, -1)
            if start < 0:
                continue
            # 段边界：下一个出现的 playlist div（或页面尾）
            nxt = [p for n, p in positions.items() if p > start]
            end = min(nxt) if nxt else len(html)
            seg = html[start:end]

            eps = re.findall(r'href="(/qingwaplay/\d+-\d+-\d+\.html)"[^>]*>([^<]+)</a>', seg)
            if not eps:
                continue
            eps.sort(key=self._ep_sort_key)
            ep_list = ["%s$%s" % (ep_name.strip(), ep_href) for ep_href, ep_name in eps]

            name = tab_name.strip()
            play_from.append(LINE_NAMES.get(name, name))
            play_url.append("#".join(ep_list))

        return play_from, play_url

    def detailContent(self, ids):
        if isinstance(ids, str):
            ids = [ids]
        vod_id = str(ids[0])

        # 缓存命中 → 秒回（二次进入详情/换集场景）
        now = int(time.time())
        cached = self._detail_cache.get(vod_id)
        if cached and now - self._detail_cache_time.get(vod_id, 0) < 600:
            return {"list": [dict(cached)]}

        html = self._get(HOST + "/qingwa/" + vod_id + ".html")
        if not html:
            return {"list": []}

        # 基础字段
        name = self._strip_tags(self._match(r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>([^<]*)</h1>', html))
        if not name:
            name = self._strip_tags(self._match(r'<title>([^<-]*)', html))
        pic = self._fix_pic(self._match(r'data-original="([^"]*)"', html))
        remark = self._grab(html, "状态") or "HD"
        type_name = self._grab(html, "类型")
        area = self._grab(html, "地区")
        year = self._match(r'年份[：:]\s*(?:</?[a-z][^>]*>)*\s*(\d{4})', html)
        lang = self._grab(html, "语言")

        # 导演 / 主演（a 标签文本拼接）
        dm = re.search(r'导演[：:]\s*(.*?)(?:</p>|<p|$)', html, re.S)
        director = self._strip_tags(re.sub(r'<[^>]+>', ' ', dm.group(1))) if dm else ""
        am = re.search(r'主演[：:]\s*(.*?)(?:</p>|<p|$)', html, re.S)
        actor = self._strip_tags(re.sub(r'<[^>]+>', ' ', am.group(1))) if am else ""
        actor = re.sub(r'\s{2,}', ' ', actor)

        # 简介（完整版优先，截断版兜底）
        content = self._strip_tags(self._match(
            r'detail-content"[^>]*>([^<]*)', html)) or \
            self._strip_tags(self._match(
                r'detail-sketch"[^>]*>([^<]*)', html))
        content = content[:500]

        # 线路与选集
        play_from, play_url = self._parse_playlists(html)

        if not play_url:
            return {"list": []}

        vod = {
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "type_name": type_name,
            "vod_year": year,
            "vod_area": area,
            "vod_language": lang,
            "vod_remarks": remark,
            "vod_actor": actor,
            "vod_director": director,
            "vod_content": content,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }

        # 写入缓存（LRU 简易淘汰，最多保留 30 条）
        if len(self._detail_cache) >= 30:
            oldest = min(self._detail_cache_time, key=self._detail_cache_time.get)
            self._detail_cache.pop(oldest, None)
            self._detail_cache_time.pop(oldest, None)
        self._detail_cache[vod_id] = dict(vod)
        self._detail_cache_time[vod_id] = now

        return {"list": [vod]}

    # ============================================================
    # 搜索
    # ============================================================

    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg or 1)
            if page < 1:
                page = 1

            url = HOST + "/search.html?" + urlencode({"wd": key, "page": page})
            html = self._get(url, referer=HOST + "/", timeout=15)

            # 滑动验证 → 自动破解后重试一次
            if _SLIDER_MARK in html:
                if self._crack_slider(html):
                    time.sleep(0.3)
                    html = self._get(url, referer=HOST + "/", timeout=15)

            if not html or _SLIDER_MARK in html:
                return {"list": []}

            vods = self._parse_cards(html)
            return {"list": vods}
        except Exception:
            return {"list": []}

    # ============================================================
    # 播放解析
    # ============================================================

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 0, "playUrl": "", "url": ""}

        play_url = str(id).replace("\\/", "/")
        if not play_url.startswith("http"):
            play_url = HOST + play_url

        html = self._get(play_url, referer=HOST + "/", timeout=12)

        # player_aaaa 变量 → 直链
        m = re.search(r'player_aaaa\s*=\s*(\{.*?\})\s*</script>', html, re.S)
        if m:
            try:
                data = json.loads(m.group(1))
                url = data.get("url", "") or ""
                enc = int(data.get("encrypt", 0) or 0)
                if enc == 1:
                    url = unquote(url)
                elif enc == 2:
                    try:
                        url = unquote(base64.b64decode(url).decode("utf-8", "ignore"))
                    except Exception:
                        url = ""
                url = url.replace("\\/", "/")

                if url and self._is_direct_media(url):
                    is_m3u8 = ".m3u8" in url.lower()
                    return {
                        "parse": 0,
                        "playUrl": "",
                        "url": url,
                        "header": {
                            "User-Agent": UA,
                            "Referer": HOST + "/",
                        },
                        "format": "application/x-mpegURL" if is_m3u8 else "",
                        "contentType": "application/x-mpegURL" if is_m3u8 else "",
                    }
            except Exception:
                pass

        # 提取失败 → 交给壳子用播放页嗅探
        return {
            "parse": 1,
            "playUrl": "",
            "url": play_url,
            "header": {
                "User-Agent": UA,
                "Referer": HOST + "/",
            },
        }

    # ===== 本地代理 =====
    def localProxy(self, param):
        return [200, "video/MP2T", b"", ""]

    # ===== 清理 =====
    def destroy(self):
        self._home_cache = []
        self._detail_cache = {}
        self._detail_cache_time = {}
        self._cat_cache = {}
        self._cat_cache_time = {}
        if self._sess is not None:
            try:
                self._sess.close()
            except Exception:
                pass
        self._sess = None

    def close(self):
        self.destroy()
