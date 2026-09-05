# coding=utf-8
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import re
import json
import time
import base64
import urllib.parse
import requests
from urllib.parse import quote
from lxml import etree

sys.path.append('..')
try:
    from base.spider import Spider
except ImportError:
    class Spider(object):
        pass

try:
    requests.packages.urllib3.disable_warnings()
except Exception:
    pass


class Spider(Spider):

    def __init__(self):
        try:
            super().__init__()
        except Exception:
            pass
        self.name = "初8影视"
        self.host = "https://cjysw.cc"
        self.header = {
            'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                           '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': self.host + '/'
        }
        self._player_list = None
        self._session = None
        self._last = {}

    # ================= 基础 =================

    def getName(self):
        return self.name

    def init(self, extend=""):
        return

    def isVideoFormat(self, url):
        if not url:
            return False
        u = url.split('?')[0].split('#')[0].lower()
        return any(u.endswith(x) for x in
                   ['.m3u8', '.mp4', '.flv', '.ts', '.mkv', '.avi', '.mov', '.webm', '.mpd'])

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return

    def localProxy(self, params):
        return [200, "video/MP2T", {}, ""]

    # ================= 工具 =================

    def _sess(self):
        if self._session is None:
            s = requests.Session()
            s.trust_env = False
            self._session = s
        return self._session

    def _get(self, url, timeout=15, headers=None, retry=2):
        for i in range(retry + 1):
            try:
                r = self._sess().get(url, headers=headers or self.header,
                                     timeout=timeout, verify=False)
                r.encoding = 'utf-8'
                if r.status_code == 404:
                    return ''
                if r.status_code == 200 and r.text:
                    return r.text
            except Exception:
                pass
            if i < retry:
                time.sleep(0.6 * (i + 1))
        return ''

    def _fix(self, url):
        if not url:
            return ''
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('/'):
            return self.host + url
        return url

    def _txt(self, el):
        if el is None:
            return ''
        return ''.join(el.itertext()).strip()

    def _pic(self, el):
        if el is None:
            return ''
        imgs = [el] if el.tag == 'img' else el.xpath('.//img')
        if not imgs:
            return ''
        img = imgs[0]
        pic = (img.get('data-original') or img.get('data-src')
               or img.get('data-echo') or img.get('src') or '')
        if pic.startswith('data:image') or 'load.gif' in pic:
            pic = img.get('data-original') or img.get('data-src') or ''
        return self._fix(pic)

    def _is_limited(self, html):
        if not html:
            return False
        return ('mx-mac_msg_jump' in html) or ('请不要频繁操作' in html)

    def _throttle(self, key='search', gap=3.2):
        last = self._last.get(key, 0)
        wait = gap - (time.time() - last)
        if wait > 0:
            time.sleep(wait)
        self._last[key] = time.time()

    def _fetch_list(self, url, tries=3, key=None):
        html = ''
        for i in range(tries):
            if key:
                self._throttle(key)
            html = self._get(url)
            if self._is_limited(html):
                time.sleep(3.3)
                continue
            vlist = self._parse_list(html)
            if vlist:
                return html, vlist
            if i < tries - 1:
                time.sleep(0.8 * (i + 1))
        if self._is_limited(html):
            return '', []
        return html, self._parse_list(html)

    def _pagecount(self, html, default=1):
        total = 0
        try:
            for m in re.finditer(r'/vod(?:show|search)/[^"\']*?-(\d+)-{3}\.html', html):
                total = max(total, int(m.group(1)))
            root = etree.HTML(html)
            for a in root.xpath('//a[contains(@class,"page-link")]'):
                t = self._txt(a)
                if t.isdigit():
                    total = max(total, int(t))
        except Exception:
            pass
        return total or default

    # ================= 列表解析 =================

    # 精确 class 匹配 (整词), 防止 xxx-title / xxx-content 之类被误命中
    CLS = ('//*[contains(concat(" ", normalize-space(@class), " "), " %s ")]')

    def _parse_item(self, node):
        a = None
        if node.tag == 'a':
            a = node
        else:
            for xp in ('.//a[contains(@class,"module-card-item-poster")]',
                       './/a[contains(@class,"module-item-poster")]',
                       './/a[contains(@href,"/voddetail/")]'):
                got = node.xpath(xp)
                if got:
                    a = got[0]
                    break
        if a is None:
            return None

        m = re.search(r'/voddetail/(\d+)\.html', a.get('href', ''))
        if not m:
            return None
        vid = m.group(1)

        name = (a.get('title') or '').strip()
        if not name:
            for xp in ('.//div[contains(@class,"module-poster-item-title")]',
                       './/div[contains(@class,"module-card-item-title")]'):
                got = node.xpath(xp)
                if got:
                    name = self._txt(got[0])
                    break
        if not name:
            imgs = a.xpath('.//img')
            if imgs:
                name = (imgs[0].get('alt') or '').strip()
        if not name:
            return None

        pic = self._pic(a)
        if not pic:
            pic = self._pic(node)

        note = node.xpath('.//div[contains(@class,"module-item-note")]/text()')
        remark = note[0].strip() if note else ''

        return {"vod_id": vid, "vod_name": name, "vod_pic": pic, "vod_remarks": remark}

    def _parse_list(self, html):
        out, seen = [], set()
        if not html:
            return out
        try:
            root = etree.HTML(html)
            # 精确匹配 class, 避免命中 module-card-item-title 等子元素
            nodes = root.xpath(self.CLS % 'module-card-item')
            if not nodes:
                nodes = root.xpath(self.CLS % 'module-item')
            if not nodes:
                nodes = root.xpath('//a[contains(@href,"/voddetail/")]')
            for n in nodes:
                try:
                    v = self._parse_item(n)
                    if v and v['vod_id'] not in seen:
                        seen.add(v['vod_id'])
                        out.append(v)
                except Exception:
                    continue
        except Exception:
            pass
        return out

    # ================= 首页 =================

    def homeContent(self, filter):
        classes = [
            {"type_name": "电影", "type_id": "1"},
            {"type_name": "剧集", "type_id": "15"},
            {"type_name": "动漫", "type_id": "30"},
            {"type_name": "短剧", "type_id": "47"},
            {"type_name": "综艺", "type_id": "24"},
            {"type_name": "纪录片", "type_id": "63"},
        ]
        result = {
            "class": classes,
            "filters": self.FILTERS,
            "list": self.homeVideoContent().get('list', []),
            "parse": 0,
            "jx": 0
        }
        return result

    def homeVideoContent(self):
        _, vlist = self._fetch_list(self.host + '/', tries=2)
        if not vlist:
            _, vlist = self._fetch_list(self.host + '/vodshow/1-----------.html', tries=2)
        return {"list": vlist[:60], "parse": 0, "jx": 0}

    # ================= 分类 =================

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1
        try:
            if isinstance(extend, str) and extend:
                try:
                    extend = json.loads(extend)
                except Exception:
                    extend = {}
            if not isinstance(extend, dict):
                extend = {}

            # 子分类替换 type_id
            real_tid = str(extend.get('tid') or tid)

            segs = [''] * 12
            segs[0] = real_tid
            segs[1] = quote(extend.get('area', ''))
            segs[2] = extend.get('by', '') or 'time'
            segs[3] = quote(extend.get('class', ''))
            segs[4] = quote(extend.get('lang', ''))
            segs[5] = quote(extend.get('letter', ''))
            segs[8] = str(page)
            segs[11] = quote(extend.get('year', ''))

            url = '%s/vodshow/%s.html' % (self.host, '-'.join(segs))
            html, vlist = self._fetch_list(url)
            pc = self._pagecount(html, 1 if not vlist else page)

            return {
                'list': vlist,
                'page': page,
                'pagecount': pc,
                'limit': len(vlist) or 45,
                'total': (pc * len(vlist)) if vlist else 0
            }
        except Exception:
            return {'list': [], 'page': page, 'pagecount': 1, 'limit': 45, 'total': 0}

    # ================= 详情 =================

    def detailContent(self, ids):
        try:
            vid = ids[0] if isinstance(ids, (list, tuple)) else ids
            vid = str(vid).split('/')[-1].replace('.html', '')
            html = self._get('%s/voddetail/%s.html' % (self.host, vid))
            if not html:
                return {'list': [], 'parse': 0, 'jx': 0}
            root = etree.HTML(html)

            # 标题
            name = ''
            h1 = root.xpath('//div[contains(@class,"module-info-heading")]/h1')
            if h1:
                name = self._txt(h1[0])
            if not name:
                t = root.xpath('//title/text()')
                if t:
                    name = re.split(r'[-_|]', t[0])[0].strip()

            # 封面
            pic = ''
            box = root.xpath('//div[contains(@class,"module-info-poster")]')
            if box:
                pic = self._pic(box[0])

            # 标签: 年份 / 地区 / 剧情
            year = area = vclass = ''
            for a in root.xpath('//div[contains(@class,"module-info-tag")]//a'):
                t = self._txt(a)
                href = a.get('href', '')
                if re.match(r'^\d{4}$', t):
                    year = year or t
                elif re.search(r'/vodshow/\d+-[^-]+-', href):
                    area = area or t
                elif re.search(r'/vodshow/\d+---[^-]+-', href):
                    vclass = vclass or t
                elif not area and t:
                    area = t

            # 导演 / 主演 / 备注
            director = actor = remarks = ''
            for item in root.xpath('//div[contains(@class,"module-info-item")]'):
                key = item.xpath('./span[contains(@class,"module-info-item-title")]/text()')
                key = key[0].strip() if key else ''
                cont = item.xpath('.//div[contains(@class,"module-info-item-content")]') or \
                       item.xpath('.//p[contains(@class,"module-info-item-content")]')
                if not cont:
                    continue
                links = [x.strip() for x in cont[0].xpath('.//a/text()') if x.strip()]
                val = ','.join(links) if links else self._txt(cont[0])
                if '导演' in key:
                    director = val
                elif '主演' in key:
                    actor = val
                elif '备注' in key or '更新' in key:
                    remarks = remarks or val

            # 简介
            content = ''
            desc = root.xpath('//div[contains(@class,"module-info-introduction-content")]')
            if desc:
                content = self._txt(desc[0])
            content = re.sub(r'\s*展开\s*$', '', content).strip()

            # 播放线路
            froms = root.xpath('//div[contains(@class,"module-tab-item")]/@data-dropdown-value')
            if not froms:
                froms = [x.strip() for x in
                         root.xpath('//div[contains(@class,"module-tab-item")]//span/text()')]
            froms = [f.strip() for f in froms if f and f.strip()]

            boxes, seen = [], set()
            for b in root.xpath(self.CLS % 'module-play-list'):
                links = b.xpath('.//a[contains(@href,"/vodplay/")]')
                if not links:
                    continue
                key = links[0].get('href', '')
                if key in seen:
                    continue
                seen.add(key)
                boxes.append(links)

            play_from, play_url = [], []
            for i, links in enumerate(boxes):
                eps = []
                for a in links:
                    ep = self._txt(a)
                    href = a.get('href', '')
                    if not ep or not href:
                        continue
                    eps.append('%s$%s' % (ep.replace('$', ' ').replace('#', ' '),
                                          self._fix(href)))
                if not eps:
                    continue
                play_from.append(froms[i] if i < len(froms) else ('线路%d' % (i + 1)))
                play_url.append('#'.join(eps))

            detail = {
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic,
                "type_name": vclass,
                "vod_year": year,
                "vod_area": area,
                "vod_remarks": remarks,
                "vod_actor": actor,
                "vod_director": director,
                "vod_content": content,
                "vod_play_from": "$$$".join(play_from) if play_from else "默认",
                "vod_play_url": "$$$".join(play_url)
            }
            return {'list': [detail], 'parse': 0, 'jx': 0}
        except Exception:
            return {'list': [], 'parse': 0, 'jx': 0}

    # ================= 播放 =================

    def _player_conf(self):
        if self._player_list is not None:
            return self._player_list
        self._player_list = {}
        try:
            js = self._get(self.host + '/static/js/playerconfig.js')
            m = re.search(r'player_list\s*=\s*', js)
            if m:
                start = js.index('{', m.end())
                depth = 0
                for i in range(start, len(js)):
                    if js[i] == '{':
                        depth += 1
                    elif js[i] == '}':
                        depth -= 1
                        if depth == 0:
                            self._player_list = json.loads(js[start:i + 1])
                            break
        except Exception:
            self._player_list = {}
        return self._player_list

    def _player_aaaa(self, html):
        m = re.search(r'player_aaaa\s*=\s*', html)
        if not m:
            return None
        try:
            start = html.index('{', m.end())
            depth = 0
            for i in range(start, len(html)):
                if html[i] == '{':
                    depth += 1
                elif html[i] == '}':
                    depth -= 1
                    if depth == 0:
                        return json.loads(html[start:i + 1])
        except Exception:
            return None
        return None

    def playerContent(self, flag, id, vipFlags):
        play_page = id if str(id).startswith('http') else self._fix(id)
        headers = {
            'User-Agent': self.header['User-Agent'],
            'Referer': self.host + '/'
        }
        result = {'parse': 1, 'url': play_page, 'playUrl': '', 'header': json.dumps(headers)}
        try:
            html = self._get(play_page)
            data = self._player_aaaa(html) or {}
            url = data.get('url', '')
            src = data.get('from', '')
            enc = data.get('encrypt', 0)

            if url:
                if enc == 1:
                    url = urllib.parse.unquote(url)
                elif enc == 2:
                    try:
                        url = urllib.parse.unquote(base64.b64decode(url).decode('utf-8'))
                    except Exception:
                        pass
                url = url.replace('\\/', '/')

            # 非直链 (爱奇艺/B站等官方页) -> 走站点解析接口
            if url and not self.isVideoFormat(url) and src:
                info = self._player_conf().get(src, {})
                if str(info.get('ps', '0')) == '1' and info.get('parse'):
                    api = info['parse'].replace('&player', '')
                    try:
                        r = self._sess().get(api + url, headers=headers, timeout=20, verify=False)
                        r.encoding = 'utf-8'
                        j = json.loads(r.text)
                        got = j.get('url') or j.get('play_url') or ''
                        if got and str(j.get('code', 200)) in ('1', '200'):
                            url = got.replace('\\/', '/')
                    except Exception:
                        pass

            if not url:
                found = re.findall(r'(https?:[^\s"\'<>\\]+\.(?:m3u8|mp4)[^\s"\'<>\\]*)', html)
                if found:
                    url = found[0].replace('\\/', '/')

            if url:
                url = self._fix(url)
                result['url'] = url
                result['parse'] = 0 if self.isVideoFormat(url) else 1
        except Exception:
            pass
        return result

    # ================= 搜索 =================

    def searchContent(self, key, quick, pg='1'):
        page = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1
        try:
            segs = [''] * 14
            segs[0] = quote(str(key))
            segs[10] = str(page)
            url = '%s/vodsearch/%s.html' % (self.host, '-'.join(segs))
            html, vlist = self._fetch_list(url, key='search')
            pc = self._pagecount(html, page if vlist else 1)

            # 回退: 被限流或无结果时, 首页用联想接口补全
            if not vlist and page == 1:
                try:
                    api = '%s/index.php/ajax/suggest?mid=1&wd=%s&limit=30' % (
                        self.host, quote(str(key)))
                    j = json.loads(self._get(api))
                    for it in (j.get('list') or []):
                        vlist.append({
                            "vod_id": str(it.get('id', '')),
                            "vod_name": it.get('name', ''),
                            "vod_pic": self._fix(it.get('pic', '')),
                            "vod_remarks": ""
                        })
                    pc = 1
                except Exception:
                    pass

            return {'list': vlist, 'page': page, 'pagecount': pc,
                    'limit': len(vlist) or 16, 'total': pc * (len(vlist) or 16)}
        except Exception:
            return {'list': [], 'page': page, 'pagecount': 1, 'limit': 16, 'total': 0}

    # ================= 筛选器 (实爬站点生成) =================

    FILTERS = json.loads(r'''{"1": [{"key": "tid", "name": "类型", "value": [{"n": "全部", "v": ""}, {"n": "动作片", "v": "2"}, {"n": "喜剧片", "v": "3"}, {"n": "爱情片", "v": "4"}, {"n": "科幻片", "v": "5"}, {"n": "恐怖片", "v": "6"}, {"n": "剧情片", "v": "7"}, {"n": "战争片", "v": "8"}, {"n": "悬疑片", "v": "10"}, {"n": "动画片", "v": "11"}, {"n": "犯罪片", "v": "12"}, {"n": "奇幻片", "v": "13"}, {"n": "其他片", "v": "67"}]}, {"key": "area", "name": "地区", "value": [{"n": "全部", "v": ""}, {"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"}, {"n": "台湾", "v": "台湾"}, {"n": "美国", "v": "美国"}, {"n": "法国", "v": "法国"}, {"n": "英国", "v": "英国"}, {"n": "日本", "v": "日本"}, {"n": "韩国", "v": "韩国"}, {"n": "德国", "v": "德国"}, {"n": "泰国", "v": "泰国"}, {"n": "印度", "v": "印度"}, {"n": "意大利", "v": "意大利"}, {"n": "西班牙", "v": "西班牙"}, {"n": "加拿大", "v": "加拿大"}, {"n": "其他", "v": "其他"}]}, {"key": "lang", "name": "语言", "value": [{"n": "全部", "v": ""}, {"n": "国语", "v": "国语"}, {"n": "英语", "v": "英语"}, {"n": "粤语", "v": "粤语"}, {"n": "闽南语", "v": "闽南语"}, {"n": "韩语", "v": "韩语"}, {"n": "日语", "v": "日语"}, {"n": "法语", "v": "法语"}, {"n": "德语", "v": "德语"}, {"n": "其它", "v": "其它"}]}, {"key": "year", "name": "年份", "value": [{"n": "全部", "v": ""}, {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"}, {"n": "2024", "v": "2024"}, {"n": "2023", "v": "2023"}, {"n": "2022", "v": "2022"}, {"n": "2021", "v": "2021"}, {"n": "2020", "v": "2020"}, {"n": "2019", "v": "2019"}, {"n": "2018", "v": "2018"}, {"n": "2017", "v": "2017"}, {"n": "2016", "v": "2016"}, {"n": "2015", "v": "2015"}, {"n": "2014", "v": "2014"}]}, {"key": "letter", "name": "字母", "value": [{"n": "全部", "v": ""}, {"n": "A", "v": "A"}, {"n": "B", "v": "B"}, {"n": "C", "v": "C"}, {"n": "D", "v": "D"}, {"n": "E", "v": "E"}, {"n": "F", "v": "F"}, {"n": "G", "v": "G"}, {"n": "H", "v": "H"}, {"n": "I", "v": "I"}, {"n": "J", "v": "J"}, {"n": "K", "v": "K"}, {"n": "L", "v": "L"}, {"n": "M", "v": "M"}, {"n": "N", "v": "N"}, {"n": "O", "v": "O"}, {"n": "P", "v": "P"}, {"n": "Q", "v": "Q"}, {"n": "R", "v": "R"}, {"n": "S", "v": "S"}, {"n": "T", "v": "T"}, {"n": "U", "v": "U"}, {"n": "V", "v": "V"}, {"n": "W", "v": "W"}, {"n": "X", "v": "X"}, {"n": "Y", "v": "Y"}, {"n": "Z", "v": "Z"}, {"n": "0-9", "v": "0"}]}, {"key": "by", "name": "排序", "value": [{"n": "时间", "v": "time"}, {"n": "人气", "v": "hits"}, {"n": "评分", "v": "score"}]}], "15": [{"key": "tid", "name": "类型", "value": [{"n": "全部", "v": ""}, {"n": "国产剧", "v": "16"}, {"n": "香港剧", "v": "17"}, {"n": "台湾剧", "v": "18"}, {"n": "美国剧", "v": "19"}, {"n": "韩国剧", "v": "20"}, {"n": "日本剧", "v": "21"}, {"n": "海外剧", "v": "22"}, {"n": "泰剧", "v": "23"}, {"n": "其他剧", "v": "68"}]}, {"key": "area", "name": "地区", "value": [{"n": "全部", "v": ""}, {"n": "内地", "v": "内地"}, {"n": "韩国", "v": "韩国"}, {"n": "香港", "v": "香港"}, {"n": "台湾", "v": "台湾"}, {"n": "日本", "v": "日本"}, {"n": "美国", "v": "美国"}, {"n": "泰国", "v": "泰国"}, {"n": "英国", "v": "英国"}, {"n": "新加坡", "v": "新加坡"}, {"n": "其他", "v": "其他"}]}, {"key": "lang", "name": "语言", "value": [{"n": "全部", "v": ""}, {"n": "国语", "v": "国语"}, {"n": "英语", "v": "英语"}, {"n": "粤语", "v": "粤语"}, {"n": "闽南语", "v": "闽南语"}, {"n": "韩语", "v": "韩语"}, {"n": "日语", "v": "日语"}, {"n": "其它", "v": "其它"}]}, {"key": "year", "name": "年份", "value": [{"n": "全部", "v": ""}, {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"}, {"n": "2024", "v": "2024"}, {"n": "2023", "v": "2023"}, {"n": "2022", "v": "2022"}, {"n": "2021", "v": "2021"}, {"n": "2020", "v": "2020"}, {"n": "2019", "v": "2019"}, {"n": "2018", "v": "2018"}, {"n": "2017", "v": "2017"}, {"n": "2016", "v": "2016"}, {"n": "2015", "v": "2015"}, {"n": "2014", "v": "2014"}]}, {"key": "letter", "name": "字母", "value": [{"n": "全部", "v": ""}, {"n": "A", "v": "A"}, {"n": "B", "v": "B"}, {"n": "C", "v": "C"}, {"n": "D", "v": "D"}, {"n": "E", "v": "E"}, {"n": "F", "v": "F"}, {"n": "G", "v": "G"}, {"n": "H", "v": "H"}, {"n": "I", "v": "I"}, {"n": "J", "v": "J"}, {"n": "K", "v": "K"}, {"n": "L", "v": "L"}, {"n": "M", "v": "M"}, {"n": "N", "v": "N"}, {"n": "O", "v": "O"}, {"n": "P", "v": "P"}, {"n": "Q", "v": "Q"}, {"n": "R", "v": "R"}, {"n": "S", "v": "S"}, {"n": "T", "v": "T"}, {"n": "U", "v": "U"}, {"n": "V", "v": "V"}, {"n": "W", "v": "W"}, {"n": "X", "v": "X"}, {"n": "Y", "v": "Y"}, {"n": "Z", "v": "Z"}, {"n": "0-9", "v": "0"}]}, {"key": "by", "name": "排序", "value": [{"n": "时间", "v": "time"}, {"n": "人气", "v": "hits"}, {"n": "评分", "v": "score"}]}], "30": [{"key": "tid", "name": "类型", "value": [{"n": "全部", "v": ""}, {"n": "国产动漫", "v": "31"}, {"n": "日韩动漫", "v": "32"}, {"n": "欧美动漫", "v": "33"}, {"n": "港台动漫", "v": "34"}, {"n": "海外动漫", "v": "35"}]}, {"key": "area", "name": "地区", "value": [{"n": "全部", "v": ""}, {"n": "内地", "v": "内地"}, {"n": "日本", "v": "日本"}, {"n": "欧美", "v": "欧美"}, {"n": "其他", "v": "其他"}]}, {"key": "lang", "name": "语言", "value": [{"n": "全部", "v": ""}, {"n": "国语", "v": "国语"}, {"n": "英语", "v": "英语"}, {"n": "粤语", "v": "粤语"}, {"n": "闽南语", "v": "闽南语"}, {"n": "韩语", "v": "韩语"}, {"n": "日语", "v": "日语"}, {"n": "其它", "v": "其它"}]}, {"key": "year", "name": "年份", "value": [{"n": "全部", "v": ""}, {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"}, {"n": "2024", "v": "2024"}, {"n": "2023", "v": "2023"}, {"n": "2022", "v": "2022"}, {"n": "2021", "v": "2021"}, {"n": "2020", "v": "2020"}, {"n": "2019", "v": "2019"}, {"n": "2018", "v": "2018"}, {"n": "2017", "v": "2017"}, {"n": "2016", "v": "2016"}, {"n": "2015", "v": "2015"}, {"n": "2014", "v": "2014"}]}, {"key": "letter", "name": "字母", "value": [{"n": "全部", "v": ""}, {"n": "A", "v": "A"}, {"n": "B", "v": "B"}, {"n": "C", "v": "C"}, {"n": "D", "v": "D"}, {"n": "E", "v": "E"}, {"n": "F", "v": "F"}, {"n": "G", "v": "G"}, {"n": "H", "v": "H"}, {"n": "I", "v": "I"}, {"n": "J", "v": "J"}, {"n": "K", "v": "K"}, {"n": "L", "v": "L"}, {"n": "M", "v": "M"}, {"n": "N", "v": "N"}, {"n": "O", "v": "O"}, {"n": "P", "v": "P"}, {"n": "Q", "v": "Q"}, {"n": "R", "v": "R"}, {"n": "S", "v": "S"}, {"n": "T", "v": "T"}, {"n": "U", "v": "U"}, {"n": "V", "v": "V"}, {"n": "W", "v": "W"}, {"n": "X", "v": "X"}, {"n": "Y", "v": "Y"}, {"n": "Z", "v": "Z"}, {"n": "0-9", "v": "0"}]}, {"key": "by", "name": "排序", "value": [{"n": "时间", "v": "time"}, {"n": "人气", "v": "hits"}, {"n": "评分", "v": "score"}]}], "47": [{"key": "tid", "name": "类型", "value": [{"n": "全部", "v": ""}, {"n": "有声动漫", "v": "48"}, {"n": "女频恋爱", "v": "49"}, {"n": "反转爽剧", "v": "50"}, {"n": "脑洞悬疑", "v": "51"}, {"n": "年代穿越", "v": "52"}, {"n": "古装仙侠", "v": "53"}, {"n": "现代都市", "v": "54"}, {"n": "漫剧", "v": "66"}]}, {"key": "year", "name": "年份", "value": [{"n": "全部", "v": ""}, {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"}, {"n": "2024", "v": "2024"}, {"n": "2023", "v": "2023"}, {"n": "2022", "v": "2022"}, {"n": "2021", "v": "2021"}, {"n": "2020", "v": "2020"}, {"n": "2019", "v": "2019"}, {"n": "2018", "v": "2018"}, {"n": "2017", "v": "2017"}, {"n": "2016", "v": "2016"}, {"n": "2015", "v": "2015"}, {"n": "2014", "v": "2014"}]}, {"key": "letter", "name": "字母", "value": [{"n": "全部", "v": ""}, {"n": "A", "v": "A"}, {"n": "B", "v": "B"}, {"n": "C", "v": "C"}, {"n": "D", "v": "D"}, {"n": "E", "v": "E"}, {"n": "F", "v": "F"}, {"n": "G", "v": "G"}, {"n": "H", "v": "H"}, {"n": "I", "v": "I"}, {"n": "J", "v": "J"}, {"n": "K", "v": "K"}, {"n": "L", "v": "L"}, {"n": "M", "v": "M"}, {"n": "N", "v": "N"}, {"n": "O", "v": "O"}, {"n": "P", "v": "P"}, {"n": "Q", "v": "Q"}, {"n": "R", "v": "R"}, {"n": "S", "v": "S"}, {"n": "T", "v": "T"}, {"n": "U", "v": "U"}, {"n": "V", "v": "V"}, {"n": "W", "v": "W"}, {"n": "X", "v": "X"}, {"n": "Y", "v": "Y"}, {"n": "Z", "v": "Z"}, {"n": "0-9", "v": "0"}]}, {"key": "by", "name": "排序", "value": [{"n": "时间", "v": "time"}, {"n": "人气", "v": "hits"}, {"n": "评分", "v": "score"}]}], "24": [{"key": "tid", "name": "类型", "value": [{"n": "全部", "v": ""}, {"n": "大陆综艺", "v": "25"}, {"n": "日韩综艺", "v": "26"}, {"n": "港台综艺", "v": "27"}, {"n": "欧美综艺", "v": "28"}, {"n": "演唱会", "v": "29"}]}, {"key": "area", "name": "地区", "value": [{"n": "全部", "v": ""}, {"n": "内地", "v": "内地"}, {"n": "港台", "v": "港台"}, {"n": "日韩", "v": "日韩"}, {"n": "欧美", "v": "欧美"}]}, {"key": "lang", "name": "语言", "value": [{"n": "全部", "v": ""}, {"n": "国语", "v": "国语"}, {"n": "英语", "v": "英语"}, {"n": "粤语", "v": "粤语"}, {"n": "闽南语", "v": "闽南语"}, {"n": "韩语", "v": "韩语"}, {"n": "日语", "v": "日语"}, {"n": "其它", "v": "其它"}]}, {"key": "year", "name": "年份", "value": [{"n": "全部", "v": ""}, {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"}, {"n": "2024", "v": "2024"}, {"n": "2023", "v": "2023"}, {"n": "2022", "v": "2022"}, {"n": "2021", "v": "2021"}, {"n": "2020", "v": "2020"}, {"n": "2019", "v": "2019"}, {"n": "2018", "v": "2018"}, {"n": "2017", "v": "2017"}, {"n": "2016", "v": "2016"}, {"n": "2015", "v": "2015"}, {"n": "2014", "v": "2014"}]}, {"key": "letter", "name": "字母", "value": [{"n": "全部", "v": ""}, {"n": "A", "v": "A"}, {"n": "B", "v": "B"}, {"n": "C", "v": "C"}, {"n": "D", "v": "D"}, {"n": "E", "v": "E"}, {"n": "F", "v": "F"}, {"n": "G", "v": "G"}, {"n": "H", "v": "H"}, {"n": "I", "v": "I"}, {"n": "J", "v": "J"}, {"n": "K", "v": "K"}, {"n": "L", "v": "L"}, {"n": "M", "v": "M"}, {"n": "N", "v": "N"}, {"n": "O", "v": "O"}, {"n": "P", "v": "P"}, {"n": "Q", "v": "Q"}, {"n": "R", "v": "R"}, {"n": "S", "v": "S"}, {"n": "T", "v": "T"}, {"n": "U", "v": "U"}, {"n": "V", "v": "V"}, {"n": "W", "v": "W"}, {"n": "X", "v": "X"}, {"n": "Y", "v": "Y"}, {"n": "Z", "v": "Z"}, {"n": "0-9", "v": "0"}]}, {"key": "by", "name": "排序", "value": [{"n": "时间", "v": "time"}, {"n": "人气", "v": "hits"}, {"n": "评分", "v": "score"}]}], "63": [{"key": "area", "name": "地区", "value": [{"n": "全部", "v": ""}, {"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"}, {"n": "台湾", "v": "台湾"}, {"n": "美国", "v": "美国"}, {"n": "法国", "v": "法国"}, {"n": "英国", "v": "英国"}, {"n": "日本", "v": "日本"}, {"n": "韩国", "v": "韩国"}, {"n": "德国", "v": "德国"}, {"n": "泰国", "v": "泰国"}, {"n": "印度", "v": "印度"}, {"n": "意大利", "v": "意大利"}, {"n": "西班牙", "v": "西班牙"}, {"n": "加拿大", "v": "加拿大"}, {"n": "其他", "v": "其他"}]}, {"key": "lang", "name": "语言", "value": [{"n": "全部", "v": ""}, {"n": "国语", "v": "国语"}, {"n": "英语", "v": "英语"}, {"n": "粤语", "v": "粤语"}, {"n": "闽南语", "v": "闽南语"}, {"n": "韩语", "v": "韩语"}, {"n": "日语", "v": "日语"}, {"n": "法语", "v": "法语"}, {"n": "德语", "v": "德语"}, {"n": "其它", "v": "其它"}]}, {"key": "year", "name": "年份", "value": [{"n": "全部", "v": ""}, {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"}, {"n": "2024", "v": "2024"}, {"n": "2023", "v": "2023"}, {"n": "2022", "v": "2022"}, {"n": "2021", "v": "2021"}, {"n": "2020", "v": "2020"}, {"n": "2019", "v": "2019"}, {"n": "2018", "v": "2018"}, {"n": "2017", "v": "2017"}, {"n": "2016", "v": "2016"}, {"n": "2015", "v": "2015"}, {"n": "2014", "v": "2014"}]}, {"key": "letter", "name": "字母", "value": [{"n": "全部", "v": ""}, {"n": "A", "v": "A"}, {"n": "B", "v": "B"}, {"n": "C", "v": "C"}, {"n": "D", "v": "D"}, {"n": "E", "v": "E"}, {"n": "F", "v": "F"}, {"n": "G", "v": "G"}, {"n": "H", "v": "H"}, {"n": "I", "v": "I"}, {"n": "J", "v": "J"}, {"n": "K", "v": "K"}, {"n": "L", "v": "L"}, {"n": "M", "v": "M"}, {"n": "N", "v": "N"}, {"n": "O", "v": "O"}, {"n": "P", "v": "P"}, {"n": "Q", "v": "Q"}, {"n": "R", "v": "R"}, {"n": "S", "v": "S"}, {"n": "T", "v": "T"}, {"n": "U", "v": "U"}, {"n": "V", "v": "V"}, {"n": "W", "v": "W"}, {"n": "X", "v": "X"}, {"n": "Y", "v": "Y"}, {"n": "Z", "v": "Z"}, {"n": "0-9", "v": "0"}]}, {"key": "by", "name": "排序", "value": [{"n": "时间", "v": "time"}, {"n": "人气", "v": "hits"}, {"n": "评分", "v": "score"}]}]}''')
