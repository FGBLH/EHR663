# coding=utf-8
"""
豆花影视 (dhvideo.cc) 爬虫
适配影视仓 / OK影视 / TVBox 等空壳影视APP

接口规范：
- homeContent(filter)       → {"class":[...], "filters":{...}}
- homeVideoContent()        → {"list":[...]}
- categoryContent(tid,pg,filter,extend) → {"list":[...], "page":..., "pagecount":..., ...}
- detailContent(ids)        → {"list":[{...}]}
- playerContent(flag,id,vipFlags) → {"parse":..., "url":..., "header":...}
- searchContent(key,quick,pg) → {"list":[...], ...}
"""

import re
import json
import urllib.parse
import requests
from lxml import etree
from base.spider import Spider


class Spider(Spider):
    def __init__(self):
        self.name = "dhys"
        self.host = "https://dhvideo.cc"
        self.cdn = "https://pic2.tupian.click"
        self.sion_id = "6a7021e3d742658065a970b4"
        self.header = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': self.host
        }
        # 分类页面映射
        self._cat_map = {
            "1": "dianying",     # 电影
            "2": "dianshiju",    # 电视剧
            "3": "zongyi",       # 综艺
            "4": "dongman",      # 动漫
            "5": "duanju",       # 短剧
        }
        # 反向映射
        self._cat_rev = {v: k for k, v in self._cat_map.items()}

    def getName(self):
        return self.name

    def init(self, extend=''):
        pass

    def _get(self, url, params=None, allow_redirects=True):
        """发送GET请求"""
        r = requests.get(url, headers=self.header, params=params,
                         timeout=20, allow_redirects=allow_redirects)
        r.encoding = 'utf-8'
        return r.text

    def _post(self, url, data=None):
        """发送POST请求"""
        r = requests.post(url, headers=self.header, data=data, timeout=20)
        r.encoding = 'utf-8'
        return r.text

    def _fix_url(self, url):
        """修复相对URL为绝对URL"""
        if not url:
            return ''
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('/'):
            return self.host + url
        return url

    def _fix_pic(self, url):
        """修复图片URL，使用CDN"""
        if not url:
            return ''
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('/'):
            return self.cdn + url
        return url

    def _parse_text(self, elem):
        """提取元素内所有文本"""
        if elem is None:
            return ''
        if isinstance(elem, list):
            if not elem:
                return ''
            elem = elem[0]
        return ''.join(elem.itertext()).strip()

    def _build_url(self, cat_en, **params):
        """构建分类页面URL"""
        base = f"{self.host}/{cat_en}.html"
        qs = {"sion_id": self.sion_id}
        for k, v in params.items():
            if v:
                qs[k] = v
        qs_str = urllib.parse.urlencode(qs)
        return f"{base}?{qs_str}"

    # ==================== 列表解析 ====================

    def _parse_video_card(self, card):
        """解析单个视频卡片"""
        try:
            # 获取链接（aspect-[2/3] 类的 a 标签）
            a = card.xpath('.//a[contains(@class, "aspect-")]')
            if not a:
                # 如果卡片本身就是a标签
                if card.tag == 'a':
                    a = [card]
                else:
                    a = card.xpath('.//a')
            if not a:
                return None
            a = a[0]
            href = a.get('href', '')
            if not href:
                return None

            # 提取 vod_id - 保留完整 id(含 -数字 后缀)，避免详情页 302
            vod_id = href
            m = re.search(r'/(?:movie|tv)/([^/]+?)\.html', href)
            if m:
                vod_id = m.group(1)

            # 图片
            img = a.xpath('.//img')
            vod_pic = ''
            if img:
                vod_pic = img[0].get('data-src') or img[0].get('src', '')
            if not vod_pic:
                img = card.xpath('.//img')
                if img:
                    vod_pic = img[0].get('data-src') or img[0].get('src', '')
            vod_pic = self._fix_pic(vod_pic)

            # 标题
            vod_name = ''
            title_h3 = card.xpath('.//h3/a/text()')
            if title_h3:
                vod_name = title_h3[0].strip()
            if not vod_name:
                title_a = card.xpath('.//h3//text()')
                if title_a:
                    vod_name = ''.join(title_a).strip()
            if not vod_name:
                # 从图片alt获取
                img_alt = a.xpath('.//img/@alt')
                if img_alt:
                    vod_name = img_alt[0].strip()

            # 备注（badge）
            vod_remarks = ''
            badge = card.xpath('.//span[contains(@class, "bg-black/60")]/text()')
            if badge:
                vod_remarks = badge[0].strip()

            # 类型和年份
            vod_type = ''
            type_text = card.xpath('.//div[contains(@class, "truncate")]/text()')
            if type_text:
                vod_type = type_text[0].strip()

            year = ''
            year_text = card.xpath('.//div[contains(@class, "justify-between")]//span/text()')
            if year_text:
                for yt in year_text:
                    yt = yt.strip()
                    if yt.isdigit() and len(yt) == 4:
                        year = yt
                        break

            return {
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_remarks": vod_remarks,
                "type_name": vod_type,
                "vod_year": year
            }
        except Exception:
            return None

    def _parse_video_list(self, html):
        """解析视频列表页"""
        videos = []
        try:
            root = etree.HTML(html)
            # 视频卡片在 grid 容器内，每个卡片是 div.flex.flex-col.gap-2.group
            cards = root.xpath(
                '//div[contains(@class, "grid-cols")]'
                '/div[contains(@class, "flex flex-col") and contains(@class, "group")]'
            )
            if not cards:
                # 备选：通过图片链接的父级查找
                img_links = root.xpath('//a[contains(@class, "aspect-")]/..')
                cards = [link.getparent() if link.tag == 'a' else link for link in img_links]
                # 去重
                seen = set()
                unique_cards = []
                for c in cards:
                    cid = id(c)
                    if cid not in seen:
                        seen.add(cid)
                        unique_cards.append(c)
                cards = unique_cards

            for card in cards:
                try:
                    video = self._parse_video_card(card)
                    if video and video.get("vod_name"):
                        videos.append(video)
                except Exception:
                    pass
        except Exception:
            pass
        return videos

    def _parse_pagecount(self, html):
        """解析总页数"""
        total = 1
        try:
            root = etree.HTML(html)
            page_links = root.xpath('//section[contains(@class, "mt-12")]//a[contains(@href, "page=")]')
            for link in page_links:
                m = re.search(r'page=(\d+)', link.get('href', ''))
                if m:
                    page_num = int(m.group(1)) + 1  # 0-based → 1-based
                    total = max(total, page_num)
        except Exception:
            pass
        return total

    # ==================== 首页接口 ====================

    def homeContent(self, filter):
        result = {"class": []}
        classes = [
            {"type_name": "电影", "type_id": "1"},
            {"type_name": "电视剧", "type_id": "2"},
            {"type_name": "综艺", "type_id": "3"},
            {"type_name": "动漫", "type_id": "4"},
            {"type_name": "短剧", "type_id": "5"},
        ]
        result["class"] = classes

        # 筛选器
        area_vals = [
            {"n": "全部", "v": ""},
            {"n": "中国大陆", "v": "中国大陆"},
            {"n": "中国香港", "v": "中国香港"},
            {"n": "中国台湾", "v": "中国台湾"},
            {"n": "美国", "v": "美国"},
            {"n": "日本", "v": "日本"},
            {"n": "韩国", "v": "韩国"},
            {"n": "英国", "v": "英国"},
            {"n": "法国", "v": "法国"},
            {"n": "德国", "v": "德国"},
            {"n": "意大利", "v": "意大利"},
            {"n": "印度", "v": "印度"},
            {"n": "泰国", "v": "泰国"},
            {"n": "加拿大", "v": "加拿大"},
            {"n": "西班牙", "v": "西班牙"},
            {"n": "俄罗斯", "v": "俄罗斯"},
            {"n": "澳大利亚", "v": "澳大利亚"},
            {"n": "菲律宾", "v": "菲律宾"},
            {"n": "其他", "v": "其他"},
        ]

        class_vals = [
            {"n": "全部", "v": ""},
            {"n": "剧情", "v": "剧情"},
            {"n": "喜剧", "v": "喜剧"},
            {"n": "动作", "v": "动作"},
            {"n": "爱情", "v": "爱情"},
            {"n": "惊悚", "v": "惊悚"},
            {"n": "犯罪", "v": "犯罪"},
            {"n": "恐怖", "v": "恐怖"},
            {"n": "悬疑", "v": "悬疑"},
            {"n": "冒险", "v": "冒险"},
            {"n": "奇幻", "v": "奇幻"},
            {"n": "科幻", "v": "科幻"},
            {"n": "院线", "v": "院线"},
            {"n": "家庭", "v": "家庭"},
            {"n": "历史", "v": "历史"},
            {"n": "战争", "v": "战争"},
            {"n": "纪录片", "v": "纪录片"},
            {"n": "古装", "v": "古装"},
            {"n": "音乐", "v": "音乐"},
            {"n": "动画", "v": "动画"},
            {"n": "传记", "v": "传记"},
            {"n": "武侠", "v": "武侠"},
            {"n": "运动", "v": "运动"},
            {"n": "短片", "v": "短片"},
        ]

        year_vals = [{"n": "全部", "v": ""}]
        for y in range(2026, 2002, -1):
            year_vals.append({"n": str(y), "v": str(y)})

        order_vals = [
            {"n": "默认", "v": ""},
            {"n": "最新", "v": "time"},
            {"n": "最热", "v": "play_hot"},
        ]

        filters = {}
        for c in classes:
            filters[c['type_id']] = [
                {"key": "area", "name": "地区", "value": area_vals},
                {"key": "class", "name": "分类", "value": class_vals},
                {"key": "year", "name": "年份", "value": year_vals},
                {"key": "order", "name": "排序", "value": order_vals},
            ]
        result["filters"] = filters
        return result

    def homeVideoContent(self):
        """首页推荐列表"""
        videos = []
        try:
            url = f"{self.host}/?sion_id={self.sion_id}"
            html = self._get(url)
            videos = self._parse_video_list(html)
        except Exception:
            pass
        return {"list": videos}

    # ==================== 分类接口 ====================

    def categoryContent(self, tid, pg, filter, extend):
        """分类内容列表"""
        videos = []
        try:
            # 解析 extend（筛选参数）
            if isinstance(extend, str) and extend:
                try:
                    extend = json.loads(extend)
                except Exception:
                    extend = {}
            elif not extend:
                extend = {}

            cat_en = self._cat_map.get(str(tid), "dianying")
            area = extend.get('area', '')
            cls = extend.get('class', '')
            year = extend.get('year', '')
            order = extend.get('order', '')
            page = max(int(pg) - 1, 0)  # 转为0-based

            params = {
                "sion_id": self.sion_id,
                "page": str(page) if page > 0 else None,
                "area": area if area else None,
                "class": cls if cls else None,
                "year": year if year else None,
                "sort_field": order if order else None,
            }
            # 过滤掉None值
            params = {k: v for k, v in params.items() if v is not None}

            url = self._build_url(cat_en, **{k: v for k, v in params.items() if k != "sion_id"})
            # 手动构建URL以保持sion_id
            base = f"{self.host}/{cat_en}.html"
            qs = {"sion_id": self.sion_id}
            for k, v in params.items():
                if k != "sion_id" and v:
                    qs[k] = v
            qs_str = urllib.parse.urlencode(qs)
            url = f"{base}?{qs_str}"

            html = self._get(url)
            videos = self._parse_video_list(html)
            total_pages = self._parse_pagecount(html)

            return {
                'list': videos,
                'page': int(pg),
                'pagecount': total_pages,
                'limit': len(videos),
                'total': total_pages * len(videos) if videos else 0
            }
        except Exception:
            return {'list': [], 'page': 1, 'pagecount': 0, 'limit': 0, 'total': 0}

    # ==================== 详情接口 ====================

    def detailContent(self, ids):
        """获取视频详情"""
        try:
            vod_id = ids[0]

            # 判断是电影还是电视剧：尝试两种URL
            detail_url = None
            for prefix in ['movie', 'tv']:
                test_url = f"{self.host}/{prefix}/{vod_id}.html?sion_id={self.sion_id}"
                try:
                    r = requests.get(test_url, headers=self.header, timeout=15, allow_redirects=False)
                    if r.status_code == 200:
                        detail_url = test_url
                        break
                except Exception:
                    continue

            if not detail_url:
                # 使用默认movie类型
                detail_url = f"{self.host}/movie/{vod_id}.html?sion_id={self.sion_id}"

            html = self._get(detail_url)
            root = etree.HTML(html)

            # ---- 标题 ----
            vod_name = ''
            title_h1 = root.xpath('//h1/text()')
            if title_h1:
                vod_name = title_h1[0].strip()
            if not vod_name:
                title_tag = root.xpath('//title/text()')
                if title_tag:
                    vod_name = title_tag[0].split('_')[0].strip()

            # ---- 年份 ----
            vod_year = ''
            year_span = root.xpath('//h1/following-sibling::span/text()')
            if year_span:
                m = re.search(r'(\d{4})', year_span[0])
                if m:
                    vod_year = m.group(1)
            if not vod_year:
                year_span2 = root.xpath('//div[contains(@class, "text-lg")]//span/text()')
                for s in year_span2:
                    m = re.search(r'(\d{4})', s)
                    if m:
                        vod_year = m.group(1)
                        break

            # ---- 封面 ----
            vod_pic = ''
            pic_img = root.xpath('//div[contains(@class, "vk-card")]//img')
            if pic_img:
                vod_pic = pic_img[0].get('src', '') or pic_img[0].get('data-src', '')
            vod_pic = self._fix_pic(vod_pic)

            # ---- 类型 ----
            vod_type = ''
            type_link = root.xpath('//div[contains(@class, "flex flex-wrap")]//a[contains(@class, "vk-link")]/text()')
            if type_link:
                vod_type = type_link[0].strip()

            # ---- 地区 ----
            vod_area = ''
            area_link = root.xpath('//a[contains(@href, "area=")]/text()')
            if area_link:
                vod_area = area_link[0].strip()

            # ---- 分类标签 ----
            vod_class = ''
            class_links = root.xpath('//span[contains(@class, "text-[#666]")]//a[contains(@href, "class=")]/text()')
            if class_links:
                vod_class = ', '.join([c.strip() for c in class_links])

            # ---- 导演 ----
            vod_director = ''
            director_links = root.xpath('//div[contains(., "导演")]//a[contains(@href, "director=")]/text()')
            if director_links:
                vod_director = ', '.join([d.strip() for d in director_links])

            # ---- 主演 ----
            vod_actor = ''
            actor_links = root.xpath('//div[contains(., "主演")]//a[contains(@href, "actor=")]/text()')
            if actor_links:
                vod_actor = ', '.join([a.strip() for a in actor_links])

            # ---- 简介 ----
            vod_content = ''
            desc_elem = root.xpath('//div[contains(@class, "reset-style")]//p/text()')
            if desc_elem:
                vod_content = '\n'.join([d.strip() for d in desc_elem if d.strip()])
            if not vod_content:
                desc_elem2 = root.xpath('//div[contains(@class, "reset-style")]/text()')
                if desc_elem2:
                    vod_content = '\n'.join([d.strip() for d in desc_elem2 if d.strip()])

            # ---- 播放列表 ----
            vod_play_from = []
            vod_play_url = []

            episode_lists = root.xpath('//div[contains(@class, "episode-list")]')
            for idx, ep_list in enumerate(episode_lists):
                # 线路名：取该线路首个 episode-button 的 data-origin 属性，
                # 并去掉末尾的 m3u8（如 modum3u8→modu、jsm3u8→js、vip→vip）
                ep_links = ep_list.xpath('.//a[contains(@class, "episode-button")]')
                source_name = ''
                if ep_links:
                    origin = (ep_links[0].get('data-origin') or '').strip()
                    if origin.endswith('m3u8'):
                        origin = origin[:-4]
                    source_name = origin
                if not source_name:
                    source_name = f'线路{idx + 1}'

                play_list = []
                for a in ep_links:
                    # 集名提取（多结构兼容）：
                    #   1) data-title 属性 —— vip / wztv 等卡片式线路集名在此
                    #   2) <button> 子元素文本 —— 普通 m3u8 线路
                    #   3) title 属性
                    #   4) <img> alt 兜底
                    ep_name = (a.get('data-title') or '').strip()
                    if not ep_name:
                        btn = a.xpath('.//button/text()')
                        if btn:
                            ep_name = btn[0].strip()
                    if not ep_name:
                        ep_name = (a.get('title') or '').strip()
                    if not ep_name:
                        alt = a.xpath('.//img/@alt')
                        if alt:
                            ep_name = (alt[0] or '').strip()

                    href = a.get('href', '')
                    if not ep_name or not href:
                        continue

                    play_url = self._fix_url(href)
                    play_list.append(f"{ep_name}${play_url}")

                if play_list:
                    vod_play_from.append(source_name)
                    vod_play_url.append("#".join(play_list))

            if vod_play_from:
                vod_play_from_str = "$$$".join(vod_play_from)
                vod_play_url_str = "$$$".join(vod_play_url)
            else:
                vod_play_from_str = "默认"
                vod_play_url_str = ""

            detail = {
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_type": vod_type,
                "vod_area": vod_area,
                "vod_year": vod_year,
                "vod_class": vod_class,
                "vod_actor": vod_actor,
                "vod_director": vod_director,
                "vod_content": vod_content,
                "vod_play_from": vod_play_from_str,
                "vod_play_url": vod_play_url_str
            }
            return {'list': [detail]}
        except Exception as e:
            return {'list': []}

    # ==================== 播放接口 ====================

    def _extract_aa_url(self, html):
        """从播放页 xg_video_player_doc.aa 提取真实视频URL

        页面内形如:  aa: JSON.parse('{\\u0022origin\\u0022:...,\\u0022url\\u0022:\\u0022...\\u0022}')
        存在两层转义：
          \\u0022 (单反斜杠) → "    JSON 双引号转义
          \\/     (单反斜杠) → /    JSON 斜杠转义
          \\\\u0026 (双反斜杠) → &  JS 字符串层对 JSON \\u0026 的二次转义
        需先解双重转义 \\\\uXXXX，再解单层 \\u0022 / \\/，否则 json.loads 会失败。
        """
        for pat in (
            r"aa\s*:\s*JSON\.parse\s*\(\s*'(\{.*?\})'\s*\)",
            r'aa\s*:\s*JSON\.parse\s*\(\s*"(\{.*?\})"\s*\)',
        ):
            m = re.search(pat, html, re.DOTALL)
            if not m:
                continue
            aa_json = m.group(1)
            # 1. 先解 JS 双重转义：\\uXXXX → 对应字符（如 \\u0026 → &）
            aa_json = re.sub(
                r'\\\\u([0-9a-fA-F]{4})',
                lambda mm: chr(int(mm.group(1), 16)),
                aa_json
            )
            # 2. 再解 JSON 单层转义：\u0022 → "，\/ → /
            aa_json = aa_json.replace('\\u0022', '"').replace('\\/', '/')
            try:
                aa_data = json.loads(aa_json)
                url = (aa_data.get('url') or '').strip()
                if url:
                    return url
            except Exception:
                pass
        return None

    def _resolve_play_url(self, url):
        """递归解析多级 m3u8，返回最终可播放的媒体播放列表 URL

        vip 线路的 aa.url 是站内相对路径 /api/m3u8?...，解析链如下：
          dhvideo.cc/api/m3u8      →302→ box.dyrs.com.de/api/super  (主播放列表,200)
            └─ /api/direct?vip1    →302→ vip1.wzzym3u8.cc/.../1.m3u8 (媒体播放列表,可播放)

        requests 的 allow_redirects 只跟 HTTP 302，不会解析 m3u8 内容里的子流相对路径，
        因此需要手动逐层解析：遇到主播放列表(EXT-X-STREAM-INF)就取子流 URL 继续跟进，
        遇到媒体播放列表(EXTINF)即为目标，返回该 URL。
        """
        visited = set()
        current = self._fix_url(url)
        for _ in range(10):  # 最多 10 层，防死循环
            if current in visited:
                break
            visited.add(current)
            try:
                r = requests.get(current, headers=self.header,
                                 timeout=20, allow_redirects=True)
            except Exception:
                return current
            final_url = r.url or current
            text = r.text or ''
            # 主播放列表：含 EXT-X-STREAM-INF，需取子流 URL 继续解析
            if '#EXT-X-STREAM-INF' in text:
                sub_urls = []
                for line in text.splitlines():
                    line = line.strip()
                    if line and not line.startswith('#'):
                        sub_urls.append(urllib.parse.urljoin(final_url, line))
                if not sub_urls:
                    return final_url
                # 逐个尝试子流，优先选重定向后落在 .m3u8 媒体播放列表的
                # （/api/direct 会 302 到 vip1.wzzym3u8.cc/.../1.m3u8，比
                #   /api/m3u8 返回的混合分片列表兼容性更好）
                fallback = None
                for sub_url in sub_urls:
                    if sub_url in visited:
                        continue
                    try:
                        sr = requests.get(sub_url, headers=self.header,
                                          timeout=15, allow_redirects=True)
                        sub_final = sr.url or sub_url
                        sub_text = sr.text or ''
                        if '.m3u8' in sub_final.lower() and '#EXTINF' in sub_text:
                            return sub_final
                        if fallback is None and '#EXTINF' in sub_text:
                            fallback = sub_final
                    except Exception:
                        continue
                if fallback:
                    return fallback
                current = sub_urls[0]
                continue
            # 媒体播放列表（含 EXTINF）或视频直链 → 可播放，返回
            if '#EXTINF' in text or self.isVideoFormat(final_url):
                return final_url
            return final_url
        return current

    def playerContent(self, flag, id, vipFlags):
        """解析播放地址 - 从 xg_video_player_doc 提取真实视频URL"""
        try:
            play_url = id if id.startswith('http') else self._fix_url(id)
            html = self._get(play_url)

            # 主路径：解析 aa 字段中的真实地址
            real_url = self._extract_aa_url(html)
            if real_url:
                # 兼容 // 与 / 开头的相对路径（vip 线路返回 /api/m3u8?...）
                # 递归解析多级 m3u8，拿到最终可播放的媒体播放列表
                real_url = self._resolve_play_url(real_url)
                if real_url:
                    return {
                        "parse": 0,
                        "playUrl": "",
                        "url": real_url,
                        "header": json.dumps({
                            "User-Agent": "Mozilla/5.0",
                            "Referer": self.host
                        })
                    }

            # 兜底1: 直接查找 m3u8 链接
            m3u8_match = re.search(
                r'["\'](https?://[^"\'\s<>]+\.m3u8[^"\'\s<>]*)["\']',
                html
            )
            if m3u8_match:
                real_url = m3u8_match.group(1)
                return {
                    "parse": 0, "playUrl": "", "url": real_url,
                    "header": json.dumps({"User-Agent": "Mozilla/5.0", "Referer": self.host})
                }

            # 兜底2: 直接查找 mp4/flv/ts/mkv 链接
            mp4_match = re.search(
                r'["\'](https?://[^"\'\s<>]+\.(?:mp4|flv|ts|mkv)[^"\'\s<>]*)["\']',
                html
            )
            if mp4_match:
                real_url = mp4_match.group(1)
                return {
                    "parse": 0, "playUrl": "", "url": real_url,
                    "header": json.dumps({"User-Agent": "Mozilla/5.0", "Referer": self.host})
                }

            # 最终兜底：返回播放页地址让解析器处理
            return {
                "parse": 1, "playUrl": "", "url": play_url,
                "header": json.dumps(self.header)
            }
        except Exception:
            return {"parse": 0, "playUrl": "", "url": ""}

    # ==================== 搜索接口 ====================

    def searchContent(self, key, quick, pg='1'):
        """搜索"""
        videos = []
        try:
            page = max(int(pg) - 1, 0)
            url = f"{self.host}/s.html"
            params = {
                "name": key,
                "page": str(page) if page > 0 else "0",
                "sort_field": "_id",
                "sion_id": self.sion_id,
            }
            html = self._get(url, params=params)
            videos = self._parse_video_list(html)
            total_pages = self._parse_pagecount(html)

            return {
                'list': videos,
                'page': int(pg),
                'pagecount': total_pages,
                'limit': len(videos),
                'total': len(videos)
            }
        except Exception:
            return {'list': [], 'page': 1, 'pagecount': 0, 'limit': 0, 'total': 0}

    # ==================== 辅助方法 ====================

    def isVideoFormat(self, url):
        """判断URL是否为直链视频格式"""
        return any(url.lower().endswith(fmt) for fmt in ['.m3u8', '.mp4', '.flv', '.ts', '.mkv', '.avi', '.mov'])

    def manualVideoCheck(self):
        pass

    def localProxy(self, params):
        return None

    def destroy(self):
        pass
