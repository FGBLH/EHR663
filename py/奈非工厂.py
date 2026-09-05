# -*- coding: utf-8 -*-
import sys
import re
import json
import base64
import requests as rq
from urllib.parse import urljoin, quote, unquote

sys.path.append('..')
try:
    from base.spider import Spidaer
except ImportError:
    class Spider:
        def fetch(self, url, headers=None, **kw):
            import requests as rq
            kw.pop('timeout', None)
            method = kw.pop('method', 'GET')
            data = kw.pop('data', None)
            r = rq.request(method, url, headers=headers, data=data, timeout=15, **kw)
            r.encoding = 'utf-8'
            return r

HOST = "https://www.netflixgc.com"
UA = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36"

CATEGORIES = {
    "1": "电影", "2": "连续剧", "24": "纪录片",
    "3": "漫剧", "23": "综艺", "57": "直播",
}


class Spider(Spider):
    def init(self, extend=""):
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

    def _pic(self, url):
        if not url:
            return ''
        m = re.search(r'image\.baidu\.com/search/down\?url=([^&]+)', url)
        if m:
            inner = unquote(m.group(1))
            if 'ffeiimg.com/upload/' in inner:
                url = inner
        return url.replace('ffeiimg.com/upload/', 'ffeiimg.com//upload/', 1)

    def _post(self, url, data):
        try:
            import urllib.request, urllib.parse
            req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(),
                                         headers={"User-Agent": UA, "Referer": HOST + "/",
                                                  "Content-Type": "application/x-www-form-urlencoded"})
            return urllib.request.urlopen(req, timeout=20).read().decode('utf-8', 'ignore')
        except:
            return ''

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
            data = {'type': cat, 'class': '', 'area': '', 'year': '', 'lang': '', 'version': '',
                    'state': '', 'letter': '', 'time': '', 'level': '0', 'weekday': '', 'by': 'time', 'page': str(pn)}
            res = json.loads(self._post(f"{HOST}/index.php/ds_api/vod", data))
            if res.get("code") == 1:
                items = []
                for it in res.get("list", []):
                    items.append({
                        "vod_id": str(it.get("vod_id", "")),
                        "vod_name": str(it.get("vod_name", "")),
                        "vod_pic": self._pic(str(it.get("vod_pic", "") or "")),
                        "vod_remarks": str(it.get("vod_remarks", "") or ""),
                    })
                return {
                    "page": pn,
                    "pagecount": int(res.get("pagecount") or 1),
                    "limit": int(res.get("limit") or 40),
                    "total": int(res.get("total") or len(items)),
                    "list": items
                }
        except:
            pass
        try:
            r = self.fetch(f"{HOST}/vodshow/{cat}-----------.html", headers={"User-Agent": UA}, timeout=30000)
            html = r.text if hasattr(r, 'text') else str(r)
            items = self._items(html)
            return {
                "page": pn,
                "pagecount": self._pagecount(html, pn),
                "limit": 42,
                "total": len(items),
                "list": items
            }
        except:
            return {"page": pn, "pagecount": 1, "limit": 42, "total": 0, "list": []}

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
        tn = re.search(r'<title>(.*?)</title>', h)
        if tn:
            d["vod_name"] = tn.group(1).split("_")[0].strip()

        # 封面 (lazy img data-src)
        p = re.search(r'class="[^"]*lazy[^"]*"[\s\S]*?data-src="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"', h, re.I)
        if not p:
            p = re.search(r'data-src="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"', h, re.I)
        if not p:
            p = re.search(r'<img[^>]*(?:data-original|src)="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"', h, re.I)
        if p:
            d["vod_pic"] = self._pic(p.group(1))

        # 简介 (meta description 优先)
        desc_m = re.search(r'<meta name="description" content="([^"]+)"', h)
        if not desc_m:
            desc_m = re.search(r'class="[^"]*vod-content[^"]*"[^>]*>([\s\S]*?)</div>', h)
        if desc_m:
            d["vod_content"] = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', desc_m.group(1))).strip()[:500]

        # 年份
        ym = re.search(r'<em[^>]*>([12]\d{3})</em>', h)
        if not ym:
            ym = re.search(r'([12]\d{3})</[a-z]+>', h)
        if ym:
            d["vod_year"] = ym.group(1)

        # 地区
        am = re.search(r'地区[：:]?</span>\s*([^<\n]+?)(?:\s|</)', h)
        if not am:
            am = re.search(r'地区[：:]?\s*([^<\n]+?)(?:\s|</)', h)
        if am:
            d["vod_area"] = am.group(1).strip().rstrip('，').strip()

        # 分类
        cm = re.search(r'分类[：:]?</span>\s*([^<\n]+?)(?:\s|</)', h)
        if not cm:
            cm = re.search(r'类型[：:]?\s*([^<\n]+?)(?:\s|</)', h)
        if cm:
            d["vod_class"] = cm.group(1).strip().rstrip('，').strip()

        # 导演
        dm = re.search(r'导演[：:]</span>([\s\S]*?)(?:</p>|</div>|<div)', h)
        if not dm:
            dm = re.search(r'导演[：:]?\s*([^<\n]+?)(?:\s|</)', h)
        if dm:
            d["vod_director"] = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', dm.group(1))).strip().rstrip('，').strip()

        # 主演
        am2 = re.search(r'主演[：:]</span>([\s\S]*?)(?:</p>|</div>|<div)', h)
        if not am2:
            am2 = re.search(r'(?:演员|主演)[：:]?\s*([^<\n]+?)(?:\s|</)', h)
        if am2:
            d["vod_actor"] = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', am2.group(1))).strip().rstrip('，').strip()

        # 备注/状态
        rm = re.search(r'class="[^"]*slide-info-remarks[^"]*"[^>]*>([^<]+)<', h)
        if not rm:
            rm = re.search(r'更新[至到]?([^<\n]+)', h)
        if rm:
            d["vod_remarks"] = rm.group(1).strip()

        # 播放源
        try:
            pf, pu = [], []
            # 线路名: anthology-tab swiper-slide
            tab_area = re.search(r'class="[^"]*(?:anthology-tab|module-tab-items|play-tab|tab-list)[^"]*"[\s\S]*?</div>', h)
            valid_tab_names = []
            if tab_area:
                tabs = re.findall(r'<a[^>]*class="[^"]*swiper-slide[^"]*"[^>]*>([\s\S]*?)</a>', tab_area.group(0))
                for tab in tabs:
                    clean = re.sub(r'<span class="badge">[\s\S]*?</span>', '', tab)
                    clean = re.sub(r'<[^>]+>', '', clean).replace('&nbsp;', '').strip()
                    if clean and '排序' not in clean and '报错' not in clean and len(clean) < 20:
                        valid_tab_names.append(clean)

            # 播放列表: anthology-list-box 顺序对应 tab
            playlist_area = re.search(r'<div class="anthology-list[^>]*>([\s\S]*?)</div>\s*</div>\s*</div>', h)
            if playlist_area:
                uls = re.findall(r'<ul[^>]*>([\s\S]*?)</ul>', playlist_area.group(0))
                for i, ul in enumerate(uls):
                    links = re.findall(r'href="(/vodplay/\d+-\d+-\d+\.html)"[^>]*>([^<]+)</a>', ul)
                    if links:
                        name = valid_tab_names[i] if i < len(valid_tab_names) else f"线路{i+1}"
                        pf.append(name)
                        pu.append("#".join([f"{ep}${urljoin(HOST, href)}" for href, ep in links]))
            else:
                # 兜底: 全局搜索 vodplay 链接
                play_urls = re.findall(r'href="(/vodplay/\d+-(\d+)-(\d+)\.html)"[^>]*>([^<]+)</a>', h)
                routes = {}
                for href, route, ep, name in play_urls:
                    if route not in routes:
                        routes[route] = []
                    routes[route].append(f"{name.strip()}${urljoin(HOST, href)}")
                route_idx = 0
                for route in sorted(routes.keys(), key=lambda x: int(x) if x.isdigit() else 999):
                    name = valid_tab_names[route_idx] if route_idx < len(valid_tab_names) else f"线路{route}"
                    pf.append(name)
                    pu.append("#".join(routes[route]))
                    route_idx += 1

            if pf:
                i = next((k for k, n in enumerate(pf) if n.strip() == '蓝光-1'), None)
                if i is not None:
                    j = max(k for k, n in enumerate(pf) if n.startswith('蓝光'))
                    if i < j:
                        pf.insert(j, pf.pop(i))
                        pu.insert(j, pu.pop(i))
                d["vod_play_from"] = "$$$".join(pf)
                d["vod_play_url"] = "$$$".join(pu)
        except:
            pass

        return {"list": [d]}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            url = f"{HOST}/vodsearch/{quote(key)}-------------.html"
            r = self.fetch(url, headers={"User-Agent": UA}, timeout=30000)
            html = r.text if hasattr(r, 'text') else str(r)
            items = self._items(html)
            return {"list": items, "page": int(pg) if str(pg).isdigit() else 1}
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

        pd = re.search(r'player_aaaa\s*=\s*(\{[\s\S]*?\})\s*[;<]', h, re.S)
        if pd:
            try:
                data = json.loads(pd.group(1))
                play_url = data.get("url", "")
                if play_url:
                    if data.get("encrypt") == 2:
                        try:
                            play_url = unquote(base64.b64decode(play_url).decode('utf-8', 'ignore'))
                        except:
                            play_url = unquote(play_url)
                    if play_url.startswith("http"):
                        return {"url": play_url}
                    if play_url.startswith('NBY-'):
                        return {"parse": 1, "url": "https://cjbfq.netflixgc.tv/player/ec.php?code=netflix&if=1&url=" + quote(play_url)}
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
        try:
            m = re.search(r'[?&]url=([^&]+)', str(param))
            if not m:
                return None
            url = unquote(m.group(1))
            if not url.startswith('http'):
                return None
            import urllib.request, gzip
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Referer": HOST + "/", "Accept-Encoding": "gzip"})
            resp = urllib.request.urlopen(req, timeout=15)
            data = resp.read()
            if resp.headers.get('Content-Encoding') == 'gzip':
                data = gzip.decompress(data)
            return data
        except:
            return None

    def _pagecount(self, html, current_page=1):
        pages = re.findall(r'href="/vodshow/\d+--------(\d+)---\.html"', html)
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
            cover = re.search(r'(?:data-src|data-original|original|src)="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"', after, re.I)
            if not cover:
                cover = re.search(r'src="(https?://[^"]+)"', after)
            remark = re.search(r'class="[^"]*(?:slide-info-remarks|module-item-note|pic-text|public-list-prb|remarks|status)[^"]*"[^>]*>([^<]+)<', after)
            if not remark:
                remark = re.search(r'<div[^>]*class="[^"]*(?:note|text|remark)[^"]*"[^>]*>([^<]+)<', after, re.I)
            seen.add(vid)
            items.append({
                "vod_id": vid,
                "vod_name": name[:50],
                "vod_pic": self._pic(cover.group(1) if cover else ""),
                "vod_remarks": remark.group(1).strip() if remark else "",
            })
        # 搜索页兜底: 无 title, 名称在 <h3>, 图片在链接前
        for m in re.finditer(r'href="/voddetail/(\d+)\.html"[^>]*>\s*<h3[^>]*>([^<]+)</h3>', html):
            vid = m.group(1)
            if vid in seen:
                continue
            name = m.group(2).strip()
            if not name or len(name) > 100:
                continue
            before = html[max(0, m.start() - 600):m.start()]
            cover = re.search(r'(?:data-src|src)="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"', before, re.I)
            after = html[m.end():m.end() + 600]
            remark = re.search(r'class="[^"]*slide-info-remarks cor5[^"]*"[^>]*>([^<]+)<', after)
            seen.add(vid)
            items.append({
                "vod_id": vid,
                "vod_name": name[:50],
                "vod_pic": self._pic(cover.group(1) if cover else ""),
                "vod_remarks": remark.group(1).strip() if remark else "",
            })
        return items
