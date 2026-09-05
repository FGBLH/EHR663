# coding=utf-8
"""
目标站: 搜剧AI (souju.ai)
模板: 影视聚合搜索 / 爬虫播放
站点类型: 综合影视
核心逻辑: HMAC-SHA256 签名 JSON API
支持: 首页, 分类(含二级筛选), 搜索, 详情(多线路), 播放
"""

import sys
import json
import time
import hmac
import hashlib
import os
import urllib.parse

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    def init(self, extend=""):
        self.site_url = "https://souju.ai"
        self.api_secret = "f39d73aa7a6426203cdee1ef17b31d3b7ea8c23f4c59c62a3a8aa0f39ee5e79d"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': self.site_url + '/',
            'Origin': self.site_url,
        }
        self.default_pic = 'https://pic.rmb.bdstatic.com/bjh/user/default.png'
        self.categories = {
            'movie': '电影',
            'series': '电视剧',
            'anime': '动漫',
            'variety': '综艺',
            'short_drama': '短剧',
        }
        self.filters = {
            'movie': [
                {'key': 'genre', 'name': '类型', 'value': [
                    {'n': '全部', 'v': ''}, {'n': '动作', 'v': '动作'}, {'n': '喜剧', 'v': '喜剧'},
                    {'n': '爱情', 'v': '爱情'}, {'n': '科幻', 'v': '科幻'}, {'n': '恐怖', 'v': '恐怖'},
                    {'n': '剧情', 'v': '剧情'}, {'n': '战争', 'v': '战争'}, {'n': '动画', 'v': '动画'},
                    {'n': '悬疑', 'v': '悬疑'}, {'n': '犯罪', 'v': '犯罪'}, {'n': '冒险', 'v': '冒险'},
                ]},
                {'key': 'region', 'name': '地区', 'value': [
                    {'n': '全部', 'v': ''}, {'n': '中国大陆', 'v': '中国大陆'}, {'n': '中国香港', 'v': '中国香港'},
                    {'n': '中国台湾', 'v': '中国台湾'}, {'n': '美国', 'v': '美国'}, {'n': '韩国', 'v': '韩国'},
                    {'n': '日本', 'v': '日本'}, {'n': '英国', 'v': '英国'}, {'n': '法国', 'v': '法国'},
                    {'n': '印度', 'v': '印度'}, {'n': '泰国', 'v': '泰国'},
                ]},
                {'key': 'year', 'name': '年份', 'value': [
                    {'n': '全部', 'v': ''}, {'n': '2026', 'v': '2026'}, {'n': '2025', 'v': '2025'},
                    {'n': '2024', 'v': '2024'}, {'n': '2023', 'v': '2023'}, {'n': '2022', 'v': '2022'},
                    {'n': '2021', 'v': '2021'}, {'n': '2020', 'v': '2020'}, {'n': '2019', 'v': '2019'},
                    {'n': '2018', 'v': '2018'}, {'n': '更早', 'v': '2010_2017'},
                ]},
                {'key': 'sort', 'name': '排序', 'value': [
                    {'n': '最新', 'v': 'newest'}, {'n': '最热', 'v': 'hottest'}, {'n': '好评', 'v': 'rating'},
                ]},
            ],
            'series': [
                {'key': 'genre', 'name': '类型', 'value': [
                    {'n': '全部', 'v': ''}, {'n': '古装', 'v': '古装'}, {'n': '都市', 'v': '都市'},
                    {'n': '悬疑', 'v': '悬疑'}, {'n': '武侠', 'v': '武侠'}, {'n': '科幻', 'v': '科幻'},
                    {'n': '战争', 'v': '战争'}, {'n': '喜剧', 'v': '喜剧'}, {'n': '爱情', 'v': '爱情'},
                    {'n': '家庭', 'v': '家庭'}, {'n': '历史', 'v': '历史'}, {'n': '谍战', 'v': '谍战'},
                ]},
                {'key': 'region', 'name': '地区', 'value': [
                    {'n': '全部', 'v': ''}, {'n': '中国大陆', 'v': '中国大陆'}, {'n': '韩国', 'v': '韩国'},
                    {'n': '美国', 'v': '美国'}, {'n': '日本', 'v': '日本'}, {'n': '中国香港', 'v': '中国香港'},
                    {'n': '中国台湾', 'v': '中国台湾'}, {'n': '英国', 'v': '英国'},
                ]},
                {'key': 'year', 'name': '年份', 'value': [
                    {'n': '全部', 'v': ''}, {'n': '2026', 'v': '2026'}, {'n': '2025', 'v': '2025'},
                    {'n': '2024', 'v': '2024'}, {'n': '2023', 'v': '2023'}, {'n': '2022', 'v': '2022'},
                    {'n': '2021', 'v': '2021'}, {'n': '2020', 'v': '2020'}, {'n': '2019', 'v': '2019'},
                ]},
                {'key': 'status', 'name': '状态', 'value': [
                    {'n': '全部', 'v': ''}, {'n': '连载', 'v': 'ongoing'}, {'n': '完结', 'v': 'completed'},
                ]},
            ],
            'anime': [
                {'key': 'genre', 'name': '类型', 'value': [
                    {'n': '全部', 'v': ''}, {'n': '热血', 'v': '热血'}, {'n': '恋爱', 'v': '恋爱'},
                    {'n': '校园', 'v': '校园'}, {'n': '奇幻', 'v': '奇幻'}, {'n': '科幻', 'v': '科幻'},
                    {'n': '搞笑', 'v': '搞笑'}, {'n': '冒险', 'v': '冒险'}, {'n': '运动', 'v': '运动'},
                ]},
                {'key': 'region', 'name': '地区', 'value': [
                    {'n': '全部', 'v': ''}, {'n': '日本', 'v': '日本'}, {'n': '中国', 'v': '中国'},
                    {'n': '欧美', 'v': '欧美'}, {'n': '韩国', 'v': '韩国'},
                ]},
                {'key': 'year', 'name': '年份', 'value': [
                    {'n': '全部', 'v': ''}, {'n': '2026', 'v': '2026'}, {'n': '2025', 'v': '2025'},
                    {'n': '2024', 'v': '2024'}, {'n': '2023', 'v': '2023'}, {'n': '2022', 'v': '2022'},
                ]},
            ],
            'variety': [
                {'key': 'region', 'name': '地区', 'value': [
                    {'n': '全部', 'v': ''}, {'n': '中国大陆', 'v': '中国大陆'}, {'n': '韩国', 'v': '韩国'},
                    {'n': '中国台湾', 'v': '中国台湾'}, {'n': '美国', 'v': '美国'}, {'n': '日本', 'v': '日本'},
                ]},
                {'key': 'year', 'name': '年份', 'value': [
                    {'n': '全部', 'v': ''}, {'n': '2026', 'v': '2026'}, {'n': '2025', 'v': '2025'},
                    {'n': '2024', 'v': '2024'}, {'n': '2023', 'v': '2023'},
                ]},
            ],
            'short_drama': [
                {'key': 'genre', 'name': '类型', 'value': [
                    {'n': '全部', 'v': ''}, {'n': '都市', 'v': '都市'}, {'n': '古装', 'v': '古装'},
                    {'n': '逆袭', 'v': '逆袭'}, {'n': '甜宠', 'v': '甜宠'}, {'n': '赘婿', 'v': '赘婿'},
                ]},
                {'key': 'year', 'name': '年份', 'value': [
                    {'n': '全部', 'v': ''}, {'n': '2026', 'v': '2026'}, {'n': '2025', 'v': '2025'}, {'n': '2024', 'v': '2024'},
                ]},
            ],
        }

    def _sign_headers(self, method, path_with_search):
        ts = str(int(time.time() * 1000))
        nonce = os.urandom(16).hex()
        msg = '{0}\n{1}\n{2}\n{3}'.format(method, path_with_search, ts, nonce)
        sig = hmac.new(self.api_secret.encode('utf-8'), msg.encode('utf-8'), hashlib.sha256).hexdigest()
        return {
            **self.headers,
            'x-ai-movie-timestamp': ts,
            'x-ai-movie-nonce': nonce,
            'x-ai-movie-signature': sig,
        }

    def _api_get(self, path):
        url = self.site_url + path
        headers = self._sign_headers('GET', path)
        try:
            resp = self.fetch(url, headers=headers)
            if not resp:
                return {}
            return json.loads(resp.text)
        except Exception:
            return {}

    def _api_post(self, path, payload):
        url = self.site_url + path
        headers = self._sign_headers('POST', path)
        headers['Content-Type'] = 'application/json'
        try:
            resp = self.fetch(url, headers=headers, data=json.dumps(payload, ensure_ascii=False))
            if not resp:
                return {}
            return json.loads(resp.text)
        except Exception:
            return {}

    def _parse_card(self, card):
        vid = card.get('id', '') or ''
        name = card.get('title', '') or ''
        pic = card.get('poster_url', '') or ''
        remark = card.get('remarks', '') or ''
        year = str(card.get('year', '')) if card.get('year') else ''
        area = card.get('area', '') or ''
        genres = card.get('genres', [])
        type_name = ' / '.join(genres[:3]) if genres else ''
        return {
            'vod_id': vid,
            'vod_name': name,
            'vod_pic': pic if pic else self.default_pic,
            'vod_remarks': remark,
            'vod_year': year,
            'vod_area': area,
            'vod_type': type_name,
        }

    def _calc_pagecount(self, pag, page, limit):
        total = pag.get('total', 0)
        if total and limit:
            return (total + limit - 1) // limit
        if pag.get('has_more'):
            return page + 1
        return page

    def _is_valid_video_url(self, url):
        if not url:
            return False
        url_lower = url.lower()
        for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp']:
            if ext in url_lower:
                return False
        return True

    def homeContent(self, filter):
        categories = [{'type_id': k, 'type_name': v} for k, v in self.categories.items()]
        data = self._api_get('/v1/feed/home')
        videos = []
        seen = set()
        for sec in data.get('sections', []):
            for card in sec.get('cards', []):
                vid = card.get('id', '')
                if not vid or vid in seen:
                    continue
                seen.add(vid)
                videos.append(self._parse_card(card))
        filters = {}
        for k, v in self.categories.items():
            if k in self.filters:
                filters[k] = self.filters[k]
        return {'class': categories, 'list': videos[:30], 'filters': filters}

    def homeVideoContent(self):
        data = self._api_get('/v1/feed/home')
        videos = []
        seen = set()
        for sec in data.get('sections', []):
            for card in sec.get('cards', []):
                vid = card.get('id', '')
                if not vid or vid in seen:
                    continue
                seen.add(vid)
                videos.append(self._parse_card(card))
        return {'list': videos[:30]}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        limit = 30
        params = ['kind={0}'.format(tid), 'page={0}'.format(page), 'limit={0}'.format(limit)]
        if extend:
            if extend.get('genre'):
                params.append('genre={0}'.format(urllib.parse.quote(extend['genre'])))
            if extend.get('region'):
                params.append('region={0}'.format(urllib.parse.quote(extend['region'])))
            if extend.get('year'):
                y = extend['year']
                if '_' in y:
                    parts = y.split('_')
                    params.append('year_from={0}&year_to={1}'.format(parts[0], parts[1]))
                else:
                    params.append('year={0}'.format(y))
            if extend.get('sort'):
                params.append('sort={0}'.format(extend['sort']))
            if extend.get('status'):
                params.append('status={0}'.format(extend['status']))
        path = '/v1/browse/catalog?' + '&'.join(params)
        data = self._api_get(path)
        cards = data.get('cards', []) or []
        videos = [self._parse_card(c) for c in cards if c.get('id')]
        pag = data.get('pagination', {}) or {}
        total = pag.get('total', 0) or len(videos)
        pagecount = self._calc_pagecount(pag, page, limit)
        return {
            'list': videos,
            'page': page,
            'pagecount': pagecount,
            'limit': limit,
            'total': total,
        }

    def searchContent(self, key, quick, pg='1'):
        page = int(pg) if pg else 1
        limit = 30
        encoded = urllib.parse.quote(key)
        path = '/v1/browse/catalog?q={0}&page={1}&limit={2}'.format(encoded, page, limit)
        data = self._api_get(path)
        cards = data.get('cards', []) or []
        videos = [self._parse_card(c) for c in cards if c.get('id')]
        pag = data.get('pagination', {}) or {}
        total = pag.get('total', 0) or len(videos)
        pagecount = self._calc_pagecount(pag, page, limit)
        return {
            'list': videos,
            'page': page,
            'pagecount': pagecount,
            'limit': limit,
            'total': total,
        }

    def detailContent(self, ids):
        if not ids:
            return {'list': []}
        vid = ids[0]
        data = self._api_get('/v1/catalog/{0}'.format(vid))
        if not data or 'id' not in data:
            return {'list': []}
        title = data.get('title', '') or ''
        pic = data.get('poster_url', '') or self.default_pic
        content = data.get('description', '') or ''
        actors = data.get('actors', [])
        actor = ' / '.join(actors[:20]) if actors else ''
        directors = data.get('directors', [])
        director = ' / '.join(directors[:10]) if directors else ''
        year = str(data.get('year', '')) if data.get('year') else ''
        area = data.get('area', '') or ''
        genres = data.get('genres', [])
        type_name = ' / '.join(genres[:5]) if genres else ''
        play_from = []
        play_url = []

        def extract_episodes(episodes, provider_id=''):
            ep_list = []
            suffix = '@@{0}'.format(provider_id) if provider_id else ''
            for ep in episodes:
                ep_title = ep.get('title', '') or ''
                if not ep_title:
                    num = ep.get('number')
                    if num is not None:
                        ep_title = '第{0}集'.format(num)
                    else:
                        ep_title = '播放'
                token = ep.get('token', '')
                if not token:
                    continue
                ep_list.append('{0}${1}{2}'.format(ep_title, token, suffix))
            return ep_list

        episodes = data.get('episodes', [])
        if not episodes:
            ep_data = self._api_get('/v1/catalog/{0}/episodes'.format(vid))
            episodes = ep_data.get('episodes', [])

        if episodes:
            first_token = ''
            for ep in episodes:
                if ep.get('token'):
                    first_token = ep.get('token')
                    break

            valid_lines = []
            if first_token:
                resolve_data = self._api_get('/v1/playback/resolve/{0}'.format(first_token))
                line_options = resolve_data.get('line_options', []) or []
                seen_providers = set()
                for opt in line_options:
                    if not opt.get('url'):
                        continue
                    pid = opt.get('provider_id')
                    if pid in seen_providers:
                        continue
                    seen_providers.add(pid)
                    valid_lines.append(opt)

                def line_rank(opt):
                    kind = opt.get('url_kind', '')
                    name = (opt.get('provider_name') or '').lower()
                    if kind == 'resolve_ticket':
                        return 2
                    if '资源' in name:
                        return 0
                    return 1

                valid_lines.sort(key=lambda x: (-line_rank(x), -x.get('preference_weight', 0)))
                valid_lines = valid_lines[:12]

            if valid_lines:
                for line in valid_lines:
                    provider_name = line.get('provider_name') or line.get('label') or '默认线路'
                    provider_id = line.get('provider_id') or ''
                    play_from.append(provider_name)
                    ep_list = extract_episodes(episodes, provider_id)
                    if ep_list:
                        play_url.append('#'.join(ep_list))

            if not play_from:
                play_from.append('默认线路')
                ep_list = extract_episodes(episodes)
                if ep_list:
                    play_url.append('#'.join(ep_list))
        else:
            play_from.append('默认线路')
            play_url.append('播放${0}/v1/catalog/{1}'.format(self.site_url, vid))

        result = [{
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': pic,
            'vod_content': content,
            'vod_actor': actor,
            'vod_director': director,
            'vod_year': year,
            'vod_area': area,
            'vod_type': type_name,
            'vod_play_from': '$$$'.join(play_from),
            'vod_play_url': '$$$'.join(play_url),
        }]
        return {'list': result}

    def playerContent(self, flag, id, vipFlags):
        raw_id = id
        if '$' in raw_id:
            raw_id = raw_id.split('$')[-1]
        raw_id = raw_id.strip()
        token = raw_id
        selected_provider = ''
        if '@@' in token:
            token, selected_provider = token.split('@@', 1)
        token = token.strip()
        if not token:
            return {'parse': 1, 'url': id, 'header': self.headers}
        if token.startswith('http') and ('.m3u8' in token or '.mp4' in token):
            return {
                'parse': 0,
                'url': token,
                'header': {
                    'User-Agent': self.headers['User-Agent'],
                    'Referer': self.site_url + '/',
                }
            }
        if not token.startswith('YJ-'):
            return {'parse': 1, 'url': token, 'header': self.headers}
        try:
            path = '/v1/playback/resolve/{0}'.format(urllib.parse.quote(token))
            resolve_data = self._api_get(path)
            line_options = resolve_data.get('line_options', [])
            if not line_options:
                return {'parse': 1, 'url': id, 'header': self.headers}
        except Exception:
            return {'parse': 1, 'url': id, 'header': self.headers}

        def is_selected(opt):
            if selected_provider and opt.get('provider_id') == selected_provider:
                return True
            if selected_provider and opt.get('play_from') == selected_provider:
                return True
            if flag and opt.get('provider_name') == flag:
                return True
            return False

        sorted_lines = sorted(
            line_options,
            key=lambda x: (not is_selected(x), -x.get('preference_weight', 0))
        )

        for line in sorted_lines:
            raw_url = line.get('url', '')
            if not raw_url:
                continue
            url_kind = line.get('url_kind', '')
            if url_kind in ['m3u8', 'mp4', 'hls'] and raw_url.startswith('http'):
                if self._is_valid_video_url(raw_url):
                    return {
                        'parse': 0,
                        'url': raw_url,
                        'header': {
                            'User-Agent': self.headers['User-Agent'],
                            'Referer': self.site_url + '/',
                        }
                    }
            if url_kind == 'resolve_ticket':
                ticket = raw_url.replace('resolve://', '')
                if not ticket:
                    continue
                payload = {
                    'ticket': ticket,
                    'line': line.get('playback_source_id', ''),
                    'provider_id': line.get('provider_id', ''),
                    'play_from': line.get('play_from', ''),
                }
                try:
                    line_data = self._api_post('/v1/playback/resolve-line', payload)
                    line_info = line_data.get('line', {})
                    real_url = line_info.get('url', '')
                except Exception:
                    continue
                if real_url and self._is_valid_video_url(real_url):
                    return {
                        'parse': 0,
                        'url': real_url,
                        'header': {
                            'User-Agent': self.headers['User-Agent'],
                            'Referer': self.site_url + '/',
                        }
                    }

        return {
            'parse': 1,
            'url': '{0}/yj/{1}'.format(self.site_url, token.replace('YJ-', '')),
            'header': self.headers
        }
