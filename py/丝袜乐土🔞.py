# -*- coding: utf-8 -*-
# 官网:https://xbffh.swwlt15.xyz/

import sys, re, json, base64, html as html_mod, os, threading, time
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




def d_decode(encoded_str):
    """模拟JavaScript d()函数: window.atob -> escape -> decodeURIComponent"""
    if not encoded_str or not isinstance(encoded_str, str):
        return ""
    try:
        decoded_bytes = base64.b64decode(encoded_str)
        text = decoded_bytes.decode('utf-8', errors='replace')
        return text
    except Exception:
        return encoded_str


def clean_hidden_spans(text):
    if not text:
        return ""
    text = re.sub(
        r'<span[^>]*display\s*:\s*none[^>]*>[^<]*</span>',
        '',
        text,
        flags=re.IGNORECASE | re.DOTALL
    )
    return text.strip()


def d_clean(encoded_str):
    decoded = d_decode(encoded_str)
    return clean_hidden_spans(decoded)


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
    text = html_mod.unescape(str(text))
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def extract_play_url(html_text, host):
    if not html_text:
        return ""
    patterns = [
        r'(https?://[^\s"\']+\.m3u8[^\s"\']*)',
        r'(https?://[^\s"\']+\.mp4[^\s"\']*)',
        r'var\s+now\s*=\s*[\'"]([^\'"]+)[\'"]',
        r'player_data\s*=\s*(\{.*?\})',
        r'<iframe[^>]+src=["\']([^"\']+)["\']',
        r'videoSources\s*:\s*(\[.*?\])',
        r'wvPlayer\.play\s*\(\s*["\']([^"\']+)["\']',
        r'url\s*:\s*["\']([^"\']+\.m3u8)["\']',
        r'var\s+playurl\s*=\s*["\']([^"\']+)["\']',
    ]
    for pat in patterns:
        m = re.search(pat, html_text, re.DOTALL)
        if m:
            result = m.group(1)
            if pat.endswith('})'):
                try:
                    result = json.loads(result).get('url', '')
                except:
                    continue
            elif pat == r'<iframe[^>]+src=["\']([^"\']+)["\']':
                iframe_url = fix_url(result, host)
                try:
                    r = requests.get(iframe_url, headers={
                        "User-Agent": "Mozilla/5.0",
                        "Referer": host
                    }, timeout=10, verify=False)
                    return extract_play_url(r.text, iframe_url)
                except:
                    pass
            elif pat.endswith('})') and 'videoSources' in pat:
                try:
                    result = json.loads(result)[0].get('file', '')
                except:
                    continue
            return result
    return ""


def decode_all_d_calls(html_text):
    def replacer(m):
        encoded = m.group(1)
        return d_clean(encoded)
    return re.sub(
        r"document\.write\(d\('([^']+)'\)\)",
        replacer,
        html_text
    )




