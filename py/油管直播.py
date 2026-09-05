#coding=utf-8
#!/usr/bin/python
import re
import sys
import json
import html
import time
from urllib.parse import quote, unquote, urljoin

import requests
from base.spider import Spider

sys.path.append('..')

DEBUG_LOG = '/sdcard/Download/ytblive_debug.log'

LIVE_CLASSES = [
    {'type_id': 'live', 'type_name': '正在直播'},
    {'type_id': 'news live', 'type_name': '新闻直播'},
    {'type_id': 'music live', 'type_name': '音乐直播'},
    {'type_id': 'lofi live', 'type_name': 'Lofi直播'},
    {'type_id': 'space live', 'type_name': '太空直播'},
    {'type_id': 'nature live', 'type_name': '自然直播'},
    {'type_id': 'game live', 'type_name': '游戏直播'},
    {'type_id': 'sports live', 'type_name': '体育直播'},
]


def debug_log(message, data=None):
    try:
        line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}"
        if data is not None:
            if isinstance(data, (dict, list)):
                line += ' ' + json.dumps(data, ensure_ascii=False, default=str)
            else:
                line += ' ' + str(data)
        with open(DEBUG_LOG, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass


class YouTubeLiveLite:
    def __init__(self, session, headers=None, config=None):
        self.session = session
        self.headers = headers or {}
        self.config = config or {}
        self.cache = {}
        self.cache_ttl = int(self.config.get('live_cache_ttl') or 45)

    @staticmethod
    def extract_video_id(text):
        text = str(text or '').strip()
        for pattern in [
            r'(?:v=|/v/|/embed/|/shorts/|youtu\.be/)([0-9A-Za-z_-]{11})',
            r'^([0-9A-Za-z_-]{11})$',
        ]:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        raise Exception('无法识别 YouTube 视频 ID')

    def extract_live(self, url_or_id):
        video_id = self.extract_video_id(url_or_id)
        now = time.time()
        cached = self.cache.get(video_id)
        if cached and cached.get('expires', 0) > now:
            debug_log('live cache hit', {'video_id': video_id, 'ttl': int(cached.get('expires', 0) - now)})
            return cached.get('data')

        watch_url = f'https://www.youtube.com/watch?v={video_id}'
        debug_log('live extract start', {'input': url_or_id, 'video_id': video_id})
        response = self._get(watch_url)
        page = response.text
        player_response = self._extract_initial_player_response(page) or {}
        ytcfg = self._extract_ytcfg(page) or {}
        api_key = ytcfg.get('INNERTUBE_API_KEY') or self._search(r'"INNERTUBE_API_KEY":"([^"]+)"', page)
        visitor_data = self._extract_visitor_data(ytcfg, player_response)
        status_obj = player_response.get('playabilityStatus') or {}
        streaming = player_response.get('streamingData') or {}
        details = player_response.get('videoDetails') or {}

        debug_log('live page parsed', {
            'status': status_obj.get('status'),
            'reason': status_obj.get('reason'),
            'is_live': details.get('isLiveContent'),
            'has_hls': bool(streaming.get('hlsManifestUrl')),
            'has_api_key': bool(api_key),
            'has_visitor': bool(visitor_data),
        })

        page_hls_url = streaming.get('hlsManifestUrl') or ''
        hls_source = 'page' if page_hls_url else ''
        api_data = None
        if api_key:
            api_data = self._call_player_api(video_id, api_key, ytcfg, watch_url, visitor_data)
            if api_data:
                api_streaming = api_data.get('streamingData') or {}
                api_details = api_data.get('videoDetails') or {}
                api_hls_url = api_streaming.get('hlsManifestUrl') or ''
                if api_hls_url:
                    streaming = api_streaming
                    hls_source = api_data.get('_client_name') or 'api'
                elif not page_hls_url and api_streaming:
                    streaming = api_streaming
                    hls_source = api_data.get('_client_name') or 'api_no_hls'
                if api_details:
                    details = api_details
                status_obj = api_data.get('playabilityStatus') or status_obj
        if not (streaming.get('hlsManifestUrl') or '') and page_hls_url:
            streaming = dict(streaming or {})
            streaming['hlsManifestUrl'] = page_hls_url
            hls_source = 'page_fallback'

        hls_url = streaming.get('hlsManifestUrl') or ''
        is_live = bool(details.get('isLiveContent') or hls_url)
        status = status_obj.get('status') or ''
        reason = status_obj.get('reason') or ''
        title = details.get('title') or video_id

        data = {
            'id': video_id,
            'title': title,
            'is_live': is_live,
            'status': status,
            'reason': reason,
            'hls_url': hls_url,
            'duration': int(details.get('lengthSeconds') or 0),
        }
        debug_log('live extract result', {
            'video_id': video_id,
            'status': status,
            'is_live': is_live,
            'has_hls': bool(hls_url),
            'hls_source': hls_source,
            'duration': data.get('duration'),
        })
        self.cache[video_id] = {'data': data, 'expires': time.time() + self.cache_ttl}
        return data

    def _get(self, url, **kwargs):
        headers = self.headers.copy()
        headers.update(kwargs.pop('headers', {}) or {})
        response = self.session.get(url, headers=headers, timeout=kwargs.pop('timeout', 15), **kwargs)
        response.raise_for_status()
        return response

    def _post_json(self, url, payload, headers=None):
        final_headers = self.headers.copy()
        final_headers.update({'Content-Type': 'application/json', 'Origin': 'https://www.youtube.com'})
        if headers:
            final_headers.update({k: v for k, v in headers.items() if v})
        response = self.session.post(url, json=payload, headers=final_headers, timeout=15)
        response.raise_for_status()
        return response.json()

    def _call_player_api(self, video_id, api_key, ytcfg, referer, visitor_data=None):
        context = ytcfg.get('INNERTUBE_CONTEXT') or {
            'client': {'clientName': 'WEB', 'clientVersion': '2.20240310.01.00', 'hl': 'en', 'gl': 'US'}
        }
        clients = [
            {'client': {'clientName': 'ANDROID', 'clientVersion': '21.02.35', 'androidSdkVersion': 30, 'userAgent': 'com.google.android.youtube/21.02.35 (Linux; U; Android 11) gzip', 'osName': 'Android', 'osVersion': '11', 'hl': 'en', 'gl': 'US'}},
            {'client': {'clientName': 'IOS', 'clientVersion': '21.02.3', 'deviceMake': 'Apple', 'deviceModel': 'iPhone16,2', 'userAgent': 'com.google.ios.youtube/21.02.3 (iPhone16,2; U; CPU iOS 18_3_2 like Mac OS X;)', 'osName': 'iPhone', 'osVersion': '18.3.2.22D82', 'hl': 'en', 'gl': 'US'}},
            {'client': {'clientName': 'MWEB', 'clientVersion': '2.20260115.01.00', 'userAgent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1', 'hl': 'en', 'gl': 'US'}},
            context,
        ]
        for ctx in clients:
            client = ctx.get('client') or {}
            client_name = client.get('clientName') or 'WEB'
            try:
                url = f'https://www.youtube.com/youtubei/v1/player?key={quote(api_key)}&prettyPrint=false'
                headers = {
                    'Referer': referer,
                    'X-YouTube-Client-Name': str(self._client_name_id(client_name)),
                    'X-YouTube-Client-Version': client.get('clientVersion') or '',
                }
                if visitor_data:
                    headers['X-Goog-Visitor-Id'] = visitor_data
                if client.get('userAgent'):
                    headers['User-Agent'] = client.get('userAgent')
                payload = {
                    'context': ctx,
                    'videoId': video_id,
                    'contentCheckOk': True,
                    'racyCheckOk': True,
                }
                data = self._post_json(url, payload, headers=headers)
                streaming = data.get('streamingData') or {}
                status = (data.get('playabilityStatus') or {}).get('status')
                debug_log('live api client', {
                    'client': client_name,
                    'status': status,
                    'has_hls': bool(streaming.get('hlsManifestUrl')),
                    'has_streaming': bool(streaming),
                })
                if streaming.get('hlsManifestUrl'):
                    data['_client_name'] = client_name
                    return data
            except Exception as e:
                debug_log('live api client error', {'client': client_name, 'error': repr(e)})
        return None

    def _extract_visitor_data(self, ytcfg, player_response):
        return (
            self.config.get('visitor_data')
            or ytcfg.get('VISITOR_DATA')
            or (((ytcfg.get('INNERTUBE_CONTEXT') or {}).get('client') or {}).get('visitorData'))
            or ((player_response.get('responseContext') or {}).get('visitorData'))
        )

    def _extract_ytcfg(self, text):
        match = re.search(r'ytcfg\.set\s*\(\s*({.+?})\s*\)\s*;', text or '', re.S)
        if not match:
            return None
        try:
            return json.loads(match.group(1))
        except Exception:
            return None

    def _extract_initial_player_response(self, text):
        return self._extract_json_after(text, 'ytInitialPlayerResponse')

    def _extract_json_after(self, text, marker):
        pos = (text or '').find(marker)
        if pos < 0:
            return None
        start = text.find('{', pos)
        if start < 0:
            return None
        depth = 0
        in_str = None
        escape = False
        for index in range(start, len(text)):
            char = text[index]
            if escape:
                escape = False
                continue
            if char == '\\':
                escape = True
                continue
            if in_str:
                if char == in_str:
                    in_str = None
                continue
            if char in ('"', "'"):
                in_str = char
                continue
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:index + 1])
                    except Exception:
                        return None
        return None

    @staticmethod
    def _search(pattern, text, default=None):
        match = re.search(pattern, text or '', re.S)
        return match.group(1) if match else default

    def _client_name_id(self, client_name):
        return {
            'WEB': 1,
            'MWEB': 2,
            'ANDROID': 3,
            'IOS': 5,
            'TVHTML5': 7,
            'ANDROID_VR': 28,
            'WEB_EMBEDDED_PLAYER': 56,
            'WEB_REMIX': 67,
        }.get(client_name, 1)


