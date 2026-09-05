# -*- coding: utf-8 -*-
"""
好剧影视 (好剧屋 www.haojuwu.cc)
适配 TVBox / 影视仓 / OK影视 等空壳影视 APP 的 Python 源
"""

import re
import sys
import json
import time
import random
import urllib.parse

import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def fetch(self, url, headers=None, timeout=20, verify=False, cookies=None):
            s = requests.Session()
            s.trust_env = False
            return s.get(url, headers=headers, timeout=timeout, verify=verify, cookies=cookies)

        def post(self, url, headers=None, data=None, timeout=20, verify=False, cookies=None):
            s = requests.Session()
            s.trust_env = False
            return s.post(url, headers=headers, data=data, timeout=timeout, verify=verify, cookies=cookies)


class Spider(BaseSpider):
    name = '好剧影视'
    host = 'https://www.haojuwu.cc/'

    CATEGORIES = [
        ('1', '电影'),
        ('2', '电视剧'),
        ('20', '短剧'),
        ('3', '综艺'),
        ('4', '动漫'),
        ('42', '其它'),
        ('43', '体育'),
    ]

    SUB2PARENT = {
        '6': '1', '7': '1', '8': '1', '9': '1', '10': '1', '11': '1', '12': '1',
        '21': '1', '22': '1', '23': '1', '24': '1', '25': '1', '40': '1', '39': '1',
        '13': '2', '14': '2', '15': '2', '16': '2', '26': '2', '27': '2', '28': '2', '29': '2',
        '35': '3', '36': '3', '37': '3', '38': '3',
        '30': '4', '31': '4', '32': '4', '33': '4', '34': '4',
        '48': '42', '49': '42',
        '44': '43', '45': '43', '46': '43', '47': '43',
    }

    FILTERS = {
    "1": [
        {"key": "tid", "name": "类型", "value": [{"n": "全部", "v": ""}, {"n": "动作片", "v": "6"}, {"n": "喜剧片", "v": "7"}, {"n": "爱情片", "v": "8"}, {"n": "科幻片", "v": "9"}, {"n": "恐怖片", "v": "10"}, {"n": "剧情片", "v": "11"}, {"n": "战争片", "v": "12"}, {"n": "记录片", "v": "21"}, {"n": "悬疑片", "v": "22"}, {"n": "动画片", "v": "23"}, {"n": "犯罪片", "v": "24"}, {"n": "奇幻片", "v": "25"}, {"n": "惊悚片", "v": "40"}, {"n": "预告片", "v": "39"}]},
        {"key": "class", "name": "剧情", "value": [{"n": "全部", "v": ""}, {"n": "喜剧", "v": "喜剧"}, {"n": "爱情", "v": "爱情"}, {"n": "恐怖", "v": "恐怖"}, {"n": "动作", "v": "动作"}, {"n": "科幻", "v": "科幻"}, {"n": "剧情", "v": "剧情"}, {"n": "战争", "v": "战争"}, {"n": "警匪", "v": "警匪"}, {"n": "犯罪", "v": "犯罪"}, {"n": "动画", "v": "动画"}, {"n": "奇幻", "v": "奇幻"}, {"n": "武侠", "v": "武侠"}, {"n": "冒险", "v": "冒险"}, {"n": "枪战", "v": "枪战"}, {"n": "悬疑", "v": "悬疑"}, {"n": "惊悚", "v": "惊悚"}, {"n": "经典", "v": "经典"}, {"n": "青春", "v": "青春"}, {"n": "文艺", "v": "文艺"}, {"n": "微电影", "v": "微电影"}, {"n": "古装", "v": "古装"}, {"n": "历史", "v": "历史"}, {"n": "运动", "v": "运动"}, {"n": "农村", "v": "农村"}, {"n": "儿童", "v": "儿童"}, {"n": "网络电影", "v": "网络电影"}]},
        {"key": "area", "name": "地区", "value": [{"n": "全部", "v": ""}, {"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"}, {"n": "台湾", "v": "台湾"}, {"n": "美国", "v": "美国"}, {"n": "法国", "v": "法国"}, {"n": "英国", "v": "英国"}, {"n": "日本", "v": "日本"}, {"n": "韩国", "v": "韩国"}, {"n": "德国", "v": "德国"}, {"n": "泰国", "v": "泰国"}, {"n": "印度", "v": "印度"}, {"n": "意大利", "v": "意大利"}, {"n": "西班牙", "v": "西班牙"}, {"n": "加拿大", "v": "加拿大"}, {"n": "其他", "v": "其他"}]},
        {"key": "year", "name": "年份", "value": [{"n": "全部", "v": ""}, {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"}, {"n": "2024", "v": "2024"}, {"n": "2023", "v": "2023"}, {"n": "2022", "v": "2022"}, {"n": "2021", "v": "2021"}, {"n": "2020", "v": "2020"}, {"n": "2019", "v": "2019"}, {"n": "2018", "v": "2018"}, {"n": "2017", "v": "2017"}, {"n": "2016", "v": "2016"}, {"n": "2015", "v": "2015"}, {"n": "2014", "v": "2014"}, {"n": "2013", "v": "2013"}, {"n": "2012", "v": "2012"}, {"n": "2011", "v": "2011"}, {"n": "2010", "v": "2010"}]},
        {"key": "lang", "name": "语言", "value": [{"n": "全部", "v": ""}, {"n": "国语", "v": "国语"}, {"n": "英语", "v": "英语"}, {"n": "粤语", "v": "粤语"}, {"n": "闽南语", "v": "闽南语"}, {"n": "韩语", "v": "韩语"}, {"n": "日语", "v": "日语"}, {"n": "法语", "v": "法语"}, {"n": "德语", "v": "德语"}, {"n": "其它", "v": "其它"}]},
        {"key": "by", "name": "排序", "value": [{"n": "默认", "v": ""}, {"n": "时间", "v": "time"}, {"n": "人气", "v": "hits"}, {"n": "评分", "v": "score"}]},
    ],
    "2": [
        {"key": "tid", "name": "类型", "value": [{"n": "全部", "v": ""}, {"n": "国产剧", "v": "13"}, {"n": "香港剧", "v": "14"}, {"n": "台湾剧", "v": "15"}, {"n": "美国剧", "v": "16"}, {"n": "韩国剧", "v": "26"}, {"n": "日本剧", "v": "27"}, {"n": "泰国剧", "v": "28"}, {"n": "海外剧", "v": "29"}]},
        {"key": "class", "name": "剧情", "value": [{"n": "全部", "v": ""}, {"n": "古装", "v": "古装"}, {"n": "战争", "v": "战争"}, {"n": "青春偶像", "v": "青春偶像"}, {"n": "喜剧", "v": "喜剧"}, {"n": "家庭", "v": "家庭"}, {"n": "犯罪", "v": "犯罪"}, {"n": "动作", "v": "动作"}, {"n": "奇幻", "v": "奇幻"}, {"n": "剧情", "v": "剧情"}, {"n": "历史", "v": "历史"}, {"n": "经典", "v": "经典"}, {"n": "乡村", "v": "乡村"}, {"n": "情景", "v": "情景"}, {"n": "商战", "v": "商战"}, {"n": "网剧", "v": "网剧"}, {"n": "其他", "v": "其他"}]},
        {"key": "area", "name": "地区", "value": [{"n": "全部", "v": ""}, {"n": "内地", "v": "内地"}, {"n": "韩国", "v": "韩国"}, {"n": "香港", "v": "香港"}, {"n": "台湾", "v": "台湾"}, {"n": "日本", "v": "日本"}, {"n": "美国", "v": "美国"}, {"n": "泰国", "v": "泰国"}, {"n": "英国", "v": "英国"}, {"n": "新加坡", "v": "新加坡"}, {"n": "其他", "v": "其他"}]},
        {"key": "year", "name": "年份", "value": [{"n": "全部", "v": ""}, {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"}, {"n": "2024", "v": "2024"}, {"n": "2023", "v": "2023"}, {"n": "2022", "v": "2022"}, {"n": "2021", "v": "2021"}, {"n": "2020", "v": "2020"}, {"n": "2019", "v": "2019"}, {"n": "2018", "v": "2018"}, {"n": "2017", "v": "2017"}, {"n": "2016", "v": "2016"}, {"n": "2015", "v": "2015"}, {"n": "2014", "v": "2014"}, {"n": "2013", "v": "2013"}, {"n": "2012", "v": "2012"}, {"n": "2011", "v": "2011"}, {"n": "2010", "v": "2010"}]},
        {"key": "lang", "name": "语言", "value": [{"n": "全部", "v": ""}, {"n": "国语", "v": "国语"}, {"n": "英语", "v": "英语"}, {"n": "粤语", "v": "粤语"}, {"n": "闽南语", "v": "闽南语"}, {"n": "韩语", "v": "韩语"}, {"n": "日语", "v": "日语"}, {"n": "其它", "v": "其它"}]},
        {"key": "by", "name": "排序", "value": [{"n": "默认", "v": ""}, {"n": "时间", "v": "time"}, {"n": "人气", "v": "hits"}, {"n": "评分", "v": "score"}]},
    ],
    "20": [
        {"key": "year", "name": "年份", "value": [{"n": "全部", "v": ""}, {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"}, {"n": "2024", "v": "2024"}, {"n": "2023", "v": "2023"}, {"n": "2022", "v": "2022"}, {"n": "2021", "v": "2021"}, {"n": "2020", "v": "2020"}, {"n": "2019", "v": "2019"}, {"n": "2018", "v": "2018"}, {"n": "2017", "v": "2017"}, {"n": "2016", "v": "2016"}, {"n": "2015", "v": "2015"}, {"n": "2014", "v": "2014"}, {"n": "2013", "v": "2013"}, {"n": "2012", "v": "2012"}, {"n": "2011", "v": "2011"}, {"n": "2010", "v": "2010"}]},
        {"key": "by", "name": "排序", "value": [{"n": "默认", "v": ""}, {"n": "时间", "v": "time"}, {"n": "人气", "v": "hits"}, {"n": "评分", "v": "score"}]},
    ],
    "3": [
        {"key": "tid", "name": "类型", "value": [{"n": "全部", "v": ""}, {"n": "大陆综艺", "v": "35"}, {"n": "日韩综艺", "v": "36"}, {"n": "欧美综艺", "v": "37"}, {"n": "港台综艺", "v": "38"}]},
        {"key": "class", "name": "剧情", "value": [{"n": "全部", "v": ""}, {"n": "选秀", "v": "选秀"}, {"n": "情感", "v": "情感"}, {"n": "访谈", "v": "访谈"}, {"n": "播报", "v": "播报"}, {"n": "旅游", "v": "旅游"}, {"n": "音乐", "v": "音乐"}, {"n": "美食", "v": "美食"}, {"n": "纪实", "v": "纪实"}, {"n": "曲艺", "v": "曲艺"}, {"n": "生活", "v": "生活"}, {"n": "游戏互动", "v": "游戏互动"}, {"n": "财经", "v": "财经"}, {"n": "求职", "v": "求职"}]},
        {"key": "area", "name": "地区", "value": [{"n": "全部", "v": ""}, {"n": "内地", "v": "内地"}, {"n": "港台", "v": "港台"}, {"n": "日韩", "v": "日韩"}, {"n": "欧美", "v": "欧美"}]},
        {"key": "year", "name": "年份", "value": [{"n": "全部", "v": ""}, {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"}, {"n": "2024", "v": "2024"}, {"n": "2023", "v": "2023"}, {"n": "2022", "v": "2022"}, {"n": "2021", "v": "2021"}, {"n": "2020", "v": "2020"}, {"n": "2019", "v": "2019"}, {"n": "2018", "v": "2018"}, {"n": "2017", "v": "2017"}, {"n": "2016", "v": "2016"}, {"n": "2015", "v": "2015"}, {"n": "2014", "v": "2014"}, {"n": "2013", "v": "2013"}, {"n": "2012", "v": "2012"}, {"n": "2011", "v": "2011"}, {"n": "2010", "v": "2010"}]},
        {"key": "lang", "name": "语言", "value": [{"n": "全部", "v": ""}, {"n": "国语", "v": "国语"}, {"n": "英语", "v": "英语"}, {"n": "粤语", "v": "粤语"}, {"n": "闽南语", "v": "闽南语"}, {"n": "韩语", "v": "韩语"}, {"n": "日语", "v": "日语"}, {"n": "其它", "v": "其它"}]},
        {"key": "by", "name": "排序", "value": [{"n": "默认", "v": ""}, {"n": "时间", "v": "time"}, {"n": "人气", "v": "hits"}, {"n": "评分", "v": "score"}]},
    ],
    "4": [
        {"key": "tid", "name": "类型", "value": [{"n": "全部", "v": ""}, {"n": "国产动漫", "v": "30"}, {"n": "日韩动漫", "v": "31"}, {"n": "欧美动漫", "v": "32"}, {"n": "港台动漫", "v": "33"}, {"n": "海外动漫", "v": "34"}]},
        {"key": "class", "name": "剧情", "value": [{"n": "全部", "v": ""}, {"n": "情感", "v": "情感"}, {"n": "科幻", "v": "科幻"}, {"n": "热血", "v": "热血"}, {"n": "推理", "v": "推理"}, {"n": "搞笑", "v": "搞笑"}, {"n": "冒险", "v": "冒险"}, {"n": "萝莉", "v": "萝莉"}, {"n": "校园", "v": "校园"}, {"n": "动作", "v": "动作"}, {"n": "机战", "v": "机战"}, {"n": "运动", "v": "运动"}, {"n": "战争", "v": "战争"}, {"n": "少年", "v": "少年"}, {"n": "少女", "v": "少女"}, {"n": "社会", "v": "社会"}, {"n": "原创", "v": "原创"}, {"n": "亲子", "v": "亲子"}, {"n": "益智", "v": "益智"}, {"n": "励志", "v": "励志"}, {"n": "其他", "v": "其他"}]},
        {"key": "area", "name": "地区", "value": [{"n": "全部", "v": ""}, {"n": "国产", "v": "国产"}, {"n": "日本", "v": "日本"}, {"n": "欧美", "v": "欧美"}, {"n": "其他", "v": "其他"}]},
        {"key": "year", "name": "年份", "value": [{"n": "全部", "v": ""}, {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"}, {"n": "2024", "v": "2024"}, {"n": "2023", "v": "2023"}, {"n": "2022", "v": "2022"}, {"n": "2021", "v": "2021"}, {"n": "2020", "v": "2020"}, {"n": "2019", "v": "2019"}, {"n": "2018", "v": "2018"}, {"n": "2017", "v": "2017"}, {"n": "2016", "v": "2016"}, {"n": "2015", "v": "2015"}, {"n": "2014", "v": "2014"}, {"n": "2013", "v": "2013"}, {"n": "2012", "v": "2012"}, {"n": "2011", "v": "2011"}, {"n": "2010", "v": "2010"}]},
        {"key": "lang", "name": "语言", "value": [{"n": "全部", "v": ""}, {"n": "国语", "v": "国语"}, {"n": "英语", "v": "英语"}, {"n": "粤语", "v": "粤语"}, {"n": "闽南语", "v": "闽南语"}, {"n": "韩语", "v": "韩语"}, {"n": "日语", "v": "日语"}, {"n": "其它", "v": "其它"}]},
        {"key": "by", "name": "排序", "value": [{"n": "默认", "v": ""}, {"n": "时间", "v": "time"}, {"n": "人气", "v": "hits"}, {"n": "评分", "v": "score"}]},
    ],
    "42": [
        {"key": "tid", "name": "类型", "value": [{"n": "全部", "v": ""}, {"n": "国创", "v": "48"}, {"n": "番剧", "v": "49"}]},
        {"key": "year", "name": "年份", "value": [{"n": "全部", "v": ""}, {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"}, {"n": "2024", "v": "2024"}, {"n": "2023", "v": "2023"}, {"n": "2022", "v": "2022"}, {"n": "2021", "v": "2021"}, {"n": "2020", "v": "2020"}, {"n": "2019", "v": "2019"}, {"n": "2018", "v": "2018"}, {"n": "2017", "v": "2017"}, {"n": "2016", "v": "2016"}, {"n": "2015", "v": "2015"}, {"n": "2014", "v": "2014"}, {"n": "2013", "v": "2013"}, {"n": "2012", "v": "2012"}, {"n": "2011", "v": "2011"}, {"n": "2010", "v": "2010"}]},
        {"key": "by", "name": "排序", "value": [{"n": "默认", "v": ""}, {"n": "时间", "v": "time"}, {"n": "人气", "v": "hits"}, {"n": "评分", "v": "score"}]},
    ],
    "43": [
        {"key": "tid", "name": "类型", "value": [{"n": "全部", "v": ""}, {"n": "足球", "v": "44"}, {"n": "篮球", "v": "45"}, {"n": "网球", "v": "46"}, {"n": "斯诺克", "v": "47"}]},
        {"key": "year", "name": "年份", "value": [{"n": "全部", "v": ""}, {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"}, {"n": "2024", "v": "2024"}, {"n": "2023", "v": "2023"}, {"n": "2022", "v": "2022"}, {"n": "2021", "v": "2021"}, {"n": "2020", "v": "2020"}, {"n": "2019", "v": "2019"}, {"n": "2018", "v": "2018"}, {"n": "2017", "v": "2017"}, {"n": "2016", "v": "2016"}, {"n": "2015", "v": "2015"}, {"n": "2014", "v": "2014"}, {"n": "2013", "v": "2013"}, {"n": "2012", "v": "2012"}, {"n": "2011", "v": "2011"}, {"n": "2010", "v": "2010"}]},
        {"key": "by", "name": "排序", "value": [{"n": "默认", "v": ""}, {"n": "时间", "v": "time"}, {"n": "人气", "v": "hits"}, {"n": "评分", "v": "score"}]},
    ],
    }

    # vodshow 段位索引 (共 12 段)
    SHOW_SEG = {'tid': 0, 'area': 1, 'by': 2, 'class': 3, 'lang': 4,
                'letter': 5, 'plot': 6, 'state': 7, 'page': 8,
                'tag': 9, 'version': 10, 'year': 11}
    SHOW_LEN = 12
    # vodsearch 段位: 共 14 段, [0]=wd, [10]=page
    SEARCH_LEN = 14
    SEARCH_WD = 0
    SEARCH_PAGE = 10

    # 需要走解析接口的线路 (playerconfig.js 中 ps=1)
    PARSE_API = 'https://api.jxapi.cc/api/?key=5eeebc4f347ad9a5197f3b13ba00fdb9&url='
    # 线路展示名 (playerconfig.js)
    FLAG_NAME = {
        'lzm3u8': '在线播放1', 'liangzi': '在线播放2', 'mzm3u8': '在线播放3',
        'qq': '腾讯', 'qiyi': '爱奇艺', 'youku': '优酷', 'mgtv': '芒果',
        'bilibili': '哔哩', 'rrmj': '人人视频', 'hmdj': '短剧',
    }

    VIDEO_EXT = ('.m3u8', '.mp4', '.flv', '.mkv', '.avi', '.ts', '.m3u', '.mpd')

    def __init__(self):
        try:
            super().__init__()
        except Exception:
            pass
        self._debug = True
        self._last_ts = {}

    # ==================================================================
    # 三、TVBox 基础接口
    # ==================================================================

    def getName(self):
        return self.name

    def init(self, extend=''):
        self._log(f'初始化完成: {self.host}')
        return {}

    def isVideoFormat(self, url):
        if not url:
            return False
        u = str(url).split('?')[0].lower()
        return u.endswith(self.VIDEO_EXT)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def _log(self, msg):
        if self._debug:
            print(f'[{self.name}] {msg}')

    def _headers(self, referer=None):
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': referer or self.host + '/',
        }

    def _throttle(self, key, gap=2.5):
        now = time.time()
        last = self._last_ts.get(key)
        if last is not None:
            wait = gap - (now - last)
            if wait > 0:
                time.sleep(wait)
        self._last_ts[key] = time.time()

    @staticmethod
    def _is_limited(html):
        """识别站点限流空壳页 (HTTP 200 但无内容)"""
        if not html:
            return True
        if len(html) < 3000:
            return True
        return ('请不要频繁操作' in html) or ('mac_msg_jump' in html)

    def _fetch(self, url, referer=None, retries=3, timeout=20):
        for i in range(retries):
            try:
                if i > 0:
                    time.sleep(random.uniform(0.6, 1.4))
                r = self.fetch(url, headers=self._headers(referer), timeout=timeout, verify=False)
                if getattr(r, 'status_code', 0) == 200:
                    if not r.encoding or r.encoding.lower() in ('iso-8859-1', 'latin-1'):
                        r.encoding = 'utf-8'
                    else:
                        r.encoding = 'utf-8'
                    return r.text or ''
                self._log(f'HTTP {r.status_code}: {url}')
            except Exception as e:
                self._log(f'请求异常 [{url}]: {e} (重试 {i + 1}/{retries})')
        return ''

    def _fetch_list(self, url, key=None, gap=2.5, tries=3):
        html = ''
        for i in range(tries):
            if key:
                self._throttle(key, gap)
            html = self._fetch(url)
            if html and not self._is_limited(html):
                return html
            self._log(f'疑似限流, 退避重试 {i + 1}/{tries}')
            time.sleep(gap)
        return html

    def _fix(self, url):
        if not url:
            return ''
        url = url.strip()
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('/'):
            return self.host + url
        if not url.startswith('http'):
            return urllib.parse.urljoin(self.host + '/', url)
        return url

    @staticmethod
    def _txt(s):
        if not s:
            return ''
        s = re.sub(r'<[^>]+>', ' ', str(s))
        s = s.replace('\xa0', ' ').replace('&nbsp;', ' ')
        return re.sub(r'\s+', ' ', s).strip()

    @staticmethod
    def _pic(node):
        """懒加载封面: data-original > data-src > src, 过滤 load.gif 占位"""
        if node is None:
            return ''
        for attr in ('data-original', 'data-src', 'data-echo', 'src'):
            v = (node.get(attr) or '').strip()
            if v and 'load.gif' not in v and not v.startswith('data:'):
                return v
        return ''

    def _show_url(self, tid, page=1, extend=None):
        """构造 /vodshow/ 12 段位 URL, 子分类替换段位[0]"""
        ext = extend if isinstance(extend, dict) else {}
        segs = [''] * self.SHOW_LEN

        # 子分类: 优先使用筛选器里选中的 tid, 否则用传入 tid
        real_tid = str(ext.get('tid') or '').strip() or str(tid)
        segs[self.SHOW_SEG['tid']] = real_tid

        for k in ('area', 'by', 'class', 'lang', 'year', 'letter', 'plot', 'state', 'tag', 'version'):
            v = str(ext.get(k) or '').strip()
            if v:
                segs[self.SHOW_SEG[k]] = urllib.parse.quote(v, safe='')

        p = int(page or 1)
        if p > 1:
            segs[self.SHOW_SEG['page']] = str(p)

        return f"{self.host}/vodshow/{'-'.join(segs)}.html"

    def _search_url(self, key, page=1):
        """构造 /vodsearch/ 14 段位 URL, 页码在段位[10]"""
        segs = [''] * self.SEARCH_LEN
        segs[self.SEARCH_WD] = urllib.parse.quote(str(key), safe='')
        p = int(page or 1)
        if p > 1:
            segs[self.SEARCH_PAGE] = str(p)
        return f"{self.host}/vodsearch/{'-'.join(segs)}.html"

    def _parse_list(self, html):
        """解析 stui-vodlist 卡片 (首页/分类/搜索通用)"""
        items, seen = [], set()
        if not html:
            return items
        soup = BeautifulSoup(html, 'html.parser')

        nodes = soup.select('a.stui-vodlist__thumb')
        if not nodes:
            nodes = soup.select('.stui-vodlist__box a[href*="/voddetail/"]')

        for a in nodes:
            try:
                href = a.get('href') or ''
                m = re.search(r'/voddetail/(\d+)', href)
                if not m:
                    continue
                vid = m.group(1)
                if vid in seen:
                    continue
                seen.add(vid)

                # 名称: title 属性优先, 其次同级 h4.title
                name = (a.get('title') or '').strip()
                box = a.find_parent(class_='stui-vodlist__box') or a.parent
                if not name and box:
                    h4 = box.select_one('.stui-vodlist__detail h4.title a, h4.title a, h4.title')
                    name = self._txt(h4.get_text() if h4 else '')

                # 封面: a 自身 data-original, 或内部 img
                pic = self._pic(a)
                if not pic:
                    pic = self._pic(a.select_one('img'))
                if not pic and box:
                    pic = self._pic(box.select_one('img'))

                # 备注: .pic-text (HD / 更新至第N集)
                remarks = ''
                rt = a.select_one('.pic-text')
                if rt:
                    remarks = self._txt(rt.get_text())
                if not remarks and box:
                    rt = box.select_one('.pic-text')
                    remarks = self._txt(rt.get_text()) if rt else ''
                # 副标题(演员)兜底
                if not remarks and box:
                    sub = box.select_one('.stui-vodlist__detail p.text')
                    remarks = self._txt(sub.get_text()) if sub else ''

                items.append({
                    'vod_id': vid,
                    'vod_name': name[:200],
                    'vod_pic': self._fix(pic),
                    'vod_remarks': remarks[:60],
                })
            except Exception as e:
                self._log(f'解析卡片异常: {e}')
                continue
        return items

    @staticmethod
    def _pagecount(html, page):
        """页码: 优先取 <li class="active num"><a>当前/总数</a>"""
        page = int(page or 1)
        if not html:
            return page
        m = re.search(r'class="active num"[^>]*>\s*<a[^>]*>\s*(\d+)\s*/\s*(\d+)\s*</a>', html)
        if m:
            return max(page, int(m.group(2)))
        # 兜底: 尾页链接
        m = re.search(r'href="(/vod(?:show|search)/[^"]+)"[^>]*>\s*尾页\s*<', html)
        if m:
            nums = re.findall(r'-(\d+)-', m.group(1))
            if nums:
                return max(page, max(int(x) for x in nums))
        return page

    def homeContent(self, filter=True):
        classes = [{'type_id': t, 'type_name': n} for t, n in self.CATEGORIES]
        result = {
            'class': classes,
            'filters': self.FILTERS,
            'parse': 0,
            'jx': 0,
        }
        try:
            html = self._fetch(self.host + '/')
            result['list'] = self._parse_list(html)[:40]
        except Exception as e:
            self._log(f'homeContent 异常: {e}')
            result['list'] = []
        return result

    def homeVideoContent(self):
        try:
            html = self._fetch(self.host + '/')
            return {'list': self._parse_list(html)[:40], 'parse': 0, 'jx': 0}
        except Exception as e:
            self._log(f'homeVideoContent 异常: {e}')
            return {'list': [], 'parse': 0, 'jx': 0}

    def categoryContent(self, tid, pg, filter=True, extend=None):
        page = int(pg) if pg else 1
        try:
            url = self._show_url(tid, page, extend)
            html = self._fetch_list(url, key='show', gap=0.4)
            items = self._parse_list(html)
            pc = self._pagecount(html, page)
            return {
                'list': items,
                'page': page,
                'pagecount': pc,
                'limit': len(items) or 12,
                'total': pc * (len(items) or 12),
                'parse': 0,
                'jx': 0,
            }
        except Exception as e:
            self._log(f'categoryContent 异常: {e}')
            return {'list': [], 'page': page, 'pagecount': page,
                    'limit': 12, 'total': 0, 'parse': 0, 'jx': 0}

    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, (list, tuple)) else ids)
        vid = re.sub(r'\D', '', vid) or vid
        url = f'{self.host}/voddetail/{vid}.html'
        try:
            html = self._fetch(url, referer=self.host + '/')
            if not html:
                return self._empty_detail(vid)
            return {'list': [self._parse_detail(vid, html)], 'parse': 0, 'jx': 0}
        except Exception as e:
            self._log(f'detailContent 异常: {e}')
            return self._empty_detail(vid)

    def _empty_detail(self, vid):
        return {'list': [{
            'vod_id': vid, 'vod_name': '获取失败', 'vod_pic': '',
            'vod_play_from': '默认', 'vod_play_url': '',
        }], 'parse': 0, 'jx': 0}

    def _parse_detail(self, vid, html):
        soup = BeautifulSoup(html, 'html.parser')

        # --- 标题 ---
        h1 = soup.select_one('.stui-content__detail h1.title') or soup.select_one('h1.title')
        vod_name = self._txt(h1.get_text() if h1 else '')
        if not vod_name:
            m = re.search(r'<title>([^<]*?)(?:-[^-]*)?</title>', html)
            vod_name = self._txt(m.group(1)) if m else vid

        # --- 封面 ---
        pic = self._pic(soup.select_one('.stui-content__thumb img'))
        if not pic:
            m = re.search(r'property="og:image"\s+content="([^"]+)"', html)
            pic = m.group(1) if m else ''

        # --- 信息行 ---
        info = {}
        for p in soup.select('.stui-content__detail p.data'):
            t = self._txt(p.get_text(' '))
            for part in t.split(' / '):
                m = re.match(r'^(类型|地区|年份|语言|状态|导演|主演|更新)[：:]\s*(.*)$', part.strip())
                if m and m.group(2):
                    k, v = m.group(1), m.group(2).strip()
                    if k not in info or len(v) > len(info[k]):
                        info[k] = v

        # --- 简介 ---
        desc = soup.select_one('.detail-content') or soup.select_one('.detail-sketch')
        vod_content = self._txt(desc.get_text() if desc else '')

        # --- 播放线路 ---
        # tab 名称 -> #playlistN
        tab_map = {}
        for a in soup.select('ul.nav.nav-tabs.dpplay li a'):
            href = (a.get('href') or '').lstrip('#')
            if href:
                tab_map[href] = self._txt(a.get_text()) or href

        froms, urls = [], []
        for div in soup.select('div[id^="playlist"]'):
            did = div.get('id') or ''
            eps = []
            for a in div.select('ul.stui-content__playlist li a'):
                ep_name = self._txt(a.get_text())
                href = a.get('href') or ''
                m = re.search(r'/vodplay/(\d+)-(\d+)-(\d+)', href)
                if not m:
                    continue
                # 播放标识: vid-sid-nid, 由 playerContent 解析
                eps.append(f'{ep_name}${m.group(1)}-{m.group(2)}-{m.group(3)}')
            if not eps:
                continue
            froms.append(tab_map.get(did, did))
            urls.append('#'.join(eps))

        if not froms:
            froms, urls = ['默认'], [f'正片${vid}-1-1']

        return {
            'vod_id': vid,
            'vod_name': vod_name,
            'vod_pic': self._fix(pic),
            'type_name': info.get('类型', ''),
            'vod_year': info.get('年份', ''),
            'vod_area': info.get('地区', ''),
            'vod_lang': info.get('语言', ''),
            'vod_remarks': info.get('状态', '') or info.get('更新', ''),
            'vod_actor': info.get('主演', ''),
            'vod_director': info.get('导演', ''),
            'vod_content': vod_content,
            'vod_play_from': '$$$'.join(froms),
            'vod_play_url': '$$$'.join(urls),
        }

    def playerContent(self, flag, id, vipFlags=None):
        pid = str(id or '').strip()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Referer': self.host + '/',
        }
        try:
            # 已经是直链
            if pid.startswith('http') and self.isVideoFormat(pid):
                return self._play(pid, headers, parse=0)

            if not re.match(r'^\d+-\d+-\d+$', pid):
                m = re.search(r'(\d+-\d+-\d+)', pid)
                if not m:
                    return self._play('', headers, parse=1, play_url=pid)
                pid = m.group(1)

            play_page = f'{self.host}/vodplay/{pid}.html'
            html = self._fetch(play_page, referer=self.host + '/')
            data = self._player_data(html)
            if not data:
                return self._play('', headers, parse=1, play_url=play_page)

            raw = self._decode_url(data.get('url') or '', data.get('encrypt'))
            frm = (data.get('from') or '').strip()

            # 1) 直链 m3u8 / mp4
            if raw and self.isVideoFormat(raw):
                return self._play(raw, headers, parse=0)

            # 2) share 分享页 -> var main = "/xxx/index.m3u8?sign=..."
            if raw and '/share/' in raw:
                real = self._resolve_share(raw)
                if real:
                    return self._play(real, headers, parse=0)

            # 3) 官方解析接口 (爱奇艺/腾讯/优酷/B站等)
            if raw:
                real = self._resolve_parse(raw)
                if real:
                    return self._play(real, headers, parse=0)
                # 解析失败 -> 交给 APP 自带解析
                return self._play('', headers, parse=1, play_url=raw)

            return self._play('', headers, parse=1, play_url=play_page)
        except Exception as e:
            self._log(f'playerContent 异常: {e}')
            return self._play('', headers, parse=1, play_url=pid)

    @staticmethod
    def _play(url, headers, parse=0, play_url=''):
        return {
            'parse': parse,
            'playUrl': '',
            'url': url or play_url,
            'header': json.dumps(headers),
            'jx': 0,
            'contentType': 'application/vnd.apple.mpegurl' if str(url).find('.m3u8') > 0 else '',
        }

    @staticmethod
    def _player_data(html):
        if not html:
            return None
        m = re.search(r'player_\w+\s*=\s*(\{.*?\})\s*</script>', html, re.S)
        if not m:
            m = re.search(r'player_\w+\s*=\s*(\{.*?\});', html, re.S)
        if not m:
            return None
        try:
            return json.loads(m.group(1))
        except Exception:
            return None

    @staticmethod
    def _decode_url(url, encrypt):
        """MacCMS encrypt: 0=明文 1=urlencode 2=base64+urlencode"""
        if not url:
            return ''
        try:
            e = int(encrypt or 0)
        except Exception:
            e = 0
        try:
            if e == 1:
                url = urllib.parse.unquote(url)
            elif e == 2:
                import base64
                url = urllib.parse.unquote(base64.b64decode(url).decode('utf-8'))
        except Exception:
            pass
        return url.strip()

    def _resolve_share(self, share_url):
        """量子/CDN 分享页 -> 真实 m3u8"""
        try:
            html = self._fetch(share_url, referer=self.host + '/', retries=2)
            if not html:
                return ''
            m = re.search(r'var\s+main\s*=\s*["\']([^"\']+)["\']', html)
            if not m:
                m = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', html)
                return m.group(1) if m else ''
            main = m.group(1)
            if main.startswith('http'):
                return main
            pr = urllib.parse.urlparse(share_url)
            return f'{pr.scheme}://{pr.netloc}{main}'
        except Exception as e:
            self._log(f'share 解析失败: {e}')
            return ''

    def _resolve_parse(self, target):
        """调用站点 playerconfig.js 中的解析接口取真实播放地址"""
        try:
            api = self.PARSE_API + urllib.parse.quote(target, safe='')
            r = self.fetch(api, headers=self._headers(), timeout=25, verify=False)
            if getattr(r, 'status_code', 0) != 200:
                return ''
            r.encoding = 'utf-8'
            txt = r.text or ''
            try:
                d = json.loads(txt)
                u = d.get('url') or d.get('play_url') or (d.get('data') or {}).get('url')
                if u:
                    return u
            except Exception:
                pass
            m = re.search(r'(https?://[^"\'\s\\]+\.m3u8[^"\'\s\\]*)', txt)
            return m.group(1) if m else ''
        except Exception as e:
            self._log(f'解析接口失败: {e}')
            return ''

    def searchContent(self, key, quick=False, pg='1'):
        page = int(pg) if pg else 1
        try:
            url = self._search_url(key, page)
            html = self._fetch_list(url, key='search', gap=2.5, tries=3)
            items = self._parse_list(html)
            pc = self._pagecount(html, page)
            return {
                'list': items,
                'page': page,
                'pagecount': pc,
                'limit': len(items) or 12,
                'total': pc * (len(items) or 12),
                'parse': 0,
                'jx': 0,
            }
        except Exception as e:
            self._log(f'searchContent 异常: {e}')
            return {'list': [], 'page': page, 'pagecount': page,
                    'limit': 12, 'total': 0, 'parse': 0, 'jx': 0}

    def searchContentPage(self, key, quick=False, pg='1'):
        return self.searchContent(key, quick, pg)

    def localProxy(self, param):
        try:
            if isinstance(param, dict):
                url = param.get('url') or ''
            else:
                url = str(param or '')
            if not url.startswith('http'):
                return None
            r = self.fetch(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': self.host + '/',
            }, timeout=20, verify=False)
            ct = r.headers.get('Content-Type', 'application/octet-stream')
            return [200, ct, r.content]
        except Exception:
            return None


if __name__ == '__main__':
    sp = Spider()
    sp.init()

    print('\n================ 1. 首页 / 分类 / 筛选器 ================')
    home = sp.homeContent(True)
    print(f"父分类 {len(home['class'])} 个: " + ', '.join(f"{c['type_name']}({c['type_id']})" for c in home['class']))
    print(f"首页推荐 {len(home['list'])} 条")
    for v in home['list'][:5]:
        print(f"   {v['vod_name'][:26]:<28} id={v['vod_id']:<8} 备注={v['vod_remarks'][:12]:<14} 封面={'OK' if v['vod_pic'].startswith('http') else '缺失'}")
    print('筛选器:')
    for tid, groups in home['filters'].items():
        tn = dict(sp.CATEGORIES).get(tid, tid)
        print(f"   {tn}({tid}): " + ' | '.join(f"{g['name']}×{len(g['value'])}" for g in groups))

    print('\n================ 2. 分类 + 分页 ================')
    for tid, pg in [('1', 1), ('1', 3), ('2', 1), ('20', 2), ('4', 1), ('43', 1)]:
        r = sp.categoryContent(tid, pg, True, {})
        tn = dict(sp.CATEGORIES).get(tid, tid)
        first = r['list'][0]['vod_name'][:20] if r['list'] else '-'
        print(f"   {tn}({tid}) 第{pg}页: {len(r['list']):>2} 条 / 共 {r['pagecount']} 页  首条={first}")

    print('\n================ 3. 每个父分类下的子分类(筛选器) ================')
    for tid, groups in home['filters'].items():
        tn = dict(sp.CATEGORIES).get(tid, tid)
        sub = next((g for g in groups if g['key'] == 'tid'), None)
        if not sub:
            print(f"   {tn}({tid}): 无子分类")
            continue
        for item in sub['value']:
            if not item['v']:
                continue
            r = sp.categoryContent(tid, 1, True, {'tid': item['v']})
            first = r['list'][0]['vod_name'][:18] if r['list'] else '-'
            print(f"   {tn}>{item['n']}({item['v']}): {len(r['list']):>2} 条 / {r['pagecount']} 页  首条={first}")

    print('\n================ 4. 组合筛选 ================')
    combos = [
        ('1', {'tid': '6', 'area': '大陆', 'year': '2025', 'by': 'hits'}, '电影>动作片+大陆+2025+人气'),
        ('1', {'class': '古装'}, '电影+剧情:古装'),
        ('2', {'tid': '13', 'lang': '国语', 'year': '2026'}, '电视剧>国产剧+国语+2026'),
        ('4', {'tid': '31', 'class': '热血'}, '动漫>日韩动漫+热血'),
    ]
    for tid, ext, label in combos:
        r = sp.categoryContent(tid, 1, True, ext)
        first = r['list'][0]['vod_name'][:20] if r['list'] else '-'
        print(f"   {label}: {len(r['list'])} 条 / {r['pagecount']} 页  首条={first}")

    print('\n================ 5. 详情 ================')
    target = home['list'][0] if home['list'] else None
    det = None
    if target:
        det = sp.detailContent([target['vod_id']])['list'][0]
        print(f"   名称: {det['vod_name']}")
        print(f"   封面: {det['vod_pic'][:80]}")
        print(f"   类型: {det['type_name']} | 地区: {det['vod_area']} | 年份: {det['vod_year']} | 语言: {det['vod_lang']}")
        print(f"   状态: {det['vod_remarks']}")
        print(f"   导演: {det['vod_director'][:40]}")
        print(f"   主演: {det['vod_actor'][:60]}")
        print(f"   简介: {det['vod_content'][:70]}...")
        fl = det['vod_play_from'].split('$$$')
        ul = det['vod_play_url'].split('$$$')
        print(f"   线路 {len(fl)} 条:")
        for f, u in zip(fl, ul):
            eps = u.split('#')
            print(f"      {f}: {len(eps)} 集  -> {eps[0]}")

    print('\n================ 6. 播放解析 ================')
    if det:
        fl = det['vod_play_from'].split('$$$')
        ul = det['vod_play_url'].split('$$$')
        for f, u in zip(fl, ul):
            first_ep = u.split('#')[0]
            pid = first_ep.split('$')[-1]
            p = sp.playerContent(f, pid)
            print(f"   [{f}] parse={p['parse']}  url={p['url'][:100]}")

    print('\n================ 7. 剧集多线路(电视剧样例) ================')
    tv = sp.categoryContent('2', 1, True, {})['list']
    if tv:
        d2 = sp.detailContent([tv[0]['vod_id']])['list'][0]
        print(f"   {d2['vod_name']} | 封面={'OK' if d2['vod_pic'].startswith('http') else '缺失'}")
        for f, u in zip(d2['vod_play_from'].split('$$$'), d2['vod_play_url'].split('$$$')):
            eps = u.split('#')
            print(f"      {f}: {len(eps)} 集")
        f0 = d2['vod_play_from'].split('$$$')[0]
        u0 = d2['vod_play_url'].split('$$$')[0].split('#')
        pick = u0[min(2, len(u0) - 1)].split('$')[-1]
        p = sp.playerContent(f0, pick)
        print(f"      播放({f0} 第{min(3, len(u0))}集) parse={p['parse']} url={p['url'][:100]}")

    print('\n================ 8. 搜索 + 搜索分页 ================')
    for kw in ['斗罗大陆', '庆余年', '仙逆']:
        r = sp.searchContent(kw, False, '1')
        first = r['list'][0]['vod_name'][:24] if r['list'] else '-'
        print(f"   搜索[{kw}]: {len(r['list'])} 条 / {r['pagecount']} 页  首条={first}")
    r2 = sp.searchContent('斗罗大陆', False, '2')
    print(f"   搜索[斗罗大陆] 第2页: {len(r2['list'])} 条  首条={r2['list'][0]['vod_name'][:24] if r2['list'] else '-'}")

    print('\n完成。')
