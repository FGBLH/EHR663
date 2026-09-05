import sys, re, json, requests
from urllib.parse import quote
from lxml import etree
from base.spider import Spider

class Spider(Spider):
    siteUrl = "https://ys2046.lat"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Referer": "https://ys2046.lat/"}

    def init(self, extend=""):
        self.cateManual = [
            {"name": "电影", "tid": "1", "type": "dianying", "filters": {"class": [{"key": "全部", "value": ""}] + [{"key": k, "value": k} for k in ["喜剧","爱情","动作","恐怖","科幻","剧情","犯罪","奇幻","战争","悬疑","动画","文艺","纪录","传记","歌舞","古装","历史","惊悚","伦理"]], "area": [{"key": "全部", "value": ""}] + [{"key": k, "value": k} for k in ["大陆","香港","台湾","美国","韩国","日本","泰国","新加坡","马来西亚","印度","英国","法国","加拿大","西班牙","俄罗斯","其它"]], "year": [{"key": "全部", "value": ""}] + [{"key": str(y), "value": str(y)} for y in range(2026, 2004, -1)]}},
            {"name": "连续剧", "tid": "2", "type": "lianxuju", "filters": {"class": [{"key": "全部", "value": ""}] + [{"key": k, "value": k} for k in ["喜剧","爱情","动作","恐怖","科幻","剧情","犯罪","奇幻","战争","悬疑","动画","文艺","纪录","传记","歌舞","古装","历史","惊悚","伦理"]], "area": [{"key": "全部", "value": ""}] + [{"key": k, "value": k} for k in ["大陆","香港","台湾","美国","韩国","日本","泰国","新加坡","马来西亚","印度","英国","法国","加拿大","西班牙","俄罗斯","其它"]], "year": [{"key": "全部", "value": ""}] + [{"key": str(y), "value": str(y)} for y in range(2026, 2004, -1)]}},
            {"name": "综艺", "tid": "3", "type": "zongyi", "filters": {"class": [{"key": "全部", "value": ""}] + [{"key": k, "value": k} for k in ["脱口秀","真人秀","搞笑","访谈","生活","音乐","美食","游戏","旅游","时尚","益智","职场","晚会","纪录"]], "area": [{"key": "全部", "value": ""}] + [{"key": k, "value": k} for k in ["大陆","香港","台湾","美国","韩国","日本","英国","其他"]], "year": [{"key": "全部", "value": ""}] + [{"key": str(y), "value": str(y)} for y in range(2026, 2010, -1)]}},
            {"name": "动漫", "tid": "4", "type": "dongman", "filters": {"class": [{"key": "全部", "value": ""}] + [{"key": k, "value": k} for k in ["热血","搞笑","科幻","剧情","冒险","奇幻","战斗","校园","恋爱","治愈","悬疑","推理","机战","运动","美食","历史","少儿"]], "area": [{"key": "全部", "value": ""}] + [{"key": k, "value": k} for k in ["大陆","日本","美国","韩国","法国","英国","其他"]], "year": [{"key": "全部", "value": ""}] + [{"key": str(y), "value": str(y)} for y in range(2026, 2000, -1)]}},
            {"name": "短剧", "tid": "5", "type": "duanju", "filters": {"class": [{"key": "全部", "value": ""}] + [{"key": k, "value": k} for k in ["喜剧","爱情","动作","剧情","悬疑","奇幻","古装","都市","逆袭"]], "area": [{"key": "全部", "value": ""}] + [{"key": k, "value": k} for k in ["大陆","其他"]], "year": [{"key": "全部", "value": ""}] + [{"key": str(y), "value": str(y)} for y in range(2026, 2020, -1)]}},
            {"name": "伦理", "tid": "6", "type": "lunli", "filters": {"class": [{"key": "全部", "value": ""}] + [{"key": k, "value": k} for k in ["剧情","爱情","惊悚"]], "area": [{"key": "全部", "value": ""}] + [{"key": k, "value": k} for k in ["大陆","香港","台湾","美国","法国","日本","韩国"]], "year": [{"key": "全部", "value": ""}] + [{"key": str(y), "value": str(y)} for y in range(2026, 2000, -1)]}},
        ]

    def _get(self, url):
        try: return requests.get(url, headers=self.headers, timeout=10).text
        except: return ""

    def _parse_list(self, html):
        tree = etree.HTML(html)
        return [{"vod_id": m.group(1) if (m := re.search(r'/detail/[\w-]+-(\d+)\.html', a.get("href", ""))) else a.get("href", ""), 
                 "vod_name": t.text.strip() if t.text else "", 
                 "vod_pic": a.get("data-original") or a.get("data-src") or a.get("src") or "", 
                 "vod_remarks": r[0].strip() if (r := li.xpath('.//span[contains(@class,"fed-list-remarks")]/text()')) else ""}
                for li in tree.xpath('//li[contains(@class,"fed-list-item")]')
                for a in li.xpath('.//a[contains(@class,"fed-list-pics")]')
                for t in li.xpath('.//a[contains(@class,"fed-list-title")]')
                if a.get("href") and (a.get("data-original") or a.get("data-src") or a.get("src")) and t.text]

    def homeContent(self, filter):
        return {"class": [{"type_id": c["tid"], "type_name": c["name"]} for c in self.cateManual], 
                "filters": {c["tid"]: c["filters"] for c in self.cateManual}} if filter else {"class": [{"type_id": c["tid"], "type_name": c["name"]} for c in self.cateManual]}

    def homeVideoContent(self):
        return {"list": self._parse_list(self._get(self.siteUrl))}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg)
        cls = extend.get("class", "") if extend else ""
        area = extend.get("area", "") if extend else ""
        year = extend.get("year", "") if extend else ""
        p = f"-{pg}" if pg > 1 else ""
        return {"page": pg, "pagecount": 9999, "limit": 9999, "total": 9999, "list": self._parse_list(self._get(f"{self.siteUrl}/show/{tid}-{cls}--{area}-{year}{p}.html"))}

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) else ids
        cate = next((c for c in self.cateManual if len(html := self._get(f"{self.siteUrl}/detail/{c['type']}-{vid}.html")) > 500), None)
        if not cate: return {}
        tree = etree.HTML(html)
        name = n[0].strip() if (n := tree.xpath('//h1/a/text()')) else ""
        img = i[0] if (i := tree.xpath('//div[contains(@class,"fed-deta-info")]//img/@data-original | //div[contains(@class,"fed-deta")]//img/@data-src | //a[contains(@class,"fed-list-pics")]/@data-original')) else ""
        
        play_btns = tree.xpath('//a[contains(@href,"/play/")]')
        sources = []
        seen_sid = set()
        for a in play_btns:
            if m := re.search(r'/play/[\w-]+-(\d+)-(\d+)\.html', a.get("href", "")):
                sid = m.group(1)
                if sid not in seen_sid:
                    seen_sid.add(sid)
                    sources.append({"name": a.text.strip() if a.text else f"线路{sid}", "sid": sid})
        
        source_names = tree.xpath('//div[contains(@class,"fed-drop-btns")]//a')
        if source_names and len(source_names) == len(sources):
            for i, sn in enumerate(source_names):
                if sn.text and sn.text.strip(): sources[i]["name"] = sn.text.strip()

        parts = []
        for src in sources:
            sid = src["sid"]
            play_tree = etree.HTML(self._get(f"{self.siteUrl}/play/{cate['type']}-{vid}-{sid}-1.html"))
            ep_list = []
            seen_nid = set()
            for ep in play_tree.xpath(f'//a[contains(@href,"-{sid}-")]'):
                if em := re.search(rf'/play/[\w-]+-{sid}-(\d+)\.html', ep.get("href", "")):
                    nid = em.group(1)
                    if nid not in seen_nid:
                        seen_nid.add(nid)
                        ept = ep.text.strip() if ep.text else f"第{nid}集"
                        ep_list.append(f"{ept}${vid}_{sid}_{nid}_{cate['type']}")
            parts.append("#".join(ep_list) if ep_list else f"第1集${vid}_{sid}_1_{cate['type']}")

        return {"vod_id": vid, "vod_name": name, "vod_pic": img, "type_name": cate["name"],
                "vod_year": "", "vod_area": "", "vod_remarks": "", "vod_actor": "", "vod_director": "", "vod_content": "",
                "vod_play_from": "$$$".join([s["name"] for s in sources]), "vod_play_url": "$$$".join(parts)}

    def searchContent(self, key, quick, pg=1):
        pg = int(pg)
        return self._parse_list(self._get(f"{self.siteUrl}/search/{quote(key)}---{pg}.html"))

    def playerContent(self, flag, id, vipFlags):
        parts = id.split("_")
        if len(parts) == 4:
            vid, sid, nid, vtype = parts
            return {"parse": 1, "url": f"{self.siteUrl}/play/{vtype}-{vid}-{sid}-{nid}.html"}
        if len(parts) == 3:
            vid, sid, nid = parts
            for c in self.cateManual:
                url = f"{self.siteUrl}/play/{c['type']}-{vid}-{sid}-{nid}.html"
                if len(self._get(url)) > 500: return {"parse": 1, "url": url}
        return {"parse": 1, "url": id if id.startswith("http") else self.siteUrl + id}