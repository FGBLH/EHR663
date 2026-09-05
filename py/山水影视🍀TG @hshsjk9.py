# -*- coding: utf-8 -*-
"""
山水影院 Spider – 最终修复版（剧集排序修复 + 集数命名修正）
站点: http://www.shanxihighway.com/
"""

import sys
import json
import re
import time
import html
from urllib.parse import urljoin, quote

sys.path.append('..')

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
        def fetch(self, url, headers=None, **kw):
            timeout = kw.pop('timeout', 15)
            r = _rq.get(url, headers=headers, timeout=timeout, verify=False, **kw)
            return r

# ============================================================
# 常量配置
# ============================================================

BASE_URL = "http://www.shanxihighway.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

CLASSES = [
    {"type_name": "电影", "type_id": "1"},
    {"type_name": "电视剧", "type_id": "2"},
    {"type_name": "综艺", "type_id": "3"},
    {"type_name": "动漫", "type_id": "4"},
    {"type_name": "爽文短剧", "type_id": "30"},
    {"type_name": "伦理片", "type_id": "36"},
]

LINE_NAMES = {
    "mgtv": "芒果TV", "qq": "腾讯视频", "qiyi": "爱奇艺", "youku": "优酷",
    "bilibili": "B站", "dytt": "电影天堂", "ffzy": "非凡资源",
    "bfzym3u8": "非凡资源", "zuidam3u8": "最大资源", "wjm3u8": "无尽资源",
    "snm3u8": "索尼资源", "wolong": "卧龙资源", "xlm3u8": "新浪资源",
    "tpm3u8": "淘片资源", "dbm3u8": "百度资源", "yun": "云播", "bdys": "百度影音",
    "ckm3u8": "酷客", "km3u8": "快播",
    "hym3u8": "红影资源", "1080zyk": "1080影视", "1080zy": "1080影视",
    "hzm3u8": "红影资源", "hkzy": "好看资源",
    "ukm3u8": "优酷源", "mtm3u8": "美淘资源", "dyttm3u8": "电影天堂",
    "wlm3u8": "卧龙资源", "wolzy": "卧龙资源", "zuidazy": "最大资源",
}

CACHE_HOME_TTL = 300
CACHE_CATEGORY_TTL = 300
CACHE_DETAIL_TTL = 1800

