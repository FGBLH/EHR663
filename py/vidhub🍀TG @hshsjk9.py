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

HOST = "https://vidhub.tv"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
CATEGORIES = {"1": "电影", "2": "电视剧", "3": "综艺", "4": "动漫", "29": "短剧", "30": "纪录片"}

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

    def homeContent(self, filter=False):
        r = {"class": [], "list": []}
        for k, v in CATEGORIES.items():
            r["class"].append({"type_id": k, "type_name": v})
        html = self._get(HOST)
        items = self._items(html)
        r["list"] = items[:50]
        return r

    def homeVideoContent(self):
        html = self._get(HOST)
        return {"list": self._items(html)[:50]}

    def categoryContent(self, tid, pg=1, filter=False, extend=""):
        pn = 1
        try:
            pn = max(int(str(pg)), 1)
        except:
            pass
        cat = str(tid)
        if cat not in CATEGORIES:
            cat = "1"
        url = f"{HOST}/vodshow/{cat}--------{pn}---.html"
        html = self._get(url)
        items = self._items(html, no_short=(cat == '2'), only_short=(cat == '29'))
        return {
            "page": pn,
            "pagecount": self._pagecount(html, pn),
            "limit": 72,
            "total": len(items),
            "list": items
        }

    def detailContent(self, ids):
        if isinstance(ids, list):
            vid = ids[0] if ids else ""
        else:
            vid = str(ids) if ids else ""
        m = re.search(r'(\d+)', str(vid))
        vid = m.group(1) if m else ""
        if not vid:
            return {"list": []}
        html = self._get(f"{HOST}/voddetail/{vid}.html")
        if not html:
            return {"list": []}
        d = {
            "vod_id": vid, "vod_name": "", "vod_pic": "", "vod_year": "",
            "vod_area": "", "vod_class": "", "vod_director": "", "vod_actor": "",
            "vod_content": "", "vod_remarks": "", "vod_play_from": "", "vod_play_url": ""
        }
        tn = re.search(r'<h1[^>]*>(.*?)</h1>', html)
        if tn:
            d["vod_name"] = re.sub(r'<[^>]+>', '', tn.group(1)).strip()
        else:
            tn = re.search(r'<title>(.*?)</title>', html)
            if tn:
                d["vod_name"] = tn.group(1).split("-")[0].strip()
        p = re.search(r'<img[^>]*data-src="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"', html, re.I)
        if not p:
            p = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]*)"', html)
            if p and p.group(1).startswith("//"):
                d["vod_pic"] = "https:" + p.group(1)
            elif p:
                d["vod_pic"] = p.group(1)
        if p and p.group(1).startswith("http"):
            d["vod_pic"] = p.group(1)
        dm = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]*)"', html)
        if dm:
            d["vod_content"] = dm.group(1).strip()[:500]
        ym = re.search(r'(\d{4})', html[html.find('年份'):html.find('年份') + 200] if '年份' in html else '')
        if ym:
            d["vod_year"] = ym.group(1)
        lines = re.findall(r'data-dropdown-value="([^"]+)"', html)
        blocks = []
        for m2 in re.finditer(r'<div class="module-list module-player-list tab-list sort-list"[^>]*>(.*?)</div>\s*</div>', html, re.DOTALL):
            if '/vodplay/' in m2.group(1):
                blocks.append(m2.group(1))
        if not blocks:
            pos = 0
            while True:
                start = html.find('<div class="module-list module-player-list tab-list sort-list">', pos)
                if start == -1:
                    break
                start += len('<div class="module-list module-player-list tab-list sort-list">')
                depth = 0
                end = None
                i = start
                while i < len(html):
                    if html[i:i+5] == '<div ':
                        depth += 1
                        i += 5
                    elif html[i:i+6] == '</div>':
                        if depth == 0:
                            end = i + 6
                            break
                        else:
                            depth -= 1
                            i += 6
                    else:
                        i += 1
                if end is not None:
                    if '/vodplay/' in html[start:end]:
                        blocks.append(html[start:end])
                    pos = end
                else:
                    pos = start + 1
        if len(lines) < len(blocks):
            lines = lines + [f"线路{i+1}" for i in range(len(lines), len(blocks))]
        pf, pu = [], []
        for i, block in enumerate(blocks[:len(lines)]):
            eps = re.findall(r'href="(/vodplay/(\d+)-(\d+)-(\d+)\.html)"[^>]*>(.*?)</a>', block, re.DOTALL)
            if eps:
                pf.append(lines[i])
                pu.append("#".join([f"{re.sub(r'<[^>]+>', '', ep[4]).strip()}${ep[1]}-{ep[2]}-{ep[3]}" for ep in eps]))
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
            html = self._get(f"{HOST}/vodsearch/{quote(key)}-------------.html")
            return {"list": self._items(html), "page": pn}
        except:
            return {"list": []}

    def playerContent(self, flag, id, vipFlags=None):
        try:
            vid = str(id)
            m = re.search(r'(\d+)-(\d+)-(\d+)', vid)
            if not m:
                return {"url": ""}
            vod_id, sid, nid = m.group(1), m.group(2), m.group(3)
            html = self._get(f"{HOST}/vodplay/{vod_id}-{sid}-{nid}.html", referer=f"{HOST}/voddetail/{vod_id}.html")
            if not html:
                return {"url": ""}
            m2 = re.search(r'<iframe[^>]*src="(/player/\?u=[^"]+)"', html)
            if not m2:
                m2 = re.search(r'src="(https?://[^"]*player[^"]*\?u=[^"]+)"', html)
            if not m2:
                return {"url": ""}
            pu = m2.group(1)
            if pu.startswith("/"):
                pu = HOST + pu
            mu = re.search(r'u=([^&]+)', pu)
            if not mu:
                return {"url": ""}
            u = mu.group(1)
            headers = {"User-Agent": UA, "Accept": "application/json, text/javascript, */*; q=0.01", "Referer": pu, "X-Requested-With": "XMLHttpRequest"}
            r = None
            for attempt in range(3):
                r = self._req(f"{HOST}/player/api/resolve.php?u={u}", headers=headers)
                if self._ok(r):
                    break
                time.sleep(1)
            if r is None:
                return {"url": ""}
            result = json.loads(self._text(r))
            if result.get("code") != 200:
                return {"url": ""}
            return {"parse": 0, "url": result.get("url", "")}
        except:
            return {"url": ""}

    def localProxy(self, param):
        pass

    def _pagecount(self, html, current_page=1):
        pages = re.findall(r'/vodshow/\d+--------(\d+)---\.html', html)
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

    def _items(self, html, no_short=False, only_short=False):
        items, seen = [], set()
        blocks = [m.start() for m in re.finditer(r'<div class="module-item">', html)]
        if blocks:
            for i, s in enumerate(blocks):
                block = html[s:blocks[i + 1] if i + 1 < len(blocks) else s + 4000]
                m = re.search(r'href="/voddetail/(\d+)\.html"[^>]*title="([^"]*)"', block)
                if not m:
                    continue
                vid = m.group(1)
                if vid in seen:
                    continue
                name = m.group(2).strip()
                if not name or len(name) > 100:
                    continue
                cm = re.search(r'video-class">([^<]+)<', block)
                vc = cm.group(1).strip() if cm else ''
                if no_short and vc == '短剧':
                    continue
                if only_short and vc != '短剧':
                    continue
                cover = re.search(r'(?:data-src|data-original|src)="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"', block, re.I)
                remark = re.search(r'class="[^"]*module-item-note[^"]*"[^>]*>([^<]+)<', block)
                if not remark:
                    remark = re.search(r'class="[^"]*module-item-text[^"]*"[^>]*>([^<]+)<', block)
                seen.add(vid)
                items.append({
                    "vod_id": vid,
                    "vod_name": name[:50],
                    "vod_pic": cover.group(1) if cover else "",
                    "vod_remarks": remark.group(1).strip() if remark else "",
                })
            return items
        m0 = re.search(r'<div class="module-list module-line-list"[^>]*>(.*?)</div>\s*</div>', html, re.DOTALL)
        seg = m0.group(1) if m0 else html
        for m in re.finditer(r'href="/voddetail/(\d+)\.html"[^>]*title="([^"]*)"', seg):
            vid = m.group(1)
            if vid in seen:
                continue
            name = m.group(2).strip()
            if not name or len(name) > 100:
                continue
            after = seg[m.end():m.end() + 800]
            cover = re.search(r'(?:data-src|data-original|src)="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"', after, re.I)
            remark = re.search(r'class="[^"]*module-item-note[^"]*"[^>]*>([^<]+)<', after)
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

    def getName(self):
        return "VidHub影视"

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass
