# -*- coding: utf-8 -*-
# by @6666
import concurrent.futures
import json
import re
import sys
import time
from base64 import b64decode, b64encode
import requests
from pyquery import PyQuery as pq
sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    def init(self, extend=""):
        self.host = "https://vip.wwgz.cn:5200"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
            'Referer': self.host + '/',
            'Accept': 'text/html'
        }
        self.cateConfig = {
            "12": [{"key": "cateId", "name": "类型", "value": [{"n": "国产剧", "v": "12"}]}],
            "4": [{"key": "cateId", "name": "类型", "value": [{"n": "动漫", "v": "4"}]}],
            "1": [{"key": "cateId", "name": "类型", "value": [{"n": "电影", "v": "1"}]}],
            "2": [{"key": "cateId", "name": "类型", "value": [{"n": "电视剧", "v": "2"}]}],
            "3": [{"key": "cateId", "name": "类型", "value": [{"n": "综艺", "v": "3"}]}],
            "26": [{"key": "cateId", "name": "类型", "value": [{"n": "短剧", "v": "26"}]}]
        }
        self.filterConfig = {}

    def getName(self):
        return "农民影视"

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    def homeContent(self, filter):
        result = {}
        classes = [
            {'type_name': '国产剧', 'type_id': '12'},
            {'type_name': '动漫', 'type_id': '4'},
            {'type_name': '电影', 'type_id': '1'},
            {'type_name': '电视剧', 'type_id': '2'},
            {'type_name': '综艺', 'type_id': '3'},
            {'type_name': '短剧', 'type_id': '26'}
        ]
        try:
            data = self.fetch(self.host, headers=self.headers).text
            doc = pq(data)
            videos = []
            # 修改选择器并添加去重逻辑
            seen_ids = set()  # 用于记录已处理的影片ID
            for item in doc('.globalPicList li:has(img)').items():
                vod_id = self.host + item('a').attr('href')
                if vod_id not in seen_ids:  # 检查是否已处理过
                    seen_ids.add(vod_id)  # 记录已处理的ID
                    pic_url = item('img').attr('data-echo') or item('img').attr('data-src') or item('img').attr('src')
                    # 替换图片域名
                    if pic_url and 'pic.lzzypic.com' in pic_url:
                        pic_url = pic_url.replace('https://pic.lzzypic.com', 'https://img.lzzyimg.com')
                    videos.append({
                        'vod_id': vod_id,
                        'vod_name': item('.sTit').text(),
                        'vod_pic': pic_url,
                        'vod_remarks': item('.sBottom').text()
                    })
            result['class'] = classes
            result['filters'] = self.cateConfig
            result['list'] = videos
        except Exception as e:
            print(f"首页数据获取失败: {str(e)}")
            result['class'] = classes
            result['filters'] = self.cateConfig
            result['list'] = []
        return result

    def homeVideoContent(self):
        pass

    def categoryContent(self, tid, pg, filter, extend):
        result = {}
        try:
            if tid == "4-dm":
                # 处理大陆人气动漫分类
                url = "https://www.wwgz.cn/vod-list-id-4-pg-{}-order--by-hits-class-0-year-0-letter--area-大陆-lang-.html".format(pg)
            else:
                cateId = tid
                url = f"{self.host}/vod-list-id-{cateId}-pg-{pg}.html"
                
            data = self.fetch(url, headers=self.headers).text
            doc = pq(data)
            
            videos = []
            for item in doc('.globalPicList li').items():
                pic_url = item('img').attr('data-echo') or item('img').attr('data-src') or item('img').attr('src')
                # 替换图片域名
                if pic_url and 'pic.lzzypic.com' in pic_url:
                    pic_url = pic_url.replace('https://pic.lzzypic.com', 'https://img.lzzyimg.com')
                videos.append({
                    'vod_id': self.host + item('a').attr('href'),
                    'vod_name': item('.sTit').text(),
                    'vod_pic': pic_url,
                    'vod_remarks': item('.sBottom').text()
                })
            
            result['list'] = videos
            result['page'] = pg
            result['pagecount'] = 9999
            result['limit'] = 90
            result['total'] = 999999
        except Exception as e:
            print(f"分类数据获取失败: {str(e)}")
            result['list'] = []
            result['page'] = pg
            result['pagecount'] = 1
            result['limit'] = 90
            result['total'] = 0
        return result

    def detailContent(self, ids):
        result = {}
        try:
            url = ids[0]
            data = self.fetch(url, headers=self.headers).text
            doc = pq(data)
            
            # 获取播放线路和剧集
            play_from = []
            play_url = []
            
            tab_box = doc('#leftTabBox')
            if tab_box:
                for tab in tab_box('ul li').items():
                    play_from.append(tab.text())
                
                play_lists = []
                for num_list in tab_box('.numList').items():
                    episodes = []
                    # 修改这里：将items()转换为列表后反转顺序
                    for ep in list(num_list('li').items())[::-1]:  # 反转列表顺序
                        episodes.append(f"{ep('a').text()}${self.host}{ep('a').attr('href')}")
                    play_lists.append('#'.join(episodes))
                
                play_url = play_lists
            
            # 获取详情信息
            vod = {
                'vod_name': doc('h1 a').text(),
                'vod_year': doc('span:contains("年代：")').text().replace('年代：', ''),
                'vod_area': '',
                'vod_actor': doc('.sDes:contains("主演:")').text().replace('主演:', ''),
                'vod_director': '',
                'vod_content': doc('.detail-con p').text().replace('简介:', ''),
                'vod_play_from': '$$$'.join(play_from),
                'vod_play_url': '$$$'.join(play_url)
            }
            result['list'] = [vod]
        except Exception as e:
            print(f"详情数据获取失败: {str(e)}")
            result['list'] = []
        return result

    def searchContent(self, key, quick, pg="1"):
        result = {}
        try:
            url = f"{self.host}/index.php?m=vod-search"
            data = {'wd': key}
            headers = {
                'User-Agent': self.headers['User-Agent'],
                'Referer': self.host + '/'
            }
            html = self.post(url, data=data, headers=headers).text
            doc = pq(html)
            
            videos = []
            for item in doc('#data_list li').items():
                pic_url = item('.lazyload').attr('data-src')
                # 替换图片域名
                if pic_url and 'pic.lzzypic.com' in pic_url:
                    pic_url = pic_url.replace('https://pic.lzzypic.com', 'https://img.lzzyimg.com')
                videos.append({
                    'vod_id': self.host + item('a').attr('href'),
                    'vod_name': item('.sTit').text(),
                    'vod_pic': pic_url,
                    'vod_remarks': item('.sDes').eq(-1).text()
                })
            
            result['list'] = videos
            result['page'] = pg
        except Exception as e:
            print(f"搜索数据获取失败: {str(e)}")
            result['list'] = []
            result['page'] = pg
        return result

    def playerContent(self, flag, id, vipFlags):
        result = {}
        try:
            if '@' in id:
                ids = id.split('@')
                if not ids[0]:
                    raise Exception('未找到播放地址')
                
                js_url = f"{self.host}/player/{ids[0]}.js"
                js_data = self.fetch(js_url, headers=self.headers).text
                jxurl = re.search(r'http.*?url=', js_data).group()
                
                data = self.fetch(f"{jxurl}{ids[1]}", headers=self.headers).text
                matches = re.findall(r'http.*?url=', data)
                
                if matches:
                    url = []
                    for i, x in enumerate(matches):
                        js = {'jx': x, 'id': ids[1]}
                        purl = f"{self.getProxyUrl()}&wdict={self.e64(json.dumps(js))}"
                        url.extend([f'线路{i + 1}', purl])
                else:
                    url = re.search(r"url='(.*?)'", data).group(1)
                
                if not url:
                    raise Exception('未找到播放地址')
                
                p = 0
            else:
                p, url = 1, id
            
            result['parse'] = p
            result['url'] = url
            result['header'] = self.headers
        except Exception as e:
            print(f"播放数据获取失败: {str(e)}")
            result['parse'] = 1
            result['url'] = id
            result['header'] = self.headers
        return result

    def localProxy(self, param):
        try:
            wdict = json.loads(self.d64(param['wdict']))
            url = f"{wdict['jx']}{wdict['id']}"
            data = self.fetch(url, headers=self.headers).text
            doc = pq(data)
            html = doc('script').eq(-1).text()
            url = re.search(r'src="(.*?)"', html).group(1)
            return [302, 'text/html', None, {'Location': url}]
        except Exception as e:
            print(f"代理处理失败: {str(e)}")
            return [500, 'text/plain', str(e).encode('utf-8')]

    def liveContent(self, url):
        pass

    def e64(self, text):
        try:
            text_bytes = text.encode('utf-8')
            encoded_bytes = b64encode(text_bytes)
            return encoded_bytes.decode('utf-8')
        except Exception as e:
            print(f"Base64编码错误: {str(e)}")
            return ""

    def d64(self, encoded_text):
        try:
            encoded_bytes = encoded_text.encode('utf-8')
            decoded_bytes = b64decode(encoded_bytes)
            return decoded_bytes.decode('utf-8')
        except Exception as e:
            print(f"Base64解码错误: {str(e)}")
            return ""