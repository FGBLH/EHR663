#coding=utf-8
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TVBox / 影视仓  Python源脚本
站点: 一起影视 (www.yiqiys.com)
模板: 苹果CMS V10 (stui)，播放直链从 player_data 中提取
"""

import sys
import re
import json
import time
import requests
from urllib.parse import quote
sys.path.append('..')
from base.spider import Spider

class Spider(Spider):

    def __init__(self):
        super().__init__()
        self.site = 'https://www.yiqiys.com'
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.yiqiys.com/'
        })
        self.cateManual = {
            '电影': '1',
            '电视剧': '2',
            '综艺': '3',
            '动漫': '4'
        }

    def init(self, extend=""):
        pass

    def getName(self):
        return "一起影视"

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    # ---------------- 工具方法 ----------------

    def fetch(self, url):
        r = self.session.get(url, timeout=15)
        r.encoding = 'utf-8'
        return r.text

    def stripTag(self, s):
        if not s:
            return ''
        s = re.sub(r'<[^>]+>', '', s)
        s = s.replace('&nbsp;', ' ')
        s = re.sub(r'\s+', ' ', s)
        return s.strip()

    def buildShowUrl(self, tid, page, area='', year=''):
        """筛选列表页: /show/{tid}-{area}-------{page}---{year}.html 共12段"""
        parts = [''] * 12
        parts[0] = str(tid)
        if area:
            parts[1] = quote(str(area))
        if page and int(page) > 1:
            parts[8] = str(page)
        if year:
            parts[11] = str(year)
        return f"{self.site}/show/{'-'.join(parts)}.html"

    def parseList(self, html):
        """解析 stui-vodlist__box 列表项"""
        videos = []
        seen = set()
        for m in re.finditer(r'<div class="stui-vodlist__box">(.*?)</div>\s*</li>', html, re.DOTALL):
            block = m.group(1)
            hm = re.search(r'href="(/detail/(\d+)\.html)"', block)
            if not hm:
                continue
            vid = hm.group(2)
            if vid in seen:
                continue
            # 标题：优先取缩略图a的title属性
            title = ''
            tm = re.search(r'title="([^"]+)"', block)
            if tm:
                title = tm.group(1).strip()
            if not title:
                tm2 = re.search(r'<h4[^>]*>\s*<a[^>]*>([^<]+)</a>', block)
                if tm2:
                    title = tm2.group(1).strip()
            # 图片
            pic = ''
            pm = re.search(r'data-original="([^"]+)"', block)
            if pm:
                pic = pm.group(1).strip()
                if pic.startswith('/'):
                    pic = self.site + pic
            # 备注(更新状态/清晰度)
            note = ''
            nm = re.search(r'<span class="pic-text[^"]*">([^<]*)</span>', block)
            if not nm:
                # 首页"最新更新"板块备注在 score span 里
                nm = re.search(r'<span class="score[^"]*">([^<]*)</span>', block)
            if nm:
                note = nm.group(1).strip()
            if title:
                seen.add(vid)
                videos.append({
                    'vod_id': vid,
                    'vod_name': title,
                    'vod_pic': pic,
                    'vod_remarks': note
                })
        return videos

    def getPageTotal(self, html):
        """从 <li class="active num"><a>2/3843</a></li> 提取总页数"""
        m = re.search(r'<li class="active num"><a>\d+/(\d+)</a></li>', html)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
        return 0

    def getFilters(self):
        years = [('全部', '')] + [(str(y), str(y)) for y in range(2026, 2009, -1)]
        area_movie = [('全部', ''), ('大陆', '大陆'), ('香港', '香港'), ('台湾', '台湾'),
                      ('美国', '美国'), ('法国', '法国'), ('英国', '英国'), ('日本', '日本'),
                      ('韩国', '韩国'), ('泰国', '泰国'), ('印度', '印度'), ('西班牙', '西班牙'),
                      ('加拿大', '加拿大'), ('俄罗斯', '俄罗斯'), ('其它', '其它')]
        area_zh = [('全部', ''), ('大陆', '大陆'), ('香港', '香港'), ('美国', '美国'),
                   ('台湾', '台湾'), ('韩国', '韩国'), ('日本', '日本')]

        def fv(items):
            return [{'n': n, 'v': v} for n, v in items]

        return {
            '1': [
                {'key': 'class', 'name': '类型', 'value': fv([('全部', ''), ('动作片', '5'), ('喜剧片', '6'),
                                                              ('爱情片', '7'), ('科幻片', '8'), ('恐怖片', '9'),
                                                              ('剧情片', '10'), ('战争片', '11')])},
                {'key': 'area', 'name': '地区', 'value': fv(area_movie)},
                {'key': 'year', 'name': '年份', 'value': fv(years)},
            ],
            '2': [
                {'key': 'class', 'name': '类型', 'value': fv([('全部', ''), ('国产剧', '12'), ('港台剧', '13'),
                                                              ('欧美剧', '14'), ('日韩剧', '15'), ('海外剧', '16')])},
                {'key': 'area', 'name': '地区', 'value': fv(area_movie)},
                {'key': 'year', 'name': '年份', 'value': fv(years)},
            ],
            '3': [
                {'key': 'area', 'name': '地区', 'value': fv(area_zh)},
                {'key': 'year', 'name': '年份', 'value': fv(years)},
            ],
            '4': [
                {'key': 'area', 'name': '地区', 'value': fv(area_zh)},
                {'key': 'year', 'name': '年份', 'value': fv(years)},
            ],
        }

    # ---------------- 接口实现 ----------------

    def homeContent(self, filter):
        result = {'class': [], 'filters': {}, 'list': [], 'parse': 0, 'jx': 0}
        for k, v in self.cateManual.items():
            result['class'].append({
                'type_id': str(v),
                'type_name': k
            })
        if filter:
            result['filters'] = self.getFilters()
        return result

    def homeVideoContent(self):
        videos = []
        try:
            html = self.fetch(self.site + '/')
            videos = self.parseList(html)
        except Exception as e:
            print(f'homeVideoContent error: {e}')
        return {'list': videos[:24], 'parse': 0, 'jx': 0}

    def categoryContent(self, tid, pg, filter, extend):
        result = {'list': [], 'parse': 0, 'jx': 0}
        page = int(pg) if pg else 1
        extend = extend or {}
        html = ''
        try:
            # 子类筛选覆盖tid
            real_tid = extend.get('class') or tid
            area = extend.get('area') or ''
            year = extend.get('year') or ''
            url = self.buildShowUrl(real_tid, page, area, year)
            html = self.fetch(url)
            result['list'] = self.parseList(html)
        except Exception as e:
            print(f'categoryContent error: {e}')

        total = self.getPageTotal(html) if html else 0
        pagecount = total if total > 0 else (page + 1 if result['list'] else page)
        result['page'] = page
        result['pagecount'] = max(pagecount, page)
        result['limit'] = len(result['list'])
        result['total'] = result['limit'] * result['pagecount']
        return result

    def detailContent(self, ids):
        result = {'list': [], 'parse': 0, 'jx': 0}
        vid = ids[0] if ids else ''
        if not vid:
            return result
        html = ''
        try:
            url = f'{self.site}/detail/{vid}.html'
            html = self.fetch(url)

            # 标题
            title = ''
            m = re.search(r'<h1 class="title">(.*?)</h1>', html, re.DOTALL)
            if m:
                title = self.stripTag(m.group(1))

            # 海报
            pic = ''
            m = re.search(r'<img[^>]+data-original="([^"]+)"', html)
            if m:
                pic = m.group(1).strip()
                if pic.startswith('/'):
                    pic = self.site + pic

            # 元信息(状态/年份/类型/国家/导演)
            def grab(label):
                mm = re.search(r'<span class="(?:left )?data2">' + label + r'：</span>(.*?)</p>', html, re.DOTALL)
                return self.stripTag(mm.group(1)) if mm else ''

            state = grab('状态')
            year = grab('年份')
            type_name = grab('类型')
            area = grab('国家')
            director = grab('导演')

            # 主演
            actor = ''
            m = re.search(r'<span class="left data2">主演：</span><span class="data5">(.*?)</span>', html, re.DOTALL)
            if m:
                actor = self.stripTag(m.group(1))

            # 简介(优先完整版)
            desc = ''
            m = re.search(r'<span class="detail-content"[^>]*>(.*?)</span>', html, re.DOTALL)
            if m:
                desc = self.stripTag(m.group(1))
            if not desc:
                m = re.search(r'<span class="detail-sketch">(.*?)</span>', html, re.DOTALL)
                if m:
                    desc = self.stripTag(m.group(1))

            # 播放线路名(按出现顺序)
            line_names = []
            for m in re.finditer(r'<div class="stui-vodlist__head">.*?<h4>(.*?)</h4>', html, re.DOTALL):
                name = self.stripTag(m.group(1))
                if name:
                    line_names.append(name)

            # 各线路剧集列表(按出现顺序与线路名一一对应)
            playlists = re.findall(r'<ul class="stui-content__playlist[^"]*">(.*?)</ul>', html, re.DOTALL)

            play_from = []
            play_url = []
            for i, pl in enumerate(playlists):
                eps = re.findall(r'<a[^>]+href="(/play/\d+-\d+-\d+\.html)"[^>]*>([^<]+)</a>', pl)
                if not eps:
                    continue
                line = line_names[i] if i < len(line_names) else f'线路{i + 1}'
                play_from.append(line)
                play_url.append('#'.join(f'{t.strip()}${h}' for h, t in eps))

            vod = {
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': pic,
                'type_name': type_name,
                'vod_year': year,
                'vod_area': area,
                'vod_remarks': state,
                'vod_actor': actor,
                'vod_director': director,
                'vod_content': desc,
                'vod_play_from': '$$$'.join(play_from) if play_from else '',
                'vod_play_url': '$$$'.join(play_url) if play_url else ''
            }
            result['list'].append(vod)
        except Exception as e:
            print(f'detailContent error: {e}')
        return result

    def playerContent(self, flag, id, vipFlags):
        result = {}
        try:
            play_url = id if id.startswith('http') else self.site + id
            html = self.fetch(play_url)

            video_url = ''
            # 标准苹果CMS: var player_data = {...}
            m = re.search(r'var\s+player_data\s*=\s*(.*?)</script>', html, re.DOTALL)
            if m:
                raw = m.group(1).strip().rstrip(';').strip()
                try:
                    data = json.loads(raw)
                    u = data.get('url') or ''
                    if u.startswith('http') and not data.get('encrypt'):
                        video_url = u
                except Exception:
                    pass

            # 兜底: 正则直搜m3u8/mp4
            if not video_url:
                m = re.search(r'https?://[^\s"\'<>]+?\.(?:m3u8|mp4)[^\s"\'<>]*', html)
                if m:
                    video_url = m.group(0)

            if video_url:
                result['parse'] = 0
                result['playUrl'] = ''
                result['url'] = video_url
                result['jx'] = 0
                result['header'] = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Referer': self.site + '/'
                }
            else:
                result['parse'] = 1
                result['url'] = play_url
                result['jx'] = 0
                result['header'] = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Referer': self.site + '/'
                }
        except Exception as e:
            print(f'playerContent error: {e}')
            result['parse'] = 1
            result['url'] = id if id.startswith('http') else self.site + id
            result['jx'] = 0
            result['header'] = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': self.site + '/'
            }
        return result

    def searchContent(self, key, quick, pg='1'):
        result = {'list': [], 'parse': 0, 'jx': 0}
        page = int(pg) if pg else 1
        try:
            if page > 1:
                url = f"{self.site}/search/{quote(key)}----------{page}---.html"
            else:
                url = f"{self.site}/search/-------------.html?wd={quote(key)}"
            html = self.fetch(url)
            # 站点限制: 两次搜索间隔需3秒, 触发限流时等待后重试一次
            if '频繁操作' in html:
                time.sleep(3.5)
                html = self.fetch(url)
            result['list'] = self.parseList(html)
        except Exception as e:
            print(f'searchContent error: {e}')

        result['page'] = page
        result['pagecount'] = page + 1 if result['list'] else page
        result['limit'] = len(result['list'])
        result['total'] = len(result['list'])
        return result

    def localProxy(self, params):
        return [200, "video/MP2T", {}, ""]
