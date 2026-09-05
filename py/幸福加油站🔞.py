# -*- coding: utf-8 -*-


import sys
import re
import json
import requests
from urllib import parse
from bs4 import BeautifulSoup

sys.path.append("..")
from base.spider import Spider


class Spider(Spider):
    def __init__(self):
        self.siteUrl = "https://887717.xyz"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.siteUrl,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        self.session = requests.Session()

    def getName(self):
        return "887717"

    def init(self, extend=""):
        return

    def isVideoFormat(self, url):
        return any(ext in url.lower() for ext in [".m3u8", ".mp4", ".flv", ".ts", ".mkv"])

    def manualVideoCheck(self):
        return False

    # ───────── 源天书 · 定龙脉 ─────────
    def fetch(self, url):
        try:
            resp = self.session.get(url, headers=self.headers, timeout=10)
            resp.encoding = "utf-8"
            return resp.text
        except Exception as e:
            print(f"[源天书] 定龙脉失败: {e}")
            return ""

    # ───────── 临字秘 · 首页分类 ─────────
    def homeContent(self, filter):
        html = self.fetch(self.siteUrl)
        if not html:
            return {"class": []}

        soup = BeautifulSoup(html, "html.parser")
        classes = []
        seen = set()

        # 从主导航提取WP分类（只取taxonomy类型）
        menu = soup.find("ul", id="menu-main-menu")
        if menu:
            for li in menu.find_all("li", class_="menu-item-type-taxonomy"):
                a = li.find("a")
                if not a:
                    continue
                href = a.get("href", "")
                title = a.get("title", "") or a.get_text(strip=True)
                if not href or not title:
                    continue
                # 提取slug： https://887717.xyz/slug/ → slug
                slug = href.rstrip("/").split("/")[-1]
                slug = parse.unquote(slug)
                if slug and slug not in seen:
                    seen.add(slug)
                    classes.append({"type_id": slug, "type_name": title})

        # 者字秘兜底：若提取失败，硬编码主分类（基于当前HTML菜单）
        if not classes:
            classes = [
                {"type_id": "91大神", "type_name": "91"},
                {"type_id": "国产自拍", "type_name": "自拍"},
                {"type_id": "探花", "type_name": "探花"},
                {"type_id": "ribenyouma", "type_name": "日韩"},
                {"type_id": "自拍泄露", "type_name": "网曝"},
                {"type_id": "欧美中字", "type_name": "欧美"},
                {"type_id": "美女裸聊", "type_name": "裸聊"},
                {"type_id": "日本无码", "type_name": "无码"},
                {"type_id": "fc2无码", "type_name": "FC2"},
            ]

        return {"class": classes}

    # ───────── 斗字秘 · 列表提取 ─────────
    def categoryContent(self, tid, pg, filter, extend):
        tid = parse.quote(tid, safe="")
        page_str = f"page/{int(pg)}/" if int(pg) > 1 else ""
        url = f"{self.siteUrl}/{tid}/{page_str}"

        html = self.fetch(url)
        videos = []

        if html:
            soup = BeautifulSoup(html, "html.parser")
            for block in soup.select(".video-block"):
                a_thumb = block.select_one("a.thumb")
                a_info = block.select_one("a.infos")
                img = block.select_one("img.video-img")
                views = block.select_one(".views-number")

                if a_thumb and a_info:
                    href = a_thumb.get("href", "")
                    # 统一存相对路径，减少数据体积
                    vid = href.replace(self.siteUrl, "") if href.startswith(self.siteUrl) else href
                    name = a_info.get("title", "") or a_info.get_text(strip=True)
                    # 斗字秘核心：取data-src（懒加载），非src
                    pic = img.get("data-src", "") if img else ""
                    remark = views.get_text(strip=True) if views else ""

                    videos.append({
                        "vod_id": vid,
                        "vod_name": name,
                        "vod_pic": pic,
                        "vod_remarks": remark,
                    })

        return {
            "list": videos,
            "page": int(pg),
            "pagecount": 9999,
            "limit": 24,
            "total": 99999,
        }

    # ───────── 前字秘 · 五层详情解析 ─────────
    def detailContent(self, ids):
        vid = ids[0]
        url = f"{self.siteUrl}{vid}" if vid.startswith("/") else f"{self.siteUrl}/{vid}"
        html = self.fetch(url)
        play_url = ""

        if html:
            # 第一层：直链m3u8/mp4
            m = re.search(r'(https?://[^\s"\'<>]+\.(?:m3u8|mp4)(?:\?[^\s"\'<>]*)?)', html)
            if m:
                play_url = m.group(1)
            else:
                # 第二层：video标签
                m = re.search(r'<video[^>]+src=["\']([^"\']+)["\']', html)
                if m:
                    play_url = m.group(1)
                else:
                    # 第三层：iframe嵌入
                    m = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html)
                    if m:
                        play_url = m.group(1)
                    else:
                        # 第四层：JS变量
                        m = re.search(r'(?:var|let|const)\s+(?:url|src|video_url|play_url)\s*=\s*["\']([^"\']+)["\']', html)
                        if m:
                            play_url = m.group(1)
                        else:
                            # 第五层：JSON中的url字段
                            m = re.search(r'"url"\s*:\s*"([^"]+)"', html)
                            if m:
                                play_url = m.group(1)

        # 该站为单集短视频模式，无需多集拼接
        play_url_str = f"第1集${play_url}" if play_url else ""

        return {
            "list": [{
                "vod_id": vid,
                "vod_name": "视频详情",
                "vod_play_from": "直链",
                "vod_play_url": play_url_str,
            }]
        }

    # ───────── 阵字秘 · 播放直取 ─────────
    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {}
        # 预置Referer防图片/视频403
        return {
            "parse": 0,
            "url": id,
            "header": json.dumps(self.headers),
        }

    # ───────── 列字秘 · 搜索 ─────────
    def searchContent(self, key, quick, pg="1"):
        pg = int(pg)
        if pg > 1:
            url = f"{self.siteUrl}/page/{pg}/?s={parse.quote(key)}"
        else:
            url = f"{self.siteUrl}/?s={parse.quote(key)}"

        html = self.fetch(url)
        videos = []

        if html:
            soup = BeautifulSoup(html, "html.parser")
            for block in soup.select(".video-block"):
                a_thumb = block.select_one("a.thumb")
                a_info = block.select_one("a.infos")
                img = block.select_one("img.video-img")
                views = block.select_one(".views-number")

                if a_thumb and a_info:
                    href = a_thumb.get("href", "")
                    vid = href.replace(self.siteUrl, "") if href.startswith(self.siteUrl) else href
                    name = a_info.get("title", "") or a_info.get_text(strip=True)
                    pic = img.get("data-src", "") if img else ""
                    remark = views.get_text(strip=True) if views else "搜索"
                    videos.append({
                        "vod_id": vid,
                        "vod_name": name,
                        "vod_pic": pic,
                        "vod_remarks": remark,
                    })

        return {
            "list": videos,
            "page": pg,
            "pagecount": 9999,
            "limit": 24,
            "total": 99999,
        }

    def localProxy(self, param):
        return [200, "video/MP2T", "", ""]
