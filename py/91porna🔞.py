# coding=utf-8
# !/usr/bin/python

import json
import re
import sys
import time
import hashlib
from base64 import b64decode, b64encode
from urllib.parse import urljoin, quote, urlencode, urlparse, parse_qs, urlunparse

import requests
from bs4 import BeautifulSoup
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

sys.path.append('..')
from base.spider import Spider as BaseSpider

_DEFAULT_HOST = "https://91porna.com"
_img_cache = {}


def _soup(html: str):
    # 避免依赖 lxml，OK/TVBox 运行环境更稳
    return BeautifulSoup(html or "", "html.parser")


def _unpack_packer(s: str) -> str:
    m = re.search(
        r"eval\(function\(p,a,c,k,e,(?:d|r)\)\{[\s\S]+?\}\('\s*([\s\S]*?)\s*',\s*(\d+),\s*(\d+),\s*'([\s\S]*?)'\.split\('\|'\)\s*,\s*0\s*,\s*\{\}\)\)",
        s,
    )
    if not m:
        return s

    p, a, c, k = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4).split("|")

    digits = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

    def base(n: int) -> str:
        if n == 0:
            return "0"
        out = ""
        while n:
            n, r = divmod(n, a)
            out = digits[r] + out
        return out

    for i in range(c - 1, -1, -1):
        key = base(i)
        val = k[i] if i < len(k) and k[i] else key
        p = re.sub(r"\b" + re.escape(key) + r"\b", val, p)

    return p


