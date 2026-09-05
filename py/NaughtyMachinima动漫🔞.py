# -*- coding: utf-8 -*-
# TVBox爬虫 - Naughty Machinima (3D动画成人视频)
# 网站: https://www.naughtymachinima.com

import sys
import re
import json
import urllib.parse
from base.spider import Spider
from bs4 import BeautifulSoup
import requests


class Spider(Spider):
    def getName(self):
        return "NaughtyMachinima"

    def init(self, extend=""):
        self.host = "https://www.naughtymachinima.com"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": self.host,
        })
        self.class_map = {
            "popular": "热门",
            "latest": "最新",
        }
        self.debug = False

    def _log(self, msg):
        if self.debug:
            print(f"[Naughty] {msg}")

    def _fetch(self, url, timeout=15):
        try:
            self._log(f"Fetch: {url}")
            resp = self.session.get(url, timeout=timeout)
            resp.encoding = "utf-8"
            return resp.text
        except Exception as e:
            self._log(f"Fetch error: {e}")
            return ""

    def _fix_url(self, url):
        if not url:
            return ""
        url = url.strip()
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host + url
        if not url.startswith("http"):
            return self.host + "/" + url
        return url

    # ---------- 首页分类 ----------
    def homeContent(self, filter=False):
        classes = [{"type_id": cid, "type_name": name} for cid, name in self.class_map.items()]
        return {"class": classes}

    def homeVideoContent(self):
        return self.categoryContent("popular", "1", False, {})

    # ---------- 分类列表 ----------
    def categoryContent(self, tid, pg, filter=False, extend=None):
        try:
            pg = int(pg) if pg else 1
            tid_str = str(tid)

            # 构造分类URL
            if tid_str == "popular":
                base_url = self.host + "/videos?o=bw"
            elif tid_str == "latest":
                base_url = self.host + "/videos"
            else:
                return {"list": [], "page": pg, "pagecount": 1, "limit": 0, "total": 0}

            # 分页参数（有些页面可能支持 &page=2）
            if pg > 1:
                if "?" in base_url:
                    url = base_url + "&page=" + str(pg)
                else:
                    url = base_url + "?page=" + str(pg)
            else:
                url = base_url

            html = self._fetch(url)
            if not html:
                return {"list": [], "page": pg, "pagecount": 1, "limit": 0, "total": 0}

            videos = self._parse_video_list(html)

            # 简单分页（假设有更多页，但无法获取总页数，默认 pagecount = pg + 1 如果列表满20个）
            pagecount = pg
            if len(videos) >= 20:
                pagecount = pg + 1

            return {
                "list": videos,
                "page": pg,
                "pagecount": pagecount,
                "limit": len(videos),
                "total": pagecount * 20
            }
        except Exception as e:
            self._log(f"categoryContent异常: {e}")
            return {"list": [], "page": 1, "pagecount": 1, "limit": 0, "total": 0}

    # ---------- 解析视频列表 ----------
    def _parse_video_list(self, html):
        soup = BeautifulSoup(html, "html.parser")
        videos = []
        seen = set()

        # 选择所有包含 /video/ 的 a 标签
        for a in soup.select('a[href^="/video/"]'):
            try:
                # 检查是否有 thumb-overlay（避免广告）
                overlay = a.find('div', class_='thumb-overlay')
                if not overlay:
                    continue

                video_url = a.get('href')
                if not video_url or video_url in seen:
                    continue
                seen.add(video_url)

                # 提取视频ID
                vid_match = re.search(r'/video/(\d+)/', video_url)
                if not vid_match:
                    continue
                vid = vid_match.group(1)

                # 标题
                title = a.get('title') or ''
                if not title:
                    img = a.find('img')
                    if img:
                        title = img.get('title') or img.get('alt') or ''

                # 封面图
                img = a.find('img')
                pic = img.get('src') if img else ''
                if pic.startswith('//'):
                    pic = 'https:' + pic

                # 时长
                duration_tag = a.find('div', class_='duration')
                duration = duration_tag.get_text(strip=True) if duration_tag else ''

                # 观看数等（从 content-info 提取）
                # 获取外层容器（a 的父级的父级）
                parent_div = a.parent  # 这是包含 thumb-overlay 的div
                outer_div = parent_div.parent if parent_div else None
                content_info = outer_div.find('div', class_='content-info') if outer_div else None
                views_text = ''
                if content_info:
                    views_span = content_info.find('span', class_='content-views')
                    if views_span:
                        views_text = views_span.get_text(strip=True)
                remark = duration
                if views_text:
                    remark += ' | ' + views_text

                videos.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remark
                })
            except Exception as e:
                self._log(f"解析卡片失败: {e}")
                continue

        self._log(f"解析到 {len(videos)} 个视频")
        return videos

    # ---------- 搜索 ----------
    def searchContent(self, key, quick=False, pg="1"):
        try:
            pg = int(pg) if pg else 1
            enc_key = urllib.parse.quote(key)
            # 搜索URL（POST方式，但也可以通过GET？实际搜索表单是POST）
            # 我们尝试使用 GET 参数，但不确定是否支持
            url = self.host + "/search/videos?search_query=" + enc_key + "&page=" + str(pg)
            html = self._fetch(url)
            if not html:
                return {"list": [], "page": pg, "pagecount": 1, "limit": 0, "total": 0}
            videos = self._parse_video_list(html)
            pagecount = pg + 1 if len(videos) >= 20 else pg
            return {
                "list": videos,
                "page": pg,
                "pagecount": pagecount,
                "limit": len(videos),
                "total": pagecount * 20
            }
        except Exception as e:
            self._log(f"searchContent异常: {e}")
            return {"list": [], "page": 1, "pagecount": 1, "limit": 0, "total": 0}

    # ---------- 详情 ----------
    def detailContent(self, ids):
        try:
            if not ids:
                return {"list": []}
            vid = ids[0]
            url = self.host + "/video/" + vid
            html = self._fetch(url)
            if not html:
                return {"list": []}

            soup = BeautifulSoup(html, "html.parser")

            # 标题
            title = ""
            title_tag = soup.find("h1")
            if title_tag:
                title = title_tag.get_text(strip=True)
            if not title:
                meta_title = soup.find("meta", property="og:title")
                if meta_title:
                    title = meta_title.get("content", "")

            # 封面
            pic = ""
            img_tag = soup.find("img", class_="img-responsive") or soup.find("video")
            if img_tag:
                pic = img_tag.get("poster") or img_tag.get("src") or ""
            if not pic:
                img_tag = soup.find("img")
                if img_tag:
                    pic = img_tag.get("src") or ""
            if pic.startswith("//"):
                pic = "https:" + pic

            # 简介（meta description）
            desc = ""
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if meta_desc:
                desc = meta_desc.get("content", "")

            # 尝试提取播放地址
            play_url = self._extract_video(html)

            if play_url:
                play_url = "播放$" + play_url
            else:
                # 降级：直接打开详情页
                play_url = "详情页$" + url

            return {
                "list": [{
                    "vod_id": vid,
                    "vod_name": title or "未知视频",
                    "vod_pic": pic,
                    "vod_content": desc,
                    "vod_play_from": "NaughtyMachinima",
                    "vod_play_url": play_url
                }]
            }
        except Exception as e:
            self._log(f"detailContent异常: {e}")
            return {"list": []}

    # ---------- 提取视频播放地址 ----------
    def _extract_video(self, html):
        # 1. 找 <video> 标签的 src 或 source
        video_srcs = re.findall(r'<video[^>]+src=["\']([^"\']+)["\']', html, re.I)
        if video_srcs:
            return self._fix_url(video_srcs[0])
        sources = re.findall(r'<source[^>]+src=["\']([^"\']+)["\']', html, re.I)
        if sources:
            return self._fix_url(sources[0])

        # 2. 找 iframe
        iframes = re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', html, re.I)
        if iframes:
            # 如果有 iframe，可能是嵌入的播放器，直接返回 iframe URL（但 TVBox 不一定能播放）
            return self._fix_url(iframes[0])

        # 3. 找 JS 中的视频变量（常见如 video_url, file, source）
        patterns = [
            r'(?:video|file|source|url)\s*[:=]\s*["\']([^"\']+\.(?:m3u8|mp4|webm))["\']',
            r'"video"\s*:\s*["\']([^"\']+)["\']',
            r'"url"\s*:\s*["\']([^"\']+)["\']',
        ]
        for pat in patterns:
            m = re.search(pat, html, re.I)
            if m:
                return self._fix_url(m.group(1))

        # 4. 直接找 .m3u8 或 .mp4 链接
        m = re.search(r'(https?://[^\s"\']+\.(?:m3u8|mp4)[^\s"\']*)', html)
        if m:
            return self._fix_url(m.group(1))

        return None

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags=None):
        try:
            if not id:
                return {"parse": 1, "url": "", "header": {}}

            # 如果包含 "$"，提取后面的部分
            if "$" in id:
                parts = id.split("$")
                if len(parts) > 1:
                    id = parts[-1]

            # 检查是否为直链
            if re.search(r'\.(m3u8|mp4|webm|flv)', id, re.I):
                return {
                    "parse": 0,
                    "url": id,
                    "header": {
                        "User-Agent": "Mozilla/5.0",
                        "Referer": self.host
                    }
                }
            else:
                # 否则用 WebView 打开详情页
                if not id.startswith("http"):
                    id = self._fix_url(id)
                return {
                    "parse": 1,
                    "url": id,
                    "header": {
                        "User-Agent": "Mozilla/5.0",
                        "Referer": self.host
                    }
                }
        except Exception as e:
            self._log(f"playerContent异常: {e}")
            return {"parse": 1, "url": id or "", "header": {}}

    # ---------- 辅助 ----------
    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        if self.session:
            self.session.close()

    def localProxy(self, param):
        return None