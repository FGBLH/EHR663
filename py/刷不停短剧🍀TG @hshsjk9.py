# -*- coding: utf-8 -*-
"""
目标站: 刷不停短剧网
站点: https://duan.brloop.com/
说明: MacCMS / 海洋CMS 类站点爬虫，支持首页、分类、详情、搜索和播放解析。
"""
import json
import re
import sys
import urllib.parse

from bs4 import BeautifulSoup

sys.path.append("..")
from base.spider import Spider


class Spider(Spider):
    def init(self, extend=""):
        self.site_url = "https://duan.brloop.com"
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": self.site_url + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        self.categories = self._fetch_categories()

    def _default_categories(self):
        return [
            {"type_id": "duanju", "type_name": "短剧"},
            {"type_id": "dianying", "type_name": "电影"},
            {"type_id": "dianshi", "type_name": "电视"},
            {"type_id": "dongman", "type_name": "动漫"},
            {"type_id": "zongyi", "type_name": "综艺"},
            {"type_id": "jilupian", "type_name": "纪录片"},
        ]

    def _fetch_categories(self):
        try:
            resp = self.fetch(self.site_url + "/", headers=self.headers)
            if not resp:
                return self._default_categories()

            soup = BeautifulSoup(resp.text, "html.parser")
            categories = []
            seen = set()
            for a in soup.select("a[href^='/t'], a[href^='https://duan.brloop.com/t']"):
                href = a.get("href", "")
                name = a.get("title") or a.get_text(strip=True)
                match = re.search(r"/t([a-zA-Z0-9_]+)(?:-\d+)?/?", href)
                if not match:
                    continue
                tid = match.group(1)
                if tid in seen or not name or name in ["首页"]:
                    continue
                if tid in ["duanju", "dianying", "dianshi", "dongman", "zongyi", "jilupian"]:
                    seen.add(tid)
                    categories.append({"type_id": tid, "type_name": name})

            return categories or self._default_categories()
        except Exception as e:
            print(f"[刷不停短剧] 获取分类失败: {e}")
            return self._default_categories()

    def _fix_url(self, url):
        if not url:
            return ""
        url = url.strip()
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return urllib.parse.urljoin(self.site_url, url)
        if not url.startswith("http"):
            return urllib.parse.urljoin(self.site_url + "/", url)
        return url

    def _clean_text(self, text):
        if not text:
            return ""
        return re.sub(r"\s+", " ", text).strip()

    def _parse_video_list(self, html):
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        results = []
        seen = set()

        for a in soup.select('a[href*="/vid/"]'):
            href = a.get("href", "")
            match = re.search(r"/vid/(\d+)/", href)
            if not match:
                continue

            vod_id = match.group(1)
            if vod_id in seen:
                continue
            seen.add(vod_id)

            title = a.get("title") or a.get_text(strip=True)
            if not title:
                title_elem = a.find_parent().select_one(".title a") if a.find_parent() else None
                title = title_elem.get("title") or title_elem.get_text(strip=True) if title_elem else ""
            title = self._clean_text(title)
            if not title:
                continue

            pic = a.get("data-original") or a.get("data-src") or ""
            img = a.select_one("img")
            if img and not pic:
                pic = img.get("data-original") or img.get("data-src") or img.get("src") or ""

            remark = ""
            parent = a
            for _ in range(5):
                parent = parent.parent if parent else None
                if not parent:
                    break
                if not pic:
                    img2 = parent.select_one("img, a[data-original], a[data-src]")
                    if img2:
                        pic = img2.get("data-original") or img2.get("data-src") or img2.get("src") or ""
                note = parent.select_one(".pic-text, .module-item-note, .remarks, .text-right")
                if note:
                    remark = self._clean_text(note.get_text())
                    break

            results.append(
                {
                    "vod_id": vod_id,
                    "vod_name": title,
                    "vod_pic": self._fix_url(pic),
                    "vod_remarks": remark,
                }
            )

        return results

    def homeContent(self, filter):
        resp = self.fetch(self.site_url + "/", headers=self.headers)
        video_list = self._parse_video_list(resp.text)[:40] if resp else []
        return {"class": self.categories, "list": video_list, "filters": {}}

    def homeVideoContent(self):
        return self.homeContent(False)

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        urls = []
        if page <= 1:
            urls.extend(
                [
                    f"{self.site_url}/t{tid}/",
                    f"{self.site_url}/t{tid}-1/",
                    f"{self.site_url}/shw/{tid}-----------/",
                ]
            )
        else:
            urls.extend(
                [
                    f"{self.site_url}/t{tid}-{page}/",
                    f"{self.site_url}/shw/{tid}-----------{page}/",
                ]
            )

        html_text = ""
        for url in urls:
            resp = self.fetch(url, headers=self.headers)
            if resp and resp.text and "页面不存在" not in resp.text:
                html_text = resp.text
                break

        if not html_text:
            return {"list": [], "page": page, "pagecount": 1, "limit": 24, "total": 0}

        video_list = self._parse_video_list(html_text)
        pagecount = self._parse_pagecount(html_text, page)
        return {
            "list": video_list,
            "page": page,
            "pagecount": pagecount,
            "limit": 24,
            "total": max(len(video_list) * pagecount, len(video_list)),
        }

    def _parse_pagecount(self, html, current_page):
        nums = [current_page]
        for text in re.findall(r"(\d+)\s*/\s*(\d+)", html):
            nums.append(int(text[1]))
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.select(".stui-page a, .stui-page-text a, .pagination a, .page a"):
            t = a.get_text(strip=True)
            if t.isdigit():
                nums.append(int(t))
            href = a.get("href", "")
            for n in re.findall(r"-(\d+)/", href):
                nums.append(int(n))
        return max(nums) if nums else current_page

    def detailContent(self, ids):
        if not ids:
            return {"list": []}

        vod_id = ids[0]
        url = f"{self.site_url}/vid/{vod_id}/"
        resp = self.fetch(url, headers=self.headers)
        if not resp:
            return {"list": []}

        soup = BeautifulSoup(resp.text, "html.parser")

        title_elem = soup.select_one(".stui-content__detail .title, h1, h3.title")
        vod_name = self._clean_text(title_elem.get_text()) if title_elem else vod_id

        img_elem = soup.select_one(".stui-content__thumb img, .picture img, .vod-pic img")
        vod_pic = ""
        if img_elem:
            vod_pic = img_elem.get("data-original") or img_elem.get("data-src") or img_elem.get("src") or ""
            vod_pic = self._fix_url(vod_pic)

        detail_text = soup.select_one(".stui-content__detail")
        detail_text = detail_text.get_text(" ", strip=True) if detail_text else ""

        vod_actor = self._extract_field(resp.text, "主演")
        vod_director = self._extract_field(resp.text, "导演")
        vod_area = self._extract_field(resp.text, "地区")
        vod_year = self._extract_field(resp.text, "年份")
        vod_type = self._extract_field(resp.text, "类型")

        content_elem = soup.select_one(".detail-content, .desc, .seo-hidden")
        vod_content = self._clean_text(content_elem.get_text(" ", strip=True)) if content_elem else ""

        play_from_list = []
        play_url_list = []
        playlist_boxes = soup.select(".playlist, .stui-content__playlist")
        if not playlist_boxes:
            playlist_boxes = soup.select("ul:has(a[href*='/plei/'])")

        for idx, block in enumerate(playlist_boxes):
            title_node = block.find_previous(["h3", "h4"])
            line_name = self._clean_text(title_node.get_text()) if title_node else f"播{idx + 1}"
            episodes = []
            seen_ep = set()
            for a in block.select('a[href*="/plei/"]'):
                href = a.get("href", "")
                ep_match = re.search(r"/plei/\d+-\d+-\d+/", href)
                if not ep_match or href in seen_ep:
                    continue
                seen_ep.add(href)
                ep_name = self._clean_text(a.get_text()) or f"第{len(episodes) + 1}集"
                episodes.append(f"{ep_name}${self._fix_url(href)}")
            if episodes:
                play_from_list.append(line_name or f"播{idx + 1}")
                play_url_list.append("#".join(episodes))

        if not play_url_list:
            episodes = []
            for a in soup.select('a[href*="/plei/"]'):
                href = a.get("href", "")
                ep_name = self._clean_text(a.get_text()) or f"第{len(episodes) + 1}集"
                episodes.append(f"{ep_name}${self._fix_url(href)}")
            if episodes:
                play_from_list.append("默认线路")
                play_url_list.append("#".join(episodes))

        vod = {
            "vod_id": vod_id,
            "vod_name": vod_name,
            "vod_pic": vod_pic,
            "type_name": vod_type,
            "vod_year": vod_year,
            "vod_area": vod_area,
            "vod_remarks": "",
            "vod_actor": vod_actor,
            "vod_director": vod_director,
            "vod_content": vod_content or detail_text,
            "vod_play_from": "$$$".join(play_from_list) if play_from_list else "默认线路",
            "vod_play_url": "$$$".join(play_url_list) if play_url_list else f"播放${vod_id}",
        }
        return {"list": [vod]}

    def _extract_field(self, html, field_name):
        text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
        patterns = [
            rf"{field_name}：\s*(.*?)(?:导演：|主演：|类型：|地区：|年份：|语言：|别名：|更新：|简介：|$)",
            rf"{field_name}:\s*(.*?)(?:导演:|主演:|类型:|地区:|年份:|语言:|别名:|更新:|简介:|$)",
        ]
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                value = self._clean_text(m.group(1))
                value = re.sub(r"\s+", ",", value)
                return value.strip(",")
        return ""

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        encoded_key = urllib.parse.quote(key)
        urls = [
            f"{self.site_url}/sch/----------{page}---{encoded_key}/",
            f"{self.site_url}/sch/-------------/?wd={encoded_key}",
        ]
        html_text = ""
        for url in urls:
            resp = self.fetch(url, headers=self.headers)
            if resp and resp.text and "页面不存在" not in resp.text:
                html_text = resp.text
                break
        video_list = self._parse_video_list(html_text) if html_text else []
        pagecount = self._parse_pagecount(html_text, page) if html_text else 1
        return {"list": video_list, "page": page, "pagecount": pagecount}

    def playerContent(self, flag, id, vipFlags):
        play_url = self._fix_url(id)
        headers = dict(self.headers)
        headers["Referer"] = self.site_url + "/"

        if re.search(r"\.(m3u8|mp4|flv)(\?|$)", play_url, re.I):
            return {"parse": 0, "url": play_url, "header": headers}

        resp = self.fetch(play_url, headers=headers)
        if not resp:
            return {"parse": 1, "url": play_url, "header": headers}

        html = resp.text

        player_match = re.search(r"var\s+player_aaaa\s*=\s*({.*?})</script>", html, re.S)
        if not player_match:
            player_match = re.search(r"var\s+player_aaaa\s*=\s*({[^;]+});", html, re.S)

        if player_match:
            try:
                data = json.loads(player_match.group(1))
                url = data.get("url", "")
                if url:
                    url = url.replace("\\/", "/")
                    if data.get("encrypt") == 1:
                        url = urllib.parse.unquote(url)
                    elif data.get("encrypt") == 2:
                        import base64

                        url = base64.b64decode(url).decode("utf-8")
                    if re.search(r"\.(m3u8|mp4|flv)", url, re.I):
                        return {"parse": 0, "url": self._fix_url(url), "header": headers}
                    return {"parse": 1, "url": self._fix_url(url), "header": headers}
            except Exception as e:
                print(f"[刷不停短剧] player_aaaa 解析失败: {e}")

        direct = re.search(r"(https?://[^\s\"']+\.(?:m3u8|mp4|flv)[^\s\"']*)", html, re.I)
        if direct:
            return {"parse": 0, "url": direct.group(1), "header": headers}

        iframe = re.search(r"<iframe[^>]+src=[\"']([^\"']+)[\"']", html, re.I)
        if iframe:
            return {"parse": 1, "url": self._fix_url(iframe.group(1)), "header": headers}

        return {"parse": 1, "url": play_url, "header": headers}
