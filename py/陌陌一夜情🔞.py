# -*- coding: utf-8 -*-
import sys, re, json, base64, html
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
        def searchContent(self, key, quick, pg="1"): pass
        def isVideoFormat(self, url): pass
        def manualVideoCheck(self): pass
        def localProxy(self, param): pass

def fix_url(url, host):
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return urljoin(host, url)
    if url.startswith("http"):
        return url
    return urljoin(host, "/" + url)

def clean_text(text):
    if not text:
        return ""
    return html.unescape(re.sub(r"<[^>]+>", "", str(text))).strip()

class Spider(BaseSpider):
    def __init__(self):
        super().__init__()
        self.host = "https://ryoz487.mmyy25.top"
        self.name = "ZheTianV4_v10_video"
        self.s = requests.Session() if requests else None
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/",
            "sec-ch-ua": "\"Not_A Brand\";v=\"8\", \"Chromium\";v=\"120\""
        }
        if self.s:
            self.s.headers.update(self.headers)

    def init(self, extend=""):
        pass

    def getName(self):
        return self.name

    def isVideoFormat(self, url):
        return any(x in url for x in [".m3u8", ".mp4", ".flv", ".ts"])

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return [200, "video/MP2T", b"", {}]

    def _fetch(self, url):
        if not self.s:
            return ""
        try:
            r = self.s.get(url, timeout=15, headers=self.headers)
            r.raise_for_status()
            return r.text
        except Exception:
            return ""

    def homeContent(self, filter):
        try:
            classes = [
                {"type_name": "美女主播", "type_id": "6"},
                {"type_name": "精品推荐", "type_id": "7"},
                {"type_name": "自拍偷拍", "type_id": "3"},
                {"type_name": "国产乱伦", "type_id": "8"},
                {"type_name": "制服丝袜", "type_id": "9"},
                {"type_name": "传媒探花", "type_id": "10"},
                {"type_name": "清纯学生", "type_id": "11"},
                {"type_name": "淫妻作乐", "type_id": "12"},
                {"type_name": "反差母狗", "type_id": "13"},
                {"type_name": "足浴撩妹", "type_id": "17"},
                {"type_name": "制服诱惑", "type_id": "14"},
                {"type_name": "AI换脸", "type_id": "18"},
                {"type_name": "丝袜美腿", "type_id": "15"},
                {"type_name": "多人群交", "type_id": "4"},
                {"type_name": "中文字幕", "type_id": "16"},
                {"type_name": "主奴调教", "type_id": "5"}
            ]
            filters = {
                "6": [
                    {"key": "by", "name": "排序", "value": [{"n":"时间","v":"time"},{"n":"人气","v":"hits"},{"n":"评分","v":"score"}]}
                ]
            }
            for tid in ["3","4","5","7","8","9","10","11","12","13","14","15","16","17","18"]:
                filters[tid] = filters["6"]
            return {"class": classes, "filters": filters}
        except Exception:
            return {"class": [], "filters": {}}

    def homeVideoContent(self):
        return self.categoryContent("6", "1", False, {})

    def categoryContent(self, tid, pg, filter, extend):
        try:
            result = {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}
            by = extend.get("by", "time") if extend else "time"
            url = f"{self.host}/index.php/vod/type/id/{tid}.html"
            if int(pg) > 1:
                url = f"{self.host}/index.php/vod/type/id/{tid}/page/{pg}.html"
            html_text = self._fetch(url)
            if not html_text:
                return result
            doc = etree.HTML(html_text) if etree else None
            if not doc:
                return result
            items = doc.xpath('//div[contains(@class,"row")]//dl')
            if not items:
                items = doc.xpath('//dl[contains(@class,"preview-item")]')
            if not items:
                items = doc.xpath('//a[contains(@href,"/vod/play/") and .//img]/ancestor::dl')
            seen = set()
            for item in items:
                try:
                    a_tag = item.xpath('.//a[contains(@href,"/vod/play/")]')
                    if not a_tag:
                        continue
                    a_tag = a_tag[0]
                    href = a_tag.get("href", "")
                    if not href:
                        continue
                    vid_match = re.search(r'/id/(\d+)', href)
                    vid = vid_match.group(1) if vid_match else href
                    if vid in seen:
                        continue
                    seen.add(vid)
                    title = item.xpath('.//h3/text()')
                    if not title:
                        title = item.xpath('.//img/@alt')
                    if not title:
                        title = item.xpath('.//a/@title')
                    title = clean_text(title[0]) if title else vid
                    pic = item.xpath('.//img/@src')
                    if not pic:
                        pic = item.xpath('.//img/@data-original')
                    pic = fix_url(pic[0], self.host) if pic else ""
                    result["list"].append({"vod_id": vid, "vod_name": title, "vod_pic": pic, "vod_remarks": ""})
                except Exception:
                    continue
            pc_match = re.search(r'page/(\d+)\.html', html_text)
            if pc_match:
                result["pagecount"] = int(pc_match.group(1))
            else:
                pc_match = re.search(r'共\s*(\d+)\s*页', html_text)
                if pc_match:
                    result["pagecount"] = int(pc_match.group(1))
            return result
        except Exception:
            return {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}

    def detailContent(self, ids):
        try:
            vid = ids[0] if isinstance(ids, list) else ids
            result = {"list": []}
            play_url = f"{self.host}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
            detail_url = f"{self.host}/index.php/vod/detail/id/{vid}.html"
            html_text = self._fetch(play_url)
            if not html_text:
                html_text = self._fetch(detail_url)
            if not html_text:
                return result
            title = vid
            pic = ""
            doc = etree.HTML(html_text) if etree else None
            if doc:
                title_nodes = doc.xpath('//h1/text()') or doc.xpath('//h2/text()') or doc.xpath('//div[contains(@class,"title")]/h3/text()') or doc.xpath('//h3/text()')
                if title_nodes:
                    title = clean_text(title_nodes[0])
                pic_nodes = doc.xpath('//img[contains(@class,"poster") or contains(@class,"cover") or contains(@class,"pic")]/@src') or doc.xpath('//img[contains(@class,"nature")]/@src')
                if pic_nodes:
                    pic = fix_url(pic_nodes[0], self.host)
            play_link = ""
            m = re.search(r'player_data\s*=\s*(\{.*?\})', html_text, re.DOTALL)
            if m:
                try:
                    pdata = json.loads(m.group(1))
                    play_link = pdata.get("url", "")
                except Exception:
                    pass
            if not play_link:
                m = re.search(r'var\s+now\s*=\s*["\']([^"\']+)["\']', html_text)
                if m:
                    play_link = m.group(1)
            if not play_link:
                m = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html_text)
                if m:
                    play_link = m.group(1)
            if not play_link:
                m = re.search(r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*)', html_text)
                if m:
                    play_link = m.group(1)
            if not play_link:
                m = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html_text)
                if m:
                    iframe_src = fix_url(m.group(1), self.host)
                    try:
                        iframe_html = self._fetch(iframe_src)
                        if iframe_html:
                            m2 = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', iframe_html)
                            if m2:
                                play_link = m2.group(1)
                    except Exception:
                        pass
            result["list"].append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_play_from": "默认线路",
                "vod_play_url": f"正片${play_link}" if play_link else f"播放${play_url}"
            })
            return result
        except Exception:
            return {"list": []}

    def playerContent(self, flag, id, vipFlags=None):
        try:
            if self.isVideoFormat(id):
                return {"parse": 0, "url": id, "header": json.dumps({"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]})}
            if id.startswith("http"):
                html_text = self._fetch(id)
                if html_text:
                    play_link = ""
                    m = re.search(r'player_data\s*=\s*(\{.*?\})', html_text, re.DOTALL)
                    if m:
                        try:
                            pdata = json.loads(m.group(1))
                            play_link = pdata.get("url", "")
                        except Exception:
                            pass
                    if not play_link:
                        m = re.search(r'var\s+now\s*=\s*["\']([^"\']+)["\']', html_text)
                        if m:
                            play_link = m.group(1)
                    if not play_link:
                        m = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html_text)
                        if m:
                            play_link = m.group(1)
                    if not play_link:
                        m = re.search(r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*)', html_text)
                        if m:
                            play_link = m.group(1)
                    if play_link:
                        return {"parse": 0, "url": play_link, "header": json.dumps({"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]})}
                return {"parse": 0, "url": id, "header": json.dumps({"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]})}
            return {"parse": 0, "url": id}
        except Exception:
            return {"parse": 0, "url": id}

    def searchContent(self, key, quick, pg="1"):
        try:
            result = {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}
            url = f"{self.host}/index.php/vod/search.html?wd={quote(key)}&page={pg}"
            html_text = self._fetch(url)
            if not html_text:
                return result
            doc = etree.HTML(html_text) if etree else None
            if not doc:
                return result
            items = doc.xpath('//div[contains(@class,"row")]//dl')
            if not items:
                items = doc.xpath('//dl[contains(@class,"preview-item")]')
            if not items:
                items = doc.xpath('//a[contains(@href,"/vod/play/") and .//img]/ancestor::dl')
            seen = set()
            for item in items:
                try:
                    a_tag = item.xpath('.//a[contains(@href,"/vod/play/")]')
                    if not a_tag:
                        continue
                    a_tag = a_tag[0]
                    href = a_tag.get("href", "")
                    if not href:
                        continue
                    vid_match = re.search(r'/id/(\d+)', href)
                    vid = vid_match.group(1) if vid_match else href
                    if vid in seen:
                        continue
                    seen.add(vid)
                    title = item.xpath('.//h3/text()')
                    if not title:
                        title = item.xpath('.//img/@alt')
                    if not title:
                        title = item.xpath('.//a/@title')
                    title = clean_text(title[0]) if title else vid
                    pic = item.xpath('.//img/@src')
                    if not pic:
                        pic = item.xpath('.//img/@data-original')
                    pic = fix_url(pic[0], self.host) if pic else ""
                    result["list"].append({"vod_id": vid, "vod_name": title, "vod_pic": pic, "vod_remarks": ""})
                except Exception:
                    continue
            return result
        except Exception:
            return {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}