class Spider(BaseSpider):
    def _cr(self, href: str, name: str) -> str:
        if not (href and name):
            return ""
        try:
            payload = json.dumps({"id": href, "name": name}, ensure_ascii=False)
        except Exception:
            payload = json.dumps({"id": href, "name": name})
        return f"[a=cr:{payload}/]{name}[/a]"

    def init(self, extend=""):
        cfg = json.loads(extend) if isinstance(extend, str) and extend else (extend or {})
        self.proxies = cfg.get("proxies") or {}
        self.host = (cfg.get("host") or _DEFAULT_HOST).rstrip("/")

        self.headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": f"{self.host}/",
        }

    def getName(self):
        return "91porna(OK适配精简版)"

    def isVideoFormat(self, url):
        u = (url or "").lower()
        return any(x in u for x in (".m3u8", ".mp4", ".ts"))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        _img_cache.clear()

    # ---------------- 首页 ----------------

    def homeContent(self, filter):
        # 直接用站点真实导航（避免抓首页再猜）
        classes = [
            {"type_name": "正在播放", "type_id": "/comic/index/video?category=play"},
            {"type_name": "当前最热", "type_id": "/comic/index/video?category=now_hot"},
            {"type_name": "最近更新", "type_id": "/comic/index/video?category=new_update"},
            {"type_name": "91原创", "type_id": "/comic/index/video?category=original"},
            {"type_name": "本月最热", "type_id": "/comic/index/video?category=now_month_hot"},
            {"type_name": "高清", "type_id": "/comic/index/video?category=hd"},
            {"type_name": "每月最热", "type_id": "/comic/index/video?category=month_hot"},
            {"type_name": "本月讨论", "type_id": "/comic/index/video?category=now_month_comment"},
            {"type_name": "收藏最多", "type_id": "/comic/index/video?category=max_collect"},
        ]

        # 首页也给一页视频（取“正在播放”第一页）
        try:
            v = self.categoryContent(classes[0]["type_id"], 1, False, {})
            return {"class": classes, "filters": {}, "list": v.get("list", [])}
        except Exception:
            return {"class": classes, "filters": {}, "list": []}

    def homeVideoContent(self):
        return {"list": self.homeContent(None).get("list", [])}

    # ---------------- 分类/搜索 ----------------

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        url = tid if tid.startswith("http") else urljoin(self.host + "/", tid.lstrip("/"))

        # 站点分页：?page=2（不是 /2/）
        p = urlparse(url)
        qs = parse_qs(p.query)
        if pg > 1:
            qs["page"] = [str(pg)]
        else:
            qs.pop("page", None)
        url = urlunparse(p._replace(query=urlencode(qs, doseq=True)))

        r = requests.get(url, headers=self.headers, proxies=self.proxies, timeout=10)
        if r.status_code != 200:
            return {"list": [], "page": pg, "pagecount": 0, "limit": 30, "total": 0}

        r.encoding = r.apparent_encoding
        soup = _soup(r.text)

        videos = self.getlist(soup, "div.video-item")
        return {"list": videos, "page": pg, "pagecount": 9999, "limit": 30, "total": 999999}

    def searchContent(self, key, quick, pg="1"):
        pg = int(pg or 1)
        url = f"{self.host}/comic/index/search?keyword={quote(key)}"
        if pg > 1:
            url += f"&page={pg}"
        r = requests.get(url, headers=self.headers, proxies=self.proxies, timeout=10)
        r.encoding = r.apparent_encoding
        soup = _soup(r.text)
        return {"list": self.getlist(soup, "div.video-item"), "page": pg, "pagecount": 9999}

    # ---------------- 详情/播放 ----------------

    def detailContent(self, ids):
        # ids: /comic/index/detail?video_key=xxxx
        vid_url = ids[0] if ids[0].startswith("http") else urljoin(self.host + "/", ids[0].lstrip("/"))
        q = parse_qs(urlparse(vid_url).query)
        video_key = (q.get("video_key") or [""])[0]

        r = requests.get(vid_url, headers=self.headers, proxies=self.proxies, timeout=10)
        r.encoding = r.apparent_encoding
        soup = _soup(r.text)
        title = (soup.select_one("h1") or soup.title)
        title = title.get_text(strip=True) if title else video_key
        desc = "".join(x.get_text(" ", strip=True) for x in soup.select("#detail, .detail, article, .post-content"))

        play_url, play_type = self._extract_play_url(video_key, fallback_html=r.text)
        # 直链优先：避免部分运行环境 getProxyUrl 为空导致最终播放地址为空
        play = f"播放${play_url or vid_url}"

        vod = {
            "vod_play_from": "91porna",
            "vod_play_url": play,
            "vod_content": desc or title,
            "vod_remarks": play_type or "",
        }

        # ---------- 导演(发布者/UP主) 可点击 ----------
        # 结构：a[href^="/comic/index/publicvideo?"] 内部文本为名称
        a_user = soup.select_one('a[href^="/comic/index/publicvideo?"]')
        if a_user:
            href = a_user.get("href") or ""
            name = a_user.get_text(" ", strip=True)
            if href and not href.startswith("http"):
                href = urljoin(self.host + "/", href.lstrip("/"))
            if name:
                vod["vod_director"] = self._cr(href, name)

        # ---------- 影片介绍（详情页 h2.bg-base1...） ----------
        intro = ""
        h2 = soup.select_one("h2.bg-base1")
        if h2:
            # get_text 会把 <br> 转为分隔符
            intro = h2.get_text("\n", strip=True)

        # ---------- 标签 可点击，写入简介 vod_content（标签置顶） ----------
        tags = []
        for ta in soup.select('ul.flex.flex-wrap.text-default.mb-3 a[href^="/comic/index/search?"]'):
            name = ta.get_text(strip=True)
            href = ta.get("href") or ""
            if href and not href.startswith("http"):
                href = urljoin(self.host + "/", href.lstrip("/"))
            if name and href:
                tags.append(self._cr(href, name))

        parts = []
        if tags:
            parts.append("标签: " + " ".join(tags))

        # 影片介绍优先，其次回退到原抓到的 desc/title
        base_desc = (intro or desc or title).strip()
        if base_desc:
            parts.append(base_desc)

        if parts:
            vod["vod_content"] = "\n\n".join(parts)

        return {"list": [vod]}

    def _extract_play_url(self, video_key: str, fallback_html: str = ""):
        """返回 (直链URL, 类型m3u8/mp4/空)。

        站点逻辑：detail -> embed(id=video_key) -> embed_play.js(img,u,t) -> document.write(video src=...)

        兼容点：
        - embed_play.js 可能返回不同转义/引号格式
        - 少数情况下页面里可能直接出现 m3u8/mp4
        """
        if not video_key:
            return "", ""

        # 0) 先在详情页 HTML 里做一次兜底搜索（有时直链直接内嵌在 script/json）
        for pat, typ in (
            (r"https?://[^\"'\\s]+\\.m3u8[^\"'\\s]*", "m3u8"),
            (r"https?://[^\"'\\s]+\\.mp4[^\"'\\s]*", "mp4"),
        ):
            m = re.search(pat, fallback_html or "", re.I)
            if m:
                return m.group(0), typ

        embed = f"{self.host}/comic/index/embed?id={video_key}"
        r = requests.get(embed, headers=self.headers, proxies=self.proxies, timeout=10)
        r.encoding = r.apparent_encoding
        html = r.text or ""

        # 1) 解包 embed 页 packer，提取 embed_play.js 参数
        unpacked = _unpack_packer(html)
        img = re.search(r"embed_play\.js\?img=([^\"&]+)", unpacked)
        u = re.search(r"encodeURIComponent\([\"']([^\"']+)[\"']\)", unpacked)

        # 若 packer 解不出来，直接从原文抓一次
        if not (img and u):
            img = re.search(r"embed_play\.js\?img=([^\"&]+)", html)
            u = re.search(r"encodeURIComponent\([\"']([^\"']+)[\"']\)", html)

        if not (img and u):
            return "", ""

        t_bucket = int(time.time() / 1800)
        js_url = f"{self.host}/index/embed_play.js?img={img.group(1)}&u={quote(u.group(1), safe='')}&t={t_bucket}"

        js_resp = requests.get(js_url, headers=self.headers, proxies=self.proxies, timeout=10)
        js_resp.encoding = js_resp.apparent_encoding
        js = _unpack_packer(js_resp.text or "")

        # 2) 先按站点常见格式抓（最稳）：src=\\"https://...m3u8...\\"
        m3 = re.search(r'src=\\\\"(https?://[^\\\\"]+\\.m3u8[^\\\\"]*)\\\\"', js, re.I)
        if m3:
            u0 = m3.group(1)
            u0 = u0.replace("\\/", "/").strip().strip("\"'").rstrip("\\")
            return u0, "m3u8"

        # 3) 再做宽松搜索兜底（兼容单双引号、是否转义）
        m3b = re.search(r"https?://[^\"'\s\\]+\.m3u8[^\"'\s]*", js, re.I)
        if m3b:
            u0 = m3b.group(0).replace("\\/", "/").strip().strip("\"'").rstrip("\\")
            return u0, "m3u8"
        mp4 = re.search(r"https?://[^\"'\s\\]+\.mp4[^\"'\s]*", js, re.I)
        if mp4:
            u0 = mp4.group(0).replace("\\/", "/").strip().strip("\"'").rstrip("\\")
            return u0, "mp4"

        return "", ""

    def playerContent(self, flag, id, vipFlags):
        # 直链：m3u8/mp4 直接播放
        return {"parse": 0, "url": id, "header": self.headers}

    # ---------------- 本地代理(仅用于图片) ----------------

    def localProxy(self, param):
        t = (param or {}).get("type")
        if t == "cache":
            key = (param or {}).get("key")
            return [200, "image/jpeg", _img_cache.get(key, b"")]

        if t == "img":
            url = (param or {}).get("url")
            real = self.d64(url) if url and not url.startswith("http") else url
            raw = requests.get(real, headers=self.headers, proxies=self.proxies, timeout=10).content
            return [200, "image/jpeg", self.aesimg(raw)]

        return [404, "text/plain", b""]

    def proxy_img(self, url: str, type_: str):
        # TVBox/OK：vod_pic 走本地代理可兼容加密图/防盗链
        return f"{self.getProxyUrl()}&url={self.e64(url)}&type={type_}" if url else ""

    # ---------------- 列表解析 ----------------

    def getlist(self, soup: BeautifulSoup, selector: str):
        out = []
        seen = set()

        for item in soup.select(selector):
            a = item.select_one('a[href*="/comic/index/detail"]')
            if not a:
                continue
            href = a.get("href")
            if not href:
                continue
            href = href if href.startswith("http") else urljoin(self.host, href)
            if href in seen:
                continue
            seen.add(href)

            img = item.select_one("img")
            pic = (img.get("data-src") or img.get("src") or "") if img else ""
            if pic.startswith("/"):
                pic = urljoin(self.host, pic)
            if "poster_loading" in pic:
                pic = img.get("data-src") if img else pic

            title = (img.get("alt") if img else "") or ""
            if not title:
                t = item.select_one(".line-clamp-2, .line-clamp-1")
                title = t.get_text(strip=True) if t else ""
            title = title.strip()
            if len(title) < 2:
                continue

            dur = item.get_text(" ", strip=True)
            m = re.search(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", dur)
            remark = m.group(0) if m else ""

            out.append(
                {
                    "vod_id": href,
                    "vod_name": title,
                    "vod_pic": self._img_url(pic) if pic else "",
                    "vod_remarks": remark,
                    "style": {"type": "rect", "ratio": 1.33},
                }
            )

        return out

    # ---------------- 图片(AES) ----------------

    def e64(self, text):
        return b64encode(str(text).encode()).decode()

    def d64(self, text):
        return b64decode(str(text).encode()).decode()

    def aesimg(self, data: bytes) -> bytes:
        if len(data) < 16:
            return data
        for key, iv in ((b"f5d965df75336270", b"97b60394abc2fbe1"), (b"75336270f5d965df", b"abc2fbe197b60394")):
            try:
                dec = unpad(AES.new(key, AES.MODE_CBC, iv).decrypt(data), 16)
                if dec.startswith((b"\xff\xd8", b"\x89PNG", b"GIF8")):
                    return dec
            except Exception:
                pass
        return data

    def _img_url(self, url):
        url = (url or "").strip("'\" ")
        if not url:
            return ""

        if url.startswith("data:"):
            _, b64s = url.split(",", 1)
            raw = b64decode(b64s)
            raw = raw if raw.startswith((b"\xff\xd8", b"\x89PNG", b"GIF8")) else self.aesimg(raw)
            key = hashlib.md5(raw).hexdigest()
            _img_cache[key] = raw
            return f"{self.getProxyUrl()}&type=cache&key={key}"

        url = url if url.startswith("http") else urljoin(self.host, url)
        return self.proxy_img(url, "img")
