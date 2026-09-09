# -*- coding: utf-8 -*-
"""
短剧网(htjht.com) Python Spider v2 — 兼容 FongMi/TV (T3) 与 WebHomeTV / PeekPro (T4)
站点: https://www.htjht.com/

v2 修复:
  - 重复内容: ① ID+剧名双重去重(治同剧多ID) ② 相邻页重叠检测自动判定真实末页
    (治翻页后站点重复返回最后一页) ③ 列表解析改为 <li> 块级解析(治封面串位)
  - 速度: 移除 apparent_encoding 慢速编码探测 / 超时收紧 8s /
    分类页缓存60s / 详情缓存 / Session 复用
  - 搜索: 候选地址扩展至 8 种主流CMS规则, 命中自动缓存
"""

import sys
import json
import re
import time
import base64
import threading

sys.path.append('..')

# ===== 兼容导入 =====
try:
    from base.spider import Spider
except ImportError:
    import requests as _rq
    try:
        import urllib3
        urllib3.disable_warnings()
    except Exception:
        pass

    class Spider:
        def fetch(self, url, headers=None, **kw):
            timeout = kw.pop('timeout', 15)
            r = _rq.get(url, headers=headers, timeout=timeout, verify=False, **kw)
            r.encoding = 'utf-8'
            return r

from urllib.parse import quote, urlencode


# ============================================================
# 常量
# ============================================================

HOST = "https://www.htjht.com"
UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")

CLASSES = [
    {"type_name": "短剧", "type_id": "17"},
    {"type_name": "网络电影", "type_id": "14"},
    {"type_name": "动作片", "type_id": "5"},
    {"type_name": "恐怖片", "type_id": "8"},
    {"type_name": "港剧", "type_id": "18"},
    {"type_name": "日剧", "type_id": "20"},
    {"type_name": "英剧", "type_id": "23"},
    {"type_name": "泰剧", "type_id": "24"},
    {"type_name": "动漫", "type_id": "3"},
    {"type_name": "纪录片", "type_id": "12"},
]

