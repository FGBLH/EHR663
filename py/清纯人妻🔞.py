# -*- coding: utf-8 -*-
#!/usr/bin/python
import sys, re, json, base64, html, os, threading, time, hashlib
from urllib.parse import quote, unquote, urljoin, urlparse
try:
    from lxml import etree
except ImportError:
    etree = None
try:
    import requests
except ImportError:
    requests = None
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def init(self, extend=""): pass
        def homeContent(self, filter): pass
        def homeVideoContent(self): pass
        def categoryContent(self, tid, pg, filter, extend): pass
        def detailContent(self, ids): pass
        def playerContent(self, flag, id, vipFlags=None): pass
        def searchContent(self, key, quick, pg='1'): pass
        def isVideoFormat(self, url): pass
        def manualVideoCheck(self): pass
        def localProxy(self, param): pass

def fix_url(url, host):
    if not url: return ""
    if url.startswith("//"): return "https:" + url
    if url.startswith("/"): return urljoin(host, url)
    if url.startswith("http"): return url
    return urljoin(host, "/" + url)

def clean_text(text):
    if not text: return ""
    return html.unescape(re.sub(r"<[^>]+>", "", str(text))).strip()

def extract_play(html_text, host):
    m = re.search(r'(https?://\S+?\.m3u8)', html_text)
    if m: return m.group(1)
    m = re.search(r'(https?://\S+?\.mp4)', html_text)
    if m: return m.group(1)
    m = re.search(r'var\s+src\s*=\s*([\"\'])(.+?)\1', html_text)
    if m: return m.group(2).replace("\\/", "/")
    m = re.search(r'player_data\s*=\s*(\{.*?\})', html_text, re.DOTALL)
    if m:
        try: return json.loads(m.group(1)).get("url", "")
        except: pass
    m = re.search(r'<iframe[^>]+src=([\"\'])(.+?)\1', html_text)
    if m:
        iframe_src = fix_url(m.group(2), host)
        try:
            iframe_html = requests.get(iframe_src, headers={"User-Agent":"Mozilla/5.0","Referer":host+"/"}, timeout=10, verify=False).text
            m2 = re.search(r'(https?://\S+?\.m3u8)', iframe_html)
            if m2: return m2.group(1)
        except: pass
    m = re.search(r'videoSources\s*:\s*(\[.*?\])', html_text, re.DOTALL)
    if m:
        try:
            srcs = json.loads(m.group(1))
            return srcs[0].get("file", "") if srcs else ""
        except: pass
    m = re.search(r'url\s*:\s*([\"\'])([^\1]+?\.m3u8)\1', html_text)
    if m: return m.group(2)
    m = re.search(r'var\s+playurl\s*=\s*([\"\'])(.+?)\1', html_text)
    if m: return m.group(2)
    m = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\})', html_text, re.DOTALL)
    if m:
        try: return json.loads(m.group(1)).get("url", "")
        except: pass
    m = re.search(r'(https?://\S+?\.(?:m3u8|mp4|flv))', html_text)
    return m.group(1) if m else ""

def _parse_list_regex(html_text, host):
    videos = []
    seen = set()
    pattern = r'<a[^>]*href=([\"\'])([^\1]*?/v/video-(\d+)/)\1[^>]*class=[\"\'][^\"\']*post-link[^\"\']*[\"\'][^>]*>[\s\S]*?<img[^>]*src=([\"\'])([^\4]+)\4[^>]*alt=([\"\'])([^\6]*)\6[^>]*>[\s\S]*?<span>([^<]+)</span>'
    for m in re.finditer(pattern, html_text):
        href, vid, pic, alt, title = m.group(2), m.group(3), m.group(5), m.group(7), m.group(8)
        if vid in seen: continue
        seen.add(vid)
        videos.append({"vod_id": vid, "vod_name": clean_text(title or alt), "vod_pic": fix_url(pic, host), "vod_remarks": ""})
    if videos: return videos
    pattern2 = r'<a[^>]*href=[\"\']([^\"\']*/v/video-(\d+)/)[\"\'][^>]*>[\s\S]*?<img[^>]*src=[\"\']([^\"\']+)[\"\'][^>]*alt=[\"\']([^\"\']*)[\"\'][^>]*>[\s\S]*?<span>([^<]+)</span>'
    for m in re.finditer(pattern2, html_text):
        href, vid, pic, alt, title = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
        if vid in seen: continue
        seen.add(vid)
        videos.append({"vod_id": vid, "vod_name": clean_text(title or alt), "vod_pic": fix_url(pic, host), "vod_remarks": ""})
    return videos

