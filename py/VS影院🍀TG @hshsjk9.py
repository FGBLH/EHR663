#!/usr/bin/python
# -*- coding: utf-8 -*-
import re, json, time
from urllib.parse import quote, unquote
try:
    import requests
    from lxml import etree
except:
    requests = None
    import urllib.request as _ur
try:
    from base.spider import Spider as _Base
except:
    _Base = object

BASE = "https://www.vssdy.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
H = {"User-Agent": UA, "Referer": BASE + "/"}
CATS = [("电视剧-中国大陆-------0-24.html", "大陆剧"), ("电视剧-台湾-------0-24.html", "港台剧"), ("电视剧-美国-------0-24.html", "欧美剧"), ("电视剧-日本-------0-24.html", "日韩剧"), ("电视剧-其他-------0-24.html", "海外剧"), ("电影---动作-----0-24.html", "动作片"), ("电影---喜剧-----0-24.html", "喜剧片"), ("电影---爱情-----0-24.html", "爱情片"), ("电影---科幻-----0-24.html", "科幻片"), ("电影---恐怖-----0-24.html", "恐怖片"), ("电影---灾难-----0-24.html", "灾难片"), ("电影---战争-----0-24.html", "战争片"), ("电影---剧情-----0-24.html", "剧情片"), ("综艺-中国大陆-------0-24.html", "内地综艺"), ("综艺-台湾-------0-24.html", "港台综艺"), ("综艺-日本-------0-24.html", "日韩综艺"), ("综艺-美国-------0-24.html", "欧美综艺"), ("动漫-日本-------0-24.html", "日韩动漫"), ("动漫-中国大陆-------0-24.html", "国产动漫"), ("动漫-美国-------0-24.html", "欧美动漫"), ("动漫-台湾-------0-24.html", "港台动漫")]


class Spider(_Base):
    def init(self, extend=""):
        self.host = BASE
        if requests:
            self.s = requests.Session()
            self.s.headers.update(H)

    def getName(self):
        return "VS影院"

    def _get(self, url):
        for _ in range(3):
            try:
                if requests:
                    r = self.s.get(url, timeout=15)
                    if r.text:
                        r.encoding = "utf-8"
                        return r.text
                else:
                    req = _ur.Request(url, headers=H)
                    with _ur.urlopen(req, timeout=15) as rp:
                        return rp.read().decode("utf-8", "ignore")
            except:
                pass
        return ""

    def _list(self, html):
        try:
            tree = etree.HTML(html)
        except:
            return []
        if tree is None:
            return []
        out, seen = [], set()
        for a in tree.xpath("//a[contains(@class,'stui-vodlist__thumb')]"):
            m = re.search(r"/resource/(\d+)\.html", a.get("href", ""))
            if not m or m.group(1) in seen:
                continue
            seen.add(m.group(1))
            out.append({"vod_id": m.group(1), "vod_name": (a.get("title") or "").strip(), "vod_pic": a.get("data-original") or "", "vod_remarks": "".join(a.xpath('.//span[contains(@class,"pic-text")]/text()')).strip()})
        return out

    def homeContent(self, filter):
        return {"class": [{"type_id": t, "type_name": n} for t, n in CATS], "list": self._list(self._get(BASE + "/catalog/--------0-24.html")), "filters": {}}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        lst = self._list(self._get(f"{BASE}/catalog/{quote(tid)}?order=&page={pg - 1}&size=28"))
        return {"page": pg, "pagecount": 9999, "limit": 28, "total": 99999, "list": lst}

    def detailContent(self, ids):
        vid = ids[0]
        html = self._get(f"{BASE}/resource/{vid}.html")
        try:
            tree = etree.HTML(html)
        except:
            return {"list": []}
        if tree is None or not html:
            return {"list": []}
        name = "".join(tree.xpath("//h1/text()")).strip()
        pic = "".join(tree.xpath("//div[contains(@class,'stui-content__thumb')]//a/@data-original | //div[contains(@class,'stui-content__thumb')]//img/@data-original | //div[contains(@class,'stui-content__thumb')]//a/@href[contains(.,'.webp') or contains(.,'.jpg') or contains(.,'.png')]")).strip()
        if pic and not pic.startswith("http"):
            pic = BASE + pic
        info = " ".join(t.strip() for t in tree.xpath("//p[contains(@class,'data')]//text()") if t.strip())
        year = re.search(r"年份：\s*(\d{4})", info)
        srcs, eps = [], []
        for tab in tree.xpath("//ul[contains(@class,'ff-playurl-tab-type')]//li/a"):
            label = "".join(tab.xpath(".//text()")).strip()
            target = tab.get("data-target", "").lstrip(".")
            items = []
            for ul in tree.xpath("//ul[contains(@class,'stui-content__playlist')]"):
                if target and target in (ul.get("class") or "").split():
                    for a in ul.xpath(".//a"):
                        m = re.search(r"/play/(\d+)-(\d+)-(\d+)\.html", a.get("href", ""))
                        if m:
                            items.append(f'{(a.get("title") or "".join(a.xpath(".//text()"))).strip()}${m.group(1)}-{m.group(2)}-{m.group(3)}')
            if items:
                srcs.append(label or f"线路{len(srcs) + 1}")
                eps.append("#".join(items))
        if not srcs:
            items = []
            for a in tree.xpath("//ul[contains(@class,'stui-content__playlist')]//a"):
                m = re.search(r"/play/(\d+)-(\d+)-(\d+)\.html", a.get("href", ""))
                if m:
                    items.append(f'{(a.get("title") or "".join(a.xpath(".//text()"))).strip()}${m.group(1)}-{m.group(2)}-{m.group(3)}')
            if items:
                srcs.append("在线播放")
                eps.append("#".join(items))
        return {"list": [{"vod_id": vid, "vod_name": name, "vod_pic": pic, "vod_year": year.group(1) if year else "", "vod_play_from": "$$$".join(srcs), "vod_play_url": "$$$".join(eps)}]}

    def searchContent(self, key, quick, pg="1"):
        pg = int(pg or 1)
        url = f"{BASE}/search?searchword={quote(key)}"
        if pg > 1:
            url += f"&page={pg - 1}&size=24"
        return {"list": self._list(self._get(url)), "page": pg}

    def playerContent(self, flag, id, vipFlags):
        try:
            vid, pid, epid = str(id).split("-")
        except:
            return {"parse": 0, "url": ""}
        t = int(time.time())
        k = t * (t % 16) + t * (t % 32) + t * (t % 64) + 198664
        data = self._get(f"{BASE}/gpyj?vid={vid}&pid={pid}&epid={epid}&t={t}&k={k}").strip()
        url = ""
        try:
            out, L = "", len(data)
            for i in range(0, L, 2):
                out = chr((int(data[i:i + 2], 16) + 0x100000 - 871 - (L // 2 - 1 - i // 2)) % 256) + out
            m = re.search(r"[?&]url=([^&]+)", out)
            if m:
                url = unquote(m.group(1))
            elif re.search(r"https?://[^\s'\"]+\.(?:m3u8|mp4)", out):
                url = re.search(r"https?://[^\s'\"]+\.(?:m3u8|mp4)", out).group(0)
        except:
            pass
        return {"parse": 0, "url": url, "header": json.dumps({"User-Agent": UA, "Referer": BASE + "/"})}
