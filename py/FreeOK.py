# -*- coding: utf-8 -*-
"""CatVod spider for the FreeOK (MacCMS/STUI) site."""

import base64
import html
import json
import mimetypes
import re
import sys
import time
from urllib.parse import quote, unquote, urljoin, urlparse

import requests
import urllib3
from lxml import etree
from pyquery import PyQuery as pq

sys.path.append('..')
from base.spider import Spider


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class Spider(Spider):

    HOST = 'https://www.freeok88.com'
    PAGE_SIZE = 30
    PLAYER_API = 'https://v.70066.cc/video/v/'

    DEFAULT_CLASSES = (
        ('电影', '/page/dianying.html'),
        ('电视剧', '/page/dianshiju.html'),
        ('综艺', '/page/zongyi.html'),
        ('次元动漫', '/page/ciyuandongman.html'),
        ('喜剧片', '/page/xijupian.html'),
        ('科幻片', '/page/kehuanpian.html'),
        ('动作片', '/page/dongzuopian.html'),
        ('爱情片', '/page/aiqingpian.html'),
        ('剧情片', '/page/juqingpian.html'),
        ('战争片', '/page/zhanzhengpian.html'),
        ('恐怖片', '/page/kongbupian.html'),
        ('悬疑片', '/page/xuanyipian.html'),
        ('动画片', '/page/donghuapian.html'),
        ('奇幻片', '/page/qihuanpian.html'),
        ('国产剧', '/page/guochanju.html'),
        ('港台剧', '/page/gangtaiju.html'),
        ('日韩剧', '/page/rihanju.html'),
        ('欧美剧', '/page/oumeiju.html'),
        ('大陆综艺', '/page/daluzongyi.html'),
        ('日韩综艺', '/page/rihanzongyi.html'),
        ('国产动漫', '/page/guochandongman.html'),
        ('日本动漫', '/page/ribendongman.html'),
        ('欧美动漫', '/page/oumeidongman.html'),
    )

    def __init__(self):
        self.host = self.HOST
        self.ext = ''
        self.session = requests.Session()
        self.proxies = {}
        self.search_fallback = True
        self.search_fallback_pages = 1
        self.play_cache = {}
        self.media_cache = {}
        self.headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/138.0.0.0 Safari/537.36'
            ),
            'Accept': (
                'text/html,application/xhtml+xml,application/xml;'
                'q=0.9,image/avif,image/webp,*/*;q=0.8'
            ),
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Cache-Control': 'no-cache',
        }
        self.classes = [
            {'type_name': name, 'type_id': path}
            for name, path in self.DEFAULT_CLASSES
        ]

    def getName(self):
        return 'FreeOK'

    def getDependence(self):
        return []

    def setExtendInfo(self, extend):
        self.ext = extend or ''
        config = self._parse_config(extend)
        host = str(config.get('host') or '').strip().rstrip('/')
        if host.startswith(('http://', 'https://')):
            self.host = host

        user_agent = str(
            config.get('userAgent') or config.get('User-Agent') or config.get('ua') or ''
        ).strip()
        if user_agent:
            self.headers['User-Agent'] = user_agent
        cookie = str(config.get('cookie') or config.get('Cookie') or '').strip()
        if cookie:
            self.headers['Cookie'] = cookie
        elif 'Cookie' in self.headers:
            self.headers.pop('Cookie', None)
        referer = str(config.get('referer') or '').strip()
        self.headers['Referer'] = (
            referer if referer.startswith(('http://', 'https://')) else self.host + '/'
        )
        self.search_fallback = self._bool(config.get('searchFallback', True), True)
        self.search_fallback_pages = max(1, self._int(config.get('searchPages'), 1))
        self._set_proxy(config.get('proxy'))
        return None

    def init(self, extend=''):
        # Some CatVod hosts call setExtendInfo before init; keep that
        # configuration when init is invoked without an argument.
        self.setExtendInfo(extend if extend else self.ext)
        return None

    def homeLayout(self):
        return 0

    def manualVideoCheck(self):
        return False

    def isVideoFormat(self, url):
        value = str(url or '').lower()
        path = urlparse(value).path
        return any(
            marker in path or marker in value
            for marker in ('.m3u8', '.mp4', '.m4v', '.flv', '.webm', '.ts')
        )

    def destroy(self):
        try:
            self.session.close()
        except Exception:
            pass

    def homeContent(self, filter=False):
        return {'class': self.classes, 'filters': {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            response = self._request(self.host + '/', referer=self.host + '/')
            return {'list': self._parse_cards(response.text, response.url or self.host + '/')}
        except Exception as error:
            self.log('FreeOK home failed: %s' % error)
            return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        page = max(1, self._int(pg, 1))
        try:
            candidates = self._category_candidates(tid, page)
            response = self._request_candidates(candidates)
            if response is None:
                raise RuntimeError('category page unavailable')
            videos = self._parse_cards(response.text, response.url or self.host + '/')
            page_count = self._page_count(response.text, page)
            limit = len(videos) or self.PAGE_SIZE
            return {
                'list': videos,
                'page': page,
                'pagecount': page_count,
                'limit': limit,
                'total': page_count * limit if page_count else len(videos),
            }
        except Exception as error:
            self.log('FreeOK category failed: %s' % error)
            return {
                'list': [],
                'page': page,
                'pagecount': page,
                'limit': self.PAGE_SIZE,
                'total': 0,
            }

    def detailContent(self, ids):
        raw_id = str(ids[0] if ids else '').strip()
        if not raw_id:
            return {'list': []}
        try:
            detail_url = self._detail_url(raw_id)
            response = self._request(detail_url, referer=self.host + '/')
            page_url = response.url or detail_url
            data = self._doc(response.text)
            content = data('.stui-content').eq(0)
            title = self._clean(
                content('h1.title').eq(0).text()
                or data('h1.title').eq(0).text()
                or data('meta[property="og:title"]').eq(0).attr('content')
                or data('title').eq(0).text()
            )
            title = self._clean_title(title) or raw_id

            thumb = content('a.v-thumb img, .v-thumb img, img[data-original]').eq(0)
            picture = self._picture(
                thumb.attr('data-original')
                or thumb.attr('data-src')
                or thumb.attr('src'),
                page_url,
            )
            remark = self._clean(
                content('a.v-thumb .pic-text').eq(0).text()
                or content('.pic-text').eq(0).text()
            )
            fields = self._detail_fields(content if len(content) else data)
            from_list, url_list = self._playlists(data, page_url)
            if not url_list:
                return {'list': []}

            vod = {
                'vod_id': page_url,
                'vod_name': title,
                'vod_pic': picture,
                'type_name': fields.get('type_name', ''),
                'vod_year': fields.get('vod_year', ''),
                'vod_area': fields.get('vod_area', ''),
                'vod_actor': fields.get('vod_actor', ''),
                'vod_director': fields.get('vod_director', ''),
                'vod_remarks': remark or fields.get('vod_remarks', ''),
                'vod_content': self._detail_content(content if len(content) else data) or title,
                'vod_play_from': '$$$'.join(from_list),
                'vod_play_url': '$$$'.join(url_list),
            }
            return {'list': [vod]}
        except Exception as error:
            self.log('FreeOK detail failed: %s' % error)
            return {'list': []}

    def searchContent(self, key, quick, pg='1'):
        page = max(1, self._int(pg, 1))
        keyword = str(key or '').strip()
        if not keyword:
            return {'list': [], 'page': page, 'pagecount': page, 'limit': self.PAGE_SIZE, 'total': 0}

        try:
            response = self._request_candidates(
                self._search_candidates(keyword, page),
                validator=self._valid_search_page,
            )
            if response is not None:
                videos = self._parse_cards(response.text, response.url or self.host + '/')
                # A WAF/interstitial can contain generic video links and pass
                # the lightweight page validator while yielding no usable
                # search cards.  Let the fallback scanner handle that case.
                if videos:
                    page_count = self._page_count(response.text, page)
                    limit = len(videos)
                    return {
                        'list': videos,
                        'page': page,
                        'pagecount': page_count,
                        'limit': limit,
                        'total': page_count * limit if page_count else len(videos),
                    }
        except Exception as error:
            self.log('FreeOK search request failed: %s' % error)

        if self.search_fallback:
            return self._fallback_search(keyword, page)
        return {'list': [], 'page': page, 'pagecount': page, 'limit': self.PAGE_SIZE, 'total': 0}

    def playerContent(self, flag, id, vipFlags):
        value = str(id or '').strip()
        if '@Headers=' in value:
            value = value.split('@Headers=', 1)[0].strip()
        if '$' in value and not self._is_http(value):
            value = value.rsplit('$', 1)[-1].strip()
        if value.startswith('//'):
            value = 'https:' + value
        if self._is_http(value) and self.isVideoFormat(value):
            result = {
                'parse': 0,
                'playUrl': '',
                'url': value,
                'header': self._media_headers(value),
            }
            if '.m3u8' in value.lower():
                result['type'] = 'm3u8'
            return result
        play_url = self._play_url(value)
        if not play_url:
            return {'parse': 1, 'playUrl': '', 'url': self.host + '/', 'header': self._page_headers(self.host + '/')}
        try:
            if play_url in self.play_cache:
                player = self.play_cache[play_url]
            else:
                response = self._request(play_url, referer=self.host + '/')
                player = self._parse_player(response.text)
                self.play_cache[play_url] = player
            if not player:
                raise ValueError('player_aaaa not found')

            source = str(player.get('from') or '').strip().lower()
            raw_url = self._decode_player_url(player.get('url'), player.get('encrypt', 0))
            media_url = self._clean_media_url(raw_url, play_url)

            if media_url and not self._is_http(media_url):
                if source == 'bba':
                    parser_url = 'https://ok.70066.cc/nbcj/' + quote(media_url, safe='')
                    return {
                        'parse': 1,
                        'playUrl': '',
                        'url': parser_url,
                        'header': self._page_headers(parser_url),
                    }
                if source == 'ucyunbo' or self._looks_like_token(media_url):
                    resolved = self._resolve_ucyunbo(media_url, play_url)
                    if resolved:
                        media_url = resolved
                    else:
                        parser_url = self._ucyunbo_page(media_url)
                        return {
                            'parse': 1,
                            'playUrl': '',
                            'url': parser_url or play_url,
                            'header': self._page_headers(parser_url or play_url),
                        }

            if not media_url or not self._is_http(media_url):
                return {
                    'parse': 1,
                    'playUrl': '',
                    'url': play_url,
                    'header': self._page_headers(play_url),
                }

            if source in ('iframe', 'link', 'swf') and not self.isVideoFormat(media_url):
                return {
                    'parse': 1,
                    'playUrl': '',
                    'url': media_url,
                    'header': self._page_headers(play_url),
                }
            if source == 'bba' and media_url:
                parser_url = media_url if self._is_http(media_url) else 'https://ok.70066.cc/nbcj/' + quote(media_url, safe='')
                return {
                    'parse': 1,
                    'playUrl': '',
                    'url': parser_url,
                    'header': self._page_headers(play_url),
                }

            result = {
                'parse': 0,
                'playUrl': '',
                'url': media_url,
                # Douyin media rejects a FreeOK Referer; UA-only is valid for
                # both the resolved MP4 and the site's direct HLS sources.
                'header': self._media_headers(media_url),
            }
            if '.m3u8' in media_url.lower():
                result['type'] = 'm3u8'
            return result
        except Exception as error:
            self.log('FreeOK player failed: %s' % error)
            return {
                'parse': 1,
                'playUrl': '',
                'url': play_url,
                'header': self._page_headers(play_url),
            }

    def localProxy(self, param):
        try:
            param_type = param.get('type')
            param_url = param.get('url')
        except Exception:
            param_type = param_url = None
        if param_type != 'img' or not param_url:
            return [404, 'text/plain; charset=utf-8', b'not found']
        try:
            response = self.session.get(
                str(param_url),
                headers={
                    'User-Agent': self.headers['User-Agent'],
                    'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
                },
                timeout=(8, 20),
                verify=False,
            )
            response.raise_for_status()
            return [200, self._mime(response.content, response.headers.get('Content-Type')), response.content]
        except Exception as error:
            self.log('FreeOK image proxy failed: %s' % error)
            return [500, 'text/plain; charset=utf-8', b'image proxy failed']

    def _request(self, url, params=None, referer=None, timeout=22):
        headers = dict(self.headers)
        headers['Referer'] = referer or headers.get('Referer') or self.host + '/'
        response = self.session.get(
            url,
            params=params,
            headers=headers,
            timeout=timeout,
            verify=False,
            allow_redirects=True,
        )
        response.raise_for_status()
        if not response.encoding or response.encoding.lower() in ('iso-8859-1', 'ascii'):
            response.encoding = 'utf-8'
        return response

    def _request_candidates(self, candidates, validator=None):
        for candidate in candidates:
            if isinstance(candidate, (tuple, list)):
                url = candidate[0]
                params = candidate[1] if len(candidate) > 1 else None
            else:
                url, params = candidate, None
            try:
                response = self._request(url, params=params, referer=self.host + '/')
                if validator is None or validator(response):
                    return response
            except Exception:
                continue
        return None

    def _category_candidates(self, tid, page):
        original = str(tid or '').strip()
        path = original
        if self._is_http(path):
            path = urlparse(path).path
        path = path.split('?', 1)[0]
        if '@@' in path:
            path = path.split('@@', 1)[-1]
        slug = self._category_slug(path)
        if not slug:
            slug = 'dianying'
        page = max(1, page)
        canonical = '/page/%s.html' % slug if page == 1 else '/page/%s-%d.html' % (slug, page)
        candidates = [self.host + canonical]
        if page == 1:
            page_one = self.host + '/page/%s-1.html' % slug
            if page_one not in candidates:
                candidates.append(page_one)
        else:
            query_page = self.host + '/page/%s.html' % slug
            candidates.append((query_page, {'page': page}))

        # Keep the original MacCMS route as a fallback for mirrors which do
        # not expose the site's friendly /page/ aliases.
        vodshow = '/vodshow/%s-----------.html' % slug if page == 1 else '/vodshow/%s--------%d---.html' % (slug, page)
        vodshow_url = self.host + vodshow
        known_urls = [item[0] if isinstance(item, (tuple, list)) else item for item in candidates]
        if vodshow_url not in known_urls:
            candidates.append(vodshow_url)
        return candidates

    def _search_candidates(self, keyword, page):
        encoded = quote(keyword, safe='')
        params = {'wd': keyword}
        if page > 1:
            params['page'] = page
        page_params = {'wd': keyword}
        if page > 1:
            page_params['pg'] = page
        return [
            (self.host + '/so/-------------.html', params),
            (self.host + '/so/-------------.html', page_params),
            self.host + '/so/%s-------------.html' % encoded,
            self.host + '/vodsearch/%s----------%d---.html' % (encoded, page),
            self.host + '/index.php/vod/search/page/%d/wd/%s.html' % (page, encoded),
        ]

    def _fallback_search(self, keyword, page):
        if page > 1:
            # The native search endpoint is WAF-blocked on this host, so the
            # fallback can only provide a first-page scan without duplicating
            # the same items on every requested page.
            return {
                'list': [],
                'page': page,
                'pagecount': 1,
                'limit': self.PAGE_SIZE,
                'total': 0,
            }
        needle = keyword.casefold()
        results = []
        seen = set()
        sources = ['/']
        for slug in ('dianying', 'dianshiju', 'zongyi', 'ciyuandongman'):
            for scan_page in range(1, self.search_fallback_pages + 1):
                sources.append('/page/%s%s.html' % (
                    slug, '' if scan_page == 1 else '-%d' % scan_page
                ))
        for path in sources:
            try:
                response = self._request(self.host + path, referer=self.host + '/')
                for item in self._parse_cards(response.text, response.url or self.host + '/'):
                    haystack = ' '.join(
                        str(item.get(key) or '')
                        for key in ('vod_name', 'vod_actor', 'vod_remarks', 'vod_content')
                    ).casefold()
                    if needle not in haystack:
                        continue
                    vid = item.get('vod_id')
                    if vid and vid not in seen:
                        seen.add(vid)
                        results.append(item)
            except Exception:
                continue
        return {
            'list': results,
            'page': page,
            'pagecount': page,
            'limit': self.PAGE_SIZE,
            'total': len(results),
        }

    @staticmethod
    def _valid_search_page(response):
        text = str(getattr(response, 'text', '') or '')
        low = text[:12000].lower()
        if any(marker in low for marker in ('403 forbidden', 'system error', '系统提示')):
            return False
        return (
            '/video/' in text
            or 'stui-vodlist' in low
            or '没有找到' in text
            or '暂无数据' in text
        )

    def _parse_cards(self, html_text, page_url=''):
        data = self._doc(html_text)
        boxes = list(data('.stui-vodlist__box').items())
        if not boxes:
            for selector in ('.stui-vodlist__media', '.stui-search-list li', '.stui-vodlist li'):
                boxes = list(data(selector).items())
                if boxes:
                    break

        videos = []
        seen = set()
        if boxes:
            anchors = []
            for box in boxes:
                anchor = box('a[href*="/video/"]').eq(0)
                if len(anchor):
                    anchors.append((anchor, box))
        else:
            anchors = []
            for anchor in data('a[href*="/video/"]').items():
                box = anchor.parents('li').eq(0)
                if not len(box):
                    box = anchor
                anchors.append((anchor, box))

        for anchor, box in anchors:
            href = html.unescape(str(anchor.attr('href') or '').strip())
            if not re.search(r'/video/[^/?#]+\.html', href, re.I):
                continue
            absolute = urljoin(page_url or self.host + '/', href)
            if absolute in seen:
                continue
            title = self._clean(
                anchor.attr('title')
                or box('h4.title a, h3.title a, .title a').eq(0).attr('title')
                or box('h4.title a, h3.title a, .title a').eq(0).text()
                or anchor.text()
            )
            if not title:
                continue
            raw_pic = ''
            for image in box('img').items():
                value = image.attr('data-original') or image.attr('data-src') or image.attr('src')
                if value and 'load.gif' not in value.lower():
                    raw_pic = value
                    break
            picture = self._picture(raw_pic, absolute)
            remark = self._clean(box('.pic-text').eq(0).text())
            actor = self._clean(box('.dx .text, .text-muted').eq(0).text())
            seen.add(absolute)
            videos.append({
                'vod_id': absolute,
                'vod_name': title,
                'vod_pic': picture,
                'vod_remarks': remark,
                'vod_actor': actor,
                'style': {'type': 'rect', 'ratio': 1.78},
            })
        return videos

    def _playlists(self, data, page_url):
        play_from = []
        play_urls = []
        blocks = list(data('.sp1-box.playlist').items()) or list(data('.playlist').items())
        for index, block in enumerate(blocks, start=1):
            line = self._clean(block('.sp1__head .title, .hd h2.title, h2.title').eq(0).text())
            episodes = []
            used = set()
            for anchor in block('a[href*="/play/"]').items():
                href = html.unescape(str(anchor.attr('href') or '').strip())
                if not re.search(r'/play/[^/?#]+\.html', href, re.I):
                    continue
                href = urljoin(page_url, href)
                if href in used:
                    continue
                used.add(href)
                name = self._clean(anchor.text()) or self._episode_name(href, len(episodes) + 1)
                episodes.append('%s$%s' % (self._safe_part(name, '播放'), href))
            if episodes:
                play_from.append(self._safe_part(line, '线路%d' % index))
                play_urls.append('#'.join(episodes))

        if not play_urls:
            groups = {}
            for anchor in data('a[href*="/play/"]').items():
                href = html.unescape(str(anchor.attr('href') or '').strip())
                match = re.search(r'/play/[^/?#]+-(\d+)-(\d+)\.html', href, re.I)
                if not match:
                    continue
                sid = match.group(1)
                absolute = urljoin(page_url, href)
                groups.setdefault(sid, []).append(
                    '%s$%s' % (self._safe_part(self._clean(anchor.text()), self._episode_name(absolute, 1)), absolute)
                )
            for sid, episodes in groups.items():
                play_from.append('线路%s' % sid)
                play_urls.append('#'.join(dict.fromkeys(episodes)))
        return play_from, play_urls

    def _detail_fields(self, root):
        result = {}
        known = {
            '主演': 'vod_actor', '演员': 'vod_actor', '演员表': 'vod_actor',
            '导演': 'vod_director', '类型': 'type_name', '分类': 'type_name',
            '地区': 'vod_area', '年份': 'vod_year', '状态': 'vod_remarks',
        }
        for row in root('.data').items():
            raw = row.html() or ''
            matches = list(re.finditer(
                r'<span[^>]*class=["\'][^"\']*text-muted[^"\']*["\'][^>]*>(.*?)</span>',
                raw, re.I | re.S,
            ))
            if not matches:
                continue
            for index, match in enumerate(matches):
                label = self._clean(match.group(1)).rstrip(':：').strip()
                if label not in known:
                    continue
                end = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
                segment = raw[match.end():end]
                fragment = self._doc('<div>%s</div>' % segment)
                values = [self._clean(a.text()) for a in fragment('a').items()]
                values = [value for value in values if value]
                value = ', '.join(dict.fromkeys(values)) if values else self._clean(fragment.text())
                if value:
                    key = known[label]
                    result[key] = self._merge_field(result.get(key, ''), value)
        return result

    def _detail_content(self, root):
        return self._clean(
            root('.detail-content').eq(0).text()
            or root('.detail-sketch').eq(0).text()
            or root('.desc').eq(0).text()
            or root('meta[name="description"]').eq(0).attr('content')
        )

    def _category_slug(self, value):
        path = str(value or '').strip().strip('/')
        if self._is_http(path):
            path = urlparse(path).path.strip('/')
        if path.startswith('page/') or path.startswith('vodshow/'):
            path = path.split('/', 1)[1]
        path = path.split('/', 1)[-1]
        path = re.sub(r'\.html?$', '', path, flags=re.I)
        path = re.sub(r'-\d+$', '', path)
        path = re.sub(r'-{3,}.*$', '', path)
        return path or 'dianying'

    def _category_url(self, value, page):
        slug = self._category_slug(value)
        return self.host + ('/page/%s.html' % slug if page <= 1 else '/page/%s-%d.html' % (slug, page))

    def _page_count(self, html_text, current):
        data = self._doc(html_text)
        values = [max(1, self._int(current, 1))]
        number = self._clean(data('.stui-page .num').eq(0).text())
        match = re.search(r'/\s*(\d+)', number)
        if match:
            values.append(self._int(match.group(1), values[0]))
        for anchor in data('.stui-page a[href]').items():
            href = str(anchor.attr('href') or '')
            match = re.search(r'-(\d+)\.html(?:$|[?#])', href, re.I)
            if match:
                values.append(self._int(match.group(1), values[0]))
        return max(values)

    def _detail_url(self, value):
        value = html.unescape(str(value or '').strip())
        if self._is_http(value):
            return value
        if value.startswith('/'):
            return urljoin(self.host + '/', value)
        if re.search(r'\.html$', value, re.I):
            return urljoin(self.host + '/', '/' + value)
        match = re.search(r'([A-Za-z0-9]{4,})', value)
        return self.host + '/video/%s.html' % (match.group(1) if match else value)

    def _play_url(self, value):
        value = html.unescape(str(value or '').strip())
        if self._is_http(value):
            return value
        if value.startswith('/'):
            return urljoin(self.host + '/', value)
        if value.startswith('play/') or value.startswith('play\\'):
            return urljoin(self.host + '/', '/' + value.replace('\\', '/'))
        if re.search(r'\.html$', value, re.I):
            return urljoin(self.host + '/', '/' + value)
        if re.match(r'^[A-Za-z0-9]+-\d+-\d+$', value):
            return self.host + '/play/%s.html' % value
        if re.match(r'^[A-Za-z0-9]+$', value):
            return self.host + '/play/%s-1-1.html' % value
        return ''

    def _parse_player(self, text):
        source = str(text or '')
        match = re.search(
            r'var\s+player_[A-Za-z0-9_]*\s*=\s*(\{.*?\})\s*;?\s*</script>',
            source, re.I | re.S,
        )
        if not match:
            return {}
        raw = html.unescape(match.group(1)).replace('\\/', '/').strip()
        try:
            value = json.loads(raw)
            return value if isinstance(value, dict) else {}
        except Exception:
            result = {}
            for key in ('url', 'from', 'flag', 'id', 'link', 'link_next'):
                found = re.search(r'["\']%s["\']\s*:\s*["\'](.*?)["\']' % key, raw, re.S)
                if found:
                    result[key] = found.group(1)
            found = re.search(r'["\']encrypt["\']\s*:\s*(\d+)', raw)
            if found:
                result['encrypt'] = int(found.group(1))
            return result

    def _decode_player_url(self, value, encrypt=0):
        text = html.unescape(str(value or '')).replace('\\/', '/').strip()
        mode = self._int(encrypt, 0)
        if not text:
            return ''
        try:
            if mode == 1:
                return self._js_unescape(text)
            if mode == 2:
                encoded = unquote(text)
                encoded += '=' * ((4 - len(encoded) % 4) % 4)
                encoded = encoded.replace('-', '+').replace('_', '/')
                decoded = base64.b64decode(encoded).decode('utf-8', errors='ignore')
                return self._js_unescape(decoded)
        except Exception:
            pass
        return text

    def _resolve_ucyunbo(self, token, play_url=''):
        token = str(token or '').strip()
        if not token or self._is_http(token):
            return token if self._is_http(token) else ''
        cached = self.media_cache.get(token)
        if cached:
            expires_at, cached_url = cached
            if expires_at > time.time():
                return cached_url
            self.media_cache.pop(token, None)
        try:
            parsed = urlparse(self.host)
            origin = '%s://%s' % (parsed.scheme, parsed.netloc)
            response = self.session.get(
                self.PLAYER_API + quote(token, safe=''),
                headers={
                    'User-Agent': self.headers['User-Agent'],
                    'Accept': 'application/json',
                    'Referer': self.host + '/static/player/videoparse.html?v=' + quote(token, safe=''),
                    'Origin': origin,
                },
                timeout=(8, 20),
                verify=False,
            )
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict):
                if isinstance(payload.get('data'), dict):
                    payload = payload['data']
                if self._int(payload.get('code'), 200) not in (0, 200):
                    return ''
                url = self._clean_media_url(payload.get('url'), self.PLAYER_API + token)
                if self._is_http(url):
                    # The resolver returns signed media URLs; refresh them
                    # periodically instead of retaining an expired address.
                    self.media_cache[token] = (time.time() + 300, url)
                    return url
        except Exception as error:
            self.log('FreeOK ucyunbo resolve failed: %s' % error)
        return ''

    def _ucyunbo_page(self, token):
        token = str(token or '').strip()
        return self.host + '/static/player/videoparse.html?v=' + quote(token, safe='') if token else ''

    def _parse_config(self, value):
        if isinstance(value, dict):
            return dict(value)
        text = str(value or '').strip()
        if text.startswith('{'):
            try:
                data = json.loads(text)
                return data if isinstance(data, dict) else {}
            except Exception:
                return {}
        if text.startswith(('http://', 'https://')):
            return {'host': text}
        return {}

    def _set_proxy(self, value):
        proxy = str(value or '').strip()
        self.proxies = {}
        try:
            self.session.proxies.clear()
        except Exception:
            pass
        if not proxy:
            return
        if '://' not in proxy:
            proxy = 'http://' + proxy
        self.proxies = {'http': proxy, 'https': proxy}
        try:
            self.session.proxies.update(self.proxies)
        except Exception:
            pass

    def _doc(self, value):
        text = value.decode('utf-8', errors='ignore') if isinstance(value, bytes) else str(value or '')
        try:
            parser = etree.HTMLParser(encoding='utf-8', recover=True)
            root = etree.fromstring(text.encode('utf-8', errors='ignore'), parser=parser)
            return pq(root) if root is not None else pq('<html></html>')
        except Exception:
            return pq('<html></html>')

    def _picture(self, value, page_url):
        raw = html.unescape(str(value or '').strip()).strip('`"\' ')
        if not raw or 'load.gif' in raw.lower() or raw.lower().startswith('data:image'):
            return ''
        return urljoin(page_url or self.host + '/', raw)

    def _media_headers(self, url=''):
        return {
            'User-Agent': self.headers['User-Agent'],
            'Accept': '*/*',
        }

    def _page_headers(self, referer=''):
        return {
            'User-Agent': self.headers['User-Agent'],
            'Accept': self.headers.get('Accept', '*/*'),
            'Referer': referer or self.host + '/',
        }

    @staticmethod
    def _clean_media_url(value, base=''):
        raw = html.unescape(str(value or '')).replace('\\/', '/').strip()
        if raw.startswith('//'):
            raw = 'https:' + raw
        if not raw or not base or re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:', raw):
            return raw
        # MacCMS's ucyunbo source stores a bare token in `url`.  Do not
        # accidentally turn that token into a relative FreeOK URL.
        if raw.startswith(('/', './', '../')) or re.search(
            r'\.(?:m3u8|mp4|m4v|flv|webm|ts)(?:$|[?#])', raw, re.I
        ):
            return urljoin(base, raw)
        return raw

    @staticmethod
    def _is_http(value):
        return str(value or '').lower().startswith(('http://', 'https://'))

    @staticmethod
    def _looks_like_token(value):
        return bool(re.fullmatch(r'[A-Za-z0-9_-]{24,}', str(value or '').strip()))

    @staticmethod
    def _episode_name(url, fallback):
        match = re.search(r'-(\d+)\.html', str(url or ''), re.I)
        return '第%02d集' % int(match.group(1)) if match else '播放%d' % fallback

    @staticmethod
    def _safe_part(value, fallback=''):
        result = re.sub(r'[$#]+', ' ', str(value or '')).strip()
        return result or fallback

    @staticmethod
    def _merge_field(old, value):
        values = [x.strip() for x in str(old or '').split(',') if x.strip()]
        for item in str(value or '').split(','):
            item = item.strip()
            if item and item not in values:
                values.append(item)
        return ', '.join(values)

    @staticmethod
    def _clean_title(value):
        return re.sub(r'\s+-\s+(?:HD高清完整版|高清完整版).*$', '', str(value or ''), flags=re.I).strip()

    @staticmethod
    def _clean(value):
        return re.sub(r'\s+', ' ', html.unescape(str(value or ''))).strip()

    @staticmethod
    def _js_unescape(value):
        text = str(value or '')
        text = re.sub(r'%u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), text)
        return unquote(text)

    @staticmethod
    def _bool(value, default=False):
        if value is None:
            return default
        return str(value).strip().lower() not in ('0', 'false', 'off', 'no', '')

    @staticmethod
    def _int(value, default=0):
        try:
            return int(value)
        except Exception:
            return default

    @staticmethod
    def _mime(data, declared=''):
        if data.startswith(b'\xff\xd8\xff'):
            return 'image/jpeg'
        if data.startswith(b'\x89PNG'):
            return 'image/png'
        if data.startswith(b'GIF8'):
            return 'image/gif'
        if len(data) > 11 and data[:4] == b'RIFF' and data[8:12] == b'WEBP':
            return 'image/webp'
        declared = str(declared or '').split(';', 1)[0].strip()
        return declared if declared.startswith('image/') else (mimetypes.guess_type('cover.jpg')[0] or 'application/octet-stream')
