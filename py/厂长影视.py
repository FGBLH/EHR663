#!/usr/bin/python
# -*- coding: utf-8 -*-
import json
import re
import html
from urllib.parse import quote, unquote, urljoin

try:
    from base.spider import Spider as BaseSpider
except Exception:
    import requests
    class BaseSpider(object):
        def fetch(self, url, headers=None, params=None, timeout=15, **kwargs):
            return requests.get(url, headers=headers, params=params, timeout=timeout, **kwargs)

from lxml import etree


class Spider(BaseSpider):
    def getName(self):
        return "厂长影视"

    def init(self, extend=""):
        self.host = "https://www.hebeigoogle.com"
        self.name = "厂长影视"
        self.header = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Referer": self.host + "/",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }

    def homeContent(self, filter):
        self.init()
        classes = [
            {"type_name": "电影", "type_id": "1"},
            {"type_name": "电视剧", "type_id": "2"},
            {"type_name": "综艺", "type_id": "3"},
            {"type_name": "动漫", "type_id": "4"},
            {"type_name": "短剧", "type_id": "5"},
        ]
        years = [{"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 2009, -1)]
        area = [{"n": i, "v": "" if i == "全部" else i} for i in ["全部", "大陆", "香港", "台湾", "美国", "法国", "英国", "日本", "韩国", "德国", "泰国", "印度", "其他"]]
        by = [{"n": "最新", "v": "time"}, {"n": "最热", "v": "hits"}, {"n": "评分", "v": "score"}]
        filters = {
            "1": [{"key": "cate", "name": "类型", "value": self._opts([("全部", ""), ("动作片", "6"), ("喜剧片", "7"), ("爱情片", "8"), ("科幻片", "9"), ("恐怖片", "10"), ("剧情片", "11"), ("战争片", "12"), ("纪录片", "13"), ("悬疑片", "14"), ("犯罪片", "15"), ("动画片", "16")])}, {"key": "area", "name": "地区", "value": area}, {"key": "year", "name": "年代", "value": years}, {"key": "by", "name": "排序", "value": by}],
            "2": [{"key": "cate", "name": "类型", "value": self._opts([("全部", ""), ("国产剧", "17"), ("港台剧", "18"), ("日韩剧", "20"), ("欧美剧", "21"), ("海外剧", "22")])}, {"key": "area", "name": "地区", "value": area}, {"key": "year", "name": "年代", "value": years}, {"key": "by", "name": "排序", "value": by}],
            "3": [{"key": "cate", "name": "类型", "value": self._opts([("全部", ""), ("大陆综艺", "23"), ("港台综艺", "24"), ("日韩综艺", "25"), ("欧美综艺", "26")])}, {"key": "area", "name": "地区", "value": area}, {"key": "year", "name": "年代", "value": years}, {"key": "by", "name": "排序", "value": by}],
            "4": [{"key": "cate", "name": "类型", "value": self._opts([("全部", ""), ("国产动漫", "27"), ("日韩动漫", "28"), ("欧美动漫", "29"), ("其他动漫", "30")])}, {"key": "area", "name": "地区", "value": area}, {"key": "year", "name": "年代", "value": years}, {"key": "by", "name": "排序", "value": by}],
            "5": [{"key": "class", "name": "类型", "value": self._opts([("全部", ""), ("女频恋爱", "女频恋爱"), ("反转爽", "反转爽"), ("脑洞悬疑", "脑洞悬疑"), ("年代穿越", "年代穿越"), ("古装仙侠", "古装仙侠"), ("现代都市", "现代都市")])}, {"key": "year", "name": "年代", "value": years}, {"key": "by", "name": "排序", "value": by}],
        }
        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        self.init()
        try:
            root = self._html(self.host + "/")
            return {"list": self._parse_vods(root)[:24]}
        except Exception as e:
            print(f"[{self.name}] 错误: 首页爬取失败 - {e}")
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        self.init()
        try:
            pg = str(pg or "1")
            url = self._category_url(str(tid), pg, extend or {})
            root = self._html(url)
            vods = self._parse_vods(root)
            pagecount, total = self._page_info(root, len(vods), pg)
            print(f"[{self.name}] 分类列表匹配到 {len(vods)} 个视频")
            return {"list": vods, "page": int(pg), "pagecount": pagecount, "limit": 36, "total": total}
        except Exception as e:
            print(f"[{self.name}] 错误: 分类爬取失败 - {e}")
            return {"list": [], "page": int(pg or 1), "pagecount": 1, "limit": 36, "total": 0}

    def detailContent(self, ids):
        self.init()
        try:
            vid = ids[0] if isinstance(ids, list) else ids
            vid = re.search(r"(\d+)", str(vid)).group(1)
            url = f"{self.host}/igojs/{vid}.html"
            root = self._html(url)
            name = self._first(root.xpath('//meta[@property="og:title"]/@content'))
            name = re.search(r"《(.+?)》", name).group(1) if re.search(r"《(.+?)》", name) else self._clean(root.xpath('string(//div[contains(@class,"detail")]//h1)'))
            pic = self._fix(self._first(root.xpath('//meta[@property="og:image"]/@content')))
            desc = self._clean(root.xpath('string((//div[contains(@class,"vod_content")])[1])')) or self._meta_desc(root)
            actor = self._info_by_label(root, "主演")
            director = self._info_by_label(root, "导演")
            area = self._info_by_label(root, "制片国家")
            remarks = self._info_by_label(root, "状态")
            vtype = self._clean(root.xpath('string(//span[contains(@class,"video-tag-icon")])'))
            play_from, play_url = self._parse_play_lists(root)
            vod = {
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic,
                "type_name": vtype,
                "vod_year": self._first(re.findall(r"/igosw/\d+-{11}(\d{4})\.html", etree.tostring(root, encoding="unicode"))),
                "vod_area": area,
                "vod_remarks": remarks,
                "vod_actor": actor,
                "vod_director": director,
                "vod_content": desc,
                "vod_play_from": play_from,
                "vod_play_url": play_url,
            }
            print(f"[{self.name}] 详情页提取到 {len(play_from.split('$$$')) if play_from else 0} 个播放源")
            return {"list": [vod]}
        except Exception as e:
            print(f"[{self.name}] 错误: 详情解析失败 - {e}")
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        self.init()
        try:
            url = f"{self.host}/igoso/-------------.html?wd={quote(str(key))}"
            if str(pg) != "1":
                url += f"&page={pg}"
            root = self._html(url)
            vods = self._parse_vods(root)
            print(f"[{self.name}] 搜索结果匹配到 {len(vods)} 个视频")
            return {"list": vods, "page": int(pg or 1), "pagecount": 1, "limit": 20, "total": len(vods)}
        except Exception as e:
            print(f"[{self.name}] 错误: 搜索失败 - {e}")
            return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        self.init()
        try:
            url = self._fix(str(id))
            if self.isVideoFormat(url):
                return {"parse": 0, "playUrl": "", "url": url, "header": self.header}
            text = self._text(url)
            p = re.search(r"var\s+player_aaaa\s*=\s*(\{[\s\S]*?\})\s*</script>", text)
            if p:
                data = json.loads(p.group(1))
                play = unquote(data.get("url", "")).replace("\\/", "/")
                print(f"[{self.name}] 播放解析: {flag} -> {play[:60]}...")
                return {"parse": 0, "playUrl": "", "url": play, "header": self.header}
            m = re.search(r'["\']url["\']\s*:\s*["\']([^"\']+)["\']', text) or re.search(r'(https?://[^"\']+\.(?:m3u8|mp4)[^"\']*)', text)
            play = unquote(m.group(1)).replace("\\/", "/") if m else url
            return {"parse": 0, "playUrl": "", "url": play, "header": self.header}
        except Exception as e:
            print(f"[{self.name}] 错误: 播放解析失败 - {e}")
            return {"parse": 1, "playUrl": "", "url": id, "header": self.header}

    def isVideoFormat(self, url):
        return bool(re.search(r"\.(m3u8|mp4|flv|avi|mkv|mov)(\?|$)", str(url), re.I))

    def manualVideoCheck(self):
        return True

    def localProxy(self, param):
        return [200, "video/MP2T", "", ""]

    def destroy(self):
        pass

    def _opts(self, pairs):
        return [{"n": n, "v": v} for n, v in pairs]

    def _category_url(self, tid, pg, ext):
        tid = str(ext.get("cate") or tid)
        area = ext.get("area", "")
        by = ext.get("by", "time") or "time"
        cls = ext.get("class", "")
        year = ext.get("year", "")
        fields = [tid, area, by, cls, "", "", "", "", "" if pg == "1" else pg, "", "", year]
        fields = [quote(str(i), safe="") if i else "" for i in fields]
        return self.host + "/igosw/" + "-".join(fields) + ".html"

    def _text(self, url):
        rsp = self.fetch(url, headers=self.header, timeout=15)
        if hasattr(rsp, "text"):
            return rsp.text
        if isinstance(rsp, dict):
            return rsp.get("content") or rsp.get("text") or ""
        return str(rsp)

    def _html(self, url):
        return etree.HTML(self._text(url))

    def _parse_vods(self, root):
        vods, seen = [], set()
        items = root.xpath('//li[contains(@class,"dx-vod")]')
        if not items:
            items = root.xpath('//a[contains(@href,"/igojs/") and (contains(@class,"cover-area") or .//img)]/..')
        for it in items:
            try:
                data = {}
                raw = self._first(it.xpath("./@data-json"))
                if raw:
                    data = json.loads(html.unescape(raw))
                href = data.get("link") or self._first(it.xpath('.//a[contains(@href,"/igojs/")]/@href'))
                mid = str(data.get("id") or self._first(it.xpath("./@data-id")) or self._id_from_url(href))
                if not mid or mid in seen:
                    continue
                seen.add(mid)
                name = data.get("name") or self._clean(self._first(it.xpath('.//*[contains(@class,"title")]/text()'))) or self._first(it.xpath('.//a[contains(@class,"cover-area")]/@title'))
                pic = data.get("pic") or self._first(it.xpath('.//a[contains(@class,"cover-area")]/@data-original | .//img/@data-original | .//img/@src'))
                remarks = self._clean(self._first(it.xpath('.//*[contains(@class,"vod_remarks")]/text()')))
                if name:
                    vods.append({"vod_id": mid, "vod_name": self._clean(name), "vod_pic": self._fix(pic), "vod_remarks": remarks})
            except Exception as e:
                print(f"[{self.name}] 单条列表解析跳过: {e}")
        return vods

    def _parse_play_lists(self, root):
        tabs = []
        for a in root.xpath('//div[@id="detailPlayNumTab"]//a[contains(@class,"Tab")]'):
            did = self._first(a.xpath("./@data-id"))
            name = self._clean(a.xpath("string(.)"))
            if did and name:
                tabs.append((did, name))
        sources, urls = [], []
        for did, name in tabs:
            divs = root.xpath('//*[@id=$id]', id=did)
            links = divs[0].xpath('.//a[contains(@href,"/igokj/")]') if divs else []
            eps = []
            for a in links:
                ep = self._clean(a.xpath("string(.)")) or "播放"
                href = self._fix(self._first(a.xpath("./@href")))
                if href:
                    eps.append(ep + "$" + href)
            if eps:
                sources.append(name)
                urls.append("#".join(eps))
        if not sources:
            links = root.xpath('//a[contains(@href,"/igokj/")]')
            eps = []
            for a in links:
                ep, href = self._clean(a.xpath("string(.)")), self._fix(self._first(a.xpath("./@href")))
                if ep and href:
                    eps.append(ep + "$" + href)
            if eps:
                sources.append("在线播放")
                urls.append("#".join(eps))
        return "$$$".join(sources), "$$$".join(urls)

    def _info_by_label(self, root, label):
        nodes = root.xpath(f'//div[contains(@class,"info-items")][contains(string(label),"{label}")]')
        if not nodes:
            return ""
        return self._clean(" ".join(nodes[0].xpath('.//*[not(self::label)]/text()')))

    def _page_info(self, root, count, pg):
        text = self._clean(root.xpath('string(//*[contains(@class,"page") or contains(@class,"pagination")])'))
        m = re.search(r"/(\d+)页", text)
        total_m = re.search(r"共(\d+)条", etree.tostring(root, encoding="unicode"))
        pagecount = int(m.group(1)) if m else max(int(pg), 1)
        total = int(total_m.group(1)) if total_m else pagecount * max(count, 1)
        return pagecount, total

    def _meta_desc(self, root):
        return self._clean(self._first(root.xpath('//meta[@name="description"]/@content')))

    def _id_from_url(self, url):
        m = re.search(r"/igojs/(\d+)\.html", str(url))
        return m.group(1) if m else ""

    def _fix(self, url):
        url = (url or "").strip()
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        return urljoin(self.host, url)

    def _clean(self, text):
        return re.sub(r"\s+", " ", str(text or "")).strip(" /　\t\r\n")

    def _first(self, arr):
        return arr[0] if arr else ""
