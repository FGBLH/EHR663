# -*- coding: utf-8 -*-
import sys, re, json, time
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

HOSTS = ["https://www.maihaolian.com", "http://www.maihaolian.com", "https://maihaolian.com", "http://maihaolian.com"]
HOST = "https://www.maihaolian.com"
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
CATEGORIES = {"1": "电影", "2": "电视剧", "3": "综艺", "4": "动漫", "5": "热门短剧", "qq": "腾讯SVIP", "youku": "优酷SVIP", "bli": "B站SVIP", "duanju": "红果短剧"}
PLAYABLE = {"1", "2", "3", "4", "5", "6"}
PARSERS = {"JD4K": "https://fgsrg.hzqingshan.com/player/", "JD2K": "https://fgsrg.hzqingshan.com/player/", "co": "https://zzrs.mfdyvip.com/player/", "BBA": "https://zzrs.mfdyvip.com/player/", "YYNB": "https://zzrs.mfdyvip.com/player/", "youku": "https://zzrs.mfdyvip.com/player/", "qq": "https://zzrs.mfdyvip.com/player/", "bilibili": "https://zzrs.mfdyvip.com/player/", "qiyi": "https://zzrs.mfdyvip.com/player/"}

class Spider(Spider):
    def _fetch(self, url, headers=None, timeout=15):
        for fn in (lambda: self.fetch(url, headers=headers, verify=False), lambda: self.fetch(url, verify=False)):
            try:
                r = fn()
                h = r.text if hasattr(r, 'text') else (r.decode('utf-8', 'ignore') if isinstance(r, bytes) else str(r))
                if h and len(h) > 500 and "系统安全验证" not in h:
                    return h
            except:
                pass
        try:
            import requests as rq
            h = rq.get(url, headers=headers, timeout=min(timeout, 8), verify=False).text
            if h and len(h) > 500 and "系统安全验证" not in h:
                return h
        except:
            pass
        try:
            import urllib.request as uq
            req = uq.Request(url, headers=dict(headers or {}))
            h = uq.urlopen(req, timeout=min(timeout, 8)).read().decode('utf-8', 'ignore')
            if h and len(h) > 500 and "系统安全验证" not in h:
                return h
        except:
            pass
        return ""

    def init(self, extend=""):
        global HOST
        for h in HOSTS:
            try:
                if "枫叶影院" in self._fetch(h, {"User-Agent": UA}):
                    HOST = h
                    break
            except:
                pass

    def _html(self, path):
        url = path if path.startswith("http") else HOST + path
        headers = {"User-Agent": UA, "Connection": "close", "Referer": HOST + "/"}
        for _ in range(2):
            h = self._fetch(url, headers)
            if h and "系统安全验证" not in h and not h.startswith("403"):
                return h
            time.sleep(1)
        return ""

    def _pic(self, u):
        u = (u or "").replace("\\", "").replace("&amp;", "&").strip()
        if not u:
            return ""
        if u.startswith("//"):
            u = "https:" + u
        if not u.startswith("http"):
            u = HOST + u
        if "gimg0.baidu.com" in u:
            return u
        m = re.match(r'https?://([^/]+)(/.*)$', u)
        if m and "hzqingshan.com" in m.group(1):
            return "https://gimg0.baidu.com/gimg/app=2001&n=0&g=0n&fmt=jpeg&src=" + m.group(1) + m.group(2)
        return u

    def homeContent(self, filter=False):
        return {"class": [{"type_id": k, "type_name": v} for k, v in CATEGORIES.items()], "list": self._cards(self._html("/"))}

    def homeVideoContent(self):
        return {"list": self._cards(self._html("/"))}

    def categoryContent(self, tid, pg=1, filter=False, extend=""):
        pn = 1
        try:
            pn = max(int(str(pg)), 1)
        except:
            pass
        t = str(tid)
        if t.isdigit():
            h = self._fetch("%s/index.php/ajax/data?mid=1&tid=%s&page=%s&limit=24" % (HOST, t, pn), {"User-Agent": UA, "Referer": HOST + "/", "X-Requested-With": "XMLHttpRequest"})
            try:
                d = json.loads(h)
            except:
                d = None
            if d and d.get("code") == 1 and d.get("list"):
                items = [{"vod_id": str(v.get("vod_id")), "vod_name": v.get("vod_name") or "", "vod_pic": self._pic(v.get("vod_pic")), "vod_remarks": v.get("vod_remarks") or ""} for v in d.get("list") or []]
                return {"page": pn, "pagecount": max(int(d.get("pagecount") or pn), pn), "limit": 24, "total": int(d.get("total") or 0), "list": items}
        base = "/type/%s" % t if t.isdigit() else "/label/%s" % t
        url = base + ".html" if pn == 1 else base + "/page/%d.html" % pn
        html = self._html(url)
        items = self._cards(html)
        pc = max(self._pagecount(html, pn), pn + 1 if len(items) >= 20 else pn)
        return {"page": pn, "pagecount": pc, "limit": max(len(items), 20), "total": len(items), "list": items}

    def _cards(self, html):
        items, seen = [], set()
        if not html:
            return items
        for m in re.finditer(r'<a[^>]+href="(/detail/(\d+)\.html)"[^>]*>(.*?)</a>', html, re.S):
            vid = m.group(2)
            if vid in seen:
                continue
            g = m.group(3)
            t = re.search(r'alt="([^"]+)"', g) or re.search(r'<span[^>]*>([^<]+)</span>', g)
            name = re.sub(r'\s+', '', t.group(1)).strip() if t else ""
            if not name:
                name = re.sub(r'\s+', '', re.sub(r'<[^>]+>', '', g)).strip()
            if not name or len(name) > 100:
                continue
            p = re.search(r'data-src="([^"]+)"', g) or re.search(r'src="([^"]+)"', g) or re.search(r'background-image:\s*url\(([^)]+)\)', g)
            remark = re.sub(r'<[^>]+>', '', g)
            remark = re.sub(r'\s+', '', remark).replace(name, '').strip('|')
            seen.add(vid)
            items.append({"vod_id": vid, "vod_name": name[:50], "vod_pic": self._pic(p.group(1) if p else ""), "vod_remarks": remark[:20]})
        return items

    def detailContent(self, ids):
        if isinstance(ids, list):
            vid = ids[0] if ids else ""
        else:
            vid = str(ids) if ids else ""
        m = re.search(r'(\d+)', str(vid))
        vid = m.group(1) if m else ""
        if not vid:
            return {"list": []}
        h = self._html("/detail/%s.html" % vid)
        if not h:
            return {"list": []}
        d = {"vod_id": vid, "vod_name": "", "vod_pic": "", "vod_year": "", "vod_area": "", "vod_class": "", "vod_director": "", "vod_actor": "", "vod_content": "", "vod_remarks": "", "vod_play_from": "", "vod_play_url": ""}
        tn = re.search(r'<h3[^>]*class="[^"]*slide-info-title[^"]*"[^>]*>([^<]+)</h3>', h) or re.search(r'alt="《([^》]+)》', h)
        if tn:
            d["vod_name"] = tn.group(1).strip()
        p = re.search(r'data-src="([^"]+)"', h) or re.search(r'src="([^"]+)"', h)
        if p:
            d["vod_pic"] = p.group(1).replace('&amp;', '&')
        for k, f in (("类型", "vod_class"), ("演员", "vod_actor"), ("导演", "vod_director"), ("年份", "vod_year"), ("连载", "vod_remarks")):
            m2 = re.search(r'<strong class="r6">%s:</strong>([^<]*)<' % k, h)
            if m2:
                d[f] = m2.group(1).strip()
        dm = re.search(r'id="height_limit"[^>]*>(.*?)</div>', h, re.S)
        if dm:
            d["vod_content"] = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', dm.group(1))).strip()
            d["vod_content"] = re.sub(r'^简介[:：]?\s*', '', d["vod_content"])[:500]
        froms = re.findall(r'aria-label="(\d+)\s*/\s*\d+"[^>]*>(.*?)</a>', h, re.S)
        eps = re.findall(r'href="(/play/%s-(\d+)-(\d+)\.html)"[^>]*>([^<]+)</a>' % vid, h)
        groups = {}
        for url, sid, nid, ename in eps:
            groups.setdefault(sid, []).append((nid, ename, url))
        pf, pu = [], []
        for sid, fname in froms:
            if sid not in groups or not groups[sid] or sid not in PLAYABLE:
                continue
            fname = re.sub(r'\(\d+\)$', '', re.sub(r'\s+', '', re.sub(r'<[^>]+>', '', fname).replace('&nbsp;', ' ')).strip())
            pf.append(fname or ("线路%s" % sid))
            pu.append("#".join("%s$%s" % (e, u) for n, e, u in groups[sid]))
        if pf:
            d["vod_play_from"] = "$$$".join(pf)
            d["vod_play_url"] = "$$$".join(pu)
        return {"list": [d]}

    def searchContent(self, key, quick=False, pg="1"):
        return {"list": self._cards(self._html("/cupfox-search/-------------.html?wd=" + quote(key))), "page": 1}

    def _resolve(self, base, code):
        h = self._fetch(base + "?url=" + code, {"User-Agent": UA, "Referer": HOST + "/"})
        m = re.search(r'data-te="([^"]+)"', h or "")
        if not m:
            return ""
        try:
            import requests as rq
            r = rq.post(base + "mplayer.php", data={"url": code, "token": m.group(1)}, headers={"User-Agent": UA, "Referer": base}, timeout=15, verify=False)
            j = r.json()
        except:
            try:
                import urllib.request as uq
                import urllib.parse as up
                data = up.urlencode({"url": code, "token": m.group(1)}).encode()
                req = uq.Request(base + "mplayer.php", data=data, headers={"User-Agent": UA, "Referer": base, "Content-Type": "application/x-www-form-urlencoded"})
                j = json.loads(uq.urlopen(req, timeout=15).read().decode("utf-8", "ignore"))
            except:
                return ""
        if j.get("code") == 200 and j.get("url"):
            return j["url"]
        return ""

    def playerContent(self, flag, id, vipFlags=None):
        url = str(id) if id else str(flag)
        if url.startswith("http") and (".m3u8" in url or ".mp4" in url):
            return {"parse": 0, "url": url}
        if not url.startswith("/"):
            url = "/" + url
        h = self._fetch(HOST + url, {"User-Agent": UA, "Referer": HOST + "/"})
        if not h:
            return {"parse": 0, "url": ""}
        pd = re.search(r'player_aaaa=(\{.*?\})\s*</script>', h, re.S)
        if pd:
            try:
                d = json.loads(pd.group(1))
                u = d.get("url") or ""
                if u.startswith("http"):
                    return {"parse": 0, "url": u}
                if u and (d.get("from") or "") in PARSERS:
                    ru = self._resolve(PARSERS[d.get("from")], u)
                    if ru:
                        return {"parse": 0, "url": ru}
            except:
                pass
        m = re.match(r'/play/(\d+)-(\d+)-(\d+)\.html', url)
        if m:
            for alt in sorted(PLAYABLE):
                if alt == m.group(2):
                    continue
                h2 = self._fetch("%s/play/%s-%s-%s.html" % (HOST, m.group(1), alt, m.group(3)), {"User-Agent": UA, "Referer": HOST + "/"})
                if h2:
                    pd2 = re.search(r'player_aaaa=(\{.*?\})\s*</script>', h2, re.S)
                    if pd2:
                        try:
                            d2 = json.loads(pd2.group(1))
                            u2 = d2.get("url") or ""
                            if u2.startswith("http"):
                                return {"parse": 0, "url": u2}
                            if u2 and (d2.get("from") or "") in PARSERS:
                                ru2 = self._resolve(PARSERS[d2.get("from")], u2)
                                if ru2:
                                    return {"parse": 0, "url": ru2}
                        except:
                            pass
        m3u8 = re.search(r'(https?://[^\s"\'<>]+\.m3u8)', h)
        if m3u8:
            return {"parse": 0, "url": m3u8.group(1)}
        return {"parse": 0, "url": ""}

    def localProxy(self, param):
        pass

    def _pagecount(self, html, current_page=1):
        if not html:
            return current_page
        pages = re.findall(r'/(?:type|label)/[^/]+/page/(\d+)\.html', html)
        max_page = current_page
        for p in pages:
            try:
                n = int(p)
                if n > max_page:
                    max_page = n
            except:
                pass
        return max_page
