#!/usr/bin/python
# coding: utf-8
import base64
import json
import re
import sys
from html import unescape
from urllib.parse import quote, unquote, urlparse

import requests

requests.packages.urllib3.disable_warnings()

try:
    sys.path.append('..')
    from base.spider import Spider
except Exception:
    class Spider(object):
        pass


class Spider(Spider):

    def __init__(self):
        super().__init__()
        self.name = '饭搭子影视'
        self.host = 'https://fdzys.net'
        self.header = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': self.host + '/'
        }
        self.cate_map = {
            'movie': 'movie/all',
            'tv': 'tv/all',
            'dongman': 'dongman/all',
            'zongyi': 'zongyi/all',
            'duanju': 'duanju/all',
            'tiyu': 'tiyu'
        }
        self.classes = [
            {'type_name': '电影', 'type_id': 'movie'},
            {'type_name': '电视剧', 'type_id': 'tv'},
            {'type_name': '动漫', 'type_id': 'dongman'},
            {'type_name': '综艺', 'type_id': 'zongyi'},
            {'type_name': '短剧', 'type_id': 'duanju'},
            {'type_name': '体育', 'type_id': 'tiyu'}
        ]
        self.filters = {
            'movie': [{'key': 'cate', 'name': '分类', 'value': [
                {'n': '全部', 'v': 'movie/all'}, {'n': '动作', 'v': 'movie/dongzuo'},
                {'n': '喜剧', 'v': 'movie/xiju'}, {'n': '爱情', 'v': 'movie/aiqing'},
                {'n': '科幻', 'v': 'movie/kehuan'}, {'n': '恐怖', 'v': 'movie/kongbupian'}
            ]}],
            'tv': [{'key': 'cate', 'name': '分类', 'value': [
                {'n': '全部', 'v': 'tv/all'}, {'n': '国产剧', 'v': 'tv/guochan'},
                {'n': '欧美剧', 'v': 'tv/oumei'}, {'n': '日本剧', 'v': 'tv/riben'},
                {'n': '韩国剧', 'v': 'tv/hanguo'}
            ]}],
            'dongman': [{'key': 'cate', 'name': '分类', 'value': [
                {'n': '全部', 'v': 'dongman/all'}, {'n': '国漫', 'v': 'dongman/guochan'},
                {'n': '日韩', 'v': 'dongman/rihan'}, {'n': '欧美', 'v': 'dongman/oumei'}
            ]}],
            'zongyi': [{'key': 'cate', 'name': '分类', 'value': [
                {'n': '全部', 'v': 'zongyi/all'}, {'n': '大陆', 'v': 'zongyi/dalu'},
                {'n': '港台', 'v': 'zongyi/goutong'}, {'n': '日韩', 'v': 'zongyi/rihan'},
                {'n': '欧美', 'v': 'zongyi/oumei'}
            ]}],
            'duanju': [{'key': 'cate', 'name': '分类', 'value': [{'n': '全部', 'v': 'duanju/all'}]}],
            'tiyu': [{'key': 'cate', 'name': '分类', 'value': [{'n': '全部', 'v': 'tiyu'}]}]
        }

    def init(self, extend=''):
        pass

    def destroy(self):
        pass

    def homeContent(self, filter=False):
        result = {'class': self.classes}
        if filter:
            result['filters'] = self.filters
        try:
            result['list'] = self.parse_list(self.fetch(self.host))
        except Exception as e:
            print('[%s] 首页获取失败: %s' % (self.name, e))
            result['list'] = []
        return result

    def homeVideoContent(self):
        try:
            return {'list': self.parse_list(self.fetch(self.host))}
        except Exception as e:
            print('[%s] 首页推荐失败: %s' % (self.name, e))
            return {'list': []}

    def categoryContent(self, tid, pg, filter, extend, flag=None):
        pg = int(pg or 1)
        extend = extend or {}
        cate = extend.get('cate') or self.cate_map.get(tid, tid)
        try:
            html = self.fetch(self.build_category_url(cate, pg))
            videos = self.parse_list(html)
            pagecount = self.parse_pagecount(html, pg)
            return {
                'list': videos,
                'page': pg,
                'pagecount': pagecount,
                'limit': len(videos),
                'total': pagecount * max(len(videos), 24)
            }
        except Exception as e:
            print('[%s] 分类失败: %s' % (self.name, e))
            return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 0, 'total': 0}

    def detailContent(self, ids):
        try:
            vod_id = ids[0] if isinstance(ids, list) else ids
            html = self.fetch(self.fix_url(vod_id), referer=self.host + '/')
            data = self.extract_player_data(html)
            vod_data = data.get('vod_data') or {}

            title = self.clean_text(vod_data.get('vod_name') or self.match_text(html, r'<h1[^>]*>(.*?)</h1>') or vod_id.rstrip('/').split('/')[-1])
            pic = self.pick_pic(self.match_all_attrs(html, ['data-src', 'data-original', 'src'], tag='img'))
            og_pic = self.match_attr_by_regex(html, r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]*>', 'content')
            pic = og_pic or pic
            actor = self.clean_text(vod_data.get('vod_actor') or self.extract_label_text(html, '主演'))
            director = self.clean_text(vod_data.get('vod_director') or self.extract_label_text(html, '导演'))
            type_name = self.clean_text(vod_data.get('vod_class') or '')
            desc = self.clean_text(self.match_text(html, r'<div[^>]+class=["\'][^"\']*(?:vod-content|intro)[^"\']*["\'][^>]*>(.*?)</div>'))
            year_match = re.search(r'(20\d{2}|19\d{2})', html)
            year = year_match.group(1) if year_match else ''
            remark = self.clean_text(self.match_text(html, r'<div[^>]+class=["\'][^"\']*score[^"\']*["\'][^>]*>(.*?)</div>'))

            play_from, play_url = self.parse_playlists(html)
            vod = {
                'vod_id': vod_id,
                'vod_name': title,
                'vod_pic': pic,
                'vod_year': year,
                'vod_area': '',
                'vod_lang': '',
                'vod_remarks': remark,
                'vod_actor': actor,
                'vod_director': director,
                'type_name': type_name,
                'vod_content': desc,
                'vod_play_from': play_from,
                'vod_play_url': play_url
            }
            return {'list': [vod]}
        except Exception as e:
            print('[%s] 详情失败: %s' % (self.name, e))
            return {'list': []}

    def searchContent(self, key, quick=False, pg=1):
        pg = int(pg or 1)
        try:
            url = '%s/yu-%s-xianguan-de-yingpian-shippin-zhibo' % (self.host, quote(key))
            if pg > 1:
                url += '?page=%s' % pg
            videos = self.parse_list(self.fetch(url))
            return {'list': videos, 'page': pg, 'pagecount': pg + 1 if videos else pg}
        except Exception as e:
            print('[%s] 搜索失败: %s' % (self.name, e))
            return {'list': [], 'page': pg, 'pagecount': 1}

    def playerContent(self, flag, id, vipFlags):
        try:
            play_url = id
            if not self.isVideoFormat(play_url):
                html = self.fetch(self.fix_url(id), referer=self.host + '/')
                data = self.extract_player_data(html)
                play_url = self.decrypt_player_url(data)
            header = {
                'User-Agent': self.header['User-Agent'],
                'Referer': self.host + '/',
                'Origin': self.host
            }
            parse = 0 if self.isVideoFormat(play_url) else 1
            return {'parse': parse, 'playUrl': '', 'url': play_url or id, 'header': json.dumps(header)}
        except Exception as e:
            print('[%s] 播放失败: %s' % (self.name, e))
            return {'parse': 1, 'playUrl': '', 'url': id, 'header': json.dumps(self.header)}

    def parse_list(self, html):
        videos = []
        seen = set()
        pattern = r'<a\b([^>]*href=["\'][^"\']*/(?:movie|tv|dongman|zongyi|duanju|tiyu)/[^"\']+["\'][^>]*)>(.*?)</a>'
        for m in re.finditer(pattern, html or '', re.I | re.S):
            attrs, body = m.group(1), m.group(2)
            if '<img' not in body.lower():
                continue
            href = self.attr(attrs, 'href')
            vod_id = self.normalize_vod_id(href)
            if not vod_id or vod_id in seen:
                continue
            seen.add(vod_id)
            img_tag = self.match_text(body, r'(<img\b[^>]*>)')
            title = self.attr(img_tag, 'alt') or self.attr(attrs, 'title') or self.clean_text(self.remove_tags(body))
            pic = self.pick_pic([self.attr(img_tag, 'data-src'), self.attr(img_tag, 'data-original'), self.attr(img_tag, 'src')])
            text = self.clean_text(self.remove_tags(body))
            remark = self.clean_text(self.remove_tags(self.match_text(body, r'<[^>]+class=["\'][^"\']*(?:remarks|tag|note)[^"\']*["\'][^>]*>(.*?)</[^>]+>')))
            if not remark:
                rm = re.search(r'(更新至[^主演简介]+|已完结[^主演简介]*|全\d+集|HDTC|HD|TC中字|TC国语|正片|完结)', text)
                remark = rm.group(1) if rm else ''
            videos.append({'vod_id': vod_id, 'vod_name': title, 'vod_pic': pic, 'vod_remarks': remark})
        return videos

    def parse_playlists(self, html):
        source_map = {}
        for m in re.finditer(r'<li\b([^>]*class=["\'][^"\']*player_name[^"\']*["\'][^>]*)>(.*?)</li>', html or '', re.I | re.S):
            sid = self.attr(m.group(1), 'data-sid')
            name = self.clean_text(self.remove_tags(m.group(2))) or ('线路%s' % sid)
            if sid:
                source_map[sid] = name

        starts = list(re.finditer(r'<div\b([^>]*id=["\']playlist[^"\']*["\'][^>]*)>', html or '', re.I))
        play_from_list = []
        play_url_list = []
        seen_source = set()
        for idx, st in enumerate(starts):
            attrs = st.group(1)
            sid = self.attr(attrs, 'data-sid') or re.sub(r'\D+', '', self.attr(attrs, 'id'))
            end = starts[idx + 1].start() if idx + 1 < len(starts) else len(html)
            block = html[st.end():end]
            source_name = source_map.get(sid, '线路%s' % (sid or (len(play_from_list) + 1)))
            if source_name in seen_source:
                continue
            eps = []
            for a in re.finditer(r'<a\b([^>]*href=["\'][^"\']+["\'][^>]*)>(.*?)</a>', block, re.I | re.S):
                href = self.attr(a.group(1), 'href')
                if not href:
                    continue
                name = self.clean_text(self.remove_tags(a.group(2))) or ('第%s集' % (len(eps) + 1))
                eps.append('%s$%s' % (name, href))
            if eps:
                seen_source.add(source_name)
                play_from_list.append(source_name)
                play_url_list.append('#'.join(eps))
        return '$$$'.join(play_from_list), '$$$'.join(play_url_list)

    def extract_player_data(self, html):
        m = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*</script>', html or '', re.I | re.S)
        if not m:
            m = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\})(?:;|\s)', html or '', re.I | re.S)
        if not m:
            return {}
        try:
            return json.loads(m.group(1))
        except Exception:
            return {}

    def decrypt_player_url(self, data):
        url = data.get('url', '') if data else ''
        encrypt = int(data.get('encrypt', 0) or 0) if data else 0
        try:
            if encrypt == 1:
                url = unquote(url)
            elif encrypt == 2:
                url = unquote(base64.b64decode(url).decode('utf-8'))
        except Exception:
            pass
        return (url or '').replace('\\/', '/')

    def parse_pagecount(self, html, pg):
        nums = [int(x) for x in re.findall(r'<a[^>]+class=["\'][^"\']*page[^"\']*["\'][^>]*>\s*(\d+)\s*</a>', html or '', re.I) if x.isdigit()]
        has_next = re.search(r'<a[^>]+href=["\'][^"\']+["\'][^>]*>[^<]*(?:下一|&gt;|>)[^<]*</a>', html or '', re.I)
        return 999 if has_next else max(max(nums) if nums else pg, pg)

    def build_category_url(self, cate, pg):
        cate = (cate or 'movie/all').strip('/')
        url = '%s/%s' % (self.host, cate)
        if pg > 1:
            url += '?page=%s' % pg
        return url

    def fetch(self, url, referer=None):
        headers = dict(self.header)
        if referer:
            headers['Referer'] = referer
        resp = requests.get(self.fix_url(url), headers=headers, timeout=20, verify=False)
        resp.encoding = 'utf-8'
        return resp.text

    def normalize_vod_id(self, href):
        if not href:
            return ''
        if href.startswith(self.host):
            href = href[len(self.host):]
        elif href.startswith('http'):
            href = urlparse(href).path
        if not href.startswith('/'):
            href = '/' + href
        if re.search(r'/(movie|tv|dongman|zongyi|duanju|tiyu)/[^/?#]+/?$', href):
            return href.rstrip('/')
        return ''

    def fix_url(self, url):
        if not url:
            return ''
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('/'):
            return self.host + url
        return url

    def pick_pic(self, pics):
        for pic in pics or []:
            pic = (pic or '').strip()
            if not pic or pic.startswith('data:image') or 'loading' in pic.lower() or 'logo' in pic.lower():
                continue
            return self.fix_url(pic)
        return ''

    def extract_label_text(self, html, label):
        m = re.search(label + r'\s*[:：]?\s*</?[^>]*>\s*([^<]+)', html or '', re.I)
        return self.clean_text(m.group(1)) if m else ''

    def match_all_attrs(self, html, attrs, tag=''):
        values = []
        tag_pattern = r'<%s\b[^>]*>' % tag if tag else r'<[^>]+>'
        for t in re.findall(tag_pattern, html or '', re.I | re.S):
            for a in attrs:
                v = self.attr(t, a)
                if v:
                    values.append(v)
        return values

    def match_attr_by_regex(self, html, tag_regex, attr):
        m = re.search(tag_regex, html or '', re.I | re.S)
        return self.attr(m.group(0), attr) if m else ''

    def match_text(self, text, pattern):
        m = re.search(pattern, text or '', re.I | re.S)
        return m.group(1) if m else ''

    def attr(self, text, name):
        if not text:
            return ''
        m = re.search(r'\s%s\s*=\s*["\']([^"\']*)["\']' % re.escape(name), text, re.I)
        return unescape(m.group(1)) if m else ''

    def remove_tags(self, text):
        text = re.sub(r'<script[\s\S]*?</script>', ' ', text or '', flags=re.I)
        text = re.sub(r'<style[\s\S]*?</style>', ' ', text, flags=re.I)
        return unescape(re.sub(r'<[^>]+>', ' ', text))

    def clean_text(self, text):
        return re.sub(r'\s+', ' ', unescape(text or '')).strip()

    def isVideoFormat(self, url):
        if not url:
            return False
        return any(x in url.lower() for x in ['.m3u8', '.mp4', '.flv', '.avi', '.mkv', '.mov', '.ts'])

    def manualVideoSniffer(self):
        return False

    def localProxy(self, param):
        return [200, 'text/plain', '']
