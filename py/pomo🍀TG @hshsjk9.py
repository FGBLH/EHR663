# -*- coding: utf-8 -*-
import sys
import re
import json
import time
from urllib.parse import quote

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

HOST = "https://pomo.mom"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
CATEGORIES = {"huayurm": "华语热门", "jiating": "家庭影院", "donghuadadiany": "动画大电影", "lengmenjiapian": "冷门佳片", "paihangbang": "TOP250", "sort/12": "蓝光原盘", "dianshiju": "剧集"}

class Spider(Spider):
    def init(self, extend=""):
        pass

    def _req(self, url, headers=None, method='GET', data=None):
        try:
            try:
                r = self.fetch(url, headers=headers, method=method, data=data, timeout=30000)
            except TypeError:
                try:
                    r = self.fetch(url, headers=headers, method=method, data=data)
                except TypeError:
                    r = self.fetch(url, headers=headers)
            except Exception:
                try:
                    r = self.fetch(url, headers=headers, method=method, data=data)
                except Exception:
                    try:
                        r = self.fetch(url, headers=headers)
                    except Exception:
                        return None
            return r
        except:
            return None

    def _text(self, r):
        if r is None:
            return ""
        return r.text if hasattr(r, 'text') else str(r)

    def _ok(self, r):
        if r is None:
            return False
        if hasattr(r, 'status_code'):
            return r.status_code == 200
        return True

    def _get(self, url, referer=""):
        headers = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
        if referer:
            headers["Referer"] = referer
        for attempt in range(3):
            r = self._req(url, headers=headers)
            if r is None:
                time.sleep(1)
                continue
            if hasattr(r, 'status_code') and r.status_code >= 400:
                time.sleep(1)
                continue
            return self._text(r)
        return ""

    def _card(self, block):
        m = re.search(r'<a href="https?://pomo\.mom/(\d+)(?:\.html)?"[^>]*>(.*?)</a>', block, re.DOTALL)
        if not m:
            return None
        vid = m.group(1)
        b = m.group(2)
        nm = re.search(r'<h3[^>]*>(.*?)</h3>', b, re.DOTALL)
        im = re.search(r'<img[^>]*src="(https?://[^"]+)"[^>]*alt="([^"]*)"', b)
        if not im:
            im = re.search(r'<img[^>]*alt="([^"]*)"[^>]*src="(https?://[^"]+)"', b)
        tags = re.findall(r'<div class="tag">(?:IMDB)?<span[^>]*>([^<]+)</span>|class="tag">([^<]+)<', b)
        name = re.sub(r'<[^>]+>', '', nm.group(1)).strip() if nm else ''
        if not name:
            name = im.group(2).strip() if im else ''
        remark = ' '.join([x[0] or x[1] for x in tags])[:60]
        return {"vod_id": vid, "vod_name": name[:80], "vod_pic": (im.group(1) if im else ''), "vod_remarks": remark}

    def _items(self, html):
        items, seen = [], set()
        for m in re.finditer(r'<a href="https?://pomo\.mom/(\d+)(?:\.html)?" class="block h-full flex flex-col">(.*?)</a>', html, re.DOTALL):
            vid = m.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            b = m.group(2)
            nm = re.search(r'<h3[^>]*>(.*?)</h3>', b, re.DOTALL)
            im = re.search(r'<img[^>]*src="(https?://[^"]+)"[^>]*alt="([^"]*)"', b)
            if not im:
                im = re.search(r'<img[^>]*alt="([^"]*)"[^>]*src="(https?://[^"]+)"', b)
            tags = re.findall(r'<div class="tag">(?:IMDB)?<span[^>]*>([^<]+)</span>|class="tag">([^<]+)<', b)
            name = re.sub(r'<[^>]+>', '', nm.group(1)).strip() if nm else ''
            if not name:
                name = im.group(2).strip() if im else ''
            items.append({
                "vod_id": vid,
                "vod_name": name[:80],
                "vod_pic": im.group(1) if im else "",
                "vod_remarks": ' '.join([x[0] or x[1] for x in tags])[:60],
            })
        for m in re.finditer(r'<a href="https?://pomo\.mom/(\d+)" class="hover:text-accent transition">([^<]+)</a>', html):
            vid = m.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            i0 = html.rfind('<img', 0, m.start())
            im = re.search(r'src="(https?://[^"]+)"', html[i0:m.start()]) if i0 >= 0 else None
            items.append({"vod_id": vid, "vod_name": m.group(2).strip()[:80], "vod_pic": im.group(1) if im else "", "vod_remarks": ""})
        return items

    def homeContent(self, filter=False):
        r = {"class": [{"type_id": k, "type_name": v} for k, v in CATEGORIES.items()], "list": []}
        html = self._get(HOST)
        r["list"] = self._items(html)[:50]
        return r

    def homeVideoContent(self):
        return {"list": self._items(self._get(HOST))[:50]}

    def categoryContent(self, tid, pg=1, filter=False, extend=""):
        try:
            pn = max(int(str(pg)), 1)
        except:
            pn = 1
        cat = str(tid)
        if cat not in CATEGORIES:
            cat = "dianshiju"
        url = f"{HOST}/{cat}/page/{pn}" if pn > 1 else f"{HOST}/{cat}"
        html = self._get(url)
        items = self._items(html)
        return {"page": pn, "pagecount": self._pagecount(html, pn), "limit": 24, "total": len(items), "list": items}

    def _routes(self, html):
        routes = re.findall(r'const\s+route(\d+)Data\s*=\s*(\[[^\]]*\])', html)
        has = dict(re.findall(r'const\s+hasRoute(\d+)\s*=\s*(true|false)', html))
        out = []
        for num, data in routes:
            n = int(num)
            if n > 1 and has.get(str(n), 'true') != 'true':
                continue
            try:
                out.append((n, json.loads(data.replace('\\/', '/'))))
            except:
                pass
        return out

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) else str(ids)
        m = re.search(r'(\d+)', vid)
        if not m:
            return {"list": []}
        vid = m.group(1)
        html = self._get(f"{HOST}/{vid}")
        if not html:
            return {"list": []}
        d = {"vod_id": vid, "vod_name": "", "vod_pic": "", "vod_year": "", "vod_area": "", "vod_class": "", "vod_director": "", "vod_actor": "", "vod_content": "", "vod_remarks": "", "vod_play_from": "", "vod_play_url": ""}
        tn = re.search(r'<h2[^>]*class="[^"]*x-dbjs-title[^"]*"[^>]*>(.*?)</h2>', html, re.DOTALL)
        if tn:
            d["vod_name"] = re.sub(r'<[^>]+>', '', tn.group(1)).strip()
        else:
            tn = re.search(r'<title>(.*?)</title>', html)
            if tn:
                d["vod_name"] = re.sub(r'\s*-\s*4K原盘免费下载\s*$', '', tn.group(1)).strip()
        pm = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]*)"', html)
        if pm:
            d["vod_content"] = pm.group(1).strip()[:500]
        pi = re.search(r'src="(https?://[^"]*poster_[^"]+\.(?:jpg|jpeg|webp))"', html)
        if not pi:
            pi = re.search(r'src="(https?://[^"]+\.(?:jpg|jpeg|webp))"', html)
        if pi:
            d["vod_pic"] = pi.group(1)
        for key, pat in (("vod_director", r'导演：</span>([^<]+)<'), ("vod_area", r'国家：</span>([^<]+)<'), ("vod_class", r'类型：</span>([^<]+)<')):
            mm = re.search(pat, html)
            if mm:
                d[key] = mm.group(1).strip()
        ym = re.search(r'时间：</span>(\d{4})', html)
        if ym:
            d["vod_year"] = ym.group(1)
        mags = re.findall(r'data-url="(magnet:[^"]+)"', html)
        if mags:
            d["vod_remarks"] = f"{len(mags)}个磁力源"
        ph = self._get(f"{HOST}/?plugin=plyr_player&gid={vid}")
        routes = self._routes(ph)
        if routes:
            pf, pu = [], []
            for n, arr in routes:
                eps = [x.split('$') for x in arr if '$' in x]
                if not eps:
                    continue
                pf.append(f"线路{n}")
                pu.append("#".join([f"{e[0].strip()}${vid}-{n}-{i}" for i, e in enumerate(eps)]))
            if pf:
                d["vod_play_from"] = "$$$".join(pf)
                d["vod_play_url"] = "$$$".join(pu)
        return {"list": [d]}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            html = self._get(f"{HOST}/search/?keyword={quote(key)}")
            return {"list": self._items(html), "page": 1}
        except:
            return {"list": []}

    def playerContent(self, flag, id, vipFlags=None):
        try:
            m = re.search(r'(\d+)-(\d+)-(\d+)', str(id))
            if not m:
                return {"url": ""}
            vid, rn, ei = m.group(1), int(m.group(2)), int(m.group(3))
            ph = self._get(f"{HOST}/?plugin=plyr_player&gid={vid}")
            routes = self._routes(ph)
            for n, arr in routes:
                if n == rn:
                    if ei >= len(arr):
                        return {"url": ""}
                    item = arr[ei]
                    url = item.split('$')[1] if '$' in item else item
                    if not url.startswith('http'):
                        return {"url": ""}
                    return {"parse": 0, "url": url}
            return {"url": ""}
        except:
            return {"url": ""}

    def localProxy(self, param):
        pass

    def _pagecount(self, html, current_page=1):
        pages = re.findall(r'/page/(\d+)', html)
        max_page = current_page
        for p in pages:
            try:
                n = int(p)
                if n > max_page:
                    max_page = n
            except:
                pass
        if max_page == current_page and re.search(r'下一页|page/%d' % (current_page + 1), html):
            max_page = current_page + 1
        return max_page

    def getName(self):
        return "POMO4K"

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass
