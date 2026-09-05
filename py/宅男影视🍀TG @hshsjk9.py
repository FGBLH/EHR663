# -*- coding: utf-8 -*-
import sys
import re
import json
import ssl
import urllib.request
from urllib.parse import quote

sys.path.append('..')
try:
    from base.spider import Spider
except ImportError:
    class Spider:
        pass

HOSTS = ["https://zndy.top", "https://www.znys.top", "https://znys.top"]
HOST = "https://zndy.top"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
HOT_API = "https://cj.10010888.xyz/api.php/provide/vod/"
SHORT_API = "https://bf.xoxowin86cisyap.com/api.php/provide/vod/"
LZ_API = "https://cj.lziapi.com/api.php/provide/vod/"
CATEGORIES = {
    "1": "电影", "2": "电视剧", "4": "动漫", "3": "综艺",
    "L52": "AI漫剧",
    "s68": "反转爽文", "s71": "都市脑洞", "s72": "古装仙侠", "s67": "现代言情", "s66": "穿越年代",
}
JIEXI_LIST = [
    ("冰豆解析", "https://bd.jx.cn"),
    ("789解析", "https://jiexi.789jiexi.com"),
]

class Spider(Spider):
    def _req(self, url, data=None):
        try:
            body = json.dumps(data).encode() if data is not None else None
            req = urllib.request.Request(url, data=body, method="POST" if data is not None else "GET")
            req.add_header("User-Agent", UA)
            if data is not None:
                req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=15, context=ssl._create_unverified_context()) as r:
                return json.loads(r.read().decode("utf-8", "ignore"))
        except:
            return {}

    def init(self, extend=""):
        global HOST, HOT_API, SHORT_API, CATEGORIES
        for h in HOSTS:
            d = self._req(h + "/api/web").get("data")
            if not d:
                continue
            HOST = h
            cats = {}
            hs = [l for l in str(d.get("hot_db", "")).split("\n") if l.strip()]
            ss = [l for l in str(d.get("short", "")).split("\n") if l.strip()]
            if hs:
                HOT_API = hs[0].strip()
                for line in hs[1:]:
                    for pair in line.split("|"):
                        if "," in pair:
                            n, t = pair.split(",", 1)
                            cats[t.strip()] = n.strip()
            if ss:
                SHORT_API = ss[0].strip()
                for line in ss[1:]:
                    for pair in line.split("|"):
                        if "," in pair:
                            n, t = pair.split(",", 1)
                            cats["s" + t.strip()] = n.strip()
            if cats:
                cats["L52"] = "AI漫剧"
                CATEGORIES = cats
            return

    def _post(self, path, data):
        return self._req(HOST + path, data)

    def _list(self, api, tid, pg, prefix=""):
        r = self._post("/api/hot", {"type": str(tid), "page": int(pg), "api_url": api})
        return [{"vod_id": prefix + str(x["id"]), "vod_name": x.get("title", ""), "vod_pic": x.get("cover", ""), "vod_remarks": x.get("vod_remarks", "")} for x in r.get("data", [])]

    def homeContent(self, filter=False):
        return {"class": [{"type_id": k, "type_name": v} for k, v in CATEGORIES.items()], "list": []}

    def homeVideoContent(self):
        return {"list": []}

    def _lz_t(self, t, pg, drop_dm=False):
        r = self._req(f"{LZ_API}?ac=videolist&t={t}&pg={pg}")
        items = [{"vod_id": "L" + str(x["vod_id"]), "vod_name": x.get("vod_name", ""), "vod_pic": x.get("vod_pic", ""), "vod_remarks": x.get("vod_remarks", "")} for x in r.get("list", []) if not (drop_dm and "动态漫" in str(x.get("vod_name", "")))]
        return items, int(r.get("pagecount") or pg)

    def _lz_page(self, pg):
        items, pcs = [], []
        for t in (29, 30):
            it, pc = self._lz_t(t, pg, True)
            items += it
            pcs.append(pc)
        return {"page": pg, "pagecount": max(pcs), "limit": 40, "total": len(items), "list": items}

    def _lz_single(self, t, pg):
        items, pc = self._lz_t(t, pg, False)
        return {"page": pg, "pagecount": pc, "limit": 20, "total": len(items), "list": items}

    def categoryContent(self, tid, pg=1, filter=False, extend=""):
        try:
            pn = max(int(str(pg)), 1)
        except:
            pn = 1
        cat = str(tid)
        if cat == "4":
            return self._lz_page(pn)
        if cat == "L52":
            return self._lz_single(52, pn)
        if cat.startswith("s"):
            api, t, prefix = SHORT_API, cat[1:], "s"
        else:
            api, t, prefix = HOT_API, cat, ""
        items = self._list(api, t, pn, prefix)
        return {"page": pn, "pagecount": pn + 1, "limit": 20, "total": len(items), "list": items}

    def _main_official(self, name):
        try:
            r = self._req(f"{HOT_API}?ac=videolist&wd={quote(name, safe='')}")
            for x in r.get("list", []):
                if x.get("vod_name") == name:
                    rd = self._req(f"{HOT_API}?ac=detail&ids={x['vod_id']}")
                    if rd.get("list"):
                        d = rd["list"][0]
                        fs = str(d.get("vod_play_from", "")).split("$$$")
                        us = str(d.get("vod_play_url", "")).split("$$$")
                        if fs and len(fs) == len(us):
                            off = {k: v for k, v in zip(fs, us) if v and not re.search(r'\.(m3u8|mp4|flv|mkv)(\?|$)', str(v), re.I)}
                            if off:
                                return off
        except Exception:
            pass
        return {}

    def _jx_lines(self, u, force=False):
        eps = str(u).split("$$$")[0].split("#")
        out = []
        for name, base in JIEXI_LIST:
            segs = []
            for ep in eps:
                if "$" in ep:
                    n, url = ep.split("$", 1)
                else:
                    n, url = "", ep
                if not force and re.search(r'\.(m3u8|mp4|flv|mkv)(\?|$)', url, re.I):
                    segs.append(ep)
                else:
                    jx = base + quote(url, safe='') if "url=" in base else base + "?url=" + quote(url, safe='')
                    segs.append(f"{n}${jx}" if n else jx)
            out.append("#".join(segs))
        return out

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) and ids else (str(ids) if ids else "")
        if not vid:
            return {"list": []}
        if str(vid).startswith("L"):
            r = self._req(f"{LZ_API}?ac=detail&ids={str(vid)[1:]}")
            if r.get("list"):
                d = r["list"][0]
                f = str(d.get("vod_play_from", ""))
                u = str(d.get("vod_play_url", ""))
                if f and u:
                    off = self._main_official(str(d.get("vod_name", "")))
                    if off:
                        d["vod_play_from"] = f + "$$$" + "$$$".join(off.keys())
                        d["vod_play_url"] = u + "$$$" + "$$$".join(off.values())
                return {"list": [d]}
            return {"list": []}
        if str(vid).startswith("s"):
            api, real = SHORT_API, str(vid)[1:]
        else:
            api, real = HOT_API, str(vid)
        r = self._post("/api/detail", {"api": api, "ids": real})
        d = r.get("data", {})
        if d:
            f = str(d.get("vod_play_from", ""))
            u = str(d.get("vod_play_url", ""))
            if f and u:
                eps = u.split("$$$")[0].split("#")
                need = any(not re.search(r'\.(m3u8|mp4|flv|mkv)(\?|$)', (ep.split("$", 1)[1] if "$" in ep else ep), re.I) for ep in eps)
                if need:
                    d["vod_play_from"] = f + "$$$" + "$$$".join(j[0] for j in JIEXI_LIST)
                    d["vod_play_url"] = u + "$$$" + "$$$".join(self._jx_lines(u))
        return {"list": [d] if d else []}

    def searchContent(self, key, quick=False, pg="1"):
        r = self._post("/api/search", {"api": HOT_API, "keyword": key, "page": 1})
        return {"list": [{"vod_id": str(x.get("vod_id", "")), "vod_name": x.get("vod_name", ""), "vod_pic": x.get("vod_pic", ""), "vod_remarks": x.get("vod_remarks", "")} for x in r.get("data", [])]}

    def playerContent(self, flag, id, vipFlags=None):
        url = str(id) if id else str(flag)
        if re.search(r'\.(m3u8|mp4|flv|mkv)(\?|$)', url, re.I):
            return {"url": url}
        if url.startswith("http"):
            return {"parse": 1, "url": url}
        return {"url": ""}

    def localProxy(self, param):
        pass
