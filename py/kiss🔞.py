# -*- coding: utf-8 -*-
import sys
import re
import requests
import base64
from urllib.parse import quote, unquote
sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
    def init(self, extend=""):
        self.host = "https://kissjav.li"
        self.pic_host = "https://assets6.cdnhop.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 11; SAMSUNG SM-G973U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.141 Mobile Safari/537.36",
            "Referer": self.host + "/",
            "Origin": self.host
        }

    def getName(self):
        return "KissJAV"

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|flv|avi|mkv|mov|ts)(\?|$)|/get_file/', url or "", re.I))

    def manualVideoCheck(self):
        return False

    def homeContent(self, filter):
        return {
            "class": [
                {"type_id": "latest-updates", "type_name": "Latest"},
                {"type_id": "most-popular/?sort_by=video_viewed", "type_name": "Most Viewed"},
                {"type_id": "categories/korean-porn", "type_name": "Korean Porn"},
                {"type_id": "categories/korean-bj", "type_name": "Korean BJ"},
                {"type_id": "categories/vip", "type_name": "KVIP"},
                {"type_id": "categories/jvip", "type_name": "JVIP"},
                {"type_id": "categories/fc2ppv", "type_name": "FC2PPV"},
                {"type_id": "categories/uncensored", "type_name": "Uncensored"},
                {"type_id": "categories/hentai", "type_name": "Hentai"}
            ]
        }

    def homeVideoContent(self):
        return {"list": self.parseList(self.get(self.host + "/"))}

    def categoryContent(self, tid, pg, filter, extend):
        path = str(tid or "latest-updates").strip("/")
        if "?" in path:
            url = self.host + "/" + path + (("&page=" + str(pg)) if str(pg) != "1" else "")
        else:
            url = self.host + "/" + path + "/" if str(pg) == "1" else self.host + "/" + path + "/" + str(pg) + "/"
        html = self.get(url)
        return {
            "page": int(pg),
            "pagecount": 999,
            "limit": 30,
            "total": 999999,
            "list": self.parseList(html)
        }

    def detailContent(self, ids):
        vid = ids[0]
        html = self.get(vid)
        sid = self.match(vid, r'/video/(\d+)/')
        name = self.clean(self.match(html, r'<meta property="og:title" content="(.*?)"') or self.match(html, r'video_title:\s*[\'"]([^\'"]+)'))
        pic = self.fix(self.match(html, r'<meta property="og:image" content="(.*?)"') or self.match(html, r'preview_url:\s*[\'"]([^\'"]+)') or self.realPic(sid))
        desc = self.clean(self.match(html, r'<meta property="og:description" content="(.*?)"'))
        cate = self.clean(self.match(html, r'video_categories:\s*[\'"]([^\'"]*)'))
        remarks = self.clean(self.match(html, r'<meta property="video:duration" content="(.*?)"'))
        play_from = []
        play_url = []
        eps = []
        for m in re.finditer(r'(video_url(?:_hd)?):\s*[\'"]([^\'"]+)', html):
            key = "HD" if "_hd" in m.group(1) else "SD"
            url = m.group(2)
            if url and url != "MQ==":
                try:
                    url = base64.b64decode(url).decode("utf-8")
                except Exception:
                    url = url
                if url:
                    eps.append(key + "$" + url)
        if not eps:
            em = self.match(html, r'embedUrl"\s*:\s*"(.*?)"') or self.match(html, r'src="(https://kissjav\.li/embed/[^"]+)')
            if em:
                eps.append("播放$" + em)
        if eps:
            play_from.append("KissJAV")
            play_url.append("#".join(eps))
        return {
            "list": [{
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": self.img(pic),
                "vod_remarks": remarks,
                "type_name": cate,
                "vod_year": "",
                "vod_area": "",
                "vod_lang": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_content": desc,
                "vod_play_from": "$$$".join(play_from),
                "vod_play_url": "$$$".join(play_url)
            }]
        }

    def searchContent(self, key, quick, pg="1"):
        q = quote(key)
        url = self.host + "/search/" + q + "/" if str(pg) == "1" else self.host + "/search/" + q + "/" + str(pg) + "/"
        html = self.get(url)
        return {"list": self.parseList(html), "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        url = id
        if "/embed/" in url:
            html = self.get(url)
            u = self.match(html, r'(?:video_url(?:_hd)?|file)\s*[:=]\s*[\'"]([^\'"]+)')
            if u:
                try:
                    u = base64.b64decode(u).decode("utf-8") if not u.startswith("http") else u
                except Exception:
                    u = u
                url = u
        return {"parse": 0 if self.isVideoFormat(url) else 1, "playUrl": "", "url": url, "header": self.headers}

    def localProxy(self, param):
        url = ""
        for k in ["url", "img", "pic"]:
            v = param.get(k, "")
            if isinstance(v, list):
                v = v[0] if len(v) > 0 else ""
            if v:
                url = v
                break
        url = unquote(url or "")
        if not url:
            return [404, "text/plain", "", ""]
        try:
            h = dict(self.headers)
            h.update({
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                "Referer": self.host + "/"
            })
            r = requests.get(url, headers=h, timeout=20, verify=False)
            ct = r.headers.get("Content-Type", "")
            if r.status_code == 200 and r.content:
                return [200, ct or "image/jpeg", r.content, ""]
        except Exception:
            pass
        return [404, "text/plain", "", ""]

    def destroy(self):
        return "正在Destroy"

    def get(self, url):
        try:
            r = requests.get(url, headers=self.headers, timeout=15, verify=False)
            r.encoding = r.apparent_encoding or "utf-8"
            return r.text
        except Exception:
            return ""

    def match(self, text, rule):
        m = re.search(rule, text or "", re.S)
        return m.group(1) if m else ""

    def clean(self, text):
        return re.sub(r"\s+", " ", re.sub(r"<.*?>", "", text or "").replace("&nbsp;", " ")).strip()

    def fix(self, url):
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host + url
        return url

    def realPic(self, vid):
        if not vid:
            return ""
        base = str(int(int(vid) / 1000) * 1000)
        return self.pic_host + "/contents/videos_screenshots/" + base + "/" + str(vid) + "/320x180/1.jpg"

    def img(self, url):
        url = self.fix(url)
        if not url:
            return ""
        try:
            return self.getProxyUrl() + "&url=" + quote(url, safe="")
        except Exception:
            return url

    def parseList(self, html):
        res = []
        seen = set()
        for m in re.finditer(r'<a\s+href=["\'](https?://kissjav\.li/video/([^/]+)/[^"\']*/)["\']\s+title=["\']([^"\']+)["\']', html or "", re.S):
            url = m.group(1)
            vid = m.group(2)
            if url in seen:
                continue
            seen.add(url)
            start = m.start()
            end = html.find('<a href="https://kissjav.li/video/', m.end())
            item = html[start:end if end > start else min(len(html), m.end() + 1600)]
            name = self.clean(m.group(3))
            pic = self.match(item, r'(?:data-original|data-webp|data-src)=["\']([^"\']+)["\']') or self.match(item, r'src=["\']([^"\']+)["\']') or self.realPic(vid)
            if "data:image" in pic or "load.gif" in pic or "logo" in pic:
                pic = self.realPic(vid)
            remarks = self.clean(self.match(item, r'<div[^>]+class=["\'][^"\']*time[^"\']*["\'][^>]*>(.*?)</div>') or vid)
            if name:
                res.append({
                    "vod_id": url,
                    "vod_name": name,
                    "vod_pic": self.img(pic),
                    "vod_remarks": remarks
                })
        if not res:
            for m in re.finditer(r'href=["\'](https?://kissjav\.li/video/([^/]+)/[^"\']*/)["\'][^>]*title=["\']([^"\']+)["\']', html or "", re.S):
                url = m.group(1)
                vid = m.group(2)
                if url in seen:
                    continue
                seen.add(url)
                res.append({
                    "vod_id": url,
                    "vod_name": self.clean(m.group(3)),
                    "vod_pic": self.img(self.realPic(vid)),
                    "vod_remarks": vid
                })
        return res