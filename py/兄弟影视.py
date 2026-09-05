# -*- coding: utf-8 -*-
import sys
import re
import json
from urllib.parse import urljoin, quote, unquote, urlparse
from html import unescape as html_unescape
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

HOST = "https://www.brovod.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# 封面URL中这些域名已失效，对应影片会被过滤掉
DEAD_IMG_HOSTS = {"image.caiji.cyou", "wim.xrc888.com"}
# 分类映射: tid -> 中文名
CATEGORIES = {
    "Movies": "电影",
    "TV": "剧集",
    "Anime": "动漫",
    "Documentaries": "纪录片",
    "Snaps": "短剧",
    "Shows": "综艺",
}

# weserv.nl 代理前缀，需要去掉以获取原始URL
WESERV_PREFIX = "https://images.weserv.nl/?url="

# from值 -> 线路显示名 (来自 playerconfig.js)
# 蓝光①(xdxl/xdyy)和蓝光④(xdjp)已禁用（无法播放）
FROM_DISPLAY = {
    "xdrs": "蓝光②", "xdac": "蓝光③", "xd5": "蓝光⑤",
    "bfzym3u8": "极速①", "1080zyk": "极速②", "jsm3u8": "极速③",
}
# 禁用的from值，对应的线路会被过滤掉
BLOCKED_FROMS = {"xdxl", "xdyy", "xdjp"}


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
        r = {"class": []}
        for k, v in CATEGORIES.items():
            r["class"].append({"type_id": k, "type_name": v})
        return r

    def homeVideoContent(self):
        try:
            r = self.fetch(HOST, headers={"User-Agent": UA}, timeout=15000)
            html = r.text if hasattr(r, 'text') else str(r)
            return {"list": [it for it in self._items(html) if it.get("vod_pic")]}
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
            return {"page": pn, "pagecount": 1, "limit": 36, "total": 0, "list": []}
        try:
            url = self._build_category_url(cat, pn, extend)
            r = self.fetch(url, headers={"User-Agent": UA}, timeout=30000)
            html = r.text if hasattr(r, 'text') else str(r)
            items = [it for it in self._items(html) if it.get("vod_pic")]
            pc = self._pagecount(html, pn)
            return {"page": pn, "pagecount": pc, "limit": 36, "total": len(items), "list": items}
        except:
            return {"page": pn, "pagecount": 1, "limit": 36, "total": 0, "list": []}

    def _build_category_url(self, cat, pn, extend=""):
        """构建分类URL
        网站URL实际格式为12段（以-分隔）:
        /show/{类名}-{地区}-{排序}-{类型}-{语言}-{字母}-----{页码}---{年份}/
        段位说明（0-indexed）:
          0: 类名 (Movies/TV/Anime/Documentaries/Snaps/Shows)
          1: 地区 (大陆/香港/美国/...)
          2: 排序 (time/hits/score)
          3: 类型 (喜剧/爱情/动作/...)
          4: 语言 (国语/英语/粤语/...)
          5: 字母 (A/B/C/.../0-9)
          6-7: 空
          8: 页码 (1/2/3/...)
          9-10: 空
          11: 年份 (2026/2025/...)
        示例: /show/Movies-----------/ (无筛选,首页)
        示例: /show/Movies--------1---/ (第1页) 注意首页无筛选时不需要页码
        示例: /show/Movies--------2---/ (第2页)
        示例: /show/Movies-%E5%A4%A7%E9%99%86----------/ (地区=大陆)
        示例: /show/Movies---%E5%96%9C%E5%89%A7--------/ (类型=喜剧)
        示例: /show/Movies-----------2026/ (年份=2026)
        示例: /show/Movies--time---------/ (按时间排序)
        """
        ext = {}
        if extend and isinstance(extend, str) and extend.strip():
            try:
                ext = json.loads(extend)
            except:
                pass

        area = ext.get("area") or ""
        sort = ext.get("sort") or ""
        genre = ext.get("class") or ""
        lang = ext.get("lang") or ""
        letter = ext.get("letter") or ""
        year = ext.get("year") or ""

        # 12段: [类名, 地区, 排序, 类型, 语言, 字母, "", "", 页码, "", "", 年份]
        parts = [cat, "", "", "", "", "", "", "", "", "", "", ""]
        if area and area != "全部":
            parts[1] = quote(area)
        if sort:
            parts[2] = sort
        if genre and genre != "全部":
            parts[3] = quote(genre)
        if lang and lang != "全部":
            parts[4] = quote(lang)
        if letter and letter != "全部":
            parts[5] = letter
        if pn > 1:
            parts[8] = str(pn)
        if year and year != "全部":
            parts[11] = str(year)

        url = "/show/" + "-".join(parts) + "/"
        return HOST + url

    def detailContent(self, ids):
        if isinstance(ids, list):
            vid = ids[0] if ids else ""
        else:
            vid = str(ids) if ids else ""
        if not vid:
            return {"list": []}
        detail_id = vid

        # 构建详情页URL
        if "/" in vid:
            detail_url = vid if vid.startswith("http") else urljoin(HOST, vid)
        else:
            detail_url = f"{HOST}/detail/{vid}/"

        try:
            r = self.fetch(detail_url, headers={"User-Agent": UA}, timeout=30000)
            h = r.text if hasattr(r, 'text') else str(r)
        except:
            return {"list": []}

        d = {
            "vod_id": detail_id,
            "vod_name": "",
            "vod_pic": "",
            "vod_year": "",
            "vod_area": "",
            "vod_class": "",
            "vod_director": "",
            "vod_actor": "",
            "vod_content": "",
            "vod_remarks": "",
            "vod_play_from": "",
            "vod_play_url": "",
        }

        # === 标题: <h3 class="slide-info-title hide">名称</h3> ===
        tn = re.search(r'class="slide-info-title[^"]*"[^>]*>(.*?)</(?:h1|h2|h3)>', h, re.S)
        if tn:
            d["vod_name"] = re.sub(r'<[^>]+>', '', tn.group(1)).strip()
        if not d["vod_name"]:
            tn = re.search(r'<title>(.*?)</title>', h)
            if tn:
                d["vod_name"] = tn.group(1).split("-")[0].strip()

        # === 封面: 详情页中 data-src ===
        p = re.search(r'data-src="(https?://[^"]+)"', h)
        if not p:
            p = re.search(r'src="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"', h, re.I)
        if p:
            d["vod_pic"] = self._clean_pic(p.group(1))

        # === slide-info 区域提取年份/地区/类型/导演/演员/备注/更新时间 ===
        # 结构:
        # <div class="slide-info">
        #   <span class="slide-info-remarks"><a>2025</a></span>
        #   <span class="slide-info-remarks"><a>大陆</a></span>
        #   <span class="slide-info-remarks"><a>动作</a></span>...
        # </div>
        # <div class="slide-info"><strong>备注 :</strong>蓝光</div>
        # <div class="slide-info"><strong>导演 :</strong><a>巨兴茂</a>/</div>
        # <div class="slide-info"><strong>演员 :</strong><a>杨旭文</a>/...</div>
        # <div class="slide-info"><strong>更新 :</strong>2026-02-21 18:28:06</div>

        # 提取slide-info区域中的标签(年份、地区、类型)
        slide_info_tags = re.findall(
            r'<div class="slide-info[^"]*">\s*'
            r'((?:<span class="slide-info-remarks">.*?</span>\s*)+)\s*</div>',
            h, re.S
        )
        if slide_info_tags:
            tag_text = re.sub(r'<[^>]+>', ' ', slide_info_tags[0])
            tag_text = re.sub(r'\s+', ' ', tag_text).strip()
            parts = [t.strip() for t in tag_text.split() if t.strip()]
            # 第一个通常是年份
            for p_text in parts:
                if re.match(r'^\d{4}$', p_text) and not d["vod_year"]:
                    d["vod_year"] = p_text
                # 地区关键词
                elif p_text in ("大陆", "香港", "台湾", "美国", "韩国", "日本", "英国",
                                "法国", "德国", "泰国", "印度", "加拿大", "其他",
                                "意大利", "西班牙", "未知"):
                    if not d["vod_area"]:
                        d["vod_area"] = p_text
                elif not d["vod_area"] and re.match(r'^[\u4e00-\u9fff]{2,3}$', p_text):
                    d["vod_area"] = p_text
            # 剩余的是类型
            type_parts = []
            year_done = False
            area_done = False
            for p_text in parts:
                if re.match(r'^\d{4}$', p_text):
                    year_done = True
                    continue
                if p_text in ("大陆", "香港", "台湾", "美国", "韩国", "日本", "英国",
                              "法国", "德国", "泰国", "印度", "加拿大", "其他",
                              "意大利", "西班牙", "未知"):
                    area_done = True
                    continue
                if year_done and area_done:
                    type_parts.append(p_text)
            if type_parts:
                d["vod_class"] = " ".join(type_parts)

        # 备注: <strong>备注 :</strong>蓝光
        rm = re.search(r'备注\s*[：:]\s*</strong>\s*([^<\s]+)', h)
        if rm:
            d["vod_remarks"] = rm.group(1).strip()

        # 导演: <strong>导演 :</strong><a>巨兴茂</a>
        dm = re.search(r'导演\s*[：:]\s*</strong>([\s\S]*?)(?:</div>)', h)
        if dm:
            d["vod_director"] = re.sub(r'<[^>]+>', '', dm.group(1)).replace("/", ",").strip().rstrip(",").strip()

        # 演员: <strong>演员 :</strong><a>杨旭文</a>/<a>杨志刚</a>/...
        am = re.search(r'演员\s*[：:]\s*</strong>([\s\S]*?)(?:</div>)', h)
        if am:
            d["vod_actor"] = re.sub(r'<[^>]+>', '', am.group(1)).replace("/", ",").strip().rstrip(",").strip()

        # === 简介 ===
        # 优先从slide-info-content区域提取
        desc_m = re.search(r'class="slide-info-content"[^>]*>([\s\S]*?)</div>', h)
        if desc_m:
            d["vod_content"] = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', desc_m.group(1))).strip()[:500]
        if not d["vod_content"]:
            # 尝试从影视简介区域提取
            desc_m = re.search(r'影视简介[\s\S]{0,10}?>([\s\S]*?)</(?:div|p)>', h)
            if desc_m:
                d["vod_content"] = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', desc_m.group(1))).strip()[:500]
        if not d["vod_content"]:
            # 尝试card-text区域（搜索结果页）
            desc_m = re.search(r'class="card-text">([\s\S]*?)</div>', h)
            if desc_m:
                d["vod_content"] = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', desc_m.group(1))).strip()[:500]

        # === 播放列表解析 ===
        try:
            pf_list, pu_list = [], []

            # 1. 从anthology-tab提取线路名（按顺序）
            # HTML结构: <div class="anthology-tab">...<a class="swiper-slide"><i>...</i>蓝光①<span class="badge">40</span></a>...</div>
            tab_names = []
            tab_section = re.search(
                r'<div class="anthology-tab[^"]*">(.*?)</div>\s*</div>\s*<div class="anthology-list',
                h, re.S
            )
            if not tab_section:
                tab_section = re.search(
                    r'<div class="anthology-tab[^"]*">(.*?)</div>\s*</div>',
                    h, re.S
                )
            if tab_section:
                for tab_m in re.finditer(r'<a[^>]*class="swiper-slide"[^>]*>([\s\S]*?)</a>', tab_section.group(1)):
                    tab_text = html_unescape(re.sub(r'<[^>]+>', '', tab_m.group(1)).strip())
                    tab_text = tab_text.replace('\xa0', ' ').strip()
                    if tab_text:
                        tab_names.append(tab_text)

            # 2. 从anthology-list-box提取各线路的集数链接
            # HTML结构: <div class="anthology-list"><div class="anthology-list-box">...<ul class="anthology-list-play">...<a href="/play/xxx-1-1/">集名</a>...</div>...</div>
            # 每个anthology-list-box对应一个线路

            list_section = re.search(
                r'<div class="anthology-list[^"]*">(.*?)</div>\s*</div>\s*</div>',
                h, re.S
            )
            if not list_section:
                # 更宽松匹配
                list_section = re.search(
                    r'class="anthology-list[^"]*"(.*?)$',
                    h, re.S
                )

            if list_section:
                boxes = re.findall(
                    r'<div class="anthology-list-box[^"]*">(.*?)</ul>\s*</div>',
                    list_section.group(1), re.S
                )
                if not boxes:
                    boxes = re.findall(
                        r'<div class="anthology-list-box[^"]*">(.*?)(?=<div class="anthology-list-box|</div>\s*</div>)',
                        list_section.group(1), re.S
                    )

                for idx, box_html in enumerate(boxes):
                    # 提取集数链接
                    eps = re.findall(
                        r'href="(/play/[^"]+)"[^>]*>(.*?)</a>',
                        box_html, re.S
                    )
                    if not eps:
                        continue

                    ep_list = []
                    for ep_url, ep_name in eps:
                        ep_name = re.sub(r'<[^>]+>', '', ep_name).strip()
                        if not ep_name:
                            ep_name = f"第{len(ep_list) + 1}集"
                        full_url = urljoin(HOST, ep_url)
                        ep_list.append(f"{ep_name}${full_url}")

                    if ep_list:
                        # 检查该线路的from值，过滤禁用线路
                        skip = False
                        try:
                            first_url = urljoin(HOST, eps[0][0]) if eps else ""
                            rp = self.fetch(first_url, headers={"User-Agent": UA}, timeout=5000)
                            hp = rp.text if hasattr(rp, 'text') else str(rp)
                            fm = re.search(r'"from"\s*:\s*"([^"]+)"', hp)
                            if fm and fm.group(1) in BLOCKED_FROMS:
                                skip = True
                        except:
                            pass
                        if skip:
                            continue
                        # 线路名: 优先使用anthology-tab中的名称
                        if idx < len(tab_names):
                            line_name = tab_names[idx]
                        else:
                            line_name = f"线路{idx + 1}"
                        pf_list.append(line_name)
                        pu_list.append("#".join(ep_list))

            # 如果上述方式没找到，备用方案: 直接匹配所有play链接并按线路序号分组
            if not pf_list:
                play_links = re.findall(
                    r'href="(/play/[^"]+-\d+-\d+/)"[^>]*>([\s\S]*?)</a>',
                    h, re.S
                )
                line_episodes = {}
                line_froms = {}
                for link_url, ep_name in play_links:
                    ep_name = re.sub(r'<[^>]+>', '', ep_name).strip()
                    m2 = re.search(r'/play/.+?-(\d+)-(\d+)/', link_url)
                    if m2:
                        line_idx = m2.group(1)
                        if line_idx not in line_episodes:
                            line_episodes[line_idx] = []
                        full_url = urljoin(HOST, link_url)
                        line_episodes[line_idx].append((ep_name, full_url))
                        # 获取from值（只需每条线路检查一次）
                        if line_idx not in line_froms:
                            try:
                                rp = self.fetch(full_url, headers={"User-Agent": UA}, timeout=5000)
                                hp = rp.text if hasattr(rp, 'text') else str(rp)
                                pm = re.search(r'"from"\s*:\s*"([^"]+)"', hp)
                                if pm:
                                    line_froms[line_idx] = pm.group(1)
                            except:
                                pass

                for line_idx in sorted(line_episodes.keys(), key=lambda x: int(x)):
                    eps = line_episodes[line_idx]
                    from_val = line_froms.get(line_idx, "")
                    if from_val in BLOCKED_FROMS:
                        continue
                    line_name = FROM_DISPLAY.get(from_val, f"线路{line_idx}")
                    ep_list = []
                    for ep_name, ep_url in eps:
                        if not ep_name:
                            ep_name = f"第{len(ep_list) + 1}集"
                        ep_list.append(f"{ep_name}${ep_url}")
                    if ep_list:
                        pf_list.append(line_name)
                        pu_list.append("#".join(ep_list))

            if pf_list:
                d["vod_play_from"] = "$$$".join(pf_list)
                d["vod_play_url"] = "$$$".join(pu_list)
        except Exception:
            pass

        return {"list": [d]}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            pn = 1
            try:
                pn = int(str(pg))
            except:
                pass
            # 搜索URL: /ss/-------------/?wd=关键词
            url = f"{HOST}/ss/-------------/?wd={quote(key)}"
            r = self.fetch(url, headers={"User-Agent": UA}, timeout=30000)
            html = r.text if hasattr(r, 'text') else str(r)
            items = self._search_items(html)
            return {"list": items, "page": pn}
        except:
            return {"list": []}

    def playerContent(self, flag, id, vipFlags=None):
        url = str(id) if id else str(flag)
        # 如果已经是m3u8直链，直接返回
        if url.startswith("http") and ".m3u8" in url:
            return {"url": url}
        # 构建完整URL
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

        # 尝试提取 var player_aaaa 中的数据
        player_m = re.search(r'player_aaaa\s*=\s*(\{.*?\})\s*</script>', h, re.S)
        if player_m:
            try:
                data = json.loads(player_m.group(1))
                play_url = data.get("url", "")
                # 如果url是明文的m3u8链接，直接返回
                if play_url and play_url.startswith("http") and ".m3u8" in play_url:
                    return {"url": play_url}
                # emoji加密的url，构建解析地址返回
                if play_url:
                    from urllib.parse import quote
                    parse_url = f"https://play.brovod.com/?url={quote(play_url)}"
                    # parse=1 告诉APP用WebView加载解析页面嗅探m3u8
                    return {"url": parse_url, "parse": 1, "header": {"User-Agent": UA}}
            except Exception:
                pass

        # 尝试匹配页面中的m3u8直链
        m3u8 = re.search(r'(https?://[^\s"\'<>]+\.m3u8)', h)
        if m3u8:
            return {"url": m3u8.group(1)}

        # 兜底：返回播放页URL，让APP的WebView去嗅探
        return {"url": full_url, "parse": 1, "header": {"User-Agent": UA}}

    def localProxy(self, param):
        pass

    def _clean_pic(self, pic_url):
        """清理封面URL: 去掉weserv代理前缀, HTTP升级HTTPS, 过滤失效图床"""
        if not pic_url:
            return ""
        # 去掉weserv.nl代理前缀
        if pic_url.startswith(WESERV_PREFIX):
            pic_url = pic_url[len(WESERV_PREFIX):]
            try:
                pic_url = unquote(pic_url)
            except Exception:
                pass
        # HTTP升级为HTTPS
        if pic_url.startswith("http://"):
            pic_url = pic_url.replace("http://", "https://", 1)
        # 过滤失效图床域名
        host = urlparse(pic_url).hostname or ""
        if host in DEAD_IMG_HOSTS:
            return ""
        return pic_url

    def _items(self, html, cat_filter=""):
        """从分类/首页HTML中提取列表项
        HTML结构:
        <a class="public-list-exp" href="/detail/xxx-123/" title="名称">
          <img data-src="封面URL" />
          <span class="public-list-prb hide ft2">备注</span>
        </a>
        """
        items, seen = [], set()
        # 匹配 public-list-exp 中的详情链接
        for m in re.finditer(
            r'class="public-list-exp"[^>]*href="(/detail/[^"]+)"[^>]*title="([^"]*)"',
            html
        ):
            detail_url = m.group(1)
            name = m.group(2).strip()
            if not name or len(name) > 100:
                continue
            # 提取数字ID去重
            vid_m = re.search(r'-(\d+)/?$', detail_url)
            vid = vid_m.group(1) if vid_m else detail_url
            if vid in seen:
                continue
            seen.add(vid)

            # 在匹配位置之后查找封面和备注（向前搜索3000字符）
            after = html[m.end():m.end() + 3000]

            # 封面: data-src
            cover = re.search(r'data-src="(https?://[^"]+)"', after)
            if not cover:
                cover = re.search(r'src="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"', after, re.I)
            pic_url = self._clean_pic(cover.group(1)) if cover else ""

            # 备注: class="public-list-prb"
            remark = re.search(r'class="public-list-prb[^"]*"[^>]*>([^<]+)<', after)
            if not remark:
                remark = re.search(r'class="[^"]*prb[^"]*"[^>]*>([^<]+)<', after)

            items.append({
                "vod_id": detail_url,
                "vod_name": name[:50],
                "vod_pic": pic_url,
                "vod_remarks": remark.group(1).strip() if remark else "",
            })
        return items

    def _search_items(self, html):
        """从搜索结果HTML中提取列表项
        搜索结果HTML结构（search-box）:
        <div class="public-list-box search-box flex rel">
          <div class="left public-list-bj">
            <a href="/detail/xxx-123/"><img data-src="封面URL" />
            <span class="public-list-prb hide ft2">备注</span></a>
          </div>
          <div class="right">
            <div class="thumb-txt"><a href="/detail/xxx-123/">名称</a></div>
            ...
          </div>
        </div>
        """
        items, seen = [], set()
        # 按 public-list-box search-box 块分割
        boxes = re.split(r'<div class="public-list-box[^"]*search-box', html)
        for box_html in boxes[1:]:  # 跳过第一个(分割前的内容)
            # 提取详情链接
            detail_m = re.search(r'href="(/detail/[^"]+)"', box_html)
            if not detail_m:
                continue
            detail_url = detail_m.group(1)
            vid_m = re.search(r'-(\d+)/?$', detail_url)
            vid = vid_m.group(1) if vid_m else detail_url
            if vid in seen:
                continue
            seen.add(vid)

            # 名称: thumb-txt中的链接文本
            name_m = re.search(r'class="thumb-txt[^"]*"[^>]*><a[^>]*href="[^"]*"[^>]*>(.*?)</a>', box_html, re.S)
            if name_m:
                name = html_unescape(re.sub(r'<[^>]+>', '', name_m.group(1)).strip())
            else:
                name_m = re.search(r'title="([^"]+)"', box_html)
                name = name_m.group(1).strip() if name_m else ""
            if not name or len(name) > 100:
                continue

            # 封面: data-src
            cover = re.search(r'data-src="(https?://[^"]+)"', box_html)
            if not cover:
                cover = re.search(r'src="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"', box_html, re.I)
            pic_url = self._clean_pic(cover.group(1)) if cover else ""

            # 备注: public-list-prb
            remark = re.search(r'class="public-list-prb[^"]*"[^>]*>([^<]+)<', box_html)

            items.append({
                "vod_id": detail_url,
                "vod_name": name[:50],
                "vod_pic": pic_url,
                "vod_remarks": remark.group(1).strip() if remark else "",
            })
        return items

    def _pagecount(self, html, current_page=1):
        """从HTML中提取总页数
        分页结构: ...尾页</a>...</div>...
        尾页链接: href="/show/Movies--------1643---/"
        """
        max_page = current_page

        # 匹配 "尾页" 链接中的页码
        tail_m = re.search(r'尾页[^>]*href="[^"]*?-(\d+)---/"', html)
        if tail_m:
            try:
                max_page = int(tail_m.group(1))
                return max_page
            except Exception:
                pass

        # 从分页数字链接中推断最大页码
        # URL格式: /show/Movies--------{N}---/
        pages = re.findall(r'/show/\w+-{4,}(\d+)---/', html)
        for p in pages:
            try:
                n = int(p)
                if n > max_page:
                    max_page = n
            except Exception:
                pass

        # 如果有下一页标记且当前页接近最大值，多给几页
        has_next = re.search(r'>下一页<', html)
        if has_next and max_page <= current_page + 5:
            max_page = current_page + 5

        return max_page if max_page >= 1 else 1