class Spider(Spider):
    def getName(self):
        return 'YouTube直播'

    def init(self, extend):
        try:
            self.extendDict = json.loads(extend) if extend else {}
        except Exception:
            self.extendDict = {}
        self.session = requests.Session()
        self.proxy_str = None
        proxy_val = self.extendDict.get('proxy')
        if proxy_val:
            if isinstance(proxy_val, dict):
                self.session.proxies = proxy_val
                self.proxy_str = (proxy_val.get('http') or proxy_val.get('https') or '').replace('http://', '').replace('https://', '')
            elif isinstance(proxy_val, str):
                self.proxy_str = proxy_val.replace('http://', '').replace('https://', '')
                proxy_url = f'http://{self.proxy_str}'
                self.session.proxies = {'http': proxy_url, 'https': proxy_url}
        self.header = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://www.youtube.com/'
        }
        self.session.headers.update(self.header)
        self.yt = YouTubeLiveLite(self.session, self.header, self.extendDict)
        self.search_page_cache = {}
        self.hls_url_cache = {}
        self.hls_proxy_enabled = self.extendDict.get('hls_proxy', True) is not False
        debug_log('spider init', {'has_proxy': bool(self.proxy_str or self.session.proxies), 'hls_proxy': self.hls_proxy_enabled})

    def homeContent(self, filter):
        return {'class': LIVE_CLASSES}

    def homeVideoContent(self):
        return {'list': []}

    def categoryContent(self, cid, page, filter, ext):
        page = int(page or 1)
        keyword = self._build_live_keyword(cid, ext if isinstance(ext, dict) else {})
        videos, has_more = self._search_youtube_page(keyword, page)
        return {'list': videos, 'page': page, 'pagecount': page + 1 if has_more else page, 'limit': len(videos), 'total': len(videos)}

    def searchContent(self, key, quick, pg=1):
        page = int(pg or 1)
        keyword = str(key or '').strip()
        if 'live' not in keyword.lower() and '直播' not in keyword:
            keyword = f'{keyword} live'
        videos, has_more = self._search_youtube_page(keyword, page)
        return {'list': videos, 'page': page, 'pagecount': page + 1 if has_more else page, 'limit': len(videos), 'total': len(videos)}

    def detailContent(self, did):
        video_id = did[0]
        title = self._get_video_title(video_id)
        status = '直播'
        try:
            data = self.yt.extract_live(video_id)
            title = data.get('title') or title
            if data.get('hls_url'):
                status = '直播中'
            elif data.get('status') == 'LIVE_STREAM_OFFLINE':
                status = data.get('reason') or '未开播'
            elif data.get('status') and data.get('status') != 'OK':
                status = data.get('reason') or data.get('status')
            else:
                status = '无HLS'
            debug_log('detail live status', {'video_id': video_id, 'status': status, 'has_hls': bool(data.get('hls_url'))})
        except Exception as e:
            debug_log('detail live error', {'video_id': video_id, 'error': repr(e)})
        safe_title = self._safe_title(title)
        vod = {
            'vod_id': video_id,
            'vod_name': title,
            'vod_pic': f'https://img.youtube.com/vi/{video_id}/hqdefault.jpg',
            'vod_remarks': status,
            'vod_play_from': '直播',
            'vod_play_url': f'{safe_title}${video_id}@live'
        }
        return {'list': [vod]}

    def playerContent(self, flag, pid, vipFlags):
        raw_pid = pid.split('$')[-1]
        video_id = raw_pid.rsplit('@', 1)[0] if '@' in raw_pid else raw_pid
        debug_log('player live', {'flag': flag, 'pid': pid, 'video_id': video_id})
        try:
            data = self.yt.extract_live(video_id)
            hls_url = data.get('hls_url') or ''
            if not hls_url:
                status = data.get('status') or 'NO_HLS'
                reason = data.get('reason') or '未获取到直播 HLS 地址'
                debug_log('player live no hls', {'video_id': video_id, 'status': status, 'reason': reason})
                raise Exception(reason)
            if self.extendDict.get('hls_probe'):
                self._probe_hls(video_id, hls_url)
            play_url = hls_url
            if self.hls_proxy_enabled:
                play_url = self._cache_hls_url(hls_url, video_id, 'master')
            debug_log('return live hls', {'video_id': video_id, 'url_len': len(hls_url), 'status': data.get('status'), 'proxy': self.hls_proxy_enabled})
            return {
                'parse': 0,
                'jx': 0,
                'url': play_url,
                'header': self.header,
                'format': 'application/x-mpegURL'
            }
        except Exception as e:
            debug_log('player live error', {'video_id': video_id, 'error': repr(e)})
            return {'parse': 1, 'jx': 1, 'url': pid}

    def _probe_hls(self, video_id, hls_url):
        try:
            response = self.session.get(hls_url, headers=self.header, timeout=10)
            full_text = response.text or ''
            text = full_text[:5000]
            lines = [line.strip() for line in full_text.splitlines() if line.strip()][:12]
            variant_url = self._pick_variant_playlist(hls_url, full_text)
            debug_log('hls master probe', {
                'video_id': video_id,
                'status': response.status_code,
                'content_type': response.headers.get('content-type'),
                'length': len(response.text or ''),
                'has_extm3u': text.startswith('#EXTM3U'),
                'has_stream_inf': '#EXT-X-STREAM-INF' in text,
                'has_media_sequence': '#EXT-X-MEDIA-SEQUENCE' in text,
                'variant': bool(variant_url),
                'sample': lines,
            })
            if variant_url:
                child = self.session.get(variant_url, headers=self.header, timeout=10)
                child_text = child.text[:5000] if child.text else ''
                child_lines = [line.strip() for line in child_text.splitlines() if line.strip()][:12]
                debug_log('hls variant probe', {
                    'video_id': video_id,
                    'status': child.status_code,
                    'content_type': child.headers.get('content-type'),
                    'length': len(child.text or ''),
                    'has_extm3u': child_text.startswith('#EXTM3U'),
                    'has_media_sequence': '#EXT-X-MEDIA-SEQUENCE' in child_text,
                    'has_segments': bool(re.search(r'^[^#].+', child_text, re.M)),
                    'sample': child_lines,
                })
        except Exception as e:
            debug_log('hls probe error', {'video_id': video_id, 'error': repr(e)})

    def _pick_variant_playlist(self, base_url, text):
        lines = [line.strip() for line in (text or '').splitlines()]
        best_score = -1
        best_url = ''
        for index, line in enumerate(lines):
            if not line.startswith('#EXT-X-STREAM-INF'):
                continue
            score = 0
            bandwidth = re.search(r'BANDWIDTH=(\d+)', line)
            resolution = re.search(r'RESOLUTION=(\d+)x(\d+)', line)
            if bandwidth:
                score += int(bandwidth.group(1))
            if resolution:
                score += int(resolution.group(1)) * int(resolution.group(2))
            for next_line in lines[index + 1:]:
                if not next_line or next_line.startswith('#'):
                    continue
                if score > best_score:
                    best_score = score
                    best_url = urljoin(base_url, next_line)
                break
        return best_url

    # 不同类型缓存的存活时间：master/playlist 会被播放器长期反复复用（直播刷新同一
    # 播放列表 URL），需要长 TTL；media 分段一次性消费，用短 TTL 即可。
    HLS_TTL = {'master': 6 * 3600, 'playlist': 6 * 3600, 'media': 120, 'media_retry': 120}

    def _hls_ttl(self, kind):
        return self.HLS_TTL.get(kind, 180)

    def _prune_hls_cache(self):
        # 清理过期项，避免长时间直播时 media key 无限膨胀导致内存泄漏。
        now = time.time()
        expired = [k for k, v in self.hls_url_cache.items() if v.get('expires', 0) < now]
        for k in expired:
            self.hls_url_cache.pop(k, None)

    def _cache_hls_url(self, target_url, video_id='', kind='media'):
        self._prune_hls_cache()
        # 用单调递增计数器而非 len(dict) 生成后缀，避免清理后长度回落造成 key 碰撞。
        self._hls_key_seq = getattr(self, '_hls_key_seq', 0) + 1
        key = f'{int(time.time() * 1000)}_{self._hls_key_seq}'
        self.hls_url_cache[key] = {
            'url': target_url,
            'video_id': video_id,
            'kind': kind,
            'expires': time.time() + self._hls_ttl(kind),
        }
        return f'http://127.0.0.1:9978/proxy?do=py&type=hls&key={quote(key)}'

    def localProxy(self, params):
        if params.get('do') != 'py' or params.get('type') != 'hls':
            return None
        key = params.get('key') or ''
        item = self.hls_url_cache.get(key)
        if not item or item.get('expires', 0) < time.time():
            debug_log('hls proxy missing', {'key': key})
            return [404, 'text/plain', 'HLS 缓存已过期']
        # 访问续期：只要播放器还在反复刷新该 URL（尤其是 master/playlist），
        # 就保持其存活，避免固定 TTL 到期后直播中途 404 卡顿。
        item['expires'] = time.time() + self._hls_ttl(item.get('kind'))
        target_url = item.get('url') or ''
        try:
            headers = self._hls_headers(target_url, item.get('kind'))
            response = self.session.get(target_url, headers=headers, stream=True, timeout=15)
            retried = False
            if item.get('kind') == 'media' and response.status_code == 403:
                retry_headers = self._hls_headers(target_url, 'media_retry')
                response.close()
                retried = True
                response = self.session.get(target_url, headers=retry_headers, stream=True, timeout=15)
            content_type = response.headers.get('content-type') or ''
            is_m3u8 = item.get('kind') in ('master', 'playlist') or 'mpegurl' in content_type.lower() or target_url.split('?')[0].endswith('.m3u8')
            debug_log('hls proxy response', {
                'key': key,
                'kind': item.get('kind'),
                'status': response.status_code,
                'content_type': content_type,
                'is_m3u8': is_m3u8,
                'url_len': len(target_url),
                'path_tail': target_url.split('?')[0][-80:],
                'retried': retried,
            })
            if is_m3u8:
                text = response.text
                rewritten = self._rewrite_m3u8(text, target_url, item.get('video_id') or '')
                return [response.status_code, 'application/vnd.apple.mpegurl', rewritten, {'Content-Type': 'application/vnd.apple.mpegurl', 'Cache-Control': 'no-cache'}]
            resp_headers = {'Content-Type': content_type or 'application/octet-stream', 'Cache-Control': 'no-cache'}
            if response.headers.get('content-length'):
                resp_headers['Content-Length'] = response.headers.get('content-length')
            return [response.status_code, content_type or 'application/octet-stream', response.content, resp_headers]
        except Exception as e:
            debug_log('hls proxy error', {'key': key, 'error': repr(e)})
            return [500, 'text/plain', f'HLS 代理失败: {str(e)}']

    def _hls_headers(self, target_url, kind=None):
        if kind == 'media_retry':
            return {
                'User-Agent': 'com.google.android.youtube/21.02.35 (Linux; U; Android 11) gzip',
                'Accept': '*/*',
            }
        headers = self.header.copy()
        headers['Accept'] = '*/*'
        if kind in ('master', 'playlist'):
            headers['Origin'] = 'https://www.youtube.com'
            headers['Referer'] = 'https://www.youtube.com/'
        elif kind == 'media':
            headers['User-Agent'] = 'com.google.android.youtube/21.02.35 (Linux; U; Android 11) gzip'
            headers.pop('Origin', None)
            headers.pop('Referer', None)
        return headers

    def _rewrite_m3u8(self, text, base_url, video_id=''):
        output = []
        for line in (text or '').splitlines():
            stripped = line.strip()
            if not stripped:
                output.append(line)
                continue
            if stripped.startswith('#'):
                output.append(self._rewrite_m3u8_tag(line, base_url, video_id))
                continue
            absolute = urljoin(base_url, stripped)
            kind = 'playlist' if stripped.endswith('.m3u8') or '/hls_playlist/' in stripped else 'media'
            output.append(self._cache_hls_url(absolute, video_id, kind))
        return '\n'.join(output) + '\n'

    def _rewrite_m3u8_tag(self, line, base_url, video_id=''):
        def replace_uri(match):
            raw_url = match.group(1)
            absolute = urljoin(base_url, raw_url)
            proxied = self._cache_hls_url(absolute, video_id, 'media')
            return f'URI="{proxied}"'
        return re.sub(r'URI="([^"]+)"', replace_uri, line)

    def _build_live_keyword(self, cid, filters=None):
        raw = str(cid or '').strip()
        terms = [raw if raw else 'live']
        if isinstance(filters, dict):
            for value in filters.values():
                term = self._normalize_filter_term(value)
                if term:
                    terms.append(term)
        keyword = ' '.join([x for x in terms if x]).strip()
        if 'live' not in keyword.lower() and '直播' not in keyword:
            keyword = f'{keyword} live'
        return keyword

    def _normalize_filter_term(self, value):
        if isinstance(value, (list, tuple)):
            return ' '.join([self._normalize_filter_term(item) for item in value if item])
        if isinstance(value, dict):
            return ' '.join([self._normalize_filter_term(item) for item in value.values() if item])
        return re.sub(r'\s+', ' ', str(value or '')).strip()[:180]

    def _search_cache_key(self, key):
        return re.sub(r'\s+', ' ', str(key or '')).strip().lower()

    def _search_youtube_page(self, key, page=1):
        page = max(1, int(page or 1))
        cache_key = self._search_cache_key(key)
        session = self.search_page_cache.get(cache_key)
        if page == 1 or not session:
            session = self._fetch_search_first_page(key)
            self.search_page_cache[cache_key] = session
        while len(session.get('pages', [])) < page and session.get('next'):
            data = self._fetch_search_continuation(session)
            videos = self._extract_videos_from_api(data, 30)
            session.setdefault('pages', []).append(videos)
            session['next'] = self._extract_continuation_token(data)
        pages = session.get('pages', [])
        videos = pages[page - 1] if len(pages) >= page else []
        has_more = bool(session.get('next')) or len(pages) > page
        debug_log('search page', {'key': key, 'page': page, 'count': len(videos), 'has_more': has_more})
        return videos, has_more

    def _fetch_search_first_page(self, key):
        search_url = f'https://www.youtube.com/results?search_query={quote(str(key or ""))}&sp=EgJAAQ%253D%253D'
        response = self.session.get(search_url, timeout=10)
        html_str = response.text
        data = self.yt._extract_json_after(html_str, 'ytInitialData') or {}
        ytcfg = self.yt._extract_ytcfg(html_str) or {}
        api_key = ytcfg.get('INNERTUBE_API_KEY') or self.yt._search(r'"INNERTUBE_API_KEY":"([^"]+)"', html_str)
        context = ytcfg.get('INNERTUBE_CONTEXT') or {'client': {'clientName': 'WEB', 'clientVersion': '2.20240310.01.00', 'hl': 'zh-CN', 'gl': 'US'}}
        client = context.get('client') or {}
        return {
            'key': key,
            'api_key': api_key,
            'context': context,
            'client_name': client.get('clientName') or 'WEB',
            'client_version': client.get('clientVersion') or '2.20240310.01.00',
            'referer': search_url,
            'pages': [self._extract_videos_from_api(data, 30)],
            'next': self._extract_continuation_token(data),
        }

    def _fetch_search_continuation(self, session):
        token = session.get('next')
        api_key = session.get('api_key')
        if not token or not api_key:
            return {}
        url = f'https://www.youtube.com/youtubei/v1/search?key={quote(api_key)}'
        headers = self.header.copy()
        headers.update({
            'Content-Type': 'application/json',
            'Origin': 'https://www.youtube.com',
            'Referer': session.get('referer') or 'https://www.youtube.com/',
            'X-YouTube-Client-Name': str(self.yt._client_name_id(session.get('client_name'))),
            'X-YouTube-Client-Version': session.get('client_version') or '2.20240310.01.00',
        })
        payload = {'context': session.get('context') or {}, 'continuation': token}
        response = self.session.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()

    def _extract_continuation_token(self, data):
        tokens = []
        def scan(obj):
            if isinstance(obj, dict):
                endpoint = obj.get('continuationEndpoint') or {}
                token = endpoint.get('continuationCommand', {}).get('token')
                if token:
                    tokens.append(token)
                renderer = obj.get('continuationItemRenderer') or {}
                token = renderer.get('continuationEndpoint', {}).get('continuationCommand', {}).get('token')
                if token:
                    tokens.append(token)
                for value in obj.values():
                    scan(value)
            elif isinstance(obj, list):
                for value in obj:
                    scan(value)
        scan(data)
        return tokens[0] if tokens else ''

    def _extract_videos_from_api(self, data, limit=30):
        videos = []
        seen = set()
        def scan(obj):
            if len(videos) >= limit:
                return
            if isinstance(obj, dict):
                for key in ('videoRenderer', 'compactVideoRenderer', 'gridVideoRenderer'):
                    if key in obj:
                        item = self._parse_renderer(obj[key])
                        if item and item['vod_id'] not in seen:
                            seen.add(item['vod_id'])
                            videos.append(item)
                for value in obj.values():
                    scan(value)
            elif isinstance(obj, list):
                for value in obj:
                    scan(value)
        scan(data)
        return videos[:limit]

    def _parse_renderer(self, renderer):
        try:
            video_id = renderer.get('videoId')
            if not video_id:
                nav = renderer.get('navigationEndpoint') or {}
                video_id = (nav.get('watchEndpoint') or {}).get('videoId')
            if not video_id:
                return None
            title_obj = renderer.get('title') or renderer.get('headline') or {}
            title = title_obj.get('simpleText') or ''.join([x.get('text', '') for x in title_obj.get('runs', [])]) or 'YouTube Live'
            badges = json.dumps(renderer.get('badges') or renderer.get('ownerBadges') or [], ensure_ascii=False)
            overlays = json.dumps(renderer.get('thumbnailOverlays') or [], ensure_ascii=False)
            view_text = self._text_from_obj(renderer.get('viewCountText'))
            metadata = ' '.join([badges, overlays, view_text]).lower()
            is_live = 'live' in metadata or '直播' in metadata or 'watching' in view_text.lower()
            remarks = '直播' if is_live else (self._text_from_obj(renderer.get('lengthText')) or 'Live')
            return {
                'vod_id': video_id,
                'vod_name': html.unescape(title),
                'vod_pic': f'https://img.youtube.com/vi/{video_id}/hqdefault.jpg',
                'vod_remarks': remarks,
            }
        except Exception as e:
            debug_log('parse renderer error', repr(e))
            return None

    def _text_from_obj(self, obj):
        if not obj:
            return ''
        if isinstance(obj, str):
            return obj
        if isinstance(obj, dict):
            return obj.get('simpleText') or ''.join([x.get('text', '') for x in obj.get('runs', [])])
        return ''

    def _get_video_title(self, video_id):
        try:
            response = self.session.get(f'https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json', timeout=5)
            return response.json().get('title') or video_id
        except Exception:
            return video_id

    def _safe_title(self, title):
        if not title:
            return 'live'
        return re.sub(r'[#$@%&!?*|\\/:<>]', ' ', title)[:60]
