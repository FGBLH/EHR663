#coding=utf-8
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TVBox / 影视仓  Python源脚本
站点: 可可影视 (103.51.147.112:51120)
"""

import sys
import re
import json
import requests
from urllib.parse import quote
from pyquery import PyQuery as pq
sys.path.append('..')
from base.spider import Spider

class Spider(Spider):

    def __init__(self):
        super().__init__()
        self.site = 'https://103.51.147.112:51120'
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://103.51.147.112:51120/'
        })
        self.cateManual = {
            '电影': '1',
            '连续剧': '2',
            '动漫': '3',
            '综艺纪录': '4',
            '短剧': '6'
        }
        # 隐晦的站点标识
        self._mark = chr(26143) + chr(27827)

    def init(self, extend=""):
        pass

    def getName(self):
        return "可可影视"

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def homeContent(self, filter):
        result = {'class': [], 'filters': {}, 'list': [], 'parse': 0, 'jx': 0}
        for k, v in self.cateManual.items():
            result['class'].append({
                'type_id': str(v),
                'type_name': k
            })
        return result

    def homeVideoContent(self):
        videos = []
        try:
            url = f'{self.site}/channel/1.html'
            r = self.session.get(url, timeout=15, verify=False)
            r.encoding = 'utf-8'
            doc = pq(r.text)
            items = doc('.module-item')
            seen = set()
            for item in items.items():
                a = item.find('.v-item')
                href = a.attr('href') or ''
                vid = self.getVid(href)
                if not vid or vid in seen:
                    continue
                seen.add(vid)

                # 标题
                titles = item.find('.v-item-title')
                title = ''
                for j in range(len(titles)):
                    t = titles.eq(j).text().strip()
                    if t and t != '可可影视-kekys.com':
                        title = t
                        break

                # 图片
                pic = ''
                imgs = item.find('img')
                for j in range(len(imgs)):
                    img = imgs.eq(j)
                    src = img.attr('data-original') or ''
                    if src and 'placeholder' not in src and 'logo_placeholder' not in src:
                        pic = src
                        break
                if pic and pic.startswith('/'):
                    pic = 'https://vres.zyxpedu.com' + pic

                # 备注
                note = ''
                bottom = item.find('.v-item-bottom span')
                if bottom.length:
                    note = bottom.text().strip()

                if title:
                    videos.append({
                        'vod_id': vid,
                        'vod_name': title,
                        'vod_pic': pic,
                        'vod_remarks': note
                    })
        except Exception as e:
            print(f'homeVideoContent error: {e}')
        return {'list': videos[:24], 'parse': 0, 'jx': 0}

    def categoryContent(self, tid, pg, filter, extend):
        result = {'list': [], 'parse': 0, 'jx': 0}
        page = int(pg) if pg else 1
        try:
            url = f'{self.site}/channel/{tid}.html?page={page}'
            r = self.session.get(url, timeout=15, verify=False)
            r.encoding = 'utf-8'
            doc = pq(r.text)
            items = doc('.module-item')
            for item in items.items():
                a = item.find('.v-item')
                href = a.attr('href') or ''
                vid = self.getVid(href)
                if not vid:
                    continue

                # 标题
                titles = item.find('.v-item-title')
                title = ''
                for j in range(len(titles)):
                    t = titles.eq(j).text().strip()
                    if t and t != '可可影视-kekys.com':
                        title = t
                        break

                # 图片
                pic = ''
                imgs = item.find('img')
                for j in range(len(imgs)):
                    img = imgs.eq(j)
                    src = img.attr('data-original') or ''
                    if src and 'placeholder' not in src and 'logo_placeholder' not in src:
                        pic = src
                        break
                if pic and pic.startswith('/'):
                    pic = 'https://vres.zyxpedu.com' + pic

                # 备注
                note = ''
                bottom = item.find('.v-item-bottom span')
                if bottom.length:
                    note = bottom.text().strip()

                if title:
                    result['list'].append({
                        'vod_id': vid,
                        'vod_name': title,
                        'vod_pic': pic,
                        'vod_remarks': note
                    })
        except Exception as e:
            print(f'categoryContent error: {e}')

        result['page'] = page
        result['pagecount'] = page + 1 if len(result['list']) > 0 else page
        result['limit'] = len(result['list'])
        result['total'] = len(result['list'])
        return result

    def detailContent(self, ids):
        result = {'list': [], 'parse': 0, 'jx': 0}
        vid = ids[0] if ids else ''
        if not vid:
            return result
        try:
            url = f'{self.site}/detail/{vid}.html'
            r = self.session.get(url, timeout=15, verify=False)
            r.encoding = 'utf-8'
            html = r.text

            # 标题：从title标签提取，最可靠
            title = ''
            title_match = re.search(r'<title>(.+?)</title>', html)
            if title_match:
                title = title_match.group(1).split('-')[0].strip()
                # 去掉特殊字符水印
                title = re.sub(r'[𝕜𝕜𝕪𝕤𝟘𝟙𝕔𝕠𝕞.\s]+', ' ', title).strip()
                title = re.sub(r'\s+', ' ', title).strip()

            # 图片：从og:image提取
            pic = ''
            og_img = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html)
            if og_img:
                pic = og_img.group(1)
                if pic.startswith('/'):
                    pic = 'https://vres.zyxpedu.com' + pic

            # 简介：从meta description提取
            desc = ''
            desc_match = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', html)
            if desc_match:
                desc = desc_match.group(1).strip()

            # 播放线路和集数
            play_from = []
            play_url = []
            episodes_by_sid = {}
            sids_in_order = []
            seen_sids = set()

            # 纯正则提取所有播放链接
            all_play = re.findall(r'<a[^>]+href="(/play/\d+-(\d+)-(\d+)\.html)"[^>]+class="episode-item"[^>]*>(.*?)</a>', html, re.DOTALL)
            # 如果没匹配到，试试class在href前面的情况
            if not all_play:
                all_play = re.findall(r'<a[^>]+class="episode-item"[^>]+href="(/play/\d+-(\d+)-(\d+)\.html)"[^>]*>(.*?)</a>', html, re.DOTALL)
            for href, sid, nid, link_html in all_play:
                text = re.sub(r'<[^>]+>', '', link_html).strip()
                if not text:
                    continue
                if sid not in episodes_by_sid:
                    episodes_by_sid[sid] = []
                episodes_by_sid[sid].append(f'{text}${href}')
                if sid not in seen_sids:
                    seen_sids.add(sid)
                    sids_in_order.append(sid)

            # 线路名称
            source_labels = []
            all_labels = re.findall(r'class="source-item-label"[^>]*>([^<]+)</', html)
            for label in all_labels:
                label = label.strip()
                if label:
                    source_labels.append(label)

            for i, sid in enumerate(sids_in_order):
                if sid in episodes_by_sid and episodes_by_sid[sid]:
                    if i < len(source_labels):
                        line_name = source_labels[i]
                    else:
                        line_name = f'线路{sid}'
                    # 跳过4K线路（只有APP端能用）
                    if line_name == '4K':
                        continue
                    play_from.append(line_name)
                    play_url.append('#'.join(episodes_by_sid[sid]))

            vod = {
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': pic,
                'type_name': '',
                'vod_year': '',
                'vod_area': '',
                'vod_remarks': '',
                'vod_actor': '',
                'vod_director': self._mark,
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
            play_url = id
            if id and not id.startswith('http'):
                play_url = self.site + id

            r = self.session.get(play_url, timeout=15, verify=False)
            r.encoding = 'utf-8'

            video_url = ''
            
            patterns = [
                r'src:\s*["\']([^"\']+\.(m3u8|mp4)[^"\']*)["\']',
                r'"url"\s*:\s*"([^"]+\.(m3u8|mp4)[^"]*)"',
                r"url\s*:\s*'([^']+\.(m3u8|mp4)[^']*)'",
            ]
            
            for pat in patterns:
                m = re.search(pat, r.text, re.DOTALL)
                if m:
                    video_url = m.group(1)
                    break
            
            if not video_url:
                all_urls = re.findall(r'https?://[^\s"\'<>]+\.(m3u8|mp4)[^\s"\'<>]*', r.text)
                if all_urls:
                    for url_match in all_urls:
                        u = url_match[0] if isinstance(url_match, tuple) else url_match
                        if 'index.m3u8' in u or 'video.m3u8' in u or '.mp4' in u:
                            video_url = u
                            break
                    if not video_url:
                        video_url = all_urls[0][0] if isinstance(all_urls[0], tuple) else all_urls[0]

            if video_url:
                result['parse'] = 0
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
            # 先访问搜索页获取token
            search_url = f'{self.site}/search?k={quote(key)}'
            r = self.session.get(search_url, timeout=15, verify=False)
            r.encoding = 'utf-8'
            t_match = re.search(r'name="t" value="([^"]+)"', r.text)
            t = t_match.group(1) if t_match else ''
            
            if t:
                url = f'{self.site}/search?k={quote(key)}&t={quote(t)}'
                if page > 1:
                    url += f'&page={page}'
                r = self.session.get(url, timeout=15, verify=False)
                r.encoding = 'utf-8'

            doc = pq(r.text)
            items = doc('.search-result-item')
            for item in items.items():
                href = item.attr('href') or ''
                vid = self.getVid(href)
                if not vid:
                    continue

                # 标题
                title = ''
                title_elem = item.find('.title')
                if title_elem.length:
                    title = title_elem.text().strip()
                if not title:
                    img = item.find('img')
                    if img.length:
                        title = img.attr('alt') or img.attr('title') or ''
                        title = title.strip()

                # 图片
                pic = ''
                imgs = item.find('img')
                for j in range(len(imgs)):
                    img = imgs.eq(j)
                    src = img.attr('data-original') or img.attr('src') or ''
                    if src and 'placeholder' not in src and 'logo_placeholder' not in src:
                        pic = src
                        break
                if pic and pic.startswith('/'):
                    pic = 'https://vres.zyxpedu.com' + pic

                if title:
                    result['list'].append({
                        'vod_id': vid,
                        'vod_name': title,
                        'vod_pic': pic,
                        'vod_remarks': ''
                    })
        except Exception as e:
            print(f'searchContent error: {e}')

        result['page'] = page
        result['pagecount'] = page + 1 if len(result['list']) > 0 else page
        result['limit'] = len(result['list'])
        result['total'] = len(result['list'])
        return result

    def localProxy(self, params):
        return [200, "video/MP2T", {}, ""]

    def getVid(self, url):
        if not url:
            return ''
        m = re.search(r'/detail/(\d+)\.html', url)
        if m:
            return m.group(1)
        m = re.search(r'/play/(\d+)-', url)
        if m:
            return m.group(1)
        return ''
