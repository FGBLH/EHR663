# -*- coding: utf-8 -*-
# 遮天法 · 极道帝兵自动生成 · MacCMS v8/v10 适配（详情页+播放修复版）
import sys, re, json, html, requests, base64, time, random
from urllib.parse import quote, unquote, urljoin
try:
    from lxml import etree
except ImportError:
    etree = None
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def init(self, extend=""): pass
        def homeContent(self, filter): pass
        def homeVideoContent(self): pass
        def categoryContent(self, tid, pg, filter, extend): pass
        def detailContent(self, ids): pass
        def playerContent(self, flag, id, vipFlags=None): pass
        def searchContent(self, key, quick, pg='1'): pass
        def isVideoFormat(self, url): pass
        def manualVideoCheck(self): pass
        def localProxy(self, param): pass

def fix_url(url, host):
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return urljoin(host, url)
    if url.startswith("http"):
        return url
    return urljoin(host, "/" + url)

def clean_text(text):
    if not text:
        return ""
    return html.unescape(re.sub(r"<[^>]+>", "", str(text))).strip()

def _try_base64(url):
    if not url:
        return ""
    try:
        decoded = base64.b64decode(url).decode("utf-8")
        return decoded
    except:
        return url

def _decode_player_url(url, encrypt=0):
    if not url:
        return ""
    if url.startswith("http"):
        return url
    if encrypt == 1 or "%" in url:
        try:
            decoded = unquote(url)
            if decoded.startswith("http"):
                return decoded
        except:
            pass
    decoded = _try_base64(url)
    if decoded.startswith("http"):
        return decoded
    try:
        decoded2 = unquote(decoded)
        if decoded2.startswith("http"):
            return decoded2
    except:
        pass
    return url

def _extract_balanced_json(html_text, var_name):
    """从 HTML 中提取指定变量的 JSON 对象，支持嵌套大括号"""
    pattern = rf'var\s+{re.escape(var_name)}\s*=\s*'
    m = re.search(pattern, html_text)
    if not m:
        pattern = rf'{re.escape(var_name)}\s*=\s*'
        m = re.search(pattern, html_text)
    if not m:
        return None

    start = m.end()
    while start < len(html_text) and html_text[start] in ' \t\n\r':
        start += 1

    if start >= len(html_text) or html_text[start] != '{':
        return None

    depth = 0
    in_string = False
    string_char = None
    escape = False

    for i in range(start, len(html_text)):
        ch = html_text[i]
        if escape:
            escape = False
            continue
        if ch == '\\\\':
            escape = True
            continue
        if in_string:
            if ch == string_char:
                in_string = False
                string_char = None
            continue
        if ch in '"\'':
            in_string = True
            string_char = ch
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return html_text[start:i+1]
    return None

