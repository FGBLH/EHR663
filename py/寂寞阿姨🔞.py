# -*- coding: utf-8 -*-
#!/usr/bin/python
import sys, re, json, base64, html, os
from urllib.parse import quote, unquote, urljoin, urlparse

try: from lxml import etree
except ImportError: etree = None

try: import requests
except ImportError: requests = None

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
    if not url: return ""
    if url.startswith("//"): return "https:" + url
    if url.startswith("/"): return urljoin(host, url)
    if url.startswith("http"): return url
    return urljoin(host, "/" + url)

def clean_text(text):
    if not text: return ""
    text = html.unescape(str(text))
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def extract_bg_pic(style_attr, host):
    if not style_attr: return ""
    m = re.search(r'url\(([^)]+)\)', style_attr)
    if m:
        return fix_url(m.group(1).strip().strip('"').strip("'"), host)
    return ""

def extract_play(html_text, host):
    if not html_text: return ""
    m = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html_text)
    if m: return m.group(1)
    m = re.search(r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*)', html_text)
    if m: return m.group(1)
    m = re.search(r'var\s*now\s*=\s*["\']([^"\']+)["\']', html_text)
    if m: return m.group(1)
    m = re.search(r'player_data\s*=\s*(\{.*?\})', html_text, re.DOTALL)
    if m:
        try: return json.loads(m.group(1)).get("url", "")
        except: pass
    m = re.search(r'var\s*player_aaaa\s*=\s*(\{.*?\})', html_text, re.DOTALL)
    if m:
        try:
            d = json.loads(m.group(1))
            return d.get("url", "") or d.get("link", "")
        except: pass
    m = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html_text)
    if m:
        iframe_url = fix_url(m.group(1), host)
        try:
            r = requests.get(iframe_url, headers={
                "User-Agent": "Mozilla/5.0", "Referer": host
            }, timeout=10)
            return extract_play(r.text, host)
        except: pass
    m = re.search(r'videoSources\s*:\s*(\[.*?\])', html_text, re.DOTALL)
    if m:
        try: return json.loads(m.group(1))[0].get("file", "")
        except: pass
    m = re.search(r'var\s*playurl\s*=\s*["\']([^"\']+)["\']', html_text)
    if m: return m.group(1)
    m = re.search(r'player\._src\s*=\s*["\']([^"\']+)["\']', html_text)
    if m: return m.group(1)
    m = re.search(r'cms_player\s*=\s*(\{.*?\})', html_text, re.DOTALL)
    if m:
        try:
            d = json.loads(m.group(1))
            return d.get("url", "") or d.get("src", "")
        except: pass
    m = re.search(r'url\s*[:=]\s*["\']([^"\']+\.m3u8)["\']', html_text)
    if m: return m.group(1)
    m = re.search(r'<source[^>]+src=["\']([^"\']+)["\']', html_text)
    if m: return m.group(1)
    m = re.search(r'(https?://[^\s"\'<>]+\.(?:m3u8|mp4|flv|ts))', html_text)
    return m.group(1) if m else ""


