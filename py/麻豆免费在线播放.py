"""
@header({
  searchable: 1,
  filterable: 0,
  quickSearch: 0,
  title: '麻豆免费在线播放',
  lang: 'hipy'
})
"""

import json, re, sys
from urllib import parse as urlparse
import requests as req
from pyquery import PyQuery as pq
sys.path.append('..')
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):

    def getName(self):
        return self.name

    def init(self, extend='{}'):
        self.debug = False
        self.name = '麻豆免费在线播放'
        self.home_url = 'https://c-you.hair'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36'
        }
        self.extend = extend

    def getDependence(self):
        return []

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def liveContent(self, url):
        return {'list': [], 'code': 0, 'error': 0}

    # ---------- 首页分类 ----------
    def homeContent(self, filterable=False):
        result = {
            'class': [
                {'type_name': '国产精品', 'type_id': '6'},
                {'type_name': '中文字幕', 'type_id': '7'},
                {'type_name': '伦理影片', 'type_id': '8'},
                {'type_name': '自拍偷拍', 'type_id': '9'},
                {'type_name': '口交视频', 'type_id': '10'},
                {'type_name': '日韩无码', 'type_id': '11'},
                {'type_name': '制服诱惑', 'type_id': '12'},
                {'type_name': '国产色情', 'type_id': '13'},
            ],
            'filters': {},
            'list': [],
            'code': 0,
            'error': 0
        }
        return result

    # ---------- 首页推荐 ----------
    def homeVideoContent(self):
        result = {'list': [], 'code': 0, 'error': 0}
        try:
            r = req.get(self.home_url + '/', headers=self.headers, timeout=10)
            r.encoding = 'utf-8'
            doc = pq(r.text)
            items = doc('.col-md-3.resent-grid.recommended-grid')
            for item in items.items():
                a = item('.resent-grid-img a')
                href = a.attr('href') or ''
                title = item('h5 a.title').text().strip()
                img = item('.resent-grid-img img').attr('data-original') or ''
                views = item('.views-info span').text().strip()
                if href and title:
                    result['list'].append({
                        'vod_id': href,
                        'vod_name': title,
                        'vod_pic': img,
                        'vod_remarks': views + '观看' if views else '',
                    })
        except Exception as e:
            print(f'homeVideoContent error: {e}')
        return result

    # ---------- 一级分类列表 ----------
    def categoryContent(self, tid, pg, filterable, extend):
        result = {'list': [], 'page': pg, 'pagecount': pg, 'limit': 90, 'total': 999999, 'code': 0, 'error': 0}
        try:
            if int(pg) <= 1:
                url = f'{self.home_url}/vodtype/{tid}.html'
            else:
                url = f'{self.home_url}/vodtype/{tid}-{pg}.html'
            r = req.get(url, headers=self.headers, timeout=10)
            r.encoding = 'utf-8'
            doc = pq(r.text)
            # 获取总页数
            page_info = doc('.pager .active a').text().strip()
            if '/' in page_info:
                total_pages = page_info.split('/')[-1].strip()
                result['pagecount'] = int(total_pages) if total_pages.isdigit() else pg
            else:
                result['pagecount'] = 9999
            items = doc('.col-md-3.resent-grid.recommended-grid')
            for item in items.items():
                a = item('.resent-grid-img a')
                href = a.attr('href') or ''
                title = item('h5 a.title').text().strip()
                img = item('.resent-grid-img img').attr('data-original') or ''
                views = item('.views-info span').text().strip()
                if href and title:
                    result['list'].append({
                        'vod_id': href,
                        'vod_name': title,
                        'vod_pic': img,
                        'vod_remarks': views + '观看' if views else '',
                    })
        except Exception as e:
            print(f'categoryContent error: {e}')
        return result

    # ---------- 二级详情 ----------
    def detailContent(self, ids):
        result = {'list': [], 'code': 0, 'error': 0}
        try:
            vod_id = ids[0]
            url = self.home_url + vod_id
            r = req.get(url, headers=self.headers, timeout=10)
            r.encoding = 'utf-8'
            doc = pq(r.text)
            title = doc('.song-info h3').text().strip()
            img = doc('.video-grid img').attr('src') or ''
            # 影片介绍块
            info_text = doc('#myList li p').text().strip()
            # 提取发布时间和时长
            pub_time = ''
            duration = ''
            pub_match = re.search(r'发布时间：([\d\-]+)', info_text)
            if pub_match:
                pub_time = pub_match.group(1)
            dur_match = re.search(r'视频时长：(\S+)', info_text)
            if dur_match:
                duration = dur_match.group(1)
            # 分类标签
            category = ''
            cat_match = re.search(r'影片分类：(\S+)', info_text)
            if cat_match:
                category = cat_match.group(1).strip()
            # 简介内容
            content = info_text.split('​')[-1].strip() if '​' in info_text else ''
            if not content:
                # 尝试取最后一行非标签内容
                lines = [l.strip() for l in info_text.split('\n') if l.strip()]
                content = lines[-1] if lines else ''
            # 播放链接
            play_url = doc('a[href*="/vodplay/"]').attr('href') or ''
            play_from = '在线播放'
            play_url_formatted = ''
            if play_url:
                play_from = '在线播放'
                play_url_formatted = f'播放${play_url}'
            result['list'].append({
                'vod_id': vod_id,
                'vod_name': title if title else '',
                'vod_pic': img,
                'type_name': category,
                'vod_year': pub_time[:4] if len(pub_time) >= 4 else '',
                'vod_area': '',
                'vod_actor': '',
                'vod_director': '',
                'vod_remarks': duration,
                'vod_content': content,
                'vod_play_from': play_from,
                'vod_play_url': play_url_formatted,
            })
        except Exception as e:
            print(f'detailContent error: {e}')
        return result

    # ---------- 搜索 ----------
    def searchContent(self, key, quick=False, pg=1):
        result = {'list': [], 'code': 0, 'error': 0}
        try:
            if int(pg) <= 1:
                url = f'{self.home_url}/vodsearch/{urlparse.quote(key)}-------------.html'
            else:
                url = f'{self.home_url}/vodsearch/{urlparse.quote(key)}-------------{pg}---.html'
            r = req.get(url, headers=self.headers, timeout=10)
            r.encoding = 'utf-8'
            doc = pq(r.text)
            items = doc('.col-md-3.resent-grid.recommended-grid')
            for item in items.items():
                a = item('.resent-grid-img a')
                href = a.attr('href') or ''
                title = item('h5 a.title').text().strip()
                img = item('.resent-grid-img img').attr('data-original') or ''
                views = item('.views-info span').text().strip()
                if href and title:
                    result['list'].append({
                        'vod_id': href,
                        'vod_name': title,
                        'vod_pic': img,
                        'vod_remarks': views + '观看' if views else '',
                    })
        except Exception as e:
            print(f'searchContent error: {e}')
        return result

    # ---------- 播放解析 ----------
    def playerContent(self, flag, pid, vipFlags):
        result = {
            'parse': 1,
            'playUrl': '',
            'url': '',
            'header': {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 9_1 like Mac OS X) AppleWebKit/601.1.46 (KHTML, like Gecko) Version/9.0 Mobile/13B143 Safari/601.1'
            }
        }
        try:
            play_url = self.home_url + pid
            r = req.get(play_url, headers=self.headers, timeout=10)
            r.encoding = 'utf-8'
            html = r.text
            # 尝试提取 player_data 或其他已知变量
            player_match = re.search(r'var\s+player_data\s*=\s*({.*?});', html, re.DOTALL)
            if player_match:
                player_json = json.loads(player_match.group(1))
                real_url = player_json.get('url', '')
                if real_url:
                    result['url'] = real_url
                    result['parse'] = 0
                    return result
            # 尝试匹配常见 iframe
            iframe_match = re.search(r'<iframe[^>]+src="([^"]+)"', html)
            if iframe_match:
                result['url'] = iframe_match.group(1)
                result['parse'] = 1
                return result
            # 尝试匹配 video 标签
            video_match = re.search(r'<video[^>]+src="([^"]+)"', html)
            if video_match:
                result['url'] = video_match.group(1)
                result['parse'] = 0
                return result
            # 尝试匹配 source 标签
            source_match = re.search(r'<source[^>]+src="([^"]+)"', html)
            if source_match:
                result['url'] = source_match.group(1)
                result['parse'] = 0
                return result
            # 兜底：嗅探模式，把播放页URL交给壳子嗅探
            result['url'] = play_url
            result['parse'] = 1
        except Exception as e:
            print(f'playerContent error: {e}')
        return result

    def localProxy(self, params):
        return [404, 'text/plain', 'Not Found']

    def destroy(self):
        return '正在Destroy'