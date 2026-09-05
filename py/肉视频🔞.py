#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RouVideo CatVod/TVBox Spider 爬虫源
- 新增：多域名轮询 (https://rou.video / https://rouva8.xyz)
- 新增：智能地址发布页动态抓取机制 (https://rdz3.xyz/dizhi)
  * 当所有默认域名失效时，自动解析“肉視頻”板块的最新【科學地址】
- 防篡改保护：篡改作者名/线路名“飞鱼”将直接导致解析失败及崩溃
- 修复选集显示01空数据问题
- 重构视频分类：支持点击分类卡片穿透加载子视频列表（folder 机制）
- 新增：[日本] 与 [全部视频] 顶级分类及排序筛选
- 重构：详情页视频简介解析 (vod_content)，支持全层级文本与 NEXT_DATA 解析
- 新增：详情页番号展示优化（番号单独传入 vod_remarks 备注与 vod_content 简介中，保持标题干净）
- 修复：优化列表页角标 (vod_remarks) 提取，精确匹配徽章并过滤异常长文本
- 作者/线路名称标识：飞鱼
"""

import base64
import json
import re
from urllib.parse import quote, unquote
from bs4 import BeautifulSoup
from base.spider import Spider


class Spider(Spider):

    # 1. 默认备选域名列表
    HOSTS = [
        "https://rouva8.xyz",
        "https://rou.video",
        "https://rou-video.zproxy.org",  # 代理
    ]
    # 2. 地址发布页 URL
    PUB_PAGE_URL = "https://rdz3.xyz/dizhi"

    _current_host_idx = 0
    _fetched_pub_page = False  # 标记是否已经请求过发布页，避免重复请求

    @property
    def HOST(self):
        return self.HOSTS[self._current_host_idx]

    def getName(self):
        return "飞鱼"

    def init(self, extend=""):
        self._check_tamper()

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def actionHeaders(self, host_url=None):
        ref = host_url if host_url else self.HOST
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                " AppleWebKit/537.36 (KHTML, like Gecko)"
                " Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": f"{ref}/",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }

    # -----------------------------------------------------------------
    # 发布页精准解析：仅提取“肉視頻”下的【科學地址】
    # -----------------------------------------------------------------
    def _fetch_latest_host_from_pub(self):
        """抓取地址发布页，定位‘肉視頻’板块并提取‘科學地址’"""
        if self._fetched_pub_page:
            return None
        self._fetched_pub_page = True

        try:
            res = self.fetch(self.PUB_PAGE_URL, headers=self.actionHeaders(self.PUB_PAGE_URL))
            if not res or res.status_code != 200 or not res.text:
                return None

            soup = BeautifulSoup(res.text, "html.parser")

            # 遍历页面中的各个 <section class="sec">
            sections = soup.find_all("section", class_="sec")
            for sec in sections:
                h2 = sec.find("h2")
                # 严格匹配“肉視頻”板块，忽略“肉漫屋”
                if h2 and "肉視頻" in h2.get_text(strip=True):
                    # 查找文本内容为“科學地址”的 <a> 标签
                    a_tags = sec.find_all("a")
                    for a in a_tags:
                        if "科學地址" in a.get_text(strip=True):
                            href = a.get("href", "").strip().rstrip("/")
                            if href and href.startswith("http"):
                                return href

                    # 兜底：如果没拿到 href，尝试读取其紧随的 <span class="url">
                    url_span = sec.find("span", class_="url")
                    if url_span:
                        span_url = url_span.get_text(strip=True).rstrip("/")
                        if span_url and span_url.startswith("http"):
                            return span_url
        except Exception:
            pass

        return None

    # -----------------------------------------------------------------
    # 核心网络请求封装：支持多域名轮询 + 地址发布页兜底
    # -----------------------------------------------------------------
    def _req(self, path):
        """
        1. 优先轮询当前 `HOSTS` 里的可用域名。
        2. 如果全部失败，请求发布页提取“肉視頻”最新【科學地址】。
        3. 提取到新地址后，更新 `HOSTS` 列表并重新发起请求。
        """
        # 第一阶段：尝试现有的 HOSTS 列表
        for i in range(len(self.HOSTS)):
            idx = (self._current_host_idx + i) % len(self.HOSTS)
            host = self.HOSTS[idx]
            url = f"{host}{path}" if path.startswith("/") else f"{host}/{path}"

            try:
                res = self.fetch(url, headers=self.actionHeaders(host))
                if res and res.status_code == 200 and res.text:
                    self._current_host_idx = idx
                    return res.text
            except Exception:
                pass

        # 第二阶段：现有域名均失效，从发布页获取最新【科學地址】
        new_host = self._fetch_latest_host_from_pub()
        if new_host and new_host not in self.HOSTS:
            self.HOSTS.append(new_host)
            self._current_host_idx = len(self.HOSTS) - 1  # 切换到最新的科学地址

            # 使用获取到的最新科学地址重新发起请求
            url = f"{new_host}{path}" if path.startswith("/") else f"{new_host}/{path}"
            try:
                res = self.fetch(url, headers=self.actionHeaders(new_host))
                if res and res.status_code == 200 and res.text:
                    return res.text
            except Exception:
                pass

        return ""

    # -----------------------------------------------------------------
    # 防篡改核心校验
    # -----------------------------------------------------------------
    def _check_tamper(self):
        if self.getName() != "飞鱼":
            raise RuntimeError("版权被篡改，无法启动引擎！")

    # -----------------------------------------------------------------
    # 核心解密逻辑
    # -----------------------------------------------------------------
    def _decrypt_ev(self, ev_d, ev_k=35):
        if self.getName() != "飞鱼":
            return {}

        try:
            b = base64.b64decode(ev_d)
            k = int(ev_k)
            decrypted_bytes = bytes([(x - k) % 256 for x in b])
            return json.loads(decrypted_bytes.decode("utf-8", "replace"))
        except Exception:
            return {}

    def _extract_next_data(self, html):
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass
        return {}

    # -----------------------------------------------------------------
    # 分类与筛选数据配置
    # -----------------------------------------------------------------
    def homeContent(self, filter):
        if self.getName() != "飞鱼":
            return {}

        classes = [
            {"type_id": "國產AV", "type_name": "國產AV"},
            {"type_id": "麻豆傳媒", "type_name": "麻豆傳媒"},
            {"type_id": "探花", "type_name": "探花"},
            {"type_id": "OnlyFans", "type_name": "OnlyFans"},
            {"type_id": "日本", "type_name": "日本"},
            {"type_id": "全部视频", "type_name": "全部视频"},
            {"type_id": "视频分类", "type_name": "视频分类"},
        ]

        order_filter = {
            "key": "order",
            "name": "排序",
            "value": [
                {"n": "最新发布", "v": "createdAt"},
                {"n": "最多观看", "v": "viewCount"},
                {"n": "最多点赞", "v": "likeCount"},
            ],
        }

        filters = {
            "國產AV": [
                order_filter,
                {
                    "key": "sub_cate",
                    "name": "厂牌/频道",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "糖心Vlog", "v": "糖心Vlog"},
                        {"n": "蜜桃影像傳媒", "v": "蜜桃影像傳媒"},
                        {"n": "香蕉視頻傳媒", "v": "香蕉視頻傳媒"},
                        {"n": "星空無限傳媒", "v": "星空無限傳媒"},
                        {"n": "天美傳媒", "v": "天美傳媒"},
                        {"n": "精東影業", "v": "精東影業"},
                        {"n": "杏吧傳媒", "v": "杏吧傳媒"},
                        {"n": "91製片廠", "v": "91製片廠"},
                        {"n": "皇家華人", "v": "皇家華人"},
                        {"n": "起點傳媒", "v": "起點傳媒"},
                        {"n": "大象傳媒", "v": "大象傳媒"},
                        {"n": "果凍傳媒", "v": "果凍傳媒"},
                        {"n": "蘿莉社", "v": "蘿莉社"},
                        {"n": "ED Mosaic", "v": "ED Mosaic"},
                        {"n": "兔子先生", "v": "兔子先生"},
                        {"n": "扣扣傳媒", "v": "扣扣傳媒"},
                        {"n": "SA國際傳媒", "v": "SA國際傳媒"},
                        {"n": "愛神傳媒", "v": "愛神傳媒"},
                        {"n": "性視界傳媒", "v": "性視界傳媒"},
                        {"n": "PsychopornTW", "v": "PsychopornTW"},
                        {"n": "拍攝花絮", "v": "拍攝花絮"},
                        {"n": "抖陰", "v": "抖陰"},
                        {"n": "91茄子", "v": "91茄子"},
                        {"n": "絕對領域傳媒", "v": "絕對領域傳媒"},
                        {"n": "烏托邦傳媒", "v": "烏托邦傳媒"},
                        {"n": "紅斯燈影像", "v": "紅斯燈影像"},
                        {"n": "草莓視頻", "v": "草莓視頻"},
                        {"n": "渡邊傳媒", "v": "渡邊傳媒"},
                        {"n": "葫蘆影業", "v": "葫蘆影業"},
                        {"n": "樂播傳媒", "v": "樂播傳媒"},
                        {"n": "Pussy Hunter", "v": "Pussy Hunter"},
                        {"n": "麻麻傳媒", "v": "麻麻傳媒"},
                        {"n": "三只狼傳媒", "v": "三只狼傳媒"},
                        {"n": "萝莉原创", "v": "萝莉原创"},
                        {"n": "辣椒原創", "v": "辣椒原創"},
                        {"n": "MisAV", "v": "MisAV"},
                        {"n": "SWAG@daisybaby", "v": "SWAG@daisybaby"},
                        {"n": "冠希傳媒", "v": "冠希傳媒"},
                        {"n": "微密圈傳媒", "v": "微密圈傳媒"},
                        {"n": "愛妃傳媒", "v": "愛妃傳媒"},
                        {"n": "天美影院", "v": "天美影院"},
                        {"n": "西瓜影視", "v": "西瓜影視"},
                        {"n": "肉肉傳媒", "v": "肉肉傳媒"},
                        {"n": "烏鴉傳媒", "v": "烏鴉傳媒"},
                        {"n": "日出文化", "v": "日出文化"},
                        {"n": "鯨魚傳媒", "v": "鯨魚傳媒"},
                        {"n": "國產AV劇情", "v": "國產AV劇情"},
                        {"n": "SWAG@cartiernn", "v": "SWAG@cartiernn"},
                        {"n": "TWAV", "v": "TWAV"},
                        {"n": "Mini傳媒", "v": "Mini傳媒"},
                        {"n": "桃花源", "v": "桃花源"},
                        {"n": "叮叮映畫", "v": "叮叮映畫"},
                        {"n": "蜜桃視頻", "v": "蜜桃視頻"},
                        {"n": "O-STAR", "v": "O-STAR"},
                        {"n": "開心鬼傳媒", "v": "開心鬼傳媒"},
                        {"n": "葵心娛樂", "v": "葵心娛樂"},
                        {"n": "愛污傳媒", "v": "愛污傳媒"},
                    ],
                }
            ],
            "麻豆傳媒": [
                order_filter,
                {
                    "key": "sub_cate",
                    "name": "厂牌/系列",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "愛豆傳媒", "v": "愛豆傳媒"},
                        {"n": "MD", "v": "MD"},
                        {"n": "MDX", "v": "MDX"},
                        {"n": "麻豆US", "v": "麻豆US"},
                        {"n": "MSD", "v": "MSD"},
                        {"n": "MCY", "v": "MCY"},
                        {"n": "MKY", "v": "MKY"},
                        {"n": "MPG", "v": "MPG"},
                        {"n": "FLIXKO", "v": "FLIXKO"},
                        {"n": "貓爪影像", "v": "貓爪影像"},
                        {"n": "國產麻豆AV節目", "v": "國產麻豆AV節目"},
                        {"n": "麻豆女神微愛視頻", "v": "麻豆女神微愛視頻"},
                        {"n": "麻豆番外", "v": "麻豆番外"},
                        {"n": "麻豆三十天特別企劃", "v": "麻豆三十天特別企劃"},
                        {"n": "麻豆導演系列", "v": "麻豆導演系列"},
                        {"n": "情趣K歌房", "v": "情趣K歌房"},
                        {"n": "MDWP", "v": "MDWP"},
                        {"n": "突襲女優家", "v": "突襲女優家"},
                        {"n": "麻豆女優", "v": "麻豆女優"},
                        {"n": "麻豆達人秀", "v": "麻豆達人秀"},
                        {"n": "澀會", "v": "澀會"},
                        {"n": "MDS", "v": "MDS"},
                        {"n": "MDSR", "v": "MDSR"},
                        {"n": "麻豆女神微愛影片", "v": "麻豆女神微愛影片"},
                        {"n": "MDL", "v": "MDL"},
                        {"n": "MAN", "v": "MAN"},
                        {"n": "MSM", "v": "MSM"},
                        {"n": "MDHT", "v": "MDHT"},
                        {"n": "MDAG", "v": "MDAG"},
                        {"n": "MS", "v": "MS"},
                        {"n": "MSG", "v": "MSG"},
                        {"n": "MDJ", "v": "MDJ"},
                        {"n": "MDM", "v": "MDM"},
                        {"n": "MXJ", "v": "MXJ"},
                        {"n": "MDD", "v": "MDD"},
                        {"n": "MLT", "v": "MLT"},
                    ],
                }
            ],
            "探花": [
                order_filter,
                {
                    "key": "sub_cate",
                    "name": "主播/探花",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "91沈先生", "v": "91沈先生"},
                        {"n": "探花精選400", "v": "探花精選400"},
                        {"n": "小寶尋花", "v": "小寶尋花"},
                        {"n": "91lisa", "v": "91lisa"},
                        {"n": "調教小景甜", "v": "調教小景甜"},
                        {"n": "午夜尋花", "v": "午夜尋花"},
                        {"n": "91鳳鳴鳥唱", "v": "91鳳鳴鳥唱"},
                        {"n": "大神精選", "v": "大神精選"},
                        {"n": "AVOVE直播", "v": "AVOVE直播"},
                        {"n": "91貓先生", "v": "91貓先生"},
                        {"n": "千人斬探花", "v": "千人斬探花"},
                        {"n": "全國探花", "v": "全國探花"},
                        {"n": "91Fans", "v": "91Fans"},
                        {"n": "七天探花", "v": "七天探花"},
                        {"n": "9總全國探花", "v": "9總全國探花"},
                        {"n": "91大神@LovELolita7", "v": "91大神@LovELolita7"},
                        {"n": "18歲母狗無限高潮", "v": "18歲母狗無限高潮"},
                        {"n": "鴨哥探花", "v": "鴨哥探花"},
                        {"n": "锤子探花", "v": "锤子探花"},
                        {"n": "探花合集", "v": "探花合集"},
                        {"n": "91不見星空", "v": "91不見星空"},
                        {"n": "早期東莞ISO桑拿系列", "v": "早期東莞ISO桑拿系列"},
                        {"n": "91康先生", "v": "91康先生"},
                        {"n": "肉オナホ", "v": "肉オナホ"},
                        {"n": "91大神唐伯虎", "v": "91大神唐伯虎"},
                        {"n": "韋小寶", "v": "韋小寶"},
                        {"n": "91風流哥全集", "v": "91風流哥全集"},
                        {"n": "91蜜桃的合集", "v": "91蜜桃的合集"},
                        {"n": "換妻探花", "v": "換妻探花"},
                        {"n": "小陳頭星選", "v": "小陳頭星選"},
                        {"n": "91大神括約肌大叔", "v": "91大神括約肌大叔"},
                        {"n": "情侶自拍", "v": "情侶自拍"},
                        {"n": "探花精選", "v": "探花精選"},
                        {"n": "91呆哥", "v": "91呆哥"},
                        {"n": "mmmn753", "v": "mmmn753"},
                        {"n": "楊導撩妹", "v": "楊導撩妹"},
                        {"n": "歌廳探花陳先生", "v": "歌廳探花陳先生"},
                        {"n": "91美女涵菱", "v": "91美女涵菱"},
                        {"n": "太子探花", "v": "太子探花"},
                        {"n": "小馬尋花", "v": "小馬尋花"},
                        {"n": "91唐哥", "v": "91唐哥"},
                        {"n": "jimmybiiig", "v": "jimmybiiig"},
                        {"n": "91天堂原創", "v": "91天堂原創"},
                        {"n": "小飛探花", "v": "小飛探花"},
                        {"n": "文軒探花", "v": "文軒探花"},
                        {"n": "王子哥專啪學生妹", "v": "王子哥專啪學生妹"},
                        {"n": "偉哥尋歡", "v": "偉哥尋歡"},
                        {"n": "大草莓寶貝", "v": "大草莓寶貝"},
                        {"n": "探花女下海直播", "v": "探花女下海直播"},
                        {"n": "91天堂系列", "v": "91天堂系列"},
                        {"n": "91大神胖Kyo", "v": "91大神胖Kyo"},
                        {"n": "攝影師果哥出品", "v": "攝影師果哥出品"},
                        {"n": "莞式選妃", "v": "莞式選妃"},
                        {"n": "catman", "v": "catman"},
                        {"n": "90w粉", "v": "90w粉"},
                        {"n": "探花大神", "v": "探花大神"},
                        {"n": "91原創達人@多乙丶", "v": "91原創達人@多乙丶"},
                        {"n": "91大黃鴨", "v": "91大黃鴨"},
                        {"n": "小東全國尋妹", "v": "小東全國尋妹"},
                        {"n": "91Dr哥", "v": "91Dr哥"},
                        {"n": "大熊探花", "v": "大熊探花"},
                        {"n": "91約妹達人", "v": "91約妹達人"},
                        {"n": "91大神揚風", "v": "91大神揚風"},
                        {"n": "91愛絲小仙女思妍", "v": "91愛絲小仙女思妍"},
                        {"n": "探花郎李尋歡", "v": "探花郎李尋歡"},
                        {"n": "91新晉大神sweattt", "v": "91新晉大神sweattt"},
                        {"n": "91新人GD超模（現改名69DD）", "v": "91新人GD超模（現改名69DD）"},
                        {"n": "91大神jinx", "v": "91大神jinx"},
                        {"n": "91sex哥", "v": "91sex哥"},
                        {"n": "175車模", "v": "175車模"},
                        {"n": "東莞探花", "v": "東莞探花"},
                        {"n": "嫖嫖sex探花", "v": "嫖嫖sex探花"},
                        {"n": "秀人網模特", "v": "秀人網模特"},
                    ],
                }
            ],
            "OnlyFans": [
                order_filter,
                {
                    "key": "sub_cate",
                    "name": "创作者",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "fansly", "v": "fansly"},
                        {"n": "tangbo_hu", "v": "tangbo_hu"},
                        {"n": "HongKongDoll", "v": "HongKongDoll"},
                        {"n": "BunnyMiffy", "v": "BunnyMiffy"},
                        {"n": "Nana_Taipei", "v": "Nana_Taipei"},
                        {"n": "qiobnxingcai", "v": "qiobnxingcai"},
                        {"n": "suchanghub", "v": "suchanghub"},
                        {"n": "ssrpeach", "v": "ssrpeach"},
                        {"n": "nicolove.cc", "v": "nicolove.cc"},
                        {"n": "Miuzxc", "v": "Miuzxc"},
                        {"n": "yui_xin_tw", "v": "yui_xin_tw"},
                        {"n": "kitty2002102", "v": "kitty2002102"},
                        {"n": "kittyxkum", "v": "kittyxkum"},
                        {"n": "juneliu", "v": "juneliu"},
                        {"n": "YuZuKitty", "v": "YuZuKitty"},
                        {"n": "jeenzen", "v": "jeenzen"},
                        {"n": "monmon_tw", "v": "monmon_tw"},
                        {"n": "applecptv", "v": "applecptv"},
                        {"n": "Loliiiiipop99", "v": "Loliiiiipop99"},
                        {"n": "andmlove", "v": "andmlove"},
                        {"n": "daintywilder", "v": "daintywilder"},
                        {"n": "ZZZ666", "v": "ZZZ666"},
                        {"n": "aixiaixi", "v": "aixiaixi"},
                        {"n": "ChiChibae", "v": "ChiChibae"},
                        {"n": "blazeconjure3", "v": "blazeconjure3"},
                        {"n": "moremore618", "v": "moremore618"},
                        {"n": "bdollairi", "v": "bdollairi"},
                        {"n": "olive_emmm", "v": "olive_emmm"},
                        {"n": "chocoletmilkk", "v": "chocoletmilkk"},
                        {"n": "SLRabbit", "v": "SLRabbit"},
                        {"n": "Xreindeers", "v": "Xreindeers"},
                        {"n": "Carla Grace", "v": "Carla Grace"},
                    ],
                }
            ],
            "日本": [order_filter],
            "全部视频": [order_filter],
        }
        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        return self.categoryContent("國產AV", "1", False, {})

    # -----------------------------------------------------------------
    # 分类视频列表页解析
    # -----------------------------------------------------------------
    def categoryContent(self, tid, pg, filter, extend):
        if self.getName() != "飞鱼":
            return {"page": 1, "pagecount": 0, "limit": 0, "total": 0, "list": []}

        page = str(pg)
        extend = extend or {}
        order = extend.get("order", "createdAt")

        if tid.startswith("cat_tag:"):
            real_tag = tid.replace("cat_tag:", "").strip()
            path = f"/t/{quote(real_tag)}?order={order}&page={page}"
            html = self._req(path)
            return self._parse_video_list(html, page)

        if tid == "视频分类":
            return self._parse_three_level_categories()

        if tid == "全部视频":
            path = f"/v?order={order}&page={page}"
            html = self._req(path)
            return self._parse_video_list(html, page)

        sub_cate = extend.get("sub_cate", "")
        cate_id = sub_cate if sub_cate else tid

        path = f"/t/{quote(cate_id)}?order={order}&page={page}"
        html = self._req(path)
        return self._parse_video_list(html, page)

    def _parse_three_level_categories(self):
        tag_items = []
        seen_tags = set()

        try:
            html = self._req("/cat")
            next_data = self._extract_next_data(html)
            page_props = next_data.get("props", {}).get("pageProps", {})

            if page_props:
                for group_key, items in page_props.items():
                    if isinstance(items, list):
                        for item in items:
                            if isinstance(item, dict):
                                tag_id = item.get("id", "").strip()
                                count = item.get("count", 0)

                                if tag_id and tag_id not in seen_tags:
                                    seen_tags.add(tag_id)
                                    tag_items.append({
                                        "vod_id": f"cat_tag:{tag_id}",
                                        "vod_name": tag_id,
                                        "vod_pic": f"{self.HOST}/favicon.ico",
                                        "vod_remarks": f"{count} 个视频",
                                        "vod_tag": "folder",
                                    })

            if not tag_items:
                soup = BeautifulSoup(html, "html.parser")
                for a_tag in soup.find_all("a", href=re.compile(r"^/t/")):
                    href = a_tag.get("href", "")
                    tag_name = unquote(href.replace("/t/", "").strip())
                    full_text = a_tag.get_text(strip=True)
                    cnt_match = re.search(r"(\d+)", full_text)
                    count_str = f"{cnt_match.group(1)} 个视频" if cnt_match else "分类目录"

                    if tag_name and tag_name not in seen_tags:
                        seen_tags.add(tag_name)
                        tag_items.append({
                            "vod_id": f"cat_tag:{tag_name}",
                            "vod_name": tag_name,
                            "vod_pic": f"{self.HOST}/favicon.ico",
                            "vod_remarks": count_str,
                            "vod_tag": "folder",
                        })
        except Exception:
            pass

        return {
            "page": 1,
            "pagecount": 1,
            "limit": len(tag_items),
            "total": len(tag_items),
            "list": tag_items,
        }

    # -----------------------------------------------------------------
    # 搜索功能
    # -----------------------------------------------------------------
    def searchContent(self, key, quick, pg="1"):
        if self.getName() != "飞鱼":
            return {"page": 1, "pagecount": 0, "limit": 0, "total": 0, "list": []}

        page = str(pg)
        path = f"/search?q={quote(key)}&t=&sort=&page={page}"
        html = self._req(path)
        return self._parse_video_list(html, page)

    def _parse_video_list(self, html, page="1"):
        videos = []
        if not html:
            return {"page": 1, "pagecount": 0, "limit": 0, "total": 0, "list": []}

        soup = BeautifulSoup(html, "html.parser")
        cards = soup.find_all("div", attrs={"data-slot": "card"})

        for card in cards:
            a_tag = card.find("a", href=re.compile(r"^/v/"))
            if not a_tag:
                continue

            href = a_tag.get("href", "")
            vod_id = href.replace("/v/", "").strip()

            imgs = a_tag.find_all("img")
            vod_pic = ""
            if len(imgs) >= 2:
                vod_pic = imgs[1].get("src", "")
            elif len(imgs) == 1:
                vod_pic = imgs[0].get("src", "")

            h3 = card.find("h3")
            vod_name = h3.get_text(strip=True) if h3 else ""
            if not vod_name and len(imgs) >= 2:
                vod_name = imgs[1].get("alt", "")

            # ---------------- 精确修复角标解析 ----------------
            remarks = []
            # 1. 优先查找带 badge 属性的 span 标签
            badges = a_tag.find_all("span", attrs={"data-slot": "badge"})

            # 2. 如果没匹配到 data-slot，尝试查找常见覆盖在图片上的绝对定位/角标 class
            if not badges:
                badges = a_tag.find_all("span", class_=re.compile(r"absolute|badge|bg-black|rounded"))

            for b in badges:
                text = b.get_text(strip=True)
                # 过滤掉与标题重合、文本过长（>20字符）或重复的描述
                if text and text != vod_name and len(text) < 20 and text not in remarks:
                    remarks.append(text)

            vod_remarks = " | ".join(remarks) if remarks else ""
            # --------------------------------------------------

            if vod_id and vod_name:
                videos.append({
                    "vod_id": vod_id,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": vod_remarks,
                })

        p_num = int(page) if str(page).isdigit() else 1
        return {
            "page": p_num,
            "pagecount": p_num + 1 if len(videos) > 0 else p_num,
            "limit": 20,
            "total": 999,
            "list": videos,
        }

    # -----------------------------------------------------------------
    # 详情页解析 (优化 vod_content 抓取逻辑，番号单独传入 vod_remarks 与 vod_content)
    # -----------------------------------------------------------------
    def detailContent(self, array):
        if self.getName() != "飞鱼":
            return {"list": []}

        vod_id = array[0]
        clean_id = re.sub(r"^https?://[^/]+/v/", "", vod_id).replace("/v/", "").strip()
        path = f"/v/{clean_id}"

        html = self._req(path)
        soup = BeautifulSoup(html, "html.parser")

        # 提取标题
        title_el = soup.find("h1")
        vod_name = title_el.get_text(strip=True) if title_el else "飞鱼"

        # -----------------------------------------------------------------
        # 提取番号 (Badge)
        # -----------------------------------------------------------------
        code_badge = soup.find("span", attrs={"data-slot": "badge"})
        code_text = code_badge.get_text(strip=True) if code_badge else ""

        # 提取封面图片
        vod_pic = ""
        video_el = soup.find("video")
        if video_el and video_el.get("poster"):
            vod_pic = video_el.get("poster")
        else:
            img_el = soup.find("img")
            vod_pic = img_el.get("src", "") if img_el else ""

        # -----------------------------------------------------------------
        # 深度抓取简介 (vod_content)
        # -----------------------------------------------------------------
        vod_content = ""

        # 探测 1：优先尝试 JSON `__NEXT_DATA__`（最直接干净的数据源）
        next_data = self._extract_next_data(html)
        if next_data:
            props = next_data.get("props", {}).get("pageProps", {})
            video_info = props.get("video", {}) or props.get("item", {}) or props
            if isinstance(video_info, dict):
                vod_content = (
                    video_info.get("description")
                    or video_info.get("desc")
                    or video_info.get("intro")
                    or ""
                ).strip()

        # 探测 2：HTML DOM 全面搜寻（遍历包含排版/文本样式的节点）
        if not vod_content:
            candidates = soup.find_all(
                ["p", "div", "span"],
                class_=re.compile(r"whitespace-pre-wrap|leading-relaxed|text-gray-"),
            )
            for cand in candidates:
                text = cand.get_text(strip=True)
                # 排除标题重合、导航栏或过短文字
                if text and text != vod_name and len(text) > 3:
                    # 避免抓到页面顶部的隐藏类或标签列表
                    if not cand.find("a") and not cand.find("h1"):
                        vod_content = text
                        break

        # 探测 3：页面 border-t 容器兜底
        if not vod_content:
            border_div = soup.find("div", class_=re.compile(r"border-t"))
            if border_div:
                text = border_div.get_text(strip=True)
                if text and text != vod_name:
                    vod_content = text

        # 探测 4：meta description 描述信息兜底
        if not vod_content:
            meta_desc = soup.find("meta", attrs={"name": "description"}) or soup.find(
                "meta", attrs={"property": "og:description"}
            )
            if meta_desc and meta_desc.get("content"):
                vod_content = meta_desc.get("content", "").strip()

        # 如果存在番号，将其置顶拼接到简介开头
        if code_text:
            vod_content = f"【番号】：{code_text}\n{vod_content}" if vod_content else f"【番号】：{code_text}"

        # 提取分类/标签
        types = []
        main_tag = soup.find("main")
        if main_tag:
            tag_container = main_tag.find("div", class_=re.compile(r"flex-wrap.*gap-1\.5"))
            if tag_container:
                a_tags = tag_container.find_all("a", href=re.compile(r"^/t/"))
                for a in a_tags:
                    text = a.get_text(strip=True)
                    if text and text not in types:
                        types.append(text)

        if not types and main_tag:
            a_tags = main_tag.find_all("a", href=re.compile(r"^/t/"))
            for a in a_tags:
                text = a.get_text(strip=True)
                if text and text not in types:
                    types.append(text)

        if not types:
            hidden_div = soup.find("div", class_="hidden")
            if hidden_div:
                types = [x.strip() for x in hidden_div.get_text(strip=True).split(",") if x.strip()]

        type_name = " • ".join(types) if types else "飞鱼"

        vod = {
            "vod_id": clean_id,
            "vod_name": vod_name,
            "vod_remarks": code_text,  # 番号作为角标/备注展示
            "vod_pic": vod_pic,
            "type_name": type_name,
            "vod_content": vod_content,
            "vod_play_from": self.getName(),
            "vod_play_url": f"正片播放${clean_id}",
        }
        return {"list": [vod]}

    # -----------------------------------------------------------------
    # 播放地址解密与解析
    # -----------------------------------------------------------------
    def playerContent(self, flag, id, vipFlags):
        if self.getName() != "飞鱼":
            return {"parse": 0, "url": ""}

        clean_id = re.sub(r"^https?://[^/]+/v/", "", id).replace("/v/", "").strip()
        path = f"/v/{clean_id}"

        html = self._req(path)
        data = self._extract_next_data(html)
        ev = data.get("props", {}).get("pageProps", {}).get("ev", {})

        ev_d = ev.get("d", "")
        ev_k = ev.get("k", 35)

        real_url = ""
        if ev_d:
            decrypted = self._decrypt_ev(ev_d, ev_k)
            real_url = decrypted.get("videoUrl", "")

        if real_url:
            return {
                "parse": 0,
                "url": real_url,
                "header": {
                    "User-Agent": self.actionHeaders()["User-Agent"],
                    "Referer": f"{self.HOST}/",
                },
            }

        return {"parse": 1, "url": f"{self.HOST}/v/{clean_id}"}
