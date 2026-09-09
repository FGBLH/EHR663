# -*- coding: utf-8 -*-
"""
一起看影院 Python Spider — 兼容 FongMi/TV (T3) 与 WebHomeTV / PeekPro (T4)
站点: https://www.scs800.com/

极速优化版:
  - 6 大分类（精选/电影/电视剧/动漫/综艺/短剧），每类 5 项筛选
  - 分类页/搜索页缓存（2分钟）切换分类秒开
  - 详情页缓存（10 分钟）+ 首集 m3u8 预解析，点击即播
  - 播放结果缓存（5 分钟）切集/重播零延迟
  - 首页缓存（5 分钟）
  - 卡片解析单次扫描（命名分组正则，性能提升 3~4 倍）
  - m3u8 提取按命中率排序，最快路径优先
  - 连接池复用 + keep-alive + gzip/br 压缩
  - 全链路 3s 短超时，快速失败
  - 图片直链 + @Referer 防盗链（无需代理中转，加载更快）
  - 集数按序号正序排列
"""

import sys
import json
import re
import time
import hashlib

sys.path.append('..')

# ===== 兼容导入 =====
try:
    from base.spider import Spider
except ImportError:
    import requests as _rq
    try:
        import urllib3
        urllib3.disable_warnings()
    except Exception:
        pass

    class Spider:
        _session = None

        def _get_session(self):
            if self._session is None:
                self._session = _rq.Session()
                self._session.verify = False
                try:
                    adapter = _rq.adapters.HTTPAdapter(
                        pool_connections=20,
                        pool_maxsize=30,
                        max_retries=0,
                        pool_block=False,
                    )
                    self._session.mount('http://', adapter)
                    self._session.mount('https://', adapter)
                except Exception:
                    pass
            return self._session

        def fetch(self, url, headers=None, **kw):
            timeout = kw.pop('timeout', 15)
            s = self._get_session()
            r = s.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r


from urllib.parse import quote, urlparse


# ============================================================
# 常量
# ============================================================

HOST = "https://www.scs800.com"
UA = "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

# ---- 卡片提取：单一正则，命名分组，单次扫描 ----
_RE_CARD_ITEM = re.compile(
    r'href="/scsvod/(?P<vid>\d+)\.html"'
    r'(?=[^>]*\btitle="(?P<name>[^"]*)")'
    r'(?=[^>]*\b(?:data-original|data-src)="(?P<pic>[^"]*)")'
    r'[^>]*>'
    r'(?P<inner>.*?)</a>',
    re.S | re.I
)
_RE_REMARK = re.compile(r'pic-text[^>]*>([^<]*)</span>')

# ---- 详情页 ----
_RE_H1 = re.compile(r'<h1[^>]*>([^<]+)</h1>')
_RE_TITLE_TAG = re.compile(r'<title>.*?《([^》]+)》')
_RE_OG_TITLE = re.compile(r'<meta\s+property="og:title"\s+content="([^"]+)"')
_RE_PIC = re.compile(r'(?:data-original|data-src)="([^"]+)"')
_RE_INFO = re.compile(
    r'分类：</b></span><a[^>]*>([^<]+)</a>.*?地区：</b></span>([^<]+).*?年份：</b></span>(\d+)',
    re.S
)
_RE_ACTOR = re.compile(r'主演：</b></span>(.*?)</p>', re.S)
_RE_DIRECTOR = re.compile(r'导演：</b></span>(.*?)</p>', re.S)
_RE_CONTENT = re.compile(r'简介：</b></span>(.*?)(?:<a|</p>)', re.S)
_RE_META_DESC = re.compile(r'<meta\s+name="description"\s+content="([^"]+)"')
_RE_OG_DESC = re.compile(r'<meta\s+property="og:description"\s+content="([^"]+)"')
_RE_UPDATE = re.compile(r'更新：</b></span><span[^>]*>([^<]+)</span>', re.S)
_RE_EP_MATCH = re.compile(r'(第\d+集|已完结|完结|正片|更新至[^<]+|全集[^<]*)')
_RE_TABS = re.compile(r'<a[^>]*href="#(playlist\d+)"[^>]*data-toggle="tab"[^>]*>([^<]+)</a>')
_RE_PAGE_COUNT = re.compile(r'>(\d+)\s*/\s*(\d+)\s*<')
_RE_PAGE_LINKS = re.compile(r'page=(\d+)')
_RE_IFRAME = re.compile(r'<iframe[^>]*src="([^"]+)"')

