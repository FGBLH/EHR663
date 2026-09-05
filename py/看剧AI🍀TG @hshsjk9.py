# -*- coding: utf-8 -*-
import sys
import json
import time
import hmac
import hashlib
import secrets
import urllib.parse
import math

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

HOSTS = ["https://kanju.ai", "https://kanju20.com"]
KEY = "557d0e4ae929f438da6bd84412374e6086b8af09b3fed54bf22601d5bf8c54a0"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
YJ = "https://zy.baipiaozhe.com/v1/playback/yjm3u8/%s.m3u8"
CLIENT = {
    "x-ai-movie-client-name": "dianyingtiantang-frontend",
    "x-ai-movie-client-version": "1.0.0",
    "x-ai-movie-build-version": "dianyingtiantang-v2026.08.11.1-8cbb0b0d407e-672e67d62528",
    "x-ai-movie-protocol-version": "2026-07-05.library-v2.playback-v1",
}

CATEGORIES = {
    "movie": "电影", "series": "电视剧", "short_drama": "短剧",
    "anime": "动漫", "variety": "综艺", "documentary": "纪录片",
}

GENRES = {
    "movie": ["动作", "冒险", "剧情", "喜剧", "奇幻", "古装", "家庭", "科幻"],
    "series": ["动作", "冒险", "剧情", "刑侦", "古装", "历史", "台剧", "悬疑"],
    "short_drama": ["剧情", "动作", "反转爽剧", "古装仙侠", "喜剧", "女频恋爱", "家庭", "年代"],
    "anime": ["热血", "冒险", "奇幻", "日本动漫", "国产动漫", "爆笑", "武侠", "儿童"],
    "variety": ["大陆综艺", "真人秀", "情感", "爱情", "社交观察"],
    "documentary": ["历史", "纪录片"],
}