class Spider(BaseSpider):
    def __init__(self):
        super().__init__()
        self.host = "https://wtwgi.qingwife01.club"
        self.name = "ZheTian_qingwife_wp"
        self.s = requests.Session() if requests else None
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/",
            "sec-ch-ua": "\"Not_A Brand\";v=\"8\", \"Chromium\";v=\"120\"",
            "Upgrade-Insecure-Requests": "1"
        }
        self.seen_ids = set()
        if self.s: self.s.headers.update(self.headers)

    def init(self, extend=""):
        if extend and extend.startswith("http"):
            self.host = extend.rstrip("/")
            self.headers["Referer"] = self.host + "/"
            if self.s: self.s.headers.update({"Referer": self.host + "/"})

    def getName(self):
        return self.name

    def isVideoFormat(self, url):
        return any(x in url for x in [".m3u8", ".mp4", ".flv", ".ts"])

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return [200, "video/MP2T", b"", {}]

    def _fetch(self, url):
        if not self.s: return ""
        try:
            r = self.s.get(url, timeout=15, headers=self.headers, verify=False)
            r.raise_for_status()
            r.encoding = "utf-8"
            return r.text
        except Exception as e:
            return ""

    def homeContent(self, filter):
        try:
            classes = [
                {"type_name": "女优明星", "type_id": "nv-you-ming-xing"},
                {"type_name": "欧美无码", "type_id": "ou-mei-wu-ma"},
                {"type_name": "中文字幕", "type_id": "zhong-wen-zi-mu"},
                {"type_name": "熟女人妻", "type_id": "shu-nv-ren-qi"},
                {"type_name": "制服诱惑", "type_id": "zhi-fu-you-huo"},
                {"type_name": "多人群交", "type_id": "duo-ren-qun-jiao"},
                {"type_name": "萝莉少女", "type_id": "luo-li-shao-nv"},
                {"type_name": "强奸乱伦", "type_id": "qiang-jian-luan-lun"},
                {"type_name": "网红头条", "type_id": "wang-hong-tou-tiao"},
                {"type_name": "SM调教", "type_id": "SM-tiao-jiao"},
                {"type_name": "国产自拍", "type_id": "guo-chan-zi-pai"},
                {"type_name": "欧美系列", "type_id": "ou-mei-xi-lie"},
                {"type_name": "美女主播", "type_id": "mei-nv-zhu-bo"},
                {"type_name": "抖音视频", "type_id": "dou-yin-shi-pin"},
                {"type_name": "网爆黑料", "type_id": "wang-bao-hei-liao"},
                {"type_name": "卡通动漫", "type_id": "ka-tong-dong-man"},
                {"type_name": "AI换脸", "type_id": "AI-huan-lian"},
                {"type_name": "韩国主播", "type_id": "han-guo-zhu-bo"},
                {"type_name": "麻豆传媒", "type_id": "ma-dou-chuan-mei"},
                {"type_name": "三级伦理", "type_id": "san-ji-lun-li"},
                {"type_name": "AV解说", "type_id": "AV-jie-shuo"},
                {"type_name": "无码专区", "type_id": "wu-ma-zhuan-qu"},
                {"type_name": "美乳巨乳", "type_id": "mei-ru-ju-ru"},
                {"type_name": "女同性爱", "type_id": "nv-tong-xing-ai"},
            ]
            filters = {}
            return {"class": classes, "filters": filters}
        except Exception as e:
            return {"class": [], "filters": {}}

    def homeVideoContent(self):
        return self.categoryContent("nv-you-ming-xing", "1", False, {})

    def categoryContent(self, tid, pg, filter, extend):
        try:
            result = {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}
            if int(pg) <= 1:
                url = f"{self.host}/vtype/{tid}/"
            else:
                url = f"{self.host}/vtype/{tid}/page/{pg}/"
            html_text = self._fetch(url)
            if not html_text: return result
            if etree:
                try:
                    doc = etree.HTML(html_text)
                    if doc:
                        items = doc.xpath('//a[contains(@class,"post-link")]')
                        if not items:
                            items = doc.xpath('//div[contains(@class,"post-item")]//a')
                        self.seen_ids.clear()
                        for item in items:
                            try:
                                href = item.xpath('./@href')[0] if item.xpath('./@href') else ""
                                if "/v/video-" not in href:
                                    continue
                                vid_match = re.search(r'/v/video-(\d+)/', href)
                                vid = vid_match.group(1) if vid_match else href
                                if vid in self.seen_ids: continue
                                self.seen_ids.add(vid)
                                title = item.xpath('.//div[contains(@class,"post-title-container")]//span/text()')
                                if not title: title = item.xpath('.//img/@alt')
                                if not title: title = item.xpath('./@title')
                                title = clean_text(title[0]) if title else vid
                                pic = item.xpath('.//img/@src') or item.xpath('.//img/@data-src') or item.xpath('.//img/@data-original')
                                pic = fix_url(pic[0], self.host) if pic else ""
                                result["list"].append({"vod_id": vid, "vod_name": title, "vod_pic": pic, "vod_remarks": ""})
                            except Exception as e:
                                continue
                except Exception as e:
                    pass
            if not result["list"]:
                result["list"] = _parse_list_regex(html_text, self.host)
            if etree:
                try:
                    doc = etree.HTML(html_text)
                    if doc:
                        page_nav = doc.xpath('//div[contains(@class,"page-nav")]//a[contains(@class,"page-numbers")]/@href')
                        max_page = 1
                        for p in page_nav:
                            m = re.search(r'/page/(\d+)/', p)
                            if m: max_page = max(max_page, int(m.group(1)))
                        if max_page > 1: result["pagecount"] = max_page
                except:
                    pass
            if result["pagecount"] == 1 and len(result["list"]) >= 24:
                result["pagecount"] = int(pg) + 1
            return result
        except Exception as e:
            return {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}

    def detailContent(self, ids):
        try:
            vid = ids[0] if isinstance(ids, list) else ids
            result = {"list": []}
            url = f"{self.host}/v/video-{vid}/"
            html_text = self._fetch(url)
            if not html_text: return result
            doc = etree.HTML(html_text) if etree else None
            title = vid
            pic = ""
            if doc:
                try:
                    title_el = doc.xpath('//h1/text()') or doc.xpath('//h2/text()') or doc.xpath('//title/text()')
                    if title_el: title = clean_text(title_el[0])
                    pic_el = doc.xpath('//meta[@property="og:image"]/@content') or doc.xpath('//img[contains(@class,"poster")]/@src') or doc.xpath('//img[contains(@class,"cover")]/@src')
                    if pic_el: pic = fix_url(pic_el[0], self.host)
                except:
                    pass
            play_url = extract_play(html_text, self.host)
            result["list"].append({
                "vod_id": vid, "vod_name": title, "vod_pic": pic,
                "vod_play_from": "默认线路",
                "vod_play_url": f"正片${play_url or url}"
            })
            return result
        except Exception as e:
            return {"list": []}

    def playerContent(self, flag, id, vipFlags=None):
        try:
            result = {"parse": 0, "playUrl": "", "url": "", "header": ""}
            if self.isVideoFormat(id):
                result["url"] = id
                result["header"] = json.dumps({"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]})
                return result
            if id.startswith("http") and not self.isVideoFormat(id):
                html_text = self._fetch(id)
                if html_text:
                    play_url = extract_play(html_text, self.host)
                    if play_url:
                        result["url"] = play_url
                        result["header"] = json.dumps({"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]})
                        return result
            result["url"] = id
            result["header"] = json.dumps({"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]})
            return result
        except Exception as e:
            return {"parse": 0, "playUrl": "", "url": id, "header": ""}

    def searchContent(self, key, quick, pg="1"):
        try:
            result = {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}
            if int(pg) <= 1:
                url = f"{self.host}/?s={quote(key)}"
            else:
                url = f"{self.host}/page/{pg}/?s={quote(key)}"
            html_text = self._fetch(url)
            if not html_text: return result

            if etree:
                try:
                    doc = etree.HTML(html_text)
                    if doc:
                        items = doc.xpath('//a[contains(@class,"post-link")]')
                        if not items:
                            items = doc.xpath('//div[contains(@class,"post-item")]//a')
                        self.seen_ids.clear()
                        for item in items:
                            try:
                                href = item.xpath('./@href')[0] if item.xpath('./@href') else ""
                                if "/v/video-" not in href:
                                    continue
                                vid_match = re.search(r'/v/video-(\d+)/', href)
                                vid = vid_match.group(1) if vid_match else href
                                if vid in self.seen_ids: continue
                                self.seen_ids.add(vid)
                                title = item.xpath('.//div[contains(@class,"post-title-container")]//span/text()')
                                if not title: title = item.xpath('.//img/@alt')
                                if not title: title = item.xpath('./@title')
                                title = clean_text(title[0]) if title else vid
                                pic = item.xpath('.//img/@src') or item.xpath('.//img/@data-src') or item.xpath('.//img/@data-original')
                                pic = fix_url(pic[0], self.host) if pic else ""
                                result["list"].append({"vod_id": vid, "vod_name": title, "vod_pic": pic, "vod_remarks": ""})
                            except Exception as e:
                                continue
                except:
                    pass

            if not result["list"]:
                result["list"] = _parse_list_regex(html_text, self.host)

            if etree:
                try:
                    doc = etree.HTML(html_text)
                    if doc:
                        page_nav = doc.xpath('//div[contains(@class,"page-nav")]//a[contains(@class,"page-numbers")]/@href')
                        max_page = 1
                        for p in page_nav:
                            m = re.search(r'/page/(\d+)/', p)
                            if m: max_page = max(max_page, int(m.group(1)))
                        if max_page > 1: result["pagecount"] = max_page
                except:
                    pass
            if result["pagecount"] == 1 and len(result["list"]) >= 24:
                result["pagecount"] = int(pg) + 1
            return result
        except Exception as e:
            return {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}