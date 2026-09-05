import json, requests
from urllib.parse import quote
from base.spider import Spider

class Spider(Spider):
    def getName(self):
        return "艾旦影视"

    def init(self, extend=""):
        self.host = "https://www.lovedan.net"
        self.api = self.host + "/api.php/provide/vod/"
        self.headers = {"User-Agent": "Mozilla/5.0", "Referer": self.host + "/"}
        self.class_order = ["6","7","8","9","10","11","12","20","21","22","70","69","13","14","15","16","30","63","31","23","24","25","71","26","27","28","29","64","17","18","37","65","66","67","68"]
        self.block_ids = set(["1","2","3","4","5","32","33","34","35","36","38","39","40","41","42","43","44","45","46","47","48","49","50","51","52","53","54","55","56","57","58","59","60","61","62"])
        self.block_names = ["电影","电视剧","综艺","动漫","福利视频","明星","福利图片","爱蜜社","头条女神","美媛馆","嗲囡囡","波萝社","魅妍社","爱尤物","秀人网","尤果网","推女神","DGC套图","尤蜜荟","模范学院","尤物馆","优星馆","蜜桃社","影私荟","顽味生活","星乐园","花の颜","御女郎","糖果画报","花漾","星颜社","画语界","直播","央视","卫视"]

    def _get(self, url):
        r = requests.get(url, headers=self.headers, timeout=10)
        r.encoding = "utf-8"
        return r.json()

    def _fix(self, url):
        url = url or ""
        return self.host + url if url.startswith("/") else "https:" + url if url.startswith("//") else url

    def _pic(self, item):
        p = item.get("vod_pic") or item.get("vod_pic_thumb") or item.get("vod_pic_slide") or item.get("vod_pic_screenshot") or ""
        return self._fix(p)

    def _vod(self, item):
        pic = self._pic(item)
        return {"vod_id": str(item.get("vod_id", "")), "vod_name": item.get("vod_name", ""), "vod_pic": pic, "vod_pic_thumb": pic, "vod_remarks": item.get("vod_remarks", "")}

    def _ok(self, item):
        cid = str(item.get("type_id", ""))
        tname = item.get("type_name", "")
        vclass = item.get("vod_class", "")
        return cid not in self.block_ids and tname not in self.block_names and vclass not in self.block_names

    def _classes(self, classes):
        mp = {str(i.get("type_id", "")): i.get("type_name", "") for i in classes}
        arr = [{"type_id": i, "type_name": mp[i]} for i in self.class_order if i in mp and i not in self.block_ids]
        used = set([i["type_id"] for i in arr])
        arr += [{"type_id": str(i.get("type_id", "")), "type_name": i.get("type_name", "")} for i in classes if str(i.get("type_id", "")) not in used and str(i.get("type_id", "")) not in self.block_ids and i.get("type_name", "") not in self.block_names]
        return arr

    def homeContent(self, filter):
        data = self._get(self.api + "?ac=list")
        return {"class": self._classes(data.get("class", [])), "list": []}

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        data = self._get(f"{self.api}?ac=detail&t={tid}&pg={pg}")
        items = [i for i in data.get("list", []) if self._ok(i)]
        exact = [i for i in items if str(i.get("type_id", "")) == str(tid)]
        arr = exact if exact else items
        return {"page": int(data.get("page", pg)), "pagecount": int(data.get("pagecount", 1)), "limit": int(data.get("limit", 20)), "total": int(data.get("total", 0)), "list": [self._vod(i) for i in arr]}

    def detailContent(self, ids):
        data = self._get(f"{self.api}?ac=detail&ids={ids[0]}")
        arr = data.get("list", [])
        if arr:
            pic = self._pic(arr[0])
            arr[0]["vod_pic"] = pic
            arr[0]["vod_pic_thumb"] = pic
        return {"list": arr}

    def searchContent(self, key, quick, pg="1"):
        data = self._get(f"{self.api}?ac=detail&wd={quote(key)}&pg={pg}")
        return {"list": [self._vod(i) for i in data.get("list", []) if self._ok(i)]}

    def playerContent(self, flag, id, vipFlags):
        return {"parse": 0, "url": self._fix(id), "header": json.dumps(self.headers)}