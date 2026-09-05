import sys
import re
import json
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from base.spider import Spider

class Spider(Spider):
    def getName(self):
        return "TOPTV"

    def init(self, extend=""):
        super().init(extend)
        self.site_url = "https://toptv15.cyou"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.site_url
        }
        self.sess = requests.Session()
        self.sess.mount("https://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1)))

    def fetch(self, url, timeout=10):
        try:
            res = self.sess.get(url, headers=self.headers, timeout=timeout, verify=False)
            res.encoding = "utf-8"
            return res
        except:
            return None

    def homeContent(self, filter):
        cate_list = [
            {"type_name": "国产自拍", "type_id": "1"},
            {"type_name": "国产传媒", "type_id": "2"},
            {"type_name": "探花系列", "type_id": "3"},
            {"type_name": "人妻熟女", "type_id": "4"},
            {"type_name": "日本无码", "type_id": "5"},
            {"type_name": "美乳巨乳", "type_id": "6"},
            {"type_name": "强制侵犯", "type_id": "7"},
            {"type_name": "制服诱惑", "type_id": "8"},
            {"type_name": "绝色佳人", "type_id": "9"},
            {"type_name": "家庭乱伦", "type_id": "10"},
            {"type_name": "绝顶潮吹", "type_id": "11"},
            {"type_name": "网红主播", "type_id": "12"}
        ]
        return {"class": cate_list}

    def categoryContent(self, tid, pg, filter, extend):
        if not hasattr(self, 'site_url'): self.init()
        pg = int(pg) if str(pg).isdigit() else 1
        list_url = f"{self.site_url}/index.php/vod/type/id/{tid}/page/{pg}.html"
        res = self.fetch(list_url)
        video_list = []
        if res:
            pattern = r'href="(/index.php/vod/detail/id/(\d+).html)".*?data-original="(.*?)".*?vod-name.*?>(.*?)<'
            matches = re.findall(pattern, res.text, re.S)
            for href, v_id, pic, name in matches:
                video_list.append({
                    "vod_id": v_id,
                    "vod_name": name.strip(),
                    "vod_pic": pic if pic.startswith("http") else self.site_url + pic,
                    "vod_remarks": ""
                })
        return {'list': video_list, 'page': pg, 'pagecount': 999, 'limit': 20, 'total': 9999}

    def detailContent(self, ids):
        if not hasattr(self, 'site_url'): self.init()
        vod_id = ids[0]
        res = self.fetch(f"{self.site_url}/index.php/vod/detail/id/{vod_id}.html")
        if not res: return {}
        html = res.text
        name_match = re.search(r'vod-name.*?>(.*?)<', html) or re.search(r'title-box.*?>(.*?)<', html)
        pic_match = re.search(r'detail-pic.*?src="(.*?)"', html) or re.search(r'data-original="(.*?)"', html)
        
        play_matches = re.findall(r'href="(/index.php/vod/play/id/(\d+)/sid/(\d+)/nid/(\d+).html)">(.*?)<', html)
        play_urls = []
        for m in play_matches:
            play_urls.append(f"{m[4]}${m[1]}-{m[2]}-{m[3]}")
        
        if not play_urls:
            play_urls.append(f"立即播放${vod_id}-1-1")

        vod = {
            "vod_id": vod_id,
            "vod_name": name_match.group(1).strip() if name_match else "视频详情",
            "vod_pic": pic_match.group(1) if pic_match else "",
            "vod_play_from": "TOP-TV",
            "vod_play_url": "#".join(play_urls)
        }
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags):
        if not hasattr(self, 'site_url'): self.init()
        parts = id.split('-')
        if len(parts) == 3:
            v_id, s_id, n_id = parts
            play_url = f"{self.site_url}/index.php/vod/play/id/{v_id}/sid/{s_id}/nid/{n_id}.html"
        else:
            play_url = f"{self.site_url}/index.php/vod/play/id/{id}.html"
        res = self.fetch(play_url)
        if res:
            data_json = re.search(r'var player_aaaa=(.*?)</script>', res.text)
            if data_json:
                try:
                    url = json.loads(data_json.group(1)).get("url", "")
                    return {"parse": 0, "url": url, "header": self.headers}
                except:
                    pass
        return {"parse": 1, "url": play_url}

    def searchContent(self, key, quick, pg=1):
        if not hasattr(self, 'site_url'): self.init()
        res = self.fetch(f"{self.site_url}/index.php/vod/search/page/{pg}/wd/{key}.html")
        video_list = []
        if res:
            pattern = r'href="(/index.php/vod/detail/id/(\d+).html)".*?data-original="(.*?)".*?vod-name.*?>(.*?)<'
            matches = re.findall(pattern, res.text, re.S)
            for href, v_id, pic, name in matches:
                video_list.append({
                    "vod_id": v_id,
                    "vod_name": name.strip(),
                    "vod_pic": pic if pic.startswith("http") else self.site_url + pic
                })
        return {"list": video_list}
