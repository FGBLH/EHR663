# -*- coding: utf-8 -*-
# TVBox爬虫 - 优质粉嫩鲍
# 目标：https://fcy.yzfnb8.lat/yzfnb/

import re
import json
import urllib.parse
from base.spider import Spider
from bs4 import BeautifulSoup
import requests

class Spider(Spider):
    def __init__(self):
        self.host = "https://fcy.yzfnb8.lat/cn/home/web/"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept-Encoding": "gzip, deflate",
        })
        self.class_map = {
            "20": "熟母少妇", "21": "网红直播", "22": "自拍偷拍",
            "23": "强奸乱伦", "24": "高清国产", "25": "韩国专区",
            "26": "日本有码", "27": "日本无码", "28": "欧美情色",
            "29": "动漫卡通", "30": "三级伦理"
        }

    def init(self, extend=""):
        try:
            config = json.loads(extend) if extend else {}
            if config.get("proxy"):
                self.session.proxies = {"http": config["proxy"], "https": config["proxy"]}
        except:
            pass

    def getName(self):
        return "优质粉嫩鲍"

    def isVideoFormat(self, url):
        return any(ext in url for ext in [".m3u8", ".mp4", ".flv", ".ts"])

    def manualVideoCheck(self):
        return False

    def _fix_url(self, url):
        if not url:
            return ""
        if url.startswith("http"):
            return url
        if url.startswith("//"):
            return "https:" + url
        return urllib.parse.urljoin(self.host, url)

    def _fetch(self, url, timeout=15):
        try:
            resp = self.session.get(url, timeout=timeout)
            resp.encoding = "utf-8"
            return resp.text
        except Exception as e:
            print(f"[Fetch Error] {url} -> {e}")
            return ""

    def homeContent(self, filter=False):
        classes = [{"type_id": tid, "type_name": name} for tid, name in self.class_map.items()]
        filters = {}
        for tid in self.class_map:
            filters[tid] = [
                {"key": "order", "name": "排序", "value": [
                    {"n": "时间", "v": "time"}, {"n": "人气", "v": "hits"}
                ]}
            ]
        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        return self.categoryContent("20", "1", False, {})

    def categoryContent(self, tid, pg, filter=False, extend=None):
        try:
            pg = max(1, int(pg))
            if pg <= 1:
                url = f"{self.host}index.php/vod/type/id/{tid}.html"
            else:
                url = f"{self.host}index.php/vod/type/id/{tid}/page/{pg}.html"

            html = self._fetch(url)
            if not html:
                return {"list": [], "page": pg, "pagecount": 1, "limit": 20, "total": 0}

            soup = BeautifulSoup(html, "html.parser")
            videos = []
            seen = set()

            for a_tag in soup.find_all("a", href=re.compile(r"/play/id/\d+")):
                href = a_tag.get("href", "")
                vid_match = re.search(r"/play/id/(\d+)", href)
                vod_id = vid_match.group(1) if vid_match else ""
                if not vod_id or vod_id in seen:
                    continue

                title = a_tag.get("title", "").strip()
                if not title:
                    title = a_tag.get_text(strip=True)
                if not title:
                    title = "未知视频"

                img_tag = a_tag.find("img")
                pic = ""
                if img_tag:
                    pic = img_tag.get("src", "") or img_tag.get("data-original", "")
                pic = self._fix_url(pic)

                remark = ""
                p_tag = a_tag.find("p")
                if p_tag:
                    remark = p_tag.get_text(strip=True)
                else:
                    parent = a_tag.parent
                    if parent:
                        p_tag = parent.find("p")
                        if p_tag:
                            remark = p_tag.get_text(strip=True)
                if not remark:
                    remark_tag = a_tag.find(class_=re.compile(r"remark|note|caption"))
                    if remark_tag:
                        remark = remark_tag.get_text(strip=True)

                seen.add(vod_id)
                videos.append({
                    "vod_id": vod_id,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remark[:50]
                })

            if not videos:
                pattern = r'<a[^>]*href="([^"]*play/id/\d+[^"]*)"[^>]*title="([^"]*)"[^>]*>.*?<img[^>]+(?:data-original|src)="([^"]+)"[^>]*>.*?<p[^>]*>([^<]*)</p>'
                matches = re.findall(pattern, html, re.S)
                for href, title, pic, remark in matches:
                    vid_match = re.search(r'/play/id/(\d+)', href)
                    vod_id = vid_match.group(1) if vid_match else ""
                    if not vod_id or vod_id in seen:
                        continue
                    seen.add(vod_id)
                    videos.append({
                        "vod_id": vod_id,
                        "vod_name": title.strip(),
                        "vod_pic": self._fix_url(pic),
                        "vod_remarks": remark.strip()[:50]
                    })

            pagecount = 1
            page_links = soup.find_all("a", href=re.compile(r"/page/\d+"))
            nums = []
            for link in page_links:
                m = re.search(r"/page/(\d+)", link.get("href", ""))
                if m:
                    nums.append(int(m.group(1)))
            if nums:
                pagecount = max(nums)
            else:
                if "下一页" in html or "next" in html.lower():
                    pagecount = pg + 1
                else:
                    if len(videos) >= 20:
                        pagecount = pg + 1
                    else:
                        pagecount = pg

            pagecount = max(pagecount, pg)

            return {
                "list": videos,
                "page": pg,
                "pagecount": pagecount,
                "limit": 20,
                "total": pagecount * 20
            }
        except Exception as e:
            print(f"分类异常: {e}")
            return {"list": [], "page": pg, "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        try:
            vod_id = ids[0]
            url = f"{self.host}index.php/vod/play/id/{vod_id}/sid/1/nid/1.html"
            html = self._fetch(url)

            title = ""
            title_match = re.search(r"<h1[^>]*>(.*?)</h1>", html)
            if title_match:
                title = title_match.group(1).strip()
            else:
                title_match = re.search(r"<title>(.*?)</title>", html)
                if title_match:
                    title = title_match.group(1).split("-")[0].strip()

            pic = ""
            pic_match = re.search(r'<div class="cover">.*?<img[^>]+data-original="([^"]+)"', html, re.S)
            if not pic_match:
                pic_match = re.search(r'<img[^>]+class="vod_img"[^>]+src="([^"]+)"', html)
            if pic_match:
                pic = self._fix_url(pic_match.group(1))

            desc = ""
            desc_match = re.search(r'<div class="video-desc">(.*?)</div>', html, re.S)
            if desc_match:
                desc = re.sub(r"<[^>]+>", "", desc_match.group(1)).strip()

            play_urls = []
            video_src = re.search(r'<video[^>]+src="([^"]+\.m3u8)"', html)
            if video_src:
                play_urls.append(f"第1集${video_src.group(1)}")

            if not play_urls:
                iframe = re.search(r'<iframe[^>]+src="([^"]+)"', html)
                if iframe:
                    iframe_url = self._fix_url(iframe.group(1))
                    iframe_html = self._fetch(iframe_url)
                    deep_video = re.search(r'<video[^>]+src="([^"]+\.m3u8)"', iframe_html)
                    if deep_video:
                        play_urls.append(f"第1集${deep_video.group(1)}")
                    else:
                        deep_player = re.search(r'player_aaaa\s*=\s*"([^"]+)"', iframe_html)
                        if deep_player:
                            play_urls.append(f"第1集${deep_player.group(1)}")

            if not play_urls:
                player = re.search(r'player_aaaa\s*=\s*"([^"]+)"', html)
                if player:
                    play_urls.append(f"第1集${player.group(1)}")

            if not play_urls:
                m3u8s = re.findall(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', html)
                if m3u8s:
                    play_urls.append(f"第1集${m3u8s[0]}")

            if not play_urls:
                play_urls.append("第1集$")

            return {
                "list": [{
                    "vod_id": vod_id,
                    "vod_name": title or "未命名",
                    "vod_pic": pic,
                    "vod_content": desc,
                    "vod_play_from": "优质粉嫩鲍",
                    "vod_play_url": "#".join(play_urls)
                }]
            }
        except Exception as e:
            print(f"详情异常: {e}")
            return {"list": []}

    def playerContent(self, flag, id, vipFlags=None):
        try:
            if not id:
                return {"parse": 0, "url": "", "header": {}}
            if not id.startswith("http"):
                id = self._fix_url(id)
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": self.host
            }
            return {"parse": 0, "url": id, "header": json.dumps(headers)}
        except Exception:
            return {"parse": 0, "url": id, "header": {}}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            pg = max(1, int(pg))
            enc_key = urllib.parse.quote(key)
            if pg <= 1:
                url = f"{self.host}index.php/vod/search.html?wd={enc_key}"
            else:
                url = f"{self.host}index.php/vod/search/{pg}.html?wd={enc_key}"

            html = self._fetch(url)
            soup = BeautifulSoup(html, "html.parser")
            videos = []
            seen = set()

            for a_tag in soup.find_all("a", href=re.compile(r"/play/id/\d+")):
                href = a_tag.get("href", "")
                vid_match = re.search(r"/play/id/(\d+)", href)
                vod_id = vid_match.group(1) if vid_match else ""
                if not vod_id or vod_id in seen:
                    continue
                title = a_tag.get("title", "").strip()
                if not title:
                    title = a_tag.get_text(strip=True)
                img_tag = a_tag.find("img")
                pic = ""
                if img_tag:
                    pic = img_tag.get("src", "") or img_tag.get("data-original", "")
                pic = self._fix_url(pic)
                p_tag = a_tag.find("p")
                remark = p_tag.get_text(strip=True) if p_tag else ""
                seen.add(vod_id)
                videos.append({
                    "vod_id": vod_id,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remark[:50]
                })

            pagecount = 3 if len(videos) >= 20 else 1
            return {"list": videos, "page": pg, "pagecount": pagecount, "limit": 20, "total": pagecount * 20}
        except Exception as e:
            print(f"搜索异常: {e}")
            return {"list": [], "page": int(pg), "pagecount": 1, "limit": 20, "total": 0}

    def localProxy(self, param):
        try:
            url = ""
            if isinstance(param, dict):
                url = param.get("url") or param.get("pic") or ""
            elif isinstance(param, str):
                url = param
            if not url:
                return [404, "text/plain", "no url"]
            headers = {"Referer": self.host, "User-Agent": "Mozilla/5.0"}
            resp = self.session.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                return [resp.status_code, "text/plain", ""]
            return [200, resp.headers.get("Content-Type", "image/jpeg"), resp.content]
        except Exception as e:
            return [502, "text/plain", str(e)]

    def destroy(self):
        if self.session:
            self.session.close()