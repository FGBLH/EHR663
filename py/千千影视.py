# -*- coding: utf-8 -*-
import requests, re, json, base64
from urllib.parse import urljoin, quote, unquote

HOST = "https://www.moxy.top"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

class Spider:
    def init(self, extend=""):
        global HOST
        try:
            resp = requests.get(HOST, headers={"User-Agent": UA}, timeout=15, allow_redirects=True)
            if resp.url and "moxy" not in resp.url:
                HOST = resp.url.rstrip("/")
        except:
            pass

    def homeContent(self, filter=False):
        r = {"class": [], "list": [], "filter": {}}
        for k, v in {"1":"电影","2":"连续剧","3":"综艺","4":"动漫","5":"短剧"}.items():
            r["class"].append({"type_id": k, "type_name": v})
        try:
            resp = requests.get(HOST, headers={"User-Agent": UA}, timeout=30)
            resp.encoding = "utf-8"
            r["list"] = self._items(resp.text)[:60]
        except:
            pass
        return r

    def homeVideoContent(self):
        return {"list": self.homeContent().get("list", [])}

    def categoryContent(self, tid, pg=1, filter=False, extend=""):
        pn = 1
        try: pn = max(int(str(pg)), 1)
        except: pass
        cid = str(tid) if str(tid) in "12345" else "1"
        try:
            # 网站分页URL格式: /vodshow/{cid}--------{page}---.html
            if pn > 1:
                url = f"{HOST}/vodshow/{cid}--------{pn}---.html"
            else:
                url = f"{HOST}/vodshow/{cid}-----------.html"
            resp = requests.get(url, headers={"User-Agent": UA}, timeout=30)
            resp.encoding = "utf-8"
            items = self._items(resp.text)
            # 提取总页数
            pagecount = self._pagecount(resp.text)
            return {"page": pn, "pagecount": pagecount, "limit": 50, "total": len(items), "list": items}
        except:
            return {"page": pn, "pagecount": 1, "limit": 50, "total": 0, "list": []}

    def detailContent(self, ids):
        ids = str(ids) if ids else ""
        m = re.search(r'(\d+)', ids)
        vid = m.group(1) if m else ""
        if not vid: return {"list": []}
        try:
            resp = requests.get(f"{HOST}/voddetail{vid}.html", headers={"User-Agent": UA}, timeout=30)
            resp.encoding = "utf-8"
        except:
            return {"list": []}
        h = resp.text
        d = {"vod_id": vid, "vod_name": "", "vod_pic": "", "vod_year": "",
             "vod_area": "", "vod_class": "", "vod_director": "", "vod_actor": "",
             "vod_content": "", "vod_remarks": "", "vod_play_from": "", "vod_play_url": ""}
        t1 = re.search(r'<h1[^>]*>(.*?)</h1>', h)
        if t1: d["vod_name"] = t1.group(1).strip()
        if not d["vod_name"]:
            t2 = re.search(r'<title>(.*?)</title>', h)
            if t2: d["vod_name"] = t2.group(1).split("-")[0].strip()
        p = re.search(r'data-original="([^"]+)"', h)
        if p: d["vod_pic"] = p.group(1)
        for t in re.findall(r'<a[^>]*title="(\d{4})"', h):
            d["vod_year"] = t
        for t in re.findall(r'<a[^>]*title="([^"]*)"', h):
            if t in ("中国大陆","中国","香港","台湾","美国","日本","韩国","英国","法国","泰国","印度"):
                d["vod_area"] = t
        desc = re.search(r'<div[^>]*class="[^"]*module-info-introduction-content[^"]*"[^>]*>\s*<p>(.*?)</p>', h, re.S)
        if desc: d["vod_content"] = re.sub(r'<[^>]+>', '', desc.group(1)).strip()[:500]
        for m in re.finditer(r'<div[^>]*class="[^"]*module-info-item[^"]*"[^>]*>(.*?)</div>', h, re.S):
            t = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if "导演" in t: d["vod_director"] = t.replace("导演：","").replace("导演:","").strip()
            elif "主演" in t: d["vod_actor"] = t.replace("主演：","").replace("主演:","").strip()
            elif "备注" in t: d["vod_remarks"] = t.replace("备注：","").replace("备注:","").strip()
        try:
            sources = re.findall(r'data-dropdown-value="([^"]+)"', h) or ["默认"]
            blocks = re.findall(r'<div[^>]*class="[^"]*module-play-list[^"]*"[^>]*>(.*?)</div>\s*</div>\s*</div>', h, re.S)
            if not blocks:
                blocks = re.findall(r'<div[^>]*class="[^"]*module-play-list-content[^"]*"[^>]*>(.*?)</div>', h, re.S)
            pf, pu = [], []
            for i, blk in enumerate(blocks):
                eps = re.findall(r'<a[^>]*href="(/vodplay/[^"]+)"[^>]*>(?:<[^>]+>)*([^<]{1,20})(?:</[^>]+>)*</a>', blk, re.S)
                if not eps:
                    eps = re.findall(r'<a[^>]*href="(/vodplay/[^"]+)"[^>]*>.*?<span>(.*?)</span>', blk, re.S)
                if eps:
                    src = sources[i] if i < len(sources) else f"源{i+1}"
                    el = [f"{n.strip()}${urljoin(HOST, u)}" for u, n in eps if n.strip()]
                    if el:
                        pf.append(src)
                        pu.append("#".join(el))
            if pf:
                d["vod_play_from"] = "$$$".join(pf)
                d["vod_play_url"] = "$$$".join(pu)
        except:
            pass
        return {"list": [d]}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            resp = requests.get(f"{HOST}/vodsearch/{quote(str(key))}-------------.html", headers={"User-Agent": UA}, timeout=15)
            resp.encoding = "utf-8"
            if len(resp.text) > 200:
                return {"list": self._items(resp.text)[:30]}
        except:
            pass
        return {"list": []}

    def playerContent(self, flag, id, vipFlags=None):
        """
        兼容两种壳子参数顺序:
        - FongMi/TV: playerContent(flag, id, vipFlags)
        - PeekPro/CatVod: playerContent(id, flag, vipFlags)
        自动检测哪个是播放页URL，哪个是flag
        """
        a, b = str(flag), str(id) if id else ""
        # 自动判断：包含http或/vodplay的是URL，另一个是flag
        if a.startswith("http") or "/vodplay/" in a:
            url, flag_val = a, b
        elif b.startswith("http") or "/vodplay/" in b:
            url, flag_val = b, a
        elif a.startswith("/"):
            url, flag_val = urljoin(HOST, a), b
        elif b.startswith("/"):
            url, flag_val = urljoin(HOST, b), a
        else:
            url, flag_val = a, b

        try:
            resp = requests.get(url, headers={"User-Agent": UA}, timeout=30)
            resp.encoding = "utf-8"
        except:
            return {"url": ""}
        pd = re.search(r'player_data\s*=\s*(\{.*?\})', resp.text, re.S)
        if pd:
            try:
                data = json.loads(pd.group(1))
                u = data.get("url", "")
                if u:
                    try:
                        real_url = unquote(base64.b64decode(u).decode("utf-8"))
                    except:
                        real_url = u
                    if real_url.startswith("http"):
                        return {"url": real_url}
            except:
                pass
        return {"url": ""}

    def localProxy(self, param):
        return []

    def _pagecount(self, html):
        """从页面提取总页数"""
        pc = 1
        # 方法1: 尾页链接
        last = re.search(r'<a[^>]*href="[^"]*vodshow/\d+[^"]*(\d+)---\.html"[^>]*>尾页', html, re.S)
        if last:
            pc = max(pc, int(last.group(1)))
        # 方法2: page-link page-next 链接中的最大页码
        page_links = re.findall(r'<a[^>]*href="[^"]*vodshow/\d+-(\d+)', html)
        for p in page_links:
            try:
                n = int(p)
                if n > 100:  # 年份过滤掉
                    continue
                pc = max(pc, n)
            except:
                pass
        # 方法3: page-current 附近的页码
        all_nums = re.findall(r'class="[^"]*page-number[^"]*"[^>]*>\s*(\d+)\s*<', html)
        for n in all_nums:
            try:
                pc = max(pc, int(n))
            except:
                pass
        return pc

    def _items(self, html):
        items, seen = [], set()
        def ext(href, block):
            v = re.search(r'/voddetail(\d+)\.html', href)
            if not v or v.group(1) in seen: return None
            seen.add(v.group(1))
            t = (re.search(r'title="([^"]*)"', block) or re.search(r'alt="([^"]*)"', block))
            if not t: return None
            p = re.search(r'data-original="([^"]+)"', block)
            n = re.search(r'<div[^>]*class="[^"]*module-item-note[^"]*"[^>]*>([^<]+)</div>', block)
            return {"vod_id": v.group(1), "vod_name": t.group(1),
                    "vod_pic": p.group(1) if p else "",
                    "vod_remarks": n.group(1).strip() if n else "",
                    "vod_url": urljoin(HOST, href)}
        for m in re.finditer(
            r'<a[^>]*href="(/voddetail\d+\.html)"[^>]*title="([^"]*)"[^>]*class="[^"]*module-poster-item[^"]*"[^>]*>.*?</a>',
            html, re.S
        ):
            item = ext(m.group(1), m.group(0))
            if item: items.append(item)
        for m in re.finditer(
            r'<a[^>]*href="(/voddetail\d+\.html)"[^>]*class="[^"]*module-card-item-poster[^"]*"[^>]*>.*?</a>',
            html, re.S
        ):
            item = ext(m.group(1), m.group(0))
            if item: items.append(item)
        return items
