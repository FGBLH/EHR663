# -*- coding: utf-8 -*-
#!/usr/bin/python

import sys, re, json, base64, html, os, threading, time, hashlib
from urllib.parse import quote, unquote, urljoin, urlparse

try:
    from lxml import etree
except ImportError:
    etree = None

try:
    import requests
    import urllib3
    urllib3.disable_warnings()
except ImportError:
    requests = None

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
    url = str(url).strip()
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
    text = str(text)
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()



DECODE_MAP = {
    'e': 'P', 'w': 'D', 'T': 'y', '+': 'J', 'l': '!', 't': 'L',
    'E': 'E', '@': '2', 'd': 'a', 'b': '%', 'q': 'l', 'X': 'v',
    '~': 'R', '5': 'r', '&': 'X', 'C': 'j', ']': 'F', 'a': ')',
    '^': 'm', ',': '~', '}': '1', 'x': 'C', 'c': '(', 'G': '@',
    'h': 'h', '.': '*', 'L': 's', '=': ',', 'p': 'g', 'I': 'Q',
    '1': '7', '_': 'u', 'K': '6', 'F': 't', '2': 'n', '8': '=',
    'k': 'G', 'Z': ']', ')': 'b', 'P': '}', 'B': 'U', 'S': 'k',
    '6': 'i', 'g': ':', 'N': 'N', 'i': 'S', '%': '+', '-': 'Y',
    '?': '|', '4': 'z', '*': '-', '3': '^', '[': '{', '(': 'c',
    'u': 'B', 'y': 'M', 'U': 'Z', 'H': '[', 'z': 'K', '9': 'H',
    '7': 'f', 'R': 'x', 'v': '&', '!': ';', 'M': '_', 'Q': '9',
    'Y': 'e', 'o': '4', 'r': 'A', 'm': '.', 'O': 'o', 'V': 'W',
    'J': 'p', 'f': 'd', ':': 'q', '{': '8', 'W': 'I', 'j': '?',
    'n': '5', 's': '3', '|': 'T', 'A': 'V', 'D': 'w', ';': 'O'
}


def decode_obfuscated(encoded_str):
    try:
        decoded = ''.join(DECODE_MAP.get(ch, ch) for ch in encoded_str)
        if decoded.startswith("http") and (".m3u8" in decoded or ".mp4" in decoded):
            return decoded
        return decoded
    except:
        return ""


def extract_base64_from_eval(html_text):
    m = re.search(r"data:image/jpg;base64,([A-Za-z0-9+/=]+)", html_text)
    if m:
        try:
            raw = base64.b64decode(m.group(1)).decode("utf-8", errors="ignore")
            return raw
        except:
            pass
    return ""



def extract_play(html_text, host=""):
    if not html_text:
        return ""

    # 第1层: 直接 m3u8 链接
    m = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html_text)
    if m:
        return m.group(1)

    # 第2层: 直接 mp4 链接
    m = re.search(r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*)', html_text)
    if m:
        return m.group(1)

    # 第3层: var now = "..."  (MacCMS v8 经典)
    m = re.search(r'var\s+now\s*=\s*["\']([^"\']+)["\']', html_text)
    if m:
        return m.group(1)

    # 第4层: player_data = {...}
    m = re.search(r'player_data\s*=\s*(\{.*?\})', html_text, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(1))
            url = data.get("url", "") or data.get("src", "")
            if url:
                return url
        except:
            pass

    # 第5层: var player_aaaa = {...}
    m = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\})', html_text, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(1))
            url = data.get("url", "")
            if url:
                return url
        except:
            pass

    # 第6层: PlaylistData / playlist
    m = re.search(r'(?:PlaylistData|playlist)\s*[:=]\s*["\']([^"\']+)["\']', html_text)
    if m:
        return m.group(1)

    # 第7层: iframe 嵌套
    m = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html_text)
    if m:
        iframe_url = fix_url(m.group(1), host)
        try:
            iframe_html = requests.get(
                iframe_url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": host
                },
                timeout=15
            ).text
            return extract_play(iframe_html, iframe_url)
        except:
            pass

    # 第8层: videoSources 嗅探
    m = re.search(r'videoSources\s*:\s*(\[.*?\])', html_text, re.DOTALL)
    if m:
        try:
            sources = json.loads(m.group(1))
            if isinstance(sources, list) and len(sources) > 0:
                return sources[0].get("file", "") or sources[0].get("src", "")
        except:
            pass

    # 第9层: wvPlayer.play(...)
    m = re.search(r'wvPlayer\.play\s*\(\s*["\']([^"\']+)["\']', html_text)
    if m:
        return m.group(1)

    # 第10层: location.href 跳转
    m = re.search(r'location\.href\s*=\s*["\']([^"\']+)["\']', html_text)
    if m:
        return m.group(1)

    # 第11层: url: "xxx.m3u8"
    m = re.search(r'url\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']', html_text)
    if m:
        return m.group(1)

    # 第12层: var playurl = "..."
    m = re.search(r'var\s+playurl\s*=\s*["\']([^"\']+)["\']', html_text)
    if m:
        return m.group(1)

    # 第13层: 任意 m3u8/mp4/flv (兜底)
    m = re.search(r'(https?://[^\s"\'<>]+\.(?:m3u8|mp4|flv))', html_text)
    if m:
        return m.group(1)

    return ""


