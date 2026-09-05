# -*- coding: utf-8 -*-
import sys
import re
import json
import base64
import threading
from urllib.parse import urljoin, quote, unquote

sys.path.append('..')
try:
    from base.spider import Spider
except ImportError:
    class Spider:
        def fetch(self, url, headers=None, **kw):
            import requests as rq
            kw.pop('timeout', None)
            r = rq.get(url, headers=headers, timeout=15, **kw)
            r.encoding = 'utf-8'
            return r

import requests as _rq
_SES = _rq.Session()
_LK = threading.Lock()

try:
    from Crypto.Cipher import AES as _AES
    from Crypto.Util.Padding import unpad as _unpad
except ImportError:
    _AES = None

HOST = "https://chabeihuvideo.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
_KEY = [""]
_IMG = {}

CATEGORIES = {
    "/dianying/zuixindianying": "电影",
    "/lianxuju/lianxujuremenjuji": "连续剧",
    "/duanju/duanjuremenduanju": "短剧",
    "/zongyi/guochanzongyi": "综艺",
    "/jilupiantop/jilupianremenjilu": "纪录片",
    "/dongman/dongmanremendongman": "动漫",
    "/dianyingjieshuo/dianyingjieshuojieshuo": "解说",
}


class Spider(Spider):
    def init(self, extend=""):
        global HOST
        try:
            r = _SES.get(HOST, headers={"User-Agent": UA}, verify=False, timeout=(3050, 15000))
            if hasattr(r, 'url') and r.url and r.url != HOST.rstrip("/"):
                HOST = r.url.rstrip("/")
        except:
            pass

    def homeContent(self, filter=False):
        r = {"class": [], "list": []}
        for k, v in CATEGORIES.items():
            r["class"].append({"type_id": k, "type_name": v})
        try:
            resp = _SES.get(HOST, headers={"User-Agent": UA}, verify=False, timeout=(3050, 15000))
            html = resp.text if hasattr(resp, 'text') else str(resp)
            r["list"] = self._items(html)
        except:
            pass
        return r

    def homeVideoContent(self):
        try:
            r = _SES.get(HOST, headers={"User-Agent": UA}, verify=False, timeout=(3050, 15000))
            html = r.text if hasattr(r, 'text') else str(r)
            return {"list": self._items(html)}
        except:
            return {"list": []}

    def categoryContent(self, tid, pg=1, filter=False, extend=""):
        pn = 1
        try:
            pn = max(int(str(pg)), 1)
        except:
            pass
        cat = str(tid)
        try:
            url = f"{HOST}{cat}" + (f"/page/{pn}" if pn > 1 else "")
            r = _SES.get(url, headers={"User-Agent": UA}, verify=False, timeout=(3050, 25000))
            html = r.text if hasattr(r, 'text') else str(r)
            txt = self._rsc(html)
            items = self._items(html, txt)
            return {
                "page": pn,
                "pagecount": self._pagecount(html, pn, txt),
                "limit": 12,
                "total": len(items),
                "list": items
            }
        except:
            return {"page": pn, "pagecount": 1, "limit": 12, "total": 0, "list": []}

    def _rsc(self, html):
        txt = ""
        for seg in re.findall(r'self\.__next_f\.push\(\[1,\s*"((?:[^"\\]|\\.)*)"\]\)', html):
            try:
                txt += json.loads('"' + seg + '"')
            except:
                pass
        return txt

    def _img_key(self):
        if _KEY[0]:
            return _KEY[0]
        with _LK:
            if _KEY[0]:
                return _KEY[0]
            try:
                r = _SES.get(f"{HOST}/fronted/dictionary/by_key?key=img_key", headers={"User-Agent": UA}, verify=False, timeout=10000)
                d = json.loads(r.text)
                _KEY[0] = d["data"][0]["value"]
            except:
                pass
        return _KEY[0]

    def _ppic(self, url):
        if not url or ".bnc" not in url:
            return url
        if url in _IMG:
            return _IMG[url]
        try:
            r = _SES.get(url, headers={"User-Agent": UA}, verify=False, timeout=(3050, 8000))
            data = r.content
            key = self._img_key()
            dec = b""
            if key and _AES and data and len(data) % 16 == 0:
                dec = _unpad(_AES.new(key.encode(), _AES.MODE_ECB).decrypt(data), 16)
            if not dec:
                return url
            mime = "image/jpeg"
            if dec[:4] == b"\x89PNG":
                mime = "image/png"
            elif dec[:3] == b"GIF":
                mime = "image/gif"
            elif dec[:4] == b"RIFF":
                mime = "image/webp"
            uri = "data:%s;base64,%s" % (mime, base64.b64encode(dec).decode())
            _IMG[url] = uri
            return uri
        except:
            return url

    def _pics(self, urls):
        if not urls:
            return
        self._img_key()
        urls = urls[:16]
        self._ppic(urls[0])
        ts = []
        for u in urls[1:]:
            if u not in _IMG:
                ts.append(threading.Thread(target=self._ppic, args=(u,)))
        for t in ts:
            t.start()
        for t in ts:
            t.join()

    def detailContent(self, ids):
        if isinstance(ids, list):
            vid = ids[0] if ids else ""
        else:
            vid = str(ids) if ids else ""
        if not vid:
            return {"list": []}
        vid = unquote(unquote(vid))
        url = vid if vid.startswith("http") else urljoin(HOST, vid)
        try:
            r = _SES.get(url, headers={"User-Agent": UA}, verify=False, timeout=(3050, 25000))
            h = r.text if hasattr(r, 'text') else str(r)
        except:
            return {"list": []}

        d = {
            "vod_id": vid, "vod_name": "", "vod_pic": "", "vod_year": "",
            "vod_area": "", "vod_class": "", "vod_director": "", "vod_actor": "",
            "vod_content": "", "vod_remarks": "", "vod_play_from": "", "vod_play_url": ""
        }

        # 标题
        tn = re.search(r'property="og:title"[^>]*content="([^"]*)"', h)
        if tn:
            d["vod_name"] = tn.group(1).strip()

        # 封面
        p = re.search(r'property="og:image"[^>]*content="([^"]*)"', h)
        if not p:
            p = re.search(r'<img[^>]*(?:src|data-original)="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"', h, re.I)
        if p:
            d["vod_pic"] = self._ppic(p.group(1))

        # 简介
        dm = re.search(r'property="og:description"[^>]*content="([^"]*)"', h)
        if dm:
            d["vod_content"] = dm.group(1).strip()[:500]

        # RSC数据 → project_id/resource_id → detail_list_v2 全集
        pf, pu = [], []
        try:
            txt = self._rsc(h)
            pid = ""
            m = re.search(r'"project_id":"([^"]+)"', txt)
            if m:
                pid = m.group(1)
            rid = ""
            m = re.search(r'"resource_id":"([^"]+)"', txt)
            if m:
                rid = m.group(1)
            eps = []
            if pid and rid:
                try:
                    r2 = _SES.get(f"{HOST}/fronted/sys_video_resource/detail_list_v2?project_id={pid}&resource_id={rid}", headers={"User-Agent": UA}, verify=False, timeout=(3050, 15000))
                    data = json.loads(r2.text) if hasattr(r2, 'text') else json.loads(str(r2))
                    for ep in data.get("data", {}).get("video_details") or []:
                        u = ep.get("url") or ep.get("preview") or ""
                        if u:
                            eps.append(f"{ep.get('name') or ''}${u}")
                except:
                    pass
            if not eps:
                m = re.search(r'"mv_url":"(https?://[^"]+)"', txt)
                if m:
                    eps.append("1$" + m.group(1))
            if eps:
                pf.append("茶杯狐")
                pu.append("#".join(eps))
        except:
            pass

        if pf:
            d["vod_play_from"] = "$$$".join(pf)
            d["vod_play_url"] = "$$$".join(pu)

        return {"list": [d]}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            pn = 1
            try:
                pn = int(str(pg))
            except:
                pass
            items = []
            for p in (f"{HOST}/search?q={quote(key)}", f"{HOST}/search?wd={quote(key)}"):
                try:
                    r = _SES.get(p, headers={"User-Agent": UA}, verify=False, timeout=55000)
                    h = r.text if hasattr(r, 'text') else str(r)
                    items = self._items(h)
                    if items:
                        break
                except:
                    continue
            return {"list": items, "page": pn}
        except:
            return {"list": []}

    def playerContent(self, flag, id, vipFlags=None):
        url = str(id) if id else str(flag)
        if url.startswith("http") and (".m3u8" in url or ".mp4" in url):
            return {"url": url}
        return {"url": url if url.startswith("http") else urljoin(HOST, url)}

    def localProxy(self, param):
        pass

    def _pagecount(self, html, current_page=1, txt=None):
        if txt is None:
            txt = self._rsc(html)
        m = re.search(r'"totalPages":(\d+)', txt)
        if m:
            return max(int(m.group(1)), current_page)
        pages = re.findall(r'/page/(\d+)', html)
        max_page = current_page
        for p in pages:
            try:
                n = int(p)
                if n > max_page:
                    max_page = n
            except:
                pass
        return max_page

    def _items(self, html, txt=None):
        items, seen = [], set()
        pics = {}
        if txt is None:
            txt = self._rsc(html)
        for m in re.finditer(r'"id":"([0-9a-f]{20,40})"[^}]{0,400}?"cover_image":"(https?://[^"]+)"', txt):
            pics[m.group(1)] = m.group(2)
        self._pics(list(pics.values()))
        for m in re.finditer(r'<a[^>]*title="([^"]*)"[^>]*href="(/video-player/[^"]+)"[^>]*>', html):
            vid = m.group(2)
            if vid in seen:
                continue
            name = m.group(1).strip()
            if not name or len(name) > 100:
                continue
            cover = ""
            if vid.count("/") >= 2:
                cover = pics.get(vid.split("/")[2], "")
            seen.add(vid)
            items.append({
                "vod_id": vid,
                "vod_name": name[:50],
                "vod_pic": _IMG.get(cover, cover),
                "vod_remarks": "",
            })
        for m in re.finditer(r'"id":"([0-9a-f]{20,40})","is_ad":false,"resource_id":"[^"]*","detail_id":"","name":"((?:[^"\\]|\\.)*)","cat_id":"9"[^}]{0,800}?"cover_image":"(https?://[^"]+)"', txt):
            hid, nm, cov = m.group(1), m.group(2), m.group(3)
            try:
                nm = json.loads('"' + nm + '"')
            except:
                pass
            vid = "/video-player/" + hid + "/" + quote(nm, safe='')
            if vid in seen:
                continue
            seen.add(vid)
            items.append({
                "vod_id": vid,
                "vod_name": nm[:50],
                "vod_pic": _IMG.get(cov, cov),
                "vod_remarks": "",
            })
        return items
