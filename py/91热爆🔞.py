import sys
import json
import requests
from urllib.parse import quote
try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider(object):
        pass

class Spider(BaseSpider):
    site = "https://rb.jnyk08.icu"
    api = "https://api.vuecloudrb.com"
    headers = {"User-Agent": "Mozilla/5.0", "Referer": site + "/", "Origin": site}

    def getName(self):
        return "91热爆"

    def init(self, extend=""):
        self.site = "https://rb.jnyk08.icu"
        self.api = "https://api.vuecloudrb.com"
        self.headers = {"User-Agent": "Mozilla/5.0", "Referer": self.site + "/", "Origin": self.site}

    def isVideoFormat(self, url):
        return True

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return None

    def _ok(self):
        if not hasattr(self, "api"):
            self.init("")

    def _get(self, path, params=None):
        self._ok()
        r = requests.get(self.api + path, headers=self.headers, params=params or {}, timeout=10)
        return r.json()

    def _time(self, s):
        try:
            s = int(s or 0)
            h, m, sec = s // 3600, s % 3600 // 60, s % 60
            return "%02d:%02d:%02d" % (h, m, sec) if h else "%02d:%02d" % (m, sec)
        except Exception:
            return ""

    def _pic(self, i):
        return i.get("video_img") or i.get("screenshot1") or ""

    def _items(self, data):
        if isinstance(data, dict):
            data = data.get("data") or data.get("list_new", {}).get("data") or data.get("list_hot", {}).get("data") or []
        return [{
            "vod_id": str(i.get("video_id") or i.get("id") or ""),
            "vod_name": i.get("title") or i.get("name") or "",
            "vod_pic": self._pic(i),
            "vod_remarks": self._time(i.get("duration", 0))
        } for i in (data or []) if i.get("video_id") or i.get("id")]

    def homeContent(self, filter):
        cls = [{"type_id": "all", "type_name": "推荐"}, {"type_id": "new", "type_name": "最新"}, {"type_id": "hot", "type_name": "热门"}]
        try:
            c = self._get("/videos/classification", {"page": 1, "size": 50, "categories": 0, "sort": "post_date"}).get("content", [])
            cls += [{"type_id": str(i.get("category_id")), "type_name": i.get("title", "")} for i in c if i.get("category_id")]
        except Exception:
            pass
        data = self._get("/videos/index_byall", {"page": 1, "size": 24, "categories": 0, "sort": "post_date"}).get("content", {})
        return {"class": cls, "list": self._items(data.get("list_new", {}))}

    def homeVideoContent(self):
        data = self._get("/videos/index_byall", {"page": 1, "size": 24, "categories": 0, "sort": "post_date"}).get("content", {})
        return {"list": self._items(data.get("list_new", {}))}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        if tid == "all":
            data = self._get("/videos/index", {"page": pg, "size": 24}).get("content", {})
        elif tid == "new":
            data = self._get("/videos/index_byall", {"page": pg, "size": 24, "categories": 0, "sort": "post_date"}).get("content", {}).get("list_new", {})
        elif tid == "hot":
            data = self._get("/videos/index_byall", {"page": pg, "size": 24, "categories": 0, "sort": "video_viewed"}).get("content", {}).get("list_hot", {})
        elif str(tid).startswith("tag_"):
            data = self._get("/videos/list_bytags", {"page": pg, "size": 24, "categories": 0, "sort": "post_date", "tags": str(tid)[4:]}).get("content", {})
        else:
            data = self._get("/videos/index", {"page": pg, "size": 24, "categories": tid, "sort": "post_date"}).get("content", {})
        return {"list": self._items(data), "page": pg, "pagecount": data.get("last_page", pg), "limit": 24, "total": data.get("total", 0)}

    def detailContent(self, ids):
        vid = str(ids[0])
        c = self._get("/videos/detail", {"id": vid}).get("content", {})
        name = c.get("title") or vid
        pic = c.get("video_img") or ""
        tags = ",".join([i.get("tag", "") for i in c.get("tags", []) if isinstance(i, dict)])
        cats = ",".join([i.get("title", "") for i in c.get("categories", []) if isinstance(i, dict)])
        return {"list": [{
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "type_name": cats,
            "vod_year": c.get("post_date", ""),
            "vod_area": "",
            "vod_remarks": self._time(c.get("duration", 0)),
            "vod_actor": tags,
            "vod_director": "",
            "vod_content": name,
            "vod_play_from": "直连",
            "vod_play_url": name + "$" + vid
        }]}

    def searchContent(self, key, quick, pg="1"):
        data = self._get("/videos/search", {"keyword": key, "page": int(pg or 1), "limit": 20}).get("content", {})
        return {"list": self._items(data), "page": int(pg or 1), "pagecount": data.get("last_page", 1), "limit": 20, "total": data.get("total", 0)}

    def searchContentPage(self, key, quick, pg):
        return self.searchContent(key, quick, pg)

    def playerContent(self, flag, id, vipFlags):
        vid = str(id).strip()
        base = str((int(vid) // 1000) * 1000) if vid.isdigit() else vid[:-3] + "000"
        url = "https://delivery.douyinpaly.com/hls/contents/videos/%s/%s/%s.mp4/index.m3u8" % (base, vid, vid)
        return {"parse": 0, "playUrl": "", "url": url, "header": {"User-Agent": "Mozilla/5.0", "Referer": self.site + "/", "Origin": self.site}}

    def localProxy(self, param):
        return None