def extract_play(html_text, host):
    if not html_text:
        return ""

    # 优先：player_aaaa / player_data
    for var_name in ["player_aaaa", "player_data"]:
        json_str = _extract_balanced_json(html_text, var_name)
        if json_str:
            try:
                pd = json.loads(json_str.replace("'", '"'))
                url = pd.get("url", "")
                encrypt = pd.get("encrypt", 0)
                decoded = _decode_player_url(url, encrypt)
                if decoded.startswith("http"):
                    return decoded
            except:
                pass

    # 直接视频直链
    for pat in [r"(https?://[^\s\"\'<>]+\.m3u8[^\s\"\'<>]*)",
                r"(https?://[^\s\"\'<>]+\.mp4[^\s\"\'<>]*)",
                r"(https?://[^\s\"\'<>]+\.flv[^\s\"\'<>]*)",
                r"(https?://[^\s\"\'<>]+\.ts[^\s\"\'<>]*)",]:
        m = re.search(pat, html_text)
        if m:
            return m.group(1)

    # 变量 now/main/...
    for var_name in ["now", "main", "cms_player", "video_url", "play_url", "url"]:
        m = re.search(rf'var\s+{var_name}\s*=\s*["\']([^"\']+)["\']', html_text)
        if m:
            url = m.group(1).strip()
            decoded = _decode_player_url(url, 0)
            if decoded.startswith("http"):
                return decoded
            if url and url not in ["", "#", "javascript:;"]:
                fixed = fix_url(url, host)
                if fixed.startswith("http"):
                    return fixed

    # MacPlayer
    m = re.search(r'var\s+MacPlayer\s*=\s*(\{.*?\});', html_text, re.DOTALL)
    if m:
        try:
            raw = m.group(1).replace("'", '"')
            mp = json.loads(raw)
            url = mp.get("url", "")
            decoded = _decode_player_url(url, 0)
            if decoded.startswith("http"):
                return decoded
            if url and url not in ["", "#", "javascript:;"]:
                fixed = fix_url(url, host)
                if fixed.startswith("http"):
                    return fixed
        except:
            pass

    # player 配置对象
    m = re.search(r'player\s*=\s*\{[^}]*url\s*:\s*["\']([^"\']+)["\']', html_text)
    if m:
        url = m.group(1).strip()
        decoded = _decode_player_url(url, 0)
        if decoded.startswith("http"):
            return decoded

    # iframe
    m = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html_text)
    if m:
        iframe_src = m.group(1)
        iframe_src = fix_url(iframe_src, host)
        try:
            sub_html = requests.get(iframe_src, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": host + "/"
            }, timeout=10).text
            sub_result = extract_play(sub_html, host)
            if sub_result:
                return sub_result
        except:
            pass

    # eval
    m = re.search(r'eval\s*\((.*?)\)', html_text, re.DOTALL)
    if m:
        return "eval_encrypted"

    # videoSources
    m = re.search(r'videoSources\s*:\s*(\[.*?\])', html_text, re.DOTALL)
    if m:
        try:
            arr = json.loads(m.group(1))
            if arr and isinstance(arr, list):
                return arr[0].get("file", "")
        except:
            pass

    # wvPlayer / DPlayer / CKPlayer
    m = re.search(r'(?:wvPlayer|player|ckplayer)\.play\s*\(\s*["\']([^"\']+)["\']', html_text)
    if m:
        return m.group(1)

    # location.href
    m = re.search(r'location\.href\s*=\s*["\']([^"\']+)["\']', html_text)
    if m:
        return m.group(1)

    # url/src: "xxx.m3u8/mp4/flv"
    m = re.search(r'(?:url|src)\s*:\s*["\']([^"\']+\.(?:m3u8|mp4|flv))["\']', html_text)
    if m:
        return m.group(1)

    # <video>/<source> src
    m = re.search(r'<(?:video|source)[^>]+src=["\']([^"\']+)["\']', html_text)
    if m:
        return m.group(1)

    # data-url / data-src
    m = re.search(r'data-(?:url|src)=["\']([^"\']+)["\']', html_text)
    if m:
        return m.group(1)

    # 通用 base64 长字符串兜底
    m = re.search(r'(?:data|url|src)\s*=\s*["\']([A-Za-z0-9+/=]{30,})["\']', html_text)
    if m:
        decoded = _try_base64(m.group(1))
        if decoded.startswith("http"):
            return decoded

    return ""


def extract_title_from_page(html_text, vid=""):
    if not html_text:
        return ""
    doc = etree.HTML(html_text) if etree else None
    if doc is None:
        return ""

    # 方式1: 标准详情页标题选择器
    selectors = [
        '//div[contains(@class,"stui-content__detail")]//h1[contains(@class,"title")]/text()',
        '//div[contains(@class,"stui-content__detail")]//h1/text()',
        '//div[contains(@class,"stui-content__detail")]//h2/text()',
        '//div[contains(@class,"vod-detail")]//h1/text()',
        '//div[contains(@class,"vod-detail")]//h2/text()',
        '//div[contains(@class,"detail")]//h1/text()',
        '//div[contains(@class,"detail")]//h2/text()',
        '//div[contains(@class,"title")]/h1/text()',
        '//div[contains(@class,"title")]/h2/text()',
        '//h1[contains(@class,"title")]/text()',
        '//h2[contains(@class,"title")]/text()',
        '//h1/text()',
        '//h2/text()',
    ]
    for sel in selectors:
        t = doc.xpath(sel)
        if t:
            title = clean_text(t[0])
            if title and title != vid and len(title) > 3:
                return title

    # 方式2: 从 <title> 标签提取（兜底）
    title_elem = doc.xpath('//title/text()')
    if title_elem:
        raw_title = clean_text(title_elem[0])
        if "_" in raw_title:
            title = raw_title.split("_")[0].strip()
        elif " - " in raw_title:
            title = raw_title.split(" - ")[0].strip()
        elif "-" in raw_title:
            title = raw_title.split("-")[0].strip()
        else:
            title = raw_title
        if title and title != vid and len(title) > 3:
            return title

    return ""