AD_KEYWORDS = [
    "ad", "ads", "advert", "advertise", "advertisement",
    "sponsor", "pre", "preroll", "banner", "promo",
    "commercial", "guanggao", "片头", "广告", "/gg/",
    "_gg", "gg_", "/adv/", "/ad/", "/ads/"
]


def clean_m3u8(m3u8_text, base_url=""):
    if "#EXT-X-STREAM-INF" in m3u8_text:
        return m3u8_text

    lines = m3u8_text.replace("\r", "").split("\n")
    out = []
    pending_extinf = None
    removed = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith("#EXTINF"):
            pending_extinf = line
            continue

        if line.startswith("#"):
            out.append(line)
            continue

        # 这是一个ts/m3u8片段URL
        is_ad = any(kw in line.lower() for kw in AD_KEYWORDS)

        if is_ad:
            pending_extinf = None
            removed += 1
            continue

        if pending_extinf:
            out.append(pending_extinf)
            pending_extinf = None

        # 补全相对路径
        fixed = fix_url(line, base_url)
        out.append(fixed)

    return "\n".join(out) + "\n"



class Spider(BaseSpider):
    def __init__(self):
        super().__init__()
        self.host = "https://hbzey01ctr.emuywhat.buzz"
        self.name = "ZheTian_v10_emuywhat"
        self.s = requests.Session() if requests else None
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.host + "/",
            "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "Upgrade-Insecure-Requests": "1",
            "Connection": "keep-alive",
            "Cache-Control": "max-age=0",
        }
        self.cms_type = "v10"
        self.content_type = "video"
        self.seen_ids = set()
        if self.s:
            self.s.headers.update(self.headers)
            self.s.verify = False

    def init(self, extend=""):
        pass

    def getName(self):
        return self.name

    def isVideoFormat(self, url):
        return any(x in (url or "") for x in [".m3u8", ".mp4", ".flv", ".ts", ".mpd"])

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        if "do=m3u8" in str(param):
            params = dict(p.split("=", 1) for p in str(param).split("&") if "=" in p)
            url = unquote(params.get("url", ""))
            referer = unquote(params.get("referer", self.host))
            try:
                raw = self.s.get(url, headers={"Referer": referer}, timeout=20).text
                cleaned = clean_m3u8(raw, url)
                return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
            except:
                return [404, "text/plain", b""]
        return [404, "text/plain", b""]

    def _fetch(self, url, referer=None):
        if not self.s:
            return ""
        try:
            h = dict(self.headers)
            if referer:
                h["Referer"] = referer
            r = self.s.get(url, headers=h, timeout=15)
            r.encoding = "utf-8"
            if r.status_code == 200:
                return r.text
            return ""
        except Exception as e:
            print(f"[{self.name}] 请求失败: {url} - {e}")
            return ""

    def homeContent(self, filter):
        try:
            classes = [
                {"type_name": "国产色情", "type_id": "1"},
                {"type_name": "日本有码", "type_id": "2"},
                {"type_name": "中文字幕", "type_id": "3"},
                {"type_name": "无码专区", "type_id": "4"},
                {"type_name": "杏吧原创", "type_id": "5"},
                {"type_name": "大象传媒", "type_id": "6"},
                {"type_name": "少女萝莉", "type_id": "379"},
                {"type_name": "网曝门", "type_id": "411"},
                {"type_name": "日韩主播", "type_id": "281"},
                {"type_name": "韩国主播", "type_id": "319"},
                {"type_name": "AV区", "type_id": "384"},
                {"type_name": "日本无码", "type_id": "58"},
                {"type_name": "制服诱惑", "type_id": "15"},
                {"type_name": "欧美激情", "type_id": "288"},
                {"type_name": "强制侵犯", "type_id": "393"},
                {"type_name": "女同性恋", "type_id": "414"},
                {"type_name": "卡通动画", "type_id": "359"},
                {"type_name": "AI换脸", "type_id": "409"},
                {"type_name": "东南亚AV", "type_id": "84"},
            ]
            filters = {
                "1": [
                    {
                        "key": "area", "name": "地区",
                        "value": [
                            {"n": "全部", "v": ""},
                            {"n": "大陆", "v": "大陆"},
                            {"n": "台湾", "v": "台湾"},
                            {"n": "香港", "v": "香港"},
                        ]
                    },
                    {
                        "key": "year", "name": "年份",
                        "value": [
                            {"n": "全部", "v": ""},
                            {"n": "2026", "v": "2026"},
                            {"n": "2025", "v": "2025"},
                            {"n": "2024", "v": "2024"},
                        ]
                    },
                ]
            }
            return {"class": classes, "filters": filters}
        except Exception as e:
            print(f"[{self.name}] 首页失败: {e}")
            return {"class": [], "filters": {}}

    def homeVideoContent(self):
        return self.categoryContent("1", "1", False, {})

    def categoryContent(self, tid, pg, filter, extend):
        try:
            result = {
                "list": [],
                "page": int(pg),
                "pagecount": 1,
                "limit": 24,
                "total": 0
            }

            url = f"{self.host}/vodtype/{tid}/"
            if int(pg) > 1:
                url = f"{self.host}/vodtype/{tid}-{pg}/"

            html_text = self._fetch(url)
            if not html_text:
                return result

            doc = etree.HTML(html_text) if etree else None
            if doc is None:
                return result

            # 多级兜底选择器（诛仙四剑）
            items = []
            selectors = [
                '//a[contains(@class,"group-item") and contains(@href,"/vodplay/")]',
                '//div[contains(@class,"group-contents")]//a[contains(@href,"/vodplay/")]',
                '//a[contains(@href,"/vodplay/") and .//img]',
                '//div[contains(@class,"group-box")]//a[contains(@href,"/vodplay/") and .//p]',
            ]
            for sel in selectors:
                items = doc.xpath(sel)
                if items:
                    break

            print(f"[{self.name}] 分类列表匹配到 {len(items)} 个视频 (tid={tid}, pg={pg})")

            self.seen_ids.clear()
            for item in items:
                try:
                    # 标题
                    title = ""
                    title_nodes = item.xpath('.//p/text()')
                    if not title_nodes:
                        title_nodes = item.xpath('.//img/@alt')
                    if not title_nodes:
                        title_nodes = item.xpath('./@title')
                    title = clean_text(title_nodes[0]) if title_nodes else ""

                    # href / vid
                    href = ""
                    href_nodes = item.xpath('./@href')
                    href = href_nodes[0] if href_nodes else ""

                    vid_match = re.search(r'/vodplay/(\d+)', href)
                    vid = vid_match.group(1) if vid_match else href
                    if vid in self.seen_ids:
                        continue
                    self.seen_ids.add(vid)

       
                    pic = ""
                    pic_nodes = (
                        item.xpath('.//img/@data-src') or
                        item.xpath('.//img/@data-original') or
                        item.xpath('.//img/@src') or
                        item.xpath('./@data-src')
                    )
                    pic = fix_url(pic_nodes[0], self.host) if pic_nodes else ""

                    if title and vid:
                        result["list"].append({
                            "vod_id": vid,
                            "vod_name": title,
                            "vod_pic": pic,
                            "vod_remarks": ""
                        })
                except Exception as e:
                    print(f"[{self.name}] 单条解析失败: {e}")
                    continue

            # 分页检测
            pc_match = re.search(r'pagecount[=:]\s*(\d+)', html_text)
            if not pc_match:
                pc_match = re.search(r'共\s*(\d+)\s*页', html_text)
            if pc_match:
                result["pagecount"] = int(pc_match.group(1))
                result["total"] = result["pagecount"] * 24
            else:
                result["pagecount"] = int(pg) + 1
                result["total"] = len(result["list"])

            return result

        except Exception as e:
            print(f"[{self.name}] 分类爬取失败: {e}")
            return {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}

 
    def detailContent(self, ids):
        try:
            vid = ids[0] if isinstance(ids, list) else str(ids)
            result = {"list": []}

            # 此站detail和play合并: /vodplay/{id}-1-1/
            url = f"{self.host}/vodplay/{vid}-1-1/"
            html_text = self._fetch(url)

            if not html_text:
                return result

            doc = etree.HTML(html_text) if etree else None

            # 标题
            title = vid
            if doc:
                title_nodes = (
                    doc.xpath('//h1/text()') or
                    doc.xpath('//h2/text()') or
                    doc.xpath('//title/text()')
                )
                title = clean_text(title_nodes[0]) if title_nodes else vid

            # 图片
            pic = ""
            if doc:
                pic_nodes = (
                    doc.xpath('//img[contains(@class,"poster")]/@data-src') or
                    doc.xpath('//img[contains(@class,"poster")]/@src') or
                    doc.xpath('//img[contains(@class,"cover")]/@data-src') or
                    doc.xpath('//img[contains(@class,"cover")]/@src') or
                    doc.xpath('//img/@data-src') or
                    doc.xpath('//img/@src')
                )
                pic = fix_url(pic_nodes[0], self.host) if pic_nodes else ""

            # 播放源和剧集
            sources = []
            play_urls = []

            if doc:
                panels = (
                    doc.xpath('//div[contains(@class,"hy-play-list")]//div[contains(@class,"panel")]') or
                    doc.xpath('//div[contains(@class,"module-tab")]') or
                    doc.xpath('//div[contains(@class,"playlist")]') or
                    doc.xpath('//div[contains(@class,"play")]')
                )

                for panel in panels:
                    try:
                        sname = (
                            panel.xpath('.//a[contains(@class,"option")]/@title') or
                            panel.xpath('.//a[contains(@class,"option")]/text()') or
                            panel.xpath('.//span[contains(@class,"tab")]/text()') or
                            panel.xpath('.//h3/text()') or
                            panel.xpath('.//div[contains(@class,"title")]/text()')
                        )
                        sname = clean_text(sname[0]) if sname else "默认线路"

                        eps = (
                            panel.xpath('.//ul[contains(@class,"playlistlink")]//a') or
                            panel.xpath('.//a[contains(@href,"/vodplay/")]') or
                            panel.xpath('.//a[contains(@href,"/play/")]')
                        )

                        ep_list = []
                        for ep in eps:
                            try:
                                ep_title = ep.xpath('./text()')
                                ep_title = clean_text(ep_title[0]) if ep_title else "播放"
                                ep_href = ep.xpath('./@href')
                                ep_href = ep_href[0] if ep_href else ""
                                ep_full = fix_url(ep_href, self.host)
                                ep_list.append(f"{ep_title}${ep_full}")
                            except:
                                continue

                        if ep_list:
                            sources.append(sname)
                            play_urls.append("#".join(ep_list))
                    except Exception as e:
                        print(f"[{self.name}] 播放源解析失败: {e}")
                        continue

            print(f"[{self.name}] 详情页: {len(sources)}个源, {sum(len(x.split(chr(35))) for x in play_urls)}个剧集")

            # 兜底：如果没找到播放源，直接用当前页URL
            if not play_urls:
                sources = ["在线播放"]
                play_urls = [f"播放${url}"]

            result["list"].append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_play_from": "$$$".join(sources),
                "vod_play_url": "$$$".join(play_urls),
                "vod_content": "",
                "type_name": ""
            })

            return result

        except Exception as e:
            print(f"[{self.name}] 详情解析失败: {e}")
            return {"list": []}

 
    def playerContent(self, flag, id, vipFlags=None):
        try:
            result = {"parse": 0, "playUrl": "", "url": "", "header": ""}

            # 如果已经是直链
            if self.isVideoFormat(id):
                result["url"] = id
                result["header"] = json.dumps({
                    "Referer": self.host + "/",
                    "User-Agent": self.headers["User-Agent"]
                })
                return result

            # 获取播放页HTML
            html_text = ""
            if id.startswith("http"):
                html_text = self._fetch(id, self.host + "/")

            if not html_text:
                result["url"] = id
                return result

            # 13层深度提取
            play_url = extract_play(html_text, self.host)

            if play_url and play_url != "eval_encrypted":
                result["url"] = play_url
                result["header"] = json.dumps({
                    "Referer": self.host + "/",
                    "User-Agent": self.headers["User-Agent"],
                    "Origin": self.host,
                })
                print(f"[{self.name}] 播放解析: -> {play_url[:60]}...")
                return result

            # eval加密兜底：尝试从混淆JS中提取
            if play_url == "eval_encrypted" or not play_url:
                decoded = extract_base64_from_eval(html_text)
                if decoded:
                    inner_url = extract_play(decoded, self.host)
                    if inner_url:
                        result["url"] = inner_url
                        result["header"] = json.dumps({
                            "Referer": self.host + "/",
                            "User-Agent": self.headers["User-Agent"]
                        })
                        return result

            # 最终兜底
            result["url"] = id
            return result

        except Exception as e:
            print(f"[{self.name}] 播放解析失败: {e}")
            return {"parse": 0, "playUrl": "", "url": id, "header": ""}

   
    def searchContent(self, key, quick, pg="1"):
        try:
            result = {
                "list": [],
                "page": int(pg),
                "pagecount": 1,
                "limit": 24,
                "total": 0
            }

            # MacCMS v10 搜索: /vodsearch/{关键词}-------------/
            url = f"{self.host}/vodsearch/{quote(key)}-------------/"

            html_text = self._fetch(url)
            if not html_text:
                return result

            doc = etree.HTML(html_text) if etree else None
            if doc is None:
                return result

            items = []
            selectors = [
                '//a[contains(@class,"group-item") and contains(@href,"/vodplay/")]',
                '//div[contains(@class,"group-contents")]//a[contains(@href,"/vodplay/")]',
                '//a[contains(@href,"/vodplay/") and .//img]',
            ]
            for sel in selectors:
                items = doc.xpath(sel)
                if items:
                    break

            print(f"[{self.name}] 搜索匹配到 {len(items)} 个结果: {key}")

            self.seen_ids.clear()
            for item in items:
                try:
                    title_nodes = item.xpath('.//p/text()') or item.xpath('.//img/@alt') or item.xpath('./@title')
                    title = clean_text(title_nodes[0]) if title_nodes else ""

                    href = (item.xpath('./@href') or [""])[0]
                    vid_match = re.search(r'/vodplay/(\d+)', href)
                    vid = vid_match.group(1) if vid_match else href
                    if vid in self.seen_ids:
                        continue
                    self.seen_ids.add(vid)

                    pic_nodes = (
                        item.xpath('.//img/@data-src') or
                        item.xpath('.//img/@data-original') or
                        item.xpath('.//img/@src')
                    )
                    pic = fix_url(pic_nodes[0], self.host) if pic_nodes else ""

                    if title and vid:
                        result["list"].append({
                            "vod_id": vid,
                            "vod_name": title,
                            "vod_pic": pic
                        })
                except Exception as e:
                    print(f"[{self.name}] 搜索单条失败: {e}")
                    continue

            return result

        except Exception as e:
            print(f"[{self.name}] 搜索失败: {e}")
            return {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}