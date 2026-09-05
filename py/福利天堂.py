#!/usr/bin/python
# -*- coding: utf-8 -*-
import re, json, requests
from urllib.parse import quote
from lxml import etree
from base.spider import Spider

class Spider(Spider):
    def getName(self): return "福利天堂"
    def init(self, extend=""):
        self.host = "https://ph838.qians.cfd"
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Referer": self.host + "/"}
        self.categories = [{"type_id":"1","type_name":"偷拍"},{"type_id":"6","type_name":"国产"},{"type_id":"3","type_name":"韩国"},{"type_id":"4","type_name":"无码"},{"type_id":"5","type_name":"动漫"},{"type_id":"7","type_name":"中文"},{"type_id":"8","type_name":"91"},{"type_id":"9","type_name":"欧美"},{"type_id":"10","type_name":"有码"},{"type_id":"11","type_name":"强奸"},{"type_id":"12","type_name":"制服"},{"type_id":"13","type_name":"主播"},{"type_id":"17","type_name":"明星"},{"type_id":"14","type_name":"抖音"},{"type_id":"18","type_name":"女优"},{"type_id":"15","type_name":"调教"},{"type_id":"16","type_name":"少女"}]
    def _get(self, url):
        try:
            r = requests.get(url, headers=self.headers, timeout=15)
            r.encoding = r.apparent_encoding or "utf-8"
            return r.text
        except requests.RequestException:
            return ""
    def _fix(self, u): return "https:" + u if u and u.startswith("//") else self.host + u if u and u.startswith("/") else u or ""
    def _txt(self, x): return re.sub(r"\s+", " ", "".join(x).strip())
    def _parse_list(self, html):
        tree = etree.HTML(html or "")
        items = tree.xpath('//a[contains(@class,"thumbnail") and contains(@href,"/vod/detail/id/")]') or tree.xpath('//a[contains(@href,"/vod/detail/id/") and .//img]') or tree.xpath('//li[.//a[contains(@href,"/vod/detail/id/")]]//a[contains(@href,"/vod/detail/id/")]')
        data, seen = [], set()
        for a in items:
            href = a.get("href", "")
            m = re.search(r"/vod/detail/id/(\d+)\.html", href)
            if not m or m.group(1) in seen: continue
            seen.add(m.group(1))
            img = a.xpath(".//img")
            pic = self._fix(img[0].get("data-original") or img[0].get("data-src") or img[0].get("data-lazyload") or img[0].get("src", "")) if img else ""
            name = a.get("title", "") or (img[0].get("alt", "") if img else "") or self._txt(a.xpath(".//text()"))
            if name: data.append({"vod_id": m.group(1), "vod_name": name, "vod_pic": pic})
        return data
    def homeContent(self, filter):
        html = self._get(self.host + "/")
        return {"class": self.categories, "list": self._parse_list(html), "filters": {}}
    def categoryContent(self, tid, pg, filter, extend):
        pg = str(pg or "1")
        url = f"{self.host}/vod/type/id/{tid}.html" if pg == "1" else f"{self.host}/vod/type/id/{tid}/page/{pg}.html"
        data = self._parse_list(self._get(url))
        return {"page": int(pg), "pagecount": 999 if data else int(pg), "limit": 24, "total": 9999 if data else 0, "list": data}
    def detailContent(self, ids):
        result = []
        for vid in ids:
            html = self._get(f"{self.host}/vod/detail/id/{vid}.html")
            tree = etree.HTML(html or "")
            name = self._txt(tree.xpath('//div[contains(@class,"breadcrumbs")]//span/text()')) or self._txt(tree.xpath('//div[contains(@class,"detail-info")]//li[1]/text()')) or vid
            pic = self._fix(self._txt(tree.xpath('//div[contains(@class,"detail-poster")]//img/@data-original')) or self._txt(tree.xpath('//div[contains(@class,"detail-poster")]//img/@data-src')) or self._txt(tree.xpath('//div[contains(@class,"detail-poster")]//img/@src')))
            tabs = tree.xpath('//ul[contains(@class,"ff-playurl-tab")]//li')
            lists = tree.xpath('//ul[contains(@class,"detail-play-list")]') or tree.xpath('//ul[contains(@class,"ff-playurl")]')
            sources, urls = [], []
            for i, ul in enumerate(lists):
                s = self._txt(tabs[i].xpath(".//text()")) if i < len(tabs) else f"线路{i+1}"
                eps = []
                for a in ul.xpath('.//a[contains(@href,"/vod/play/")]'):
                    t = self._txt(a.xpath(".//text()")) or a.get("title", "") or "播放"
                    u = self._fix(a.get("href", ""))
                    if u: eps.append(f"{t}${u}")
                if eps: sources.append(s or f"线路{i+1}"); urls.append("#".join(eps))
            if not urls:
                m = re.search(r'(/vod/play/id/%s/sid/\d+/nid/\d+\.html)' % vid, html)
                if m: sources.append("默认"); urls.append("在线播放$" + self._fix(m.group(1)))
            result.append({"vod_id": vid, "vod_name": name, "vod_pic": pic, "vod_play_from": "$$$".join(sources), "vod_play_url": "$$$".join(urls)})
        return {"list": result}
    def searchContent(self, key, quick, pg="1"):
        html = self._get(f"{self.host}/vod/search.html?wd={quote(key)}")
        return {"list": self._parse_list(html), "page": int(pg or "1")}
    def playerContent(self, flag, id, vipFlags):
        url = id if id.startswith("http") else self._fix(id)
        return {"parse": 1, "url": url, "header": self.headers}