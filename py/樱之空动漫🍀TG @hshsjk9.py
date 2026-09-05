# -*- coding: utf-8 -*-
"""
站点: 樱之空动漫 (skr2.cc)
功能: 图片懒加载修复、播放线路Base64解密修复、多线路分组解析
版本: 2026-08-24 多线路修复版v3
"""
import sys
import re
import urllib.parse
import base64

sys.path.append('..')
from base.spider import Spider

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

HOSTS = [
    "https://www.skr2.cc",
    "https://www.skr.cc",
    "https://skr2.cc",
    "https://skr.skr2.cc:666",
    "http://skr.skr2.cc:666",
]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
DEFAULT_PIC = "https://pic.rmb.bdstatic.com/bjh/user/default.png"

CLASSES = [
    {"type_id": "1", "type_name": "桜漫"},
    {"type_id": "3", "type_name": "桜歌"},
    {"type_id": "32", "type_name": "桜剧"},
    {"type_id": "80", "type_name": "影视"},
    {"type_id": "2", "type_name": "桜学"},
]


class Spider(Spider):
    def getName(self):
        return "樱之空动漫"

    def init(self, extend=""):
        self.extend = extend or ""
        self.headers = {
            "User-Agent": UA,
            "Referer": "https://www.skr2.cc/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate",
        }
        self.debug = True
        self._host = None
        self._cache = {}

    def _log(self, msg):
        if self.debug:
            print("[樱之空] " + str(msg))

    def _fetch_html(self, url, force=False):
        cache_key = url
        if not force and cache_key in self._cache:
            self._log(f"📦 使用缓存: {url}")
            return self._cache[cache_key]

        if not url.startswith("http"):
            if self._host is None:
                for host in HOSTS:
                    test_url = host + "/"
                    self._log(f"🔍 尝试主机: {test_url}")
                    try:
                        if HAS_REQUESTS:
                            r = requests.get(test_url, headers=self.headers, timeout=10, verify=False)
                            if r.status_code == 200:
                                self._host = host
                                self._log(f"✅ 可用主机: {host}")
                                break
                        else:
                            resp = self.fetch(test_url, headers=self.headers, timeout=10)
                            if resp and getattr(resp, 'status_code', 0) == 200:
                                self._host = host
                                self._log(f"✅ 可用主机: {host}")
                                break
                    except Exception as e:
                        self._log(f"⚠️ 主机 {host} 失败: {e}")
                if self._host is None:
                    self._log("❌ 所有主机均不可用")
                    return None
            full_url = self._host + url
        else:
            full_url = url

        self._log(f"📡 请求: {full_url}")
        try:
            if HAS_REQUESTS:
                r = requests.get(full_url, headers=self.headers, timeout=15, verify=False)
                self._log(f"状态码: {r.status_code}")
                if r.status_code == 200:
                    html = r.text
                    self._log(f"内容长度: {len(html)}")
                    self._cache[cache_key] = html
                    return html
                else:
                    self._log(f"⚠️ 状态码非200: {r.status_code}")
                    return None
            else:
                resp = self.fetch(full_url, headers=self.headers, timeout=15)
                if not resp:
                    self._log("❌ fetch返回None")
                    return None
                html = resp.text if hasattr(resp, 'text') else resp.content.decode('utf-8', 'ignore')
                self._log(f"状态码: {getattr(resp, 'status_code', '?')}")
                self._log(f"内容长度: {len(html)}")
                self._cache[cache_key] = html
                return html
        except Exception as e:
            self._log(f"❌ 请求异常: {e}")
            return None

    def _fix_pic_url(self, pic):
        """修复图片URL：补全协议和相对路径"""
        if not pic:
            return DEFAULT_PIC
        if pic.startswith("//"):
            pic = "https:" + pic
        elif not pic.startswith("http"):
            pic = urllib.parse.urljoin(self._host or HOSTS[0], pic)
        return pic

    def _extract_videos(self, html):
        videos = []
        if not html:
            return videos

        seen = set()

        # 1. 处理 vodlist_thumb lazyload (主要视频卡片)
        pattern = r'<a[^>]+class="[^"]*vodlist_thumb[^"]*lazyload[^"]*"[^>]*>'
        for m in re.finditer(pattern, html, re.I):
            full_tag = m.group(0)

            href = re.search(r'href="(/voddetail/(\d+)/)"', full_tag)
            if not href:
                continue
            vid = href.group(2)
            if vid in seen:
                continue
            seen.add(vid)

            title = re.search(r'alt="([^"]+)"', full_tag)
            title = title.group(1) if title else "未命名"

            img = re.search(r'data-original="([^"]+)"', full_tag, re.I)
            pic = self._fix_pic_url(img.group(1) if img else DEFAULT_PIC)

            # 备注
            remark = ''
            start = m.start()
            nearby = html[start:start+400]
            r_span = re.search(r'<span[^>]*>([^<]*?(?:更新|第|全)\s*\d+\s*[集页][^<]*)</span>', nearby)
            if r_span:
                remark = r_span.group(1).strip()
            else:
                r_em = re.search(r'<em[^>]*class="[^"]*voddate[^"]*"[^>]*>([^<]+)</em>', nearby)
                if r_em:
                    remark = r_em.group(1).strip()

            videos.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark,
            })

        # 2. 处理 ranklist_thumb lazyload (时间表页面)
        pattern2 = r'<a[^>]+class="[^"]*ranklist_thumb[^"]*lazyload[^"]*"[^>]*>'
        for m in re.finditer(pattern2, html, re.I):
            full_tag = m.group(0)

            href = re.search(r'href="(/voddetail/(\d+)/)"', full_tag)
            if not href:
                continue
            vid = href.group(2)
            if vid in seen:
                continue
            seen.add(vid)

            title = re.search(r'alt="([^"]+)"', full_tag)
            title = title.group(1) if title else "未命名"

            img = re.search(r'data-original="([^"]+)"', full_tag, re.I)
            pic = self._fix_pic_url(img.group(1) if img else DEFAULT_PIC)

            # 备注 - ranklist通常有日期信息
            remark = ''
            start = m.start()
            nearby = html[start:start+400]
            r_span = re.search(r'<span[^>]*class="[^"]*text_right[^"]*"[^>]*>(.*?)</span>', nearby, re.S)
            if r_span:
                remark = re.sub(r'<[^>]+>', '', r_span.group(1)).strip()
            else:
                r_span = re.search(r'<span[^>]*>([^<]*?(?:更新|第|全)\s*\d+\s*[集页][^<]*)</span>', nearby)
                if r_span:
                    remark = r_span.group(1).strip()

            videos.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark,
            })

        # 3. 处理 balist_thumb (banner轮播图)
        pattern3 = r'<a[^>]+class="[^"]*balist_thumb[^"]*"[^>]*>'
        for m in re.finditer(pattern3, html, re.I):
            full_tag = m.group(0)

            href = re.search(r'href="(/voddetail/(\d+)/)"', full_tag)
            if not href:
                continue
            vid = href.group(2)
            if vid in seen:
                continue
            seen.add(vid)

            # 标题在附近的 <p class="vodlist_title">
            start = m.start()
            nearby = html[start:start+500]
            title = re.search(r'<p[^>]*class="[^"]*vodlist_title[^"]*"[^>]*>([^<]+)</p>', nearby)
            title = title.group(1).strip() if title else "未命名"

            # 图片在 style="background-image: url(...)"
            img = re.search(r'background-image:\s*url\(([^)]+)\)', full_tag, re.I)
            pic = self._fix_pic_url(img.group(1) if img else DEFAULT_PIC)

            videos.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": "",
            })

        # 4. 兜底：纯文字列表（一览表等）
        if not videos:
            pattern4 = r'<a[^>]+href="(/voddetail/(\d+)/)"[^>]*>([^<]+)</a>'
            for href, vid, title in re.findall(pattern4, html, re.I):
                if vid in seen:
                    continue
                seen.add(vid)
                title = title.strip()
                if not title or title in ['', ' ']:
                    continue
                videos.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": DEFAULT_PIC,
                    "vod_remarks": "",
                })

        self._log(f"🔍 提取到 {len(videos)} 个视频")
        return videos

    def _extract_categories(self, html):
        cats = []
        nav = re.search(r'<ul[^>]*class="[^"]*top_nav[^"]*"[^>]*>(.*?)</ul>', html, re.S)
        if nav:
            items = re.findall(r'<a[^>]+href="/vodtype/(\d+)/"[^>]*>([^<]+)</a>', nav.group(1))
            for tid, name in items:
                if tid and name:
                    cats.append({"type_id": tid, "type_name": name.strip()})
        if not cats:
            cats = CLASSES
        return cats

    def _get_total_pages(self, html):
        m = re.search(r'共(\d+)页', html)
        if m:
            return int(m.group(1))
        nums = re.findall(r'<a[^>]*>(\d+)</a>', html)
        if nums:
            return max([int(n) for n in nums if n.isdigit()])
        return 1

    def _parse_playlists(self, html):
        """解析多线路播放列表（苹果CMS play_source_tab + content_playlist 结构）

        页面结构:
          <div class="play_source_tab" id="NumTab">
            <a href="javascript:void(0);" alt="线一">线一<div>5</div></a>  ← 线路名标签(按顺序)
            ...
          </div>
          <div class="play_list_box">        ← 每线路一个box
            <ul class="content_playlist">    ← box内含 notfull/full 两份相同列表
              <li><a href="/vodplay/视频id-线路id-集数/">第01集</a></li>
            </ul>
          </div>

        返回: (vod_play_from, vod_play_url)
          线路之间用 $$$ 分隔; 集数之间用 # 分隔; 标题与地址用 $ 分隔
        """
        # 1. 提取线路名标签（play_source_tab 与 play_list_box 之间的区域）
        tabs = []
        s = html.find('play_source_tab')
        e = html.find('play_list_box')
        if s != -1 and e > s:
            tabs = [t.strip() for t in re.findall(r'\balt="([^"]+)"', html[s:e]) if t.strip()]

        # 2. 按 content_playlist ul 提取集数链接
        #    同一线路的 notfull/full 两份 ul 相邻且线路id相同，合并去重
        groups = []  # [(线路id, [(标题, 相对链接), ...]), ...]
        for ul in re.findall(r'<ul[^>]*class="[^"]*content_playlist[^"]*"[^>]*>(.*?)</ul>', html, re.S):
            links = re.findall(r'<a[^>]+href="(/vodplay/(\d+)-(\d+)-(\d+)/)"[^>]*>([^<]+)</a>', ul)
            if not links:
                continue
            src_id = links[0][2]
            if groups and groups[-1][0] == src_id:
                eps = groups[-1][1]
                seen = {(t, u) for t, u in eps}
            else:
                eps = []
                seen = set()
                groups.append((src_id, eps))
            for url, _vid, _sid, _ep, title in links:
                title = title.strip()
                if not title or (title, url) in seen:
                    continue
                seen.add((title, url))
                eps.append((title, url))

        if not groups:
            return "", ""

        # 3. 线路命名：标签数量与线路数量一致时按顺序配对（保留网站原始线路名）
        if tabs and len(tabs) == len(groups):
            names = tabs
            self._log(f"✅ 多线路解析: {len(groups)} 条线路 {names}")
        else:
            names = ["线路" + sid for sid, _ in groups]
            self._log(f"⚠️ 线路标签({len(tabs)})与分组({len(groups)})数量不一致，使用默认命名: {names}")

        # 4. 拼接 TVBox 格式
        from_list = []
        url_list = []
        base = self._host or HOSTS[0]
        for name, (_sid, eps) in zip(names, groups):
            from_list.append(name)
            url_list.append('#'.join(
                '{}${}'.format(t, urllib.parse.urljoin(base, u)) for t, u in eps
            ))
            self._log(f"  📺 {name}: {len(eps)} 集")
        return '$$$'.join(from_list), '$$$'.join(url_list)

    def _parse_detail(self, html, vid):
        info = {
            "vod_id": vid,
            "vod_name": "",
            "vod_pic": DEFAULT_PIC,
            "vod_content": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_year": "",
            "vod_area": "",
            "vod_type": "",
            "vod_play_from": "",
            "vod_play_url": "",
        }
        title_m = re.search(r'<h1[^>]*>(.*?)</h1>', html)
        if title_m:
            info['vod_name'] = title_m.group(1).strip()

        # 详情页海报
        pic_m = re.search(r'<img[^>]+class="[^"]*poster[^"]*"[^>]+data-original="([^"]+)"', html, re.I)
        if not pic_m:
            pic_m = re.search(r'<img[^>]+class="[^"]*poster[^"]*"[^>]+src="([^"]+)"', html, re.I)
        if not pic_m:
            pic_m = re.search(r'<a[^>]+class="[^"]*pic[^"]*"[^>]+data-original="([^"]+)"', html, re.I)
        if pic_m:
            info['vod_pic'] = self._fix_pic_url(pic_m.group(1))

        desc_m = re.search(r'<div[^>]*class="[^"]*description[^"]*"[^>]*>(.*?)</div>', html, re.S)
        if desc_m:
            info['vod_content'] = re.sub(r'<[^>]+>', '', desc_m.group(1)).strip()

        info_m = re.search(r'<div[^>]*class="[^"]*info[^"]*"[^>]*>(.*?)</div>', html, re.S)
        if info_m:
            text = info_m.group(1)
            patterns = {
                'vod_actor': r'主演[：:]\s*(.*?)(?:\n|$)',
                'vod_director': r'导演[：:]\s*(.*?)(?:\n|$)',
                'vod_year': r'年份[：:]\s*(\d{4})',
                'vod_area': r'地区[：:]\s*(.*?)(?:\n|$)',
                'vod_type': r'类型[：:]\s*(.*?)(?:\n|$)',
            }
            for key, pat in patterns.items():
                m = re.search(pat, text)
                if m:
                    info[key] = m.group(1).strip()

        # 播放列表：多线路分组解析（网站链接不带.html）
        play_from, play_url = self._parse_playlists(html)
        if play_from:
            info['vod_play_from'] = play_from
            info['vod_play_url'] = play_url
        else:
            # 兜底1：全页 vodplay 链接合并为单线路
            play_links = re.findall(r'<a[^>]+href="(/vodplay/[^"]+?)"[^>]*>([^<]+)</a>', html)
            if play_links:
                episodes = []
                seen = set()
                for url, title in play_links:
                    if not url.startswith('http'):
                        url = urllib.parse.urljoin(self._host or HOSTS[0], url)
                    key = f"{title.strip()}${url}"
                    if key not in seen:
                        seen.add(key)
                        episodes.append(key)
                info['vod_play_from'] = '默认线路'
                info['vod_play_url'] = '#'.join(episodes)
            else:
                # 兜底2：iframe
                iframe = re.search(r'<iframe[^>]+src="([^"]+)"', html)
                if iframe:
                    url = iframe.group(1)
                    if not url.startswith('http'):
                        url = urllib.parse.urljoin(self._host or HOSTS[0], url)
                    info['vod_play_from'] = '默认线路'
                    info['vod_play_url'] = f"播放${url}"
        return info

    # ============================================================
    # 公开接口
    # ============================================================

    def homeContent(self, filter):
        html = self._fetch_html("/")
        if not html:
            return {"class": CLASSES, "list": [], "filters": {}}
        categories = self._extract_categories(html)
        videos = self._extract_videos(html)
        filters = {}
        for cat in categories:
            filters[cat["type_id"]] = [
                {"key": "class", "name": "类型", "value": [{"n": "全部", "v": ""}]},
                {"key": "year", "name": "年份", "value": [
                    {"n": "全部", "v": ""},
                    {"n": "2026", "v": "2026"},
                    {"n": "2025", "v": "2025"},
                ]},
            ]
        return {"class": categories, "list": videos[:30], "filters": filters}

    def homeVideoContent(self):
        html = self._fetch_html("/")
        if not html:
            return {"list": []}
        videos = self._extract_videos(html)
        return {"list": videos[:30]}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        urls = [
            f"/vodtype/{tid}/?page={page}",
            f"/vodshow/{tid}-----------/page/{page}.html",
        ]
        html = None
        for u in urls:
            html = self._fetch_html(u)
            if html:
                break
        if not html:
            return {"list": [], "page": page, "pagecount": 1, "limit": 30, "total": 0}
        videos = self._extract_videos(html)
        total_pages = self._get_total_pages(html)
        return {"list": videos, "page": page, "pagecount": total_pages, "limit": 30, "total": 0}

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        encoded = urllib.parse.quote(key)
        url = f"/vodsearch/-------------/?wd={encoded}&page={page}"
        html = self._fetch_html(url)
        if not html:
            return {"list": []}
        videos = self._extract_videos(html)
        return {"list": videos}

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vid = ids[0]
        url = f"/voddetail/{vid}/"
        html = self._fetch_html(url)
        if not html:
            return {"list": []}
        info = self._parse_detail(html, vid)
        return {"list": [info]}

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 0, "url": "", "header": {}}

        if "$" in id:
            parts = id.split("$", 1)
            url = parts[1] if len(parts) == 2 else id
        else:
            url = id

        # 修复相对路径
        if not url.startswith("http"):
            url = urllib.parse.urljoin(self._host or HOSTS[0], url)

        self._log(f"🎬 playerContent 处理: {url}")

        # 1. 直链媒体
        if re.search(r'\.(m3u8|mp4|flv|mkv|ts)', url, re.I):
            return {
                "parse": 0,
                "url": url,
                "header": {"User-Agent": UA, "Referer": self._host + "/" if self._host else HOSTS[0] + "/"}
            }

        # 2. 如果是播放页，提取苹果CMS加密播放器配置
        if "/vodplay/" in url:
            html = self._fetch_html(url, force=True)
            if html:
                self._log(f"📄 播放页HTML长度: {len(html)}")

                # 2.1 提取 player_aaaa（兼容有分号和没分号的情况）
                player_match = None
                for pattern in [
                    r'var player_aaaa=(\{.*?\})</script>',
                    r'var player_aaaa=(\{.*?\});</script>',
                    r'var player_aaaa=(\{.*?\});',
                ]:
                    player_match = re.search(pattern, html, re.S)
                    if player_match:
                        self._log(f"✅ 匹配到player_aaaa (pattern: {pattern[:40]}...)")
                        break

                if player_match:
                    try:
                        import json
                        player_data = json.loads(player_match.group(1))
                        self._log(f"🎬 播放器配置: encrypt={player_data.get('encrypt')}, from={player_data.get('from')}")

                        encrypted_url = player_data.get("url", "")
                        encrypt_type = player_data.get("encrypt", 0)

                        if encrypted_url:
                            real_url = ""
                            # encrypt: 2 = Base64编码后再URL编码
                            if encrypt_type == 2:
                                try:
                                    b64_decoded = base64.b64decode(encrypted_url).decode('utf-8')
                                    real_url = urllib.parse.unquote(b64_decoded)
                                    self._log(f"🔓 Base64+URL解码成功: {real_url[:100]}...")
                                except Exception as e:
                                    self._log(f"⚠️ Base64解码失败: {e}")
                            # encrypt: 1 = 纯URL编码
                            elif encrypt_type == 1:
                                real_url = urllib.parse.unquote(encrypted_url)
                            # encrypt: 0 或其他 = 明文
                            else:
                                real_url = encrypted_url

                            if real_url:
                                self._log(f"🔗 解密URL: {real_url}")
                                if re.search(r'\.(m3u8|mp4|flv)', real_url, re.I):
                                    self._log("✅ 返回parse=0直链")
                                    return {
                                        "parse": 0,
                                        "url": real_url,
                                        "header": {
                                            "User-Agent": UA,
                                            "Referer": self._host + "/" if self._host else HOSTS[0] + "/"
                                        }
                                    }
                                else:
                                    self._log(f"⚠️ 解密URL不是媒体格式: {real_url}")
                    except Exception as e:
                        self._log(f"⚠️ 解析player_aaaa失败: {e}")
                else:
                    self._log("❌ 未找到player_aaaa")

                # 2.2 兜底方案
                iframe = re.search(r'<iframe[^>]+src="([^"]+)"', html)
                if iframe:
                    src = iframe.group(1)
                    if not src.startswith("http"):
                        src = urllib.parse.urljoin(self._host or HOSTS[0], src)
                    self._log(f"🔄 使用iframe兜底: {src}")
                    return {
                        "parse": 1,
                        "url": src,
                        "header": {"User-Agent": UA, "Referer": self._host + "/" if self._host else HOSTS[0] + "/"}
                    }

                video = re.search(r'<video[^>]+src="([^"]+)"', html)
                if video:
                    src = video.group(1)
                    if not src.startswith("http"):
                        src = urllib.parse.urljoin(self._host or HOSTS[0], src)
                    return {
                        "parse": 0,
                        "url": src,
                        "header": {"User-Agent": UA, "Referer": self._host + "/" if self._host else HOSTS[0] + "/"}
                    }

                source = re.search(r'<source[^>]+src="([^"]+)"', html)
                if source:
                    src = source.group(1)
                    if not src.startswith("http"):
                        src = urllib.parse.urljoin(self._host or HOSTS[0], src)
                    return {
                        "parse": 0,
                        "url": src,
                        "header": {"User-Agent": UA, "Referer": self._host + "/" if self._host else HOSTS[0] + "/"}
                    }

                script_matches = re.findall(r'(?:playurl|playUrl|url)\s*[:=]\s*["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)["\']', html, re.I)
                if script_matches:
                    src = script_matches[0]
                    if not src.startswith("http"):
                        src = urllib.parse.urljoin(self._host or HOSTS[0], src)
                    return {
                        "parse": 0,
                        "url": src,
                        "header": {"User-Agent": UA, "Referer": self._host + "/" if self._host else HOSTS[0] + "/"}
                    }

                m3u8_links = re.findall(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', html)
                if m3u8_links:
                    src = m3u8_links[0]
                    return {
                        "parse": 0,
                        "url": src,
                        "header": {"User-Agent": UA, "Referer": self._host + "/" if self._host else HOSTS[0] + "/"}
                    }

        # 3. 默认交给播放器嗅探
        self._log(f"🔄 返回parse=1嗅探: {url}")
        return {
            "parse": 1,
            "url": url,
            "header": {"User-Agent": UA, "Referer": self._host + "/" if self._host else HOSTS[0] + "/"}
        }

    def localProxy(self, param):
        return [200, "video/MP2T", b"", ""]

    def destroy(self):
        self._cache.clear()

    def close(self):
        self.destroy()
