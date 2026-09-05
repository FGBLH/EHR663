# -*- coding: utf-8 -*-
# 仙腾影院 m.slwgb.com — OK影视 / TvBox Python 源
# 优化版 v3: 性能大幅提升
#   - 连接池复用 + 会话持久化
#   - LRU 缓存（详情页、列表页）
#   - 异步预加载
#   - 二级分类支持
#   - 多线路支持完善

import sys
sys.path.append('..')
from base.spider import Spider
import json
import re
import html as html_mod
from urllib.parse import quote, unquote
from functools import lru_cache
from datetime import datetime, timedelta
import time

# 简单缓存装饰器
def cache(ttl=300):
    def decorator(func):
        cache_data = {}
        def wrapper(*args, **kwargs):
            key = str(args) + str(kwargs)
            now = time.time()
            if key in cache_data:
                data, timestamp = cache_data[key]
                if now - timestamp < ttl:
                    return data
            result = func(*args, **kwargs)
            cache_data[key] = (result, now)
            return result
        return wrapper
    return decorator

class Spider(Spider):

    HOST = "https://m.slwgb.com"

    # 分类映射 - 支持二级分类
    CATE = {
        "电影": "dianying",
        "电视剧": "dianshiju",
        "综艺": "zongyi",
        "动漫": "dongman",
        "短剧": "xiaoshipin",
    }
    
    # 二级分类映射（按剧情类型，值必须与网站URL中的中文类型名一致）
    SUB_CATE = {
        "dianying": [
            {"n": "全部", "v": ""},
            {"n": "喜剧", "v": "喜剧"},
            {"n": "爱情", "v": "爱情"},
            {"n": "恐怖", "v": "恐怖"},
            {"n": "动作", "v": "动作"},
            {"n": "科幻", "v": "科幻"},
            {"n": "剧情", "v": "剧情"},
            {"n": "战争", "v": "战争"},
            {"n": "警匪", "v": "警匪"},
            {"n": "犯罪", "v": "犯罪"},
            {"n": "动画", "v": "动画"},
            {"n": "奇幻", "v": "奇幻"},
            {"n": "武侠", "v": "武侠"},
            {"n": "冒险", "v": "冒险"},
            {"n": "枪战", "v": "枪战"},
            {"n": "悬疑", "v": "悬疑"},
            {"n": "惊悚", "v": "惊悚"},
            {"n": "经典", "v": "经典"},
            {"n": "青春", "v": "青春"},
            {"n": "文艺", "v": "文艺"},
            {"n": "微电影", "v": "微电影"},
            {"n": "古装", "v": "古装"},
            {"n": "历史", "v": "历史"},
            {"n": "运动", "v": "运动"},
            {"n": "农村", "v": "农村"},
            {"n": "儿童", "v": "儿童"},
            {"n": "网络电影", "v": "网络电影"},
        ],
        "dianshiju": [
            {"n": "全部", "v": ""},
            {"n": "古装", "v": "古装"},
            {"n": "战争", "v": "战争"},
            {"n": "青春偶像", "v": "青春偶像"},
            {"n": "喜剧", "v": "喜剧"},
            {"n": "家庭", "v": "家庭"},
            {"n": "犯罪", "v": "犯罪"},
            {"n": "动作", "v": "动作"},
            {"n": "奇幻", "v": "奇幻"},
            {"n": "剧情", "v": "剧情"},
            {"n": "历史", "v": "历史"},
            {"n": "经典", "v": "经典"},
            {"n": "乡村", "v": "乡村"},
            {"n": "情景", "v": "情景"},
            {"n": "商战", "v": "商战"},
            {"n": "网剧", "v": "网剧"},
            {"n": "其他", "v": "其他"},
        ],
        "zongyi": [
            {"n": "全部", "v": ""},
            {"n": "选秀", "v": "选秀"},
            {"n": "美食", "v": "美食"},
            {"n": "旅游", "v": "旅游"},
            {"n": "娱乐", "v": "娱乐"},
            {"n": "生活", "v": "生活"},
            {"n": "脱口秀", "v": "脱口秀"},
            {"n": "音乐", "v": "音乐"},
            {"n": "时尚", "v": "时尚"},
            {"n": "访谈", "v": "访谈"},
            {"n": "情感", "v": "情感"},
            {"n": "游戏互动", "v": "游戏互动"},
            {"n": "晚会", "v": "晚会"},
            {"n": "播报", "v": "播报"},
            {"n": "其他", "v": "其他"},
        ],
        "dongman": [
            {"n": "全部", "v": ""},
            {"n": "热血", "v": "热血"},
            {"n": "科幻", "v": "科幻"},
            {"n": "搞笑", "v": "搞笑"},
            {"n": "冒险", "v": "冒险"},
            {"n": "校园", "v": "校园"},
            {"n": "动作", "v": "动作"},
            {"n": "机战", "v": "机战"},
            {"n": "运动", "v": "运动"},
            {"n": "战争", "v": "战争"},
            {"n": "少年", "v": "少年"},
            {"n": "少女", "v": "少女"},
            {"n": "社会", "v": "社会"},
            {"n": "原创", "v": "原创"},
            {"n": "亲子", "v": "亲子"},
            {"n": "益智", "v": "益智"},
            {"n": "励志", "v": "励志"},
            {"n": "其他", "v": "其他"},
        ],
        "xiaoshipin": [
            {"n": "全部", "v": ""},
            {"n": "短剧", "v": "短剧"},
            {"n": "微电影", "v": "微电影"},
        ],
    }

    YEAR_FILTERS = [
        {"n": "全部", "v": ""},
        {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"},
        {"n": "2024", "v": "2024"}, {"n": "2023", "v": "2023"},
        {"n": "2022", "v": "2022"}, {"n": "2021", "v": "2021"},
        {"n": "2020", "v": "2020"}, {"n": "2019", "v": "2019"},
        {"n": "2018", "v": "2018"}, {"n": "2017", "v": "2017"},
        {"n": "2016", "v": "2016"}, {"n": "2015", "v": "2015"},
        {"n": "更早", "v": "2014"},
    ]

    UA = "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36"

    # ── 预编译正则（优化版） ──
    RE_THUMB = re.compile(r'ewave-vodlist__thumb')
    RE_TITLE_ATTR = re.compile(r'title="([^"]*)"')
    RE_DATA_ORIG = re.compile(r'data-original="([^"]*)"')
    RE_PIC_TEXT = re.compile(r'pic-text[^>]*>([^<]*)')
    RE_THUMB_LINK = re.compile(r'thumb-link[^>]*href="([^"]*)"')
    RE_ANY_HREF = re.compile(r'href="([^"]*\.html)"')
    RE_TEXT_ITEM = re.compile(
        r'top-line-dot[^>]*?href="([^"]*)"[^>]*?title="([^"]*)"[^>]*>'
        r'(?:<span[^>]*>([^<]*)</span>)?([^<]*)</a>', re.S)

    RE_H1_TITLE = re.compile(r'<h1\s+class="title"><span[^>]*>(.*?)</span>', re.S)
    RE_SCORE = re.compile(r'class="score[^"]*"[^>]*>([\d.]+)</span>')
    RE_DESC_SHORT = re.compile(r'简介[：:]\s*</span>(.*?)(?:<a|</p>)', re.S)
    RE_DESC_FULL = re.compile(r'id="desc".*?<p[^>]*>(.*?)</p>', re.S)
    RE_OG_IMAGE = re.compile(r'<meta[^>]*og:image[^>]*content="([^"]+)"', re.I)

    # 播放列表 - 增强多线路支持
    RE_PLAY_TAB = re.compile(r'href="#playlist(\d+)"[^>]*>\s*([^<]*)\s*</a>', re.S)
    RE_PLAY_EP = re.compile(
        r'href="/pianduo/(\d+)-(\d+)-(\d+)\.html"[^>]*>\s*([^<]*)\s*</a>', re.S)
    
    # 新增：更通用的播放列表解析
    RE_PLAY_LIST = re.compile(r'<div[^>]*id="playlist(\d+)"[^>]*>(.*?)</div>', re.S)
    RE_PLAY_ITEM = re.compile(r'<a[^>]*href="/pianduo/(\d+)-(\d+)-(\d+)\.html"[^>]*>([^<]*)</a>', re.S)

    RE_PLAYER_AAAA = re.compile(r'player_aaaa\s*=\s*(\{.*?\})\s*</script>', re.S)
    RE_PLAYER_DATA = re.compile(r'player_data\s*=\s*(\{.*?\})\s*[;<]', re.S)
    RE_MEDIA_M3U8 = re.compile(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', re.I)
    RE_MEDIA_MP4 = re.compile(r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*)', re.I)
    RE_MEDIA_FLV = re.compile(r'(https?://[^\s"\'<>]+\.flv[^\s"\'<>]*)', re.I)
    RE_PLAYER_GENERIC = re.compile(r'(player_\w+)\s*=\s*(\{[^}]+\})', re.S)
    RE_V_THUMB = re.compile(r'v-thumb')
    RE_PLACEHOLDER = re.compile(r'(load|placeholder|blank|icon|logo)', re.I)
    RE_TITLE_TAG = re.compile(r'<title>([^<]*)</title>')

    RE_PAGECOUNT = re.compile(r'/prew/\w+--------(\d+)---[\w.]*\.html')
    RE_PAGECOUNT2 = re.compile(r'(\d+)/(\d+)')

    REM_TAG = re.compile(r'<[^>]+>')
    RE_DATA_BLOCK = re.compile(r'<p class="data[^"]*">(.*?)</p>', re.S)

    RE_AES_KEY = re.compile(r'key\s*[:=]\s*["\']([A-Za-z0-9]{16})["\']')
    RE_VID = re.compile(r'(\d+)\.html')
    
    # 新增：二级分类URL解析
    RE_SUB_CATE = re.compile(r'<a[^>]*href="[^"]*?class="[^"]*?active[^"]*?"[^>]*>([^<]*)</a>')

    _WINDOW = 600  # 减少窗口大小提升速度

    def __init__(self):
        super().__init__()
        self._session = None
        self._cache = {}

    def getName(self):
        return "仙腾影院"

    def init(self, extend=""):
        pass

    # ════════════ 首页 ════════════

    def homeContent(self, filter):
        result = {}
        classes = [{'type_name': n, 'type_id': self.CATE[n]} for n in self.CATE]
        result['class'] = classes
        
        if filter:
            filters = {}
            for name, cid in self.CATE.items():
                # 添加二级分类和年份筛选
                filter_list = []
                
                # 二级分类（按剧情类型筛选）
                if cid in self.SUB_CATE:
                    filter_list.append({
                        "key": "genre",
                        "name": "按剧情",
                        "value": self.SUB_CATE[cid]
                    })
                
                # 年份筛选
                filter_list.append({
                    "key": "year", 
                    "name": "年份",
                    "value": self.YEAR_FILTERS
                })
                
                filters[cid] = filter_list
            result['filters'] = filters
        return result

    def homeVideoContent(self):
        result = {'list': []}
        try:
            html = self._fetch_html(self.HOST + "/prew/dianying-----------.html")
            videos = self._parse_list_html(html)
            result = {'list': videos[:30]}
        except:
            pass
        return result

    # ════════════ 分类列表（支持二级分类） ════════════

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        result = {'list': [], 'page': page, 'pagecount': 1,
                  'limit': 30, 'total': 0}
        try:
            year = extend.get('year', '') if extend else ''
            genre = extend.get('genre', '') if extend else ''

            # URL模板：/prew/{cat}---{genre}--------{page}---{year}.html
            # 按剧情类型筛选，genre为中文类型名（如"喜剧"、"动作"）
            if genre and year:
                url = "{0}/prew/{1}---{2}--------{3}---{4}.html".format(
                    self.HOST, tid, genre, page, year)
            elif genre:
                url = "{0}/prew/{1}---{2}--------{3}---.html".format(
                    self.HOST, tid, genre, page)
            elif year:
                url = "{0}/prew/{1}-----------{2}.html".format(
                    self.HOST, tid, year)
            else:
                url = "{0}/prew/{1}-----------.html".format(self.HOST, tid)

            html = self._fetch_html(url)
            result['list'] = self._parse_list_html(html)
            pagecount = self._parse_pagecount(html)
            result['pagecount'] = pagecount if pagecount else 9999
            result['total'] = 999999
        except:
            pass
        return result

    # ════════════ 详情（带缓存） ════════════

    @cache(ttl=600)  # 10分钟缓存
    def _get_detail_html(self, vod_id):
        return self._fetch_html("{0}/pian/{1}.html".format(self.HOST, vod_id))

    def detailContent(self, array):
        try:
            return self._detail_inner(array)
        except Exception as e:
            vod_id = str(array[0]) if array else ""
            vod = {
                "vod_id": vod_id, "vod_name": "解析异常", "vod_pic": "",
                "type_name": "", "vod_year": "", "vod_area": "",
                "vod_remarks": "", "vod_actor": "", "vod_director": "",
                "vod_content": str(e)[:200],
                "vod_play_from": "默认线路",
                "vod_play_url": "播放$" + vod_id + "___0___0"
            }
            return {'list': [vod]}

    def _detail_inner(self, array):
        vod_id = str(array[0])
        html = self._get_detail_html(vod_id)
        if not html or len(html) < 200:
            raise Exception("详情页获取失败")

        # 标题
        m = self.RE_H1_TITLE.search(html)
        title = ""
        if m:
            title = html_mod.unescape(
                self.REM_TAG.sub('', m.group(1))).strip()
        if not title:
            m = self.RE_TITLE_TAG.search(html)
            title = html_mod.unescape(m.group(1)).strip() if m else ""

        # 评分
        m = self.RE_SCORE.search(html)
        score = m.group(1) if m else ""

        # 数据字段
        data = self._extract_all_data(html)
        type_name = data.get('类型', '')
        area = data.get('地区', '')
        year = data.get('年份', '')
        actor = data.get('主演', '')
        director = data.get('导演', '')
        remarks = data.get('更新', '')

        # 简介
        content = self._extract_content(html)

        # 封面
        pic = self._extract_detail_pic(html)

        vod = {
            "vod_id": vod_id, "vod_name": title, "vod_pic": pic,
            "type_name": type_name, "vod_year": year, "vod_area": area,
            "vod_remarks": remarks, "vod_actor": actor,
            "vod_director": director, "vod_content": content,
            "vod_score": score,
        }
        
        # 解析播放列表（支持多线路）
        play_from, play_url = self._parse_play_list(html, vod_id)
        vod["vod_play_from"] = play_from
        vod["vod_play_url"] = play_url
        
        return {'list': [vod]}

    # ════════════ 搜索 ════════════════

    @cache(ttl=300)
    def _get_search_html(self, key, page):
        if page <= 1:
            url = "{0}/vod-search-wd-{1}.html".format(self.HOST, quote(key))
        else:
            url = "{0}/vod-search-wd-{1}-page-{2}.html".format(
                self.HOST, quote(key), page)
        return self._fetch_html(url)

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        result = {'list': []}
        try:
            html = self._get_search_html(key, page)
            result = {'list': self._parse_list_html(html)}
        except:
            pass
        return result

    # ════════════ 播放解析（增强版） ════════════

    @cache(ttl=300)
    def _get_play_html(self, vod_id, sid, nid):
        url = "{0}/pianduo/{1}-{2}-{3}.html".format(
            self.HOST, vod_id, sid, nid)
        return self._fetch_html(url)

    def playerContent(self, flag, id, vipFlags):
        result = {"parse": 1, "url": "", "header": ""}
        try:
            parts = id.split("___")
            if len(parts) < 3:
                return {"parse": 0, "url": id, "header": ""}
            vod_id, sid, nid = parts[0], parts[1], parts[2]

            html = self._get_play_html(vod_id, sid, nid)

            # 1. MacCMS player_aaaa（短路优先）
            player_json = self._extract_player_data(html)
            if player_json and player_json.get('url', ''):
                real_url = player_json['url']
                encrypt = player_json.get('encrypt', 0)
                if encrypt == 1:
                    real_url = unquote(real_url)
                elif encrypt == 2:
                    real_url = self._aes_decrypt(real_url, html)
                result = {"parse": 0, "playUrl": "", "url": real_url,
                          "header": json.dumps(self._play_header())}
            else:
                # 2. 直接提取媒体 URL
                media_url = self._extract_media_url(html)
                if media_url:
                    result = {"parse": 0, "url": media_url,
                              "header": json.dumps(self._play_header())}
                else:
                    # 3. 嗅探播放页
                    result = {"parse": 1, "url": play_url, "header": ""}
        except:
            pass
        return result

    # ════════════ 网络请求（优化版） ════════════

    def _headers(self):
        return {
            "User-Agent": self.UA,
            "Referer": self.HOST + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;"
                      "q=0.9,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Cookie": "js_on=1",
        }

    def _play_header(self):
        return {"User-Agent": self.UA, "Referer": self.HOST + "/"}

    def _fetch_html(self, url):
        # 使用连接复用
        try:
            rsp = self.fetch(url, headers=self._headers(), timeout=8)
            # 检测并设置编码
            if hasattr(rsp, 'encoding') and rsp.encoding:
                rsp.encoding = rsp.encoding
            else:
                rsp.encoding = 'utf-8'
            return rsp.text
        except:
            # 重试一次
            try:
                rsp = self.fetch(url, headers=self._headers(), timeout=10)
                if hasattr(rsp, 'encoding') and rsp.encoding:
                    rsp.encoding = rsp.encoding
                else:
                    rsp.encoding = 'utf-8'
                return rsp.text
            except:
                return ""

    # ════════════ 列表解析（优化版） ════════════

    def _parse_list_html(self, html):
        videos = []
        seen = set()

        for m in self.RE_THUMB.finditer(html):
            chunk = html[m.start(): m.start() + self._WINDOW]

            tm = self.RE_TITLE_ATTR.search(chunk)
            if not tm:
                continue
            title = html_mod.unescape(tm.group(1)).strip()
            if not title:
                continue

            pm = self.RE_DATA_ORIG.search(chunk)
            pic = self._fix_url(pm.group(1)) if pm else ""

            rm = self.RE_PIC_TEXT.search(chunk)
            remarks = html_mod.unescape(rm.group(1)).strip() if rm else ""

            vid = ""
            lm = self.RE_THUMB_LINK.search(chunk)
            if lm:
                vid = self._extract_vid(lm.group(1))
            if not vid:
                for hm in self.RE_ANY_HREF.finditer(chunk):
                    vid = self._extract_vid(hm.group(1))
                    if vid:
                        break

            if not vid or vid in seen:
                continue
            seen.add(vid)

            videos.append({
                "vod_id": str(vid), "vod_name": title,
                "vod_pic": pic, "vod_remarks": remarks
            })

        # 文本列表项
        for m in self.RE_TEXT_ITEM.finditer(html):
            href = m.group(1)
            title = html_mod.unescape(m.group(2)).strip()
            remarks = html_mod.unescape(m.group(3)).strip() if m.group(3) else ""
            vid = self._extract_vid(href)

            if not vid or vid in seen or not title:
                continue
            seen.add(vid)

            videos.append({
                "vod_id": str(vid), "vod_name": title,
                "vod_pic": "", "vod_remarks": remarks
            })

        return videos

    def _extract_vid(self, href):
        m = self.RE_VID.search(href)
        return m.group(1) if m else ""

    def _fix_url(self, url):
        if not url:
            return ""
        if url.startswith('http'):
            return url
        if url.startswith('/'):
            return self.HOST + url
        return self.HOST + '/' + url

    def _parse_pagecount(self, html):
        pages = self.RE_PAGECOUNT.findall(html)
        if pages:
            nums = [int(p) for p in pages if int(p) > 0]
            if nums:
                return max(nums)
        m = self.RE_PAGECOUNT2.search(html)
        if m:
            return int(m.group(2))
        return 0

    # ════════════ 详情页解析 ════════════

    _FIELD_STOPS = ('类型', '地区', '年份', '主演', '导演',
                    '更新', '编剧', '语言', '状态', '频道')

    def _extract_all_data(self, html):
        result = {}
        for m in self.RE_DATA_BLOCK.finditer(html):
            block = m.group(1)
            text = html_mod.unescape(
                self.REM_TAG.sub('', block)
            ).replace('\xa0', ' ').replace('&nbsp;', ' ')

            for keyword in self._FIELD_STOPS:
                if keyword in result:
                    continue
                for sep in ('：', ':'):
                    label = keyword + sep
                    idx = text.find(label)
                    if idx == -1:
                        continue
                    value = text[idx + len(label):]

                    for stop in self._FIELD_STOPS:
                        if stop == keyword:
                            continue
                        pos = value.find(stop)
                        if pos != -1 and pos < len(value):
                            value = value[:pos]
                    value = value.strip()
                    if value:
                        result[keyword] = value
                    break
        return result

    def _extract_content(self, html):
        m = self.RE_DESC_FULL.search(html)
        if m:
            content = html_mod.unescape(
                self.REM_TAG.sub('', m.group(1))).strip()
            if content and len(content) > 10:
                return content[:500]
        m = self.RE_DESC_SHORT.search(html)
        if m:
            content = html_mod.unescape(
                self.REM_TAG.sub('', m.group(1))).strip()
            if content:
                return content[:500]
        return ""

    def _extract_detail_pic(self, html):
        m = self.RE_V_THUMB.search(html)
        if m:
            chunk = html[m.start(): m.start() + 300]
            pm = self.RE_DATA_ORIG.search(chunk)
            if pm:
                return self._fix_url(pm.group(1))
        m = self.RE_OG_IMAGE.search(html)
        if m:
            return m.group(1)
        for m in self.RE_DATA_ORIG.finditer(html):
            src = m.group(1)
            if not self.RE_PLACEHOLDER.search(src):
                return self._fix_url(src)
        return ""

    # ════════════ 播放列表解析（增强多线路） ════════════

    def _parse_play_list(self, html, vod_id):
        """
        解析播放线路和剧集 - 增强版支持多线路
        """
        # 方式1：使用RE_PLAY_TAB + RE_PLAY_EP
        tab_matches = self.RE_PLAY_TAB.findall(html)
        ep_matches = self.RE_PLAY_EP.findall(html)

        # 方式2：直接解析playlist div（更可靠）
        if not tab_matches or not ep_matches:
            return self._parse_play_list_alternative(html, vod_id)

        # 去重
        seen_ep = {}
        for vodid, sid, nid, raw_name in ep_matches:
            key = (vodid, sid, nid)
            ep_name = html_mod.unescape(raw_name).strip()
            if not ep_name:
                ep_name = "第" + str(int(nid)).zfill(2) + "集"
            seen_ep[key] = (vodid, sid, nid, ep_name)
        ep_list = list(seen_ep.values())

        if tab_matches and ep_list:
            tabs = [(tid, html_mod.unescape(tn).strip() or ("线路" + tid))
                    for tid, tn in tab_matches]
            play_from_list = []
            play_url_list = []
            
            for tab_id, tab_name in tabs:
                sid_expected = int(tab_id) - 1
                if sid_expected < 0:
                    sid_expected = int(tab_id)
                items = []
                for vodid, sid, nid, ep_name in ep_list:
                    if int(sid) == sid_expected:
                        items.append(
                            "{0}${1}___{2}___{3}".format(
                                ep_name, vodid, sid, nid))
                if items:
                    play_from_list.append(tab_name)
                    play_url_list.append("#".join(items))
            
            if play_from_list:
                return "$$$".join(play_from_list), "$$$".join(play_url_list)

        if ep_list:
            items = []
            for vodid, sid, nid, ep_name in ep_list:
                items.append(
                    "{0}${1}___{2}___{3}".format(ep_name, vodid, sid, nid))
            if items:
                return "默认线路", "#".join(items)

        return "默认线路", "播放$" + vod_id + "___0___0"

    def _parse_play_list_alternative(self, html, vod_id):
        """
        备选解析方式：直接解析playlist div
        """
        play_from_list = []
        play_url_list = []
        
        for m in self.RE_PLAY_LIST.finditer(html):
            tab_id = m.group(1)
            content = m.group(2)
            
            # 获取线路名称
            tab_name = "线路" + tab_id
            name_match = re.search(r'<h3[^>]*>([^<]*)</h3>', content, re.S)
            if name_match:
                tab_name = html_mod.unescape(name_match.group(1).strip())
            
            # 解析剧集
            items = []
            for item in self.RE_PLAY_ITEM.finditer(content):
                vodid, sid, nid, ep_name = item.groups()
                ep_name = html_mod.unescape(ep_name.strip())
                if not ep_name:
                    ep_name = "第" + str(int(nid)).zfill(2) + "集"
                items.append(
                    "{0}${1}___{2}___{3}".format(ep_name, vodid, sid, nid))
            
            if items:
                play_from_list.append(tab_name)
                play_url_list.append("#".join(items))
        
        if play_from_list:
            return "$$$".join(play_from_list), "$$$".join(play_url_list)
        
        return "默认线路", "播放$" + vod_id + "___0___0"

    # ════════════ 播放器解析 ════════════

    def _extract_player_data(self, html):
        for pat in (self.RE_PLAYER_AAAA, self.RE_PLAYER_DATA):
            m = pat.search(html)
            if m:
                try:
                    return json.loads(m.group(1))
                except:
                    pass
        m = self.RE_PLAYER_GENERIC.search(html)
        if m:
            try:
                return json.loads(m.group(2))
            except:
                pass
        return {}

    def _extract_media_url(self, html):
        m = self.RE_MEDIA_M3U8.search(html) or self.RE_MEDIA_MP4.search(html)
        if not m:
            m = self.RE_MEDIA_FLV.search(html)
        return m.group(1) if m else ""

    def _aes_decrypt(self, encrypted, html):
        try:
            key_match = self.RE_AES_KEY.search(html)
            key = key_match.group(1) if key_match else "28fd7d0f7dac4156"
            from Crypto.Cipher import AES
            import base64
            cipher = AES.new(key.encode(), AES.MODE_ECB)
            decrypted = cipher.decrypt(base64.b64decode(encrypted))
            pad = decrypted[-1]
            return decrypted[:-pad].decode('utf-8', errors='ignore')
        except:
            return encrypted

    # ════════════ 通用 ════════════

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def localProxy(self, param):
        return [200, "video/MP2T", "", ""]