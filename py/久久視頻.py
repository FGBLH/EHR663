# coding=utf-8
import sys
import os
import re
import json
import urllib.parse
from base.spider import Spider
from bs4 import BeautifulSoup

class Spider(Spider):
    def getName(self):
        return "\u4e45\u4e45\u7f51"
    
    def init(self, extend=""):
        self.host = "https://ww.jiujiu.one"
        print(f"Initialized with host: {self.host}")
    
    def header(self):
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': self.host,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
    
    def homeContent(self, filter):
        """\u8fd4\u56de\u5206\u7c7b\u5217\u8868"""
        result = {}
        classes = [
            {"type_name": "亞洲無碼", "type_id": "68"},
            {"type_name": "日本女優", "type_id": "67"},
            {"type_name": "日本無碼", "type_id": "23"},
            {"type_name": "中文字幕", "type_id": "9"},
            {"type_name": "日本有碼", "type_id": "24"},
            {"type_name": "日韓無碼", "type_id": "82"},
            {"type_name": "無碼專區", "type_id": "113"},
            {"type_name": "AV明星", "type_id": "78"},
            {"type_name": "倫理影片", "type_id": "269"},
            {"type_name": "日本片商", "type_id": "90"},
            {"type_name": "國產自拍", "type_id": "80"},
            {"type_name": "傳媒原創", "type_id": "231"},
            {"type_name": "國產精品", "type_id": "63"},
            {"type_name": "國產情色", "type_id": "77"},
            {"type_name": "美女主播", "type_id": "105"},
            {"type_name": "強姦亂倫", "type_id": "33"},
            {"type_name": "國產主播", "type_id": "36"},
            {"type_name": "亞洲有碼", "type_id": "66"},
            {"type_name": "偷拍自拍", "type_id": "3"},
            {"type_name": "抖陰視頻", "type_id": "91"},
            {"type_name": "制服誘惑", "type_id": "31"},
            {"type_name": "黑料不打烊", "type_id": "10"},
            {"type_name": "歐美精品", "type_id": "25"},
        ]
        result["class"] = classes
        result["list"] = []
        return result
    
    def homeVideoContent(self):
        """\u9996\u9875\u63a8\u8350\u89c6\u9891"""
        try:
            print("Fetching home page...")
            rsp = self.fetch(self.host, headers=self.header())
            print(f"Response status: {rsp.status}")
            
            # \u4f7f\u7528\u6b63\u5219\u8865\u6551\u65b9\u6848\uff0c\u76f4\u63a5\u4eceHTML\u4e2d\u63d0\u53d6\u89c6\u9891\u4fe1\u606f
            html = rsp.text
            
            # \u5339\u914d\u89c6\u9891\u9879\u6a21\u5f0f
            # \u67e5\u627e\u6240\u6709 div.item
            videos = []
            
            # \u4f7f\u7528BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            
            # \u76f4\u63a5\u67e5\u627e\u6240\u6709\u5e26\u6709\u89c6\u9891\u7684\u5361\u7247
            items = soup.find_all('div', class_=lambda c: c and 'item' in c.split())
            print(f"Found {len(items)} items with class containing 'item'")
            
            for item in items:
                try:
                    # \u627e\u5230\u94fe\u63a5
                    links = item.find_all('a', href=True)
                    if len(links) < 2:
                        continue
                    
                    # \u6807\u9898\u94fe\u63a5\u901a\u5e38\u662f\u7b2c\u4e8c\u4e2a
                    title_link = links[1] if len(links) > 1 else links[0]
                    href = title_link.get('href', '')
                    
                    if not href:
                        continue
                    
                    # \u6784\u5efa\u5b8c\u6574\u7684URL
                    if href.startswith('/'):
                        vod_id = self.host + href
                    else:
                        vod_id = href
                    
                    # \u6807\u9898
                    vod_name = title_link.get_text(strip=True)
                    
                    # \u5c01\u9762\u56fe
                    vod_pic = ''
                    img = item.find('img')
                    if img:
                        vod_pic = img.get('src') or img.get('data-src') or ''
                        if vod_pic and not vod_pic.startswith('http'):
                            if vod_pic.startswith('/'):
                                vod_pic = self.host + vod_pic
                            else:
                                vod_pic = 'https:' + vod_pic if vod_pic.startswith('//') else vod_pic
                    
                    # \u5907\u6ce8
                    vod_remarks = ''
                    badge = item.find('span', class_='badge')
                    if badge:
                        vod_remarks = badge.get_text(strip=True)
                    
                    if vod_name and vod_id:
                        videos.append({
                            'vod_id': vod_id,
                            'vod_name': vod_name,
                            'vod_pic': vod_pic,
                            'vod_remarks': vod_remarks
                        })
                        print(f"Added video: {vod_name}")
                except Exception as e:
                    print(f"Error processing item: {e}")
                    continue
            
            print(f"Total videos extracted: {len(videos)}")
            return {'list': videos}
        except Exception as e:
            print(f"Error in homeVideoContent: {e}")
            return {'list': []}
    
    def categoryContent(self, tid, pg, filter, extend):
        """\u5206\u7c7b\u9875\u5185\u5bb9"""
        try:
            # \u6784\u5efa\u5206\u7c7b\u9875URL\uff0c\u652f\u6301\u5206\u9875
            if pg == "1":
                url = f"{self.host}/c/{tid}"
            else:
                url = f"{self.host}/c/{tid}?page={pg}"
            
            print(f"Fetching category URL: {url}")
            rsp = self.fetch(url, headers=self.header())
            soup = BeautifulSoup(rsp.text, 'html.parser')
            videos = []
            
            items = soup.find_all('div', class_=lambda c: c and 'item' in c.split())
            
            for item in items:
                try:
                    links = item.find_all('a', href=True)
                    if len(links) < 2:
                        continue
                    
                    title_link = links[1] if len(links) > 1 else links[0]
                    href = title_link.get('href', '')
                    
                    if not href:
                        continue
                    
                    if href.startswith('/'):
                        vod_id = self.host + href
                    else:
                        vod_id = href
                    
                    vod_name = title_link.get_text(strip=True)
                    
                    vod_pic = ''
                    img = item.find('img')
                    if img:
                        vod_pic = img.get('src') or img.get('data-src') or ''
                        if vod_pic and not vod_pic.startswith('http'):
                            if vod_pic.startswith('/'):
                                vod_pic = self.host + vod_pic
                            else:
                                vod_pic = 'https:' + vod_pic if vod_pic.startswith('//') else vod_pic
                    
                    vod_remarks = ''
                    badge = item.find('span', class_='badge')
                    if badge:
                        vod_remarks = badge.get_text(strip=True)
                    
                    if vod_name and vod_id:
                        videos.append({
                            'vod_id': vod_id,
                            'vod_name': vod_name,
                            'vod_pic': vod_pic,
                            'vod_remarks': vod_remarks
                        })
                except Exception as e:
                    print(f"Error processing item: {e}")
                    continue
            
            # \u83b7\u53d6\u603b\u9875\u6570
            total_pages = 1
            pagination = soup.find('ul', class_='pagination')
            if pagination:
                page_links = pagination.find_all('a')
                for link in page_links:
                    text = link.get_text(strip=True)
                    if text.isdigit():
                        page_num = int(text)
                        if page_num > total_pages:
                            total_pages = page_num
            
            return {
                'list': videos,
                'page': int(pg),
                'pagecount': total_pages,
                'limit': len(videos),
                'total': total_pages * len(videos) if total_pages > 0 else len(videos)
            }
        except Exception as e:
            print(f"Error in categoryContent: {e}")
            return {'list': [], 'page': int(pg), 'pagecount': 1, 'limit': 0, 'total': 0}
    
    def detailContent(self, ids):
        """\u8be6\u60c5\u9875\u5185\u5bb9"""
        try:
            vod_id = ids[0]
            if not vod_id.startswith('http'):
                vod_id = self.host + vod_id
            
            print(f"Fetching detail page: {vod_id}")
            rsp = self.fetch(vod_id, headers=self.header())
            soup = BeautifulSoup(rsp.text, 'html.parser')
            
            vod = {
                'vod_id': vod_id,
                'vod_name': '',
                'vod_pic': '',
                'vod_actor': '',
                'vod_director': '',
                'vod_content': '',
                'vod_play_from': '\u4e45\u4e45\u7f51',
                'vod_play_url': ''
            }
            
            # \u6807\u9898
            title = soup.find('h1')
            if title:
                vod['vod_name'] = title.get_text(strip=True)
            
            # \u5c01\u9762
            img = soup.find('meta', property='og:image')
            if img and img.get('content'):
                vod['vod_pic'] = img.get('content')
            else:
                img = soup.find('img', class_='card-img-top')
                if img:
                    vod['vod_pic'] = img.get('src') or ''
            
            # \u64ad\u653e\u5730\u5740 - \u67e5\u627evideo\u6807\u7b64\u6216iframe
            play_url = ''
            video = soup.find('video')
            if video:
                source = video.find('source')
                if source and source.get('src'):
                    play_url = source.get('src')
            
            if not play_url:
                iframe = soup.find('iframe')
                if iframe and iframe.get('src'):
                    play_url = iframe.get('src')
            
            if play_url:
                vod['vod_play_url'] = f'\u6b63\u7247${play_url}'
            
            return {'list': [vod]}
        except Exception as e:
            print(f"Error in detailContent: {e}")
            return {'list': []}
    
    def searchContent(self, key, quick, pg=1):
        """\u641c\u7d22\u529f\u80fd"""
        try:
            search_url = f"{self.host}/node/search?q={urllib.parse.quote(keyword)}"
            print(f"Search URL: {search_url}")
            rsp = self.fetch(search_url, headers=self.header())
            soup = BeautifulSoup(rsp.text, 'html.parser')
            videos = []
            
            items = soup.find_all('div', class_=lambda c: c and 'item' in c.split())
            
            for item in items:
                try:
                    links = item.find_all('a', href=True)
                    if len(links) < 2:
                        continue
                    
                    title_link = links[1] if len(links) > 1 else links[0]
                    href = title_link.get('href', '')
                    
                    if not href:
                        continue
                    
                    if href.startswith('/'):
                        vod_id = self.host + href
                    else:
                        vod_id = href
                    
                    vod_name = title_link.get_text(strip=True)
                    
                    vod_pic = ''
                    img = item.find('img')
                    if img:
                        vod_pic = img.get('src') or img.get('data-src') or ''
                        if vod_pic and not vod_pic.startswith('http'):
                            if vod_pic.startswith('/'):
                                vod_pic = self.host + vod_pic
                            else:
                                vod_pic = 'https:' + vod_pic if vod_pic.startswith('//') else vod_pic
                    
                    vod_remarks = ''
                    badge = item.find('span', class_='badge')
                    if badge:
                        vod_remarks = badge.get_text(strip=True)
                    
                    if vod_name and vod_id:
                        videos.append({
                            'vod_id': vod_id,
                            'vod_name': vod_name,
                            'vod_pic': vod_pic,
                            'vod_remarks': vod_remarks
                        })
                except Exception as e:
                    print(f"Error processing search item: {e}")
                    continue
            
            return {'list': videos}
        except Exception as e:
            print(f"Error in searchContent: {e}")
            return {'list': []}
    
    def playerContent(self, flag, id, vipFlags):
        """\u8fd4\u56de\u64ad\u653e\u5730\u5740"""
        return {
            'parse': 0,
            'playUrl': '',
            'url': id
        }
    
    def isVideoFormat(self, url):
        """\u5224\u65ad\u662f\u5426\u4e3a\u89c6\u9891\u683c\u5f0f"""
        video_extensions = ['.mp4', '.m3u8', '.flv', '.avi', '.mkv', '.wmv', '.mov']
        lower_url = url.lower()
        for ext in video_extensions:
            if ext in lower_url:
                return True
        return False
    
    def localProxy(self, param):
        return None
    
    def destroy(self):
        pass