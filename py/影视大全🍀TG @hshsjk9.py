# -*- coding: utf-8 -*-
import sys
import re
import json
from urllib.parse import urljoin, quote

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

HOST = "https://www.iysdq.tv"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

CATEGORIES = {
    "1": "电影", "2": "电视剧", "3": "综艺",
    "4": "动漫", "5": "短剧",
}


class Spider(Spider):
    def init(self, extend=""):
        global HOST
        try:
            r = self.fetch(HOST, headers={"User-Agent": UA}, timeout=15000)
            if hasattr(r, 'url') and r.url and r.url != HOST.rstrip("/"):
                HOST = r.url.rstrip("/")
        except:
            pass

    def homeContent(self, filter=False):
        r = {"class": [], "list": []}
        for k, v in CATEGORIES.items():
            r["class"].append({"type_id": k, "type_name": v})
        return r

    def homeVideoContent(self):
        try:
            r = self.fetch(HOST, headers={"User-Agent": UA}, timeout=15000)
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
        if cat not in CATEGORIES:
            cat = "1"
        try:
            url = f"{HOST}/vodtype/{cat}-{pn}.html"
            r = self.fetch(url, headers={"User-Agent": UA}, timeout=30000)
            html = r.text if hasattr(r, 'text') else str(r)
            items = self._items(html)
            return {
                "page": pn,
                "pagecount": self._pagecount(html, pn),
                "limit": 24,
                "total": len(items),
                "list": items
            }
        except:
            return {"page": pn, "pagecount": 1, "limit": 24, "total": 0, "list": []}

    def detailContent(self, ids):
        if isinstance(ids, list):
            vid = ids[0] if ids else ""
        else:
            vid = str(ids) if ids else ""
        m = re.search(r'(\d+)', str(vid))
        vid = m.group(1) if m else ""
        if not vid:
            return {"list": []}
        try:
            r = self.fetch(f"{HOST}/voddetail/{vid}.html", headers={"User-Agent": UA}, timeout=30000)
            h = r.text if hasattr(r, 'text') else str(r)
        except:
            return {"list": []}

        d = {
            "vod_id": vid, "vod_name": "", "vod_pic": "", "vod_year": "",
            "vod_area": "", "vod_class": "", "vod_director": "", "vod_actor": "",
            "vod_content": "", "vod_remarks": "", "vod_play_from": "", "vod_play_url": ""
        }

        # 标题
        tn = re.search(r'class="this-desc-title">([^<]+)<', h)
        if not tn:
            tn = re.search(r'<title>(.*?)</title>', h)
            if tn:
                d["vod_name"] = tn.group(1).split("-")[0].replace("免费在线观看", "").replace("高清完整版", "").strip()
        if tn and not d["vod_name"]:
            d["vod_name"] = re.sub(r'<[^>]+>', '', tn.group(1)).strip()

        # 封面 (顶部大图 background-image / data-src 兜底)
        p = re.search(r'background-image:\s*url\([\'"]?(https?://[^\'")]+)', h)
        if not p:
            p = re.search(r'data-src="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"', h, re.I)
        if p:
            d["vod_pic"] = p.group(1)

        # 简介 (meta description / this-desc 兜底)
        desc_m = re.search(r'<meta name="description" content="([^"]*)"', h)
        if not desc_m:
            desc_m = re.search(r'class="[^"]*this-desc[^"]*"[^>]*>([\s\S]*?)</div>', h)
        if desc_m:
            d["vod_content"] = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', desc_m.group(1))).strip()[:500]

        # 年份/地区/备注 (this-desc-info 块)
        info_m = re.search(r'class="this-desc-info"[^>]*>([\s\S]*?)</div>', h)
        if info_m:
            info = info_m.group(1)
            ym = re.search(r'(\d{4})', info)
            if ym:
                d["vod_year"] = ym.group(1)
            am = re.search(r'([\u4e00-\u9fff]{2,8}?)(?:</span>|$)', info)
            if am and not re.search(r'更新|状态', am.group(1)):
                d["vod_area"] = am.group(1)
            rm = re.search(r'更新[至到]?([^<]+)', info)
            if rm:
                d["vod_remarks"] = rm.group(1).strip()

        # 分类
        cm = re.search(r'class="[^"]*this-tag[^"]*bj2[^"]*"[^>]*>([^<]+)<', h)
        if not cm:
            cm = re.search(r'class="this-desc-tags"[^>]*>([\s\S]*?)</div>', h)
        if cm:
            d["vod_class"] = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', cm.group(1))).strip().rstrip('，').strip()

        # 导演
        dm = re.search(r'导演:</strong>([\s\S]*?)</div>', h)
        if dm:
            d["vod_director"] = ','.join(re.findall(r'>([^<>]{1,30})</a>', dm.group(1)))

        # 主演
        am2 = re.search(r'演员:</strong>([\s\S]*?)</div>', h)
        if am2:
            d["vod_actor"] = ','.join(re.findall(r'>([^<>]{1,30})</a>', am2.group(1)))

        # 播放源
        try:
            pf, pu = [], []
            mt = re.search(r'<div class="anthology-tab[^>]*>(.*?)</div>\s*</div>', h, re.S)
            tabs = re.findall(r'&nbsp;([\u4e00-\u9fffA-Za-z]+线)', mt.group(1)) if mt else []
            boxes = re.findall(r'<div class=["\']?anthology-list-box[^>]*>(.*?)</div>\s*</div>', h, re.S)
            for tab, box in zip(tabs, boxes):
                links = re.findall(r'href="(/vodplay/\d+-\d+-\d+\.html)"[^>]*>([\s\S]*?)</a>', box)
                if not links:
                    continue
                eps = [re.sub(r'<[^>]+>', '', nm).strip() for u, nm in links]
                hrefs = [u for u, nm in links]
                pf.append(tab)
                pu.append("#".join([f"{ep}${urljoin(HOST, href)}" for ep, href in zip(eps, hrefs)]))
            if not pf:
                play_urls = re.findall(r'href="(/vodplay/\d+-(\d+)-(\d+)\.html)"[^>]*>([^<]+)</a>', h)
                routes = {}
                for href, route, ep, name in play_urls:
                    if route not in routes:
                        routes[route] = []
                    routes[route].append(f"{name.strip()}${urljoin(HOST, href)}")
                route_idx = 0
                for route in sorted(routes.keys(), key=lambda x: int(x) if x.isdigit() else 999):
                    name = tabs[route_idx] if route_idx < len(tabs) else f"线路{route}"
                    pf.append(name)
                    pu.append("#".join(routes[route]))
                    route_idx += 1
            if pf:
                d["vod_play_from"] = "$$$".join(pf)
                d["vod_play_url"] = "$$$".join(pu)
        except:
            pass

        return {"list": [d]}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            pn = 1
            try:
                pn = int(str(pg))
            except:
                pass
            url = f"{HOST}/vodsearch/-------------.html?wd={quote(key)}"
            r = self.fetch(url, headers={"User-Agent": UA}, timeout=30000)
            html = r.text if hasattr(r, 'text') else str(r)
            items = self._items(html)
            return {"list": items, "page": pn}
        except:
            return {"list": []}

    def playerContent(self, flag, id, vipFlags=None):
        url = str(id) if id else str(flag)
        if url.startswith("http") and "/vodplay/" not in url and (".m3u8" in url or ".mp4" in url):
            return {"url": url}
        if url.startswith("http"):
            full_url = url
        else:
            if not url.startswith("/"):
                url = "/" + url
            full_url = urljoin(HOST, url)
        try:
            r = self.fetch(full_url, headers={"User-Agent": UA}, timeout=30000)
            h = r.text if hasattr(r, 'text') else str(r)
        except:
            return {"url": ""}

        pd = re.search(r'var player_aaaa=(.*?)</script>', h, re.S)
        if pd:
            try:
                data = json.loads(pd.group(1))
                play_url = data.get("url", "")
                if play_url:
                    return {"url": play_url}
            except:
                pass

        m3u8 = re.search(r'(https?://[^\s"\'<>]+\.m3u8)', h)
        if m3u8:
            return {"url": m3u8.group(1)}
        mp4 = re.search(r'(https?://[^\s"\'<>]+\.mp4)', h)
        if mp4:
            return {"url": mp4.group(1)}
        return {"url": ""}

    def localProxy(self, param):
        pass

    def _pagecount(self, html, current_page=1):
        pages = re.findall(r'href="/vodtype/\d+-(\d+)\.html"', html)
        max_page = current_page
        for p in pages:
            try:
                n = int(p)
                if n > max_page:
                    max_page = n
            except:
                pass
        has_next = re.search(r'title="下一页"|class="[^"]*next[^"]*"', html)
        if has_next and max_page <= current_page + 5:
            max_page = current_page + 5
        return max_page

    def _items(self, html):
        items, seen = [], set()
        for m in re.finditer(r'href="/voddetail/(\d+)\.html"[^>]*title="([^"]*)"', html):
            vid = m.group(1)
            if vid in seen:
                continue
            name = m.group(2).strip()
            if not name or len(name) > 100:
                continue
            after = html[m.end():m.end() + 800]
            cover = re.search(r'(?:data-original|data-src|original|src)="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"', after, re.I)
            if not cover:
                cover = re.search(r'src="(https?://[^"]+)"', after)
            remark = re.search(r'class="(?:module-item-note|pic-text|public-list-prb|remarks|status|myui-vodlist__thumb)[^"]*"[^>]*>([^<]+)<', after)
            if not remark:
                remark = re.search(r'<div[^>]*class="[^"]*(?:note|text|remark)[^"]*"[^>]*>([^<]+)<', after, re.I)
            seen.add(vid)
            items.append({
                "vod_id": vid,
                "vod_name": name[:50],
                "vod_pic": cover.group(1) if cover else "",
                "vod_remarks": remark.group(1).strip() if remark else "",
            })
        return items