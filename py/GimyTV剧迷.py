# coding: utf-8
"""Gimy TV 劇迷 drpy source."""
import re
from urllib.parse import quote, urljoin
from base.spider import Spider


class Spider(Spider):
    host = 'https://gimyai.tw'

    def init(self, extend=''):
        self.host = 'https://gimyai.tw'

    def _text(self, resp):
        if hasattr(resp, 'text'):
            return resp.text or ''
        if isinstance(resp, bytes):
            return resp.decode('utf-8', 'ignore')
        return str(resp or '')

    def _get(self, url):
        try:
            return self._text(self.fetch(url, headers={'User-Agent': 'Mozilla/5.0'}))
        except Exception:
            return ''

    def _attr(self, tag, name):
        m = re.search(r'\b%s=["\']([^"\']+)' % name, tag, re.I)
        return m.group(1) if m else ''

    def _cards(self, html):
        out = []
        for m in re.finditer(r'<a\s+class=["\']poster["\'][^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.S | re.I):
            href, body = m.group(1), m.group(2)
            title = re.search(r'class=["\']poster__title["\'][^>]*>(.*?)</', body, re.S | re.I)
            meta = re.search(r'class=["\']poster__meta["\'][^>]*>(.*?)</', body, re.S | re.I)
            img = re.search(r'<img[^>]+(?:src|data-src)=["\']([^"\']+)', body, re.I)
            status = re.search(r'class=["\']poster__status["\'][^>]*>(.*?)</', body, re.S | re.I)
            clean = lambda x: re.sub(r'<[^>]+>', '', x or '').strip()
            out.append({'vod_id': urljoin(self.host, href), 'vod_name': clean(title.group(1) if title else ''),
                        'vod_pic': urljoin(self.host, img.group(1) if img else ''),
                        'vod_remarks': clean(status.group(1) if status else ''),
                        'vod_actor': clean(meta.group(1) if meta else '')})
        return out

    def homeContent(self, filter):
        classes = [{'type_id': '2', 'type_name': '電視劇'}, {'type_id': '4', 'type_name': '動漫'},
                   {'type_id': '29', 'type_name': '綜藝'}, {'type_id': '13', 'type_name': '陸劇'},
                   {'type_id': '20', 'type_name': '韓劇'}, {'type_id': '15', 'type_name': '日劇'},
                   {'type_id': '14', 'type_name': '台劇'}, {'type_id': '21', 'type_name': '港劇'},
                   {'type_id': '34', 'type_name': '短劇'}, {'type_id': '38', 'type_name': 'AI漫劇'},
                   {'type_id': '31', 'type_name': '海外劇'}, {'type_id': '22', 'type_name': '紀錄片'}]
        filters = [{
            'key': 'area', 'name': '地區', 'value': [
                {'n': '全部', 'v': ''}, {'n': '中國大陸', 'v': '中國大陸'}, {'n': '韓國', 'v': '韓國'},
                {'n': '日本', 'v': '日本'}, {'n': '台灣', 'v': '台灣'}, {'n': '香港', 'v': '香港'},
                {'n': '美國', 'v': '美國'}, {'n': '歐美', 'v': '歐美'}, {'n': '泰國', 'v': '泰國'}]},
            {'key': 'year', 'name': '年份', 'value': [{'n': '全部', 'v': ''}] + [{'n': str(y), 'v': str(y)} for y in range(2026, 2015, -1)]},
            {'key': 'sort', 'name': '排序', 'value': [
                {'n': '最近更新', 'v': 'time'}, {'n': '最新上架', 'v': 'time_add'},
                {'n': '本週人氣', 'v': 'hits_week'}, {'n': '總人氣', 'v': 'hits'}]}]
        return {'class': classes, 'filters': {'2': filters, '4': filters, '29': filters, '13': filters, '20': filters, '15': filters, '14': filters, '21': filters, '34': filters, '38': filters, '31': filters, '22': filters}, 'list': []}

    def homeVideoContent(self):
        return {'list': self._cards(self._get(self.host + '/genre/2.html'))[:12]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        f = filter if isinstance(filter, dict) else {}
        if not f and isinstance(extend, dict):
            f = extend
        area = str(f.get('area', '') or '')
        year = str(f.get('year', '') or '')
        sort = str(f.get('sort', '') or '')
        # 站点真实格式：筛选字段占位，页码是最后一段。
        # 例如 /explore/2-日本--time----2.html
        parts = [''] * 6
        if area:
            parts[0] = quote(area)
        if sort:
            parts[1] = sort
        if year:
            parts[5] = year
        if not area and not year and not sort and pg <= 1:
            url = self.host + '/genre/%s.html' % tid
        elif area:
            # 例如：/explore/2-日本----------2.html
            suffix = '----------%d' % pg if pg > 1 else '----------'
            url = self.host + '/explore/%s-%s%s.html' % (tid, quote(area), suffix)
        elif sort:
            # 例如：/explore/2--time---------2.html
            suffix = '---------%d' % pg if pg > 1 else '---------'
            url = self.host + '/explore/%s--%s%s.html' % (tid, sort, suffix)
        elif year:
            url = self.host + '/explore/%s-----------%s.html' % (tid, year)
        elif pg <= 1:
            url = self.host + '/explore/%s-----------.html' % tid
        else:
            # 无筛选分页的真实形式：/explore/2--------2---.html
            url = self.host + '/explore/%s--------%d---.html' % (tid, pg)
        html = self._get(url)
        items = self._cards(html)
        # 列表页真实分页链接采用 --2---.html 形式，不能靠伪造 pagecount。
        nums = [int(x) for x in re.findall(r'--------(?:\d+)---(\d+)\.html', html)]
        pagecount = max([1, pg] + nums) if items else max(1, pg - 1)
        return {'list': items, 'page': pg, 'pagecount': pagecount,
                'limit': len(items), 'total': len(items) * pagecount}

    def searchContent(self, key, quick, pg='1'):
        pg = int(pg or 1)
        url = self.host + '/find/-------------.html?wd=' + quote(key)
        if pg > 1:
            url += '&page=%d' % pg
        html = self._get(url)
        items = self._cards(html)
        # 搜索页无可靠总页数时，按空页结束，不伪造大页数。
        return {'list': items, 'page': pg, 'pagecount': pg if items else max(1, pg - 1),
                'limit': len(items), 'total': len(items) if not items else len(items) * pg}

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) else ids
        if str(vid).startswith('http'):
            url = vid
        else:
            url = self.host + '/detail/%s.html' % vid
        html = self._get(url)
        clean = lambda x: re.sub(r'<[^>]+>', '', x or '').strip()
        title = re.search(r'class=["\']detail__title["\'][^>]*>(.*?)</', html, re.S | re.I)
        pic = re.search(r"class=[\"']detail__poster[\"'][\\s\\S]*?<img[^>]+src=[\"']([^\"']+)", html, re.I)
        actors = re.search(r'主演：\s*(.*?)</div>', html, re.S | re.I)
        director = re.search(r'導演：\s*(.*?)</div>', html, re.S | re.I)
        area = re.search(r'地區：\s*([^<]+)', html, re.I)
        year = re.search(r'類別：.*?</a>\s*[·.]\s*(\d{4})', html, re.S | re.I)
        route_names = {'3': '優酷線路', '9': '藍光線路', '16': '4K畫質線路', '4': '高清線路'}
        routes = {}
        route_pat = r'<div[^>]+class=["\']route-title["\'][^>]*>(.*?)</div>\s*<div[^>]+data-route-sid=["\'](\d+)["\'][^>]*>(.*?)</div>'
        for route_title, sid, block in re.findall(route_pat, html, re.S | re.I):
            route_title = re.sub(r'<[^>]+>', '', route_title).replace('ᴴᴰ', '').strip()
            name = route_title or route_names.get(sid, '線路%s' % sid)
            eps = re.findall(r'href=["\']([^"\']*/play/[^"\']+)["\'][^>]*>(.*?)</a>', block, re.S | re.I)
            if eps:
                routes[name] = '#'.join('%s$%s' % (clean(e), urljoin(self.host, h)) for h, e in eps)
        vod = {'vod_id': str(vid), 'vod_name': clean(title.group(1) if title else ''),
               'vod_pic': urljoin(self.host, pic.group(1)) if pic else '', 'vod_actor': clean(actors.group(1) if actors else ''),
               'vod_director': clean(director.group(1) if director else ''), 'vod_area': clean(area.group(1) if area else ''),
               'vod_year': year.group(1) if year else '', 'vod_content': '',
               'vod_play_from': '$$$'.join(routes.keys()), 'vod_play_url': '$$$'.join(routes.values())}
        return {'list': [vod]}

    def playerContent(self, flag, id, vipFlags):
        url = id if str(id).startswith('http') else urljoin(self.host, str(id))
        html = self._get(url)
        # 先解析站点公开的 player_data，不能用宽泛 url: 正则吃掉整段 JSON。
        m = re.search(r'player_data\s*=\s*(\{.*?\})\s*</script>', html, re.S | re.I)
        media = ''
        if m:
            raw = m.group(1)
            um = re.search(r'"url"\s*:\s*"(https?:\\?/\\/[^"\\]+)"', raw, re.I)
            if um:
                media = um.group(1).replace('\\/', '/')
        if not media:
            m = re.search(r'https?:\\?/\\/[^"\' ]+\.(?:m3u8|mp4)(?:[^"\' ]*)?', html, re.I)
            media = m.group(0).replace('\\/', '/') if m else ''
        if media.startswith('//'):
            media = 'https:' + media
        # 保留来源页和站点协议，避免壳端把完整播放数据丢掉。
        if media:
            return {'parse': 0, 'jx': 0, 'playUrl': '', 'url': media,
                    'header': {'User-Agent': 'Mozilla/5.0', 'Referer': url}}
        return {'parse': 1, 'jx': 1, 'playUrl': '', 'url': url,
                'header': {'User-Agent': 'Mozilla/5.0', 'Referer': url}}