class Spider(BaseSpider):
    def __init__(self):
        super().__init__()
        self.host = "https://www123.lol"
        self.name = "寂寞阿姨_www123_lol"
        self.s = requests.Session() if requests else None
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.host + "/",
            "sec-ch-ua": '"Not_A Brand";v="8","Chromium";v="120","Google Chrome";v="120"',
            "Upgrade-Insecure-Requests": "1",
        }
        self.seen_ids = set()
        if self.s:
            self.s.headers.update(self.headers)
            self.s.verify = False

    def init(self, extend=""):
        if extend and extend.startswith("http"):
            self.host = extend.rstrip("/")
            self.headers["Referer"] = self.host + "/"
            if self.s: self.s.headers.update(self.headers)

    def getName(self):
        return self.name

    def isVideoFormat(self, url):
        return any(x in url for x in [".m3u8", ".mp4", ".flv", ".ts"])

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return [200, "video/MP2T", b"", {}]

    def _fetch(self, url, referer=None):
        if not self.s: return ""
        try:
            h = dict(self.headers)
            if referer: h["Referer"] = referer
            r = self.s.get(url, timeout=15, headers=h)
            r.raise_for_status()
            r.encoding = "utf-8"
            return r.text
        except Exception as e:
            print(f"[{self.name}] 请求失败: {url[:80]}... {e}")
            return ""

    def _parse_video_list(self, doc, html_text, host):
        result = []
        items = []
        items = doc.xpath('//li[contains(@class,"col-md-2")]//a[contains(@class,"video-pic")]')
        if not items:
            items = doc.xpath('//a[contains(@class,"videopic") and contains(@href,"/movie/")]')
        if not items:
            items = doc.xpath('//div[contains(@class,"vodlist")]//a[contains(@href,"/detail/") and .//img]')
        if not items:
            items = doc.xpath('//a[contains(@href,"/detail/") and .//img]')
        if not items:
            items = doc.xpath('//a[contains(@href,"/vod/") and .//img]')
        print(f"[{self.name}] 列表匹配到 {len(items)} 个视频项")
        self.seen_ids.clear()
        for item in items:
            try:
                href = ""
                if item.xpath('./@href'):
                    href = item.xpath('./@href')[0]
                else:
                    href_a = item.xpath('.//a')
                    if href_a:
                        href = href_a[0].xpath('./@href')[0] if href_a[0].xpath('./@href') else ""
                vid = ""
                for pat in [r'/id/(\d+)', r'/(\d+)\.html', r'/detail/(\d+)', r'/play/(\d+)']:
                    m = re.search(pat, href)
                    if m:
                        vid = m.group(1)
                        break
                if not vid: vid = href
                if vid in self.seen_ids: continue
                self.seen_ids.add(vid)
                title = ""
                title_nodes = item.xpath('.//h5[contains(@class,"text-overflow")]/a/text()')
                if not title_nodes: title_nodes = item.xpath('.//h5/a/text()')
                if not title_nodes: title_nodes = item.xpath('./@title')
                if not title_nodes: title_nodes = item.xpath('.//img/@alt')
                title = clean_text(title_nodes[0]) if title_nodes else ""
                pic = ""
                style = item.xpath('./@style')
                if style and 'url(' in style[0]:
                    pic = extract_bg_pic(style[0], host)
                if not pic:
                    pic_nodes = item.xpath('.//img/@data-original') or item.xpath('.//img/@src')
                    pic = fix_url(pic_nodes[0], host) if pic_nodes else ""
                result.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": ""
                })
            except Exception as e:
                print(f"[{self.name}] 单条解析失败: {e}")
                continue
        return result

    def _extract_pagecount(self, html_text):
        for pat in [r'pagecount[=:]\s*(\d+)', r'共\s*(\d+)\s*页',
                     r'class="page-link"[^>]*>(\d+)</a>[^<]*</li>\s*<li[^>]*class="page-item[^"]*next',
                     r'<a[^>]*href="[^"]*page/(\d+)[^"]*"[^>]*>尾页</a>']:
            m = re.search(pat, html_text, re.I)
            if m: return int(m.group(1))
        return 1

    def homeContent(self, filter):
        try:
            classes = [
                {"type_name": "国产视频", "type_id": "1"},
                {"type_name": "中文字幕", "type_id": "2"},
                {"type_name": "国产传媒", "type_id": "3"},
                {"type_name": "日本无码", "type_id": "4"},
                {"type_name": "强奸乱轮", "type_id": "5"},
                {"type_name": "制服诱惑", "type_id": "6"},
                {"type_name": "国产主播", "type_id": "7"},
                {"type_name": "激情动漫", "type_id": "8"},
                {"type_name": "明星换脸", "type_id": "9"},
                {"type_name": "抖阴视频", "type_id": "10"},
                {"type_name": "女优明星", "type_id": "11"},
                {"type_name": "网爆黑料", "type_id": "12"},
                {"type_name": "伦理三级", "type_id": "13"},
                {"type_name": "AV解说", "type_id": "14"},
                {"type_name": "SM调教", "type_id": "15"},
                {"type_name": "萝莉少女", "type_id": "16"},
                {"type_name": "极品媚黑", "type_id": "17"},
                {"type_name": "女同性恋", "type_id": "18"},
                {"type_name": "网红头条", "type_id": "20"},
                {"type_name": "人妖系列", "type_id": "21"},
                {"type_name": "韩国主播", "type_id": "22"},
                {"type_name": "VR视角", "type_id": "23"},
                {"type_name": "欧美无码", "type_id": "24"},
                {"type_name": "日本有码", "type_id": "25"},
            ]
            filters = {}
            for c in classes:
                filters[c["type_id"]] = [
                    {"key": "area", "name": "地区", "value": [
                        {"n":"全部","v":""},{"n":"大陆","v":"大陆"},{"n":"香港","v":"香港"},
                        {"n":"日本","v":"日本"},{"n":"欧美","v":"欧美"},{"n":"韩国","v":"韩国"}
                    ]},
                    {"key": "year", "name": "年份", "value": [
                        {"n":"全部","v":""},{"n":"2026","v":"2026"},{"n":"2025","v":"2025"},
                        {"n":"2024","v":"2024"},{"n":"2023","v":"2023"}
                    ]},
                    {"key": "by", "name": "排序", "value": [
                        {"n":"时间","v":"time"},{"n":"人气","v":"hits"},{"n":"评分","v":"score"}
                    ]},
                ]
            return {"class": classes, "filters": filters}
        except Exception as e:
            print(f"[{self.name}] 首页失败: {e}")
            return {"class": [], "filters": {}}

    def homeVideoContent(self):
        try:
            result = {"list": [], "page": 1, "pagecount": 1, "limit": 24, "total": 0}
            html_text = self._fetch(self.host + "/")
            if not html_text: return result
            doc = etree.HTML(html_text) if etree else None
            if doc is None: return result
            videos = self._parse_video_list(doc, html_text, self.host)
            result["list"] = videos
            pc = self._extract_pagecount(html_text)
            result["pagecount"] = max(pc, 1)
            result["total"] = len(videos)
            print(f"[{self.name}] 首页获取到 {len(videos)} 个最新视频")
            return result
        except Exception as e:
            print(f"[{self.name}] 首页视频失败: {e}")
            return {"list": [], "page": 1, "pagecount": 1, "limit": 24, "total": 0}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            result = {"list": [], "page": int(pg), "pagecount": 1,
                       "limit": 24, "total": 0}
            urls_to_try = []
            if int(pg) <= 1:
                urls_to_try.append(f"{self.host}/index.php/vod/type/id/{tid}.html")
            urls_to_try.append(f"{self.host}/index.php/vod/type/id/{tid}/page/{pg}.html")
            urls_to_try.append(f"{self.host}/index.php/vod/show/id/{tid}/page/{pg}.html")
            html_text = ""
            used_url = ""
            for u in urls_to_try:
                html_text = self._fetch(u)
                if html_text and len(html_text) > 500:
                    used_url = u
                    break
            if not html_text:
                print(f"[{self.name}] 分类{tid}页{pg}所有URL均无响应")
                return result
            print(f"[{self.name}] 分类{tid}页{pg} 使用URL: {used_url}")
            doc = etree.HTML(html_text) if etree else None
            if doc is None: return result
            videos = self._parse_video_list(doc, html_text, self.host)
            result["list"] = videos
            pc = self._extract_pagecount(html_text)
            result["pagecount"] = max(pc, int(pg))
            result["total"] = len(videos)
            print(f"[{self.name}] 分类{tid}获取到 {len(videos)} 个视频, 共{result['pagecount']}页")
            return result
        except Exception as e:
            print(f"[{self.name}] 分类爬取失败: {e}")
            return {"list": [], "page": int(pg), "pagecount": 1,
                    "limit": 24, "total": 0}

    def detailContent(self, ids):
        try:
            vid = ids[0] if isinstance(ids, list) else ids
            result = {"list": []}
            detail_urls = [
                f"{self.host}/index.php/vod/detail/id/{vid}.html",
                f"{self.host}/index.php/vod/play/id/{vid}/sid/1/nid/1.html",
            ]
            html_text = ""
            for u in detail_urls:
                html_text = self._fetch(u)
                if html_text and len(html_text) > 500: break

            if not html_text:
                return result
            doc = etree.HTML(html_text) if etree else None
            title = vid
            if doc is not None:
                t = (doc.xpath('//h1/text()') or doc.xpath('//h2/text()') or
                     doc.xpath('//title/text()') or
                     doc.xpath('//div[contains(@class,"title")]/h1/text()') or
                     doc.xpath('//div[contains(@class,"box-title")]//h3/text()'))
                title = clean_text(t[0]) if t else vid
            pic = ""
            if doc is not None:
                p = (doc.xpath('//img[contains(@class,"poster") or contains(@class,"cover")]/@src') or
                     doc.xpath('//img[contains(@class,"poster")]/@data-original') or
                     doc.xpath('//a[contains(@class,"video-pic")]/@style'))
                if p:
                    if 'url(' in str(p[0]):
                        pic = extract_bg_pic(p[0], self.host)
                    else:
                        pic = fix_url(p[0], self.host)
            sources = []
            play_urls = []
            if doc is not None:
                panels = (doc.xpath('//div[contains(@class,"hy-play-list")]//div[contains(@class,"panel")]') or
                         doc.xpath('//div[contains(@class,"module-tab")]') or
                         doc.xpath('//div[contains(@class,"playlist")]') or
                         doc.xpath('//div[contains(@class,"play_from")]'))
                for panel in panels:
                    try:
                        sname = (panel.xpath('.//a[contains(@class,"option")]/@title') or
                                panel.xpath('.//a[contains(@class,"option")]/text()') or
                                panel.xpath('.//span[contains(@class,"tab")]/text()') or
                                panel.xpath('.//h3/text()') or
                                panel.xpath('.//div[contains(@class,"from")]/text()'))
                        sname = clean_text(sname[0]) if sname else "默认线路"

                        eps = (panel.xpath('.//ul[contains(@class,"playlistlink")]//a') or
                              panel.xpath('.//a[contains(@href,"/play/") or contains(@href,"/vod/play/")]'))
                        ep_list = []
                        for ep in eps:
                            try:
                                ep_title = (ep.xpath('./text()') or ep.xpath('./@title'))
                                ep_title = clean_text(ep_title[0]) if ep_title else "播放"
                                ep_href = ep.xpath('./@href')[0] if ep.xpath('./@href') else ""
                                ep_list.append(f"{ep_title}${fix_url(ep_href, self.host)}")
                            except: continue
                        if ep_list:
                            sources.append(sname)
                            play_urls.append("#".join(ep_list))
                    except: continue
            if not sources:
                sources = ["默认线路"]
                play_urls = [
                    f"播放${self.host}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
                ]
            result["list"].append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_play_from": "$$$".join(sources),
                "vod_play_url": "$$$".join(play_urls)
            })
            print(f"[{self.name}] 详情{vid}: {title[:30]}... 播放源{len(sources)}个")
            return result
        except Exception as e:
            print(f"[{self.name}] 详情解析失败: {e}")
            return {"list": []}

    def playerContent(self, flag, id, vipFlags=None):
        try:
            result = {"parse": 0, "playUrl": "", "url": "", "header": ""}
            if self.isVideoFormat(id):
                result["url"] = id
                result["header"] = json.dumps({
                    "Referer": self.host + "/",
                    "User-Agent": self.headers["User-Agent"]
                })
                return result
            if id.startswith("http"):
                html_text = self._fetch(id, referer=self.host + "/")
                if html_text:
                    play_url = extract_play(html_text, self.host)
                    if play_url and play_url != "eval_encrypted":
                        result["url"] = play_url
                        result["header"] = json.dumps({
                            "Referer": self.host + "/",
                            "Origin": self.host,
                            "User-Agent": self.headers["User-Agent"]
                        })
                        print(f"[{self.name}] 吞天魔罐提取成功: {play_url[:60]}...")
                        return result
            result["url"] = id
            return result
        except Exception as e:
            print(f"[{self.name}] 播放解析失败: {e}")
            return {"parse": 0, "playUrl": "", "url": id, "header": ""}

    def searchContent(self, key, quick, pg="1"):
        try:
            result = {"list": [], "page": int(pg), "pagecount": 1,
                       "limit": 24, "total": 0}
            urls_to_try = [
                f"{self.host}/index.php/vod/search.html?wd={quote(key)}&page={pg}",
                f"{self.host}/index.php/vod/search/page/{pg}/wd/{quote(key)}.html",
            ]
            html_text = ""
            for u in urls_to_try:
                html_text = self._fetch(u)
                if html_text and len(html_text) > 500: break
            if not html_text:
                try:
                    r = self.s.post(
                        f"{self.host}/index.php/vod/search.html",
                        data={"wd": key, "submit": "search"},
                        timeout=15
                    )
                    html_text = r.text if r else ""
                except: pass
            if not html_text: return result
            doc = etree.HTML(html_text) if etree else None
            if doc is None: return result
            videos = self._parse_video_list(doc, html_text, self.host)
            result["list"] = videos
            pc = self._extract_pagecount(html_text)
            result["pagecount"] = max(pc, 1)
            print(f"[{self.name}] 搜索'{key}'找到 {len(videos)} 个结果")
            return result
        except Exception as e:
            print(f"[{self.name}] 搜索失败: {e}")
            return {"list": [], "page": int(pg), "pagecount": 1,
                    "limit": 24, "total": 0}