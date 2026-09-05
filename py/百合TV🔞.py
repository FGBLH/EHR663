# -*- coding: utf-8 -*-
#!/usr/bin/python
# 百合TV Spider
# 目标: https://qq.com.bh432.sbs/

import sys, re, json, base64, html, os, threading, time, hashlib
from urllib.parse import quote, unquote, urljoin, urlparse
try:
    from lxml import etree
except ImportError:
    etree = None
try:
    import requests
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
        def searchContent(self, key, quick, pg="1"): pass
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
    return html.unescape(re.sub(r"<[^>]+>", "", str(text))).strip()


def extract_play(html_text, host):
    m = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', html_text)
    if m: return m.group(1)
    m = re.search(r'(https?://[^\s"\']+\.mp4[^\s"\']*)', html_text)
    if m: return m.group(1)
    m = re.search(r'var\s*now\s*=\s*["\']([^"\']+)["\']', html_text)
    if m: return m.group(1)
    m = re.search(r'player_data\s*=\s*(\{.*?\})', html_text, re.DOTALL)
    if m:
        try: return json.loads(m.group(1)).get("url", "")
        except: pass
    m = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html_text)
    if m:
        iframe_src = fix_url(m.group(1), host)
        try:
            r = requests.get(iframe_src, headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
            if r.status_code == 200:
                return extract_play(r.text, host)
        except: pass
    m = re.search(r'eval\((.*?)\)', html_text, re.DOTALL)
    if m: return "eval_encrypted"
    m = re.search(r'videoSources\s*:\s*(\[.*?\])', html_text, re.DOTALL)
    if m:
        try: return json.loads(m.group(1))[0].get("file", "")
        except: pass
    m = re.search(r'wvPlayer\.play\s*\(\s*["\']([^"\']+)["\']', html_text)
    if m: return m.group(1)
    m = re.search(r'location\.href\s*=\s*["\']([^"\']+)["\']', html_text)
    if m: return m.group(1)
    m = re.search(r'url\s*:\s*["\']([^"\']+\.m3u8)["\']', html_text)
    if m: return m.group(1)
    m = re.search(r'var\s*playurl\s*=\s*["\']([^"\']+)["\']', html_text)
    if m: return m.group(1)
    m = re.search(r'var\s*player_aaaa\s*=\s*(\{.*?\})', html_text, re.DOTALL)
    if m:
        try: return json.loads(m.group(1)).get("url", "")
        except: pass
    m = re.search(r'(https?://[^\s"\']+\.(?:m3u8|mp4|flv))', html_text)
    return m.group(1) if m else ""


class Spider(BaseSpider):
    def __init__(self):
        super().__init__()
        self.host = "https://qq.com.bh432.sbs"
        self.name = "ZheTian_BaiHeTV"
        self.s = requests.Session() if requests else None
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/",
            "sec-ch-ua": "\"Not_A Brand\";v=\"8\", \"Chromium\";v=\"120\"",
            "Upgrade-Insecure-Requests": "1"
        }
        self.seen_ids = set()
        if self.s: self.s.headers.update(self.headers)

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

    def _fetch(self, url):
        if not self.s: return ""
        try:
            r = self.s.get(url, timeout=15, headers=self.headers)
            r.raise_for_status()
            return r.text
        except Exception as e:
            return ""

    def homeContent(self, filter):
        try:
            classes = [
                {"type_name": "视频一区", "type_id": "1"},
                {"type_name": "视频二区", "type_id": "2"},
                {"type_name": "视频三区", "type_id": "3"},
                {"type_name": "视频四区", "type_id": "4"},
                {"type_name": "视频五区", "type_id": "5"},
            ]
            filters = {
                "1": [
                    {"key": "sort", "name": "排序", "value": [
                        {"n": "最新", "v": "new"},
                        {"n": "最热", "v": "hot"},
                        {"n": "最多播放", "v": "hits"}
                    ]}
                ]
            }
            return {"class": classes, "filters": filters}
        except Exception as e:
            return {"class": [], "filters": {}}

    def homeVideoContent(self):
        return self.categoryContent("1", "1", False, {})

    def categoryContent(self, tid, pg, filter, extend):
        try:
            result = {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}
            url = f"{self.host}/t?t_id={tid}"
            if int(pg) > 1:
                url += f"&page={pg}"
            html_text = self._fetch(url)
            if not html_text: return result
            doc = etree.HTML(html_text) if etree else None
            if not doc: return result
            items = doc.xpath('//div[contains(@class,"vod-item-box")]/a[contains(@href,"p?v=")]')
            if not items:
                items = doc.xpath('//div[contains(@class,"columns")]//a[contains(@href,"p?v=") and .//img]')
            if not items:
                items = doc.xpath('//a[contains(@href,"p?v=") and .//img]')
            self.seen_ids.clear()
            for item in items:
                try:
                    title = item.xpath('.//p[contains(@class,"vod-name")]/text()')
                    if not title: title = item.xpath('./@title')
                    if not title: title = item.xpath('.//img/@alt')
                    title = clean_text(title[0]) if title else ""
                    href = item.xpath('./@href')[0] if item.xpath('./@href') else ""
                    vid = re.search(r'v=(\d+)', href)
                    vid = vid.group(1) if vid else href
                    if vid in self.seen_ids: continue
                    self.seen_ids.add(vid)
                    pic = item.xpath('.//img/@src') or item.xpath('.//img/@data-original')
                    pic = fix_url(pic[0], self.host) if pic else ""
                    hits = item.xpath('.//span[contains(@class,"vod_hits")]/text()')
                    remarks = clean_text(hits[0]) if hits else ""
                    vclass = item.xpath('.//p[contains(@class,"vod-class")]/text()')
                    vclass = clean_text(vclass[0]) if vclass else ""
                    if vclass: remarks = vclass
                    result["list"].append({
                        "vod_id": vid,
                        "vod_name": title,
                        "vod_pic": pic,
                        "vod_remarks": remarks
                    })
                except Exception as e:
                    continue
            pc = re.search(r'page[=:](\d+)', html_text) or re.search(r'共\s*(\d+)\s*页', html_text)
            if pc: result["pagecount"] = int(pc.group(1))
            else: result["pagecount"] = int(pg) + 1 if len(items) >= 24 else int(pg)
            return result
        except Exception as e:
            return {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}

    def detailContent(self, ids):
        try:
            vid = ids[0] if isinstance(ids, list) else ids
            result = {"list": []}
            url = f"{self.host}/p?v={vid}"
            html_text = self._fetch(url)
            if not html_text: return result
            doc = etree.HTML(html_text) if etree else None
            title = vid
            pic = ""
            if doc:
                title_nodes = doc.xpath('//h1/text()') or doc.xpath('//h2/text()') or doc.xpath('//p[contains(@class,"vod-name")]/text()')
                title = clean_text(title_nodes[0]) if title_nodes else vid
                pic_nodes = doc.xpath('//img[contains(@class,"poster") or contains(@class,"cover")]/@src')
                if not pic_nodes: pic_nodes = doc.xpath('//figure[contains(@class,"image")]//img/@src')
                pic = fix_url(pic_nodes[0], self.host) if pic_nodes else ""
            play_url = extract_play(html_text, self.host)
            result["list"].append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_play_from": "百合TV",
                "vod_play_url": f"正片${play_url}" if play_url else f"播放${url}"
            })
            return result
        except Exception as e:
            return {"list": []}

    def playerContent(self, flag, id, vipFlags=None):
        try:
            result = {"parse": 0, "playUrl": "", "url": "", "header": ""}
            if self.isVideoFormat(id):
                result["url"] = id
                result["header"] = json.dumps({"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]})
                return result
            if id.startswith("http"):
                html_text = self._fetch(id)
                if html_text:
                    play_url = extract_play(html_text, self.host)
                    if play_url and play_url != "eval_encrypted":
                        result["url"] = play_url
                        result["header"] = json.dumps({"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]})
                        return result
            result["url"] = id
            return result
        except Exception as e:
            return {"parse": 0, "playUrl": "", "url": id, "header": ""}

    def searchContent(self, key, quick, pg="1"):
        try:
            result = {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}
            url = f"{self.host}/s?k={quote(key)}"
            if int(pg) > 1:
                url += f"&page={pg}"
            html_text = self._fetch(url)
            if not html_text: return result
            doc = etree.HTML(html_text) if etree else None
            if not doc: return result
            items = doc.xpath('//div[contains(@class,"vod-item-box")]/a[contains(@href,"p?v=")]')
            if not items:
                items = doc.xpath('//div[contains(@class,"columns")]//a[contains(@href,"p?v=") and .//img]')
            if not items:
                items = doc.xpath('//a[contains(@href,"p?v=") and .//img]')
            self.seen_ids.clear()
            for item in items:
                try:
                    title = item.xpath('.//p[contains(@class,"vod-name")]/text()')
                    if not title: title = item.xpath('./@title')
                    if not title: title = item.xpath('.//img/@alt')
                    title = clean_text(title[0]) if title else ""
                    href = item.xpath('./@href')[0] if item.xpath('./@href') else ""
                    vid = re.search(r'v=(\d+)', href)
                    vid = vid.group(1) if vid else href
                    if vid in self.seen_ids: continue
                    self.seen_ids.add(vid)
                    pic = item.xpath('.//img/@src') or item.xpath('.//img/@data-original')
                    pic = fix_url(pic[0], self.host) if pic else ""
                    hits = item.xpath('.//span[contains(@class,"vod_hits")]/text()')
                    remarks = clean_text(hits[0]) if hits else ""
                    result["list"].append({
                        "vod_id": vid,
                        "vod_name": title,
                        "vod_pic": pic,
                        "vod_remarks": remarks
                    })
                except Exception as e:
                    continue
            pc = re.search(r'page[=:](\d+)', html_text) or re.search(r'共\s*(\d+)\s*页', html_text)
            if pc: result["pagecount"] = int(pc.group(1))
            else: result["pagecount"] = int(pg) + 1 if len(items) >= 24 else int(pg)
            return result
        except Exception as e:
            return {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}
