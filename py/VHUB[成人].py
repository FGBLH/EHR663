# coding: utf-8
import json
import sys
import re
import urllib.request
import urllib.parse
import ssl

sys.path.append('..')
from base.spider import Spider

VERSION = '2.0.0'

SITE_URL = 'https://newxvideos.pages.dev'
API_URL = 'https://newxvideos.pages.dev/api'

CATEGORIES = [
    {"type_id": "Arab-159", "type_name": "阿拉伯"},
    {"type_id": "Mature-38", "type_name": "成熟"},
    {"type_id": "Cuckold-237", "type_name": "出轨背叛"},
    {"type_id": "Femdom-235", "type_name": "调教"},
    {"type_id": "Anal-12", "type_name": "肛交"},
    {"type_id": "Brunette-25", "type_name": "褐发"},
    {"type_id": "Black_Woman-30", "type_name": "黑人"},
    {"type_id": "Redhead-31", "type_name": "红发"},
    {"type_id": "Fucked_Up_Family-81", "type_name": "家庭乱搞"},
    {"type_id": "Blonde-20", "type_name": "金发"},
    {"type_id": "Big_Cock-34", "type_name": "巨屌"},
    {"type_id": "Big_Tits-23", "type_name": "巨乳"},
    {"type_id": "Big_Ass-24", "type_name": "巨臀"},
    {"type_id": "Blowjob-15", "type_name": "口交"},
    {"type_id": "Latina-16", "type_name": "拉丁裔"},
    {"type_id": "Milf-19", "type_name": "辣妈"},
    {"type_id": "Gapes-167", "type_name": "裂开"},
    {"type_id": "Ass-14", "type_name": "美臀"},
    {"type_id": "Lesbian-26", "type_name": "女同"},
    {"type_id": "bbw-51", "type_name": "胖女"},
    {"type_id": "Squirting-56", "type_name": "喷出"},
    {"type_id": "Fisting-165", "type_name": "拳交"},
    {"type_id": "Gangbang-69", "type_name": "群交"},
    {"type_id": "Teen-13", "type_name": "少女"},
    {"type_id": "Cumshot-18", "type_name": "射颜"},
    {"type_id": "Cam_Porn-58", "type_name": "摄像头"},
    {"type_id": "Bi_Sexual-62", "type_name": "双性恋"},
    {"type_id": "Stockings-28", "type_name": "丝袜"},
    {"type_id": "Oiled-22", "type_name": "涂油"},
    {"type_id": "Lingerie-83", "type_name": "性感内衣"},
    {"type_id": "Asian_Woman-32", "type_name": "亚洲"},
    {"type_id": "Amateur-65", "type_name": "业余"},
    {"type_id": "Interracial-27", "type_name": "异族"},
    {"type_id": "Indian-89", "type_name": "印度"},
    {"type_id": "Creampie-40", "type_name": "中出"},
    {"type_id": "Solo_and_Masturbation-33", "type_name": "自慰"},
    {"type_id": "AI-239", "type_name": "AI"},
    {"type_id": "ASMR-229", "type_name": "ASMR"},
]