def extract_desc_from_page(html_text):
    """从页面HTML中提取简介"""
    if not html_text:
        return ""
    doc = etree.HTML(html_text) if etree else None
    if doc is None:
        return ""

    # 1. 标准简介选择器
    selectors = [
        '//div[contains(@class,"stui-content__desc")]//text()',
        '//div[contains(@class,"vod-content")]//text()',
        '//div[contains(@class,"detail-content")]//text()',
        '//div[contains(@class,"desc")]//text()',
        '//div[contains(@class,"intro")]//text()',
        '//div[contains(@class,"summary")]//text()',
        '//p[contains(@class,"desc")]//text()',
        '//span[contains(@class,"desc")]//text()',
    ]
    for sel in selectors:
        texts = doc.xpath(sel)
        if texts:
            desc = "".join(clean_text(t) for t in texts if clean_text(t))
            if desc and len(desc) > 5:
                return desc

    # 2. 正则兜底：匹配常见简介div
    m = re.search(r'<div[^>]*class=["\'][^"\']*(?:desc|content|intro|summary)[^"\']*["\'][^>]*>(.*?)</div>', html_text, re.DOTALL | re.IGNORECASE)
    if m:
        desc = clean_text(m.group(1))
        if desc and len(desc) > 5:
            return desc

    return ""


