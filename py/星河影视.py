# -*- coding: utf-8 -*-
# 星河影视 xhkan.top - TVBox/PY Spider 兼容修复版
# 重点：按 TVBox Py Spider 标准方法返回；分类页无 SSR 列表时自动回退首页分区数据；保留原 /api/player/resolve 播放解析。

import sys
import re
import json
import base64
import urllib.parse

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    host = 'https://xhkan.top'
    ua = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
          '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    # xhkan 详情接口里的 cat 是数字；网页分类路径是 slug
    classes = [
        {'type_id': '1', 'type_name': '电影'},
        {'type_id': '2', 'type_name': '电视剧'},
        {'type_id': '3', 'type_name': '综艺'},
        {'type_id': '4', 'type_name': '动漫'},
        {'type_id': '6', 'type_name': '短剧'},
    ]
    slug_map = {'1': 'movie', '2': 'tv', '3': 'variety', '4': 'anime', '6': 'short-drama'}
    cat_name_map = {'1': '电影', '2': '电视剧', '3': '综艺', '4': '动漫', '6': '短剧'}
    source_names = {'qq': '腾讯', 'qiyi': '爱奇艺', 'youku': '优酷', 'mgtv': '芒果', 'bilibili': '哔哩'}
    sites = ['qq', 'qiyi', 'youku', 'mgtv', 'bilibili']
    block_words = ('预告', '片花', 'trailer', 'teaser')

    def init(self, extend=''):
        self.hosts = [self.host]
        try:
            if extend:
                ext = json.loads(extend) if isinstance(extend, str) and extend.strip().startswith('{') else extend
                site = ''
                if isinstance(ext, dict):
                    site = ext.get('site') or ext.get('host') or ''
                elif isinstance(ext, str):
                    site = ext
                if site:
                    self.hosts = [i.strip().rstrip('/') for i in site.split(',') if i.strip()]
                    self.host = self.hosts[0]
        except Exception:
            pass

    def getName(self):
        return '星河影视'

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def localProxy(self, param):
        return None

    # ============ 标准 TVBox 方法 ============
    def homeContent(self, filter):
        filters = {}
        for c in self.classes:
            filters[c['type_id']] = [
                {'key': 'sort', 'name': '排序', 'value': [
                    {'n': '最新', 'v': 'time'}, {'n': '热度', 'v': 'hits'}, {'n': '评分', 'v': 'score'}
                ]},
                {'key': 'type', 'name': '类型', 'value': [
                    {'n': '全部', 'v': ''}, {'n': '喜剧', 'v': '喜剧'}, {'n': '爱情', 'v': '爱情'},
                    {'n': '动作', 'v': '动作'}, {'n': '剧情', 'v': '剧情'}, {'n': '悬疑', 'v': '悬疑'},
                    {'n': '犯罪', 'v': '犯罪'}, {'n': '科幻', 'v': '科幻'}, {'n': '动画', 'v': '动画'},
                    {'n': '其他', 'v': '其他'}
                ]},
                {'key': 'area', 'name': '地区', 'value': [
                    {'n': '全部', 'v': ''}, {'n': '大陆', 'v': '大陆'}, {'n': '香港', 'v': '香港'},
                    {'n': '台湾', 'v': '台湾'}, {'n': '美国', 'v': '美国'}, {'n': '韩国', 'v': '韩国'},
                    {'n': '日本', 'v': '日本'}, {'n': '泰国', 'v': '泰国'}, {'n': '其他', 'v': '其他'}
                ]},
                {'key': 'year', 'name': '年份', 'value': [{'n': '全部', 'v': ''}] + [
                    {'n': str(y), 'v': str(y)} for y in range(2026, 2014, -1)
                ]}
            ]
        return {'class': self.classes, 'filters': filters}

    def homeVideoContent(self):
        html = self._get_first_text(['/'])
        return {'list': self._parse_cards(html)[:40]}

    def categoryContent(self, tid, pg, filter, extend):
        tid = str(tid or '1')
        page = int(pg or 1)
        extend = extend or {}
        slug = self.slug_map.get(tid, tid)

        # 1. 优先尝试可能的 JSON API，兼容站点后续改版
        videos = self._try_category_apis(tid, slug, page, extend)

        # 2. 再尝试网页分类路径
        if not videos:
            paths = self._build_category_paths(slug, page, extend)
            for p in paths:
                html = self._get_first_text([p])
                videos = self._parse_cards(html)
                if videos:
                    break

        # 3. 当前站分类页可能只渲染筛选栏、不直接输出列表，回退首页对应分类热播数据
        if not videos:
            html = self._get_first_text(['/'])
            all_videos = self._parse_cards(html)
            videos = [v for v in all_videos if str(v.get('vod_id', '')).split('@', 1)[0] == tid]

        return {'list': videos, 'page': page, 'pagecount': page + 1, 'limit': 30, 'total': 999999}

    def searchContent(self, key, quick, pg='1'):
        page = int(pg or 1)
        kw = str(key or '').strip()
        if not kw:
            return {'list': [], 'page': page}

        videos = []
        # 1. 兼容常见搜索 API / 搜索页参数
        paths = [
            '/api/search?keyword=%s&page=%s' % (urllib.parse.quote(kw), page),
            '/api/search?wd=%s&page=%s' % (urllib.parse.quote(kw), page),
            '/search?keyword=%s&page=%s' % (urllib.parse.quote(kw), page),
            '/search?q=%s&page=%s' % (urllib.parse.quote(kw), page),
        ]
        for p in paths:
            txt = self._get_first_text([p])
            if not txt:
                continue
            st = txt.strip()
            if st.startswith('{') or st.startswith('['):
                try:
                    videos = self._parse_json_list(json.loads(st))
                except Exception:
                    videos = []
            else:
                videos = self._parse_cards(txt)
            if videos:
                break

        # 2. 搜索 API 不可用时，至少从首页已渲染资源里本地匹配，保证壳内不空白
        if not videos:
            html = self._get_first_text(['/'])
            videos = [v for v in self._parse_cards(html) if kw.lower() in v.get('vod_name', '').lower()]

        return {'list': videos, 'page': page, 'pagecount': page + 1, 'limit': 30, 'total': 999999}

    def detailContent(self, ids):
        if not ids:
            return {'list': []}
        raw = str(ids[0])
        cat, vod_id = self._split_vid(raw)
        if not vod_id:
            return {'list': []}

        detail = None
        for site in self.sites:
            try:
                api = '/api/detail?cat=%s&id=%s&site=%s' % (cat, urllib.parse.quote(vod_id), site)
                txt = self._get_first_text([api])
                data = json.loads(txt)
                if data.get('errno') == 0 and data.get('data'):
                    detail = data.get('data')
                    break
            except Exception:
                continue

        # API 失败时，解析详情页 HTML 兜底
        if not detail:
            html = self._get_first_text(['/detail/%s/%s' % (cat, urllib.parse.quote(vod_id))])
            return {'list': [self._detail_from_html(cat, vod_id, html)]}

        title = detail.get('title') or detail.get('name') or vod_id
        if self._blocked_title(title):
            return {'list': []}

        vod = {
            'vod_id': '%s@%s' % (cat, vod_id),
            'vod_name': title,
            'vod_pic': self._abs_img(detail.get('cover') or detail.get('pic') or detail.get('poster') or ''),
            'vod_remarks': detail.get('remarks') or detail.get('status') or '',
            'vod_year': str(detail.get('year') or detail.get('pubdate') or ''),
            'vod_area': self._join(detail.get('area') or ''),
            'vod_actor': self._join(detail.get('actors') or detail.get('actor') or ''),
            'vod_director': self._join(detail.get('directors') or detail.get('director') or ''),
            'vod_content': self._clean_text(detail.get('desc') or detail.get('intro') or detail.get('description') or ''),
        }

        play_from, play_urls = [], []
        allep = detail.get('allepidetail') or {}
        if isinstance(allep, dict):
            for site, eps in allep.items():
                if not isinstance(eps, list) or not eps:
                    continue
                urls = []
                for idx, ep in enumerate(eps, 1):
                    ep_no = ep.get('playlink_num') or ep.get('episode') or idx
                    name = ep.get('title') or ('第%s集' % str(ep_no).zfill(2) if str(ep_no).isdigit() else str(ep_no))
                    raw_url = ep.get('url') or ep.get('play_url') or ''
                    if not raw_url:
                        continue
                    pid = self._enc({'cat': cat, 'vod_id': vod_id, 'source': site, 'episode': int(ep_no) if str(ep_no).isdigit() else idx, 'playUrl': raw_url})
                    urls.append('%s$%s' % (name, pid))
                if urls:
                    play_from.append(self.source_names.get(site, site))
                    play_urls.append('#'.join(urls))

        vod['vod_play_from'] = '$$$'.join(play_from)
        vod['vod_play_url'] = '$$$'.join(play_urls)
        return {'list': [vod]}

    def playerContent(self, flag, id, vipFlags):
        try:
            obj = self._dec(str(id or ''))
            if not isinstance(obj, dict):
                return {'parse': 0, 'url': str(id or ''), 'header': {'User-Agent': self.ua, 'Referer': self.host + '/'}}

            play_url = obj.get('playUrl') or ''
            payload = {
                'vodId': obj.get('vod_id') or obj.get('vodId') or 'direct',
                'source': obj.get('source') or 'qq',
                'episode': int(obj.get('episode') or 1),
                'category': int(obj.get('cat') or obj.get('category') or 2),
                'playUrl': play_url
            }
            self._get_first_text(['/api/player/token'])
            txt = self._post_first_json('/api/player/resolve', payload)
            data = json.loads(txt) if txt else {}
            url = data.get('url') if data.get('success') else ''
            return {'parse': 0, 'url': url or play_url or '', 'header': {'User-Agent': self.ua, 'Referer': self.host + '/'}}
        except Exception:
            return {'parse': 0, 'url': ''}

    # ============ 分类 / API 兜底 ============
    def _build_category_paths(self, slug, page, extend):
        params = {}
        for k in ('type', 'area', 'year', 'sort'):
            if extend.get(k):
                params[k] = extend.get(k)
        if page > 1:
            params['page'] = str(page)
        q = ('?' + urllib.parse.urlencode(params)) if params else ''
        base = '/short-drama' if slug == 'short-drama' else '/category/' + slug
        paths = [base + q]
        if page > 1:
            paths.append(base + '/page/%s' % page)
            paths.append(base + '?page=%s' % page)
        return paths

    def _try_category_apis(self, tid, slug, page, extend):
        params = {
            'cat': tid,
            'category': tid,
            'type': extend.get('type', ''),
            'area': extend.get('area', ''),
            'year': extend.get('year', ''),
            'sort': extend.get('sort', ''),
            'page': str(page),
            'limit': '30'
        }
        q1 = urllib.parse.urlencode(params)
        q2 = urllib.parse.urlencode(dict(params, cat=slug, category=slug))
        paths = [
            '/api/list?' + q1,
            '/api/vod/list?' + q1,
            '/api/category?' + q1,
            '/api/category?' + q2,
            '/api/videos?' + q1,
            '/api/search?cat=%s&page=%s' % (urllib.parse.quote(tid), page),
            '/api/search?category=%s&page=%s' % (urllib.parse.quote(slug), page),
        ]
        for p in paths:
            txt = self._get_first_text([p])
            if not txt:
                continue
            try:
                obj = json.loads(txt)
                videos = self._parse_json_list(obj)
                if videos:
                    return videos
            except Exception:
                continue
        return []

    # ============ 解析工具 ============
    def _parse_cards(self, html):
        html = html or ''
        videos, seen = [], set()
        # 适配 /detail/2/xxxx，下一版如果改成完整域名也能匹配
        pattern = re.compile(r'<a[^>]+href=["\'](?:https?://[^/]+)?/detail/(\d+)/([^"\'#?]+)[^"\']*["\'][^>]*>(.*?)</a>', re.S | re.I)
        for m in pattern.finditer(html):
            cat = m.group(1)
            vid = urllib.parse.unquote(m.group(2))
            block = m.group(3)
            title = self._extract_title(block)
            if not title or self._blocked_title(title):
                continue
            pic = self._first_match(block, r'(?:data-src|src)=["\']([^"\']+)["\']') or ''
            remark = self._first_match(block, r'(全\d+集|更新至\d+集|\d{4}-\d{2}-\d{2}期|\d+期|正片)') or ''
            vod_id = '%s@%s' % (cat, vid)
            if vod_id in seen:
                continue
            seen.add(vod_id)
            videos.append({'vod_id': vod_id, 'vod_name': title, 'vod_pic': self._abs_img(pic), 'vod_remarks': remark})
        return videos

    def _parse_json_list(self, obj):
        arr = []
        if isinstance(obj, dict):
            data = obj.get('data', obj)
            if isinstance(data, dict):
                for k in ('list', 'items', 'records', 'result', 'data'):
                    if isinstance(data.get(k), list):
                        arr = data.get(k)
                        break
            elif isinstance(data, list):
                arr = data
            if not arr:
                for k in ('list', 'items', 'records', 'result'):
                    if isinstance(obj.get(k), list):
                        arr = obj.get(k)
                        break
        elif isinstance(obj, list):
            arr = obj
        videos = []
        for it in arr or []:
            if not isinstance(it, dict):
                continue
            title = it.get('title') or it.get('name') or it.get('vod_name') or it.get('videoName') or ''
            if not title or self._blocked_title(title):
                continue
            cat = str(it.get('cat') or it.get('category') or it.get('type') or it.get('type_id') or it.get('cid') or '2')
            if cat in self.slug_map:
                pass
            else:
                # slug 转数字
                for k, v in self.slug_map.items():
                    if str(cat) == v:
                        cat = k
                        break
            vid = str(it.get('id') or it.get('vod_id') or it.get('vid') or it.get('episode_id') or '')
            if not vid:
                continue
            videos.append({
                'vod_id': '%s@%s' % (cat, vid),
                'vod_name': self._clean_text(title),
                'vod_pic': self._abs_img(it.get('cover') or it.get('pic') or it.get('poster') or it.get('vod_pic') or ''),
                'vod_remarks': it.get('remarks') or it.get('status') or it.get('vod_remarks') or ''
            })
        return videos

    def _detail_from_html(self, cat, vod_id, html):
        title = self._first_match(html, r'<h1[^>]*>(.*?)</h1>') or vod_id
        title = self._clean_text(title)
        pic = self._first_match(html, r'<img[^>]+alt=["\']%s["\'][^>]+(?:src|data-src)=["\']([^"\']+)' % re.escape(title)) or self._first_match(html, r'<img[^>]+(?:src|data-src)=["\']([^"\']+)["\']')
        content = self._first_match(html, r'###?\s*简介\s*(.*?)\s*(?:展开全部|选集|</)')
        # 播放集数从详情页 /play/cat/id/ep?s=source 提取
        eps = []
        ep_re = re.compile(r'href=["\'](?:https?://[^/]+)?/play/(\d+)/([^/"\']+)/(\d+)\?s=([^"\'&]+)[^"\']*["\'][^>]*>(.*?)</a>', re.S | re.I)
        for mm in ep_re.finditer(html or ''):
            c, vid, ep, src, name = mm.group(1), urllib.parse.unquote(mm.group(2)), mm.group(3), mm.group(4), self._clean_text(mm.group(5))
            if c != str(cat) or vid != str(vod_id):
                continue
            pid = self._enc({'cat': c, 'vod_id': vid, 'source': src, 'episode': int(ep), 'playUrl': ''})
            eps.append('%s$%s' % (name or ('第%s集' % ep), pid))
        vod = {
            'vod_id': '%s@%s' % (cat, vod_id),
            'vod_name': title,
            'vod_pic': self._abs_img(pic),
            'vod_content': self._clean_text(content),
            'vod_play_from': '星河',
            'vod_play_url': '#'.join(eps)
        }
        return vod

    def _extract_title(self, block):
        title = self._first_match(block, r'alt=["\']([^"\']+)["\']') or self._first_match(block, r'title=["\']([^"\']+)["\']')
        if title:
            return self._clean_text(title)
        text = self._clean_text(block)
        # 首页卡片常见顺序：简介 + 状态 + 类型 + 标题，取最后一个较短片段
        parts = re.split(r'(?:全\d+集|更新至\d+集|\d{4}-\d{2}-\d{2}期|\d+期|正片|其他|剧情|喜剧|爱情|动作|悬疑|犯罪|动画|原创|都市|网剧|少儿)', text)
        cand = parts[-1].strip() if parts else text
        if not cand or len(cand) > 40:
            cand = text[-40:].strip()
        return cand

    def _blocked_title(self, title):
        t = (title or '').lower()
        return any(w.lower() in t for w in self.block_words)

    def _split_vid(self, raw):
        raw = str(raw)
        if '@' in raw:
            return raw.split('@', 1)
        m = re.search(r'/detail/(\d+)/([^/?#]+)', raw)
        if m:
            return m.group(1), urllib.parse.unquote(m.group(2))
        return '2', raw

    def _headers(self):
        return {
            'User-Agent': self.ua,
            'Accept': 'application/json,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Referer': self.host + '/',
        }

    def _get_first_text(self, paths, timeout=20):
        for base in getattr(self, 'hosts', [self.host]):
            base = base.rstrip('/')
            for p in paths:
                url = p if str(p).startswith('http') else base + (p if str(p).startswith('/') else '/' + str(p))
                try:
                    r = self.fetch(url, headers=self._headers(), timeout=timeout, verify=False)
                    if hasattr(r, 'text'):
                        txt = r.text
                    else:
                        content = getattr(r, 'content', b'')
                        txt = content.decode('utf-8', 'ignore') if isinstance(content, bytes) else str(content)
                    if txt:
                        return txt
                except Exception:
                    continue
        return ''

    def _post_first_json(self, path, payload, timeout=20):
        for base in getattr(self, 'hosts', [self.host]):
            url = base.rstrip('/') + path
            try:
                r = self.fetch(url, headers={**self._headers(), 'Content-Type': 'application/json'}, data=json.dumps(payload).encode('utf-8'), method='POST', timeout=timeout, verify=False)
                if hasattr(r, 'text'):
                    return r.text
                content = getattr(r, 'content', b'')
                return content.decode('utf-8', 'ignore') if isinstance(content, bytes) else str(content)
            except Exception:
                continue
        return ''

    def _enc(self, obj):
        return base64.urlsafe_b64encode(json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).decode('utf-8').rstrip('=')

    def _dec(self, s):
        try:
            return json.loads(base64.urlsafe_b64decode((s + '=' * (-len(s) % 4)).encode()).decode('utf-8'))
        except Exception:
            return s

    def _abs_img(self, url):
        url = str(url or '').strip()
        if not url:
            return ''
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('/'):
            return self.host.rstrip('/') + url
        return url

    def _clean_text(self, text):
        text = re.sub(r'<script[\s\S]*?</script>|<style[\s\S]*?</style>', ' ', str(text or ''), flags=re.I)
        text = re.sub(r'<[^>]+>', ' ', text)
        for a, b in {'&nbsp;': ' ', '&amp;': '&', '&quot;': '"', '&#39;': "'", '&lt;': '<', '&gt;': '>'}.items():
            text = text.replace(a, b)
        return re.sub(r'\s+', ' ', text).strip()

    def _first_match(self, text, pattern):
        m = re.search(pattern, text or '', re.S | re.I)
        return self._clean_text(m.group(1)) if m else ''

    def _join(self, v):
        if isinstance(v, list):
            return '/'.join([str(x.get('name') if isinstance(x, dict) else x) for x in v])
        return str(v or '')