_CLASS_FILTERS = {
    "17": ["都市", "古装", "穿越", "重生", "逆袭", "甜宠", "悬疑", "复仇",
           "豪门", "战神", "赘婿", "神医", "修仙", "AI", "漫剧"],
    "14": ["动作", "冒险", "悬疑", "喜剧", "爱情", "犯罪", "奇幻"],
    "5":  ["动作", "冒险", "犯罪", "战争", "武侠", "科幻"],
    "8":  ["恐怖", "惊悚", "悬疑", "灵异"],
    "18": ["时装", "古装", "警匪", "商战", "喜剧"],
    "20": ["爱情", "悬疑", "职场", "家庭", "推理"],
    "23": ["剧情", "犯罪", "悬疑", "喜剧"],
    "24": ["爱情", "剧情", "家庭", "喜剧"],
    "3":  ["热血", "冒险", "恋爱", "搞笑", "奇幻", "治愈"],
    "12": ["纪录", "纪实"],
}
_YEAR_FILTER = {"key": "year", "name": "年份", "value": [
    {"n": "全部", "v": ""},
    {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"},
    {"n": "2024", "v": "2024"}, {"n": "2023", "v": "2023"},
    {"n": "2022", "v": "2022"}, {"n": "2021", "v": "2021"},
]}
_BY_FILTER = {"key": "by", "name": "排序", "value": [
    {"n": "最新", "v": "time"}, {"n": "最热", "v": "hits"}, {"n": "评分", "v": "score"},
]}

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    FILTERS[tid] = [
        {"key": "class", "name": "类型",
         "value": [{"n": "全部", "v": ""}] + [{"n": k, "v": k} for k in _CLASS_FILTERS.get(tid, [])]},
        _YEAR_FILTER,
        _BY_FILTER,
    ]

# 搜索候选: 8 种主流CMS规则, 逐个尝试, 命中缓存
SEARCH_URLS = [
    lambda wd: HOST + "/vod/search.html?wd=" + quote(wd, safe=""),          # 苹果CMS
    lambda wd: HOST + "/?m=vod-search-wd-" + quote(wd, safe="") + ".html",  # 海洋CMS伪静态
    lambda wd: HOST + "/index.php?m=vod-search-wd-" + quote(wd, safe="") + ".html",
    lambda wd: HOST + "/search.php?searchword=" + quote(wd, safe=""),       # 海洋CMS旧版
    lambda wd: HOST + "/?m=vod-search&wd=" + quote(wd, safe=""),
    lambda wd: HOST + "/search/" + quote(wd, safe=""),
    lambda wd: HOST + "/s/" + quote(wd, safe=""),
    lambda wd: HOST + "/e/search/index.php?keyboard=" + quote(wd, safe="") + "&show=title",  # 帝国CMS
]

API = HOST + "/api.php/provide/vod/"


# ============================================================
# Spider 主类
# ============================================================

class Spider(Spider):

    def getName(self):
        return "短剧网"

    def init(self, extend=""):
        self.extend = "" if isinstance(extend, list) else (extend or "")
        self.header = {
            "User-Agent": UA,
            "Referer": HOST + "/",
            "Accept": "text/html,application/json,*/*",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        self._sess = None
        try:
            import requests
            self._sess = requests.Session()
            self._sess.verify = False
            self._sess.headers.update(self.header)
        except Exception:
            pass

        self._api_state = 0
        self._search_ok = None
        self._home_cache, self._home_time = [], 0
        self._cat_cache = {}        # 分类页缓存 60s
        self._detail_cache = {}     # 详情缓存(避免APP重复进详情反复请求)
        self._last_ids = set()      # 上一页ID集合(末页重叠检测)

    # ===== 网络工具(快速编码, 不用 apparent_encoding) =====
    def _fetch(self, url, timeout=8):
        if self._sess is not None:
            return self._sess.get(url, headers=self.header, timeout=timeout)
        return self.fetch(url, headers=self.header, timeout=timeout)

    def _html(self, url, timeout=8):
        try:
            r = self._fetch(url, timeout=timeout)
            raw = r.content
            enc = r.encoding
            if not enc or enc.lower() == 'iso-8859-1':
                head = raw[:1500].decode('utf-8', 'ignore')
                m = re.search(r'charset=["\']?([\w-]+)', head, re.I)
                enc = m.group(1) if m else 'utf-8'
            return raw.decode(enc, 'ignore')
        except Exception:
            return ""

    def _json(self, url, timeout=8):
        try:
            r = self._fetch(url, timeout=timeout)
            return json.loads(r.text)
        except Exception:
            return None

    @staticmethod
    def _abs(url):
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return HOST + url
        return url

    # ===== 苹果CMS API 探测 =====
    def _api_json(self, params):
        if self._api_state == -1:
            return None
        qs = urlencode(params)
        for u in (API + "?" + qs, API + "at/json/?" + qs):
            data = self._json(u, timeout=8)
            if isinstance(data, dict) and (data.get("code") == 1 or "list" in data):
                self._api_state = 1
                return data
        self._api_state = -1
        return None

    # ===== 列表解析 v2: <li> 块级解析, ID+名称双重去重 =====
    def _parse_list(self, html):
        items = []
        seen_id, seen_name = set(), set()
        if not html:
            return items
        for m in re.finditer(
                r'href="(?:https?://(?:www\.)?htjht\.com)?/qadkuxkd/(\d+)\.html"', html):
            vid, start, end = m.group(1), m.start(), m.end()
            if vid in seen_id:
                continue
            # 定位所在 <li> 块, 避免 ±600 窗口串位
            li0 = html.rfind('<li', max(0, start - 3000), start)
            li1 = html.find('</li>', end)
            block = html[li0 if li0 > 0 else max(0, start - 300):
                        (li1 + 5) if li1 > 0 else end + 300]
            anchor = html[start:end]

            name, pic = "", ""
            im = re.search(r'<img[^>]+(?:data-original|data-src|src)="([^"]+)"[^>]*>', anchor)
            if not im:
                im = re.search(r'<img[^>]+(?:data-original|data-src|src)="([^"]+)"[^>]*>', block)
            if im:
                pic = self._abs(im.group(1))
                am = re.search(r'(?:alt|title)="([^"]{1,60})"', im.group(0))
                if am:
                    name = am.group(1).strip()
            if not name:
                am = re.search(r'(?:alt|title)="([^"]{1,60})"', anchor)
                if am:
                    name = am.group(1).strip()
            if not name:
                am = re.search(r'>\s*([^<>{}\[\]]{2,40}?)\s*</a>', anchor)
                if am:
                    name = am.group(1).strip()
            if not name:
                am = re.search(r'(?:alt|title)="([^"]{1,60})"', block)
                if am:
                    name = am.group(1).strip()

            norm = re.sub(r'[\s\W_]+', '', name)
            # 同名不同ID / 同ID重复入口 → 全部跳过
            if norm and norm in seen_name:
                continue
            if not name and not pic:
                continue  # 栏目/广告链接
            seen_id.add(vid)
            if norm:
                seen_name.add(norm)

            rem = ""
            rm = re.search(r'(全\d+[集话]|更新至\d+[集话]?|完结|HD|\d{4})', block)
            if rm:
                rem = rm.group(1)
            txt = re.sub(r'<[^>]+>', ' ', block)
            items.append({
                "vod_id": vid, "vod_name": name, "vod_pic": pic,
                "vod_remarks": rem or "HD", "_txt": txt,
            })
        return items

    # ===== 详情页解析 =====
    def _parse_detail(self, html, vid):
        if not html:
            return None
        d = {"vod_id": str(vid)}

        def field(label):
            m = re.search(label + r'[::\s]*([^<>\n]{1,80})', html)
            return m.group(1).strip() if m else ""

        nm = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        d["vod_name"] = nm.group(1).strip() if nm else ""
        pm = re.search(r'property="og:image"\s+content="([^"]+)"', html)
        if not pm:
            pm = re.search(r'<img[^>]+class="[^"]*(?:pic|cover|thumb)[^"]*"[^>]+src="([^"]+)"', html)
        d["vod_pic"] = self._abs(pm.group(1)) if pm else ""
        d["vod_year"] = field('年份')
        d["vod_area"] = field('地区')
        d["type_name"] = field('类型')
        d["vod_actor"] = field('主演')
        d["vod_director"] = field('导演')
        cm = re.search(r'(?:剧情(?:介绍)?|简介|剧情简介)</?[^>]*>?\s*(.{20,600}?)<(?:/div|/p|h2|h3)', html, re.S)
        if not cm:
            cm = re.search(r'剧情介绍(.{20,600})', re.sub(r'<[^>]+>', '', html), re.S)
        d["vod_content"] = re.sub(r'<[^>]+>', '', cm.group(1)).strip()[:500] if cm else ""
        rm = re.search(r'(全\d+[集话]|更新至\d+[集话]?|完结|HD)', html)
        d["vod_remarks"] = rm.group(1) if rm else "HD"

        lines = {}
        for m in re.finditer(
                r'href="(?:https?://(?:www\.)?htjht\.com)?/adeplay/%s-(\d+)-(\d+)\.html"[^>]*>([^<]*)' % vid,
                html):
            sid, num, epname = int(m.group(1)), int(m.group(2)), m.group(3).strip()
            if sid not in lines:
                lines[sid] = {"eps": {}}
            lines[sid]["eps"][num] = epname or ("第%d集" % num)

        play_from, play_url = [], []
        for i, (sid, info) in enumerate(sorted(lines.items())):
            eps = info["eps"]
            if not eps:
                continue
            ep_list = ["%s$%s" % (eps[n], "/adeplay/%s-%d-%d.html" % (vid, sid, n))
                       for n in sorted(eps)]
            play_from.append("线路%d" % (i + 1))
            play_url.append("#".join(ep_list))
        d["play_from"], d["play_url"] = play_from, play_url
        return d

    # ===== 播放页直链提取 =====
    def _parse_play_url(self, html):
        if not html:
            return ""
        m = re.search(r'player_aaaa\s*=\s*(\{.*?\})', html, re.S)
        if m:
            try:
                info = json.loads(m.group(1))
                url = info.get("url", "")
                if info.get("encrypt") == 1:
                    try:
                        url = base64.b64decode(url).decode("utf-8", "ignore")
                    except Exception:
                        pad = 4 - len(url) % 4
                        url = base64.urlsafe_b64decode(url + "=" * pad).decode("utf-8", "ignore")
                if url and re.search(r'\.(m3u8|mp4|flv)', url, re.I):
                    return url.replace("\\/", "/")
            except Exception:
                pass
        for pat in (r'"url"\s*:\s*"([^"]+?\.(?:m3u8|mp4|flv)[^"]*)"',
                    r'"link"\s*:\s*"([^"]+?\.(?:m3u8|mp4|flv)[^"]*)"'):
            m = re.search(pat, html)
            if m:
                return m.group(1).replace("\\/", "/")
        for pat in (r'var\s+(?:now|video_url|vod_url|play_url|url)\s*=\s*["\']([^"\']+?\.(?:m3u8|mp4|flv)[^"\']*)',
                    r'(?:now|video_url|vod_url)\s*[:=]\s*["\']([^"\']+?\.(?:m3u8|mp4|flv)[^"\']*)'):
            m = re.search(pat, html)
            if m:
                return m.group(1)
        m = re.search(r'(https?://[^"\'<>\s]+?\.m3u8[^"\'<>\s]*)', html)
        if m:
            return m.group(1)
        m = re.search(r'(https?://[^"\'<>\s]+?\.mp4[^"\'<>\s]*)', html)
        if m:
            return m.group(1)
        # iframe 直链兜底
        m = re.search(r'<iframe[^>]+src="(https?://[^"]+?\.(?:m3u8|mp4)[^"]*)"', html)
        if m:
            return m.group(1)
        return ""

    @staticmethod
    def _filter(items, ext):
        if not ext:
            return items
        kw = (ext.get("class") or "").strip()
        yr = (ext.get("year") or "").strip()
        if not kw and not yr:
            return items
        out = []
        for it in items:
            txt = it.get("_txt", "")
            if kw and kw not in txt:
                continue
            if yr and yr not in txt:
                continue
            out.append(it)
        return out

    @staticmethod
    def _card(it):
        return {k: v for k, v in it.items() if not k.startswith("_")}

    # ============================================================
    # 首页
    # ============================================================
    def homeContent(self, filter):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        now = int(time.time())
        if self._home_cache and now - self._home_time < 600:
            return {"list": self._home_cache}

        data = self._api_json({"ac": "videolist", "pg": "1", "t": "17"})
        if data and data.get("list"):
            vods, seen = [], set()
            for v in data["list"]:
                norm = re.sub(r'[\s\W_]+', '', v.get("vod_name", ""))
                if norm in seen:
                    continue
                seen.add(norm)
                vods.append({
                    "vod_id": str(v.get("vod_id", "")),
                    "vod_name": v.get("vod_name", ""),
                    "vod_pic": self._abs(v.get("vod_pic", "")),
                    "vod_remarks": v.get("vod_remarks", "") or "HD",
                })
            if vods:
                self._home_cache = vods[:50]
                self._home_time = now
                return {"list": self._home_cache}

        def worker(tid, out, lock):
            try:
                its = self._parse_list(self._html("%s/azdjsku/%s-1.html" % (HOST, tid), timeout=8))
                with lock:
                    out.extend(its)
            except Exception:
                pass

        merged, threads, lock = [], [], threading.Lock()
        for c in CLASSES[:4]:
            t = threading.Thread(target=worker, args=(c["type_id"], merged, lock))
            t.start()
            threads.append(t)
        for t in threads:
            t.join(timeout=10)

        # ID + 剧名双重去重(不同分类页也常出现同一部剧)
        seen_id, seen_name, vods = set(), set(), []
        for it in merged:
            norm = re.sub(r'[\s\W_]+', '', it.get("vod_name", ""))
            if it["vod_id"] in seen_id or (norm and norm in seen_name):
                continue
            seen_id.add(it["vod_id"])
            if norm:
                seen_name.add(norm)
            vods.append(self._card(it))
        self._home_cache = vods[:50]
        self._home_time = now
        return {"list": self._home_cache}

    # ============================================================
    # 分类
    # ============================================================
    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = max(int(pg or 1), 1)
        except Exception:
            page = 1
        ext = {}
        if isinstance(extend, dict):
            ext = extend
        elif isinstance(extend, str) and extend:
            try:
                ext = json.loads(extend)
            except Exception:
                ext = {}

        # 分类页缓存 60s(翻页/回退不重复请求)
        ckey = "%s|%d|%s|%s|%s" % (tid, page, ext.get("class", ""), ext.get("year", ""), ext.get("by", ""))
        ck = self._cat_cache.get(ckey)
        if ck and int(time.time()) - ck[0] < 60:
            return ck[1]

        params = {"ac": "videolist", "t": str(tid), "pg": str(page)}
        if ext.get("class"):
            params["class"] = ext["class"]
        if ext.get("year"):
            params["year"] = ext["year"]
        if ext.get("by"):
            params["by"] = ext["by"]
        data = self._api_json(params)
        if data:
            vods = []
            for v in data.get("list", []):
                vods.append({
                    "vod_id": str(v.get("vod_id", "")),
                    "vod_name": v.get("vod_name", ""),
                    "vod_pic": self._abs(v.get("vod_pic", "")),
                    "vod_remarks": v.get("vod_remarks", "") or "HD",
                })
            if vods or page > 1:
                result = {"list": vods, "page": page,
                          "pagecount": int(data.get("pagecount", page)),
                          "limit": 20, "total": int(data.get("total", 0))}
                self._cat_cache[ckey] = (int(time.time()), result)
                return result

        html = self._html("%s/azdjsku/%s-%d.html" % (HOST, tid, page), timeout=10)
        items = self._parse_list(html)

        # ★ 末页重叠检测: 当前页与上一页ID重合过半 = 站点重复返回, 已到末页
        cur_ids = set(it["vod_id"] for it in items)
        if page > 1 and cur_ids and self._last_ids:
            overlap = len(cur_ids & self._last_ids) / float(len(cur_ids))
            if overlap > 0.5:
                result = {"list": [], "page": page, "pagecount": page - 1,
                          "limit": 20, "total": (page - 1) * 20}
                self._cat_cache[ckey] = (int(time.time()), result)
                return result
        self._last_ids = cur_ids

        items = self._filter(items, ext)

        nums = [int(x) for x in re.findall(r'/azdjsku/%s-(\d+)\.html' % tid, html)] if html else []
        if nums:
            pagecount = max(nums)
        elif len(items) < 12 and page > 1:
            pagecount = page
        else:
            pagecount = page + 1   # 让APP继续尝试下一页, 交给重叠检测兜底

        result = {"list": [self._card(it) for it in items], "page": page,
                  "pagecount": pagecount, "limit": 20, "total": page * 20}
        self._cat_cache[ckey] = (int(time.time()), result)
        return result

    # ============================================================
    # 详情
    # ============================================================
    def detailContent(self, ids):
        if isinstance(ids, str):
            ids = [ids]
        vid = str(ids[0])

        hit = self._detail_cache.get(vid)
        if hit:
            return {"list": [hit]}

        data = self._api_json({"ac": "detail", "ids": vid})
        if data and data.get("list"):
            d = data["list"][0]
            vod = {
                "vod_id": vid,
                "vod_name": d.get("vod_name", ""),
                "vod_pic": self._abs(d.get("vod_pic", "")),
                "type_name": d.get("type_name", ""),
                "vod_year": d.get("vod_year", ""),
                "vod_area": d.get("vod_area", ""),
                "vod_remarks": d.get("vod_remarks", "") or "HD",
                "vod_actor": d.get("vod_actor", ""),
                "vod_director": d.get("vod_director", ""),
                "vod_content": re.sub(r'<[^>]+>', '', d.get("vod_content", ""))[:500],
                "vod_play_from": d.get("vod_play_from", "") or "短剧网",
                "vod_play_url": d.get("vod_play_url", ""),
            }
            self._detail_cache[vid] = vod
            return {"list": [vod]}

        html = ""
        for _ in range(2):
            html = self._html("%s/qadkuxkd/%s.html" % (HOST, vid), timeout=10)
            if html and "/adeplay/" in html:
                break
            time.sleep(0.3)
        d = self._parse_detail(html, vid) if html else None
        if not d or not d["play_url"]:
            return {"list": []}
        vod = {
            "vod_id": vid,
            "vod_name": d.get("vod_name", ""),
            "vod_pic": d.get("vod_pic", ""),
            "type_name": d.get("type_name", ""),
            "vod_year": d.get("vod_year", ""),
            "vod_area": d.get("vod_area", ""),
            "vod_remarks": d.get("vod_remarks", ""),
            "vod_actor": d.get("vod_actor", ""),
            "vod_director": d.get("vod_director", ""),
            "vod_content": d.get("vod_content", ""),
            "vod_play_from": "$$$".join(d["play_from"]),
            "vod_play_url": "$$$".join(d["play_url"]),
        }
        self._detail_cache[vid] = vod
        return {"list": [vod]}

    # ============================================================
    # 搜索
    # ============================================================
    def searchContent(self, key, quick, pg="1"):
        key = (key or "").strip()
        if not key:
            return {"list": []}

        data = self._api_json({"ac": "videolist", "wd": key, "pg": str(pg or 1)})
        if data and data.get("list"):
            vods = []
            for v in data["list"]:
                vods.append({
                    "vod_id": str(v.get("vod_id", "")),
                    "vod_name": v.get("vod_name", ""),
                    "vod_pic": self._abs(v.get("vod_pic", "")),
                    "vod_remarks": v.get("vod_remarks", "") or "HD",
                })
            return {"list": vods}

        # 候选地址逐个尝试, 命中后缓存不再探测
        order = [self._search_ok] if self._search_ok else SEARCH_URLS
        order = [o for o in order if o]
        for make in order:
            try:
                items = self._parse_list(self._html(make(key), timeout=8))
            except Exception:
                items = []
            if items:
                self._search_ok = make
                return {"list": [self._card(it) for it in items[:30]]}
        return {"list": []}

    # ============================================================
    # 播放
    # ============================================================
    def playerContent(self, flag, id, vipFlags):
        url = str(id or "").replace("\\/", "/")
        if not url:
            return {"parse": 0, "playUrl": "", "url": ""}

        # 1) 直链直出
        if re.search(r'\.(m3u8|mp4|flv)', url, re.I):
            is_m3u8 = ".m3u8" in url.lower()
            return {
                "parse": 0, "playUrl": "", "url": url,
                "header": {"User-Agent": UA, "Referer": HOST + "/"},
                "format": "application/x-mpegURL" if is_m3u8 else "",
                "contentType": "application/x-mpegURL" if is_m3u8 else "",
            }

        # 2) 站内播放页: 8s 单次请求提取直链, 不重试(保证点播速度)
        if "/adeplay/" in url:
            play_page = self._abs(url)
            html = self._html(play_page, timeout=8)
            media = self._parse_play_url(html)
            if media:
                is_m3u8 = ".m3u8" in media.lower()
                ref = re.search(r'(https?://[^/]+)', play_page)
                return {
                    "parse": 0, "playUrl": "", "url": media,
                    "header": {"User-Agent": UA,
                               "Referer": ref.group(1) + "/" if ref else HOST + "/"},
                    "format": "application/x-mpegURL" if is_m3u8 else "",
                    "contentType": "application/x-mpegURL" if is_m3u8 else "",
                }
            return {"parse": 1, "playUrl": "", "url": play_page,
                    "header": {"User-Agent": UA, "Referer": HOST + "/"}}

        # 3) 其他外链 → 壳子嗅探
        return {"parse": 1, "playUrl": "", "url": url,
                "header": {"User-Agent": UA, "Referer": HOST + "/"}}

    def localProxy(self, param):
        return [200, "video/MP2T", b"", ""]

    def destroy(self):
        try:
            if self._sess is not None:
                self._sess.close()
        except Exception:
            pass

    def close(self):
        self.destroy()
