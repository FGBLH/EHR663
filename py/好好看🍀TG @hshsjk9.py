#!/usr/bin/python
# -*- coding: utf-8 -*-
import re, json, time, hashlib, threading, requests, urllib.parse
import concurrent.futures as cf
from base.spider import Spider

PIC = "http://vres.cyscyy.com"
UA = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36"

class Spider(Spider):
    def getName(self):
        return "好好看"
    def init(self, extend=""):
        try:
            ext = json.loads(extend)
            self.host = ext.get("host", "https://www.hhkan2.com").rstrip("/")
        except Exception:
            self.host = "https://www.hhkan2.com"
        self.headers = {"User-Agent": UA}
        self.s = requests.Session()
        self.s.headers.update(self.headers)
        self.s.headers["Accept-Encoding"] = "gzip, deflate"
        self.categories = [
            {"type_id": "1", "type_name": "电影"},
            {"type_id": "2", "type_name": "剧集"},
            {"type_id": "3", "type_name": "动漫"},
            {"type_id": "4", "type_name": "综艺"},
            {"type_id": "6", "type_name": "短剧"},
        ]
        self._tok = ""
        self._tok_t = 0
        self._fcache = {}
        self._src_alive = {}
        self._filters_built = False
        self._lock = threading.Lock()
        self._pool = cf.ThreadPoolExecutor(8)
    def _solve(self, html):
        m = re.search(r"'([0-9A-F]{40})'", html)
        c = m.group(1)
        n1 = int(c[0], 16)
        i = 0
        while True:
            d = hashlib.sha1((c + str(i)).encode()).digest()
            if d[n1] == 0xB0 and d[n1 + 1] == 0x0B:
                break
            i += 1
        self.s.cookies.set("cdndefend_js_cookie", c + str(i), domain=self.host.split("//")[-1])
    def _get(self, url):
        try:
            u = url if url.startswith("http") else self.host + url
            r = self.s.get(u, timeout=20)
            tries = 0
            while "cdndefend" in r.text[:3000] and tries < 3:
                with self._lock:
                    r = self.s.get(u, timeout=20)
                    if "cdndefend" in r.text[:3000]:
                        self._solve(r.text)
                        self._tok = ""
                        r = self.s.get(u, timeout=20)
                tries += 1
            return r.text
        except Exception:
            return ""
    def _pic(self, u):
        if not u:
            return ""
        return PIC + u if u.startswith("/") else u
    def _items(self, html):
        out = []
        seen = set()
        for blk in re.findall(r'<div class="module-item">.*?</div>\s*</a>\s*</div>', html, re.S):
            mid = re.search(r'href="/detail/(\d+)\.html"', blk)
            if not mid or mid.group(1) in seen:
                continue
            seen.add(mid.group(1))
            cov = next((x for x in re.findall(r'data-original="([^"]+)"', blk) if x.startswith("/vod1")), "")
            tit = re.findall(r'<div class="v-item-title">([^<]+)</div>', blk)
            rem = re.search(r'<div class="v-item-bottom">\s*<span>\s*([^<]+?)\s*</span>', blk)
            out.append({"vod_id": mid.group(1), "vod_name": tit[0].strip() if tit else "", "vod_pic": self._pic(cov), "vod_remarks": rem.group(1) if rem else ""})
        return out
    def _token(self):
        if not self._tok or time.time() - self._tok_t > 1800:
            h = self._get("/")
            m = re.search(r'/search\?k=[^&]+&(?:amp;)?t=([^"&]+)', h)
            self._tok = m.group(1) if m else ""
            self._tok_t = time.time()
        return self._tok
    def _build_filters(self, tid):
        html = self._get(f"/show/{tid}-----1-1.html")
        fmap = {"类型": "cls", "地区": "area", "语言": "lang", "年份": "year", "排序": "sort"}
        fl = []
        for name, body in re.findall(r'<div class="filter-row-side">\s*<strong>([^:]+):</strong>.*?<div class="filter-row-main">(.*?)</div>\s*</div>', html, re.S):
            key = fmap.get(name.strip())
            if not key:
                continue
            vals, seenl = [], set()
            for href, txt in re.findall(r'<a\s+href="(/show/[^"]+)"\s+class="filter-item[^"]*">([^<]+)</a>', body):
                t = txt.strip()
                if t in seenl:
                    continue
                seenl.add(t)
                segs = href[len("/show/"):].split(".")[0].split("-")
                v = ""
                if key == "sort":
                    v = segs[5] if len(segs) == 7 else "1"
                else:
                    idx = {"cls": 1, "area": 2, "lang": 3, "year": 4}[key]
                    v = urllib.parse.unquote(segs[idx]) if len(segs) == 7 else ""
                vals.append({"n": t if t != "全部" else ("综合" if key == "sort" else "全部"), "v": v})
            if vals:
                fl.append({"key": key, "name": name.strip(), "value": vals})
        order = ["sort", "cls", "area", "lang", "year"]
        fl.sort(key=lambda x: order.index(x["key"]) if x["key"] in order else 9)
        return fl
    def _ensure_filters(self):
        if self._filters_built:
            return
        futs = {tid: self._pool.submit(self._build_filters, tid) for tid, _ in [(c["type_id"], 0) for c in self.categories]}
        for tid, f in futs.items():
            try:
                self._fcache[tid] = f.result()
            except Exception:
                self._fcache[tid] = []
        self.filters = self._fcache
        self._filters_built = True
    def homeContent(self, filter):
        html = self._get("/")
        self._ensure_filters()
        hot = []
        seen = set()
        for blk in re.findall(r'<div class="module-item">.*?</div>\s*</a>\s*</div>', html, re.S):
            mid = re.search(r'href="/detail/(\d+)\.html"', blk)
            if not mid or mid.group(1) in seen:
                continue
            seen.add(mid.group(1))
            tit = re.findall(r'<div class="v-item-title">([^<]+)</div>', blk)
            cov = next((x for x in re.findall(r'data-original="([^"]+)"', blk) if x.startswith("/vod1")), "")
            if tit:
                hot.append({"vod_id": mid.group(1), "vod_name": tit[0].strip(), "vod_pic": self._pic(cov)})
        return {"class": self.categories, "list": hot[:40], "filters": self._fcache}
    def categoryContent(self, tid, pg, filter, extend):
        extend = extend or {}
        cls = urllib.parse.quote(extend.get("cls", ""))
        area = urllib.parse.quote(extend.get("area", ""))
        lang = urllib.parse.quote(extend.get("lang", ""))
        year = extend.get("year", "")
        sort = extend.get("sort", "1")
        url = f"/show/{tid}-{cls}-{area}-{lang}-{year}-{sort}-{pg}.html"
        html = self._get(url)
        lst = self._items(html)
        pagecount = int(pg) + 1 if 'page-item-next' in html else int(pg)
        return {"page": int(pg), "pagecount": pagecount, "limit": len(lst), "total": pagecount * max(len(lst), 1), "list": lst}
    def _probe_ep(self, ep):
        try:
            h = self._get(ep)
            if "initVideoPlayer" not in h:
                return True
            return bool(re.search(r'src:\s*"https?://[^"]+"', h))
        except Exception:
            return True
    def _alive_mask(self, plays, urls):
        pending = {}
        for i, us in enumerate(urls):
            sn = us.split("#")[0].split("$")[1].split("-")[-2]
            if sn not in self._src_alive and sn not in pending:
                pending[sn] = i
        if pending:
            futs = {sn: self._pool.submit(self._probe_ep, urls[i].split("#")[0].split("$")[1]) for sn, i in pending.items()}
            for sn, f in futs.items():
                try:
                    self._src_alive[sn] = f.result()
                except Exception:
                    self._src_alive[sn] = True
        mask = []
        for us in urls:
            sn = us.split("#")[0].split("$")[1].split("-")[-2]
            mask.append(self._src_alive.get(sn, True))
        return mask if any(mask) else [True] * len(urls)
    def detailContent(self, ids):
        vid = ids[0]
        html = self._get(f"/detail/{vid}.html")
        name = re.search(r'<title>([^<]+?)-[^<]*</title>', html)
        cov = re.search(r'class="detail-pic">\s*<img[^>]+data-original="([^"]+)"', html)
        tags = [t.strip() for t in re.findall(r'class="detail-tags-item">([^<]+)</a>', html)]
        rows = dict(re.findall(r'class="detail-info-row-side">([^:]+):</div>\s*<div class="detail-info-row-main">(.*?)</div>', html, re.S))
        def rowtxt(k):
            v = rows.get(k, "")
            return "/".join(re.findall(r'>([^<>]+)</a>', v)) or re.sub(r"<[^>]+>|\s+", " ", v).strip()
        desc = re.search(r'<div class="detail-desc">.*?<p>(.*?)</p>', html, re.S)
        labels = [l.strip() for l in re.findall(r'class="source-item[^"]*">\s*<span class="source-item-label">([^<]+)</span>', html)]
        lists = re.findall(r'<div class="episode-list"[^>]*>(.*?)</div>', html, re.S)
        plays, urls = [], []
        for idx, blk in enumerate(lists[:len(labels)]):
            eps = re.findall(r'href="(/play/\d+-\d+-\d+\.html)"[^>]*>\s*(?:<span>)?\s*([^<]+?)\s*(?:</span>)?\s*</a>', blk)
            if not eps:
                continue
            plays.append(labels[idx] if idx < len(labels) else f"线路{idx+1}")
            urls.append("#".join(f"{e[1].strip()}${e[0]}" for e in eps))
        alive = self._alive_mask(plays, urls)
        kplays = [p for p, a in zip(plays, alive) if a]
        kurls = [u for u, a in zip(urls, alive) if a]
        if not kplays:
            kplays, kurls = plays, urls
        vod = {"vod_id": vid, "vod_name": name.group(1).strip() if name else "", "vod_pic": self._pic(cov.group(1)) if cov else "", "type_name": ",".join(tags), "vod_year": next((t for t in tags if re.match(r"^(19|20)\d{2}", t)), ""), "vod_area": next((t for t in tags if t.endswith(("大陆", "香港", "台湾")) or t in ("美国", "韩国", "日本", "泰国", "英国", "法国", "德国", "印度")), ""), "vod_director": rowtxt("导演"), "vod_actor": rowtxt("演员"), "vod_content": re.sub(r"<[^>]+>|\s+", " ", desc.group(1)).strip() if desc else "", "vod_play_from": "$$$".join(kplays), "vod_play_url": "$$$".join(kurls)}
        return {"list": [vod]}
    def searchContent(self, key, quick, pg="1"):
        url = f"/search?k={urllib.parse.quote(key)}&page={pg}&t={self._token()}"
        html = self._get(url)
        out = []
        seen = set()
        for m in re.finditer(r'href="/detail/(\d+)\.html" class="search-result-item">(.*?)(?=<a href="/detail/|<div class="pagenation)', html, re.S):
            vid, blk = m.group(1), m.group(2)
            if vid in seen:
                continue
            seen.add(vid)
            nm = re.search(r'<div class="title">([^<]+)</div>', blk) or re.search(r'title="([^"]+)"', blk)
            cov = re.search(r'data-original="(/vod1[^"]+)"', blk)
            tg = re.search(r'<div class="tags">(.*?)</div>', blk, re.S)
            tvals = [t.strip() for t in re.findall(r'<span>([^<]+)</span>', tg.group(1))] if tg else []
            out.append({"vod_id": vid, "vod_name": nm.group(1).strip() if nm else "", "vod_pic": self._pic(cov.group(1)) if cov else "", "vod_remarks": "/".join(tvals[:2])})
        pagecount = int(pg) + 1 if 'page-item-next' in html else int(pg)
        return {"list": out, "page": int(pg), "pagecount": pagecount}
    def playerContent(self, flag, id, vipFlags):
        html = self._get(id if id.startswith("/") else "/" + id)
        m = re.search(r'src:\s*"([^"]+\.(?:m3u8|mp4)[^"]*)"', html)
        url = m.group(1) if m else ""
        return {"parse": 0, "url": url, "header": json.dumps({"User-Agent": UA})}
