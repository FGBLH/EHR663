# -*- coding: utf-8 -*-
import base64, html, json, re
from urllib.parse import quote, unquote
import requests
from lxml import etree
try:
    from Crypto.Cipher import AES
except Exception:
    AES = None
try:
    from base.spider import Spider as BaseSpider
except Exception:
    BaseSpider = object

class Spider(BaseSpider):
    def getName(self): return "黑料不打烊"
    def init(self, extend=""):
        self.host = "https://badly.okttbipbu.cc"
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36", "Referer": self.host + "/", "Accept": "*/*", "Accept-Language": "zh-CN,zh;q=0.9"}
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.last_error = ""
        self.categories = [{"type_id": "/", "type_name": "首页"}, {"type_id": "/category/24hcg/", "type_name": "今日看料"}, {"type_id": "/category/rgtj/", "type_name": "热门吃瓜"}, {"type_id": "/category/mrrg/", "type_name": "每日热瓜"}, {"type_id": "/category/hlda/", "type_name": "黑料大事"}, {"type_id": "/category/whhl/", "type_name": "网红吃瓜"}, {"type_id": "/category/mxbg/", "type_name": "明星吃瓜"}, {"type_id": "/category/fcns/", "type_name": "反差女神"}, {"type_id": "/category/xyrg/", "type_name": "学院热瓜"}, {"type_id": "/category/mrds/", "type_name": "每日大赛"}, {"type_id": "/category/swdj/", "type_name": "AI短剧"}, {"type_id": "/category/lydt/", "type_name": "撸友看片"}, {"type_id": "/category/avjs/", "type_name": "AV解说"}, {"type_id": "/category/mrst/", "type_name": "禁播动漫"}, {"type_id": "/category/pmv/", "type_name": "PMV混剪"}]
    def _client(self): return getattr(self, "session", requests)
    def _error(self, msg):
        self.last_error = msg
        try: self.log(msg)
        except Exception: pass
    def _get(self, url):
        try:
            client = self._client()
            r = client.get(url, headers=self.headers, timeout=25, verify=False, allow_redirects=True)
            if (r.status_code != 200 or not (r.text or "").strip()) and url.rstrip("/") != self.host:
                client.get(self.host + "/", headers=self.headers, timeout=25, verify=False, allow_redirects=True)
                r = client.get(url, headers=self.headers, timeout=25, verify=False, allow_redirects=True)
            if r.status_code != 200:
                self._error(f"GET {url} status={r.status_code} body={(r.text or '')[:120]}")
                return ""
            text = r.content.decode("utf-8", errors="ignore")
            if not (text or "").strip(): self._error(f"GET {url} empty body")
            return text
        except Exception as e:
            self._error(f"GET {url} error={type(e).__name__}: {e}")
            return ""
    def _fix(self, u):
        if not u: return ""
        u = html.unescape(u.strip())
        return "https:" + u if u.startswith("//") else self.host + u if u.startswith("/") else u
    def _clean(self, s): return re.sub(r"\s+", " ", html.unescape(s or "")).strip()
    def _player_header(self): return self.headers
    def _html(self, text):
        if isinstance(text, bytes): text = text.decode("utf-8", errors="ignore")
        return etree.HTML((text or "").replace("\x00", "").encode("utf-8", errors="ignore"))
    def _ids(self, ids): return ids if isinstance(ids, (list, tuple)) else [ids] if ids else []
    def _detail_url(self, sid):
        sid = str(sid or "").strip()
        if sid.startswith("http"): return self._fix(sid)
        m = re.search(r"(?:archives/)?(\d{3,})(?:\.html)?", sid)
        if m: return f"{self.host}/archives/{m.group(1)}.html"
        return self._fix(sid)
    def _is_encrypted_img(self, u): return any(x in (u or "") for x in ["/xiao/", "/upload_01/xiao/", "/upload/upload/xiao/"])
    def _is_cdn_img(self, u): return any(x in (u or "") for x in ["/xiao/", "/usr/", "/upload_01/", "/uploads/", "/upload/upload/"])
    def _proxy_base(self):
        try:
            f = getattr(self, "getProxyUrl", None)
            return f() if callable(f) else ""
        except Exception:
            return ""
    def _proxy_img_url(self, base, url):
        sep = "" if base.endswith(("?", "&")) else "&" if "?" in base else "?"
        return base + sep + "type=img&url=" + quote(url, safe="")
    def _mime_from_bytes(self, data, ext="jpeg"):
        if data.startswith(b"\xff\xd8\xff"): return "jpeg"
        if data.startswith(b"\x89PNG\r\n\x1a\n"): return "png"
        if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"): return "gif"
        if data[:4] == b"RIFF" and data[8:12] == b"WEBP": return "webp"
        return "jpeg" if ext in ["jpg", "jpeg"] else ext if ext in ["png", "gif", "webp"] else "jpeg"
    def _decrypt_image_bytes(self, data):
        if not AES: return ""
        try:
            raw = AES.new(b"f5d965df75336270", AES.MODE_CBC, b"97b60394abc2fbe1").decrypt(base64.b64decode(data))
            pad = raw[-1] if raw else 0
            return raw[:-pad] if 0 < pad <= 16 and raw.endswith(bytes([pad]) * pad) else raw
        except Exception:
            return b""
    def _image_data_url(self, url):
        try:
            data, mime = self._image_bytes(url)
            return f"data:image/{mime};base64,{base64.b64encode(data).decode()}" if data else url
        except Exception:
            return url
    def _image_bytes(self, url):
        url = unquote(url)
        ext = (url.split("?")[0].rsplit(".", 1)[-1] or "jpeg").lower()
        r = self._client().get(url, headers=self.headers, timeout=25, verify=False, allow_redirects=True)
        if self._is_encrypted_img(url):
            raw = self._decrypt_image_bytes(base64.b64encode(r.content).decode())
            if raw: return raw, self._mime_from_bytes(raw, ext)
        ctype = (r.headers.get("Content-Type") or "").split(";")[0].lower()
        mime = ctype.split("/", 1)[1] if ctype.startswith("image/") else self._mime_from_bytes(r.content, ext)
        return r.content, mime
    def _pic_url(self, url):
        base = self._proxy_base()
        if base: return self._proxy_img_url(base, url)
        if url.startswith("data:"): return url
        return self._image_data_url(url) if self._is_encrypted_img(url) else url
    def _cover_url(self, url):
        url = self._fix(url)
        base = self._proxy_base()
        return self._proxy_img_url(base, url) if base and self._is_encrypted_img(url) else url
    def proxy(self, params):
        url = params.get("url") or params.get("img") or ""
        if isinstance(url, list): url = url[0] if url else ""
        try:
            data, mime = self._image_bytes(url)
            return [200, "image/" + mime, data]
        except Exception:
            return [404, "text/plain", ""]
    def localProxy(self, params): return self.proxy(params)
    def _page_url(self, tid, pg):
        pg = int(pg or 1)
        path = tid or "/"
        if path.startswith("http"): base = path.rstrip("/") + "/"
        else: base = self.host + (path if path.startswith("/") else "/" + path)
        base = base.rstrip("/") + "/"
        if pg <= 1: return base
        return base + f"page/{pg}/" if path.strip("/") == "" else base + f"{pg}/"
    def _parse_list(self, html_text):
        if not html_text: return []
        tree = self._html(html_text)
        if tree is None: return []
        result, seen = [], set()
        items = tree.xpath('//div[@id="index" or @id="archive"]//article[.//a[contains(@href,"/archives/")]]') or tree.xpath('//article[.//a[contains(@href,"/archives/")]]')
        for item in items:
            if self._is_ad_item(item): continue
            href = "".join(item.xpath('.//a[contains(@href,"/archives/")]/@href')).strip()
            m = re.search(r"/archives/(\d+)\.html", href)
            if not m or m.group(1) in seen: continue
            seen.add(m.group(1))
            title = self._clean(" ".join(item.xpath('.//*[contains(@class,"post-card-bottom-text")]//text()')) or " ".join(item.xpath('.//h2//text()')) or "".join(item.xpath('.//a[contains(@href,"/archives/")]/@title')))
            pics = item.xpath('.//meta[@itemprop="image" or @itemprop="thumbnailUrl"]/@content') or item.xpath('.//img/@z-image-loader-url') or item.xpath('.//img/@data-xkrkllgl') or item.xpath('.//img/@data-src') or item.xpath('.//img/@src')
            pic = pics[0] if pics else ""
            result.append({"vod_id": self._fix(href), "vod_name": title or m.group(1), "vod_pic": self._cover_url(pic)})
        return result
    def _content_node(self, tree):
        nodes = tree.xpath('//div[contains(concat(" ",normalize-space(@class)," ")," post-content ")]')
        return nodes[0] if nodes else tree
    def _is_ad_item(self, item):
        return bool(item.xpath('.//a[contains(concat(" ",normalize-space(@rel)," ")," sponsored ") or @data-event="ad_click" or @data-ad_slot_key or @data-ad_id]'))
    def _parse_videos(self, node):
        videos, seen = [], set()
        for d in node.xpath('.//div[contains(@class,"dplayer") and @data-config]'):
            title = f"视频{len(videos)+1}"
            conf = html.unescape(d.get("data-config") or "")
            url = ""
            try: url = ((json.loads(conf).get("video") or {}).get("url") or "").replace("\\/", "/")
            except Exception:
                m = re.search(r'"video"\s*:\s*\{.*?"url"\s*:\s*"([^"]+)"', conf)
                url = m.group(1).replace("\\/", "/") if m else ""
            if url and url not in seen:
                seen.add(url)
                videos.append((title, self._fix(url)))
        return videos
    def _parse_images(self, node):
        imgs, seen = [], set()
        for img in node.xpath('.//img'):
            src = img.get("z-image-loader-url") or img.get("data-xkrkllgl") or img.get("data-original") or img.get("data-src") or img.get("data-lazyload") or img.get("data-lazy-src") or img.get("src") or ""
            src = self._fix(src)
            if not src or src in seen or "/usr/themes/" in src or "/usr/plugins/" in src or "/uploads/default/other/" in src: continue
            seen.add(src)
            imgs.append(src)
        return imgs
    def homeContent(self, filter):
        return {"class": self.categories, "list": self._parse_list(self._get(self.host + "/")), "filters": {}}
    def categoryContent(self, tid, pg, filter, extend):
        items = self._parse_list(self._get(self._page_url(tid, pg)))
        total = 9990 if items else 0
        return {"page": int(pg), "pagecount": 999 if items else int(pg), "limit": 10, "total": total, "count": total, "list": items}
    def detailContent(self, ids):
        self.last_error = ""
        result = {"list": []}
        for sid in self._ids(ids):
            try:
                url = self._detail_url(sid)
                html_text = self._get(url)
                if not html_text:
                    if not self.last_error: self._error(f"detail {url} empty html")
                    continue
                tree = self._html(html_text)
                if tree is None:
                    self._error(f"detail {url} etree none body={html_text[:120]}")
                    continue
                node = self._content_node(tree)
                name = self._clean("".join(tree.xpath('//meta[@property="og:title"]/@content')) or "".join(tree.xpath('//h1/text()')) or "".join(tree.xpath('//title/text()')))
                videos, imgs = self._parse_videos(node), self._parse_images(node)
                pic = self._cover_url(imgs[0] if imgs else "".join(tree.xpath('//meta[@property="og:image"]/@content')))
                text = self._clean(" ".join(node.xpath('.//p[not(ancestor::*[contains(@class,"article-ads-btn")])]/text()')))[:800]
                names, plays = [], []
                if videos:
                    names.append("视频")
                    plays.append("#".join(f"{t}${u}" for t, u in videos))
                if imgs:
                    names.append("图集")
                    plays.append("全部$pics://" + "&&".join(imgs))
                if text:
                    names.append("正文")
                    plays.append("正文$text://" + text)
                result["list"].append({"vod_id": url, "vod_name": name, "vod_pic": pic, "vod_content": text, "vod_play_from": "$$$".join(names), "vod_play_url": "$$$".join(plays)})
            except Exception as e:
                self._error(f"detail sid={sid} error={type(e).__name__}: {e}")
                continue
        return result if result["list"] else {"list": [], "msg": self.last_error or "detail empty"}
    def searchContent(self, key, quick, pg="1"):
        url = self.host + "/search/" + quote(key) + "/" + (f"page/{pg}/" if int(pg or 1) > 1 else "")
        return {"list": self._parse_list(self._get(url)), "page": int(pg)}
    def playerContent(self, flag, id, vipFlags):
        if id.startswith("pics://"):
            return {"parse": 0, "url": "pics://" + "&&".join(self._pic_url(u) for u in id[7:].split("&&") if u), "header": self._player_header()}
        if id.startswith("text://"): return {"parse": 0, "url": id, "header": self._player_header()}
        url = self._fix(id)
        lower = url.lower()
        result = {"parse": 0 if any(x in lower for x in [".m3u8", ".mp4", ".flv"]) else 1, "url": url, "header": self._player_header()}
        if ".m3u8" in lower: result["format"] = "application/x-mpegURL"
        return result
