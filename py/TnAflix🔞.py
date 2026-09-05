#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, re, json, time, gzip, ssl

sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        pass

try:
    from urllib.request import Request, urlopen, build_opener, HTTPSHandler
    from urllib.parse import quote
except ImportError:
    from urllib import quote
    from urllib2 import Request, urlopen, build_opener, HTTPSHandler


class Spider(BaseSpider):
    host = 'https://www.tnaflix.com'
    searchable = True
    filterable = True

    _CATS = [
        (1, '最新视频', 'featured'),
        (2, 'Amateur 业余', 'amateur-porn'),
        (3, 'Anal 肛交', 'anal-porn'),
        (4, 'Arabian 阿拉伯', 'arabian-porn'),
        (5, 'Asian 亚洲', 'asian-porn'),
        (6, 'Babe 美女', 'babe-videos'),
        (7, 'BBW 胖美人', 'bbw-porn'),
        (8, 'BDSM 虐恋', 'bdsm-porn'),
        (9, 'Bizarre 猎奇', 'bizarre-porn'),
        (10, 'Blonde 金发', 'blonde-porn'),
        (11, 'Blowjob 口交', 'blowjob-videos'),
        (12, 'Brunette 棕发', 'brunette-porn'),
        (13, 'Bukkake 颜射', 'bukkake-porn'),
        (14, 'Cartoon 卡通', 'cartoon-porn'),
        (15, 'Celebrity 名人', 'celebrity-porn'),
        (16, 'Classic 经典', 'classic-porn'),
        (17, 'Czech 捷克', 'czech-porn'),
        (18, 'Ebony 黑美人', 'ebony-porn'),
        (19, 'Euro 欧洲', 'euro-porn'),
        (20, 'Facial 颜面', 'facial-porn'),
        (21, 'Fat 肥女', 'fat-porn'),
        (22, 'Feet 恋足', 'feet-porn'),
        (23, 'French 法国', 'french-porn'),
        (24, 'Gay 男同', 'gay-porn'),
        (25, 'German 德国', 'german-porn'),
        (26, 'Granny 老太太', 'granny-porn'),
        (27, 'Hairy 多毛', 'hairy-porn'),
        (28, 'Handjobs 手交', 'handjobs-porn'),
        (29, 'Hardcore 重口味', 'hardcore-porn'),
        (30, 'Hentai 动漫', 'hentai-porn'),
        (31, 'Homemade 自拍', 'homemade-porn'),
        (32, 'Indian 印度', 'indian-porn'),
        (33, 'Interracial 跨种族', 'interracial-porn'),
        (34, 'Japanese 日本', 'japanese-porn'),
        (35, 'Latina 拉丁', 'latina-porn'),
        (36, 'Lesbian 女同', 'lesbian-porn'),
        (37, 'Massage 按摩', 'massage-porn'),
        (38, 'Mature 熟女', 'mature-porn'),
        (39, 'MILF 熟母', 'milf-porn'),
        (40, 'Petite 娇小', 'petite-porn'),
        (41, 'POV 第一视角', 'pov-porn'),
        (42, 'Pregnant 孕妇', 'pregnant-porn'),
        (43, 'Public 公共', 'public-porn'),
        (44, 'Reality 真实', 'reality-porn'),
        (45, 'Redhead 红发', 'redhead-porn'),
        (46, 'Russian 俄罗斯', 'russian-porn'),
        (47, 'Shemale 人妖', 'shemale-porn'),
        (48, 'Solo 独演', 'solo-porn'),
        (49, 'Storyline 剧情', 'storyline-porn'),
        (50, 'Teen 少女', 'teen-porn'),
        (51, 'Thai 泰国', 'thai-porn'),
        (52, 'VR 虚拟现实', 'vr-porn'),
        (53, 'Pornstars 明星', 'pornstars'),
    ]
    _CAT_MAP = {str(cid): path for cid, name, path in _CATS}

    def getName(self):
        return 'TNAFlix'

    def isVideoFormat(self, url):
        return bool(url and re.search(r'\.(m3u8|mp4|ts|flv|mkv)', url, re.I))

    def init(self, extend=""):
        pass

    def destroy(self):
        pass

    def localProxy(self, param):
        return [404, 'text/plain', '']

    def _http_get(self, url, timeout=20, retries=2):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        opener = build_opener(HTTPSHandler(context=ctx))
        headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Accept-Encoding': 'gzip',
            'Referer': self.host + '/',
        }
        for i in range(retries):
            try:
                req = Request(url, headers=headers)
                resp = opener.open(req, timeout=timeout)
                data = resp.read()
                if resp.headers.get('Content-Encoding') == 'gzip':
                    try:
                        data = gzip.decompress(data)
                    except Exception:
                        pass
                return data.decode('utf-8', errors='replace')
            except Exception:
                time.sleep(1)
        return ''

    def _fetch(self, url):
        return self._http_get(url)

    def _parse_cards(self, html):
        items = []
        parts = re.split(r'<div data-vid="(\d+)"', html)
        for i in range(1, len(parts), 2):
            vid = parts[i]
            part = parts[i + 1] if i + 1 < len(parts) else ''
            m = re.search(r'href="([^"]*/video' + vid + r')"', part)
            vod_id = m.group(1) if m else vid
            m = re.search(r'class="video-title text-break">\s*([^<]+)', part)
            title = m.group(1).strip() if m else ''
            m = re.search(r'<img[^>]+data-src="([^"]+)"', part)
            pic = m.group(1) if m else ''
            if not pic:
                m = re.search(r'<img[^>]+src="([^"]+)"', part)
                pic = m.group(1) if m else ''
            m = re.search(r'video-duration[^>]*>\s*([\d:]+)', part)
            duration = m.group(1) if m else ''
            m = re.search(r'icon-eye[^>]*></i>([\d.,K]+)', part)
            views = m.group(1) if m else ''
            remark = duration
            if views:
                remark = (remark + ' | ' if remark else '') + views + '次'
            items.append({
                'vod_id': vod_id,
                'vod_name': title or vid,
                'vod_pic': pic,
                'vod_remarks': remark,
            })
        return items

    def homeContent(self, filter):
        try:
            classes = [{'type_id': str(cid), 'type_name': name} for cid, name, _ in self._CATS]
            return {'class': classes, 'filters': {}}
        except Exception:
            return {'class': [], 'filters': {}}

    def homeVideoContent(self):
        try:
            html = self._fetch(self.host + '/featured')
            items = self._parse_cards(html)
            return {'list': items}
        except Exception:
            return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            path = self._CAT_MAP.get(str(tid), 'featured')
            if int(pg) <= 1:
                url = f'{self.host}/{path}'
            else:
                url = f'{self.host}/{path}/featured/{pg}'
            html = self._fetch(url)
            items = self._parse_cards(html)
            max_pg = 1
            for p in re.findall(rf'/{path}/featured/(\d+)', html):
                try:
                    max_pg = max(max_pg, int(p))
                except Exception:
                    pass
            return {
                'page': int(pg) if pg else 1,
                'pagecount': max_pg,
                'limit': 60,
                'total': len(items),
                'list': items,
            }
        except Exception:
            return {'page': 1, 'pagecount': 1, 'limit': 60, 'total': 0, 'list': []}

    def detailContent(self, ids):
        try:
            did = str(ids[0] if isinstance(ids, list) else ids)
            if did.startswith('http'):
                url = did
            elif '/video' in did:
                url = f'{self.host}/{did}'
            else:
                html = self._fetch(f'{self.host}/search?what={did}')
                m = re.search(r'href="([^"]*/video' + did + r')"', html)
                if not m:
                    return {'list': []}
                url = m.group(1)
                if not url.startswith('http'):
                    url = self.host + url

            detail_html = self._fetch(url)
            title = ''
            m = re.search(r'<title>([^<]+)</title>', detail_html)
            if m:
                title = m.group(1).strip()
            pic = ''
            m = re.search(r'<meta property="og:image" content="([^"]+)"', detail_html)
            if m:
                pic = m.group(1)
            sources = re.findall(r'<source[^>]+src="([^"]+)"', detail_html)
            if not sources:
                sources = re.findall(r'<video[^>]+src="([^"]+)"', detail_html)

            if not sources:
                return {'list': []}
            play_parts = []
            seen = set()
            for src in sources:
                m = re.search(r'(\d{3,4})p', src)
                res = m.group(1) if m else 'auto'
                if res in seen:
                    continue
                seen.add(res)
                play_parts.append(f'{res}p${src}')
            if not play_parts:
                play_parts.append(f'播放${sources[0]}')
            vod = {
                'vod_id': did,
                'vod_name': title or did,
                'vod_pic': pic,
                'vod_content': title,
                'vod_play_from': 'TNAFlix',
                'vod_play_url': '#'.join(play_parts),
                'vod_remarks': 'MP4',
            }
            return {'list': [vod]}
        except Exception:
            return {'list': []}

    def searchContent(self, key, quick, pg=1):
        try:
            url = f'{self.host}/search?what={quote(key)}'
            html = self._fetch(url)
            items = self._parse_cards(html)
            return {'list': items, 'page': int(pg) if pg else 1, 'pagecount': 1}
        except Exception:
            return {'list': [], 'page': 1, 'pagecount': 1}

    def playerContent(self, flag, id, vipFlags=None):
        return {
            'parse': 0,
            'url': id,
            'jx': 0,
            'header': {
                'User-Agent': 'Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36',
                'Referer': self.host + '/',
            }
        }
