# -*- coding: utf-8 -*-
import html
import base64
import json
import math
import re
import sys
import time
from urllib.parse import quote, urljoin, urlparse

import requests
import urllib3
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from lxml import etree
from pyquery import PyQuery as pq

sys.path.append('..')
from base.spider import Spider


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class Spider(Spider):

    HOST = 'https://hjsqn.com'
    IMAGE_KEY = b'f5d965df75336270'
    IMAGE_IV = b'97b60394abc2fbe1'

    def __init__(self):
        self.host = self.HOST
        self.ext = ''
        self.session = requests.Session()
        self.direct_session = requests.Session()
        self.direct_session.trust_env = False
        self.proxies = {}
        self.proxy_retry_after = 0
        self.cover_cache = {}
        self.headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/138.0.0.0 Safari/537.36'
            ),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        }
        self.classes = [
            {'type_name': '全部更新', 'type_id': '/'},
            {'type_name': '海角原创', 'type_id': '/category/hjyc/'},
            {'type_name': '海角乱伦', 'type_id': '/category/hjll/'},
            {'type_name': '海角吃瓜', 'type_id': '/category/hjcg/'},
            {'type_name': '海角探花', 'type_id': '/category/hjth/'},
            {'type_name': '海角网黄', 'type_id': '/category/hjwh/'},
        ]

    def getName(self):
        return '海角社区'

    def getDependence(self):
        return []

    def setExtendInfo(self, extend):
        self.ext = extend or ''
        return None

    def init(self, extend=''):
        if extend:
            self.ext = extend
        else:
            self.ext = getattr(self, 'ext', '') or ''
        config = self._parse_config(self.ext)
        host = str(config.get('host') or '').strip().rstrip('/')
        if host.startswith(('http://', 'https://')):
            self.host = host
        self._set_proxy(config.get('proxy'))
        return None

    def homeLayout(self):
        return 0

    def manualVideoCheck(self):
        return False

    def isVideoFormat(self, url):
        path = urlparse(str(url or '')).path.lower()
        return path.endswith(('.m3u8', '.mp4', '.ts', '.flv'))

    def destroy(self):
        try:
            self.session.close()
            self.direct_session.close()
        except Exception:
            pass

    def homeContent(self, filter=False):
        return {'class': self.classes, 'filters': {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            response = self._request(self.host + '/')
            return {'list': self._parse_cards(response.text)}
        except Exception as error:
            self.log('HJSQN 首页加载失败: %s' % error)
            return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        page = max(1, self._int(pg, 1))
        try:
            path = str(tid or '/').strip()
            url = self._category_url(path, page)
            response = self._request(url)
            videos = self._parse_cards(response.text)
            page_count = self._page_count(response.text, page)
            return {
                'list': videos,
                'page': page,
                'pagecount': page_count,
                'limit': len(videos) or 20,
                'total': page_count * (len(videos) or 20),
            }
        except Exception as error:
            self.log('HJSQN 分类加载失败: %s' % error)
            return {'list': [], 'page': page, 'pagecount': page, 'limit': 20, 'total': 0}

    def detailContent(self, ids):
        raw_id = str(ids[0] if ids else '').strip()
        if not raw_id:
            return {'list': []}
        try:
            url = urljoin(self.host + '/', raw_id)
            response = self._request(url)
            page_url = response.url or url
            data = self._doc(response.text)
            title = self._clean(data('h1.novel-title, h1').eq(0).text()) or '海角帖子'
            post_id = self._post_id(page_url)
            images = self._content_image_urls(data, page_url)
            video_plays = []
            used_urls = set()
            for index, node in enumerate(data('.dplayer[data-config]').items(), start=1):
                config = self._json(node.attr('data-config'))
                video = config.get('video') if isinstance(config, dict) else {}
                if not isinstance(video, dict):
                    continue
                h264 = self._clean_url(video.get('url'), page_url)
                h265 = self._clean_url(video.get('h_265') or video.get('h265'), page_url)
                if h264 and h264 not in used_urls:
                    used_urls.add(h264)
                    name = '视频%d H264' % index if len(data('.dplayer[data-config]')) > 1 else 'H264原画'
                    video_plays.append('%s$%s' % (name, h264))
                if h265 and h265 not in used_urls:
                    used_urls.add(h265)
                    name = '视频%d H265' % index if len(data('.dplayer[data-config]')) > 1 else 'H265原画'
                    video_plays.append('%s$%s' % (name, h265))

            play_from = []
            play_urls = []
            if video_plays:
                play_from.append('海角视频')
                play_urls.append('#'.join(video_plays))
            if not play_urls:
                return {'list': []}

            category = self._clean(data('.detail-info-desc a[href*="/category/"]').eq(0).text())
            author = self._clean(data('.novel-info h2').eq(0).text())
            remark = self._clean(data('.detail-info-desc').text())
            vod = {
                'vod_id': page_url,
                'vod_name': title,
                'vod_pic': self._stable_cover(post_id, images[0] if images else ''),
                'vod_remarks': category or '视频',
                'vod_actor': author,
                'vod_content': remark or title,
                'vod_play_from': '$$$'.join(play_from),
                'vod_play_url': '$$$'.join(play_urls),
            }
            return {'list': [vod]}
        except Exception as error:
            self.log('HJSQN 详情加载失败: %s' % error)
            return {'list': []}

    def searchContent(self, key, quick, pg='1'):
        page = max(1, self._int(pg, 1))
        keyword = str(key or '').strip()
        if not keyword:
            return {'list': [], 'page': page, 'pagecount': page, 'limit': 20, 'total': 0}
        limit = 20
        try:
            response = self._get(
                self.host + '/Searchs/searchpagination/',
                params={
                    'keyword': keyword,
                    'type': 'posts',
                    'page': page,
                    'limit': limit,
                },
                headers=dict(self.headers, Referer=self.host + '/search/' + quote(keyword, safe='') + '/'),
                timeout=22,
                verify=False,
            )
            response.raise_for_status()
            payload = response.json()
            raw_list = payload.get('list') if isinstance(payload, dict) else []
            if isinstance(raw_list, dict):
                raw_list = raw_list.get('posts') or []
            videos = []
            for item in raw_list if isinstance(raw_list, list) else []:
                post_id = str(item.get('cid') or '').strip()
                title = self._clean(item.get('title'))
                if not post_id or not title:
                    continue
                thumbnails = item.get('thumbnails') or []
                raw_pic = ''
                if thumbnails and isinstance(thumbnails[0], dict):
                    raw_pic = str(thumbnails[0].get('url') or '')
                category = self._clean(item.get('category_name'))
                views = self._int(item.get('view', item.get('viewsNum')), 0)
                remark = category + ((' · %s浏览' % views) if views else '')
                videos.append({
                    'vod_id': '%s/archives/%s/' % (self.host, post_id),
                    'vod_name': title,
                    'vod_pic': self._stable_cover(post_id, raw_pic),
                    'vod_remarks': remark,
                    'style': {'type': 'rect', 'ratio': 1.33},
                })
            total = max(0, self._int(payload.get('total'), len(videos)))
            page_count = max(page, int(math.ceil(float(total) / limit))) if total else page
            return {
                'list': videos,
                'page': page,
                'pagecount': page_count,
                'limit': limit,
                'total': total,
            }
        except Exception as error:
            self.log('HJSQN 搜索失败: %s' % error)
            return {'list': [], 'page': page, 'pagecount': page, 'limit': limit, 'total': 0}

    def playerContent(self, flag, id, vipFlags):
        value = str(id or '').strip()
        if not value.startswith(('http://', 'https://')):
            return {'parse': 1, 'playUrl': '', 'url': self.host + '/', 'header': self.headers}
        result = {
            'parse': 0,
            'playUrl': '',
            'url': value,
            'header': {
                'User-Agent': self.headers['User-Agent'],
                'Accept-Encoding': 'identity',
                'Referer': self.host + '/',
                'Origin': self.host,
            },
        }
        if '.m3u8' in value.lower():
            result['url'] = self.getProxyUrl() + '&type=hjsqn_m3u8&url=' + quote(value, safe='')
            result['type'] = 'm3u8'
            result['format'] = 'application/x-mpegURL'
            result['contentType'] = 'application/x-mpegURL'
        return result

    def localProxy(self, param):
        image_type = str(param.get('type') or '')
        if image_type in ('hjsqn_m3u8', 'hjsqn_media'):
            return self._media_proxy(param, image_type)
        if image_type not in ('img', 'himg'):
            return [404, 'text/plain; charset=utf-8', b'not found']
        try:
            image_url = str(param.get('url') or '').strip()
            if image_type == 'himg':
                post_id = re.sub(r'\D+', '', str(param.get('id') or ''))
                if not post_id:
                    raise ValueError('缺少帖子 ID')
                image_url = self.cover_cache.get(post_id, '')
                if not image_url:
                    response = self._request('%s/archives/%s/' % (self.host, post_id))
                    urls = self._content_image_urls(self._doc(response.text), response.url)
                    if not urls:
                        raise ValueError('帖子没有封面')
                    image_url = urls[0]
                    self.cover_cache[post_id] = image_url
            if not image_url:
                raise ValueError('缺少图片地址')
            encrypted = self._get(
                image_url,
                headers={
                    'User-Agent': self.headers['User-Agent'],
                    'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
                    'Referer': self.host + '/',
                },
                timeout=25,
                verify=False,
            )
            encrypted.raise_for_status()
            image = self._decrypt_image(encrypted.content)
            return [200, self._mime(image), image]
        except Exception as error:
            self.log('HJSQN 图片代理失败: %s' % error)
            return [500, 'text/plain; charset=utf-8', b'image proxy failed']

    def _media_proxy(self, param, media_type):
        media_url = str(param.get('url') or '').strip()
        if not media_url.startswith(('http://', 'https://')):
            return [500, 'text/plain; charset=utf-8', b'invalid media url']
        try:
            response = self._get(
                media_url,
                headers=self._media_headers(),
                timeout=(10, 35),
                verify=False,
                allow_redirects=True,
            )
            response.raise_for_status()
            content = response.content
            if media_type == 'hjsqn_m3u8':
                self.log(
                    'HJSQN HLS 清单: code=%s type=%s bytes=%s url=%s'
                    % (
                        response.status_code,
                        response.headers.get('Content-Type', ''),
                        len(content),
                        media_url,
                    )
                )
                content = self._decode_hls_manifest(content)
                if not content.lstrip().startswith(b'#EXTM3U'):
                    self.log('HJSQN HLS 清单解码失败: bytes=%s head=%r' % (len(content), content[:32]))
                    return [500, 'text/plain; charset=utf-8', b'invalid hls manifest']
                playlist = content.decode('utf-8-sig', errors='replace')
                self.log(
                    'HJSQN HLS 清单解码成功(分片直连): bytes=%s segments=%s'
                    % (len(content), len(re.findall(r'^\s*[^#\s].*$', playlist, re.M)))
                )
                lines = []
                for line in playlist.splitlines():
                    value = line.strip()
                    if value.startswith('#') and 'URI="' in value:
                        line = re.sub(
                            r'URI="([^"]+)"',
                            lambda match: 'URI="%s"' % urljoin(response.url, match.group(1)),
                            line,
                        )
                        lines.append(line)
                        continue
                    if value and not value.startswith('#'):
                        lines.append(urljoin(response.url, value))
                    else:
                        lines.append(line)
                body = ('\n'.join(lines) + '\n').encode('utf-8')
                return [200, 'application/vnd.apple.mpegurl', body, {
                    'Content-Type': 'application/vnd.apple.mpegurl',
                    'Cache-Control': 'no-cache',
                    'Access-Control-Allow-Origin': '*',
                }]
            content_type = str(response.headers.get('Content-Type') or '').lower()
            if content.startswith(b'\x47'):
                content_type = 'video/mp2t'
            elif not content_type or content_type == 'image/jpeg':
                content_type = 'application/octet-stream'
            return [200, content_type, content, {
                'Cache-Control': 'no-cache',
                'Access-Control-Allow-Origin': '*',
            }]
        except Exception as error:
            self.log('HJSQN 视频代理失败: %s' % error)
            return [500, 'text/plain; charset=utf-8', b'media proxy failed']

    @staticmethod
    def _decode_hls_manifest(content):
        """Unwrap the site's nested Base64 H264 playlist response."""
        value = bytes(content or '').strip()
        for _ in range(3):
            if value.lstrip().startswith(b'#EXTM3U'):
                return value
            match = re.match(rb'[A-Za-z0-9+/]+={0,2}', value)
            if not match:
                break
            encoded = match.group(0)
            # The CDN can return an encrypted/binary error body which may start
            # with one or two Base64-looking bytes. Do not decode that prefix.
            if len(encoded) < 16 or len(encoded) < len(value) * 0.9:
                break
            encoded += b'=' * ((4 - len(encoded) % 4) % 4)
            try:
                decoded = base64.b64decode(encoded, validate=False)
            except Exception:
                break
            if not decoded or decoded == value:
                break
            value = decoded.strip()
        return value

    def _request(self, url, timeout=22):
        response = self._get(
            url, headers=self.headers, timeout=timeout, verify=False, allow_redirects=True
        )
        response.raise_for_status()
        response.encoding = response.apparent_encoding or 'utf-8'
        return response

    def _get(self, url, **kwargs):
        if not self.proxies or time.time() < self.proxy_retry_after:
            return self.direct_session.get(url, **kwargs)
        try:
            response = self.session.get(url, **kwargs)
            self.proxy_retry_after = 0
            return response
        except (requests.exceptions.ProxyError, requests.exceptions.ConnectionError) as error:
            self.proxy_retry_after = time.time() + 30
            self.direct_session.cookies.update(self.session.cookies)
            self.log('HJSQN 代理不可用，改用直连: %s' % error)
            return self.direct_session.get(url, **kwargs)

    def _media_headers(self):
        return {
            'User-Agent': self.headers['User-Agent'],
            'Accept': '*/*',
            # This CDN serves a different, non-playable H264 payload on its
            # gzip branch. Keep the response in the site's Base64 form.
            'Accept-Encoding': 'identity',
            'Referer': self.host + '/',
            'Origin': self.host,
        }

    def _parse_cards(self, html_text):
        data = self._doc(html_text)
        videos = []
        seen = set()
        for row in data('.xqbj-list-rows').items():
            anchor = row.find('.xqbj-list-rows-image > a[title]').eq(0)
            href = str(anchor.attr('href') or '').strip()
            title = self._clean(anchor.attr('title') or anchor.find('.xqbj-list-rows-image-title').text())
            post_id = self._post_id(href)
            if not href or not title or not post_id or post_id in seen:
                continue
            seen.add(post_id)
            image = anchor.find('img[z-image-loader-url]').eq(0)
            raw_pic = str(image.attr('z-image-loader-url') or '').strip()
            category = self._clean(row.find('a[href*="/category/"]').eq(0).text())
            date = self._clean(row.find('.xqbj-icon-time').parent().find('.is-desktop').text())
            count = self._clean(row.find('.list-text-play').eq(0).text())
            remark = category
            if count and count.isdigit():
                remark = ('%s · ' % category if category else '') + count + '项'
            elif date:
                remark = ('%s · ' % category if category else '') + date
            videos.append({
                'vod_id': urljoin(self.host + '/', href),
                'vod_name': title,
                'vod_pic': self._stable_cover(post_id, raw_pic),
                'vod_remarks': remark,
                'style': {'type': 'rect', 'ratio': 1.33},
            })
        return videos

    def _content_image_urls(self, data, page_url):
        result = []
        for node in data('.text.text-content img[z-image-loader-url]').items():
            raw = str(node.attr('z-image-loader-url') or '').strip().strip('`')
            absolute = urljoin(page_url, raw) if raw else ''
            if self._valid_content_image(absolute) and absolute not in result:
                result.append(absolute)
        return result

    def _stable_cover(self, post_id, fallback=''):
        if post_id:
            if fallback:
                self.cover_cache[str(post_id)] = str(fallback)
            return self.getProxyUrl() + '&type=himg&id=' + quote(str(post_id), safe='')
        return self._proxy_image(fallback) if fallback else ''

    def _proxy_image(self, url):
        if not str(url or '').startswith(('http://', 'https://')):
            return ''
        return self.getProxyUrl() + '&type=img&url=' + quote(str(url), safe='')

    def _category_url(self, path, page):
        path = '/' + str(path or '/').strip('/') + '/'
        if page <= 1:
            return self.host + path
        return self.host + path + 'page/%d/' % page

    def _page_count(self, html_text, current):
        data = self._doc(html_text)
        values = [current]
        for anchor in data('a[href*="/page/"]').items():
            match = re.search(r'/page/(\d+)/?', str(anchor.attr('href') or ''))
            if match:
                values.append(self._int(match.group(1), current))
        return max(values)

    def _decrypt_image(self, encrypted):
        if not encrypted or len(encrypted) % AES.block_size:
            raise ValueError('图片密文长度无效')
        raw = AES.new(self.IMAGE_KEY, AES.MODE_CBC, self.IMAGE_IV).decrypt(encrypted)
        try:
            return unpad(raw, AES.block_size)
        except Exception:
            return raw.rstrip(b'\x00')

    def _doc(self, value):
        text = value.decode('utf-8', errors='ignore') if isinstance(value, bytes) else str(value or '')
        try:
            parser = etree.HTMLParser(encoding='utf-8', recover=True)
            root = etree.fromstring(text.encode('utf-8', errors='ignore'), parser=parser)
            return pq(root) if root is not None else pq('<html></html>')
        except Exception:
            return pq('<html></html>')

    def _parse_config(self, value):
        if isinstance(value, dict):
            return value
        text = str(value or '').strip()
        if text.startswith('{'):
            try:
                return json.loads(text)
            except Exception:
                pass
        if text.startswith(('http://', 'https://')):
            return {'host': text}
        return {}

    def _set_proxy(self, value):
        proxy = str(value or '').strip()
        self.proxies = {}
        self.proxy_retry_after = 0
        self.session.proxies.clear()
        if not proxy:
            return
        if '://' not in proxy:
            proxy = 'http://' + proxy
        self.proxies = {'http': proxy, 'https': proxy}
        self.session.proxies.update(self.proxies)

    @staticmethod
    def _json(value):
        try:
            return json.loads(html.unescape(str(value or '')))
        except Exception:
            return {}

    @staticmethod
    def _clean_url(value, page_url):
        url = html.unescape(str(value or '')).replace('\\/', '/').strip()
        return urljoin(page_url, url) if url else ''

    @staticmethod
    def _post_id(value):
        match = re.search(r'/archives/(\d+)', str(value or ''))
        return match.group(1) if match else ''

    @staticmethod
    def _valid_content_image(url):
        low = str(url or '').lower()
        return (
            low.startswith(('http://', 'https://'))
            and not any(x in low for x in ('default-avatar', '/logo', '/icon', 'loading', 'qrcode'))
        )

    @staticmethod
    def _clean(value):
        return re.sub(r'\s+', ' ', html.unescape(str(value or ''))).strip()

    @staticmethod
    def _int(value, default=0):
        try:
            return int(value)
        except Exception:
            return default

    @staticmethod
    def _mime(data):
        if data.startswith(b'\x89PNG'):
            return 'image/png'
        if data.startswith(b'GIF8'):
            return 'image/gif'
        if data.startswith(b'RIFF') and data[8:12] == b'WEBP':
            return 'image/webp'
        if data.startswith(b'\xff\xd8'):
            return 'image/jpeg'
        return 'application/octet-stream'