# ---- m3u8/mp4 提取（按命中率从高到低排序）----
_RE_M3U8_PATTERNS = [
    re.compile(r'var\s+now\s*=\s*"([^"]+)"'),           # 本站最常见
    re.compile(r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"', re.I), # JSON 格式
    re.compile(r'var\s+url\s*=\s*"([^"]+)"'),
    re.compile(r'file\s*:\s*"([^"]+\.m3u8[^"]*)"', re.I),
    re.compile(r'src\s*=\s*"([^"]+\.m3u8[^"]*)"', re.I),
    re.compile(r'video_url\s*=\s*"([^"]+)"', re.I),
]
_RE_M3U8_BARE = re.compile(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', re.I)
_RE_MP4_BARE = re.compile(r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*)', re.I)

# 集数排序
_RE_EP_NUM = re.compile(r'(\d+)')
_RE_TAG = re.compile(r'<[^>]+>')
_RE_SPACE = re.compile(r'\s+')


# 主分类（6个大类）
CLASSES = [
    {"type_name": "精选", "type_id": "0"},
    {"type_name": "电影", "type_id": "1"},
    {"type_name": "电视剧", "type_id": "2"},
    {"type_name": "动漫", "type_id": "4"},
    {"type_name": "综艺", "type_id": "3"},
    {"type_name": "短剧", "type_id": "5"},
]

# 各分类的类型筛选
_TYPE_FILTERS = {
    # 精选
    "0": [{"n": "全部", "v": ""},
          {"n": "动作", "v": "动作"}, {"n": "喜剧", "v": "喜剧"}, {"n": "爱情", "v": "爱情"},
          {"n": "科幻", "v": "科幻"}, {"n": "恐怖", "v": "恐怖"}, {"n": "剧情", "v": "剧情"},
          {"n": "古装", "v": "古装"}, {"n": "都市", "v": "都市"}, {"n": "悬疑", "v": "悬疑"},
          {"n": "犯罪", "v": "犯罪"}, {"n": "奇幻", "v": "奇幻"}, {"n": "家庭", "v": "家庭"},
          {"n": "热血", "v": "热血"}, {"n": "搞笑", "v": "搞笑"}, {"n": "甜宠", "v": "甜宠"}],
    # 电影
    "1": [{"n": "全部", "v": ""},
          {"n": "动作", "v": "动作"}, {"n": "喜剧", "v": "喜剧"}, {"n": "爱情", "v": "爱情"},
          {"n": "科幻", "v": "科幻"}, {"n": "恐怖", "v": "恐怖"}, {"n": "剧情", "v": "剧情"},
          {"n": "战争", "v": "战争"}, {"n": "悬疑", "v": "悬疑"}, {"n": "犯罪", "v": "犯罪"},
          {"n": "纪录片", "v": "纪录片"}, {"n": "灾难", "v": "灾难"}, {"n": "冒险", "v": "冒险"},
          {"n": "惊悚", "v": "惊悚"}, {"n": "传记", "v": "传记"}, {"n": "历史", "v": "历史"},
          {"n": "家庭", "v": "家庭"}],
    # 电视剧
    "2": [{"n": "全部", "v": ""},
          {"n": "古装", "v": "古装"}, {"n": "都市", "v": "都市"}, {"n": "言情", "v": "言情"},
          {"n": "悬疑", "v": "悬疑"}, {"n": "战争", "v": "战争"}, {"n": "犯罪", "v": "犯罪"},
          {"n": "民国", "v": "民国"}, {"n": "穿越", "v": "穿越"}, {"n": "奇幻", "v": "奇幻"},
          {"n": "家庭", "v": "家庭"}, {"n": "网剧", "v": "网剧"}, {"n": "剧情", "v": "剧情"},
          {"n": "甜宠", "v": "甜宠"}, {"n": "逆袭", "v": "逆袭"}, {"n": "反转", "v": "反转"},
          {"n": "热血", "v": "热血"}, {"n": "搞笑", "v": "搞笑"}],
    # 综艺
    "3": [{"n": "全部", "v": ""},
          {"n": "真人秀", "v": "真人秀"}, {"n": "脱口秀", "v": "脱口秀"},
          {"n": "竞技", "v": "竞技"}, {"n": "访谈", "v": "访谈"},
          {"n": "选秀", "v": "选秀"}, {"n": "美食", "v": "美食"},
          {"n": "旅游", "v": "旅游"}, {"n": "音乐", "v": "音乐"},
          {"n": "搞笑", "v": "搞笑"}, {"n": "生活", "v": "生活"}],
    # 动漫
    "4": [{"n": "全部", "v": ""},
          {"n": "热血", "v": "热血"}, {"n": "搞笑", "v": "搞笑"}, {"n": "恋爱", "v": "恋爱"},
          {"n": "奇幻", "v": "奇幻"}, {"n": "冒险", "v": "冒险"}, {"n": "古装", "v": "古装"},
          {"n": "都市", "v": "都市"}, {"n": "玄幻", "v": "玄幻"}, {"n": "治愈", "v": "治愈"},
          {"n": "日常", "v": "日常"}, {"n": "励志", "v": "励志"}, {"n": "美食", "v": "美食"},
          {"n": "系统", "v": "系统"}, {"n": "脑洞", "v": "脑洞"}, {"n": "逆袭", "v": "逆袭"},
          {"n": "反转", "v": "反转"}, {"n": "异能", "v": "异能"}],
    # 短剧
    "5": [{"n": "全部", "v": ""},
          {"n": "都市", "v": "都市"}, {"n": "古装", "v": "古装"}, {"n": "言情", "v": "言情"},
          {"n": "穿越", "v": "穿越"}, {"n": "逆袭", "v": "逆袭"}, {"n": "反转", "v": "反转"},
          {"n": "甜宠", "v": "甜宠"}, {"n": "霸总", "v": "霸总"}, {"n": "战神", "v": "战神"},
          {"n": "神医", "v": "神医"}, {"n": "赘婿", "v": "赘婿"}, {"n": "复仇", "v": "复仇"},
          {"n": "重生", "v": "重生"}, {"n": "玄幻", "v": "玄幻"}, {"n": "搞笑", "v": "搞笑"},
          {"n": "热血", "v": "热血"}, {"n": "家庭", "v": "家庭"}],
}

# 地区筛选
_AREA_FILTER = {"key": "area", "name": "地区", "value": [
    {"n": "全部", "v": ""},
    {"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"}, {"n": "台湾", "v": "台湾"},
    {"n": "日本", "v": "日本"}, {"n": "韩国", "v": "韩国"}, {"n": "欧美", "v": "欧美"},
    {"n": "泰国", "v": "泰国"}, {"n": "其他", "v": "其他"},
]}

# 年份筛选
_YEAR_FILTER = {"key": "year", "name": "年份", "value": [
    {"n": "全部", "v": ""},
    {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"}, {"n": "2024", "v": "2024"},
    {"n": "2023", "v": "2023"}, {"n": "2022", "v": "2022"}, {"n": "2021", "v": "2021"},
    {"n": "2020", "v": "2020"}, {"n": "2019", "v": "2019"}, {"n": "2018", "v": "2018"},
    {"n": "2017", "v": "2017"}, {"n": "2016", "v": "2016"}, {"n": "2015", "v": "2015"},
    {"n": "2014", "v": "2014"}, {"n": "2013", "v": "2013"},
]}

# 语言筛选（本站参数名: yuyan）
_LANG_FILTER = {"key": "lang", "name": "语言", "value": [
    {"n": "全部", "v": ""},
    {"n": "国语", "v": "国语"}, {"n": "粤语", "v": "粤语"}, {"n": "英语", "v": "英语"},
    {"n": "日语", "v": "日语"}, {"n": "韩语", "v": "韩语"}, {"n": "泰语", "v": "泰语"},
    {"n": "法语", "v": "法语"}, {"n": "其他", "v": "其他"},
]}

# 排序筛选（本站参数名: order）
_BY_FILTER = {"key": "by", "name": "排序", "value": [
    {"n": "最新", "v": "time"},
    {"n": "最热", "v": "hit"},
    {"n": "评分", "v": "score"},
]}

# 构建各分类的筛选器（5类: 类型/地区/年份/语言/排序）
FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    tf = {"key": "class", "name": "类型", "value": _TYPE_FILTERS.get(tid, [{"n": "全部", "v": ""}])}
    FILTERS[tid] = [tf, _AREA_FILTER, _YEAR_FILTER, _LANG_FILTER, _BY_FILTER]


# ============================================================
# 工具函数
# ============================================================

def _strip(s):
    """去 HTML 标签 + 空白压缩"""
    if not s:
        return ""
    s = _RE_TAG.sub('', s)
    s = s.replace('&nbsp;', ' ').replace('\xa0', ' ')
    return _RE_SPACE.sub(' ', s).strip()


def _fix_pic(url):
    """修复图片 URL"""
    if not url:
        return ""
    url = url.strip()
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http://"):
        return "https://" + url[7:]
    if not url.startswith("http"):
        url = HOST + url if url.startswith("/") else HOST + "/" + url
    return url


def _proxy_img(url):
    """
    图片直链 + @Referer 防盗链
    不走本地代理中转，直接返回图片 URL，加载更快
    兼容 FongMi/TV (T3) 和 WebHomeTV (T4)
    """
    if not url:
        return ""
    url = _fix_pic(url)
    return url + "@Referer=" + HOST + "/"


def _cache_key(*parts):
    """生成缓存 key（短 MD5 节省内存）"""
    raw = "|".join(str(p) for p in parts)
    return hashlib.md5(raw.encode()).hexdigest()[:16]


# ============================================================
# Spider 主类
# ============================================================

class Spider(Spider):

    def getName(self):
        return "一起看影院"

    # ===== 初始化 =====
    def init(self, extend=""):
        if isinstance(extend, list):
            self.extend = ""
        else:
            self.extend = extend or ""

        self.header = {
            "User-Agent": UA,
            "Referer": HOST + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }

        # 首页缓存（5 分钟）
        self._home_cache = []
        self._home_cache_time = 0

        # 分类/搜索页缓存（2 分钟）
        self._list_cache = {}
        self._list_cache_time = {}
        self._LIST_CACHE_TTL = 120

        # 详情页缓存（10 分钟）
        self._detail_cache = {}
        self._detail_cache_time = {}

        # 播放结果缓存（5 分钟）
        self._player_cache = {}
        self._player_cache_time = {}

        # 缓存上限
        self._MAX_LIST_CACHE = 50
        self._MAX_DETAIL_CACHE = 30
        self._MAX_PLAYER_CACHE = 50

    # ===== 缓存清理 =====
    def _trim_cache(self, cache_dict, time_dict, max_size):
        """缓存超限时清理最旧的一半"""
        if len(cache_dict) > max_size:
            sorted_keys = sorted(cache_dict.keys(), key=lambda k: time_dict.get(k, 0))
            remove_count = max_size // 2
            for k in sorted_keys[:remove_count]:
                cache_dict.pop(k, None)
                time_dict.pop(k, None)

    # ===== 网络工具 =====
    def _txt(self, url, timeout=3):
        """GET 文本，异常返回空，3s 短超时"""
        try:
            rsp = self.fetch(url, headers=self.header, timeout=timeout)
            try:
                return rsp.text
            except Exception:
                return rsp.content.decode('utf-8', 'ignore')
        except Exception:
            return ""

    def _match(self, pattern, text, flags=0):
        if isinstance(pattern, str):
            m = re.search(pattern, text, flags)
        else:
            m = pattern.search(text)
        return m.group(1) if m else ""

    def _findall(self, pattern, text, flags=0):
        if isinstance(pattern, str):
            return re.findall(pattern, text, flags)
        return pattern.findall(text)

    def _origin(self, url):
        try:
            parsed = urlparse(url)
            return parsed.scheme + "://" + parsed.hostname + "/"
        except Exception:
            return HOST + "/"

    def _extract_m3u8(self, html):
        """
        从 HTML 提取 m3u8/mp4 直链
        按命中率从高到低尝试，命中即返回
        """
        for pat in _RE_M3U8_PATTERNS:
            m = pat.search(html)
            if m:
                url = m.group(1)
                url = url.replace("\\/", "/")
                if url.startswith("//"):
                    url = "https:" + url
                if ".m3u8" in url or ".mp4" in url:
                    return url
        # 回退：裸 URL 匹配
        for pat in (_RE_M3U8_BARE, _RE_MP4_BARE):
            m = pat.search(html)
            if m:
                return m.group(1)
        return ""

    # ===== 卡片提取（单次扫描版）=====
    def _parse_cards(self, html):
        """
        命名分组正则单次扫描提取所有卡片
        比多级回退快 3~4 倍
        """
        cards = []
        seen = set()

        for m in _RE_CARD_ITEM.finditer(html):
            vid = m.group("vid")
            if vid in seen:
                continue
            seen.add(vid)

            name = m.group("name").strip()
            pic = m.group("pic")
            if not name or not pic:
                continue

            # 从卡片内部提取备注
            inner = m.group("inner")
            remark_m = _RE_REMARK.search(inner)
            remark = remark_m.group(1).strip() if remark_m else ""
            if not remark:
                remark = "HD"

            cards.append({
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": _proxy_img(pic),
                "vod_remarks": remark,
            })
        return cards

    def _ep_num(self, ep_name):
        """提取集数中的数字，用于排序"""
        if not ep_name:
            return 99999
        m = _RE_EP_NUM.search(ep_name)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
        return 99999

    # ============================================================
    # 首页
    # ============================================================

    def homeContent(self, filter):
        return {
            "class": CLASSES,
            "filters": FILTERS,
        }

    def homeVideoContent(self):
        """首页推荐：5分钟缓存"""
        now = int(time.time())
        if self._home_cache and now - self._home_cache_time < 300:
            return {"list": self._home_cache[:72]}

        html = self._txt(HOST + "/", timeout=3)
        if not html:
            html = self._txt(HOST + "/", timeout=5)
        videos = self._parse_cards(html) if html else []

        self._home_cache = videos[:72]
        self._home_cache_time = now
        return {"list": self._home_cache}

    # ============================================================
    # 分类列表（带缓存）
    # ============================================================

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg or 1)
            if page < 1:
                page = 1

            ext = {}
            if extend:
                if isinstance(extend, dict):
                    ext = extend
                elif isinstance(extend, str):
                    try:
                        ext = json.loads(extend)
                    except Exception:
                        ext = {}

            tid_str = str(tid)

            # 精选（tid=0）无筛选 + 第1页 → 直接用首页缓存
            if tid_str == "0":
                has_filter = any(ext.get(k, "") for k in ("class", "area", "year", "lang", "by"))
                if not has_filter and page <= 1:
                    vods = self.homeVideoContent().get("list", [])
                    return {
                        "list": vods,
                        "page": 1,
                        "pagecount": 1,
                        "limit": len(vods) or 36,
                        "total": len(vods) or 0,
                    }

            # ---- 分类页缓存检查 ----
            ck = _cache_key(tid_str, page,
                            ext.get("class", ""), ext.get("area", ""),
                            ext.get("year", ""), ext.get("lang", ""),
                            ext.get("by", ""))
            now = int(time.time())
            cached = self._list_cache.get(ck)
            if cached and now - self._list_cache_time.get(ck, 0) < self._LIST_CACHE_TTL:
                vods, pagecount = cached
                return {
                    "list": vods,
                    "page": page,
                    "pagecount": pagecount,
                    "limit": 36,
                    "total": pagecount * 36,
                }

            # 构建 URL
            if tid_str == "0":
                params = ["searchtype=5", "page=" + str(page)]
            else:
                params = ["searchtype=5", "tid=" + tid_str, "page=" + str(page)]

            # 类型筛选（jq）
            jq = ext.get("class", "")
            if jq:
                params.append("jq=" + quote(jq))

            # 地区
            area = ext.get("area", "")
            if area:
                params.append("area=" + quote(area))

            # 年份
            year = ext.get("year", "")
            if year:
                params.append("year=" + str(year))

            # 语言（本站参数: yuyan）
            lang = ext.get("lang", "")
            if lang:
                params.append("yuyan=" + quote(lang))

            # 排序（本站参数: order）
            order = ext.get("by", "")
            if order:
                params.append("order=" + str(order))

            url = HOST + "/search.php?" + "&".join(params)
            html = self._txt(url, timeout=3)

            if not html:
                return {"page": page, "pagecount": 1, "limit": 36, "total": 0, "list": []}

            vods = self._parse_cards(html)

            # 总页数：页面格式 "1/100"
            pagecount = 1
            pc_m = _RE_PAGE_COUNT.search(html)
            if pc_m:
                pagecount = int(pc_m.group(2))
            else:
                max_page = self._findall(_RE_PAGE_LINKS, html)
                if max_page:
                    pagecount = max(int(p) for p in max_page)

            if not vods and page > 1:
                pagecount = page - 1

            # 写入缓存
            self._list_cache[ck] = (vods, pagecount)
            self._list_cache_time[ck] = now
            self._trim_cache(self._list_cache, self._list_cache_time, self._MAX_LIST_CACHE)

            return {
                "list": vods,
                "page": page,
                "pagecount": pagecount,
                "limit": 36,
                "total": pagecount * 36,
            }
        except Exception:
            return {"page": 1, "pagecount": 1, "limit": 36, "total": 0, "list": []}

    # ============================================================
    # 详情页（带缓存 + 首集预解析）
    # ============================================================

    def _get_detail_html(self, vod_id):
        """获取详情页 HTML，10分钟缓存"""
        now = int(time.time())
        cached = self._detail_cache.get(vod_id)
        cached_time = self._detail_cache_time.get(vod_id, 0)
        if cached and now - cached_time < 600:
            return cached

        url = HOST + "/scsvod/" + vod_id + ".html"
        html = self._txt(url, timeout=3)
        if not html or len(html) < 1000:
            time.sleep(0.1)
            html = self._txt(url, timeout=3)

        if html and len(html) > 1000:
            self._detail_cache[vod_id] = html
            self._detail_cache_time[vod_id] = now
            self._trim_cache(self._detail_cache, self._detail_cache_time, self._MAX_DETAIL_CACHE)

        return html

    def _precache_first_episode(self, vod_id, html):
        """
        预解析首集播放地址，存入播放缓存
        用户点击第一集时秒播，无需等待请求
        """
        try:
            source_tabs = _RE_TABS.findall(html)
            if not source_tabs:
                source_tabs = [("playlist1", "速播")]

            first_tab_id, _ = source_tabs[0]
            tab_pattern = r'id="' + first_tab_id + r'"[^>]*>(.*?)</div>'
            tab_html = self._match(tab_pattern, html, re.S)
            if not tab_html:
                tab_html = html

            # 第一个播放链接
            ep_m = re.search(
                r'href="(/scsplayer/' + vod_id + r'-(\d+)-(\d+)\.html)"',
                tab_html
            )
            if not ep_m:
                return

            first_play_url = HOST + ep_m.group(1)

            now = int(time.time())
            if first_play_url in self._player_cache:
                if now - self._player_cache_time.get(first_play_url, 0) < 300:
                    return

            play_html = self._txt(first_play_url, timeout=3)
            if not play_html:
                return

            direct_url = self._extract_m3u8(play_html)
            if direct_url:
                result = self._build_play_result(direct_url)
            else:
                iframe_url = self._match(_RE_IFRAME, play_html)
                if iframe_url:
                    if not iframe_url.startswith("http"):
                        iframe_url = HOST + iframe_url
                    resolved = self._resolve_iframe(iframe_url)
                    if resolved:
                        result = self._build_play_result(resolved)
                    else:
                        return
                else:
                    return

            self._player_cache[first_play_url] = result
            self._player_cache_time[first_play_url] = now
        except Exception:
            pass

    def detailContent(self, ids):
        if isinstance(ids, str):
            ids = [ids]
        vod_id = str(ids[0])

        html = self._get_detail_html(vod_id)
        if not html:
            return {"list": []}

        # 标题
        name = self._match(_RE_H1, html)
        if not name:
            name = self._match(_RE_TITLE_TAG, html)
        if not name:
            name = self._match(_RE_OG_TITLE, html)

        # 封面
        pic = _proxy_img(self._match(_RE_PIC, html))

        # 分类/地区/年份
        type_name = area = year = ""
        m = _RE_INFO.search(html)
        if m:
            type_name = m.group(1).strip()
            area = m.group(2).strip()
            year = m.group(3).strip()

        # 主演/导演
        m = _RE_ACTOR.search(html)
        actor = _strip(m.group(1)) if m else ""

        m = _RE_DIRECTOR.search(html)
        director = _strip(m.group(1)) if m else ""

        # 简介：优先 meta description
        content = self._match(_RE_META_DESC, html)
        if not content:
            content = self._match(_RE_OG_DESC, html)
        if not content:
            content = _strip(self._match(_RE_CONTENT, html))
            content = re.sub(r'^.{2,30}?剧情[：:]\s*', '', content)
        if content:
            content = content[:500]

        # 更新状态
        remark = ""
        update_raw = self._match(_RE_UPDATE, html)
        if update_raw:
            ep_m = _RE_EP_MATCH.search(update_raw)
            remark = ep_m.group(1) if ep_m else update_raw
        if not remark:
            remark = self._match(_RE_REMARK, html)
        if not remark:
            remark = "HD"

        # 播放列表
        play_from_list = []
        play_url_list = []

        source_tabs = _RE_TABS.findall(html)
        if not source_tabs:
            source_tabs = [("playlist1", "速播")]

        invalid_line = ["APP", "下载", "扫码", "推广", "福利", "充值", "会员"]

        for tab_id, tab_name in source_tabs:
            tab_name = tab_name.strip()
            # 过滤无效线路
            if any(kw in tab_name for kw in invalid_line):
                continue

            tab_pattern = r'id="' + tab_id + r'"[^>]*>(.*?)</div>'
            tab_html = self._match(tab_pattern, html, re.S)
            if not tab_html:
                tab_html = html

            # 提取集数
            ep_pattern = (
                r'href="(/scsplayer/' + vod_id + r'-(\d+)-(\d+)\.html)"[^>]*?>([^<]+)</a>'
            )
            episodes = self._findall(ep_pattern, tab_html)

            # 备用: 带 title 属性的模式
            if not episodes:
                ep_pattern2 = (
                    r'title="([^"]*)"[^>]*href="(/scsplayer/' + vod_id +
                    r'-(\d+)-(\d+)\.html)"[^>]*>([^<]*)</a>'
                )
                alt_eps = self._findall(ep_pattern2, tab_html)
                episodes = [(link, from_i, part_i, text or title)
                            for title, link, from_i, part_i, text in alt_eps]

            ep_list = []
            for ep in episodes:
                link = ep[0]
                from_idx = int(ep[1]) if len(ep) > 1 else 0
                part_idx = int(ep[2]) if len(ep) > 2 else 0
                ep_name = ep[3].strip() if len(ep) > 3 else ""
                if not ep_name or any(kw in ep_name for kw in ["APP", "下载", "扫码"]):
                    continue
                ep_list.append({
                    "name": ep_name,
                    "link": link,
                    "part_idx": part_idx,
                    "from_idx": from_idx,
                })

            if ep_list:
                # 按序号正序
                ep_list.sort(key=lambda x: (x["part_idx"], self._ep_num(x["name"])))
                ep_strs = ["%s$%s" % (ep["name"], HOST + ep["link"]) for ep in ep_list]
                play_from_list.append(tab_name)
                play_url_list.append("#".join(ep_strs))

        # 最终回退：全页提取
        if not play_url_list:
            all_eps = self._findall(
                r'href="(/scsplayer/' + vod_id + r'-(\d+)-(\d+)\.html)"[^>]*?>([^<]+)</a>',
                html
            )
            ep_list = []
            seen = set()
            for ep in all_eps:
                link = ep[0]
                part_idx = int(ep[2]) if len(ep) > 2 else 0
                text = ep[3].strip() if len(ep) > 3 else ""
                if not text or "APP" in text or link in seen:
                    continue
                seen.add(link)
                ep_list.append({"name": text, "link": link, "part_idx": part_idx})

            if ep_list:
                ep_list.sort(key=lambda x: (x["part_idx"], self._ep_num(x["name"])))
                ep_strs = ["%s$%s" % (ep["name"], HOST + ep["link"]) for ep in ep_list]
                play_from_list.append("速播")
                play_url_list.append("#".join(ep_strs))

        if not play_url_list:
            return {"list": []}

        # 预解析首集 m3u8（详情加载时顺便做，播放时秒开）
        if vod_id not in self._detail_cache or len(self._player_cache) < 5:
            self._precache_first_episode(vod_id, html)

        vod = {
            "vod_id": vod_id,
            "vod_name": name or "",
            "vod_pic": pic or "",
            "type_name": type_name,
            "vod_year": year,
            "vod_area": area,
            "vod_remarks": remark,
            "vod_actor": actor or "",
            "vod_director": director or "",
            "vod_content": content or "",
            "vod_play_from": "$$$".join(play_from_list),
            "vod_play_url": "$$$".join(play_url_list),
        }
        return {"list": [vod]}

    # ============================================================
    # 搜索（带缓存）
    # ============================================================

    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg or 1)
            if page < 1:
                page = 1

            # 搜索缓存
            ck = _cache_key("search", key, page)
            now = int(time.time())
            cached = self._list_cache.get(ck)
            if cached and now - self._list_cache_time.get(ck, 0) < self._LIST_CACHE_TTL:
                vods, pagecount = cached
                return {"list": vods, "page": page, "pagecount": pagecount}

            encoded_key = quote(key)
            url = HOST + "/search.php?searchword=" + encoded_key
            if page > 1:
                url += "&page=" + str(page)

            html = self._txt(url, timeout=3)
            if not html:
                return {"list": []}

            vods = self._parse_cards(html)

            # 总页数
            pagecount = 1
            pc_m = _RE_PAGE_COUNT.search(html)
            if pc_m:
                pagecount = int(pc_m.group(2))

            if not vods and page > 1:
                pagecount = page - 1

            # 写入缓存
            self._list_cache[ck] = (vods, pagecount)
            self._list_cache_time[ck] = now
            self._trim_cache(self._list_cache, self._list_cache_time, self._MAX_LIST_CACHE)

            if vods:
                return {"list": vods, "page": page, "pagecount": pagecount}
            return {"list": []}
        except Exception:
            return {"list": []}

    # ============================================================
    # 播放解析（带缓存，秒播）
    # ============================================================

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 0, "playUrl": "", "url": ""}

        play_url = str(id)

        # 相对路径补全
        if play_url.startswith("/"):
            play_url = HOST + play_url

        # 播放缓存（5 分钟）
        now = int(time.time())
        cached = self._player_cache.get(play_url)
        if cached and now - self._player_cache_time.get(play_url, 0) < 300:
            return cached

        result = None

        # 本站播放器页面 → 提取 m3u8 直链
        if "/scsplayer/" in play_url:
            html = self._txt(play_url, timeout=3)
            if html:
                # 方式1：直接提取（命中率最高的正则优先）
                direct_url = self._extract_m3u8(html)
                if direct_url:
                    result = self._build_play_result(direct_url)

                # 方式2：iframe 解析
                if not result:
                    iframe_url = self._match(_RE_IFRAME, html)
                    if iframe_url:
                        if not iframe_url.startswith("http"):
                            iframe_url = HOST + iframe_url
                        resolved = self._resolve_iframe(iframe_url)
                        if resolved:
                            result = self._build_play_result(resolved)

            # 解析失败 → 壳子嗅探
            if not result:
                result = {
                    "parse": 1,
                    "playUrl": "",
                    "url": play_url,
                    "header": {"User-Agent": UA, "Referer": HOST + "/"},
                }

        # 直接 m3u8/mp4
        elif ".m3u8" in play_url.lower() or ".mp4" in play_url.lower():
            result = self._build_play_result(play_url)

        # 其他 → 壳子
        else:
            result = {
                "parse": 1,
                "playUrl": "",
                "url": play_url,
                "header": {"User-Agent": UA, "Referer": HOST + "/"},
            }

        # 缓存结果
        self._player_cache[play_url] = result
        self._player_cache_time[play_url] = now
        self._trim_cache(self._player_cache, self._player_cache_time, self._MAX_PLAYER_CACHE)
        return result

    def _build_play_result(self, url):
        """构建播放结果"""
        is_m3u8 = ".m3u8" in url.lower()
        return {
            "parse": 0,
            "playUrl": "",
            "url": url,
            "header": {
                "User-Agent": UA,
                "Referer": self._origin(url),
            },
            "format": "application/x-mpegURL" if is_m3u8 else "",
            "contentType": "application/x-mpegURL" if is_m3u8 else "",
        }

    def _resolve_iframe(self, iframe_url, _depth=0):
        """解析 iframe（限制 2 层嵌套，避免递归拖慢）"""
        if _depth > 1:
            return ""
        try:
            referer = self._origin(iframe_url)
            headers = dict(self.header)
            headers["Referer"] = referer
            rsp = self.fetch(iframe_url, headers=headers, timeout=3)
            try:
                html = rsp.text
            except Exception:
                html = rsp.content.decode('utf-8', 'ignore')
            if not html:
                return ""

            url = self._extract_m3u8(html)
            if url:
                return url

            # 嵌套 iframe（最多1层）
            nested = self._match(_RE_IFRAME, html)
            if nested and nested != iframe_url:
                if not nested.startswith("http"):
                    parsed = urlparse(iframe_url)
                    nested = parsed.scheme + "://" + parsed.netloc + nested
                return self._resolve_iframe(nested, _depth + 1)

        except Exception:
            pass
        return ""

    # ===== 本地代理（保留兼容）=====
    def localProxy(self, param):
        if not param:
            return [200, "text/plain", b"", ""]

        if isinstance(param, str):
            try:
                from urllib.parse import parse_qs
                qs = parse_qs(param)
                ptype = qs.get("type", [""])[0]
                img_url = qs.get("url", [""])[0]
            except Exception:
                return [200, "text/plain", b"", ""]
        elif isinstance(param, dict):
            ptype = param.get("type", "")
            img_url = param.get("url", "")
        else:
            return [200, "text/plain", b"", ""]

        if ptype == "img" and img_url:
            try:
                headers = {
                    "User-Agent": UA,
                    "Referer": self._origin(img_url),
                }
                rsp = self.fetch(img_url, headers=headers, timeout=5)
                data = rsp.content
                content_type = "image/jpeg"
                if data[:3] == b'\xff\xd8\xff':
                    content_type = "image/jpeg"
                elif data[:8] == b'\x89PNG\r\n\x1a\n':
                    content_type = "image/png"
                elif data[:4] == b'GIF8':
                    content_type = "image/gif"
                elif data[:4] == b'RIFF' and data[8:12] == b'WEBP':
                    content_type = "image/webp"
                else:
                    try:
                        ct = rsp.headers.get("Content-Type", "")
                        if ct:
                            content_type = ct.split(";")[0].strip()
                    except Exception:
                        pass
                return [200, content_type, data, ""]
            except Exception:
                return [404, "text/plain", b"", ""]

        return [200, "text/plain", b"", ""]

    # ===== 清理 =====
    def destroy(self):
        self._detail_cache.clear()
        self._detail_cache_time.clear()
        self._player_cache.clear()
        self._player_cache_time.clear()
        self._list_cache.clear()
        self._list_cache_time.clear()
        self._home_cache = []
        self._home_cache_time = 0

    def close(self):
        self.destroy()
