# -*- coding: utf-8 -*-
"""CatVod spider for zlys9.top (真狼影视)."""

import hashlib
import hmac
import html
import ipaddress
import json
import math
import mimetypes
import re
import secrets
import socket
import sys
import time
from urllib.parse import parse_qs, quote, unquote, urljoin, urlparse

import requests
import urllib3
from lxml import etree
from pyquery import PyQuery as pq

sys.path.append('..')
from base.spider import Spider


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class Spider(Spider):

    HOST = 'https://zlys9.top'
    PAGE_SIZE = 36

    CLASS_INFO = (
        ('电视剧', 'tv', 2),
        ('电影', 'movie', 1),
        ('综艺', 'variety', 3),
        ('动漫', 'anime', 4),
        ('儿童', 'children', 4),
    )
    CAT_TO_ALIAS = {1: 'movie', 2: 'tv', 3: 'variety', 4: 'anime'}
    ALIAS_TO_CAT = {alias: cat for _, alias, cat in CLASS_INFO}

    RANKS = {
        'movie': (('最近热映', 'rankhot'), ('最近上映', 'ranklatest'), ('最受好评', 'rankpoint')),
        'tv': (('最近热映', 'rankhot'), ('最近上映', 'ranklatest'), ('最受好评', 'rankpoint')),
        'variety': (('最近热映', 'rankhot'), ('最近上映', 'ranklatest')),
        'anime': (('最近热映', 'rankhot'), ('最近上映', 'ranklatest')),
        'children': (('最近热映', 'rankhot'), ('最近上映', 'ranklatest')),
    }
    GENRES = {
        'movie': (
            '喜剧', '爱情', '动作', '恐怖', '科幻', '剧情', '犯罪', '奇幻', '战争',
            '悬疑', '动画', '文艺', '纪录', '传记', '歌舞', '古装', '历史', '惊悚',
            '伦理', '其他',
        ),
        'tv': (
            '言情', '剧情', '伦理', '喜剧', '悬疑', '都市', '偶像', '古装', '军事',
            '警匪', '历史', '励志', '神话', '谍战', '青春剧', '家庭剧', '动作',
            '情景', '武侠', '科幻', '其他',
        ),
        'variety': (
            '脱口秀', '真人秀', '搞笑', '选秀', '八卦', '访谈', '情感', '生活',
            '晚会', '音乐', '职场', '美食', '时尚', '游戏', '少儿', '体育', '纪实',
            '科教', '曲艺', '歌舞', '财经', '汽车', '播报', '其他',
        ),
        'anime': (
            '热血', '科幻', '美少女', '魔幻', '经典', '励志', '少儿', '冒险', '搞笑',
            '推理', '恋爱', '治愈', '幻想', '校园', '动物', '机战', '亲子', '儿歌',
            '运动', '悬疑', '怪物', '战争', '益智', '青春', '童话', '竞技', '动作',
            '社会', '友情', '真人版', '电影版', 'OVA版', 'TV版', '新番动画', '完结动画',
        ),
        'children': (
            '热血', '科幻', '美少女', '魔幻', '经典', '励志', '少儿', '冒险', '搞笑',
            '推理', '恋爱', '治愈', '幻想', '校园', '动物', '机战', '亲子', '儿歌',
            '运动', '悬疑', '怪物', '战争', '益智', '青春', '童话', '竞技', '动作',
            '社会', '友情', '真人版', '电影版', 'OVA版', 'TV版', '新番动画', '完结动画',
        ),
    }
    AREAS = {
        'movie': ('大陆', '香港', '台湾', '泰国', '美国', '韩国', '日本', '法国', '英国', '德国', '印度', '其他'),
        'tv': ('内地', '香港', '台湾', '韩国', '美国', '日本', '英国', '泰国', '其他'),
        'variety': ('大陆', '香港', '台湾', '日本', '欧美'),
        'anime': ('大陆', '日本', '美国'),
        'children': ('大陆', '日本', '美国'),
    }

    def __init__(self):
        self.host = self.HOST
        self.ext = ''
        self.session = requests.Session()
        self.proxies = {}
        self.source_meta = {}
        self.source_meta_time = 0
        self.proxy_secret = secrets.token_bytes(32)
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
            {'type_name': name, 'type_id': alias}
            for name, alias, _ in self.CLASS_INFO
        ]

    def getName(self):
        return '真狼影视'

    def getDependence(self):
        return []

    def setExtendInfo(self, extend):
        self.ext = extend or ''
        config = self._parse_config(extend)
        previous_host = self.host
        host = str(config.get('host') or '').strip().rstrip('/')
        if host.startswith(('http://', 'https://')):
            self.host = host
        if self.host != previous_host:
            self.source_meta = {}
            self.source_meta_time = 0

        user_agent = str(
            config.get('userAgent') or config.get('User-Agent') or config.get('ua') or ''
        ).strip()
        if user_agent:
            self.headers['User-Agent'] = user_agent
        cookie = str(config.get('cookie') or config.get('Cookie') or '').strip()
        if cookie:
            self.headers['Cookie'] = cookie
        else:
            self.headers.pop('Cookie', None)
        referer = str(config.get('referer') or '').strip()
        self.headers['Referer'] = (
            referer if referer.startswith(('http://', 'https://')) else self.host + '/'
        )
        self._set_proxy(config.get('proxy'))
        return None

    def init(self, extend=''):
        self.setExtendInfo(extend if extend else self.ext)
        return None

    def homeLayout(self):
        return 0

    def manualVideoCheck(self):
        return False

    def isVideoFormat(self, url):
        value = unquote(str(url or '')).lower()
        path = urlparse(value).path
        return 'type=zlys_m3u8' in value or any(
            marker in path or marker in value
            for marker in ('.m3u8', '.mp4', '.m4v', '.flv', '.webm', '.ts')
        )

    def destroy(self):
        try:
            self.session.close()
        except Exception:
            pass

    def homeContent(self, filter=False):
        return {
            'class': self.classes,
            'filters': self._filters() if filter else {},
        }

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            response = self._request(self.host + '/', referer=self.host + '/')
            return {'list': self._parse_cards(response.text, response.url or self.host + '/')}
        except Exception as error:
            self.log('真狼影视首页加载失败: %s' % error)
            return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        page = max(1, self._int(pg, 1))
        alias = self._category_alias(tid)
        params = {'page': page}
        values = extend if isinstance(extend, dict) else {}
        for key in ('rank', 'type', 'year', 'area', 'act'):
            value = str(values.get(key) or '').strip()
            if value:
                params[key] = value
        try:
            url = '%s/category/%s/filter' % (self.host, quote(alias, safe=''))
            response = self._request(url, params=params, referer=self.host + '/')
            videos = self._parse_cards(response.text, response.url or url)
            page_count = self._page_count(response.text, page)
            return {
                'list': videos,
                'page': page,
                'pagecount': page_count,
                'limit': self.PAGE_SIZE,
                'total': page_count * self.PAGE_SIZE,
            }
        except Exception as error:
            self.log('真狼影视分类加载失败: %s' % error)
            return {
                'list': [], 'page': page, 'pagecount': page,
                'limit': self.PAGE_SIZE, 'total': 0,
            }

    def detailContent(self, ids):
        raw_id = str(ids[0] if ids else '').strip()
        if not raw_id:
            return {'list': []}
        try:
            detail_url = self._detail_url(raw_id)
            if not self._is_site_url(detail_url):
                raise ValueError('详情地址不属于当前站点')
            response = self._request(detail_url, referer=self.host + '/')
            page_url = response.url or detail_url
            alias, item_id = self._detail_parts(page_url)
            data = self._detail_data(response.text)
            if data:
                alias = alias or self.CAT_TO_ALIAS.get(self._int(data.get('cat'), 0), '')
                item_id = item_id or str(data.get('id') or '').strip()
            if not alias or not item_id:
                raise ValueError('详情地址缺少分类或视频 ID')

            doc = self._doc(response.text)
            detail = data.get('detail') if isinstance(data.get('detail'), dict) else {}
            fields = self._detail_dom_fields(doc)
            title = self._text(detail.get('title')) or self._clean_title(
                doc('h1.detail-hero__title').eq(0).text()
            ) or item_id
            picture = self._picture(
                data.get('cover')
                or detail.get('cdncover')
                or doc('.detail-hero__poster img').eq(0).attr('src'),
                page_url,
            )
            sources = data.get('sources') if isinstance(data.get('sources'), list) else []
            play_from, play_urls = self._playlists(alias, item_id, sources, detail)
            if not play_urls:
                return {'list': []}

            pubdate = self._text(detail.get('pubdate'))
            year_match = re.search(r'\b(19|20)\d{2}\b', pubdate or fields.get('首播', ''))
            content = self._text(detail.get('description') or detail.get('comment'))
            if not content:
                content = self._clean(doc('.detail-hero__synopsis-text').eq(0).text())
            update_text = self._text(data.get('updateText'))
            if not update_text:
                update_text = self._clean(doc('.detail-hero__release').eq(0).text())

            vod = {
                'vod_id': page_url,
                'vod_name': title,
                'vod_pic': picture,
                'type_name': self._text(detail.get('moviecategory')) or fields.get('类型', ''),
                'vod_year': year_match.group(0) if year_match else '',
                'vod_area': self._text(detail.get('area')) or fields.get('制片国家', ''),
                'vod_actor': self._text(detail.get('actor')) or fields.get('主演', ''),
                'vod_director': self._text(detail.get('director')) or fields.get('导演', ''),
                'vod_remarks': update_text,
                'vod_content': content or title,
                'vod_play_from': '$$$'.join(play_from),
                'vod_play_url': '$$$'.join(play_urls),
            }
            return {'list': [vod]}
        except Exception as error:
            self.log('真狼影视详情加载失败: %s' % error)
            return {'list': []}

    def searchContent(self, key, quick, pg='1'):
        page = max(1, self._int(pg, 1))
        keyword = str(key or '').strip()
        if not keyword:
            return {
                'list': [], 'page': page, 'pagecount': 1,
                'limit': self.PAGE_SIZE, 'total': 0,
            }
        try:
            payload = self._api('/api/search', {
                'q': keyword,
                'page': page,
                'size': self.PAGE_SIZE,
            })
            if self._int(payload.get('errno'), 0) != 0:
                raise RuntimeError(self._text(payload.get('message')) or '搜索接口返回错误')
            data = payload.get('data') if isinstance(payload.get('data'), dict) else {}
            items = data.get('items') if isinstance(data.get('items'), list) else []
            videos = [self._search_video(item) for item in items if isinstance(item, dict)]
            videos = [item for item in videos if item]
            total = max(0, self._int(data.get('total'), len(videos)))
            limit = max(1, self._int(data.get('size'), self.PAGE_SIZE))
            page_count = max(1, int(math.ceil(float(total) / limit))) if total else 1
            return {
                'list': videos,
                'page': page,
                'pagecount': page_count,
                'limit': limit,
                'total': total,
            }
        except Exception as error:
            self.log('真狼影视搜索失败: %s' % error)
            return {
                'list': [], 'page': page, 'pagecount': 1,
                'limit': self.PAGE_SIZE, 'total': 0,
            }

    def searchContentPage(self, key, quick, pg):
        return self.searchContent(key, quick, pg)

    def playerContent(self, flag, id, vipFlags):
        value = str(id or '').strip()
        if '@Headers=' in value:
            value = value.split('@Headers=', 1)[0].strip()
        if '$' in value and not self._is_http(value):
            value = value.rsplit('$', 1)[-1].strip()
        if value.startswith('//'):
            value = 'https:' + value
        if self._is_http(value) and self.isVideoFormat(value):
            return self._play_result(value, {}, allow_proxy=False)

        play_url = self._play_url(value)
        if not play_url:
            return {
                'parse': 1, 'playUrl': '', 'url': value or self.host + '/',
                'header': self._page_headers(self.host + '/'),
            }
        if urlparse(play_url).netloc.lower() != urlparse(self.host).netloc.lower():
            return {
                'parse': 1, 'playUrl': '', 'url': play_url,
                'header': self._page_headers(self.host + '/'),
            }

        last_error = None
        for attempt in range(2):
            try:
                params = {'_refresh': int(time.time() * 1000)} if attempt else None
                response = self._request(play_url, params=params, referer=self.host + '/')
                player = self._player_data(response.text)
                media_url = self._absolute_url(player.get('src'), response.url or play_url)
                if media_url and self._is_http(media_url):
                    if self._looks_like_media(media_url):
                        return self._play_result(
                            media_url,
                            player.get('headers'),
                            allow_proxy=True,
                        )
                    return {
                        'parse': 1,
                        'playUrl': '',
                        'url': media_url,
                        'header': self._page_headers(self.host + '/'),
                    }
                last_error = ValueError('播放页未返回媒体地址')
            except Exception as error:
                last_error = error

        self.log('真狼影视播放解析失败: %s' % last_error)
        return {
            'parse': 1,
            'playUrl': '',
            'url': play_url,
            'header': self._page_headers(self.host + '/'),
        }

    def localProxy(self, param):
        try:
            proxy_type = str(param.get('type') or '')
            proxy_url = str(param.get('url') or '').strip()
            proxy_sig = str(param.get('sig') or '').strip()
        except Exception:
            proxy_type = proxy_url = proxy_sig = ''
        if proxy_type not in ('zlys_m3u8', 'zlys_media', 'img'):
            return [404, 'text/plain; charset=utf-8', b'not found']
        if not proxy_url:
            return [404, 'text/plain; charset=utf-8', b'not found']
        if not self._is_http(proxy_url):
            decoded = unquote(proxy_url)
            proxy_url = decoded if self._is_http(decoded) else proxy_url
        if not self._valid_proxy_signature(proxy_type, proxy_url, proxy_sig):
            return [403, 'text/plain; charset=utf-8', b'forbidden']
        if not self._valid_remote_url(proxy_url):
            return [400, 'text/plain; charset=utf-8', b'invalid url']

        if proxy_type == 'zlys_m3u8':
            response = None
            try:
                response = self._proxy_get(
                    proxy_url,
                    headers=self._media_headers(),
                    timeout=(8, 30),
                )
                response.raise_for_status()
                body = response.content.decode('utf-8-sig', errors='ignore')
                if '#EXTM3U' not in body:
                    raise ValueError('上游未返回 HLS 清单')
                body = self._rewrite_manifest(body, response.url or proxy_url)
                return [200, 'application/vnd.apple.mpegurl', body.encode('utf-8')]
            except Exception as error:
                self.log('真狼影视 HLS 代理失败: %s' % error)
                return [502, 'text/plain; charset=utf-8', b'hls proxy failed']
            finally:
                if response is not None:
                    response.close()

        if proxy_type == 'zlys_media':
            response = None
            try:
                response = self._proxy_get(
                    proxy_url,
                    headers=self._media_headers(),
                    timeout=(8, 35),
                )
                response.raise_for_status()
                content = response.content
                transport_stream = self._strip_png_ts(content)
                if transport_stream is not None:
                    content = transport_stream
                    content_type = 'video/mp2t'
                else:
                    content_type = str(
                        response.headers.get('Content-Type') or 'application/octet-stream'
                    ).split(';', 1)[0].strip()
                    if content_type.startswith('image/'):
                        raise ValueError('媒体分片是图片且未找到 TS 数据')
                return [200, content_type, content, {
                    'Cache-Control': 'no-cache',
                    'Access-Control-Allow-Origin': '*',
                }]
            except Exception as error:
                self.log('真狼影视媒体分片代理失败: %s' % error)
                return [502, 'text/plain; charset=utf-8', b'media proxy failed']
            finally:
                if response is not None:
                    response.close()

        if proxy_type == 'img':
            response = None
            try:
                response = self._proxy_get(
                    proxy_url,
                    headers={
                        'User-Agent': self.headers['User-Agent'],
                        'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
                    },
                    timeout=(8, 25),
                )
                response.raise_for_status()
                return [
                    200,
                    self._mime(response.content, response.headers.get('Content-Type')),
                    response.content,
                ]
            except Exception as error:
                self.log('真狼影视图片代理失败: %s' % error)
                return [500, 'text/plain; charset=utf-8', b'image proxy failed']
            finally:
                if response is not None:
                    response.close()
        return [404, 'text/plain; charset=utf-8', b'not found']

    def _proxy_get(self, url, headers, timeout):
        current = str(url or '').strip()
        for _ in range(6):
            if not self._valid_remote_url(current):
                raise ValueError('代理目标不是公网地址')
            response = self.session.get(
                current,
                headers=headers,
                timeout=timeout,
                verify=False,
                allow_redirects=False,
            )
            if response.status_code not in (301, 302, 303, 307, 308):
                return response
            location = str(response.headers.get('Location') or '').strip()
            response.close()
            if not location:
                raise ValueError('上游重定向缺少地址')
            current = self._absolute_url(location, current)
        raise requests.TooManyRedirects('上游重定向次数过多')

    def _request(self, url, params=None, referer=None, timeout=25):
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

    def _api(self, path, params=None):
        response = self._request(
            self.host.rstrip('/') + '/' + str(path or '').lstrip('/'),
            params=params,
            referer=self.host + '/',
        )
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError('接口未返回 JSON 对象')
        return payload

    def _parse_cards(self, html_text, page_url):
        data = self._doc(html_text)
        cards = list(data('ul.movie-list--page li.video-card').items())
        if not cards:
            cards = list(data('li.video-card').items())
        videos = []
        seen = set()
        for card in cards:
            anchor = card('a.video-card__link[href^="/detail/"]').eq(0)
            if not len(anchor):
                anchor = card('a[href^="/detail/"]').eq(0)
            href = html.unescape(str(anchor.attr('href') or '').strip())
            if not re.match(r'^/detail/[^/]+/[^/?#]+', href, re.I):
                continue
            vod_id = urljoin(page_url or self.host + '/', href)
            if vod_id in seen:
                continue
            title = self._clean(
                anchor.attr('title')
                or card('.video-card__title a').eq(0).attr('title')
                or card('.video-card__title a').eq(0).text()
                or anchor.attr('alt')
            )
            if not title:
                continue
            image = card('img.video-card__img, img').eq(0)
            picture = self._picture(
                image.attr('src') or image.attr('data-src') or image.attr('data-original'),
                vod_id,
            )
            remark = self._clean(card('.video-card__badge').eq(0).text())
            score = self._clean(card('.video-card__score').eq(0).text())
            meta = self._clean(card('.video-card__meta').eq(0).text())
            category = self._clean(card('.video-card__cat').eq(0).text())
            seen.add(vod_id)
            videos.append({
                'vod_id': vod_id,
                'vod_name': title,
                'vod_pic': picture,
                'vod_remarks': remark or (('评分%s' % score) if score else ''),
                'vod_content': meta,
                'type_name': category,
            })
        return videos

    def _search_video(self, item):
        item_id = str(item.get('id') or '').strip()
        cat = self._int(item.get('cat'), 0)
        alias = self.CAT_TO_ALIAS.get(cat)
        title = self._text(item.get('title'))
        if not item_id or not alias or not title:
            return None
        picture = self._best_picture(item.get('cover'), item.get('coverFallbacks'))
        picture = self._picture(picture, self.host + '/')
        score = self._text(item.get('score'))
        remark = self._text(item.get('badge')) or self._text(item.get('pubdate'))
        if score and not remark:
            remark = '评分%s' % score
        return {
            'vod_id': '%s/detail/%s/%s' % (self.host, alias, quote(item_id, safe='')),
            'vod_name': title,
            'vod_pic': picture,
            'vod_remarks': remark,
            'vod_content': self._text(item.get('meta')),
        }

    def _detail_data(self, html_text):
        for item in self._walk_dicts(self._flight_records(html_text)):
            if isinstance(item.get('detail'), dict) and isinstance(item.get('sources'), list):
                return item
        return {}

    def _player_data(self, html_text):
        fallback = {}
        external = {}
        for item in self._walk_dicts(self._flight_records(html_text)):
            src = str(item.get('src') or '').strip()
            if not self._is_http(src) and not src.startswith('//'):
                continue
            is_media = self._looks_like_media(src)
            is_player = str(item.get('engine') or '').lower() == 'art'
            if is_media:
                if is_player:
                    return item
                if not fallback:
                    fallback = item
            elif is_player and not external:
                external = item
        if fallback:
            return fallback

        # Keep a narrow fallback for a future Flight serialization change.
        marker = r'\\"engine\\":\\"art\\"'
        for engine_match in re.finditer(marker, str(html_text or ''), re.I):
            prefix = str(html_text or '')[:engine_match.start()]
            start = prefix.rfind(r'\"src\":\"')
            if start < 0:
                continue
            start += len(r'\"src\":\"')
            end = prefix.find(r'\"', start)
            if end <= start:
                continue
            try:
                src = json.loads('"' + prefix[start:end] + '"')
            except Exception:
                src = prefix[start:end].replace(r'\/', '/')
            if self._is_http(src) or str(src).startswith('//'):
                item = {'src': src, 'engine': 'art', 'headers': {}}
                if self._looks_like_media(src):
                    return item
                if not external:
                    external = item
        return external

    def _flight_records(self, html_text):
        text = str(html_text or '')
        try:
            parser = etree.HTMLParser(encoding='utf-8', recover=True)
            root = etree.fromstring(text.encode('utf-8', errors='ignore'), parser=parser)
        except Exception:
            root = None
        if root is None:
            return []

        records = []
        marker = 'self.__next_f.push('
        for node in root.xpath('//script[not(@src)]'):
            script = node.text or ''
            at = script.find(marker)
            if at < 0:
                continue
            raw = script[at + len(marker):script.rfind(')')]
            try:
                payload = json.loads(raw)
            except Exception:
                continue
            value = payload[1] if len(payload) > 1 and isinstance(payload[1], str) else ''
            for line in value.splitlines():
                if ':' not in line:
                    continue
                _, encoded = line.split(':', 1)
                if encoded[:1] not in ('[', '{'):
                    continue
                try:
                    records.append(json.loads(encoded))
                except Exception:
                    continue
        return records

    @staticmethod
    def _walk_dicts(values):
        stack = list(values or [])
        while stack:
            value = stack.pop()
            if isinstance(value, dict):
                yield value
                stack.extend(value.values())
            elif isinstance(value, list):
                stack.extend(value)

    def _playlists(self, alias, item_id, sources, detail):
        metadata = self._source_metadata()
        rows = []
        for index, source in enumerate(sources):
            if not isinstance(source, dict):
                continue
            site = str(source.get('site') or '').strip()
            episodes = source.get('episodes') if isinstance(source.get('episodes'), list) else []
            meta = metadata.get(site, {})
            if not site or not episodes or meta.get('enabled') is False:
                continue
            rows.append((self._int(meta.get('sort'), 9999), index, source, meta))
        rows.sort(key=lambda item: (item[0], item[1]))

        play_from = []
        play_urls = []
        used_names = set()
        cat = self.ALIAS_TO_CAT.get(alias, 0)
        for _, _, source, meta in rows:
            site = str(source.get('site') or '').strip()
            source_name = self._safe_part(meta.get('name') or source.get('name') or site, site)
            base_name = source_name
            suffix = 2
            while source_name in used_names:
                source_name = '%s%d' % (base_name, suffix)
                suffix += 1
            used_names.add(source_name)

            episodes = []
            used_plays = set()
            raw_episodes = source.get('episodes') or []
            for index, episode in enumerate(raw_episodes, start=1):
                if not isinstance(episode, dict):
                    continue
                play_num = self._text(
                    episode.get('playlink_num')
                    or episode.get('period_alias')
                    or episode.get('sort')
                    or index
                )
                if not play_num or play_num in used_plays:
                    continue
                used_plays.add(play_num)
                name = self._episode_name(episode, play_num, len(raw_episodes), cat)
                play_url = '%s/play/%s/%s/%s/%s' % (
                    self.host,
                    quote(alias, safe=''),
                    quote(item_id, safe=''),
                    quote(site, safe=''),
                    quote(play_num, safe=''),
                )
                episodes.append('%s$%s' % (self._safe_part(name, '播放'), play_url))
            if episodes:
                play_from.append(source_name)
                play_urls.append('#'.join(episodes))

        if play_urls:
            return play_from, play_urls

        playlinks = detail.get('playlinks') if isinstance(detail.get('playlinks'), dict) else {}
        for site, official_url in playlinks.items():
            if not self._is_http(official_url):
                continue
            name = self._safe_part(metadata.get(site, {}).get('name') or site, '官方线路')
            play_from.append(name)
            play_urls.append('正片$' + str(official_url))
        return play_from, play_urls

    def _source_metadata(self):
        if self.source_meta and time.time() - self.source_meta_time < 1800:
            return self.source_meta
        try:
            payload = self._api('/api/play-sources')
            rows = payload.get('sources') if isinstance(payload.get('sources'), list) else []
            metadata = {}
            for row in rows:
                if isinstance(row, dict) and row.get('site'):
                    metadata[str(row['site'])] = dict(row)
            if metadata:
                self.source_meta = metadata
                self.source_meta_time = time.time()
        except Exception as error:
            self.log('真狼影视线路配置加载失败: %s' % error)
        return self.source_meta

    def _episode_name(self, episode, play_num, total, cat):
        period = self._text(episode.get('period'))
        title = self._text(episode.get('name'))
        if cat == 3 and period:
            name = period + ((' ' + title) if title and title != period else '')
        elif title:
            name = title
        elif total == 1:
            name = '正片'
        elif str(play_num).isdigit():
            name = '第%s集' % play_num
        else:
            name = str(play_num)
        return name[:80]

    def _play_result(self, media_url, declared_headers, allow_proxy=False):
        media_url = self._absolute_url(media_url, self.host + '/')
        headers = self._media_headers(declared_headers)
        is_hls = self._is_hls(media_url)
        result_url = media_url
        if is_hls and allow_proxy:
            proxy_url = self._manifest_proxy_url(media_url)
            if proxy_url:
                result_url = proxy_url
        result = {
            'parse': 0,
            'playUrl': '',
            'url': result_url,
            'header': headers,
        }
        if is_hls:
            result.update({
                'type': 'm3u8',
                'format': 'application/x-mpegURL',
                'contentType': 'application/x-mpegURL',
            })
        return result

    def _manifest_proxy_url(self, media_url):
        return self._local_proxy_url('zlys_m3u8', media_url)

    def _local_proxy_url(self, proxy_type, remote_url):
        remote_url = str(remote_url or '').strip()
        if not self._is_http(remote_url):
            return ''
        try:
            proxy = str(self.getProxyUrl() or '')
        except Exception:
            proxy = ''
        if not proxy:
            return ''
        separator = '&' if '?' in proxy else '?'
        signature = self._proxy_signature(proxy_type, remote_url)
        return '%s%stype=%s&url=%s&sig=%s' % (
            proxy,
            separator,
            quote(proxy_type, safe=''),
            quote(remote_url, safe=''),
            signature,
        )

    def _proxy_signature(self, proxy_type, remote_url):
        message = ('%s\n%s' % (proxy_type, remote_url)).encode('utf-8')
        return hmac.new(self.proxy_secret, message, hashlib.sha256).hexdigest()

    def _valid_proxy_signature(self, proxy_type, remote_url, signature):
        if not signature:
            return False
        expected = self._proxy_signature(proxy_type, remote_url)
        return hmac.compare_digest(expected, str(signature))

    def _rewrite_manifest(self, manifest, base_url):
        output = []
        next_is_playlist = False
        for raw_line in str(manifest or '').replace('\r', '').split('\n'):
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith('#'):
                tag = line.split(':', 1)[0].upper()
                if tag == '#EXT-X-STREAM-INF':
                    next_is_playlist = True

                def rewrite_uri(match):
                    remote_url = self._absolute_url(match.group(2), base_url)
                    proxy_type = ''
                    if tag in (
                        '#EXT-X-MEDIA',
                        '#EXT-X-I-FRAME-STREAM-INF',
                        '#EXT-X-RENDITION-REPORT',
                    ) or self._is_hls(remote_url):
                        proxy_type = 'zlys_m3u8'
                    elif tag in ('#EXT-X-MAP', '#EXT-X-PART', '#EXT-X-PRELOAD-HINT'):
                        proxy_type = 'zlys_media'
                    if proxy_type:
                        remote_url = self._local_proxy_url(proxy_type, remote_url) or remote_url
                    return 'URI=%s%s%s' % (
                        match.group(1), remote_url, match.group(1)
                    )

                line = re.sub(
                    r'URI=(["\'])(.*?)(\1)',
                    rewrite_uri,
                    line,
                    flags=re.I,
                )
                output.append(line)
            else:
                remote_url = self._absolute_url(line, base_url)
                proxy_type = 'zlys_m3u8' if next_is_playlist or self._is_hls(remote_url) else 'zlys_media'
                output.append(self._local_proxy_url(proxy_type, remote_url) or remote_url)
                next_is_playlist = False
        return '\n'.join(output) + '\n'

    def _page_count(self, html_text, current):
        data = self._doc(html_text)
        pages = [max(1, self._int(current, 1))]
        for anchor in data('a[href*="page="]').items():
            href = html.unescape(str(anchor.attr('href') or ''))
            try:
                value = parse_qs(urlparse(href).query).get('page', [''])[0]
                page = self._int(value, 0)
                if page > 0:
                    pages.append(page)
            except Exception:
                continue
        return max(pages)

    def _detail_dom_fields(self, data):
        fields = {}
        for row in data('.detail-hero__meta-row').items():
            key = self._clean(row('dt').eq(0).text()).rstrip(':：')
            value = self._clean(row('dd').eq(0).text())
            if key and value:
                fields[key] = value
        return fields

    def _detail_url(self, value):
        value = html.unescape(str(value or '').strip())
        if self._is_http(value):
            return value
        if '@@' in value:
            alias, item_id = value.split('@@', 1)
            return '%s/detail/%s/%s' % (
                self.host, quote(self._category_alias(alias), safe=''), quote(item_id, safe='')
            )
        if value.startswith('/'):
            return urljoin(self.host + '/', value)
        if value.startswith('detail/'):
            return urljoin(self.host + '/', '/' + value)
        match = re.match(r'^([a-z]+)/([^/?#]+)$', value, re.I)
        if match:
            return '%s/detail/%s/%s' % (self.host, match.group(1), match.group(2))
        return '%s/detail/movie/%s' % (self.host, quote(value, safe=''))

    def _detail_parts(self, value):
        match = re.search(r'/detail/([^/?#]+)/([^/?#]+)', urlparse(str(value or '')).path, re.I)
        return (match.group(1).lower(), match.group(2)) if match else ('', '')

    def _is_site_url(self, value):
        try:
            target = urlparse(str(value or ''))
            site = urlparse(self.host)
            target_port = target.port or (443 if target.scheme == 'https' else 80)
            site_port = site.port or (443 if site.scheme == 'https' else 80)
            return (
                target.scheme == site.scheme
                and (target.hostname or '').lower() == (site.hostname or '').lower()
                and target_port == site_port
                and not target.username
                and not target.password
            )
        except Exception:
            return False

    def _play_url(self, value):
        value = html.unescape(str(value or '').strip())
        if self._is_http(value):
            return value
        if value.startswith('/'):
            return urljoin(self.host + '/', value)
        if value.startswith('play/'):
            return urljoin(self.host + '/', '/' + value)
        return ''

    def _category_alias(self, value):
        raw = str(value or '').strip().lower()
        if self._is_http(raw):
            raw = urlparse(raw).path
        match = re.search(r'/category/([^/?#]+)', raw)
        if match:
            raw = match.group(1)
        raw = raw.strip('/').split('/', 1)[0]
        if raw.isdigit():
            raw = self.CAT_TO_ALIAS.get(self._int(raw), 'movie')
        return raw if raw in self.ALIAS_TO_CAT else 'movie'

    def _filters(self):
        years = [('全部', '')] + [(str(year), str(year)) for year in range(2026, 2006, -1)]
        years.append(('更早', 'lt_year'))
        result = {}
        for _, alias, _ in self.CLASS_INFO:
            result[alias] = [
                {
                    'key': 'rank', 'name': '排序',
                    'value': [{'n': '全部', 'v': ''}] + [
                        {'n': name, 'v': value} for name, value in self.RANKS[alias]
                    ],
                },
                {
                    'key': 'type', 'name': '类型',
                    'value': [{'n': '全部', 'v': ''}] + [
                        {'n': item, 'v': item} for item in self.GENRES[alias]
                    ],
                },
                {
                    'key': 'year', 'name': '年份',
                    'value': [{'n': name, 'v': value} for name, value in years],
                },
                {
                    'key': 'area', 'name': '地区',
                    'value': [{'n': '全部', 'v': ''}] + [
                        {'n': item, 'v': item} for item in self.AREAS[alias]
                    ],
                },
            ]
        return result

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
        if not raw or raw.lower().startswith('data:image'):
            return ''
        return self._absolute_url(raw, page_url or self.host + '/')

    def _best_picture(self, primary, fallbacks):
        values = [primary]
        if isinstance(fallbacks, list):
            values.extend(fallbacks)
        for value in values:
            raw = str(value or '').strip()
            if raw and not urlparse(raw).path.endswith('.'):
                return raw
        return str(primary or '').strip()

    def _media_headers(self, declared=None):
        result = {
            'User-Agent': self.headers['User-Agent'],
            'Accept': '*/*',
        }
        if isinstance(declared, dict):
            for key, value in declared.items():
                name = str(key or '').strip()
                if name.lower() in ('referer', 'origin', 'host', 'cookie', 'content-length'):
                    continue
                if name and value is not None:
                    result[name] = str(value)
        return result

    def _page_headers(self, referer=''):
        return {
            'User-Agent': self.headers['User-Agent'],
            'Accept': self.headers.get('Accept', '*/*'),
            'Referer': referer or self.host + '/',
        }

    def _absolute_url(self, value, base=''):
        raw = html.unescape(str(value or '')).replace('\\/', '/').strip()
        raw = re.sub(r'^(https?):/{3,}', r'\1://', raw, flags=re.I)
        if raw.startswith('//'):
            return 'https:' + raw
        if not raw:
            return ''
        if re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:', raw):
            return raw
        return urljoin(base or self.host + '/', raw)

    @staticmethod
    def _is_http(value):
        return str(value or '').lower().startswith(('http://', 'https://'))

    @staticmethod
    def _looks_like_media(value):
        return bool(re.search(r'\.(?:m3u8|mp4|m4v|flv|webm|ts|php)(?:$|[?#])', str(value or ''), re.I))

    def _is_hls(self, value):
        path = urlparse(str(value or '')).path.lower()
        return path.endswith(('.m3u8', '.php')) or '.m3u8' in str(value or '').lower()

    @staticmethod
    def _valid_remote_url(value):
        try:
            parsed = urlparse(str(value or ''))
            host = (parsed.hostname or '').lower().rstrip('.')
            if (
                parsed.scheme not in ('http', 'https')
                or not host
                or parsed.username
                or parsed.password
            ):
                return False
            port = parsed.port or (443 if parsed.scheme == 'https' else 80)
            literal_host = True
            try:
                addresses = [ipaddress.ip_address(host)]
            except ValueError:
                literal_host = False
                if host == 'localhost' or host.endswith('.localhost'):
                    return False
                records = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
                addresses = [
                    ipaddress.ip_address(record[4][0].split('%', 1)[0])
                    for record in records
                ]
            if not addresses:
                return False
            for address in addresses:
                if address.version == 6 and address.ipv4_mapped:
                    address = address.ipv4_mapped
                # Clash-style fake DNS commonly maps public hostnames into
                # 198.18.0.0/15 before forwarding them through its tunnel.
                fake_dns = (
                    not literal_host
                    and address in ipaddress.ip_network('198.18.0.0/15')
                )
                if not address.is_global and not fake_dns:
                    return False
            return True
        except Exception:
            return False

    @staticmethod
    def _strip_png_ts(data):
        content = bytes(data or b'')
        packet_size = 188
        sync_packets = 16
        last_start = min(len(content) - packet_size * sync_packets, 8192)
        if last_start < 0:
            return None
        for offset in range(last_start + 1):
            if content[offset] != 0x47:
                continue
            if not all(
                content[offset + packet_size * index] == 0x47
                for index in range(1, sync_packets)
            ):
                continue
            size = len(content) - offset
            size -= size % packet_size
            if size >= packet_size * 10:
                return content[offset:offset + size]
        return None

    @staticmethod
    def _safe_part(value, fallback=''):
        result = re.sub(r'[$#]+', ' ', str(value or '')).strip()
        return result or fallback

    @staticmethod
    def _clean_title(value):
        return re.sub(r'\s*\((?:19|20)\d{2}\)\s*$', '', str(value or '')).strip()

    @staticmethod
    def _clean(value):
        return re.sub(r'\s+', ' ', html.unescape(str(value or ''))).strip()

    def _text(self, value):
        if value is None or value == '$undefined':
            return ''
        if isinstance(value, (list, tuple)):
            return ' / '.join(self._text(item) for item in value if self._text(item))
        if isinstance(value, dict):
            return ''
        return self._clean(value)

    @staticmethod
    def _parse_config(value):
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
        self.session.proxies.update(self.proxies)

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
        return declared if declared.startswith('image/') else (
            mimetypes.guess_type('cover.jpg')[0] or 'application/octet-stream'
        )