class Spider(BaseSpider):
    def __init__(self):
        super().__init__()
        self.host = "https://fzms12.cc"
        self.name = "房中秘术_MacCMS_v8"
        self.s = requests.Session()

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": self.host + "/",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "sec-ch-ua": "\"Not_A Brand\";v=\"8\", \"Chromium\";v=\"120\", \"Google Chrome\";v=\"120\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
            "Cache-Control": "max-age=0",
        }
        self.s.headers.update(self.headers)
        try:
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            retry_strategy = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
            )
            adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=10)
            self.s.mount("https://", adapter)
            self.s.mount("http://", adapter)
        except:
            pass

        self.seen_ids = set()
        self._title_cache = {}
        self._desc_cache = {}
        self._filters_cache = None
        self._filter_extracted = False

    def init(self, extend=""):
        if extend and extend.startswith("http"):
            self.host = extend.rstrip("/")
            self.headers["Referer"] = self.host + "/"
            self.s.headers.update(self.headers)

    def getName(self):
        return self.name

    def isVideoFormat(self, url):
        return any(x in url for x in [".m3u8", ".mp4", ".flv", ".ts"])

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return [200, "video/MP2T", b"", {}]

    def _fetch(self, url, method="GET", data=None, retries=3):
        for attempt in range(retries):
            try:
                if attempt > 0:
                    time.sleep(random.uniform(0.5, 1.5))
                self.s.headers["Referer"] = self.host + "/"
                if method.upper() == "POST" and data is not None:
                    r = self.s.post(url, data=data, timeout=15)
                else:
                    r = self.s.get(url, timeout=15)
                r.raise_for_status()
                return r.text
            except requests.exceptions.ConnectionError as e:
                print(f"[{self.name}] 连接被重置 ({attempt+1}/{retries}): {url}")
                if attempt < retries - 1:
                    self.s = requests.Session()
                    self.s.headers.update(self.headers)
                    try:
                        from requests.adapters import HTTPAdapter
                        from urllib3.util.retry import Retry
                        retry_strategy = Retry(total=2, backoff_factor=1)
                        adapter = HTTPAdapter(max_retries=retry_strategy)
                        self.s.mount("https://", adapter)
                        self.s.mount("http://", adapter)
                    except:
                        pass
                    time.sleep(random.uniform(1, 2))
                else:
                    return ""
            except requests.exceptions.Timeout:
                if attempt < retries - 1:
                    time.sleep(random.uniform(1, 2))
                else:
                    return ""
            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(random.uniform(0.5, 1))
                else:
                    return ""
        return ""

    def homeContent(self, filter):
        try:
            html_text = self._fetch(self.host + "/")
            doc = etree.HTML(html_text) if etree else None
            classes = []
            if doc is not None:
                items = doc.xpath('//dl[contains(@class,"first")]//dd/a')
                for a in items:
                    href = a.xpath('./@href')[0] if a.xpath('./@href') else ""
                    name = clean_text(a.xpath('./text()')[0]) if a.xpath('./text()') else ""
                    if href and name and href.startswith("/vodtype/"):
                        tid = re.search(r'/vodtype/(\d+)\.html', href)
                        if tid:
                            classes.append({"type_id": tid.group(1), "type_name": name})
            if not classes:
                classes = [
                    {"type_id": "20", "type_name": "网曝黑料"},
                    {"type_id": "181", "type_name": "黄色仓库"},
                    {"type_id": "1", "type_name": "国产传媒"},
                    {"type_id": "2", "type_name": "国产剧情"},
                    {"type_id": "3", "type_name": "必射精选"},
                    {"type_id": "4", "type_name": "精品资源"}
                ]
            # ========== 子分类筛选修复 ==========
            filters = self._extract_filters_from_page(html_text)
            if not filters:
                filters = self._get_default_filters()
            self._filters_cache = filters
            self._filter_extracted = True
            result_filters = {}
            for c in classes:
                result_filters[c["type_id"]] = list(filters.values())
            return {"class": classes, "filters": result_filters}
        except Exception as e:
            print(f"[{self.name}] homeContent 失败: {e}")
            return {"class": [], "filters": {}}

    def homeVideoContent(self):
        return self.categoryContent("20", "1", False, {})

    def categoryContent(self, tid, pg, filter, extend):
        try:
            result = {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}
            # ========== 子分类筛选修复 ==========
            extend = extend or {}
            has_filter = bool(extend)
            html_text = ""
            if has_filter:
                show_url = self._build_show_url(tid, pg, extend)
                html_text = self._fetch(show_url)
                if not html_text or "thumbnail" not in html_text:
                    show_url_alt = self._build_show_url_alt(tid, pg, extend)
                    html_text = self._fetch(show_url_alt)
                if not html_text or "thumbnail" not in html_text:
                    url = f"{self.host}/vodtype/{tid}-{pg}.html"
                    html_text = self._fetch(url)
            else:
                url = f"{self.host}/vodtype/{tid}-{pg}.html"
                html_text = self._fetch(url)
            if not html_text:
                return result
            doc = etree.HTML(html_text) if etree else None
            if doc is None:
                return result

            items = doc.xpath('//ul[contains(@class,"thumbnail-group")]/li')
            if not items:
                items = doc.xpath('//div[contains(@class,"mhlleset-main")]//ul/li')
            if not items:
                items = doc.xpath('//a[contains(@class,"thumbnail") and contains(@href,"/voddetail/")]/..')

            self.seen_ids.clear()
            for li in items:
                try:
                    a = li.xpath('.//a[contains(@class,"thumbnail")]')[0] if li.xpath('.//a[contains(@class,"thumbnail")]') else None
                    if not a:
                        continue
                    href = a.xpath('./@href')[0] if a.xpath('./@href') else ""
                    vid = re.search(r'/voddetail/(\d+)\.html', href)
                    if not vid:
                        continue
                    vid = vid.group(1)
                    if vid in self.seen_ids:
                        continue
                    self.seen_ids.add(vid)

                    title_elem = li.xpath('.//h5/a/text()') or li.xpath('.//div[contains(@class,"video-info")]/h5/a/text()')
                    title = clean_text(title_elem[0]) if title_elem else ""
                    if title:
                        self._title_cache[vid] = title

                    # 优先 data-original，其次 src，最后 data-src
                    img = a.xpath('.//img/@data-original') or a.xpath('.//img/@src') or a.xpath('.//img/@data-src')
                    pic = fix_url(img[0], self.host) if img else ""

                    result["list"].append({
                        "vod_id": vid,
                        "vod_name": title,
                        "vod_pic": pic,
                        "vod_remarks": ""
                    })
                except Exception as e:
                    print(f"[{self.name}] category 单条解析失败: {e}")
                    continue

            pagecount = 1
            m = re.search(r'pagecount[=:]\s*(\d+)', html_text)
            if m:
                pagecount = int(m.group(1))
            m = re.search(r'共\s*(\d+)\s*页', html_text)
            if m:
                pagecount = max(pagecount, int(m.group(1)))
            pages = re.findall(r'/vodtype/\d+-(\d+)\.html', html_text)
            if pages:
                pagecount = max(pagecount, max(int(p) for p in pages))
            has_next = bool(re.search(r'下一页|下一頁|next|&gt;&gt;', html_text))
            if has_next and pagecount <= int(pg):
                pagecount = int(pg) + 1

            result["pagecount"] = pagecount
            return result
        except Exception as e:
            print(f"[{self.name}] categoryContent 失败: {e}")
            return {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}

    def detailContent(self, ids):
        try:
            vid = ids[0] if isinstance(ids, list) else ids
            result = {"list": []}
            url = f"{self.host}/voddetail/{vid}.html"
            html_text = self._fetch(url)
            doc = etree.HTML(html_text) if etree else None

            # ========== 标题 ==========
            title = ""
            if html_text:
                title = extract_title_from_page(html_text, vid)
            if not title or title == vid:
                title = self._title_cache.get(vid, vid)

            # ========== 图片 ==========
            pic = ""
            if doc is not None:
                # 适配 fzms12.cc 的 detail-poster 结构
                img_src = doc.xpath('//div[contains(@class,"detail-poster")]//img/@src')
                if img_src:
                    pic = fix_url(img_src[0], self.host)
                if not pic:
                    pic_selectors = [
                        '//div[contains(@class,"stui-content__thumb")]//img/@data-original',
                        '//div[contains(@class,"stui-content__thumb")]//img/@src',
                        '//img[contains(@class,"poster")]/@src',
                        '//img[contains(@class,"poster")]/@data-original',
                        '//img[contains(@class,"cover")]/@src',
                        '//img[contains(@class,"cover")]/@data-original',
                        '//img[contains(@class,"pic")]/@src',
                        '//div[contains(@class,"vod-detail")]//img/@src',
                        '//div[contains(@class,"detail")]//img/@src',
                        '//div[contains(@class,"thumb")]//img/@src',
                    ]
                    for sel in pic_selectors:
                        p = doc.xpath(sel)
                        if p:
                            pic = fix_url(p[0], self.host)
                            break

            # ========== 简介/说明文字 ==========
            desc = ""
            if doc is not None:
                # 适配 fzms12.cc 的 detail-actor 结构
                actor_lis = doc.xpath('//ul[contains(@class,"detail-actor")]//li')
                desc_lines = []
                for li in actor_lis:
                    text = "".join(li.xpath('.//text()')).strip()
                    text = clean_text(text)
                    if text:
                        desc_lines.append(text)
                if desc_lines:
                    desc = "\\n".join(desc_lines)

            # 如果上面的结构没拿到，再用通用方法
            if not desc and html_text:
                desc = extract_desc_from_page(html_text)

            if desc:
                self._desc_cache[vid] = desc
            else:
                desc = self._desc_cache.get(vid, "")

            # ========== 播放源解析 ==========
            sources = []
            play_urls = []
            if doc is not None:
                # 适配 fzms12.cc 的 detail-source 结构
                source_tabs = doc.xpath('//div[contains(@class,"detail-source")]//ul[contains(@class,"detail-tab")]//li')
                if source_tabs:
                    for i, tab in enumerate(source_tabs):
                        sname = clean_text("".join(tab.xpath('.//text()')))
                        if not sname:
                            sname = f"源{i+1}"

                        # 找对应的播放列表
                        # 有些模板是 ul.detail-play-list，有些是 div.tab-pane
                        play_list = doc.xpath(f'//div[contains(@class,"detail-source")]//ul[contains(@class,"detail-play-list")][{i+1}]//a')
                        if not play_list:
                            # 试试找所有在 detail-content 里的 a
                            play_list = doc.xpath('//div[contains(@class,"detail-content")]//ul[contains(@class,"detail-play-list")]//a')
                        if not play_list:
                            play_list = doc.xpath('//div[contains(@class,"detail-source")]//div[contains(@class,"tab-pane")]//a')

                        ep_list = []
                        for ep in play_list:
                            ep_title = ep.xpath('./text()')[0] if ep.xpath('./text()') else "播放"
                            ep_href = ep.xpath('./@href')[0] if ep.xpath('./@href') else ""
                            if ep_href:
                                full_href = fix_url(ep_href, self.host)
                                ep_list.append(f"{clean_text(ep_title)}${full_href}")
                        if ep_list:
                            sources.append(sname)
                            play_urls.append("#".join(ep_list))

                # 如果上面的结构没拿到，再用通用 panel 方法兜底
                if not play_urls:
                    panel_selectors = [
                        '//div[contains(@class,"hy-play-list")]//div[contains(@class,"panel")]',
                        '//div[contains(@class,"module-tab")]',
                        '//div[contains(@class,"playlist")]',
                        '//div[contains(@class,"play-list")]',
                        '//div[contains(@class,"tab-content")]',
                        '//div[contains(@class,"stui-play__list")]',
                        '//div[contains(@class,"play_source")]',
                        '//div[contains(@class,"vod-play-list")]',
                        '//div[contains(@class,"play-box")]',
                        '//div[contains(@class,"stui-content__playlist")]',
                    ]
                    panels = []
                    for sel in panel_selectors:
                        panels = doc.xpath(sel)
                        if panels:
                            break

                    for panel in panels:
                        try:
                            sname_selectors = [
                                './/a[contains(@class,"option")]/@title',
                                './/a[contains(@class,"option")]/text()',
                                './/span[contains(@class,"tab")]/text()',
                                './/h3/text()',
                                './/div[contains(@class,"title")]/text()',
                                './/li[contains(@class,"active")]//text()',
                                './/a[contains(@class,"active")]//text()',
                            ]
                            sname = "默认"
                            for sel in sname_selectors:
                                sn = panel.xpath(sel)
                                if sn:
                                    sname = clean_text(sn[0])
                                    if sname:
                                        break

                            ep_selectors = [
                                './/ul[contains(@class,"playlistlink")]//a',
                                './/a[contains(@href,"/play/") or contains(@href,"/vodplay/") or contains(@href,"/vod/play/")]',
                                './/div[contains(@class,"playlist")]//a',
                                './/a[contains(@class,"btn")]',
                                './/a[contains(@class,"episode")]',
                                './/li/a',
                                './/ul[contains(@class,"stui-content__playlist")]//a',
                            ]
                            eps = []
                            for sel in ep_selectors:
                                eps = panel.xpath(sel)
                                if eps:
                                    break

                            ep_list = []
                            for ep in eps:
                                ep_title = ep.xpath('./text()')[0] if ep.xpath('./text()') else "播放"
                                ep_href = ep.xpath('./@href')[0] if ep.xpath('./@href') else ""
                                if ep_href:
                                    full_href = fix_url(ep_href, self.host)
                                    ep_list.append(f"{clean_text(ep_title)}${full_href}")
                            if ep_list:
                                sources.append(sname)
                                play_urls.append("#".join(ep_list))
                        except Exception as e:
                            print(f"[{self.name}] 播放源解析失败: {e}")
                            continue

            # 全局正则兜底
            if not play_urls and html_text:
                all_links = re.findall(r'href=["\'](/(?:vodplay|play|vod/play)/[^"\']+)["\']', html_text)
                if all_links:
                    ep_list = []
                    for i, link in enumerate(sorted(set(all_links))):
                        full_link = fix_url(link, self.host)
                        ep_list.append(f"第{i+1}集${full_link}")
                    if ep_list:
                        sources.append("默认")
                        play_urls.append("#".join(ep_list))

            # ========== 组装返回数据 ==========
            item = {
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_play_from": "$$$".join(sources) if sources else "默认",
                "vod_play_url": "$$$".join(play_urls) if play_urls else f"播放${vid}",
            }
            if desc:
                item["vod_content"] = desc
                item["vod_blurb"] = desc[:100] + "..." if len(desc) > 100 else desc

            result["list"].append(item)
            return result
        except Exception as e:
            print(f"[{self.name}] detailContent 失败: {e}")
            return {"list": []}

    def playerContent(self, flag, id, vipFlags=None):
        try:
            result = {"parse": 0, "playUrl": "", "url": "", "header": ""}

            play_page_url = id
            if not play_page_url.startswith("http"):
                play_page_url = fix_url(play_page_url, self.host)

            if self.isVideoFormat(play_page_url):
                result["url"] = play_page_url
                result["header"] = json.dumps({"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]})
                return result

            html_text = self._fetch(play_page_url) if play_page_url else ""
            if html_text:
                play_url = extract_play(html_text, self.host)
                if play_url and play_url != "eval_encrypted":
                    result["url"] = play_url
                    result["header"] = json.dumps({"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]})
                    return result
                elif play_url == "eval_encrypted":
                    result["parse"] = 1
                    result["url"] = play_page_url
                    return result

            result["url"] = play_page_url
            return result
        except Exception as e:
            print(f"[{self.name}] playerContent 失败: {e}")
            return {"parse": 0, "playUrl": "", "url": id, "header": ""}

    def searchContent(self, key, quick, pg="1"):
        try:
            result = {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}
            url = f"{self.host}/vodsearch/-------------.html"
            data = {"wd": key}
            r_text = self._fetch(url, method="POST", data=data)
            if not r_text:
                return result
            doc = etree.HTML(r_text) if etree else None
            if doc is None:
                return result
            items = doc.xpath('//ul[contains(@class,"thumbnail-group")]/li')
            if not items:
                items = doc.xpath('//a[contains(@class,"thumbnail") and contains(@href,"/voddetail/")]/..')
            self.seen_ids.clear()
            for li in items:
                try:
                    a = li.xpath('.//a[contains(@class,"thumbnail")]')[0] if li.xpath('.//a[contains(@class,"thumbnail")]') else None
                    if not a:
                        continue
                    href = a.xpath('./@href')[0] if a.xpath('./@href') else ""
                    vid = re.search(r'/voddetail/(\d+)\.html', href)
                    if not vid:
                        continue
                    vid = vid.group(1)
                    if vid in self.seen_ids:
                        continue
                    self.seen_ids.add(vid)
                    title = li.xpath('.//h5/a/text()') or li.xpath('.//div[contains(@class,"video-info")]/h5/a/text()')
                    title = clean_text(title[0]) if title else ""
                    if title:
                        self._title_cache[vid] = title
                    # 优先 data-original
                    img = a.xpath('.//img/@data-original') or a.xpath('.//img/@src') or a.xpath('.//img/@data-src')
                    pic = fix_url(img[0], self.host) if img else ""
                    result["list"].append({"vod_id": vid, "vod_name": title, "vod_pic": pic})
                except Exception as e:
                    continue

            pages = re.findall(r'/vodsearch/[^"\']*?-(\d+)\.html', r_text)
            if pages:
                result["pagecount"] = max(int(p) for p in pages)
            else:
                has_next = bool(re.search(r'下一页|下一頁|next|&gt;&gt;', r_text))
                if has_next:
                    result["pagecount"] = int(pg) + 1

            return result
        except Exception as e:
            print(f"[{self.name}] searchContent 失败: {e}")
            return {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}

    # ==================== 子分类筛选相关方法 ====================

    def _build_show_url(self, tid, pg, extend):
        """MacCMS v8/v10 伪静态筛选URL: /vodshow/ID-地区-年份-语言-首字母-排序-方式-页码.html"""
        area = extend.get("area", "")
        year = extend.get("year", "")
        lang = extend.get("lang", "")
        letter = extend.get("letter", "")
        by = extend.get("by", "")
        order = extend.get("order", "")
        parts = [str(tid), area, year, lang, letter, by, order, str(pg)]
        return f"{self.host}/vodshow/{ '-'.join(parts) }.html"

    def _build_show_url_alt(self, tid, pg, extend):
        """备选格式: /vodshow/id/area/year/lang/letter/by/order/page.html"""
        area = extend.get("area", "")
        year = extend.get("year", "")
        lang = extend.get("lang", "")
        letter = extend.get("letter", "")
        by = extend.get("by", "")
        order = extend.get("order", "")
        parts = [str(tid), area, year, lang, letter, by, order, str(pg)]
        return f"{self.host}/vodshow/{ '/'.join(parts) }.html"

    def _extract_filters_from_page(self, html_text):
        """从分类页HTML自动提取筛选条件"""
        filters = {}
        if not html_text:
            return filters
        doc = etree.HTML(html_text) if etree else None
        if doc is None:
            return filters

        # 地区
        area_vals = [{"n": "全部", "v": ""}]
        seen = set()
        for a in doc.xpath('//a[contains(@href,"area") or contains(@href,"vodshow")]'):
            href = a.xpath('./@href')[0] if a.xpath('./@href') else ""
            name = clean_text(a.xpath('./text()')[0]) if a.xpath('./text()') else ""
            if name and name not in seen and name not in ["全部", "全部地区"]:
                seen.add(name)
                m = re.search(r'/vodshow/\\d+-([^-./]+)', href)
                val = m.group(1) if m else name
                area_vals.append({"n": name, "v": val})
        if len(area_vals) <= 1:
            area_vals = [
                {"n": "全部", "v": ""}, {"n": "大陆", "v": "大陆"}, {"n": "港台", "v": "港台"},
                {"n": "欧美", "v": "欧美"}, {"n": "日本", "v": "日本"}, {"n": "韩国", "v": "韩国"},
                {"n": "泰国", "v": "泰国"}, {"n": "其他", "v": "其他"},
            ]

        # 年份
        year_vals = [{"n": "全部", "v": ""}]
        seen = set()
        for a in doc.xpath('//a[contains(@href,"year")]'):
            name = clean_text(a.xpath('./text()')[0]) if a.xpath('./text()') else ""
            if name and re.match(r'^\\d{4}$', name) and name not in seen:
                seen.add(name)
                year_vals.append({"n": name, "v": name})
        if len(year_vals) <= 1:
            cy = time.localtime().tm_year
            year_vals = [{"n": "全部", "v": ""}]
            for y in range(cy, cy - 20, -1):
                year_vals.append({"n": str(y), "v": str(y)})

        filters = {
            "area": {"name": "地区", "key": "area", "value": area_vals},
            "year": {"name": "年份", "key": "year", "value": year_vals},
            "by": {"name": "排序", "key": "by", "value": [
                {"n": "时间", "v": "time"}, {"n": "人气", "v": "hits"}, {"n": "评分", "v": "score"}
            ]},
            "lang": {"name": "语言", "key": "lang", "value": [
                {"n": "全部", "v": ""}, {"n": "国语", "v": "国语"}, {"n": "粤语", "v": "粤语"},
                {"n": "英语", "v": "英语"}, {"n": "日语", "v": "日语"}, {"n": "韩语", "v": "韩语"}
            ]},
        }
        return filters

    def _get_default_filters(self):
        """通用默认筛选条件"""
        cy = time.localtime().tm_year
        year_vals = [{"n": "全部", "v": ""}]
        for y in range(cy, cy - 20, -1):
            year_vals.append({"n": str(y), "v": str(y)})
        return {
            "area": {"name": "地区", "key": "area", "value": [
                {"n": "全部", "v": ""}, {"n": "大陆", "v": "大陆"}, {"n": "港台", "v": "港台"},
                {"n": "欧美", "v": "欧美"}, {"n": "日本", "v": "日本"}, {"n": "韩国", "v": "韩国"},
                {"n": "泰国", "v": "泰国"}, {"n": "其他", "v": "其他"}
            ]},
            "year": {"name": "年份", "key": "year", "value": year_vals},
            "by": {"name": "排序", "key": "by", "value": [
                {"n": "时间", "v": "time"}, {"n": "人气", "v": "hits"}, {"n": "评分", "v": "score"}
            ]},
            "lang": {"name": "语言", "key": "lang", "value": [
                {"n": "全部", "v": ""}, {"n": "国语", "v": "国语"}, {"n": "粤语", "v": "粤语"},
                {"n": "英语", "v": "英语"}, {"n": "日语", "v": "日语"}, {"n": "韩语", "v": "韩语"}
            ]},
        }
