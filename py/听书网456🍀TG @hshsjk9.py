# -*- coding: utf-8 -*-
# 456听书网 (m4560.com) - TVBox 音频爬虫
# 适用于 影视仓/TVBox 听书

import re
import json
import requests
from urllib.parse import quote, urljoin
from base.spider import Spider
from bs4 import BeautifulSoup


class Spider(Spider):
    def getName(self):
        return "456听书网"

    def init(self, extend=""):
        self.host = "https://www.m4560.com"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/",
        })
        # 分类映射（从导航栏提取）
        self.class_map = {
            "言情": "1",
            "武侠": "2",
            "悬疑": "3",
            "历史": "4",
            "军事": "5",
            "评书": "6",
            "相声小品": "7",
            "商业财经": "9",
        }

    def _fix_url(self, url):
        if not url:
            return ""
        if url.startswith("http"):
            return url
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host + url
        return self.host + "/" + url

    def _fetch(self, url, timeout=15):
        try:
            resp = self.session.get(url, timeout=timeout)
            if resp.status_code == 200:
                resp.encoding = "utf-8"
                return resp.text
            return ""
        except Exception as e:
            print(f"[{self.getName()}] 请求失败: {e}")
            return ""

    # ==================== 首页分类 ====================

    def homeContent(self, filter=False):
        classes = [{"type_id": v, "type_name": k} for k, v in self.class_map.items()]
        return {"class": classes}

    # ==================== 首页推荐 ====================

    def homeVideoContent(self):
        try:
            html = self._fetch("/")
            if not html:
                return {"list": []}
            audios = self._extract_audios(html)
            return {"list": audios[:30]}
        except Exception as e:
            print(f"[{self.getName()}] homeVideoContent 异常: {e}")
            return {"list": []}

    # ==================== 音频提取 ====================

    def _extract_audios(self, html, is_search=False):
        """提取音频列表（首页、分类、搜索通用）"""
        soup = BeautifulSoup(html, "html.parser")
        audios = []
        seen = set()

        for li in soup.select(".stui-vodlist li"):
            if not li.find("a"):
                continue

            thumb = li.find("a", class_="stui-vodlist__thumb")
            if thumb:
                pic = thumb.get("data-original", "") or thumb.get("src", "")
                href = thumb.get("href", "")
            else:
                a = li.find("a")
                if a:
                    href = a.get("href", "")
                    img = a.find("img")
                    pic = img.get("data-original", "") if img else ""
                else:
                    continue

            if "/mp3/" not in href:
                continue
            m = re.search(r"/mp3/(\d+)\.html", href)
            vod_id = m.group(1) if m else ""
            if not vod_id or vod_id in seen:
                continue
            seen.add(vod_id)

            detail = li.find("div", class_="stui-vodlist__detail")
            if detail:
                title_a = detail.find("h4").find("a") if detail.find("h4") else None
                title = title_a.get_text(strip=True) if title_a else ""
                author = detail.find("p", class_="text-muted")
                author_text = author.get_text(strip=True) if author else ""
            else:
                title = thumb.get("title", "") if thumb else ""

            pic_text = thumb.find("span", class_="pic-text") if thumb else None
            remarks = pic_text.get_text(strip=True) if pic_text else ""

            if pic and not pic.startswith("http"):
                pic = self._fix_url(pic)

            audios.append({
                "vod_id": vod_id,
                "vod_name": title or f"音频{vod_id}",
                "vod_pic": pic,
                "vod_remarks": remarks or author_text,
            })

        return audios

    def _extract_pagecount(self, html):
        """提取总页数"""
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.select(".page a, .pagination a"):
            if "尾页" in a.get_text() or "末页" in a.get_text():
                href = a.get("href", "")
                m = re.search(r"page[/=](\d+)", href)
                if m:
                    try:
                        return int(m.group(1))
                    except:
                        pass
        for a in soup.select(".page a, .pagination a"):
            text = a.get_text(strip=True)
            if text.isdigit() and int(text) > 10:
                try:
                    return int(text)
                except:
                    pass
        return 1

    # ==================== 分类列表 ====================

    def categoryContent(self, tid, pg, filter=False, extend=None):
        try:
            pg = int(pg) if str(pg).isdigit() else 1
            url = f"{self.host}/list/{tid}-{pg}.html"
            html = self._fetch(url)
            if not html:
                return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 0}

            audios = self._extract_audios(html)
            pagecount = self._extract_pagecount(html)

            return {
                "list": audios,
                "page": pg,
                "pagecount": pagecount if pagecount > 1 else pg + 1,
                "limit": 24,
                "total": pagecount * 24 if pagecount > 1 else len(audios),
            }
        except Exception as e:
            print(f"[{self.getName()}] categoryContent 异常: {e}")
            return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 0}

    # ==================== 详情页 ====================

    def detailContent(self, ids):
        try:
            vod_id = ids[0]
            if "/mp3/" in vod_id:
                m = re.search(r"/mp3/(\d+)\.html", vod_id)
                if m:
                    vod_id = m.group(1)

            url = f"{self.host}/mp3/{vod_id}.html"
            html = self._fetch(url)
            if not html:
                return {"list": []}

            soup = BeautifulSoup(html, "html.parser")

            title = ""
            title_h1 = soup.select_one(".stui-content__detail h1.title")
            if title_h1:
                title = title_h1.get_text(strip=True)
            if not title:
                title_match = re.search(r"<title>(.*?)</title>", html)
                if title_match:
                    title = title_match.group(1).strip()

            pic = ""
            thumb = soup.select_one(".stui-content__thumb img")
            if thumb:
                pic = thumb.get("data-original", "") or thumb.get("src", "")
            pic = self._fix_url(pic)

            author = ""
            detail = soup.select_one(".stui-content__detail")
            if detail:
                for p in detail.find_all("p", class_="data"):
                    text = p.get_text(strip=True)
                    if "作者" in text or "主播" in text:
                        author = text.replace("作者：", "").replace("主播：", "").strip()
                        break

            intro = ""
            desc_div = soup.find("div", id="desc")
            if desc_div:
                intro = desc_div.get_text(strip=True)

            chapters = []
            playlist = soup.select_one(".stui-content__playlist")
            if playlist:
                for li in playlist.find_all("li"):
                    a = li.find("a")
                    if a:
                        href = a.get("href", "")
                        name = a.get_text(strip=True)
                        if href:
                            chapters.append({
                                "name": name or f"第{len(chapters)+1}集",
                                "url": self._fix_url(href)
                            })

            if chapters:
                play_url = "#".join([f"{item['name']}${item['url']}" for item in chapters])
            else:
                play_url = f"第1集${url}"

            return {
                "list": [{
                    "vod_id": vod_id,
                    "vod_name": title or f"音频{vod_id}",
                    "vod_pic": pic,
                    "vod_content": f"作者/主播：{author}\n{intro}" if author else intro,
                    "vod_play_from": "音频集",
                    "vod_play_url": play_url,
                }]
            }
        except Exception as e:
            print(f"[{self.getName()}] detailContent 异常: {e}")
            return {"list": []}

    # ==================== 播放（提取音频地址） ====================

    def playerContent(self, flag, id, vipFlags=None):
        try:
            result = {"parse": 0, "playUrl": "", "url": "", "header": {}}
            if not id or id == "#":
                return result

            # 如果 id 是音频直链
            if id.startswith("http") and (
                ".mp3" in id or ".m4a" in id or ".aac" in id or ".ogg" in id or ".m3u8" in id
            ):
                result["url"] = id
                result["header"] = {
                    "Referer": self.host + "/",
                    "User-Agent": self.session.headers.get("User-Agent", "Mozilla/5.0"),
                }
                return result

            # 如果是播放页链接
            if "/mp3/" in id or "/play/" in id:
                if not id.startswith("http"):
                    id = self._fix_url(id)
                html = self._fetch(id)
                if html:
                    audio_url = None

                    # var now = '...'
                    m = re.search(r'var\s+now\s*=\s*["\']([^"\']+\.(?:mp3|m4a|aac|ogg|m3u8)[^"\']*)["\']', html)
                    if m:
                        audio_url = m.group(1)
                    if not audio_url:
                        m = re.search(r'var\s+url\s*=\s*["\']([^"\']+\.(?:mp3|m4a|aac|ogg|m3u8)[^"\']*)["\']', html)
                        if m:
                            audio_url = m.group(1)
                    if not audio_url:
                        m = re.search(r'<source[^>]+src=["\']([^"\']+\.(?:mp3|m4a|aac|ogg|m3u8)[^"\']*)["\']', html)
                        if m:
                            audio_url = m.group(1)
                    if not audio_url:
                        m = re.search(r'<audio[^>]+src=["\']([^"\']+\.(?:mp3|m4a|aac|ogg|m3u8)[^"\']*)["\']', html)
                        if m:
                            audio_url = m.group(1)
                    if not audio_url:
                        m = re.search(r'(https?://[^\s"\'<>]+\.(?:mp3|m4a|aac|ogg|m3u8)[^\s"\'<>]*)', html)
                        if m:
                            audio_url = m.group(1)

                    if audio_url:
                        if audio_url.startswith("//"):
                            audio_url = "https:" + audio_url
                        elif audio_url.startswith("/"):
                            audio_url = self._fix_url(audio_url)
                        elif not audio_url.startswith("http"):
                            audio_url = self._fix_url(audio_url)

                        result["url"] = audio_url
                        result["header"] = {
                            "Referer": self.host + "/",
                            "User-Agent": self.session.headers.get("User-Agent", "Mozilla/5.0"),
                        }
                        return result

            if id.startswith("/"):
                id = self._fix_url(id)
                result["url"] = id
                result["header"] = {
                    "Referer": self.host + "/",
                    "User-Agent": self.session.headers.get("User-Agent", "Mozilla/5.0"),
                }
                return result

            result["url"] = id
            result["header"] = {
                "Referer": self.host + "/",
                "User-Agent": self.session.headers.get("User-Agent", "Mozilla/5.0"),
            }
            return result
        except Exception as e:
            print(f"[{self.getName()}] playerContent 异常: {e}")
            return {"parse": 0, "playUrl": "", "url": id if id else "", "header": {}}

    # ==================== 搜索 ====================

    def searchContent(self, key, quick=False, pg="1"):
        try:
            pg = int(pg) if str(pg).isdigit() else 1
            enc_key = quote(key)
            url = f"{self.host}/search.php?searchword={enc_key}&page={pg}"
            html = self._fetch(url)
            if not html:
                return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 0}

            audios = self._extract_audios(html, is_search=True)
            pagecount = self._extract_pagecount(html)

            return {
                "list": audios,
                "page": pg,
                "pagecount": pagecount if pagecount > 1 else pg + 1,
                "limit": 24,
                "total": pagecount * 24 if pagecount > 1 else len(audios),
            }
        except Exception as e:
            print(f"[{self.getName()}] searchContent 异常: {e}")
            return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 0}

    def isVideoFormat(self, url):
        audio_formats = [".mp3", ".m4a", ".aac", ".ogg", ".m3u8"]
        return url and any(fmt in url for fmt in audio_formats)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        if self.session:
            self.session.close()