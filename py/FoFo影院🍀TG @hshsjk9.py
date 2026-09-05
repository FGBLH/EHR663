# coding=utf-8
"""
目标站: FoFo影院 (fofo22.com)
模板: fofo22 影视聚合适配版
站点类型: 影视聚合搜索 / 爬虫播放
核心逻辑: 逆向 JS decryptDict 解密播放数据，POST /source/ 获取真实 m3u8 播放地址
"""
import re
import sys
import json
import urllib.parse
import urllib.request

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    def init(self, extend=""):
        self.site_url = "https://fofo22.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': self.site_url + "/",
        }
        self.default_pic = "https://pic.rmb.bdstatic.com/bjh/user/default.png"

    # ========== 工具方法 ==========

    def _fix_url(self, url):
        if not url:
            return ""
        url = url.strip()
        if url.startswith("//"):
            return "https:" + url
        if not url.startswith("http"):
            return urllib.parse.urljoin(self.site_url, url)
        return url

    def _decrypt_str(self, s):
        """逆向页面 JS decryptDict() 的字符解密：每个字符 charCode - 1"""
        if not s:
            return s
        return ''.join(chr(ord(c) - 1) for c in s)

    def _decrypt_obj(self, obj):
        """递归解密 decryptDict 输出的 JS 对象（key 和 value 均需解密）"""
        if isinstance(obj, str):
            dec = self._decrypt_str(obj)
            try:
                return json.loads(dec)
            except Exception:
                return dec
        elif isinstance(obj, list):
            return [self._decrypt_obj(x) for x in obj]
        elif isinstance(obj, dict):
            result = {}
            for k, v in obj.items():
                dk = self._decrypt_str(k)
                result[dk] = self._decrypt_obj(v)
            return result
        return obj

    def _parse_js_object(self, raw_str):
        """
        将 JS 对象字面量解析为 Python dict
        不使用 eval()，避免在受限环境中失败
        策略：将单引号字符串转为双引号，再用 json.loads 解析
        """
        # 将单引号字符串转换为双引号字符串
        # 匹配 '...' 形式的字符串（不跨行，不含单引号本身）
        json_str = re.sub(r"'([^']*)'", r'"\1"', raw_str)
        return json.loads(json_str)

    def _get_play_data(self, html):
        """
        从详情页 HTML 中提取并解密 decryptDict 播放数据
        返回: (play_from_list, play_url_list)
        """
        m = re.search(r'var\s+urlList\s*=\s*decryptDict\((\{.*?\})\)\s*[;\n\r]', html, re.DOTALL)
        if not m:
            return [], []
        raw_str = m.group(1)

        # 策略1：用 json.loads 解析（最安全）
        raw = None
        try:
            raw = self._parse_js_object(raw_str)
        except Exception:
            pass

        # 策略2：用 eval 解析（兼容性好但受限环境可能不支持）
        if raw is None:
            try:
                raw = eval(raw_str)
            except Exception:
                pass

        # 策略3：用 ast.literal_eval 解析
        if raw is None:
            try:
                import ast
                raw = ast.literal_eval(raw_str)
            except Exception:
                return [], []

        try:
            data = self._decrypt_obj(raw)
            sources = data.get("source", [])
            url_list = data.get("url_list", [])

            play_from = []
            play_url = []
            for i, source in enumerate(sources):
                if i >= len(url_list):
                    break
                episodes = url_list[i]
                if not episodes:
                    continue
                ep_list = []
                for ep in episodes:
                    sid = str(ep.get("sid", ""))
                    title = ep.get("title", "")
                    if not sid:
                        continue
                    ep_list.append(f"{title}${sid}")
                if ep_list:
                    play_from.append(str(source))
                    play_url.append("#".join(ep_list))
            return play_from, play_url
        except Exception:
            return [], []

    def _fetch_m3u8(self, sid, referer):
        """
        POST /source/ 获取真实 m3u8 播放地址
        sid: 纯数字的资源 ID
        """
        source_api = f"{self.site_url}/source/"
        post_headers = {
            'User-Agent': self.headers['User-Agent'],
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': referer,
        }

        # 策略1：使用 self.post（部分 TVBox 框架支持）
        try:
            resp = self.post(source_api, headers=post_headers, data={"id": sid})
            if resp and resp.text:
                url = resp.text.strip()
                if url and url.startswith("http"):
                    return url
        except Exception:
            pass

        # 策略2：使用 urllib.request（最通用）
        try:
            post_data = urllib.parse.urlencode({"id": sid}).encode('utf-8')
            req = urllib.request.Request(source_api, data=post_data, headers=post_headers, method='POST')
            with urllib.request.urlopen(req, timeout=15) as resp:
                url = resp.read().decode('utf-8').strip()
                if url and url.startswith("http"):
                    return url
        except Exception:
            pass

        return ""

    def _extract_videos(self, html):
        """从 HTML 中提取视频列表（首页 / 分类 / 搜索通用）"""
        videos = []
        pattern = re.compile(
            r'<a\s+href="(/(?:dianying|dianshiju|zongyi|dongman)/(\d+))"[^>]*class="thumbnail"[^>]*>.*?'
            r'<img[^>]*src="([^"]*)"[^>]*alt="([^"]*)"[^>]*>.*?'
            r'<div\s+class="note"><span>([^<]*)</span>',
            re.DOTALL
        )
        seen = set()
        for href, vid, pic, name, note in pattern.findall(html):
            if vid in seen:
                continue
            seen.add(vid)
            vod_name = name.strip() if name.strip() else vid
            videos.append({
                "vod_id": href.lstrip('/'),
                "vod_name": vod_name,
                "vod_pic": self._fix_url(pic),
                "vod_remarks": note.strip()
            })
        return videos

    # ========== 筛选配置 ==========

    def _get_filters(self):
        movie_genres = [
            {"n": "全部", "v": "0"}, {"n": "剧情", "v": "1"}, {"n": "喜剧", "v": "2"},
            {"n": "动作", "v": "3"}, {"n": "爱情", "v": "4"}, {"n": "科幻", "v": "5"},
            {"n": "悬疑", "v": "6"}, {"n": "惊悚", "v": "7"}, {"n": "恐怖", "v": "8"},
            {"n": "犯罪", "v": "9"}, {"n": "同性", "v": "10"}, {"n": "音乐", "v": "11"},
            {"n": "歌舞", "v": "12"}, {"n": "传记", "v": "13"}, {"n": "历史", "v": "14"},
            {"n": "战争", "v": "15"}, {"n": "西部", "v": "16"}, {"n": "奇幻", "v": "17"},
            {"n": "冒险", "v": "18"}, {"n": "灾难", "v": "19"}, {"n": "武侠", "v": "20"},
            {"n": "伦理", "v": "21"},
        ]
        zongyi_genres = [
            {"n": "全部", "v": "0"}, {"n": "真人秀", "v": "1"}, {"n": "脱口秀", "v": "2"},
            {"n": "纪录片", "v": "3"}, {"n": "传记", "v": "4"}, {"n": "歌舞", "v": "5"},
        ]
        movie_areas = [
            {"n": "全部", "v": "0"}, {"n": "中国大陆", "v": "1"}, {"n": "美国", "v": "2"},
            {"n": "香港", "v": "3"}, {"n": "台湾", "v": "4"}, {"n": "日本", "v": "5"},
            {"n": "韩国", "v": "6"}, {"n": "英国", "v": "7"}, {"n": "法国", "v": "8"},
            {"n": "德国", "v": "9"}, {"n": "意大利", "v": "10"}, {"n": "西班牙", "v": "11"},
            {"n": "印度", "v": "12"}, {"n": "泰国", "v": "13"}, {"n": "俄罗斯", "v": "14"},
            {"n": "伊朗", "v": "15"}, {"n": "加拿大", "v": "16"}, {"n": "澳大利亚", "v": "17"},
            {"n": "爱尔兰", "v": "18"}, {"n": "瑞典", "v": "19"}, {"n": "巴西", "v": "20"},
            {"n": "丹麦", "v": "21"},
        ]
        zongyi_areas = [
            {"n": "全部", "v": "0"}, {"n": "中国大陆", "v": "1"}, {"n": "美国", "v": "2"},
            {"n": "香港", "v": "3"}, {"n": "台湾", "v": "4"}, {"n": "日本", "v": "5"},
            {"n": "韩国", "v": "6"},
        ]
        dongman_areas = [
            {"n": "全部", "v": "0"}, {"n": "中国大陆", "v": "1"}, {"n": "美国", "v": "2"},
            {"n": "日本", "v": "3"}, {"n": "韩国", "v": "4"},
        ]
        years = [
            {"n": "全部", "v": "0"}, {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"},
            {"n": "2024", "v": "2024"}, {"n": "2023", "v": "2023"}, {"n": "2022", "v": "2022"},
            {"n": "2021", "v": "2021"}, {"n": "2020", "v": "2020"}, {"n": "2019", "v": "2019"},
            {"n": "2018", "v": "2018"}, {"n": "2017", "v": "2017"}, {"n": "2016", "v": "2016"},
            {"n": "2015", "v": "2015"}, {"n": "2014", "v": "2014"}, {"n": "2013", "v": "2013"},
            {"n": "2012", "v": "2012"}, {"n": "2011", "v": "2011"}, {"n": "2010", "v": "2010"},
            {"n": "2009", "v": "2009"}, {"n": "2008", "v": "2008"}, {"n": "2007", "v": "2007"},
            {"n": "2006", "v": "2006"}, {"n": "2005", "v": "2005"}, {"n": "其他", "v": "1"},
        ]
        sorts = [
            {"n": "按时间", "v": "0"}, {"n": "按人气", "v": "1"}, {"n": "按评分", "v": "2"},
        ]

        def make(genres, areas):
            return [
                {"key": "genre", "name": "类型", "value": genres},
                {"key": "area", "name": "地区", "value": areas},
                {"key": "year", "name": "年份", "value": years},
                {"key": "sort", "name": "排序", "value": sorts},
            ]

        return {
            "dianying": make(movie_genres, movie_areas),
            "dianshiju": make(movie_genres, movie_areas),
            "zongyi": make(zongyi_genres, zongyi_areas),
            "dongman": make(movie_genres, dongman_areas),
        }

    # ========== 首页 ==========

    def homeContent(self, filter):
        categories = [
            {"type_id": "dianying", "type_name": "电影"},
            {"type_id": "dianshiju", "type_name": "电视剧"},
            {"type_id": "zongyi", "type_name": "综艺"},
            {"type_id": "dongman", "type_name": "动漫"},
        ]
        resp = self.fetch(self.site_url + "/", headers=self.headers)
        videos = self._extract_videos(resp.text) if resp else []
        return {
            "class": categories,
            "list": videos[:30],
            "filters": self._get_filters()
        }

    def homeVideoContent(self):
        return self.homeContent(False)

    # ========== 分类 ==========

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        extend = extend or {}
        genre = extend.get("genre", "0")
        area = extend.get("area", "0")
        year = extend.get("year", "0")
        sort = extend.get("sort", "0")

        if genre == "0" and area == "0" and year == "0" and sort == "0":
            url = f"{self.site_url}/{tid}?page={page}"
        else:
            url = f"{self.site_url}/{tid}/{genre}-{area}-{year}-{sort}?page={page}"

        resp = self.fetch(url, headers=self.headers)
        videos = []
        pagecount = 1
        if resp:
            html = resp.text
            videos = self._extract_videos(html)
            m = re.search(r'class="pagination[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
            if m:
                pages = re.findall(r'page=(\d+)', m.group(0))
                if pages:
                    pagecount = max(int(p) for p in pages)

        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount if pagecount > 0 else 1,
            "limit": 24,
            "total": pagecount * 24 if pagecount > 0 else len(videos)
        }

    # ========== 搜索 ==========

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        encoded = urllib.parse.quote(key)
        url = f"{self.site_url}/search?q={encoded}&page={page}"
        resp = self.fetch(url, headers=self.headers)
        videos = []
        pagecount = 1
        if resp:
            html = resp.text
            videos = self._extract_videos(html)
            m = re.search(r'class="pagination[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
            if m:
                pages = re.findall(r'page=(\d+)', m.group(0))
                if pages:
                    pagecount = max(int(p) for p in pages)

        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount if pagecount > 0 else 1,
            "limit": 24,
            "total": pagecount * 24 if pagecount > 0 else len(videos)
        }

    # ========== 详情 ==========

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vid = str(ids[0])
        url = f"{self.site_url}/{vid}"
        resp = self.fetch(url, headers=self.headers)
        if not resp:
            return {"list": []}

        html = resp.text

        # ---- 标题 + 年份 ----
        name = vid
        year = ""
        title_match = re.search(r'<h1[^>]*class="product-title"[^>]*>(.*?)</h1>', html, re.DOTALL)
        if title_match:
            title_html = title_match.group(1)
            year_m = re.search(r'\((\d{4})\)', title_html)
            if year_m:
                year = year_m.group(1)
            name = re.sub(r'<[^>]+>', '', title_html).strip()
            name = re.sub(r'\(\d{4}\)', '', name).strip()
            name = re.sub(r'\d+\.\d+', '', name).strip()
            if not name:
                name = vid

        # ---- 封面图 ----
        pic = self.default_pic
        # 优先 og:image
        pic_match = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', html)
        if pic_match:
            pic = self._fix_url(pic_match.group(1))
        else:
            # 查找 product-header 内的 thumb 图片（src 可能在 class 之前或之后）
            header_m = re.search(r'class="product-header"[^>]*>(.*?)</header>', html, re.DOTALL)
            if header_m:
                img_m = re.search(r'<img[^>]*>', header_m.group(1))
                if img_m:
                    src_m = re.search(r'src="([^"]+)"', img_m.group(0))
                    if src_m:
                        pic = self._fix_url(src_m.group(1))
            if pic == self.default_pic:
                # 全局查找 thumb 图片
                img_m = re.search(r'<img[^>]*class="[^"]*thumb[^"]*"[^>]*>', html)
                if img_m:
                    src_m = re.search(r'src="([^"]+)"', img_m.group(0))
                    if src_m:
                        pic = self._fix_url(src_m.group(1))

        # ---- 影视信息（导演 / 主演 / 类型 / 地区 / 简介）----
        director = ""
        actor = ""
        type_name = ""
        area = ""
        content = ""

        excerpts = re.findall(r'<div\s+class="product-excerpt">(.*?)</div>', html, re.DOTALL)
        for excerpt in excerpts:
            label_m = re.match(r'\s*(.*?)[：:]', excerpt)
            if not label_m:
                continue
            label = label_m.group(1).strip()
            span_m = re.search(r'<span>(.*?)</span>', excerpt, re.DOTALL)
            if not span_m:
                continue
            raw_val = span_m.group(1)
            val = re.sub(r'<[^>]+>', ' ', raw_val)
            val = re.sub(r'\s+', ' ', val).strip()

            if label == '导演' and not director:
                director = val
            elif label == '主演' and not actor:
                actor = val
            elif label == '类型' and not type_name:
                type_name = val
            elif label in ('制片国家/地区', '制片国家') and not area:
                area = val
            elif label in ('剧情简介', '简介') and not content:
                content = val

        # ---- 播放数据 ----
        play_from, play_url = self._get_play_data(html)
        if not play_url:
            play_from = ["默认线路"]
            play_url = [f"播放${vid}"]

        result = [{
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_year": year,
            "vod_area": area,
            "vod_type": type_name,
            "vod_play_from": '$$$'.join(play_from),
            "vod_play_url": '$$$'.join(play_url)
        }]
        return {"list": result}

    # ========== 播放 ==========

    def playerContent(self, flag, id, vipFlags):
        sid = id
        if "$" in id:
            sid = id.split("$")[-1]

        # 如果 sid 包含 "/"（来自兜底线路的 vid），提取纯数字部分
        if "/" in sid:
            sid = sid.rsplit("/", 1)[-1]

        referer = self.site_url + "/"

        # sid 是纯数字，POST /source/ 获取真实 m3u8
        m3u8_url = self._fetch_m3u8(sid, referer)

        if m3u8_url and ('.m3u8' in m3u8_url or '.mp4' in m3u8_url):
            return {
                "parse": 0,
                "url": m3u8_url,
                "header": self.headers
            }

        if not m3u8_url:
            m3u8_url = f"{self.site_url}/{sid}"

        return {
            "parse": 1,
            "url": m3u8_url,
            "header": self.headers
        }

    # ========== 辅助 ==========

    def isVideoFormat(self, url):
        return '.m3u8' in url or '.mp4' in url

    def manualVideoCheck(self):
        return False
