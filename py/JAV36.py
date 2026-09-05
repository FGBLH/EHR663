
import re
import requests

class Spider():
    def getName(self):
        return 'JAV36'

    def init(self, extend=''):
        pass

    def getDependence(self):
        return []

    def homeContent(self, filter):
        return {
            'class': [
                {'type_name': '最新更新', 'type_id': 'latest-updates/'},
                {'type_name': '4K高清', 'type_id': 'tags/4k/'}
                ],
            'list': []
        }

    def homeVideoContent(self):
        return self.categoryContent('latest-updates/', 1, False, {})

    def categoryContent(self, tid, pg, filter, extend):
        url = f'https://jav36.com/{tid}'
        if int(pg) > 1:
            url = f'https://jav36.com/{tid}{pg}/'
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}
        try:
            res = requests.get(url, headers=headers, timeout=15)
            return {'list': self.parse_list(res.text)}
        except: return {'list': []}

    def searchContent(self, keyword, quick, pg=1):
        url = f'https://jav36.com/search/{keyword}/'
        if int(pg) > 1:
            url = f'https://jav36.com/search/{keyword}/{pg}/'
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}
        try:
            res = requests.get(url, headers=headers, timeout=15)
            return {'list': self.parse_list(res.text)}
        except: return {'list': []}

    def parse_list(self, html):
        vod_list = []
        pattern = r'href=\"https://jav36\.com/videos/(?P<id_path>\d+/(?P<id>[^/]+)/)\" title=\"(?P<name>[^\"]+)\".*?data-original=\"(?P<pic>[^\"]+)\"'
        for m in re.finditer(pattern, html, re.S):
            vod_list.append({
                'vod_id': m.group('id_path'),
                'vod_name': m.group('name').strip(),
                'vod_pic': m.group('pic'),
                'vod_remarks': 'Full HD'
            })
        return vod_list

    def detailContent(self, ids):
        return {'list': [{'vod_id': ids[0], 'vod_name': 'Video', 'vod_play_from': 'Direct', 'vod_play_url': 'Play$'+ids[0]}]}

    def playerContent(self, flag, id, vipFlags):
        url = f'https://jav36.com/videos/{id}'
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}
        try:
            res = requests.get(url, headers=headers, timeout=10)
            match = re.search(r'\"contentUrl\"\s*:\s*\"([^\"]+)\"', res.text)
            if match:
                return {'parse': 0, 'url': match.group(1), 'header': {'User-Agent': headers['User-Agent'], 'Referer': 'https://jav36.com/'}}
        except: pass
        return {'parse': 0, 'url': url}
