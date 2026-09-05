# coding: utf-8
# 性运机场 - TVBox/FongMi 爬虫
# URL: https://xyjc8.cfd/
# CMS: 苹果CMS (MacCMS)
# 分类数: 24

import re
import json
import urllib.parse
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        super().__init__()
        self.host = 'https://xyjc8.cfd'
        self.site_name = '性运机场'
        
        self.classes = [
            {'type_id': '25', 'type_name': '国产视频'},
            {'type_id': '26', 'type_name': '中文字幕'},
            {'type_id': '27', 'type_name': '国产传媒'},
            {'type_id': '28', 'type_name': '日本有码'},
            {'type_id': '29', 'type_name': '日本无码'},
            {'type_id': '30', 'type_name': '欧美无码'},
            {'type_id': '31', 'type_name': '强奸乱伦'},
            {'type_id': '32', 'type_name': '制服诱惑'},
            {'type_id': '33', 'type_name': '国产主播'},
            {'type_id': '34', 'type_name': '激情动漫'},
            {'type_id': '35', 'type_name': '明星换脸'},
            {'type_id': '36', 'type_name': '抖阴视频'},
            {'type_id': '37', 'type_name': '女优明星'},
            {'type_id': '38', 'type_name': '网曝黑料'},
            {'type_id': '39', 'type_name': '伦理三级'},
            {'type_id': '40', 'type_name': 'AV解说'},
            {'type_id': '41', 'type_name': 'SM调教'},
            {'type_id': '42', 'type_name': '萝莉少女'},
            {'type_id': '43', 'type_name': '极品媚黑'},
            {'type_id': '44', 'type_name': '女同性恋'},
            {'type_id': '45', 'type_name': '网红头条'},
            {'type_id': '46', 'type_name': '人妖系列'},
            {'type_id': '47', 'type_name': '韩国主播'},
            {'type_id': '48', 'type_name': 'VR视角'},
        ]
        
        self.filters = {}
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': self.host + '/',
            'Content-Type': 'application/x-www-form-urlencoded',
        }

    def getName(self):
        return self.site_name

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            url = f'{self.host}/'
            res = self.fetch(url, headers=self.headers)
            if res:
                html = self._get_text(res)
                if html:
                    items = self._parse_list(html)
                    if items:
                        return {"list": items[:20]}
            return {"list": []}
        except Exception:
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = pg or "1"
            tid = str(tid)
            url = f'{self.host}/frim/index{tid}.html'
            if int(page) > 1:
                url = f'{self.host}/frim/index{tid}-{page}.html'
            
            res = self.fetch(url, headers=self.headers)
            if not res:
                return {"list": [], "page": int(page), "pagecount": 0, "limit": 20}
            
            html = self._get_text(res)
            if not html:
                return {"list": [], "page": int(page), "pagecount": 0, "limit": 20}
            
            items = self._parse_list(html)
            total_pages = self._parse_total_pages(html, tid)
            
            return {
                "list": items,
                "page": int(page),
                "pagecount": total_pages or 99,
                "limit": 20,
                "total": 0
            }
        except Exception:
            return {"list": [], "page": int(pg or "1"), "pagecount": 0, "limit": 20}

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        try:
            vid = str(ids[0])
            url = f'{self.host}/movie/index{vid}.html'
            res = self.fetch(url, headers=self.headers)
            if not res:
                return {"list": []}
            html = self._get_text(res)
            if not html:
                return {"list": []}

            title_match = re.search(r'<title>(.*?)在线播放.*?</title>', html, re.S)
            vod_name = title_match.group(1).strip() if title_match else "视频"

            pic_match = re.search(r'<a class="videopic"[^>]*style="background: url\(([^)]+)\)', html)
            vod_pic = pic_match.group(1).strip() if pic_match else ""

            play_url = ""
            start = html.find('var player_aaaa=')
            if start == -1:
                start = html.find('var player_aaaa =')
            if start != -1:
                segment = html[start:start+2000]
                url_match = re.search(r'"url"\s*:\s*"([^"]+)"', segment)
                if url_match:
                    play_url = url_match.group(1).replace('\\/', '/')
                    if 'test.cn' in play_url:
                        play_url = ""

            if not play_url:
                play_res = self.fetch(f'{self.host}/play/{vid}-0-0.html', headers=self.headers)
                if play_res:
                    play_html = self._get_text(play_res)
                    if play_html:
                        now_match = re.search(r'var now="([^"]+)"', play_html)
                        if now_match:
                            play_url = now_match.group(1)

            if play_url and play_url.startswith('http'):
                vod = {
                    "vod_id": vid,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": "",
                    "vod_content": "",
                    "vod_play_from": "直链",
                    "vod_play_url": f"直链${play_url}"
                }
                return {"list": [vod]}
            else:
                vod = {
                    "vod_id": vid,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": "",
                    "vod_content": "",
                    "vod_play_from": "嗅探",
                    "vod_play_url": f"嗅探${url}"
                }
                return {"list": [vod]}
        except Exception:
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        if not key:
            return {"list": [], "page": int(pg)}
        try:
            url = f'{self.host}/search.php'
            headers = self.headers.copy()
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
            data = f'searchword={urllib.parse.quote(key)}'
            res = self.post(url, data=data, headers=headers)
            if not res:
                return {"list": [], "page": int(pg)}
            html = self._get_text(res)
            if not html or '关键字不能为空' in html:
                return {"list": [], "page": int(pg)}
            items = self._parse_list(html)
            return {"list": items, "page": int(pg)}
        except Exception:
            return {"list": [], "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 1, "url": ""}
        if ".m3u8" in id.lower() or ".mp4" in id.lower() or ".m3u" in id.lower():
            return {"parse": 0, "url": id, "header": self.headers}
        if id.startswith(('http://', 'https://')):
            return {"parse": 0, "url": id, "header": self.headers}
        return {"parse": 1, "url": id, "header": self.headers}

    def _get_text(self, res):
        if hasattr(res, 'text'):
            return res.text
        if hasattr(res, 'content'):
            try:
                return res.content.decode('utf-8')
            except:
                return str(res.content)
        if isinstance(res, str):
            return res
        return str(res)

    def _parse_list(self, html):
        items = []
        if not html:
            return items
        
        # 先尝试匹配分类页的卡片结构
        pattern = r'<div class="col-md-2 col-sm-3 col-xs-4[^"]*">.*?<a class="videopic lazy"[^>]*href="([^"]+)"[^>]*title="([^"]*)"[^>]*data-original="([^"]*)"[^>]*>.*?<span class="score">([^<]*)</span>.*?</div>\s*</div>'
        matches = re.findall(pattern, html, re.DOTALL)
        
        if matches:
            for href, title, pic, score in matches:
                if not href or not title:
                    continue
                vid_match = re.search(r'/movie/index(\d+)\.html', href)
                vid = vid_match.group(1) if vid_match else ''
                if vid:
                    items.append({
                        "vod_id": vid,
                        "vod_name": title.strip(),
                        "vod_pic": pic,
                        "vod_remarks": f"{score}分" if score else ""
                    })
            return items
        
        # 搜索结果页的卡片结构：hy-video-details
        pattern2 = r'<div class="hy-video-details active clearfix">.*?<a class="videopic"[^>]*href="([^"]+)"[^>]*style="[^"]*url\(([^)]+)\)[^"]*"[^>]*>.*?<h3><a[^>]*href="[^"]+"[^>]*>([^<]*)</a></h3>.*?<span class="branch">([^<]*)</span>'
        matches2 = re.findall(pattern2, html, re.DOTALL)
        for href, pic, title, score in matches2:
            if not href or not title:
                continue
            vid_match = re.search(r'/movie/index(\d+)\.html', href)
            vid = vid_match.group(1) if vid_match else ''
            if vid:
                items.append({
                    "vod_id": vid,
                    "vod_name": title.strip(),
                    "vod_pic": pic,
                    "vod_remarks": f"{score}分" if score else ""
                })
        
        return items

    def _parse_total_pages(self, html, tid):
        page_match = re.search(r'<a href="[^"]*index' + str(tid) + r'-(\d+)\.html">尾页</a>', html)
        if page_match:
            return int(page_match.group(1))
        
        pages = re.findall(r'<a href="[^"]*index' + str(tid) + r'-(\d+)\.html">(\d+)</a>', html)
        if pages:
            max_p = max(int(p[0]) for p in pages)
            return max_p
        return 1

    def localProxy(self, param):
        return [200, "application/vnd.apple.mpegurl", param.get("data", ""), {}]

    def destroy(self):
        pass