class Spider(Spider):
    def init(self, extend=""):
        for i, h in enumerate(HOSTS):
            try:
                r = self.fetch(h, headers={"User-Agent": UA}, timeout=15000)
                if getattr(r, 'status_code', None) == 200:
                    self._hi = i
                    break
            except Exception:
                continue
        else:
            self._hi = 0
        return ""

    def _host(self):
        return HOSTS[getattr(self, '_hi', 0)]

    def _sign(self, method, path):
        ts = str(int(time.time() * 1000))
        nonce = secrets.token_hex(16)
        msg = "%s\n%s\n%s\n%s" % (method, path, ts, nonce)
        sig = hmac.new(KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()
        return ts, nonce, sig

    def _req(self, method, path, body=None):
        for _ in range(len(HOSTS)):
            host = self._host()
            try:
                ts, nonce, sig = self._sign(method, path)
                hdrs = {
                    "User-Agent": UA, "Accept": "application/json",
                    "Referer": host + "/",
                    "x-ai-movie-timestamp": ts, "x-ai-movie-nonce": nonce,
                    "x-ai-movie-signature": sig,
                }
                hdrs.update(CLIENT)
                import requests as rq
                if body is not None:
                    hdrs["Content-Type"] = "application/json"
                    r = rq.post(host + path, json=body, headers=hdrs, timeout=10)
                else:
                    r = rq.get(host + path, headers=hdrs, timeout=10)
                if r.status_code in (200, 201):
                    return r.json()
            except Exception:
                pass
            self._hi = (self._hi + 1) % len(HOSTS)
            time.sleep(1)
        return {}

    def _vod(self, c):
        return {
            "vod_id": c.get("id", ""),
            "vod_name": c.get("title", ""),
            "vod_pic": c.get("poster_url", ""),
            "vod_remarks": c.get("remarks") or str(c.get("year") or ""),
            "vod_year": c.get("year") or "",
            "vod_area": c.get("area") or "",
            "vod_actor": "/".join((c.get("actors") or [])[:3]),
            "vod_director": "/".join((c.get("directors") or [])[:2]),
        }

    def homeContent(self, filter=False):
        cls = []
        for k, v in CATEGORIES.items():
            cls.append({
                "type_id": k, "type_name": v,
                "subs": [{"type_id": "%s:%s" % (k, g), "type_name": g} for g in GENRES[k]],
            })
        return {"class": cls, "list": []}

    def homeVideoContent(self):
        now = time.time()
        if getattr(self, "_hv_t", 0) > now - 300 and getattr(self, "_hv", None):
            return self._hv
        seen, lst = set(), []
        paths = ["/v1/feed/home", "/v1/browse/catalog?kind=movie&sort=trending&window=day&page=1&limit=40", "/v1/browse/catalog?kind=series&sort=trending&window=day&page=1&limit=40"]
        for p in paths:
            j = self._req("GET", p)
            for s in (j.get("sections") or []):
                for c in (s.get("cards") or []):
                    v = self._vod(c)
                    if v["vod_id"] and v["vod_id"] not in seen:
                        seen.add(v["vod_id"])
                        lst.append(v)
            for c in (j.get("cards") or []):
                v = self._vod(c)
                if v["vod_id"] and v["vod_id"] not in seen:
                    seen.add(v["vod_id"])
                    lst.append(v)
        self._hv, self._hv_t = {"list": lst}, now
        return self._hv

    def categoryContent(self, tid, pg=1, filter=False, extend=""):
        pn = 1
        try:
            pn = max(int(str(pg)), 1)
        except Exception:
            pass
        cat, gen = str(tid), ""
        if ":" in cat:
            cat, gen = cat.split(":", 1)
        if cat not in CATEGORIES:
            cat = "movie"
        if gen:
            path = "/v1/browse/catalog?kind=%s&genre=%s&page=%d&limit=40" % (cat, urllib.parse.quote(gen), pn)
        else:
            path = "/v1/browse/catalog?kind=%s&page=%d&limit=40" % (cat, pn)
        j = self._req("GET", path)
        cards = j.get("cards") or []
        total = (j.get("pagination") or {}).get("total", 0) or 0
        return {"page": pn, "pagecount": max(math.ceil(total / 40), 1), "limit": 40, "total": total, "list": [self._vod(c) for c in cards]}

    def detailContent(self, ids):
        if isinstance(ids, list):
            vid = ids[0] if ids else ""
        else:
            vid = str(ids) if ids else ""
        vid = vid.split("/")[0]
        if not vid:
            return {"list": []}
        d = self._req("GET", "/v1/catalog/%s" % vid)
        eps = d.get("episodes") or []
        urls = []
        for e in eps:
            t = e.get("token")
            if t:
                urls.append("%s$%s" % (e.get("title") or "第%s集" % (e.get("number") or len(urls) + 1), t))
        play_from, play_url = "kanju", "#".join(urls)
        if eps and urls:
            tok0 = eps[0].get("token")
            if tok0:
                rj = self._req("GET", "/v1/playback/resolve/%s" % tok0)
                names = [(l.get("provider_name") or "") for l in (rj.get("line_options") or [])]
                names = [n for n in names if n][:8]
                if names:
                    play_from = "$$$".join(names)
                    play_url = "$$$".join([play_url] * len(names))
        return {"list": [{
            "vod_id": vid, "vod_name": d.get("title", ""), "vod_pic": d.get("poster_url", ""),
            "vod_year": d.get("year", ""), "vod_area": d.get("area", ""),
            "vod_class": "/".join((d.get("genres") or [])[:3]),
            "vod_director": "/".join((d.get("directors") or [])[:2]),
            "vod_actor": "/".join((d.get("actors") or [])[:3]),
            "vod_content": d.get("description") or "",
            "vod_remarks": d.get("status") or d.get("remarks") or "",
            "vod_play_from": play_from, "vod_play_url": play_url,
        }]}

    def searchContent(self, key, quick=False, pg="1"):
        k = str(key or "").strip()
        ck = "q_" + k
        now = time.time()
        if getattr(self, "_sc_t", {}).get(ck, 0) > now - 300 and ck in (getattr(self, "_sc", {}) or {}):
            return self._sc[ck]
        j = self._req("GET", "/v1/browse/catalog?q=%s&page=1&limit=20" % urllib.parse.quote(k))
        r = {"list": [self._vod(c) for c in (j.get("cards") or [])]}
        if not hasattr(self, "_sc"):
            self._sc = {}
        if not hasattr(self, "_sc_t"):
            self._sc_t = {}
        self._sc[ck], self._sc_t[ck] = r, now
        return r

    def playerContent(self, flag, id, vipFlags=None, vipIds=None):
        tok = str(id or "").strip()
        if not tok:
            return {"url": ""}
        murl = YJ % tok
        try:
            import requests as rq
            r = rq.get(murl, headers={"User-Agent": UA}, timeout=6)
            if r.status_code == 200 and "#EXTM3U" in r.text:
                return {"parse": 0, "url": murl}
        except Exception:
            pass
        try:
            import requests as rq
            r = rq.get("https://zy.baipiaozhe.com/v1/playback/yjapi/%s" % tok, headers={"User-Agent": UA, "Accept": "application/json"}, timeout=6)
            if r.status_code == 200:
                j = r.json()
                u = (j.get("url") or "") if isinstance(j, dict) else ""
                if u:
                    return {"parse": 0, "url": u}
        except Exception:
            pass
        j = self._req("GET", "/v1/playback/resolve/%s" % tok)
        lines = j.get("line_options") or []
        wanted = str(flag or "")
        if wanted and wanted != "kanju":
            picked = [l for l in lines if (l.get("provider_name") or "") == wanted]
            lines = picked or lines
        for lo in lines:
            t = lo.get("url") or ""
            if t.startswith("resolve://"):
                t = t[10:]
            if not t:
                continue
            rj = self._req("POST", "/v1/playback/resolve-line", {"ticket": t})
            url = (rj.get("line") or {}).get("url") or ""
            if url:
                return {"parse": 0, "url": url}
        return {"url": ""}

    def localProxy(self, param):
        return None