# 预编译正则
_RE_LI_BLOCK = re.compile(r'<li\s+[^>]*class="[^"]*pic-list-hover[^"]*"[^>]*>(.*?)</li>', re.DOTALL)
_RE_PIC_IMG_HREF = re.compile(r'<a\s+class="pic-img"\s+href="([^"]+)"')
_RE_WEIHU_HREF = re.compile(r'<a[^>]*href="(/weihu/\d+\.html)"')
_RE_IMG_DATA_ORIGINAL = re.compile(r'<img[^>]*data-original="([^"]+)"')
_RE_TITLES_SPAN = re.compile(r'<span\s+class="titles">([^<]*)</span>')
_RE_NAME_H3 = re.compile(r'<h3\s+class="name[^"]*"[^>]*>\s*<a[^>]*>([^<]+)</a>')
_RE_NAME_H3_FALLBACK = re.compile(r'<h3[^>]*>\s*<a[^>]*>([^<]+)</a>')
_RE_VOD_ID = re.compile(r'/(\d+)\.html')
_RE_TAB = re.compile(r'<a[^>]*id="#con_playlist_(\d+)"[^>]*>(.*?)</a>', re.DOTALL)
_RE_GICO = re.compile(r'class="gico\s+(\w+)"')
_RE_UL = re.compile(r'<ul[^>]*id="con_playlist_(\d+)"[^>]*>(.*?)</ul>', re.DOTALL)
_RE_EP_LINK = re.compile(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
_RE_H1 = re.compile(r'<h1[^>]*>(.*?)</h1>', re.DOTALL)
_RE_PLAYER_AAAA = re.compile(r'var\s+player_aaaa\s*=\s*(\{.*?\})', re.DOTALL)
_RE_PLAYER_ANY = re.compile(r'var\s+player_\w*\s*=\s*(\{.*?\})', re.DOTALL)
_RE_JSON_URL_FIELD = re.compile(r'"url"\s*:\s*"([^"]+)"')
_RE_MEDIA = re.compile(r'https?://[^\s"\']+\.(?:m3u8|mp4|flv|mkv)(?:[^\s"\']*)', re.IGNORECASE)
_RE_DIRECT_MEDIA = re.compile(r'\.(m3u8|mp4|flv|mkv)(\?|$)', re.IGNORECASE)
_RE_TAG = re.compile(r'<[^>]+>')
_RE_PAGE_NUM = re.compile(r'data="p-(\d+)"')
_RE_LAST_PAGE = re.compile(r'/show/\d+--------(\d+)---\.html')
_RE_NUM_FRAC = re.compile(r'class="num">(\d+)/(\d+)<')
_RE_TOTAL_JS = re.compile(r'let total = (\d+)')

# ============================================================
# Spider 主类
# ============================================================

class Spider(Spider):

    def getName(self):
        return "山水影院"

    def init(self, extend=""):
        self.header = {
            "User-Agent": UA,
            "Referer": BASE_URL + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        self._debug = False
        self._cache = {'home': {}, 'category': {}, 'detail': {}}

    def _log(self, msg):
        if self._debug:
            print(f"[山水影院] {msg}")

    def _cache_get(self, bucket, key, ttl):
        bucket_data = self._cache.get(bucket)
        if not bucket_data:
            return None
        entry = bucket_data.get(key)
        if not entry or not isinstance(entry, dict):
            return None
        now = time.time()
        if now - entry.get('time', 0) > ttl:
            bucket_data[key] = None
            return None
        return entry.get('data')

    def _cache_put(self, bucket, key, data):
        if bucket not in self._cache:
            self._cache[bucket] = {}
        self._cache[bucket][key] = {'data': data, 'time': time.time()}

    def _fetch_html(self, url, timeout=12, referer=None):
        try:
            headers = dict(self.header)
            if referer:
                headers["Referer"] = referer
            rsp = self.fetch(url, headers=headers, timeout=timeout)
            if rsp.encoding is None:
                rsp.encoding = rsp.apparent_encoding or 'utf-8'
            return rsp.text
        except Exception as e:
            self._log(f"请求失败 {url}: {str(e)}")
            return ""

    def _unescape(self, text):
        return html.unescape(text).strip() if text else ""

    def _clean_url(self, url):
        if not url:
            return ""
        url = url.strip()
        if url.startswith("//"):
            url = "https:" + url
        elif url.startswith("/"):
            url = urljoin(BASE_URL, url)
        return url

    def _strip_tags(self, text):
        if not text:
            return ""
        text = _RE_TAG.sub('', text)
        return html.unescape(text).strip()

    def _get_line_name(self, key):
        key = key.strip()
        if key in LINE_NAMES:
            return LINE_NAMES[key]
        lower = key.lower()
        if 'm3u8' in lower:
            return key + "源"
        if 'yun' in lower:
            return "云播"
        if 'qq' in lower or 'tencent' in lower:
            return "腾讯"
        if 'qiyi' in lower or 'iqiyi' in lower:
            return "爱奇艺"
        if 'youku' in lower:
            return "优酷"
        if 'mgtv' in lower:
            return "芒果"
        return key

    # ---------- 集数提取（增强版） ----------
    def _extract_ep_number(self, url):
        """从播放页URL提取真实集数，支持多种格式"""
        if not url:
            return None
        # 匹配 /bofang/数字-数字-数字.html 或 /bofang/数字-数字.html
        m = re.search(r'/bofang/\d+-\d+-(\d+)\.html', url)
        if m:
            return int(m.group(1))
        # 匹配任意 -数字.html （可能带参数）
        m = re.search(r'-(\d+)\.html', url)
        if m and m.group(1).isdigit():
            return int(m.group(1))
        return None

    def _parse_video_list_html(self, html_txt):
        items = []
        for block in _RE_LI_BLOCK.findall(html_txt):
            href_m = _RE_PIC_IMG_HREF.search(block) or _RE_WEIHU_HREF.search(block)
            if not href_m:
                continue
            href = href_m.group(1)
            pic_m = _RE_IMG_DATA_ORIGINAL.search(block)
            pic = self._clean_url(pic_m.group(1)) if pic_m else ''
            remark_m = _RE_TITLES_SPAN.search(block)
            remark = self._unescape(remark_m.group(1)) if remark_m else "HD"
            title_m = _RE_NAME_H3.search(block) or _RE_NAME_H3_FALLBACK.search(block)
            if not title_m:
                continue
            name = self._unescape(title_m.group(1))
            if not name:
                continue
            vid = href.rstrip('/').split('/')[-1].replace('.html', '')
            if not vid.isdigit():
                id_m = _RE_VOD_ID.search(href)
                vid = id_m.group(1) if id_m else href
            items.append({
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": remark or "HD",
            })
        return items

    # ----------------------------------------------------------
    # 核心：提取播放源并排序（修复倒序问题）
    # ----------------------------------------------------------
    def _extract_play_from_html(self, html_txt):
        from_list, url_list = [], []

        try:
            # 1) 线路名
            tab_matches = _RE_TAB.findall(html_txt)
            gico_map = {}
            for m in re.finditer(
                r'<a[^>]*id="#con_playlist_(\d+)"[^>]*class="gico\s+(\w+)"[^>]*>(.*?)</a>',
                html_txt, re.DOTALL
            ):
                num, key, name = m.group(1), m.group(2), m.group(3)
                if num not in gico_map:
                    gico_map[num] = (key, name)

            seen_ids = set()
            line_names = []
            for num, raw_name in tab_matches:
                if num in seen_ids:
                    continue
                seen_ids.add(num)
                display = self._strip_tags(raw_name).strip()
                if num in gico_map:
                    g_key, _g_name = gico_map[num]
                    mapped = self._get_line_name(g_key)
                    if re.match(r'^线路?[一二三四五六七八九十\d]+$', display) or not display:
                        display = mapped
                    elif display.lower() == g_key.lower():
                        display = mapped
                if not display:
                    display = f"线路{num}"
                line_names.append((num, display))

            # 2) 提取剧集并排序
            ul_matches = _RE_UL.findall(html_txt)
            ep_by_num = {}
            for num, ul_content in ul_matches:
                eps = _RE_EP_LINK.findall(ul_content)
                ep_list_raw = []  # 存储 (ep_num, display_name, full_url)

                for idx, (href, raw_ep_name) in enumerate(eps, 1):
                    ep_name = self._strip_tags(raw_ep_name).strip()
                    ep_num = self._extract_ep_number(href)

                    # ---- 集名修正 ----
                    if ep_num is not None:
                        ep_name = f"第{ep_num}集"
                    else:
                        # 检查显示名是否为纯数字
                        digit_match = re.match(r'^(\d+)$', ep_name)
                        if digit_match:
                            ep_name = f"第{int(digit_match.group(1))}集"
                        elif ep_name and re.match(r'^第?\d+[集期话回]$', ep_name):
                            num_m = re.match(r'^第?(\d+)[集期话回]$', ep_name)
                            if num_m:
                                ep_name = f"第{int(num_m.group(1))}集"
                        else:
                            # 保留非数字特殊名称（如“花絮”），否则用序号
                            if ep_name and not re.match(r'^\d+$', ep_name) and len(ep_name) < 20:
                                pass
                            else:
                                ep_name = f"第{idx}集"
                    full_url = urljoin(BASE_URL, href)
                    ep_list_raw.append((ep_num, ep_name, full_url))

                # ---- 关键：按数字升序排序 ----
                try:
                    ep_list_raw.sort(key=lambda x: (x[0] is None, x[0] if x[0] is not None else float('inf')))
                except Exception:
                    pass  # 排序失败则保持原序
                ep_list = [f"{name}${url}" for _, name, url in ep_list_raw]
                ep_by_num[num] = ep_list

            # 组装
            if line_names and ep_by_num:
                for num, display in line_names:
                    eps = ep_by_num.get(num, [])
                    if eps:
                        from_list.append(display)
                        url_list.append("#".join(eps))
                if from_list:
                    self._log(f"✅ 线路提取成功（已排序）: {from_list}")
                    return from_list, url_list

            # ---------- 备用策略（保持原样） ----------
            # JSON 变量
            json_patterns = [
                r'var\s+player_?\w*\s*=\s*({[^;]+})',
                r'var\s+play_?\w*\s*=\s*({[^;]+})',
                r'var\s+data_?\w*\s*=\s*({[^;]+})',
                r'var\s+config\s*=\s*({[^;]+})',
                r'var\s+vod\s*=\s*({[^;]+})',
            ]
            for pat in json_patterns:
                m = re.search(pat, html_txt, re.DOTALL)
                if m:
                    try:
                        data = json.loads(m.group(1))
                        pf = data.get('vod_play_from', '')
                        pu = data.get('vod_play_url', '')
                        if pf and pu:
                            f_list = pf.split('$$$') if '$$$' in pf else [pf]
                            u_list = pu.split('$$$') if '$$$' in pu else [pu]
                            if len(f_list) == len(u_list) and len(f_list) > 0:
                                mapped = [self._get_line_name(f.strip()) for f in f_list]
                                return mapped, u_list
                    except Exception:
                        continue

            # 直接赋值变量
            mf = re.search(r'vod_play_from\s*=\s*["\']([^"\']+)["\']', html_txt)
            mu = re.search(r'vod_play_url\s*=\s*["\']([^"\']+)["\']', html_txt)
            if mf and mu:
                pf = self._unescape(mf.group(1))
                pu = self._unescape(mu.group(1))
                f_list = pf.split('$$$') if '$$$' in pf else [pf]
                u_list = pu.split('$$$') if '$$$' in pu else [pu]
                if len(f_list) == len(u_list) and len(f_list) > 0:
                    mapped = [self._get_line_name(f.strip()) for f in f_list]
                    return mapped, u_list

            # 通用播放列表兜底
            ul_patterns = [
                r'<ul[^>]*class="[^"]*(?:playlist|play_list|play-list)[^"]*"[^>]*>(.*?)</ul>',
                r'<div[^>]*class="[^"]*(?:playlist)[^"]*"[^>]*>.*?<ul>(.*?)</ul>',
            ]
            for ul_pat in ul_patterns:
                ul_match = re.search(ul_pat, html_txt, re.DOTALL)
                if ul_match:
                    links = re.findall(r'<a[^>]*href="([^"]+)"[^>]*>(?:<[^>]+>)*([^<]+)(?:</a>)?', ul_match.group(1), re.DOTALL)
                    if links:
                        eps = []
                        for idx, (url, name) in enumerate(links, 1):
                            ep_name = self._strip_tags(name).strip() or f"第{idx}集"
                            full_url = urljoin(BASE_URL, url)
                            eps.append(f"{ep_name}${full_url}")
                        return ["默认线路"], ["#".join(eps)]

            # 直链
            all_media = _RE_MEDIA.findall(html_txt)
            if all_media:
                unique = list(dict.fromkeys(all_media))
                return ["直链"], [unique[0]]

        except Exception as e:
            self._log(f"_extract_play_from_html 异常: {str(e)}")

        return from_list, url_list

    # ----------------------------------------------------------
    # 详情页
    # ----------------------------------------------------------
    def detailContent(self, ids):
        try:
            if isinstance(ids, str):
                ids = [ids]
            if not ids:
                return {"list": []}
            vod_id = str(ids[0])
            self._log(f"获取详情: {vod_id}")

            cached = self._cache_get('detail', vod_id, CACHE_DETAIL_TTL)
            if cached:
                return {"list": [cached]}

            url = urljoin(BASE_URL, f"/weihu/{vod_id}.html")
            html_txt = self._fetch_html(url)
            if not html_txt:
                return {"list": []}

            if 'con_playlist' not in html_txt and 'play-list' not in html_txt:
                html_txt = self._fetch_html(url)
                if not html_txt or ('con_playlist' not in html_txt and 'play-list' not in html_txt):
                    return {"list": []}

            decoded = html.unescape(html_txt)

            # 标题
            title = ""
            t1 = _RE_H1.search(decoded)
            if t1:
                title = self._strip_tags(t1.group(1))
            if not title:
                t2 = re.search(r'<div[^>]*class="[^"]*vod-title[^"]*"[^>]*>(.*?)</div>', decoded, re.DOTALL)
                if t2:
                    title = self._strip_tags(t2.group(1))
            if not title:
                title = "未知影片"

            # 图片
            pic = ""
            p1 = re.search(r'<img[^>]*class="[^"]*lazyload[^"]*"[^>]*data-original="([^"]+)"[^>]*>', decoded)
            if not p1:
                p1 = re.search(r'<img[^>]*data-original="([^"]+)"[^>]*alt="[^"]*"', decoded)
            if not p1:
                p1 = re.search(r'<img[^>]*class="[^"]*vod-img[^"]*"[^>]*data-original="([^"]+)"', decoded)
            if p1:
                pic = p1.group(1)
            pic = self._clean_url(pic)

            # 简介
            content = ""
            c1 = re.search(r'<p[^>]*class="[^"]*txt-hidden[^"]*"[^>]*>\s*<span\s+class="text-muted">\s*简介[:：]?\s*</span>(.*?)</p>', decoded, re.DOTALL)
            if not c1:
                c1 = re.search(r'<div\s+class="article-content"[^>]*>(.*?)</div>', decoded, re.DOTALL)
            if not c1:
                c1 = re.search(r'<span\s+class="text-muted">\s*简介[:：]?\s*</span>(.*?)(?:</p>|</div>)', decoded, re.DOTALL)
            if c1:
                content = self._strip_tags(c1.group(1))[:500]
            if not content:
                c2 = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', decoded)
                if c2:
                    content = self._strip_tags(c2.group(1))[:500]

            # 演员
            actor = ""
            a1 = re.search(r'<span\s+class="text-muted">\s*主演[:：]?\s*</span>(.*?)(?:</div>|<div)', decoded, re.DOTALL)
            if a1:
                actors = re.findall(r'<a[^>]*>([^<]+)</a>', a1.group(1))
                actor = " ".join(self._strip_tags(a) for a in actors if self._strip_tags(a))
            if not actor:
                a2 = re.search(r'<span[^>]*class="[^"]*actor[^"]*"[^>]*>([^<]+)</span>', decoded)
                if a2:
                    actor = self._strip_tags(a2.group(1))

            # 导演
            director = ""
            d1 = re.search(r'<span\s+class="text-muted">\s*导演[:：]?\s*</span>(.*?)(?:</div>|<div)', decoded, re.DOTALL)
            if d1:
                dirs = re.findall(r'<a[^>]*>([^<]+)</a>', d1.group(1))
                director = " ".join(self._strip_tags(d) for d in dirs if self._strip_tags(d))
            if not director:
                d2 = re.search(r'<span[^>]*class="[^"]*director[^"]*"[^>]*>([^<]+)</span>', decoded)
                if d2:
                    director = self._strip_tags(d2.group(1))

            # 类型、年份、地区
            type_name = ""
            ty1 = re.search(r'<span\s+class="text-muted">\s*类型[:：]?\s*</span>\s*<a[^>]*>([^<]+)</a>', decoded)
            if ty1:
                type_name = self._strip_tags(ty1.group(1))

            year = ""
            y1 = re.search(r'<span\s+class="text-muted">\s*年代[:：]?\s*</span>\s*<a[^>]*>(\d{4})</a>', decoded)
            if not y1:
                y1 = re.search(r'<span\s+class="text-muted">\s*年代[:：]?\s*</span>\s*(\d{4})', decoded)
            if y1:
                year = y1.group(1)

            area = ""
            ar1 = re.search(r'<span\s+class="text-muted">\s*国家地区[:：]?\s*</span>\s*<a[^>]*>([^<]+)</a>', decoded)
            if not ar1:
                ar1 = re.search(r'<span\s+class="text-muted">\s*国家地区[:：]?\s*</span>([^<]+)', decoded)
            if ar1:
                area = self._strip_tags(ar1.group(1))
                if not area:
                    area = ""

            # 提取播放源（已包含排序）
            from_list, url_list = self._extract_play_from_html(html_txt)

            if from_list and url_list:
                play_from = "$$$".join(from_list)
                play_url = "$$$".join(url_list)
                self._log(f"最终线路({len(from_list)}条): {play_from}")
            else:
                play_from = "默认线路"
                play_url = ""
                self._log("⚠️ 未提取到播放源")

            vod = {
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_actor": actor,
                "vod_director": director,
                "vod_content": content,
                "vod_year": year,
                "vod_area": area,
                "type_name": type_name,
                "vod_play_from": play_from,
                "vod_play_url": play_url,
            }

            self._cache_put('detail', vod_id, vod)
            return {"list": [vod]}

        except Exception as e:
            self._log(f"detailContent 异常: {str(e)}")
            return {"list": []}

    # ----------------------------------------------------------
    # 首页
    # ----------------------------------------------------------
    def homeContent(self, filter):
        return {"class": CLASSES, "filters": {}}

    def homeVideoContent(self):
        try:
            cached = self._cache_get('home', 'data', CACHE_HOME_TTL)
            if cached:
                return {"list": cached[:72]}

            html_txt = self._fetch_html(BASE_URL + "/")
            if not html_txt:
                return {"list": []}

            videos = self._parse_video_list_html(html_txt)
            seen = set()
            unique = []
            for v in videos:
                if v['vod_id'] not in seen:
                    seen.add(v['vod_id'])
                    unique.append(v)
            unique = unique[:72]
            self._cache_put('home', 'data', unique)
            return {"list": unique}
        except Exception as e:
            self._log(f"homeVideoContent 异常: {str(e)}")
            return {"list": []}

    # ----------------------------------------------------------
    # 分类
    # ----------------------------------------------------------
    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg or 1)
            if page < 1:
                page = 1

            if page > 1:
                url = f"{BASE_URL}/show/{tid}--------{page}---.html"
            else:
                url = f"{BASE_URL}/show/{tid}-----------.html"

            cache_key = f"{tid}-{page}"
            cached = self._cache_get('category', cache_key, CACHE_CATEGORY_TTL)
            if cached:
                return cached

            html_txt = self._fetch_html(url)
            if not html_txt:
                return {"page": page, "pagecount": 1, "limit": 20, "total": 0, "list": []}

            videos = self._parse_video_list_html(html_txt)

            pagecount = 1
            page_nums = _RE_PAGE_NUM.findall(html_txt)
            if page_nums:
                pagecount = max(int(p) for p in page_nums)
            if pagecount <= 1:
                last_m = _RE_LAST_PAGE.search(html_txt)
                if last_m:
                    pagecount = int(last_m.group(1))
            if pagecount <= 1:
                num_m = _RE_NUM_FRAC.search(html_txt)
                if num_m:
                    pagecount = int(num_m.group(2))
            if pagecount <= 1:
                total_m = _RE_TOTAL_JS.search(html_txt)
                if total_m:
                    total_n = int(total_m.group(1))
                    pagecount = (total_n + len(videos) - 1) // len(videos) if videos else 1
            if pagecount < 1:
                pagecount = 1

            result = {
                "list": videos,
                "page": page,
                "pagecount": pagecount,
                "limit": len(videos) if videos else 20,
                "total": pagecount * (len(videos) if videos else 20),
            }
            self._cache_put('category', cache_key, result)
            return result
        except Exception as e:
            self._log(f"categoryContent 异常: {str(e)}")
            return {"page": 1, "pagecount": 1, "limit": 20, "total": 0, "list": []}

    # ----------------------------------------------------------
    # 搜索
    # ----------------------------------------------------------
    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg or 1)
            if page < 1:
                page = 1
            url = f"{BASE_URL}/index.php?m=vod-search&wd={quote(key)}"
            if page > 1:
                url += f"&page={page}"
            html_txt = self._fetch_html(url)
            if not html_txt:
                return {"list": []}
            videos = self._parse_video_list_html(html_txt)
            return {"list": videos}
        except Exception as e:
            self._log(f"searchContent 异常: {str(e)}")
            return {"list": []}

    # ----------------------------------------------------------
    # 播放
    # ----------------------------------------------------------
    def playerContent(self, flag, id, vipFlags):
        try:
            if not id:
                return {"parse": 0, "playUrl": "", "url": ""}

            play_url = str(id).replace("\\/", "/")
            self._log(f"播放请求: flag='{flag}', id='{play_url[:80]}'")

            if _RE_DIRECT_MEDIA.search(play_url):
                return {
                    "parse": 0,
                    "playUrl": "",
                    "url": play_url,
                    "header": {"User-Agent": UA, "Referer": BASE_URL + "/"}
                }

            if '/bofang/' in play_url or play_url.startswith('/'):
                full_url = urljoin(BASE_URL, play_url)
                self._log(f"解析播放页: {full_url}")
                play_html = self._fetch_html(full_url, timeout=15, referer=BASE_URL + "/")
                if play_html:
                    real_url = self._parse_player_aaaa(play_html)
                    if real_url:
                        self._log(f"player_aaaa解析成功: {real_url[:100]}")
                        return {
                            "parse": 0,
                            "playUrl": "",
                            "url": real_url,
                            "header": {"User-Agent": UA, "Referer": BASE_URL + "/"}
                        }
                    self._log("player_aaaa解析失败，交给壳子嗅探")
                    return {
                        "parse": 1,
                        "playUrl": "",
                        "url": full_url,
                        "header": {"User-Agent": UA, "Referer": BASE_URL + "/"}
                    }

            return {
                "parse": 1,
                "playUrl": "",
                "url": play_url,
                "header": {"User-Agent": UA, "Referer": BASE_URL + "/"}
            }
        except Exception as e:
            self._log(f"playerContent 异常: {str(e)}")
            return {"parse": 1, "playUrl": "", "url": id or ""}

    def _parse_player_aaaa(self, play_html):
        try:
            m = _RE_PLAYER_AAAA.search(play_html) or _RE_PLAYER_ANY.search(play_html)
            if m:
                raw = m.group(1)
                try:
                    data = json.loads(raw)
                    url = data.get('url', '')
                    if url:
                        return url.replace('\\/', '/')
                except Exception:
                    url_m = _RE_JSON_URL_FIELD.search(raw)
                    if url_m:
                        return url_m.group(1).replace('\\/', '/')

            media_m = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', play_html, re.IGNORECASE)
            if not media_m:
                media_m = re.search(r'https?://[^\s"\']+\.mp4[^\s"\']*', play_html, re.IGNORECASE)
            if media_m:
                return media_m.group(0)
        except Exception:
            pass
        return ""

    def localProxy(self, param):
        return [200, "video/MP2T", b"", ""]

    def destroy(self):
        pass

    def close(self):
        self.destroy()