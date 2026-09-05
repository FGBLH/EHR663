# -*- coding: utf-8 -*-
import sys, re, json, base64
from urllib.parse import quote, urljoin
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
        def playerContent(self, flag, id, vipFlags): pass
        def searchContent(self, key, quick, pg="1"): pass
        def localProxy(self, param): pass
        def isVideoFormat(self, url): return False
        def manualVideoCheck(self): pass

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://sjsf1dpi.zhenshi27.xyz"
        self.session = requests.Session() if requests else None
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/"
        }
        if self.session:
            self.session.headers.update(self.headers)
        self._title_cache = {}

    def init(self, extend=""):
        pass

    def getName(self):
        return "真实未流出"

    def homeContent(self, filter):
        classes = [
            {"type_name": "国产精品", "type_id": "55"},
            {"type_name": "华语AV", "type_id": "63"},
            {"type_name": "黑料吃瓜", "type_id": "58"},
            {"type_name": "欧美大屌", "type_id": "60"},
            {"type_name": "动漫禁漫", "type_id": "57"},
            {"type_name": "学生合集", "type_id": "65"},
            {"type_name": "乱伦精品", "type_id": "64"},
            {"type_name": "探花约炮", "type_id": "61"},
            {"type_name": "日本有码", "type_id": "80"},
            {"type_name": "主播网红", "type_id": "81"},
            {"type_name": "偷拍自拍", "type_id": "12"},
            {"type_name": "国产制作", "type_id": "20"},
            {"type_name": "乱伦三观", "type_id": "21"},
            {"type_name": "嫖妓过程", "type_id": "22"},
            {"type_name": "淫乱学妹", "type_id": "23"},
            {"type_name": "黑料打烊", "type_id": "24"},
            {"type_name": "监控摄像", "type_id": "69"},
            {"type_name": "高清无码", "type_id": "71"},
            {"type_name": "中文字幕", "type_id": "72"},
            {"type_name": "成人综艺", "type_id": "25"},
            {"type_name": "媚黑母狗", "type_id": "26"},
            {"type_name": "为国争光", "type_id": "88"},
            {"type_name": "少女破处", "type_id": "56"},
            {"type_name": "人兽典藏", "type_id": "73"},
            {"type_name": "中文剧情", "type_id": "74"},
            {"type_name": "女同口交", "type_id": "76"},
            {"type_name": "重口猎奇", "type_id": "77"},
            {"type_name": "3D动漫", "type_id": "78"},
            {"type_name": "剧情故事", "type_id": "84"},
            {"type_name": "同人动漫", "type_id": "85"},
        ]
        return {"class": classes, "filters": {}}

    def homeVideoContent(self):
        return self.categoryContent("63", "1", False, {})

    def _decode_entities(self, text):
        if not text:
            return ""
        buf = []
        i = 0
        L = len(text)
        while i < L:
            if text[i] == '&' and i + 1 < L and text[i + 1] == '#':
                j = text.find(';', i + 2)
                if j != -1 and j - i < 10:
                    entity = text[i + 2:j]
                    try:
                        if entity and (entity[0] == 'x' or entity[0] == 'X'):
                            ch = chr(int(entity[1:], 16))
                        else:
                            ch = chr(int(entity))
                        buf.append(ch)
                        i = j + 1
                        continue
                    except Exception:
                        pass
            buf.append(text[i])
            i += 1
        text = ''.join(buf)
        text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        text = text.replace('&quot;', '"').replace('&apos;', "'").replace('&nbsp;', ' ')
        return text

    def _clean(self, text):
        if not text:
            return ""
        text = self._decode_entities(text)
        text = re.sub(r'<(script|style|svg)[^>]*>[\s\S]*?</\1>', '', text)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _is_dirty(self, text):
        if not text:
            return True
        dirty = ['{', '}', '.cls-', 'fill:', 'stroke:', '@media', 'function(', 'var ']
        for d in dirty:
            if d in text:
                return True
        return False

    def _fetch(self, url):
        if not self.session:
            return ""
        try:
            r = self.session.get(url, headers=self.headers, timeout=15)
            r.raise_for_status()
            r.encoding = "utf-8"
            return r.text
        except Exception as e:
            print("[fetch] %s | %s" % (url, e))
            return ""

    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}
        url = "%s/vodtype/%s-%s.html" % (self.host, tid, pg) if int(pg) > 1 else "%s/vodtype/%s.html" % (self.host, tid)
        text = self._fetch(url)
        if not text:
            return result
        videos = []
        blocks = re.findall(r'<div class="video_item">(.*?)</div>\s*</div>', text, re.S)
        for block in blocks:
            m = re.search(r'href="(/voddetail/(\d+)\.html)"', block)
            if not m:
                continue
            vid = m.group(2)
            pic_m = re.search(r'data-src="([^"]+)"', block)
            pic = pic_m.group(1) if pic_m else ""
            title_m = re.search(r'class="title"[^>]*>(.*?)</a>', block, re.S)
            raw_title = title_m.group(1) if title_m else ""
            title = self._clean(raw_title)
            if '&#;' in title or '&#x' in title:
                print("[warn] title decode fail: %s" % raw_title[:80])
            if vid and title:
                self._title_cache[vid] = title
                videos.append({"vod_id": vid, "vod_name": title, "vod_pic": pic, "vod_remarks": ""})
        if not videos:
            items = re.findall(r'href="(/voddetail/(\d+)\.html)"[^>]*class="img"[^>]*>.*?data-src="([^"]*)".*?class="title"[^>]*>(.*?)</a>', text, re.S)
            for href, vid, pic, title in items:
                title = self._clean(title)
                if vid and title:
                    self._title_cache[vid] = title
                    videos.append({"vod_id": vid, "vod_name": title, "vod_pic": pic, "vod_remarks": ""})
        result["list"] = videos
        pages = re.findall(r'href="/vodtype/\d+-(\d+)\.html"', text)
        if pages:
            result["pagecount"] = max(int(p) for p in pages)
        return result

    def detailContent(self, ids):
        vid = ids[0]
        url = "%s/voddetail/%s.html" % (self.host, vid)
        result = {"list": []}
        text = self._fetch(url)
        if not text:
            return result
        title = self._title_cache.get(vid, "")
        if not title:
            for pat in [
                r'<h1[^>]*>(.*?)</h1>',
                r'<h2[^>]*>(.*?)</h2>',
                r'<div[^>]*class="[^"]*vodname[^"]*"[^>]*>(.*?)</div>',
                r'<div[^>]*class="[^"]*movie-title[^"]*"[^>]*>(.*?)</div>',
                r'<div[^>]*class="[^"]*detail-title[^"]*"[^>]*>(.*?)</div>',
                r'<meta[^>]*name="keywords"[^>]*content="([^"]*)"',
            ]:
                m = re.search(pat, text, re.S)
                if m:
                    t = self._clean(m.group(1))
                    if t and not self._is_dirty(t) and len(t) > 3 and t != vid:
                        title = t
                        break
        if not title:
            title = vid
        pic = ""
        for pat in [
            r'<img[^>]+data-src="([^"]+)"[^>]*class="[^"]*lazyload[^"]*"', 
            r'<img[^>]+src="([^"]+)"[^>]*class="[^"]*poster[^"]*"', 
            r'<img[^>]+src="([^"]+)"[^>]*class="[^"]*cover[^"]*"', 
            r'<img[^>]+data-original="([^"]+)"'
        ]:
            m = re.search(pat, text)
            if m:
                pic = m.group(1)
                if pic:
                    break
        if pic and pic.startswith("/"):
            pic = urljoin(self.host, pic)
        content = ""
        for pat in [
            r'<div[^>]*class="[^"]*(?:detail-content|desc|content|intro|summary)[^"]*"[^>]*>(.*?)</div>', 
            r'<p[^>]*class="[^"]*(?:data|desc|content)[^"]*"[^>]*>(.*?)</p>', 
            r'<meta[^>]*name="description"[^>]*content="([^"]*)"'
        ]:
            m = re.search(pat, text, re.S)
            if m:
                content = self._clean(m.group(1))
                if len(content) > 5 and not self._is_dirty(content):
                    break
        area = ""
        year = ""
        director = ""
        actor = ""
        remarks = ""
        info_text = ""
        m = re.search(r'<div[^>]*class="[^"]*(?:detail-info|vod-info|data|info)[^"]*"[^>]*>(.*?)</div>', text, re.S)
        if m:
            info_text = m.group(1)

        def meta_extract(field, src):
            if not src:
                src = text
            for pat in [field + r'[：:]?\s*<[^>]*>(.*?)</', field + r'[：:]?\s*([^\s<]+)']:
                mm = re.search(pat, src, re.S)
                if mm:
                    val = self._clean(mm.group(1))
                    if val and not self._is_dirty(val):
                        return val
            return ""
        director = meta_extract(r"导演", info_text)
        actor = meta_extract(r"主演", info_text) or meta_extract(r"演员", info_text)
        area = meta_extract(r"地区", info_text) or meta_extract(r"国家", info_text)
        year = meta_extract(r"年份", info_text) or meta_extract(r"年代", info_text)
        if not year:
            y = re.search(r'(\d{4})', title)
            if y:
                year = y.group(1)
        remarks = meta_extract(r"更新", info_text) or meta_extract(r"状态", info_text) or meta_extract(r"备注", info_text)
        sources = []
        play_urls = []
        all_eps = re.findall(r'href="(/vodplay/(\d+)-(\d+)-(\d+)\.html)"[^>]*>(.*?)</a>', text, re.S)
        if not all_eps:
            all_eps = re.findall(r'href="(/play/(\d+)-(\d+)-(\d+)\.html)"[^>]*>(.*?)</a>', text, re.S)
        sid_map = {}
        for ep in all_eps:
            ep_url, ep_vid, ep_sid, ep_nid, ep_name = ep
            ep_name = self._clean(ep_name) or ("第%s集" % ep_nid)
            if self._is_dirty(ep_name):
                ep_name = "第%s集" % ep_nid
            full_url = urljoin(self.host, ep_url)
            sid = int(ep_sid)
            if sid not in sid_map:
                sid_map[sid] = []
            sid_map[sid].append("%s$%s" % (ep_name, full_url))
        source_names = {}
        name_blocks = re.findall(r'<(?:h3|span|a|div)[^>]*class="[^"]*(?:tab|option|source|from)[^"]*"[^>]*>(.*?)</(?:h3|span|a|div)>', text, re.S)
        idx = 1
        for nb in name_blocks:
            name = self._clean(nb)
            if name and not self._is_dirty(name) and len(name) < 20:
                source_names[idx] = name
                idx += 1
        for sid in sorted(sid_map.keys()):
            sname = source_names.get(sid, "线路%s" % sid)
            sources.append(sname)
            play_urls.append("#".join(sid_map[sid]))
        if not sources:
            m3u8 = re.search(r'(https?://[^\s"\'<>]+\.(?:m3u8|mp4)[^\s"\'<>]*)', text)
            if m3u8:
                sources.append("默认线路")
                play_urls.append("正片$%s" % m3u8.group(1))
            else:
                sources.append("默认线路")
                play_urls.append("播放$%s" % url)
        result["list"].append({
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_content": content,
            "vod_remarks": remarks,
            "vod_area": area,
            "vod_year": year,
            "vod_director": director,
            "vod_actor": actor,
            "vod_play_from": "$$$".join(sources),
            "vod_play_url": "$$$".join(play_urls)
        })
        return result

    def playerContent(self, flag, id, vipFlags):
        if self.isVideoFormat(id):
            return {"parse": 0, "url": id, "header": json.dumps(self.headers)}
        if not id.startswith("http"):
            id = urljoin(self.host, id)
        text = self._fetch(id)
        if not text:
            return {"parse": 0, "url": id, "header": json.dumps(self.headers)}
        for pat_name, pat in [("player_data", r'player_data\s*=\s*(\{.*?\})'), ("player_aaaa", r'var\s+player_aaaa\s*=\s*(\{.*?\})')]:
            m = re.search(pat, text, re.DOTALL)
            if m:
                try:
                    data = json.loads(m.group(1))
                    url = data.get("url", "")
                    encrypt = data.get("encrypt", 0)
                    if encrypt == 2 and url:
                        try:
                            url = base64.b64decode(url).decode('utf-8')
                        except:
                            pass
                    if url:
                        return {"parse": 0, "url": url, "header": json.dumps(self.headers)}
                except:
                    pass
        m = re.search(r'var\s+now\s*=\s*["\']([^"\']+)["\']', text)
        if m:
            return {"parse": 0, "url": m.group(1), "header": json.dumps(self.headers)}
        m = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', text)
        if m:
            src = m.group(1)
            if src.startswith("//"):
                src = "https:" + src
            elif src.startswith("/"):
                src = urljoin(self.host, src)
            return {"parse": 1, "url": src, "header": json.dumps(self.headers)}
        m = re.search(r'(https?://[^\s"\'<>]+\.(?:m3u8|mp4|flv)[^\s"\'<>]*)', text)
        if m:
            return {"parse": 0, "url": m.group(1), "header": json.dumps(self.headers)}
        if "eval(" in text:
            return {"parse": 1, "url": id, "header": json.dumps(self.headers)}
        return {"parse": 0, "url": id, "header": json.dumps(self.headers)}

    def searchContent(self, key, quick, pg="1"):
        result = {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}
        url = "%s/vodsearch/-------------.html?wd=%s" % (self.host, quote(key))
        if int(pg) > 1:
            url = "%s/vodsearch/%s----------%s---.html" % (self.host, quote(key), pg)
        text = self._fetch(url)
        if not text:
            return result
        videos = []
        blocks = re.findall(r'<div class="video_item">(.*?)</div>\s*</div>', text, re.S)
        for block in blocks:
            m = re.search(r'href="(/voddetail/(\d+)\.html)"', block)
            if not m:
                continue
            vid = m.group(2)
            pic_m = re.search(r'data-src="([^"]+)"', block)
            pic = pic_m.group(1) if pic_m else ""
            title_m = re.search(r'class="title"[^>]*>(.*?)</a>', block, re.S)
            title = self._clean(title_m.group(1)) if title_m else ""
            if vid and title:
                self._title_cache[vid] = title
                videos.append({"vod_id": vid, "vod_name": title, "vod_pic": pic, "vod_remarks": ""})
        if not videos:
            items = re.findall(r'href="(/voddetail/(\d+)\.html)"[^>]*class="img"[^>]*>.*?data-src="([^"]*)".*?class="title"[^>]*>(.*?)</a>', text, re.S)
            for href, vid, pic, title in items:
                title = self._clean(title)
                if vid and title:
                    self._title_cache[vid] = title
                    videos.append({"vod_id": vid, "vod_name": title, "vod_pic": pic, "vod_remarks": ""})
        result["list"] = videos
        pages = re.findall(r'href="/vodsearch/[^"]+--(\d+)---\.html"', text)
        if pages:
            result["pagecount"] = max(int(p) for p in pages)
        return result

    def localProxy(self, param):
        return [200, "video/MP2T", b"", {}]

    def isVideoFormat(self, url):
        return any(x in url for x in [".m3u8", ".mp4", ".flv", ".ts"])

    def manualVideoCheck(self):
        return False
