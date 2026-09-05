# -*- coding: utf-8 -*-
import sys
import re
import json
from urllib.parse import urljoin, quote, unquote, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

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

HOST = "https://www.58hu.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# 封面URL中这些域名已失效，对应影片会被过滤掉
DEAD_IMG_HOSTS = {"image.caiji.cyou", "wim.xrc888.com"}

CATEGORIES = {
    "1": "电影", "2": "电视剧", "3": "综艺",
    "4": "动漫", "21": "体育",
}

# 子分类: {父分类ID: {子分类ID: 名称}}
SUB_CATS = {
    "1": {"6": "动作片", "7": "喜剧片", "8": "爱情片", "9": "科幻片", "10": "恐怖片",
           "11": "剧情片", "12": "战争片", "22": "纪录片"},
    "2": {"13": "国产剧", "14": "港台剧", "15": "日韩剧", "16": "欧美剧", "24": "海外剧",
           "29": "BI番剧", "30": "BI国创", "31": "BI电影"},
    "3": {"28": "最新综艺"},
    "4": {"27": "最新动漫"},
    "21": {"26": "体育赛事"},
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
        try: pn = max(int(str(pg)), 1)
        except: pass
        cat = str(tid)
        try:
            url = self._build_category_url(cat, pn, extend)
            r = self.fetch(url, headers={"User-Agent": UA}, timeout=30000)
            html = r.text if hasattr(r, 'text') else str(r)
            cat_name = CATEGORIES.get(cat, "")
            items = self._items(html, cat_filter=cat_name)
            # 过滤掉没有封面或没有可播放线路的影片（并发检查）
            items = self._filter_items(items)
            pc = self._pagecount(html, pn)
            return {"page": pn, "pagecount": pc, "limit": 30, "total": len(items), "list": items}
        except:
            return {"page": pn, "pagecount": 1, "limit": 30, "total": 0, "list": []}

    def _build_category_url(self, cat, pn, extend=""):
        """构建分类URL，支持筛选参数"""
        # 解析extend中的筛选条件
        ext = {}
        if extend and isinstance(extend, str) and extend.strip():
            try:
                ext = json.loads(extend)
            except:
                pass

        # 判断是否为子分类（在SUB_CATS中）
        is_sub = False
        for parent, subs in SUB_CATS.items():
            if cat in subs:
                is_sub = True
                break

        # 所有分类用 vod/show 模式
        parts = []
        # class/类型
        cls = ext.get("class") or ""
        if cls and cls != "全部":
            parts.append(f"class/{quote(cls)}")
        # area/地区
        area = ext.get("area") or ""
        if area and area != "全部":
            parts.append(f"area/{quote(area)}")
        # year/年代
        year = ext.get("year") or ""
        if year and year != "全部":
            parts.append(f"year/{quote(year)}")
        # letter/字母
        letter = ext.get("letter") or ""
        if letter and letter != "全部":
            parts.append(f"letter/{quote(letter)}")
        # sort/排序
        sort = ext.get("sort") or ""
        if sort:
            parts.append(f"by/{quote(sort)}")
        # page
        if pn > 1:
            parts.append(f"page/{pn}")
        filters = "/".join(parts)
        if filters:
            return f"{HOST}/index.php/vod/show/{filters}/id/{cat}.html"
        else:
            return f"{HOST}/index.php/vod/show/id/{cat}.html"

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
            r = self.fetch(f"{HOST}/index.php/vod/detail/id/{vid}.html", headers={"User-Agent": UA}, timeout=30000)
            h = r.text if hasattr(r, 'text') else str(r)
        except:
            return {"list": []}
        d = {"vod_id": vid, "vod_name": "", "vod_pic": "", "vod_year": "",
             "vod_area": "", "vod_class": "", "vod_director": "", "vod_actor": "",
             "vod_content": "", "vod_remarks": "", "vod_play_from": "", "vod_play_url": ""}
        # 标题
        tn = re.search(r'<h1[^>]*>(.*?)</h1>', h)
        if tn:
            d["vod_name"] = re.sub(r'<[^>]+>', '', tn.group(1)).strip()
        if not d["vod_name"]:
            tn = re.search(r'<title>(.*?)</title>', h)
            if tn:
                d["vod_name"] = tn.group(1).split("-")[0].strip()
        # 封面: 优先 class="pic-img video-pic" 里的img
        p = re.search(r'class="pic-img video-pic"[\s\S]{0,100}?<img[^>]*src="(https?://[^"]+)"', h, re.I)
        if not p:
            p = re.search(r'data-src="(https?://[^"]+)"', h)
        if not p:
            p = re.search(r'src="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"', h, re.I)
        if p:
            pic_url = p.group(1)
            if pic_url.startswith("http://"):
                pic_url = pic_url.replace("http://", "https://", 1)
            d["vod_pic"] = pic_url
        # 简介
        desc_m = re.search(r'简介[\s\S]{0,30}?>([\s\S]*?)</div>', h)
        if desc_m:
            d["vod_content"] = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', desc_m.group(1))).strip()[:500]
        if not d["vod_content"]:
            desc_m = re.search(r'class="[^"]*desc[^"]*"[^>]*>([\s\S]*?)</div>', h)
            if desc_m:
                d["vod_content"] = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', desc_m.group(1))).strip()[:500]
        # 年份
        ym = re.search(r'(\d{4})', d.get("vod_name", ""))
        if ym: d["vod_year"] = ym.group(1)
        # 地区/分类/导演/主演等
        info_items = re.findall(r'<li[^>]*class="[^"]*data[^"]*"[^>]*>([\s\S]*?)</li>', h)
        for item in info_items:
            clean = re.sub(r'<[^>]+>', '', item).strip()
            if '导演' in item and not d["vod_director"]:
                d["vod_director"] = clean.replace('导演', '').strip().rstrip('，').strip()
            elif '主演' in item and not d["vod_actor"]:
                d["vod_actor"] = clean.replace('主演', '').strip().rstrip('，').strip()
            elif '类型' in item and not d["vod_class"]:
                d["vod_class"] = clean.replace('类型', '').strip()
            elif '地区' in item and not d["vod_area"]:
                d["vod_area"] = clean.replace('地区', '').strip()
        # 备注
        rm = re.search(r'class="[^"]*remarks?[^"]*"[^>]*>([^<]+)<', h)
        if rm: d["vod_remarks"] = rm.group(1).strip()
        # 播放源（只保留m3u8直链线路）
        try:
            pf, pu = [], []
            line_map = {}
            for sid, name in re.findall(r'id="#con_playlist_(\d+)"[^>]*class="gico[^"]*"[^>]*>([^<]+)</a>', h):
                line_map[sid] = name.strip()
            for m in re.finditer(r'<ul[^>]*id="con_playlist_(\d+)"[^>]*>([\s\S]*?)</ul>', h):
                sid = m.group(1)
                content = m.group(2)
                eps = re.findall(r'href="(/index\.php/vod/play/id/\d+/sid/\d+/nid/\d+\.html)"[^>]*>([\s\S]*?)</a>', content)
                if not eps:
                    continue
                line_name = line_map.get(sid, f"线路{sid}")
                # 预检第1集：只保留返回m3u8直链的线路
                first_url = urljoin(HOST, eps[0][0])
                try:
                    rp = self.fetch(first_url, headers={"User-Agent": UA}, timeout=10000)
                    hp = rp.text if hasattr(rp, 'text') else str(rp)
                    pd = re.search(r'player_data\s*=\s*(\{[\s\S]*?\})\s*[;<]', hp)
                    if not pd:
                        continue
                    pdata = json.loads(pd.group(1))
                    purl = pdata.get("url", "")
                    if not purl or not purl.startswith("http") or ".m3u8" not in purl:
                        continue
                except:
                    continue
                ep_list = []
                for url, name in eps:
                    clean_name = re.sub(r'<[^>]+>', '', name).strip()
                    ep_list.append(f"{clean_name}${urljoin(HOST, url)}")
                if ep_list:
                    pf.append(line_name)
                    pu.append("#".join(ep_list))
            if pf:
                d["vod_play_from"] = "$$$".join(pf)
                d["vod_play_url"] = "$$$".join(pu)
        except:
            pass
        return {"list": [d]}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            pn = 1
            try: pn = int(str(pg))
            except: pass
            url = f"{HOST}/index.php/vod/search/wd/{quote(key)}"
            if pn > 1:
                url += f"/page/{pn}"
            url += ".html"
            r = self.fetch(url, headers={"User-Agent": UA}, timeout=30000)
            html = r.text if hasattr(r, 'text') else str(r)
            items = self._items(html)
            return {"list": items, "page": pn}
        except:
            return {"list": []}

    def playerContent(self, flag, id, vipFlags=None):
        url = str(id) if id else str(flag)
        if url.startswith("http") and ".m3u8" in url:
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
        pd = re.search(r'player_data\s*=\s*(\{[\s\S]*?\})\s*[;<]', h)
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
        return {"url": ""}

    def localProxy(self, param):
        pass

    def _filter_items(self, items):
        """过滤：去掉没封面的 + 并发检查线路，去掉没有LZ/YZ的"""
        if not items:
            return items
        # 先去掉没封面的
        items = [it for it in items if it.get("vod_pic")]
        if not items:
            return items
        # 并发检查每个影片是否有LZ/YZ线路
        playable_ids = set()
        def check(it):
            return it["vod_id"], self._check_playable(it["vod_id"])
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(check, it): it for it in items}
            for future in as_completed(futures):
                try:
                    vid, ok = future.result()
                    if ok:
                        playable_ids.add(vid)
                except:
                    pass
        return [it for it in items if it["vod_id"] in playable_ids]

    def _check_playable(self, vid):
        """检查详情页是否有LZ或YZ线路名"""
        try:
            r = self.fetch(f"{HOST}/index.php/vod/detail/id/{vid}.html", headers={"User-Agent": UA}, timeout=5000)
            h = r.text if hasattr(r, 'text') else str(r)
            lines = re.findall(r'id="#con_playlist_\d+"[^>]*class="gico[^"]*"[^>]*>([^<]+)</a>', h)
            for name in lines:
                if "LZ" in name or "YZ" in name:
                    return True
            return False
        except:
            return False

    def _pagecount(self, html, current_page=1):
        # 匹配分页链接: /index.php/vod/show/.../page/2/...
        pages = re.findall(r'/page/(\d+)/', html)
        max_page = current_page
        for p in pages:
            try:
                n = int(p)
                if n > max_page:
                    max_page = n
            except:
                pass
        # 如果当前页是最大且还有下一页
        has_next = re.search(r'>下一页<', html)
        if has_next and max_page <= current_page + 5:
            max_page = current_page + 5
        return max_page

    def _items(self, html, cat_filter=""):
        items, seen = [], set()
        # 分类过滤关键词映射
        ANIME_KEYWORDS = {'动漫', '动画', '卡通', '番剧', '番'}
        TV_KEYWORDS = {'电视剧', '国产剧', '港台剧', '日韩剧', '欧美剧', '海外剧'}
        MOVIE_KEYWORDS = {'电影', '动作片', '喜剧片', '爱情片', '科幻片', '恐怖片', '剧情片', '战争片', '纪录片'}
        for m in re.finditer(r'href="(/index\.php/vod/detail/id/(\d+)\.html)"[^>]*title="([^"]*)"', html):
            vid = m.group(2)
            if vid in seen:
                continue
            name = m.group(3).strip()
            if not name or len(name) > 100:
                continue
            after = html[m.end():m.end()+2000]
            # 封面: 优先 data-original，再 data-src，再 src。HTTP升级为HTTPS
            cover = re.search(r'data-original="(https?://[^"]+)"', after)
            if not cover:
                cover = re.search(r'data-src="(https?://[^"]+)"', after)
            if not cover:
                cover = re.search(r'src="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"', after, re.I)
            pic_url = cover.group(1) if cover else ""
            if pic_url.startswith("http://"):
                pic_url = pic_url.replace("http://", "https://", 1)
            # 过滤失效图床域名
            if pic_url:
                host = urlparse(pic_url).hostname or ""
                if host in DEAD_IMG_HOSTS:
                    pic_url = ""
            # 备注
            remark = re.search(r'class="titles"[^>]*>([^<]+)<', after)
            if not remark:
                remark = re.search(r'class="[^"]*prb[^"]*"[^>]*>([^<]+)<', after)
            # 分类过滤: 从 mcat 提取分类标签（注意span内可能有换行）
            mcat_raw = re.search(r'class="mcat">([\s\S]*?)</div>', after)
            if mcat_raw and cat_filter:
                mcat_text = re.sub(r'<[^>]+>', '', mcat_raw.group(1)).strip()
                if cat_filter == "电视剧":
                    if any(k in mcat_text for k in ANIME_KEYWORDS):
                        continue
                elif cat_filter == "动漫":
                    if any(k in mcat_text for k in TV_KEYWORDS):
                        continue
            seen.add(vid)
            items.append({
                "vod_id": vid,
                "vod_name": name[:50],
                "vod_pic": pic_url,
                "vod_remarks": remark.group(1).strip() if remark else "",
            })
        return items
