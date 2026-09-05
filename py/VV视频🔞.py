# -*- coding: utf-8 -*-
import base64
import html
import json
import math
import mimetypes
import re
import threading
import time
from urllib.parse import quote, urljoin, urlparse

import requests
import urllib3
from Crypto.Cipher import AES
from Crypto.Hash import SHA256
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Util.Padding import unpad

import sys

sys.path.append('..')
from base.spider import Spider


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class Spider(Spider):

    WEB_HOST = 'https://351.dofd1fe.com:25118'
    ENTRY_PATH = '/video'
    DEFAULT_CHANNEL = 'vvmossdh'
    IMAGE_KEY = b'H0Z%7n#k$H8*M7xSE^N@8xXZPG*RZ&wY'
    PAGE_SIZE = 24
    FALLBACK_APIS = [
        'https://94xhn.pt6nth.com:51111',
        'https://cssy1.nb184a.com:51777',
        'https://xhs0.l34zkw.com:51666',
        'https://hao20.110ztv.com:52000',
        'https://14sn.1psisk.com:51888',
        'https://wlq.pmjqlw8.com:51888',
        'https://jvx.i3ubxvj.com:25118',
        'https://cdz.rkfwzdc.com:52000',
        'https://esi.vobis8e.com:51111',
        'https://vqh.z4shq2v.com:51666',
    ]
    FALLBACK_CLASSES = [
        ('热门', 0, 'hot'),
        ('最新', 0, 'last'),
        ('传媒', 266, 'label'),
        ('黑料', 130, 'cate'),
        ('国产', 262, 'label'),
        ('日本AV', 263, 'label'),
        ('欧美', 264, 'label'),
        ('动漫', 267, 'label'),
        ('三级', 341, 'label'),
        ('AI换脸', 342, 'label'),
        ('AV无码', 343, 'label'),
        ('探花', 143, 'cate'),
        ('SM', 127, 'cate'),
        ('乱伦', 144, 'cate'),
        ('颜值', 178, 'cate'),
        ('人妻少妇', 153, 'cate'),
        ('自拍', 133, 'cate'),
        ('中文字幕', 146, 'cate'),
        ('多男一女', 246, 'cate'),
        ('多女一男', 247, 'cate'),
        ('主播大秀', 142, 'cate'),
        ('麻豆', 358, 'label'),
        ('擦边短剧', 356, 'label'),
    ]

    def __init__(self):
        self.ext = ''
        self.web_host = self.WEB_HOST
        self.channel = self.DEFAULT_CHANNEL
        self._channel_locked = False
        self.session = requests.Session()
        self.headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/138.0.0.0 Safari/537.36'
            ),
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        }
        self.api_candidates = []
        self._discovered_at = 0
        self._discover_lock = threading.Lock()

    def getName(self):
        return 'VV视频'

    def getDependence(self):
        return []

    def setExtendInfo(self, extend):
        self.ext = extend or ''
        return None

    def init(self, extend=''):
        self.ext = getattr(self, 'ext', '') or extend or ''
        config = self._parse_config(self.ext)
        host = str(config.get('host') or '').strip().rstrip('/')
        if host.startswith(('http://', 'https://')):
            self.web_host = host
        channel = str(config.get('channel') or '').strip()
        if channel:
            self.channel = channel
            self._channel_locked = True
        api = config.get('api') or config.get('apis')
        if isinstance(api, str):
            api = [x.strip() for x in api.split(',')]
        if isinstance(api, list):
            self.api_candidates = self._unique_hosts(api)
        return None

    def homeLayout(self):
        return 0

    def manualVideoCheck(self):
        return False

    def isVideoFormat(self, url):
        value = str(url or '').lower().split('?', 1)[0]
        return value.endswith(('.m3u8', '.mp4', '.ts', '.flv'))

    def destroy(self):
        try:
            self.session.close()
        except Exception:
            pass

    def homeContent(self, filter=False):
        classes = []
        try:
            nav = self._api('/api/old_v3/video/nav')
            for item in nav if isinstance(nav, list) else []:
                item_type = str(item.get('type') or '').strip().lower()
                if item_type == 'home':
                    continue
                item_id = self._int(item.get('id', item.get('tid')), 0)
                name = self._text(item.get('title') or item.get('name'))
                if name and item_type:
                    classes.append({
                        'type_name': name,
                        'type_id': self._category_id(item_id, item_type),
                    })
        except Exception as error:
            self.log('VV 分类加载失败，使用内置分类: %s' % error)
        if not classes:
            classes = [
                {'type_name': name, 'type_id': self._category_id(item_id, item_type)}
                for name, item_id, item_type in self.FALLBACK_CLASSES
            ]
        return {'class': classes, 'filters': {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            sections = self._api('/api/old_v3/video/home')
            videos = []
            seen = set()
            for section in sections if isinstance(sections, list) else []:
                section_name = self._text(section.get('title') or section.get('name'))
                for item in section.get('list') or []:
                    video = self._video(item, section_name)
                    video_id = video.get('vod_id')
                    if video_id and video_id not in seen:
                        seen.add(video_id)
                        videos.append(video)
                    if len(videos) >= 48:
                        return {'list': videos}
            return {'list': videos}
        except Exception as error:
            self.log('VV 首页加载失败: %s' % error)
            return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        page = max(1, self._int(pg, 1))
        try:
            item_id, item_type = self._parse_category_id(tid)
            data = self._api('/api/old_v3/video/getList', {
                'id': item_id,
                'type': item_type,
                'page': page,
                'size': self.PAGE_SIZE,
            })
            items = data.get('list') if isinstance(data, dict) else []
            total = self._int(data.get('total'), len(items)) if isinstance(data, dict) else 0
            videos = [self._video(item) for item in items or []]
            page_count = max(page, int(math.ceil(float(total) / self.PAGE_SIZE))) if total else page
            return {
                'list': videos,
                'page': page,
                'pagecount': page_count,
                'limit': self.PAGE_SIZE,
                'total': total,
            }
        except Exception as error:
            self.log('VV 分类加载失败: %s' % error)
            return {'list': [], 'page': page, 'pagecount': page, 'limit': self.PAGE_SIZE, 'total': 0}

    def detailContent(self, ids):
        video_id = str(ids[0] if ids else '').strip()
        if not video_id:
            return {'list': []}
        try:
            item = self._api('/api/v3/home/public/video/long/detail', {'id': video_id})
            if not isinstance(item, dict) or not item:
                return {'list': []}
            sources = self._play_sources(item)
            if not sources:
                return {'list': []}
            play_from = []
            play_urls = []
            used_names = set()
            for index, source in enumerate(sources, start=1):
                name = self._safe_play_name(source.get('name')) or '线路%d' % index
                base_name = name
                suffix = 2
                while name in used_names:
                    name = '%s%d' % (base_name, suffix)
                    suffix += 1
                used_names.add(name)
                play_from.append(name)
                play_urls.append('播放$' + source['url'])
            vod = {
                'vod_id': video_id,
                'vod_name': self._text(item.get('title')) or 'VV视频',
                'vod_pic': self._image_url(item.get('upload_thumb') or item.get('thumb')),
                'vod_remarks': self._text(item.get('label') or item.get('duration')),
                'vod_year': self._text(item.get('years')),
                'vod_area': self._text(item.get('region')),
                'vod_actor': self._text(item.get('actor')),
                'vod_content': self._clean_html(item.get('desc')) or self._text(item.get('classify')),
                'vod_play_from': '$$$'.join(play_from),
                'vod_play_url': '$$$'.join(play_urls),
            }
            return {'list': [vod]}
        except Exception as error:
            self.log('VV 详情加载失败: %s' % error)
            return {'list': []}

    def searchContent(self, key, quick, pg='1'):
        page = max(1, self._int(pg, 1))
        keyword = str(key or '').strip()
        if not keyword:
            return {'list': [], 'page': page, 'pagecount': page, 'limit': 10, 'total': 0}
        try:
            data = self._api('/api/old_v3/video/search', {
                'keyword': keyword,
                'page': page,
                'limit': self.PAGE_SIZE,
            })
            if not isinstance(data, dict):
                data = {}
            items = data.get('data') if isinstance(data.get('data'), list) else data.get('list') or []
            total = self._int(data.get('total'), len(items))
            limit = max(1, self._int(data.get('per_page'), len(items) or 10))
            page_count = self._int(data.get('last_page'), 0)
            if page_count <= 0:
                page_count = max(page, int(math.ceil(float(total) / limit))) if total else page
            return {
                'list': [self._video(item) for item in items],
                'page': page,
                'pagecount': page_count,
                'limit': limit,
                'total': total,
            }
        except Exception as error:
            self.log('VV 搜索失败: %s' % error)
            return {'list': [], 'page': page, 'pagecount': page, 'limit': 10, 'total': 0}

    def playerContent(self, flag, id, vipFlags):
        url = str(id or '').strip()
        return {
            'parse': 0 if url.startswith(('http://', 'https://')) else 1,
            'playUrl': '',
            'url': url,
            'header': {
                'User-Agent': self.headers['User-Agent'],
                'Referer': self.web_host + self.ENTRY_PATH,
            },
        }

    def localProxy(self, param):
        if param.get('type') != 'img' or not param.get('url'):
            return [404, 'text/plain; charset=utf-8', b'not found']
        try:
            url = str(param['url'])
            response = self.session.get(
                url,
                headers={
                    'User-Agent': self.headers['User-Agent'],
                    'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
                    'Referer': self.web_host + self.ENTRY_PATH,
                },
                timeout=20,
                verify=False,
            )
            response.raise_for_status()
            data = response.content
            if urlparse(url).path.lower().endswith('.enc'):
                if len(data) <= 16:
                    raise ValueError('加密封面长度不足')
                iv, encrypted = data[:16], data[16:]
                data = unpad(AES.new(self.IMAGE_KEY, AES.MODE_CBC, iv).decrypt(encrypted), AES.block_size)
            return [200, self._image_mime(data, response.headers.get('Content-Type')), data]
        except Exception as error:
            self.log('VV 封面代理失败: %s' % error)
            return [500, 'text/plain; charset=utf-8', b'image proxy failed']

    def _api(self, path, params=None):
        params = dict(params or {})
        params.setdefault('channel', self.channel)
        last_error = None
        for attempt in range(2):
            candidates = self._get_api_candidates(force=attempt > 0)
            for api in candidates:
                try:
                    response = self.session.get(
                        api + path,
                        params=params,
                        headers=self.headers,
                        timeout=16,
                        verify=False,
                    )
                    response.raise_for_status()
                    payload = self._unwrap_envelopes(response.json())
                    code = self._int(payload.get('code'), 200) if isinstance(payload, dict) else 200
                    if code not in (0, 200):
                        raise RuntimeError(self._text(payload.get('message')) or 'API code %s' % code)
                    if api != self.api_candidates[0]:
                        self.api_candidates.remove(api)
                        self.api_candidates.insert(0, api)
                    return payload.get('data') if isinstance(payload, dict) else payload
                except Exception as error:
                    last_error = error
        raise RuntimeError(last_error or '没有可用 API')

    def _get_api_candidates(self, force=False):
        if self.api_candidates and not force and time.time() - self._discovered_at < 1800:
            return list(self.api_candidates)
        with self._discover_lock:
            if self.api_candidates and not force and time.time() - self._discovered_at < 1800:
                return list(self.api_candidates)
            discovered = []
            try:
                html_text = self._verified_home()
                discovered = self._extract_api_urls(html_text)
                discovered_channel = self._extract_channel(html_text)
                if discovered_channel and not self._channel_locked:
                    self.channel = discovered_channel
            except Exception as error:
                self.log('VV 动态 API 发现失败: %s' % error)
            self.api_candidates = self._unique_hosts(
                discovered + self.api_candidates + self.FALLBACK_APIS
            )
            self._discovered_at = time.time()
            return list(self.api_candidates)

    def _verified_home(self):
        entry_url = urljoin(self.web_host + '/', self.ENTRY_PATH.lstrip('/'))
        response = self.session.get(
            entry_url,
            headers={**self.headers, 'Accept': 'text/html,application/xhtml+xml'},
            timeout=18,
            verify=False,
        )
        response.raise_for_status()
        text = response.text
        challenge = self._challenge_script(text)
        if not challenge:
            return text
        match = re.search(r'p=(\{.*?\}),d=document', challenge, re.S)
        if not match:
            raise ValueError('未找到验证参数')
        task = json.loads(match.group(1))
        meta = {
            'ua': self.headers['User-Agent'],
            'lang': 'zh-CN',
            'tz': 'Asia/Shanghai',
            'screen': '1920x1080',
            'webdriver': False,
            'framed': False,
        }
        proof = self._proof(task['task'])
        key_text = '|'.join([
            str(task['nonce']),
            str(task['issuedAt']),
            meta['ua'],
            meta['lang'],
            meta['tz'],
            meta['screen'],
            str(proof),
        ])
        parsed_entry = urlparse(response.url or entry_url)
        request_path = parsed_entry.path or self.ENTRY_PATH
        if parsed_entry.query:
            request_path += '?' + parsed_entry.query
        body = {
            'nonce': task['nonce'],
            'issuedAt': task['issuedAt'],
            'key': self._fnv1a(key_text),
            'meta': meta,
            'proof': proof,
            'path': request_path,
        }
        origin = '%s://%s' % (parsed_entry.scheme, parsed_entry.netloc)
        verified = self.session.post(
            urljoin(self.web_host + '/', str(task['postUrl']).lstrip('/')),
            headers={
                **self.headers,
                'Content-Type': 'application/json',
                'Origin': origin,
                'Referer': response.url or entry_url,
            },
            json=body,
            timeout=18,
            verify=False,
        )
        verified.raise_for_status()
        if self._challenge_script(verified.text):
            raise ValueError('站点验证未通过')
        return verified.text

    def _challenge_script(self, text):
        return next((
            script for script in self._decoded_xor_scripts(text)
            if 'postUrl' in script and 'difficulty' in script and 'issuedAt' in script
        ), '')

    @staticmethod
    def _extract_channel(text):
        patterns = (
            r"(?:window\.)?__APP_CHANNEL__\s*=\s*['\"]([^'\"]+)['\"]",
            r"(?:window\.)?_CHANNEL_DATA\s*=\s*['\"]([^'\"]+)['\"]",
            r"(?:window\.)?__rv\s*=\s*['\"]([^'\"]+)['\"]",
        )
        for pattern in patterns:
            match = re.search(pattern, text or '')
            if match and match.group(1).strip():
                return match.group(1).strip()
        return ''

    def _extract_api_urls(self, html_text):
        urls = []
        for decoded in self._decoded_xor_scripts(html_text):
            try:
                value = json.loads(decoded)
            except Exception:
                continue
            if isinstance(value, list):
                urls.extend(value)
        return self._unique_hosts(urls)

    @staticmethod
    def _decoded_xor_scripts(text):
        result = []
        pattern = r'const _0="([^"]+)",_1="([^"]+)",_2="([^"]*)"'
        for encoded, key, _ in re.findall(pattern, text or ''):
            try:
                raw = base64.b64decode(encoded)
                key_bytes = key.encode('utf-8')
                decoded = bytes(value ^ key_bytes[index % len(key_bytes)] for index, value in enumerate(raw))
                result.append(decoded.decode('utf-8'))
            except Exception:
                continue
        return result

    @classmethod
    def _proof(cls, task):
        seed = str(task.get('seed') or '')
        difficulty = max(1, cls._int(task.get('difficulty'), 1))
        maximum = max(1, cls._int(task.get('maxIterations'), 150000))
        prefix = '0' * difficulty
        for value in range(maximum):
            if cls._fnv1a('%s|%d' % (seed, value)).startswith(prefix):
                return value
        raise ValueError('验证计算失败')

    @staticmethod
    def _fnv1a(value):
        number = 2166136261
        for char in str(value):
            number = ((number ^ ord(char)) * 16777619) & 0xFFFFFFFF
        return '%08x' % number

    def _unwrap_envelopes(self, payload):
        value = payload
        for _ in range(5):
            value, changed = self._unwrap_once(value)
            if not changed:
                break
        return value

    def _unwrap_once(self, value):
        if isinstance(value, dict):
            if isinstance(value.get('key'), str) and isinstance(value.get('data'), str):
                output = dict(value)
                output['data'] = self._decrypt_envelope(value['data'], value['key'])
                output.pop('key', None)
                return output, True
            output = {}
            changed = False
            for key, child in value.items():
                output[key], child_changed = self._unwrap_once(child)
                changed = changed or child_changed
            return output, changed
        if isinstance(value, list):
            output = []
            changed = False
            for child in value:
                unwrapped, child_changed = self._unwrap_once(child)
                output.append(unwrapped)
                changed = changed or child_changed
            return output, changed
        return value, False

    def _decrypt_envelope(self, encrypted, password):
        try:
            shifted = ''.join(chr(ord(char) - 3) for char in encrypted)
            raw = self._b64decode(shifted)
            if len(raw) < 44:
                raise ValueError('AES-GCM 数据长度不足')
            salt, iv, ciphertext = raw[:16], raw[16:28], raw[28:]
            key = PBKDF2(
                password.encode('utf-8'),
                salt,
                dkLen=32,
                count=1000,
                hmac_hash_module=SHA256,
            )
            plain = AES.new(key, AES.MODE_GCM, nonce=iv).decrypt_and_verify(
                ciphertext[:-16], ciphertext[-16:]
            )
        except Exception:
            raw = self._b64decode(encrypted)
            key = password.encode('utf-8')
            if not key:
                raise ValueError('解密 key 为空')
            plain = bytes(value ^ key[index % len(key)] for index, value in enumerate(raw))
        text = plain.decode('utf-8')
        try:
            return json.loads(text)
        except Exception:
            return text

    @staticmethod
    def _b64decode(value):
        data = re.sub(r'\s+', '', str(value or '')).replace('-', '+').replace('_', '/')
        data += '=' * ((4 - len(data) % 4) % 4)
        return base64.b64decode(data)

    def _video(self, item, fallback_remark=''):
        item = item if isinstance(item, dict) else {}
        video_id = item.get('id') or item.get('video_id') or ''
        remark = self._text(item.get('label') or item.get('duration') or fallback_remark)
        return {
            'vod_id': str(video_id),
            'vod_name': self._text(item.get('title') or item.get('name')),
            'vod_pic': self._image_url(item.get('upload_thumb') or item.get('thumb')),
            'vod_remarks': remark,
            'style': {'type': 'rect', 'ratio': 1.78},
        }

    def _image_url(self, value):
        url = str(value or '').strip()
        if not url:
            return ''
        if not url.startswith(('http://', 'https://')):
            url = urljoin(self.web_host + '/', url.lstrip('/'))
        if urlparse(url).path.lower().endswith('.enc'):
            return self.getProxyUrl() + '&type=img&url=' + quote(url, safe='')
        return url

    def _play_sources(self, item):
        signed_url = str(item.get('play_hls_url') or '').strip()
        href = str(item.get('href') or '').strip()
        cdn_list = item.get('cdn_list') if isinstance(item.get('cdn_list'), list) else []
        sources = []
        if signed_url:
            if cdn_list:
                for index, cdn in enumerate(cdn_list, start=1):
                    cdn_id = str(cdn.get('id') if cdn.get('id') is not None else index)
                    url = self._replace_query_value(signed_url, 'cdnId', cdn_id)
                    sources.append({'name': self._text(cdn.get('title')) or '线路%d' % index, 'url': url})
            else:
                sources.append({'name': '默认线路', 'url': signed_url})
        elif href:
            if href.startswith(('http://', 'https://')):
                sources.append({'name': '默认线路', 'url': href})
            elif cdn_list:
                for index, cdn in enumerate(cdn_list, start=1):
                    base = str(cdn.get('videoUrl') or '').strip().rstrip('/')
                    if base:
                        sources.append({
                            'name': self._text(cdn.get('title')) or '线路%d' % index,
                            'url': base + '/' + href.lstrip('/'),
                        })
        return [source for source in sources if source.get('url', '').startswith(('http://', 'https://'))]

    @staticmethod
    def _replace_query_value(url, key, value):
        pattern = r'([?&])%s=[^&#]*' % re.escape(key)
        if re.search(pattern, url, re.I):
            return re.sub(pattern, lambda match: match.group(1) + key + '=' + quote(value), url, flags=re.I)
        return url + ('&' if '?' in url else '?') + key + '=' + quote(value)

    @staticmethod
    def _safe_play_name(value):
        return re.sub(r'[#$]+', ' ', str(value or '')).strip()

    @staticmethod
    def _clean_html(value):
        text = re.sub(r'<br\s*/?>', '\n', str(value or ''), flags=re.I)
        text = re.sub(r'<[^>]+>', '', text)
        return re.sub(r'\n{3,}', '\n\n', html.unescape(text)).strip()

    @staticmethod
    def _image_mime(data, declared=''):
        if data.startswith(b'\xff\xd8\xff'):
            return 'image/jpeg'
        if data.startswith(b'\x89PNG'):
            return 'image/png'
        if data.startswith(b'GIF8'):
            return 'image/gif'
        if len(data) > 11 and data[:4] == b'RIFF' and data[8:12] == b'WEBP':
            return 'image/webp'
        if declared and declared.split(';', 1)[0].startswith('image/'):
            return declared.split(';', 1)[0]
        return mimetypes.guess_type('cover.jpg')[0] or 'application/octet-stream'

    @staticmethod
    def _parse_config(value):
        if isinstance(value, dict):
            return value
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

    @staticmethod
    def _unique_hosts(values):
        result = []
        for value in values or []:
            host = str(value or '').strip().rstrip('/')
            if host.startswith(('http://', 'https://')) and host not in result:
                result.append(host)
        return result

    @staticmethod
    def _category_id(item_id, item_type):
        return '%s@@%s' % (item_id, item_type)

    @staticmethod
    def _parse_category_id(value):
        parts = str(value or '').split('@@', 1)
        item_id = Spider._int(parts[0], 0)
        item_type = parts[1].strip() if len(parts) > 1 and parts[1].strip() else 'list'
        return item_id, item_type

    @staticmethod
    def _text(value):
        if value is None:
            return ''
        return re.sub(r'\s+', ' ', str(value)).strip()

    @staticmethod
    def _int(value, default=0):
        try:
            return int(value)
        except Exception:
            return default
