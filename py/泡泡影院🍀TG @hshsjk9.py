# -*- coding: utf-8 -*-
import sys
import re
import json
from urllib.parse import urljoin, quote

sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def fetch(self, url, headers=None, **kw):
            import requests as rq
            kw.pop('timeout', None)
            r = rq.get(url, headers=headers, timeout=15, **kw)
            r.encoding = 'utf-8'
            return r

HOST = "https://www.jdzsm.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

CATEGORIES = {
    "1": "电影", "2": "电视剧", "3": "综艺片", "4": "动漫",
    "24": "短剧", "6": "动作片", "7": "喜剧片", "8": "爱情片",
    "9": "科幻片", "10": "剧情片", "11": "战争片", "41": "动画片",
    "39": "恐怖片", "12": "记录片", "13": "国产剧", "14": "香港剧",
    "15": "韩国剧", "16": "欧美剧", "22": "台湾剧", "21": "日本剧",
    "20": "泰国剧", "23": "海外剧", "25": "大陆综艺", "45": "Netflix频道",
}


class Spider(BaseSpider):

    def init(self, extend=""):
        global HOST
        if extend and extend.startswith('http'):
            HOST = extend.rstrip('/')

    # ── 首页分类 ──────────────────────────────────────────
    def homeContent(self, filter=False):
        r = {"class": [], "list": []}
        for k, v in CATEGORIES.items():
            r["class"].append({"type_id": k, "type_name": v})
        return r

    # ── 首页推荐 ──────────────────────────────────────────
    def homeVideoContent(self):
        try:
            h = self._fetch_page(HOST)
            return {"list": self._parse_items(h)}
        except:
            return {"list": []}

    # ── 分类列表 ──────────────────────────────────────────
    def categoryContent(self, tid, pg=1, filter=False, extend=""):
        pn = 1
        try:
            pn = max(int(str(pg)), 1)
        except:
            pass
        try:
            url = f"{HOST}/cast/{tid}" + (f"-{pn}.html" if pn > 1 else ".html")
            h = self._fetch_page(url)
            items = self._parse_items(h)
            return {
                "page": pn,
                "pagecount": self._pagecount(h, pn),
                "limit": 30,
                "total": len(items),
                "list": items,
            }
        except:
            return {"page": pn, "pagecount": 1, "limit": 30, "total": 0, "list": []}

    # ── 详情 ──────────────────────────────────────────────
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
            h = self._fetch_page(f"{HOST}/drama/{vid}.html")
        except:
            return {"list": []}

        d = {
            "vod_id": vid, "vod_name": "", "vod_pic": "", "vod_year": "",
            "vod_area": "", "vod_class": "", "vod_director": "", "vod_actor": "",
            "vod_content": "", "vod_remarks": "", "vod_play_from": "", "vod_play_url": "",
        }

        # 标题
        tn = re.search(r'<title>(.*?)</title>', h)
        if tn:
            raw = tn.group(1).strip()
            nm = re.search(r'[《](.+?)[》]', raw)
            d["vod_name"] = nm.group(1) if nm else raw.split("_")[0].split("-")[0].strip()[:50]

        # 封面
        cover = re.search(r'myui-vodlist__thumb[^>]*background:\s*url\(([^)]+)\)', h)
        if not cover:
            cover = re.search(r'data-src="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"', h, re.I)
        if cover:
            d["vod_pic"] = cover.group(1).strip()

        # 简介
        dm = re.search(r'name="description"\s+content="([^"]*)"', h)
        if dm:
            d["vod_content"] = dm.group(1).strip()[:500]

        # 元信息 - 从 detail 区域的 span 文本提取
        detail_texts = self._extract_detail_texts(h)
        for label, key in [('分类', 'vod_class'), ('地区', 'vod_area'),
                           ('年份', 'vod_year'), ('主演', 'vod_actor'),
                           ('导演', 'vod_director'), ('更新', 'vod_remarks')]:
            val = detail_texts.get(label, "")
            if val:
                d[key] = val

        # 评分 → vod_remarks 备用
        score = re.search(r'pic-tag[^>]*>(\d+\.?\d*)\s*分', h)
        if score and not d["vod_remarks"]:
            d["vod_remarks"] = score.group(1) + "分"

        # 播放源 & 集数
        sources = re.findall(r'<a\s+href="#playlist(\d+)"\s+data-toggle="tab">([^<]+)</a>', h)
        boxes = re.findall(
            r'<div\s+id="playlist(\d+)"[^>]*>(.*?)</div>',
            h, re.S,
        )
        pf, pu = [], []
        src_map = {sid: name for sid, name in sources}
        for sid, box_html in boxes:
            eps = re.findall(
                r'href="(/act/(\d+)/(\d+)/(\d+)\.html)"[^>]*>([^<]+)</a>', box_html
            )
            if eps:
                name = src_map.get(sid, f"线路{sid}")
                pf.append(name)
                # 按集号排序，防止乱序
                eps.sort(key=lambda x: int(x[3]) if x[3].isdigit() else 0)
                links = []
                for _, drama_id, src_id, ep_id, ep_name in eps:
                    ep_name = ep_name.strip()
                    links.append(f"{ep_name}${HOST}/act/{drama_id}/{src_id}/{ep_id}.html")
                pu.append("#".join(links))
        if pf:
            d["vod_play_from"] = "$$$".join(pf)
            d["vod_play_url"] = "$$$".join(pu)

        return {"list": [d]}

    # ── 搜索 ──────────────────────────────────────────────
    def searchContent(self, key, quick=False, pg="1"):
        try:
            url = f"{HOST}/search/-------------.html?wd={quote(key)}"
            h = self._fetch_page(url)
            return {"list": self._parse_items(h)}
        except:
            return {"list": []}

    # ── 播放解析 ──────────────────────────────────────────
    def playerContent(self, flag, id, vipFlags=None):
        u = str(id)
        if not u.startswith('http'):
            return {"parse": 0, "url": ""}
        try:
            h = self._fetch_page(u)
            # 提取 player_aaaa JSON
            m = re.search(r'player_aaaa=(\{.*?\})\s*</script>', h, re.S)
            if not m:
                m = re.search(r'var\s+player_aaaa=(\{.*?\});', h, re.S)
            if m:
                data = json.loads(m.group(1))
                video_url = data.get("url", "")
                encrypt = data.get("encrypt", 0)
                if encrypt == 0 and video_url:
                    return {"parse": 0, "url": video_url}
                elif encrypt == 1 and video_url:
                    # URL 被 URL 编码
                    from urllib.parse import unquote
                    return {"parse": 0, "url": unquote(video_url)}
                elif encrypt == 2 and video_url:
                    # URL 被 Base64 编码后再 URL 编码
                    import base64
                    from urllib.parse import unquote
                    decoded = base64.b64decode(unquote(video_url)).decode('utf-8')
                    return {"parse": 0, "url": decoded}
                elif video_url:
                    return {"parse": 0, "url": video_url}
        except:
            pass
        return {"parse": 0, "url": u}

    def localProxy(self, param):
        pass

    # ── 内部方法 ──────────────────────────────────────────

    def _fetch_page(self, url):
        """带 Cloudflare  cookie 预热 的页面抓取"""
        import requests as _rq
        _s = _rq.Session()
        _s.headers.update({
            'User-Agent': UA,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        })
        # 首次请求拿 cookie（403 → JS 跳转 → 第二次带 cookie 正常）
        try:
            _s.get(url, timeout=15, allow_redirects=True)
        except:
            pass
        r = _s.get(url, timeout=15, allow_redirects=True)
        r.encoding = 'utf-8'
        return r.text

    def _parse_items(self, html):
        """解析列表页的视频卡片（兼容分类页/首页/搜索页三种卡片格式）"""
        items, seen = [], set()

        # 格式1: 分类页/搜索页 - /drama/id.html + background:url()
        for m in re.finditer(
            r'class="myui-vodlist__thumb[^"]*"[^>]*href="/drama/(\d+)\.html"'
            r'[^>]*title="([^"]*)"[^>]*background:\s*url\(([^)]+)\)',
            html,
        ):
            vid = m.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            title = m.group(2).replace("在线观看", "").strip()
            if not title or len(title) > 100:
                continue
            after = html[m.end():m.end() + 1500]
            remark = re.search(r'pic-text[^>]*>([^<]+)<', after)
            items.append({
                "vod_id": vid,
                "vod_name": title[:50],
                "vod_pic": m.group(3).strip(),
                "vod_remarks": remark.group(1).strip() if remark else "",
            })

        # 格式2: 首页 - lazyload + data-original + href=/drama/
        if not items:
            for m in re.finditer(
                r'class="myui-vodlist__thumb[^"]*lazyload[^"]*"[^>]*'
                r'title="([^"]*)"[^>]*data-original="([^"]+)"',
                html,
            ):
                # 向后查找 /drama/id.html
                chunk = html[m.start():m.end() + 500]
                vid_m = re.search(r'href="/drama/(\d+)\.html"', chunk)
                if not vid_m:
                    continue
                vid = vid_m.group(1)
                if vid in seen:
                    continue
                seen.add(vid)
                title = m.group(1).replace("在线观看", "").strip()
                if not title or len(title) > 100:
                    continue
                after = html[m.end():m.end() + 1500]
                remark = re.search(r'pic-text[^>]*>([^<]+)<', after)
                items.append({
                    "vod_id": vid,
                    "vod_name": title[:50],
                    "vod_pic": m.group(2).strip(),
                    "vod_remarks": remark.group(1).strip() if remark else "",
                })

        # 格式3: 搜索结果 - data-original + /act/ 直链
        if not items:
            for m in re.finditer(
                r'class="myui-vodlist__thumb[^"]*picture[^"]*"[^>]*'
                r'href="/act/(\d+)/\d+/\d+\.html"[^>]*title="([^"]*)"[^>]*'
                r'data-original="([^"]+)"',
                html,
            ):
                vid = m.group(1)
                if not vid or vid in seen:
                    continue
                seen.add(vid)
                title = m.group(2).replace("在线观看", "").strip()
                if not title or len(title) > 100:
                    continue
                after = html[m.end():m.end() + 1500]
                remark = re.search(r'pic-text[^>]*>([^<]+)<', after)
                items.append({
                    "vod_id": vid,
                    "vod_name": title[:50],
                    "vod_pic": m.group(3).strip(),
                    "vod_remarks": remark.group(1).strip() if remark else "",
                })
        return items

    def _pagecount(self, html, current_page=1):
        """从页面提取总页数"""
        # 尝试从 "1/850" 格式提取
        m = re.search(r'(\d+)\s*/\s*(\d+)', html)
        if m:
            total = int(m.group(2))
            if total > 0:
                return total
        # 尝试从分页链接提取最大页码
        pages = re.findall(r'/cast/\d+-(\d+)\.html', html)
        if pages:
            return max(int(p) for p in pages)
        return current_page

    def _extract_detail_texts(self, html):
        """从详情页提取结构化元信息"""
        result = {}
        # 匹配 "标签：值" 模式，值可能跨多个 <a> / <span>
        detail_area = re.search(
            r'myui-content__detail(.*?)(?=myui-content__operate|id="playlist|tab-content)',
            html, re.S,
        )
        if not detail_area:
            return result
        text = detail_area.group(1)

        for label in ['分类', '地区', '年份', '主演', '导演', '更新', '类型']:
            # 找到标签后面的内容区域
            pattern = label + r'[：:]\s*</span>\s*(.*?)(?=<span|</p>|</div>|$)'
            m = re.search(pattern, text, re.S)
            if m:
                raw = m.group(1)
                # 去掉 HTML 标签，提取纯文本
                vals = re.findall(r'>([^<]+)<', raw)
                cleaned = [v.strip().replace('\xa0', '').replace('&nbsp;', '').strip() for v in vals if v.strip() and v.strip() not in ['', '\xa0']]
                cleaned = [v for v in cleaned if v]
                if cleaned:
                    result[label] = "，".join(cleaned) if label in ('主演', '导演') else cleaned[0]
        return result
