# -*- coding: utf-8 -*-

import re
import sys
from pyquery import PyQuery as pq

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    def init(self, extend=""):
        self.extend = extend

    def getName(self):
        return "毒舌影视"

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    host = 'https://www.xnhrsb.com/'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; Mobile) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/114.0.0.0 Mobile Safari/537.36',
        'Referer': host,
    }

    # 对应 js 里的 class_name / class_url
    classes_config = [
        ("电影", "1"),
        ("电视剧", "2"),
        ("综艺", "3"),
        ("动漫", "4"),
        ("短剧", "5"),
        ("豆瓣", "duoban"),
    ]

    def homeContent(self, filter):
        result = {}
        classes = []
        vlist = []

        # 静态分类
        for name, tid in self.classes_config:
            classes.append({
                "type_name": name,
                "type_id": tid
            })

        # 首页推荐，沿用一级规则里的 .mrb ul li
        rsp = self.fetch(self.host, headers=self.headers)
        data = pq(rsp.text)

        # 一级: '.mrb&&ul li;.dytit&&Text;.lazy&&data-original;.hdinfo&&Text;a&&href'
        vlist.extend(self.getlist(data('.mrb ul li')))

        result['class'] = classes
        result['list'] = vlist
        return result

    def homeVideoContent(self):
        return {}

    def categoryContent(self, tid, pg, filter, extend):
        # js: url: '/dsshiyisw/fyclass--------fypage---.html'
        url = f'{self.host}dsshiyisw/{tid}--------{pg}---.html'
        rsp = self.fetch(url, headers=self.headers)
        data = pq(rsp.text)

        videos = self.getlist(data('.mrb ul li'))

        result = {
            'list': videos,
            'page': pg,
            'pagecount': 9999,
            'limit': 90,
            'total': 999999
        }
        return result

    def detailContent(self, ids):
        vid = ids[0]
        if not vid.startswith('http'):
            if vid.startswith('/'):
                url = self.host.rstrip('/') + vid
            else:
                url = self.host.rstrip('/') + '/' + vid
        else:
            url = vid

        rsp = self.fetch(url, headers=self.headers)
        data = pq(rsp.text)

        # 二级: title/img/desc/content/tabs/lists
        # title: 'h1&&Text;.moviedteail_list li&&a&&Text'
        name = data('h1').text()

        info_list = data('.moviedteail_list li')

        def li_text(idx):
            return info_list.eq(idx).text() if idx < len(info_list) else ''

        # 参考 desc 顺序，大致映射
        # desc: '.moviedteail_list li:eq(3)&&Text;
        #        .moviedteail_list li:eq(2)&&Text;
        #        .moviedteail_list li:eq(1)&&Text;
        #        .moviedteail_list li:eq(6)&&Text;
        #        .moviedteail_list li:eq(4)&&Text'
        type_name = li_text(3)
        director = li_text(2)
        actor = li_text(1)
        remarks = li_text(6)
        year_or_area = li_text(4)

        pic = data('div.dyimg img').attr('src') or ''
        if pic and not pic.startswith('http'):
            if pic.startswith('/'):
                pic = self.host.rstrip('/') + pic
            else:
                pic = self.host.rstrip('/') + '/' + pic

        content = data('.yp_context').text()

        vod = {
            'vod_id': vid,
            'vod_name': name,
            'vod_pic': pic,
            'type_name': type_name,
            'vod_year': year_or_area,
            'vod_area': '',
            'vod_remarks': remarks,
            'vod_actor': actor,
            'vod_director': director,
            'vod_content': content,
            'vod_play_from': '',
            'vod_play_url': ''
        }

        # tabs: '.mi_paly_box .ypxingq_t'
        tabs = [i.text() for i in data('.mi_paly_box .ypxingq_t').items()]

        # lists: '.paly_list_btn:eq(#id) a:gt(0)'
        # 对应每个 tab 一组播放列表
        play_lists = []
        play_uls = list(data('.paly_list_btn').items())

        for idx, ul in enumerate(play_uls):
            items = []
            for i, a in enumerate(ul('a').items()):
                # a:gt(0) => 跳过第一个
                if i == 0:
                    continue
                title = a.text()
                href = a.attr('href') or ''
                if href and not href.startswith('http'):
                    if href.startswith('/'):
                        href = self.host.rstrip('/') + href
                    else:
                        href = self.host.rstrip('/') + '/' + href
                items.append(f'{title}${href}')
            play_lists.append('#'.join(items))

        vod['vod_play_from'] = '$$$'.join(tabs)
        vod['vod_play_url'] = '$$$'.join(play_lists)

        return {'list': [vod]}

    def searchContent(self, key, quick, pg="1"):
        # js: searchUrl: '/dsshiyisc/**----------fypage---.html'
        url = f'{self.host}dsshiyisc/{key}----------{pg}---.html'
        rsp = self.fetch(url, headers=self.headers)
        data = pq(rsp.text)

        videos = self.getlist(data('.mrb ul li'))
        return {
            'list': videos,
            'page': pg
        }

    def playerContent(self, flag, id, vipFlags):
        """
        对应 js 里的 lazy 解析：
        - 如果页面中存在 player_aaaa 且脚本里有 "url":"xxx.m3u8" 就直接取 m3u8
        - 否则返回原始地址
        """
        if id.startswith('http'):
            play_url = id
        else:
            if id.startswith('/'):
                play_url = self.host.rstrip('/') + id
            else:
                play_url = self.host.rstrip('/') + '/' + id

        p = 0  # 直接返回真实地址，不再二级解析

        # 如果本身就是 m3u8
        if '.m3u8' in play_url:
            return {'parse': p, 'url': play_url, 'header': self.headers}

        rsp = self.fetch(play_url, headers=self.headers)
        html = rsp.text

        # 查找包含 player_aaaa 的脚本并提取 m3u8
        # js 里正则: /\"url\"\\s*:\\s*\"([^\"]+\\.m3u8[^\"]*)\"/
        m = re.search(r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"', html)
        if m:
            real = m.group(1).replace('\\/', '/')
            return {'parse': p, 'url': real, 'header': self.headers}

        # 兜底，返回原地址
        return {'parse': p, 'url': play_url, 'header': self.headers}

    def localProxy(self, param):
        return None

    def getlist(self, data):
        """
        对应 js 一级/搜索 规则:
        '.mrb&&ul li;.dytit&&Text;.lazy&&data-original;.hdinfo&&Text;a&&href'
        """
        vlist = []
        for j in data.items():
            name = j('.dytit').text()
            pic = j('.lazy').attr('data-original') or ''
            remark = j('.hdinfo').text()
            href = j('a').attr('href') or ''

            if pic and not pic.startswith('http'):
                if pic.startswith('/'):
                    pic = self.host.rstrip('/') + pic
                else:
                    pic = self.host.rstrip('/') + '/' + pic

            vod_id = href
            vlist.append({
                'vod_id': vod_id,
                'vod_name': name,
                'vod_pic': pic,
                'vod_remarks': remark
            })
        return vlist