class Spider(Spider):
    def getName(self):
        return "V-HUB[成人]"

    def init(self, extend):
        if extend:
            self.host = extend.get('host', SITE_URL)
        else:
            self.host = SITE_URL
        self.api_url = self.host.rstrip('/') + '/api'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': self.host + '/',
            'Origin': self.host
        }
        self._ssl_context = ssl.create_default_context()
        self._ssl_context.check_hostname = False
        self._ssl_context.verify_mode = ssl.CERT_NONE

    def _xhttp(self, params):
        """使用标准库urllib发起HTTP GET请求"""
        try:
            qs = urllib.parse.urlencode(params)
            full_url = self.api_url + '?' + qs
            req = urllib.request.Request(full_url, headers=self.headers, method='GET')
            resp = urllib.request.urlopen(req, context=self._ssl_context, timeout=15)
            data = json.loads(resp.read().decode('utf-8'))
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and 'data' in data:
                return data['data']
            return []
        except Exception as e:
            print('_xhttp error: %s' % str(e), file=sys.stderr)
            return []

    def _format_time_cn(self, time_str):
        """将英文时间格式转为中文，如 '11 min' -> '11分钟'"""
        if not time_str:
            return ''
        m = re.match(r'^(\d+)\s*min\s*$', time_str.strip(), re.IGNORECASE)
        if m:
            return m.group(1) + '分钟'
        m = re.match(r'^(\d+)\s*h(?:our)?s?\s*(\d+)?\s*min\s*$', time_str.strip(), re.IGNORECASE)
        if m:
            h = m.group(1)
            mi = m.group(2)
            if mi:
                return h + '小时' + mi + '分钟'
            return h + '小时'
        return time_str

    def _extract_xvid(self, url):
        """从视频URL的查询参数中提取xvid值"""
        if not url:
            return ''
        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query)
        if 'xvid' in qs:
            return qs['xvid'][0]
        return ''

    def _build_vod_list(self, raw_data):
        """将API返回的原始数据构造为vod列表"""
        videos = []
        for item in raw_data:
            title = item.get('title', '')
            clean_title = re.sub(r'^AVOTC资源网[—-]+\s*', '', title).strip()
            if not clean_title:
                clean_title = title

            url = item.get('url', '')
            vod_id = self._extract_xvid(url)
            if not vod_id:
                vod_id = str(item.get('videoid', ''))

            videos.append({
                'vod_id': vod_id,
                'vod_name': clean_title,
                'vod_pic': item.get('img', ''),
                'vod_remarks': self._format_time_cn(item.get('time', '')),
                'vod_url': url
            })
        return videos

    def homeContent(self, filter):
        """首页：返回分类列表 + 首页视频"""
        classes = []
        for cat in CATEGORIES:
            classes.append({'type_id': cat['type_id'], 'type_name': cat['type_name']})

        raw_data = self._xhttp({'play': 'list', 'page': 1})
        videos = self._build_vod_list(raw_data)

        return {'class': classes, 'list': videos}

    def homeVideoContent(self):
        return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        """分类内容"""
        raw_data = self._xhttp({'play': 'class', 'c': tid, 'page': pg})
        videos = self._build_vod_list(raw_data)

        type_name = tid
        for cat in CATEGORIES:
            if cat['type_id'] == tid:
                type_name = cat['type_name']
                break

        return {
            'page': int(pg),
            'pagecount': 9999,
            'limit': 90,
            'total': 9999,
            'type_name': type_name,
            'list': videos
        }

    def detailContent(self, array):
        """详情：通过xvid获取视频播放地址"""
        result = {}
        if not array or not array[0]:
            return result

        xvid = array[0]
        vod = {
            'vod_id': xvid,
            'vod_name': '视频详情',
            'vod_pic': '',
            'vod_remarks': '',
            'vod_play_from': 'newxvideos',
            'vod_play_url': ''
        }

        try:
            qs = urllib.parse.urlencode({'xvid': xvid})
            full_url = self.api_url + '?' + qs
            req = urllib.request.Request(full_url, headers=self.headers, method='GET')
            resp = urllib.request.urlopen(req, context=self._ssl_context, timeout=15)
            data = json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            print('detailContent error: %s' % str(e), file=sys.stderr)
            result['list'] = [vod]
            return result

        play_urls = []

        if isinstance(data, dict):
            item = data
            if 'data' in data and isinstance(data['data'], dict):
                item = data['data']

            hls_url = item.get('hls') or item.get('m3u8') or ''
            hight_url = item.get('hight') or item.get('high') or item.get('hd') or ''
            low_url = item.get('low') or item.get('sd') or ''

            if hls_url:
                play_urls.append('高清HLS$' + hls_url)
            if hight_url:
                play_urls.append('高清MP4$' + hight_url)
            if low_url:
                play_urls.append('低清MP4$' + low_url)

            title = item.get('title', '')
            if title:
                clean_title = re.sub(r'^AVOTC资源网[—-]+\s*', '', title).strip()
                if clean_title:
                    vod['vod_name'] = clean_title

            img = item.get('img', '')
            if img:
                vod['vod_pic'] = img

            time_str = item.get('time', '')
            if time_str:
                vod['vod_remarks'] = self._format_time_cn(time_str)

        elif isinstance(data, list):
            for item in data:
                hls_url = item.get('hls') or item.get('m3u8') or ''
                hight_url = item.get('hight') or item.get('high') or item.get('hd') or ''
                low_url = item.get('low') or item.get('sd') or ''

                if hls_url:
                    play_urls.append('高清HLS$' + hls_url)
                if hight_url:
                    play_urls.append('高清MP4$' + hight_url)
                if low_url:
                    play_urls.append('低清MP4$' + low_url)

                if vod['vod_name'] == '视频详情':
                    title = item.get('title', '')
                    if title:
                        clean_title = re.sub(r'^AVOTC资源网[—-]+\s*', '', title).strip()
                        if clean_title:
                            vod['vod_name'] = clean_title
                    img = item.get('img', '')
                    if img:
                        vod['vod_pic'] = img
                    time_str = item.get('time', '')
                    if time_str:
                        vod['vod_remarks'] = self._format_time_cn(time_str)

        if play_urls:
            vod['vod_play_url'] = '#'.join(play_urls)

        result['list'] = [vod]
        return result

    def searchContent(self, key, quick, pg='1'):
        """搜索"""
        raw_data = self._xhttp({'play': 'k', 'k': key, 'page': pg})
        videos = self._build_vod_list(raw_data)

        return {
            'page': int(pg),
            'pagecount': 9999,
            'limit': 90,
            'total': 9999,
            'list': videos
        }

    def playerContent(self, flag, id, vipFlags):
        """播放地址解析 - 直接返回用户选择的清晰度地址"""
        if id and (id.startswith('http://') or id.startswith('https://')):
            return {
                'parse': 0,
                'playUrl': '',
                'url': id,
                'header': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Referer': self.host + '/'
                }
            }
        return {'parse': 0, 'playUrl': '', 'url': '', 'header': {}}

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return {}