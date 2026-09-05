# coding=utf-8
import re, html, base64, requests, urllib.parse
from base.spider import Spider

pub_urls = ["https://abc.hdfby.com","https://b.hdfby.com","https://b.hdfby.net","https://b.hdfby.org"]
domain_list = ["https://hd28.huadutx.com/","https://rb.huaduys.org/"]

class Spider(Spider):
    def getName(self): return "花都影视"
    def init(self, extend=""):
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0"
        self.session = requests.Session()
        self.cache = {}
        self.headers = {"User-Agent":self.ua,"Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8","Referer":"https://hd28.huadutx.com/","Accept-Language":"zh-CN,zh;q=0.9"}
        self.host = self._domain()
        self.headers["Referer"] = self.host
        self.mheaders = {"User-Agent":"Linux; Android 12; Pixel 3 XL) AppleWebKit/537.36 Chrome/98.0.4758.101 Mobile Safari/537.36"}
        self.fallback = [
            {"type_id":"/vodshow/1-----------.html","type_name":"中文字幕"},
            {"type_id":"/vodshow/2-----------.html","type_name":"无字幕"},
            {"type_id":"/vodshow/3-----------.html","type_name":"国产"},
            {"type_id":"/vodshow/4-----------.html","type_name":"动漫"},
            {"type_id":"/vodshow/5-----------.html","type_name":"欧美"},
            {"type_id":"/vodshow/6-----------.html","type_name":"中字无码"},
            {"type_id":"/vodshow/7-----------.html","type_name":"中字有码"},
            {"type_id":"/vodshow/8-----------.html","type_name":"步兵无码"},
            {"type_id":"/vodshow/9-----------.html","type_name":"骑兵有码"},
            {"type_id":"/vodshow/10-----------.html","type_name":"国产精品"},
            {"type_id":"/vodshow/11-----------.html","type_name":"国产传媒"},
            {"type_id":"/vodshow/12-----------.html","type_name":"糖心Vlog"},
            {"type_id":"/vodshow/13-----------.html","type_name":"欧美中字"},
            {"type_id":"/vodshow/14-----------.html","type_name":"中字里番"},
            {"type_id":"/vodshow/15-----------.html","type_name":"3D动漫"},
            {"type_id":"/vodshow/16-----------.html","type_name":"AI短剧"}
        ]
    def _get(self, url):
        if url in self.cache: return self.cache[url]
        try:
            r = self.session.get(url, headers=self.headers, timeout=8, verify=False, allow_redirects=True)
            r.encoding = "utf-8"
            self.cache[url] = r.text
            return r.text
        except Exception:
            self.cache[url] = ""
            return ""
    def _fix(self, u):
        return "https:" + u if u.startswith("//") else self.host.rstrip("/") + u if u.startswith("/") else u
    def _ok(self, u):
        t = self._get(u if u.endswith("/") else u + "/")
        return len(t) > 200 and any(x in t for x in ["花都","huadu","vodtype","voddetail","stui"])
    def _domain(self):
        for u in domain_list:
            if self._ok(u): return u
        for p in pub_urls:
            t = self._get(p)
            for u in dict.fromkeys([x if x.endswith("/") else x + "/" for x in re.findall(r'https?://[a-zA-Z0-9.-]+\.(?:com|net|org|top|cc|vip)/?', t)]):
                if self._ok(u): return u
        return domain_list[0]
    def _mid(self, text, a, b):
        i = text.find(a)
        if i < 0: return ""
        j = text.find(b, i + len(a))
        return "" if j < 0 else text[i + len(a):j].replace("\\","")
    def _txt(self, s):
        return re.sub(r'\s+'," ",re.sub(r'<[^>]+>',"",html.unescape(s))).strip()
    def _pic(self, s):
        for k in ["data-original","data-src","data-lazyload","data-lazy-src","src"]:
            m = re.search(r'<img[^>]+%s=["\']([^"\']+)' % k, s)
            if m:
                u = m.group(1).strip()
                if u and "blank" not in u.lower() and "loading" not in u.lower() and "default" not in u.lower():
                    return self._fix(u)
        return ""
    def _videos(self, text):
        out, seen = [], set()
        for b in re.findall(r'<li[\s\S]*?</li>', text):
            if "stui-vodlist__thumb" not in b and "voddetail" not in b: continue
            if any(x in b for x in ["广告点赞","开元棋牌","澳门新葡京","好色直播","注册送","棋牌","赌场","葡京","博彩"]): continue
            hm = re.search(r'<h4[^>]*class=["\'][^"\']*title[^"\']*["\'][\s\S]*?<a[^>]+href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>', b)
            am = re.search(r'<a[^>]+class=["\'][^"\']*stui-vodlist__thumb[^"\']*["\'][^>]+href=["\']([^"\']+)["\']', b)
            href = hm.group(1) if hm else am.group(1) if am else ""
            if "voddetail" not in href: continue
            name = self._txt(hm.group(2)) if hm else ""
            if not name:
                tm = re.search(r'title=["\']([^"\']+)["\']', b)
                name = tm.group(1).strip() if tm else ""
            if not href or not name or href in seen or len(name) < 2: continue
            pic = self._pic(b)
            if not pic: continue
            seen.add(href)
            rm = re.search(r'<span[^>]+class=["\'][^"\']*pic-text[^"\']*["\'][^>]*>([\s\S]*?)</span>', b)
            remark = self._txt(rm.group(1)) if rm else ""
            out.append({"vod_id":href,"vod_name":name,"vod_pic":pic,"vod_remarks":remark})
        return out
    def homeContent(self, filter):
        text = self._get(self.host)
        arr, seen = [], set()
        for href, name in re.findall(r'<a[^>]+href=["\']([^"\']*(?:vodtype|vodshow)[^"\']+)["\'][^>]*>([\s\S]*?)</a>', text):
            name = self._txt(name)
            if not name or name in ["首页","发布页","VPN下载"]: continue
            href = href.replace("vodtype","vodshow")
            cid = href.split(".html")[0] + "-----------.html" if ".html" in href and "-----------" not in href else href.rstrip("/") + "-----------.html" if ".html" not in href else href
            if cid not in seen:
                seen.add(cid)
                arr.append({"type_id":cid,"type_name":name})
        for href, name in re.findall(r'<a[^>]+href=["\'](/vodshow/\d+-----------\.html)["\'][^>]*>([\s\S]*?)</a>', text):
            name = self._txt(name)
            if name and href not in seen:
                seen.add(href)
                arr.append({"type_id":href,"type_name":name})
        return {"class":arr if arr else self.fallback,"list":self._videos(text),"filters":{}}
    def homeVideoContent(self):
        return {"list":self._videos(self._get(self.host))}
    def categoryContent(self, cid, pg, filter, ext):
        pg = int(pg or 1)
        base = cid.split("---.html")[0] if "---.html" in cid else cid.replace(".html","")
        items = self._videos(self._get(self._fix(f"{base}{pg}---.html")))
        return {"page":pg,"pagecount":9999,"limit":90,"total":999999,"list":items}
    def detailContent(self, ids):
        did = self._fix(ids[0])
        text = html.unescape(self._get(did))
        name = self._txt(self._mid(text, "<h1", "</h1>")) or self._txt(self._mid(text, "标题：", "</span>"))
        pic = self._pic(text)
        content = name or ""
        director = " ".join(re.findall(r'分类：[\s\S]*?target=["\'][^"\']*["\']>(.*?)</a>', text))
        actor = " ".join(re.findall(r'演员：[\s\S]*?target=["\'][^"\']*["\']>(.*?)</a>', text))
        remarks = " ".join(re.findall(r'类别：[\s\S]*?target=["\'][^"\']*["\']>(.*?)</a>', text))
        year = self._txt(self._mid(text, "日期：", "p>"))
        area = self._txt(self._mid(text, "时长：", "p>"))
        pm = re.search(r'class=["\']btn btn-primary["\'][^>]+href=["\']([^"\']+)["\']', text)
        play = self._fix(pm.group(1)) if pm else did
        return {"list":[{"vod_id":did,"vod_name":name,"vod_pic":pic,"vod_director":director,"vod_actor":actor,"vod_remarks":remarks,"vod_year":year,"vod_area":area,"vod_content":content,"vod_play_from":"花都专线","vod_play_url":"播放$" + play}]}
    def searchContentPage(self, key, quick, pg):
        items = self._videos(self._get(self._fix("/vodsearch/-------------.html?wd=" + urllib.parse.quote(key))))
        return {"list":items,"page":int(pg),"pagecount":9999,"limit":90,"total":999999}
    def searchContent(self, key, quick, pg="1"):
        return self.searchContentPage(key, quick, pg)
    def playerContent(self, flag, id, vipFlags):
        text = self._get(id)
        u = self._mid(text, '"","url":"', '"') or self._mid(text, '"url":"', '"')
        if u:
            try: u = urllib.parse.unquote(base64.b64decode(u).decode("utf-8"))
            except Exception: u = urllib.parse.unquote(u)
        return {"parse":0 if u else 1,"playUrl":"","url":u or id,"header":self.mheaders}