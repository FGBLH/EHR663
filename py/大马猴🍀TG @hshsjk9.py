# -*- coding: utf-8 -*-
# 大马猴影视 - x-client播放线路修复版
# 适配绿豆 TVBox / OK影视
# 分类接口: /api.php/web/filter/vod?type_id=23/22/24/25&page=1&sort=hits
# 详情接口: /api.php/web/vod/get_detail?vod_id=xxx
# 聚合线路: /api.php/web/internal/search_aggregate?vod_id=xxx  优先提取 m3u8 直链

import sys
sys.path.append('..')

import json
import re
from urllib.parse import urlencode, quote
from html.parser import HTMLParser
from base.spider import Spider


class _HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._text = []

    def handle_data(self, data):
        self._text.append(data)

    def get_text(self):
        return ''.join(self._text)


class Spider(Spider):
    def __init__(self):
        self.host = 'https://dmhyy.com'
        # 大马猴真实分类 ID 来自网页 /type/xx 和 XHR 返回：
        # /type/23 电影，/type/22 剧集，/type/24 动漫，/type/25 综艺
        self.classes = [
            {'type_id': '23', 'type_name': '电影'},
            {'type_id': '22', 'type_name': '剧集'},
            {'type_id': '24', 'type_name': '动漫'},
            {'type_id': '25', 'type_name': '综艺'},
        ]
        self.web_sign = ''

    def init(self, extend=''):
        try:
            if extend:
                if isinstance(extend, dict):
                    ext = extend
                else:
                    text = str(extend).strip()
                    ext = json.loads(text) if text.startswith('{') else {'site': text}
                site = ext.get('site') or ext.get('host') or ''
                if site:
                    self.host = str(site).split(',')[0].strip().rstrip('/')
                self.web_sign = ext.get('web-sign') or ext.get('web_sign') or self.web_sign
        except Exception:
            pass
        return None

    def _ensure_ready(self):
        if not getattr(self, 'host', ''):
            self.host = 'https://dmhyy.com'
        self.host = self.host.rstrip('/')

    def getName(self):
        return '大马猴影视'

    def destroy(self):
        pass

    def isVideoFormat(self, url):
        # 选集字符串中经常是 .m3u8#下一集，不能只判断 ? 或结尾。
        return bool(re.search(r'\.(m3u8|mp4|flv|mkv|avi)(\?|#|$|\s)', str(url or ''), re.I))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None

    def _headers(self, referer=''):
        self._ensure_ready()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': referer or (self.host + '/'),
            'x-platform': 'web',
            'x-requested-with': 'XMLHttpRequest',
        }
        # 云朵站需要 web-sign；大马猴当前播放页 XHR 不需要。若 ext 显式提供则带上。
        if getattr(self, 'web_sign', ''):
            headers['web-sign'] = self.web_sign
        return headers

    def _api_get(self, path, params=None, referer=''):
        self._ensure_ready()
        params = params or {}
        qs = urlencode(params, doseq=True)
        url = self.host + path + (('?' + qs) if qs else '')
        try:
            r = self.fetch(url, headers=self._headers(referer), timeout=12)
            text = getattr(r, 'text', '') or getattr(r, 'content', b'')
            if isinstance(text, bytes):
                text = text.decode('utf-8', errors='ignore')
            if not text:
                return {}
            return json.loads(text)
        except Exception:
            return {}

    def _clean_text(self, s):
        s = str(s or '')
        s = re.sub(r'<[^>]+>', ' ', s)
        s = s.replace('&nbsp;', ' ')
        return re.sub(r'\s+', ' ', s).strip()

    def _html2text(self, html):
        try:
            p = _HTMLTextExtractor()
            p.feed(str(html or ''))
            return self._clean_text(p.get_text())
        except Exception:
            return self._clean_text(html)

    def _as_list(self, data):
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for k in ('data', 'list', 'items', 'records', 'rows', 'vod_list'):
                v = data.get(k)
                if isinstance(v, list):
                    return v
                if isinstance(v, dict):
                    vv = self._as_list(v)
                    if vv:
                        return vv
        return []

    def _vod_item(self, item):
        if not isinstance(item, dict):
            return None
        vid = item.get('vod_id') or item.get('id') or item.get('vodId')
        name = item.get('vod_name') or item.get('name') or item.get('title')
        if not vid or not name:
            return None
        area = item.get('vod_area', '')
        cls = item.get('vod_class', '')
        if isinstance(area, list):
            area = ','.join([str(x) for x in area if x])
        if isinstance(cls, list):
            cls = ','.join([str(x) for x in cls if x])
        return {
            'vod_id': str(vid),
            'vod_name': self._clean_text(name),
            'vod_pic': str(item.get('vod_pic') or item.get('pic') or item.get('cover') or ''),
            'vod_remarks': str(item.get('vod_remarks') or item.get('remarks') or item.get('vod_douban_score') or item.get('vod_year') or ''),
            'vod_year': str(item.get('vod_year') or ''),
            'type_name': self._clean_text(item.get('type_name') or cls or ''),
            'vod_area': self._clean_text(area),
        }

    def _vod_list(self, data):
        arr = self._as_list(data)
        out = []
        seen = set()
        for item in arr:
            v = self._vod_item(item)
            if not v:
                continue
            if v['vod_id'] in seen:
                continue
            seen.add(v['vod_id'])
            out.append(v)
        return out


    def _category_match(self, item, real_tid):
        """大马猴的接口即使传 type_id=22，也会混入电影/动漫/综艺。
        所以必须在脚本内按真实 type_id/type_name 再过滤一次，避免所有分类显示相同内容。
        """
        if not isinstance(item, dict):
            return False
        real_tid = str(real_tid)
        item_tid = str(item.get('type_id') or item.get('typeId') or item.get('tid') or '')
        if item_tid == real_tid:
            return True
        name = str(item.get('type_name') or '')
        class_value = item.get('vod_class') or []
        if isinstance(class_value, list):
            cls = ','.join([str(x) for x in class_value if x])
        else:
            cls = str(class_value or '')
        text = name + ',' + cls
        if real_tid == '23':
            return ('电影' in text or '动作片' in text or '剧情片' in text or '喜剧片' in text) and '电视剧' not in text
        if real_tid == '22':
            return any(k in text for k in ('剧集', '电视剧', '国产剧', '连续剧', '韩剧', '陆剧', '欧美剧', '日剧'))
        if real_tid == '24':
            return '动漫' in text or '动画' in text or '国产动漫' in text or '日韩动漫' in text
        if real_tid == '25':
            return '综艺' in text or '真人秀' in text
        return True

    def _filter_items_by_category(self, data, real_tid):
        arr = self._as_list(data)
        return [x for x in arr if self._category_match(x, real_tid)]

    def homeContent(self, filter):
        return {'class': self.classes, 'filters': {}}

    def homeVideoContent(self):
        # 用电影热门做首页推荐。
        j = self._api_get('/api.php/web/filter/vod', {
            'type_id': '23',
            'page': '1',
            'sort': 'hits'
        }, self.host + '/type/23')
        return {'list': self._vod_list(j)}

    def categoryContent(self, tid, pg, filter, extend):
        self._ensure_ready()
        page = str(pg or '1')
        sort = 'hits'
        if isinstance(extend, dict):
            sort = extend.get('sort') or extend.get('by') or sort

        # 真实 XHR 分类接口。注意大马猴不是 1/2/3/4，而是 23/22/24/25。
        # 这里保留一个兼容映射，防止旧配置或壳缓存还传入 1/2/3/4。
        tid_map = {'1': '23', '2': '22', '3': '24', '4': '25'}
        real_tid = tid_map.get(str(tid), str(tid))
        # 大马猴接口会混入其它分类，必须本地二次过滤。
        j = self._api_get('/api.php/web/filter/vod', {
            'type_id': real_tid,
            'page': page,
            'sort': sort
        }, self.host + '/type/' + real_tid)

        filtered_items = self._filter_items_by_category(j, real_tid)

        # 如果当前页过滤后太少，补抓后面 2 页同分类资源，避免分类页空白。
        try:
            cur_page = int(page)
        except Exception:
            cur_page = 1
        if len(filtered_items) < 8:
            seen_ids = set(str(x.get('vod_id') or x.get('id') or '') for x in filtered_items if isinstance(x, dict))
            for extra_page in range(cur_page + 1, cur_page + 3):
                jj = self._api_get('/api.php/web/filter/vod', {
                    'type_id': real_tid,
                    'page': str(extra_page),
                    'sort': sort
                }, self.host + '/type/' + real_tid)
                for item in self._filter_items_by_category(jj, real_tid):
                    vid = str(item.get('vod_id') or item.get('id') or '')
                    if vid and vid not in seen_ids:
                        seen_ids.add(vid)
                        filtered_items.append(item)
                if len(filtered_items) >= 24:
                    break

        videos = self._vod_list(filtered_items)
        pagecount = 1
        total = len(videos)
        limit = 24
        if isinstance(j, dict):
            pagecount = int(j.get('pageCount') or j.get('pagecount') or (cur_page + 1 if videos else cur_page))
            total = int(j.get('total') or total)
            limit = int(j.get('limit') or limit)

        return {
            'list': videos,
            'page': cur_page,
            'pagecount': pagecount,
            'limit': limit,
            'total': total
        }

    def searchContent(self, key, quick, pg='1'):
        self._ensure_ready()
        wd = str(key or '').strip()
        page = str(pg or '1')
        if not wd:
            return {'list': [], 'page': int(page)}

        # 真实网页搜索接口（其余候选接口均 404/无效）
        paths = [
            ('/api.php/web/search/index', {'wd': wd, 'page': page}),
        ]
        for path, params in paths:
            j = self._api_get(path, params, self.host + '/search?keyword=' + quote(wd))
            videos = self._vod_list(j)
            if videos:
                return {'list': videos, 'page': int(page)}
        return {'list': [], 'page': int(page)}

    def _first_detail(self, ids):
        vid = str(ids[0] if isinstance(ids, list) else ids)
        j = self._api_get('/api.php/web/vod/get_detail', {'vod_id': vid}, self.host + '/play/' + vid)
        arr = self._as_list(j)
        return (arr[0] if arr else {}), j

    def _aggregate_sources(self, vid):
        # 真实播放页会请求这个聚合接口，里面有很多站外直链 m3u8。必须使用 /play/vid referer 和 x-client。
        paths = [
            '/api.php/web/internal/search_aggregate',
            '/api.php/web/search_aggregate',
        ]
        for path in paths:
            j = self._api_get(path, {'vod_id': str(vid)}, self.host + '/play/' + str(vid))
            arr = self._as_list(j)
            if arr:
                return arr
        return []

    def _line_rank(self, src):
        name = str(src.get('site_name') or src.get('external_display_name') or src.get('vod_play_from') or '').lower()
        from_code = str(src.get('vod_play_from') or src.get('external_play_from') or '').lower()
        url = str(src.get('vod_play_url') or '')
        # 只要线路里已经是 m3u8/mp4，就按直链线路优先；decode_status 不再作为过滤条件。
        if re.search(r'\.(m3u8|mp4|flv)(\?|#|$|\s)', url, re.I):
            if '暴风' in name or 'bfzy' in from_code:
                return 1
            if '爱坤' in name or 'ikm3u8' in from_code:
                return 2
            if '极速' in name or 'jsm3u8' in from_code:
                return 3
            if '如意' in name or 'rym3u8' in from_code:
                return 4
            if '量子' in name or 'lzm3u8' in from_code:
                return 5
            return 10
        if int(src.get('decode_status') or 0) == 0:
            return 50
        return 99

    def _build_sources(self, vid, detail):
        sources = []
        seen = set()

        def add_source(name, play_url):
            name = self._clean_text(name or '')
            play_url = str(play_url or '').strip()
            if not name or not play_url:
                return
            key = name + '|' + play_url[:80]
            if key in seen:
                return
            seen.add(key)
            sources.append((name, play_url))

        # 1. 优先用真实聚合接口，它返回的是可直接播放的 m3u8 线路。
        #    这类线路比 get_detail 里的 JD/腾讯编码线路更适合 TVBox。
        agg = self._aggregate_sources(vid)
        if agg:
            agg = sorted(agg, key=self._line_rank)
            for src in agg:
                play_url = str(src.get('vod_play_url') or '').strip()
                if not play_url:
                    continue
                # 只优先加入直链线路，避免详情页无播放器或线路过多卡死。
                if not re.search(r'\.(m3u8|mp4|flv)(\?|#|$|\s)', play_url, re.I):
                    continue
                line_name = (
                    src.get('site_name')
                    or src.get('external_display_name')
                    or src.get('external_play_from')
                    or src.get('vod_play_from')
                    or '线路'
                )
                add_source(line_name, play_url)
                if len(sources) >= 4:
                    break

        # 2. 兜底：从 get_detail 里只提取含 m3u8/mp4 的线路，过滤 JD/QQ 这类需二次解析的超长线路。
        pf = str(detail.get('vod_play_from') or '')
        pu = str(detail.get('vod_play_url') or '')
        if pf and pu and len(sources) < 2:
            froms = pf.split('$$$')
            urls = pu.split('$$$')
            for idx, f in enumerate(froms):
                u = urls[idx] if idx < len(urls) else ''
                if not f or not u:
                    continue
                if not re.search(r'\.(m3u8|mp4|flv)(\?|#|$|\s)', u, re.I):
                    continue
                add_source(f, u)
                if len(sources) >= 4:
                    break

        # 3. 最后兜底：如果完全没有直链，再少量加入解析线路。
        if not sources and pf and pu:
            froms = pf.split('$$$')
            urls = pu.split('$$$')
            for idx, f in enumerate(froms[:3]):
                u = urls[idx] if idx < len(urls) else ''
                add_source(f, u)

        return sources

    def detailContent(self, ids):
        self._ensure_ready()
        if not ids:
            return {'list': []}
        vid = str(ids[0])
        detail, raw = self._first_detail([vid])

        if not detail:
            agg = self._aggregate_sources(vid)
            if agg:
                detail = agg[0]
            else:
                return {'list': []}

        area = detail.get('vod_area', '')
        cls = detail.get('vod_class', '')
        if isinstance(area, list):
            area = ','.join([str(x) for x in area if x])
        if isinstance(cls, list):
            cls = ','.join([str(x) for x in cls if x])

        sources = self._build_sources(vid, detail)
        vod = {
            'vod_id': vid,
            'vod_name': self._clean_text(detail.get('vod_name') or ''),
            'vod_pic': str(detail.get('vod_pic') or ''),
            'vod_remarks': str(detail.get('vod_remarks') or ''),
            'type_name': self._clean_text(detail.get('type_name') or cls or ''),
            'vod_year': str(detail.get('vod_year') or ''),
            'vod_area': self._clean_text(area),
            'vod_actor': self._clean_text(detail.get('vod_actor') or ''),
            'vod_director': self._clean_text(detail.get('vod_director') or ''),
            'vod_content': self._html2text(detail.get('vod_content') or ''),
            'vod_play_from': '$$$'.join([x[0] for x in sources]),
            'vod_play_url': '$$$'.join([x[1] for x in sources]),
        }
        return {'list': [vod]}

    def playerContent(self, flag, id, vipFlags):
        self._ensure_ready()
        url = str(id or '').strip()
        if not url:
            return {'parse': 0, 'url': ''}

        # 直链直接播放
        if url.startswith('http') and self.isVideoFormat(url):
            return {
                'parse': 0,
                'jx': 0,
                'url': url,
                'header': {
                    'User-Agent': 'Mozilla/5.0',
                    'Referer': self.host + '/'
                }
            }

        # 官方站外编码线路尝试用 decode 接口解析
        decode_candidates = [
            ('/api.php/web/decode/url', {'url': url}),
            ('/api.php/web/decode/url', {'play_url': url}),
            ('/api.php/web/decode/url', {'vod_url': url}),
        ]
        for path, params in decode_candidates:
            j = self._api_get(path, params, self.host + '/play')
            data = j.get('data') if isinstance(j, dict) else None
            final_url = ''
            headers = {}
            if isinstance(data, str):
                final_url = data
            elif isinstance(data, dict):
                final_url = data.get('url') or data.get('play_url') or data.get('playUrl') or data.get('video') or ''
                headers = data.get('header') or data.get('headers') or {}
            elif isinstance(j, dict):
                final_url = j.get('url') or j.get('play_url') or ''
                headers = j.get('header') or j.get('headers') or {}

            if final_url:
                return {
                    'parse': 0 if self.isVideoFormat(final_url) else 1,
                    'jx': 0 if self.isVideoFormat(final_url) else 1,
                    'url': final_url,
                    'header': headers or {'User-Agent': 'Mozilla/5.0', 'Referer': self.host + '/'}
                }

        # 腾讯/优酷/爱奇艺等网页地址交给壳解析
        if re.search(r'(v\.qq\.com|youku\.com|iqiyi\.com|mgtv\.com|bilibili\.com)', url, re.I):
            return {'parse': 1, 'jx': 1, 'url': url}

        # 其它未知地址也交给壳解析
        return {'parse': 1, 'jx': 1, 'url': url}
