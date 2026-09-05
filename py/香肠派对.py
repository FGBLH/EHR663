# -*- coding: utf-8 -*-
import re
import json
import urllib.parse
from urllib.parse import urljoin, quote
import sys
sys.path.append('..')
from base.spider import Spider
from bs4 import BeautifulSoup

class Spider(Spider):
    def getName(self):
        return "香肠派对"

    def init(self, extend=""):
        self.host = "https://xiang512.xiang.party/xcpd"
        pass

    def header(self):
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
            'Referer': self.host
        }

    def homeContent(self, filter):
        result = {"class": [], "filters": {}, "list": []}
        
        # 分类列表
        classes = [
            {"type_id": "1", "type_name": "在线看片"},
            {"type_id": "2", "type_name": "无需等待"},
            {"type_id": "3", "type_name": "不用下载"},
            {"type_id": "4", "type_name": "全部免费"}
        ]
        result["class"] = classes
        
        # 获取首页视频
        url = f"{self.host}/"
        rsp = self.fetch(url, headers=self.header())
        if rsp.status_code != 200:
            return result
        
        root = BeautifulSoup(rsp.text, 'html.parser')
        videos = []
        
        # 查找视频列表
        items = root.select('ul.thumbnail-group.clearfix li')
        for item in items:
            try:
                a = item.select_one('a.thumbnail')
                if not a:
                    continue
                href = a.get('href', '')
                vod_id = re.search(r'/vod(?:detail|play)/(\d+)', href)
                if not vod_id:
                    continue
                vod_id = vod_id.group(1)
                
                img = a.select_one('img')
                pic = img.get('src', '') if img else ''
                
                info = item.select_one('.video-info')
                if info:
                    h5 = info.select_one('h5 a')
                    name = h5.get('title', '') if h5 else ''
                    if not name:
                        name = h5.text.strip() if h5 else ''
                    p = info.select_one('p')
                    remarks = p.text.strip() if p else ''
                else:
                    name = a.get('title', '')
                    remarks = ''
                
                videos.append({
                    "vod_id": vod_id,
                    "vod_name": name,
                    "vod_pic": pic,
                    "vod_remarks": remarks
                })
                if len(videos) >= 20:
                    break
            except:
                continue
        
        result["list"] = videos
        return result

    def homeVideoContent(self):
        return self.homeContent(False)

    def categoryContent(self, tid, pg, filter, extend):
        p = int(pg)
        # 修复分页URL格式
        url = f"{self.host}/vodtype/{tid}-{p}.html"
        rsp = self.fetch(url, headers=self.header())
        if rsp.status_code != 200:
            return {"list": [], "page": p, "pagecount": 1}
        
        root = BeautifulSoup(rsp.text, 'html.parser')
        videos = []
        
        # 提取总页数（从“共XX条数据,当前X/913页”）
        pagecount = p
        page_info = root.find(string=re.compile(r'共\d+条数据,当前\d+/(\d+)页'))
        if page_info:
            try:
                pagecount = int(re.search(r'/(\d+)页', page_info).group(1))
            except:
                pass
        
        # 提取视频列表
        items = root.select('ul.thumbnail-group.clearfix li')
        for item in items:
            try:
                a = item.select_one('a.thumbnail')
                if not a:
                    continue
                href = a.get('href', '')
                vod_id = re.search(r'/vod(?:detail|play)/(\d+)', href)
                if not vod_id:
                    continue
                vod_id = vod_id.group(1)
                
                img = a.select_one('img')
                pic = img.get('src', '') if img else ''
                
                info = item.select_one('.video-info')
                if info:
                    h5 = info.select_one('h5 a')
                    name = h5.get('title', '') if h5 else ''
                    if not name:
                        name = h5.text.strip() if h5 else ''
                    p_elem = info.select_one('p')
                    remarks = p_elem.text.strip() if p_elem else ''
                else:
                    name = a.get('title', '')
                    remarks = ''
                
                videos.append({
                    "vod_id": vod_id,
                    "vod_name": name,
                    "vod_pic": pic,
                    "vod_remarks": remarks
                })
            except:
                continue
        
        return {
            "list": videos,
            "page": p,
            "pagecount": pagecount
        }

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) else ids.split(",")[0]
        url = f"{self.host}/voddetail/{vid}.html"
        rsp = self.fetch(url, headers=self.header())
        if rsp.status_code != 200:
            return {"list": []}
        
        root = BeautifulSoup(rsp.text, 'html.parser')
        
        # 标题
        title = ""
        h1 = root.select_one('h1.appel-title')
        if h1:
            title = h1.text.strip()
        if not title:
            title_elem = root.select_one('title')
            if title_elem:
                title = title_elem.text.replace('视频介绍--香肠派对', '').strip()
        
        # 图片
        pic = ""
        img = root.select_one('img.appel-img')
        if img:
            pic = img.get('src', '')
        if not pic:
            img = root.select_one('.detail-poster img')
            if img:
                pic = img.get('src', '')
        
        # 描述
        desc = ""
        desc_elem = root.select_one('.detail-content')
        if desc_elem:
            desc = desc_elem.text.strip()
        if not desc:
            desc_elem = root.select_one('.appel-content')
            if desc_elem:
                desc = desc_elem.text.strip()
        
        # 播放列表
        play_from_list = []
        play_url_list = []
        
        # 查找线路
        tabs = root.select('.detail-tab li a')
        play_blocks = root.select('ul.detail-play-list')
        
        for i, block in enumerate(play_blocks):
            line_name = tabs[i].text.strip() if i < len(tabs) else f"线路{i+1}"
            urls = []
            for a in block.select('a'):
                href = a.get('href', '')
                if href:
                    full_url = urljoin(self.host, href)
                    name = a.text.strip() or f"第{len(urls)+1}集"
                    urls.append(f"{name}${full_url}")
            if urls:
                play_from_list.append(line_name)
                play_url_list.append("#".join(urls))
        
        # 如果没有找到，尝试其他选择器
        if not play_from_list:
            lines = root.select('.ff-playurl-tab li a')
            for i, block in enumerate(root.select('.ff-playurl-tab-pane')):
                line_name = lines[i].text.strip() if i < len(lines) else f"线路{i+1}"
                urls = []
                for a in block.select('a'):
                    href = a.get('href', '')
                    if href:
                        full_url = urljoin(self.host, href)
                        name = a.text.strip() or f"第{len(urls)+1}集"
                        urls.append(f"{name}${full_url}")
                if urls:
                    play_from_list.append(line_name)
                    play_url_list.append("#".join(urls))
        
        vod_play_from = "$$$".join(play_from_list) if play_from_list else ""
        vod_play_url = "$$$".join(play_url_list) if play_url_list else ""
        
        return {"list": [{
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_content": desc,
            "vod_play_from": vod_play_from,
            "vod_play_url": vod_play_url
        }]}

    def searchContent(self, key, quick, pg="1"):
        p = int(pg)
        url = f"{self.host}/vodsearch/-------------.html?wd={quote(key)}&page={p}"
        rsp = self.fetch(url, headers=self.header())
        if rsp.status_code != 200:
            return {"list": []}
        
        root = BeautifulSoup(rsp.text, 'html.parser')
        videos = []
        
        items = root.select('ul.thumbnail-group.clearfix li')
        for item in items:
            try:
                a = item.select_one('a.thumbnail')
                if not a:
                    continue
                href = a.get('href', '')
                vod_id = re.search(r'/vod(?:detail|play)/(\d+)', href)
                if not vod_id:
                    continue
                vod_id = vod_id.group(1)
                
                img = a.select_one('img')
                pic = img.get('src', '') if img else ''
                
                info = item.select_one('.video-info')
                if info:
                    h5 = info.select_one('h5 a')
                    name = h5.get('title', '') if h5 else ''
                    if not name:
                        name = h5.text.strip() if h5 else ''
                    p_elem = info.select_one('p')
                    remarks = p_elem.text.strip() if p_elem else ''
                else:
                    name = a.get('title', '')
                    remarks = ''
                
                videos.append({
                    "vod_id": vod_id,
                    "vod_name": name,
                    "vod_pic": pic,
                    "vod_remarks": remarks
                })
            except:
                continue
        
        return {"list": videos, "page": p}

    def playerContent(self, flag, id, vipFlags):
        # 构建播放页URL
        if id.startswith('http'):
            play_url = id
        else:
            play_url = urljoin(self.host, id)
        
        rsp = self.fetch(play_url, headers=self.header())
        if rsp.status_code != 200:
            return {"parse": 0, "playUrl": play_url}
        
        html = rsp.text
        
        # 方法1：从 player_aaaa 提取
        match = re.search(r'var player_aaaa\s*=\s*({.*?});', html, re.DOTALL)
        if match:
            try:
                js_str = match.group(1)
                js_str = re.sub(r'(\w+):', r'"\1":', js_str)
                player_data = json.loads(js_str)
                if player_data.get('url'):
                    return {"parse": 0, "playUrl": player_data['url']}
            except:
                pass
        
        # 方法2：从 iframe 提取（关键修复）
        # 匹配 id="playleft" 的 td 中的 iframe
        iframe_match = re.search(r'<td[^>]*id="playleft"[^>]*>.*?<iframe[^>]+src="([^"]+)"', html, re.DOTALL)
        if iframe_match:
            iframe_url = iframe_match.group(1)
            # 提取 url 参数
            m3u8_match = re.search(r'[?&]url=([^&]+)', iframe_url)
            if m3u8_match:
                m3u8_url = urllib.parse.unquote(m3u8_match.group(1))
                return {"parse": 0, "playUrl": m3u8_url}
            # 如果 iframe 本身就是 m3u8
            if '.m3u8' in iframe_url:
                return {"parse": 0, "playUrl": iframe_url}
        
        # 方法3：直接查找 iframe
        iframe_match2 = re.search(r'<iframe[^>]+src="([^"]+)"', html)
        if iframe_match2:
            iframe_url = iframe_match2.group(1)
            m3u8_match = re.search(r'[?&]url=([^&]+)', iframe_url)
            if m3u8_match:
                m3u8_url = urllib.parse.unquote(m3u8_match.group(1))
                return {"parse": 0, "playUrl": m3u8_url}
        
        # 方法4：直接查找 m3u8
        m3u8 = re.search(r'https?://[^"\']+\.m3u8[^"\']*', html)
        if m3u8:
            return {"parse": 0, "playUrl": m3u8.group(0)}
        
        # 方法5：让系统解析
        return {"parse": 1, "url": play_url}

    def localProxy(self, params):
        return [200, "video/MP2T", ""]
