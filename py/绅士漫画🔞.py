# -*- coding: utf-8 -*-
import sys, json, re, requests, urllib.parse
from bs4 import BeautifulSoup
sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
    def getName(self): return "绅士漫画"

    def init(self, extend=""):
        self.baseUrl = "https://www.wn03.ru"
        self.session = requests.Session()
        # 核心：保持 PC UA 以获取全量图片数据
        self.ua = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 Edg/132.0.2957.129'
        self.headers = {'User-Agent': self.ua, 'Accept-Language': 'zh-CN,zh;q=0.9', 'Connection': 'keep-alive'}
        self.check_domain()

    def check_domain(self):
        try:
            if self.session.get(self.baseUrl, headers=self.headers, timeout=5).status_code >= 400:
                self.fetch_new_domain()
        except:
            self.fetch_new_domain()

    def fetch_new_domain(self):
        try:
            r = requests.get("https://wnlink.ru/", headers=self.headers, timeout=5)
            urls = re.findall(r'href="(https?://[^"]+)"', r.text)
            for url in urls:
                if "wn" in url and "link" not in url:
                    self.baseUrl = url.rstrip('/')
                    self.session.get(self.baseUrl, headers=self.headers, timeout=5)
                    break
        except: pass

    def get_header(self, url=None):
        h = self.headers.copy()
        h['Referer'] = url if url else self.baseUrl + '/'
        return h

    def homeContent(self, filter):
        classes = [
            {"type_name": x[0], "type_id": x[1]} for x in [
                ("同人/汉化", "1"), ("单行/汉化", "9"), ("短篇/汉化", "10"),
                ("韩漫/汉化", "20"), ("Cosplay", "3"), ("CG画集", "2"), ("3D漫画", "23")
            ]
        ]
        return {"class": classes}

    def homeVideoContent(self): return self.categoryContent("1", "1", None, {})

    def categoryContent(self, tid, pg, filter, extend):
        return self.parse_list(f"{self.baseUrl}/albums-index-page-{pg}-cate-{tid}.html", pg)

    def searchContent(self, key, quick, pg="1"):
        key = urllib.parse.quote(key)
        return self.parse_list(f"{self.baseUrl}/search/?q={key}&f=_all&s=create_time_DESC&p={pg}", pg)

    def parse_list(self, url, pg):
        try:
            r = self.session.get(url, headers=self.get_header(url), timeout=10)
            soup = BeautifulSoup(r.text, 'html.parser')
            # 优先定位主列表
            box = soup.select_one('.gallary_wrap') or soup.select_one('#classify_container')
            items = box.select('li') if box else soup.select('.gallary_item')
            
            videos = []
            for item in items:
                a = item.select_one('a')
                if not a or "page-" in a['href']: continue
                
                title = a.get('title') or a.get_text(strip=True)
                title = re.sub(r'^\s*\[[^\]]+\]|\d{4}-\d{2}-\d{2}.*', '', title).strip()
                
                img = item.select_one('img')
                pic = img.get('src') or img.get('data-src') or ""
                if pic.startswith("//"): pic = "https:" + pic
                
                # --- 修改：兼容繁体“張”和简体“张” ---
                info_text = item.get_text()
                # 匹配：数字 + (张 或 張 或 P)
                count_m = re.search(r'(\d+)\s*[张張P]', info_text) 
                count = count_m.group(1) + "P" if count_m else ""
                
                # 提取日期
                date_m = re.search(r'(\d{4}-\d{2}-\d{2})', info_text)
                date = date_m.group(1) if date_m else ""
                
                # 组合: 2026-01-26 22P
                remark = f"{date} {count}".strip()
                
                videos.append({"vod_id": a['href'], "vod_name": title, "vod_pic": pic, "vod_remarks": remark})
            return {"list": videos, "page": pg, "pagecount": 999, "limit": len(videos), "total": 9999}
        except: return {"list": []}

    def detailContent(self, ids):
        vid = ids[0]
        url = self.baseUrl + vid if vid.startswith('/') else vid
        try:
            # 请求详情页以获取准确标题
            r = self.session.get(url, headers=self.get_header(self.baseUrl), timeout=10)
            r.encoding = 'utf-8'
            soup = BeautifulSoup(r.text, 'html.parser')
            
            h = soup.select_one('h2') or soup.select_one('h1')
            title = h.get_text(strip=True) if h else "未知标题"
            
            img = soup.select_one('.pic_box img')
            cover = img.get('src') if img else ""
            if cover.startswith("//"): cover = "https:" + cover

            # 强制转换为 Gallery 模式以保证图片加载
            play_url = vid.replace("index", "gallery")
            if not play_url.startswith("http"): play_url = self.baseUrl + play_url
            
            return {"list": [{
                "vod_id": vid, "vod_name": title, "vod_pic": cover, "vod_type": "漫画",
                "vod_play_from": "绅士漫画$$$绅士漫画(Manga)",
                "vod_play_url": f"全集${play_url}$$$全集${play_url}"
            }]}
        except:
            return {"list": [{"vod_id": vid, "vod_name": "加载失败", "vod_play_from": "绅士漫画", "vod_play_url": f"全集${url}"}]}

    def playerContent(self, flag, id, vipFlags):
        try:
            r = self.session.get(id, headers=self.get_header(id), timeout=15)
            html = r.text.replace(r'\/', '/') # 核心：反转义
            
            img_list = []
            # 广谱正则提取 + 缩略图还原
            for m in re.findall(r'((?:https?:|//)[^"\'\s<>\[\]{}]+?\.(?:jpg|png|webp|jpeg))', html, re.I):
                url = "https:" + m if m.startswith("//") else m
                if any(x in url.lower() for x in ['logo', 'icon', 'avatar', 'banner', 'button']): continue
                
                # 缩略图还原为大图
                if "thumb" in url.lower():
                    url = url.replace("thumb_", "").replace("_thumb", "")
                
                if url not in img_list: img_list.append(url)
            
            if not img_list: return {"parse": 0, "url": "", "msg": "未找到图片"}
            
            # 根据线路返回不同协议
            protocol = "manga" if "Manga" in flag else "pics"
            return {
                "parse": 0, "playUrl": "",
                "url": f"{protocol}://" + "&&".join(img_list),
                "header": json.dumps(self.get_header(id))
            }
        except Exception as e:
            return {"parse": 0, "url": "", "msg": f"Err:{e}"}

    def localProxy(self, param): pass