class Spider(BaseSpider):
    def __init__(self):
        super().__init__()
        self.host = "https://xbffh.swwlt15.xyz"
        self.name = "ZheTian_SWLT_DiBing"
        self.s = requests.Session() if requests else None
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.host + "/",
            "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "Upgrade-Insecure-Requests": "1",
        }
        self.seen_ids = set()
        self._category_cache = {}
        if self.s:
            self.s.headers.update(self.headers)
            self.s.verify = False

    def init(self, extend=""):
        if extend and extend.startswith("http"):
            self.host = extend.rstrip("/")
            self.headers["Referer"] = self.host + "/"
            if self.s:
                self.s.headers.update(self.headers)

    def getName(self):
        return self.name

    def isVideoFormat(self, url):
        return any(x in (url or "") for x in [".m3u8", ".mp4", ".flv", ".ts"])

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return [200, "video/MP2T", b"", {}]

    def _fetch(self, url, referer=None):
        if not self.s:
            return ""
        h = dict(self.headers)
        if referer:
            h["Referer"] = referer
        try:
            r = self.s.get(url, timeout=15, headers=h)
            r.raise_for_status()
            r.encoding = 'utf-8'
            return r.text
        except Exception as e:
            print(f"[{self.name}] _fetch失败: {url} - {e}")
            return ""

    def _post_fetch(self, url, data, referer=None):
        if not self.s:
            return ""
        h = dict(self.headers)
        if referer:
            h["Referer"] = referer
        try:
            r = self.s.post(url, data=data, timeout=15, headers=h)
            r.raise_for_status()
            r.encoding = 'utf-8'
            return r.text
        except Exception as e:
            print(f"[{self.name}] _post_fetch失败: {url} - {e}")
            return ""

    def _build_categories(self, html_text):
        if self._category_cache:
            return self._category_cache
        categories = []
        seen_names = set()
        nav_pattern = re.findall(
            r'<a[^>]+href="/list\.php\?id=(\d+)&page=1"[^>]*>'
            r'<script[^>]*>document\.write\(d\(\'([^\']+)\'\)\)</script>'
            r'\s*</a>',
            html_text
        )
        for type_id, encoded_name in nav_pattern:
            name = d_clean(encoded_name)
            name = clean_text(name)
            if name and name not in seen_names and len(name) < 20:
                seen_names.add(name)
                categories.append({
                    "type_id": type_id,
                    "type_name": name
                })
        if len(categories) < 3:
            categories = [
                {"type_id": "6097633", "type_name": "精品推荐"},
                {"type_id": "6107633", "type_name": "国产精品"},
                {"type_id": "6117633", "type_name": "探花系列"},
                {"type_id": "6127633", "type_name": "自拍偷拍"},
                {"type_id": "6137633", "type_name": "少女少妇"},
                {"type_id": "6147633", "type_name": "无码专区"},
                {"type_id": "6157633", "type_name": "欧美性爱"},
                {"type_id": "6167633", "type_name": "颜值正妹"},
            ]
        self._category_cache = categories
        return categories

    def _parse_vod_cards(self, html_text, base_url):
        results = []
        self.seen_ids.clear()
        if etree:
            doc = etree.HTML(html_text)
            items = doc.xpath('//li[contains(@class,"vod-card")]')
            if not items:
                items = doc.xpath('//div[contains(@class,"vod-card")]')
            if not items:
                items = doc.xpath('//a[contains(@class,"card-thumb")]/..')
            for item in items:
                try:
                    link = item.xpath('.//a[contains(@class,"card-thumb")]/@href')
                    if not link:
                        link = item.xpath('.//a[contains(@href,"/video.php")]/@href')
                    href = link[0] if link else ""
                    vid_match = re.search(r'id=(\d+)', href)
                    vid = vid_match.group(1) if vid_match else ""
                    if not vid or vid in self.seen_ids:
                        continue
                    self.seen_ids.add(vid)
                    img = item.xpath('.//img[contains(@class,"lazy")]/@data-original')
                    if not img:
                        img = item.xpath('.//img/@data-original')
                    if not img:
                        img = item.xpath('.//img/@src')
                    pic = fix_url(img[0], base_url) if img else ""
                    title_text = ""
                    title_a = item.xpath('.//h5[contains(@class,"card-title")]/a')
                    if title_a:
                        raw_title = etree.tostring(title_a[0], encoding='unicode')
                        d_calls = re.findall(r"d\('([^']+)'\)", raw_title)
                        if d_calls:
                            title_text = d_clean(d_calls[0])
                            title_text = clean_hidden_spans(title_text)
                        else:
                            title_text = title_a[0].xpath('string(.)')
                    title_text = clean_text(title_text)
                    if title_text and vid:
                        results.append({
                            "vod_id": vid,
                            "vod_name": title_text[:100],
                            "vod_pic": pic,
                            "vod_remarks": ""
                        })
                except Exception as e:
                    print(f"[{self.name}] 卡片解析失败: {e}")
                    continue
        if not results:
            vid_matches = re.findall(
                r'<a[^>]+href="/video\.php\?id=(\d+)"[^>]*>',
                html_text
            )
            for vid in vid_matches[:30]:
                if vid not in self.seen_ids:
                    self.seen_ids.add(vid)
                    results.append({
                        "vod_id": vid,
                        "vod_name": f"视频{vid}",
                        "vod_pic": "",
                        "vod_remarks": ""
                    })
        return results

    def homeContent(self, filter):
        try:
            html_text = self._fetch(self.host + "/")
            if not html_text:
                return {"class": [], "list": []}
            categories = self._build_categories(html_text)
            vod_list = self._parse_vod_cards(html_text, self.host)
            return {
                "class": categories[:24],
                "filters": {
                    cat["type_id"]: [
                        {"key": "area", "name": "地区", "value": [
                            {"n": "全部", "v": ""}, {"n": "大陆", "v": "大陆"},
                            {"n": "日韩", "v": "日韩"}, {"n": "欧美", "v": "欧美"}
                        ]},
                        {"key": "by", "name": "排序", "value": [
                            {"n": "最新", "v": "time"}, {"n": "最热", "v": "hits"}
                        ]}
                    ] for cat in categories[:8]
                },
                "list": vod_list[:12]
            }
        except Exception as e:
            print(f"[{self.name}] homeContent失败: {e}")
            return {"class": [], "list": []}

    def homeVideoContent(self):
        return self.categoryContent("6097633", "1", False, {})

    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = int(pg) if pg else 1
            url = f"{self.host}/list.php?id={tid}&page={pg}"
            html_text = self._fetch(url, self.host + "/")
            result = {
                "list": [],
                "page": pg,
                "pagecount": pg + 1,
                "limit": 24,
                "total": 0
            }
            if not html_text:
                return result
            vod_list = self._parse_vod_cards(html_text, self.host)
            result["list"] = vod_list
            pc_match = re.search(r'pagecount[=:]\s*(\d+)', html_text, re.I)
            if not pc_match:
                pc_match = re.search(r'共\s*(\d+)\s*页', html_text)
            if pc_match:
                result["pagecount"] = int(pc_match.group(1))
            return result
        except Exception as e:
            print(f"[{self.name}] categoryContent失败: {e}")
            return {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}

    def detailContent(self, ids):
        try:
            vid = ids[0] if isinstance(ids, list) else ids
            url = f"{self.host}/video.php?id={vid}"
            html_text = self._fetch(url, self.host + "/")
            result = {"list": []}
            if not html_text:
                return result
            title = vid
            pic = ""
            if etree:
                doc = etree.HTML(html_text)
                title_el = doc.xpath('//h1/text()|//h2/text()|//h5/text()|//title/text()')
                if title_el:
                    title = clean_text(title_el[0])
                pic_el = doc.xpath('//img[contains(@class,"lazy")]/@data-original')
                if not pic_el:
                    pic_el = doc.xpath('//img/@data-original')
                if not pic_el:
                    pic_el = doc.xpath('//img/@src')
                if pic_el:
                    pic = fix_url(pic_el[0], self.host)
            play_url_raw = extract_play_url(html_text, self.host)
            if not play_url_raw:
                d_calls = re.findall(r"d\('([^']+)'\)", html_text)
                for dc in d_calls:
                    decoded = d_clean(dc)
                    m3u8_in = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', decoded)
                    if m3u8_in:
                        play_url_raw = m3u8_in.group(1)
                        break
            episode_links = re.findall(
                r'<a[^>]+href="([^"]*video\.php\?id=\d+[^"]*)"[^>]*>([^<]*)</a>',
                html_text
            )
            sources = []
            play_urls = []
            if episode_links:
                ep_list = []
                for ep_href, ep_label in episode_links:
                    ep_url = fix_url(ep_href, self.host)
                    ep_name = clean_text(ep_label) or "播放"
                    ep_list.append(f"{ep_name}${ep_url}")
                sources.append("默认线路")
                play_urls.append("#".join(ep_list))
            if play_url_raw:
                if not sources:
                    sources.append("默认线路")
                    play_urls.append(f"正片${play_url_raw}")
            if not sources:
                sources.append("默认线路")
                play_urls.append(f"播放${url}")
            result["list"].append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_play_from": "$$$".join(sources),
                "vod_play_url": "$$$".join(play_urls)
            })
            return result
        except Exception as e:
            print(f"[{self.name}] detailContent失败: {e}")
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
                html_text = self._fetch(id, self.host + "/")
                if html_text:
                    play_url = extract_play_url(html_text, self.host)
                    if play_url:
                        result["url"] = play_url
                        result["header"] = json.dumps({
                            "Referer": id,
                            "User-Agent": self.headers["User-Agent"]
                        })
                        return result
            result["url"] = id
            result["header"] = json.dumps({
                "Referer": self.host + "/",
                "User-Agent": self.headers["User-Agent"]
            })
            return result
        except Exception as e:
            print(f"[{self.name}] playerContent失败: {e}")
            return {"parse": 0, "playUrl": "", "url": id, "header": ""}

    def searchContent(self, key, quick, pg="1"):
        try:
            pg = int(pg) if pg else 1
            url = f"{self.host}/search.php"
            data = {"content": key}
            html_text = self._post_fetch(url, data, self.host + "/")
            result = {
                "list": [],
                "page": pg,
                "pagecount": 1,
                "limit": 24,
                "total": 0
            }
            if not html_text:
                return result
            vod_list = self._parse_vod_cards(html_text, self.host)
            result["list"] = vod_list
            return result
        except Exception as e:
            print(f"[{self.name}] searchContent失败: {e}")
            return {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}