# -*- coding: utf-8 -*-
"""青空次元 Sorani Spider
站点: https://www.sorani.net/
播放接口需要 Origin/Referer，播放地址为短时效 HLS。
"""
import re
import json
import html as _html
try:
    import requests
except Exception:
    requests = None
try:
    from urllib.parse import urljoin, quote
    from urllib.request import Request, urlopen
except Exception:
    urljoin = lambda b, u: u
    quote = lambda x: x
    Request = urlopen = None


class _URLSession(object):
    def __init__(self):
        self.headers = {}
    def get(self, url, headers=None, timeout=15, **kwargs):
        hs = dict(self.headers)
        if headers: hs.update(headers)
        r = urlopen(Request(url, headers=hs), timeout=timeout)
        class R:
            status_code = getattr(r, 'status', 200)
            text = r.read().decode('utf-8', 'ignore')
            content = text.encode('utf-8')
            def json(self): return json.loads(self.text)
        return R()


class Spider:
    HOST = 'https://www.sorani.net'
    API = 'https://api.sorani.cc/sorani-cms'
    UA = 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/125 Mobile Safari/537.36'

    def __init__(self):
        self.s = None
        self.session = None
        self.sess = None
        self._init_session()

    def _init_session(self):
        if requests:
            self.s = requests.Session()
            self.s.headers.update({'User-Agent': self.UA, 'Accept-Language': 'zh-CN,zh;q=0.9'})
        else:
            self.s = _URLSession()
            self.s.headers.update({'User-Agent': self.UA})
        self.session = self.s
        self.sess = self.s

    def getDependence(self):
        return []

    def init(self, extend=''):
        if self.s is None:
            self._init_session()
        return None

    def destroy(self):
        try:
            self.s.close()
        except Exception:
            pass

    def manualVideoCheck(self):
        return False

    def isVideoFormat(self, url):
        return '.m3u8' in str(url).lower() or '.mp4' in str(url).lower()

    def action(self, action):
        return {}

    def _get(self, url, api=False):
        headers = {'User-Agent': self.UA, 'Accept': 'text/html,application/xhtml+xml,application/json'}
        if api:
            headers.update({'Origin': self.HOST, 'Referer': self.HOST + '/', 'Accept': 'application/json'})
        try:
            r = self.s.get(url, headers=headers, timeout=18)
            # requests 可能误判 SSR 页面编码；站点实际统一 UTF-8
            try:
                if hasattr(r, 'content') and r.content:
                    r.encoding = 'utf-8'
            except Exception:
                pass
            return r
        except Exception:
            return None

    def _page(self, url):
        r = self._get(url)
        if not r:
            return ''
        try:
            if hasattr(r, 'content') and r.content:
                return r.content.decode('utf-8', 'ignore')
        except Exception:
            pass
        return getattr(r, 'text', '') or ''

    def _js_unquote(self, value):
        try:
            return json.loads('"' + value + '"')
        except Exception:
            return value.replace('\\"', '"').replace('\\n', ' ').strip()

    def _meta(self, text, vid):
        """从 SSR 注入的 video 对象读取准确标题和封面。"""
        p = re.search(r'(?<!\d)id:' + re.escape(str(vid)) + r',title:"((?:\\.|[^"\\])*)"', text, re.S)
        title = self._js_unquote(p.group(1)) if p else ''
        # cover 字段通常位于同一对象，兼容 cover/coverThumb/coverSmall
        pic = ''
        if p:
            near = text[p.start():p.start() + 5000]
            q = re.search(r'(?:coverThumb|coverSmall|cover|coverLarge):"((?:\\.|[^"\\])*)"', near, re.S)
            if q: pic = self._js_unquote(q.group(1))
        return title.strip(), urljoin(self.HOST, pic) if pic else ''

    def _cards(self, text):
        out, seen = [], set()
        pat = re.compile(r'<a[^>]+href=["\']/anime/mal/(\d+)["\'][^>]*>(.*?)</a>', re.S | re.I)
        for m in pat.finditer(text):
            vid, block = m.group(1), m.group(2)
            if vid in seen:
                continue
            meta_title, meta_pic = self._meta(text, vid)
            clean = meta_title
            if not clean:
                clean = _html.unescape(re.sub(r'<[^>]+>', ' ', block))
                clean = re.sub(r'\s+', ' ', clean).strip()
            if not clean or clean in ('详情', '播放'):
                near = text[max(0, m.start()-1200):m.end()+400]
                vals = re.findall(r'(?:alt|title)=["\']([^"\']+)', near, re.I)
                clean = vals[-1].strip() if vals else ('动漫 ' + vid)
            pic = meta_pic or self._pic(text[max(0,m.start()-1000):m.end()+500])
            seen.add(vid)
            out.append({'vod_id': vid, 'vod_name': clean, 'vod_pic': pic, 'vod_remarks': ''})
        return out

    def _pic(self, block):
        # 详情页也可能只在 og:image 或 SSR 对象中出现封面
        xs = re.findall(r'(?:src|data-src|data-original|content)=["\']([^"\']+)', block, re.I)
        for x in xs:
            if 'video-cover' in x or 'media-thumbs' in x:
                return urljoin(self.HOST, _html.unescape(x))
        m = re.search(r'https?://[^"\' ]+(?:video-cover|media-thumbs)[^"\' ]+', block, re.I)
        return _html.unescape(m.group(0)) if m else ''

    def _api_json(self, path):
        # API 偶发 TLS EOF/限流；短重试避免影视仓翻页时偶尔空页
        for i in range(3):
            r = self._get(self.API + path, api=True)
            try:
                obj = r.json() if r else {}
                if isinstance(obj, dict) and (obj.get('success') or obj.get('code') == 200):
                    return obj
            except Exception:
                pass
        return {}

    def _fallback_pic(self, x):
        # 少数记录主封面为空，但通常仍有背景图或 OG 图
        for k in ('coverThumb', 'coverSmall', 'cover', 'coverLarge', 'coverOg', 'backgroundThumb', 'backgroundImage', 'backgroundLarge'):
            v = x.get(k)
            if v:
                return str(v)
        return ''

    def _api_records(self, data):
        rows = (data.get('data') or {}).get('records') or []
        out = []
        for x in rows:
            if not isinstance(x, dict):
                continue
            vid = str(x.get('id', ''))
            pic = self._fallback_pic(x)
            # 只有确实没有任何图片字段时才使用统一默认图，避免影视仓显示空白
            if not pic:
                pic = self.HOST + '/favicon.ico'
            out.append({'vod_id': vid, 'vod_name': str(x.get('title') or x.get('alias') or ('动漫 ' + vid)), 'vod_pic': pic, 'vod_remarks': str(x.get('latestEpisodeLabel') or x.get('statusText') or '')})
        return out

    def _filter_values(self):
        tags = '奇幻,搞笑,战斗,校园,冒险,恋爱,科幻,治愈,热血,百合,后宫,悬疑,励志,青春,轻小说,剧情,机战,竞技,萝莉,异世界,泡面番,神魔,魔法,运动,战争,女性向,日常,肉番,推理,歌舞,犯罪,社会,恐怖,职场,美少女,游戏,历史,耽美,欢乐向,血腥,吸血鬼,伪娘,惊悚'.split(',')
        years = ['2026','2025','2024','2023','2022','2021','2020','2019','2018','2017','2016','2015','2014','2013','2012','2011','2010','2009','2008','2007','2006','2005','2004','2003','2002','2001','2000','90年代','80年代','70年代','更早']
        initials = ['0-9'] + list('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
        def vals(items): return [{'n': '全部', 'v': ''}] + [{'n': x, 'v': x} for x in items]
        return {
            'tag': {'name':'类型', 'value': vals(tags)},
            'year': {'name':'年份', 'value': vals(years)},
            'initial': {'name':'字母', 'value': vals(initials)},
            'status': {'name':'状态', 'value': [{'n':'全部','v':''},{'n':'连载中','v':'0'},{'n':'已完结','v':'1'},{'n':'即将播出','v':'2'}]},
            'sort': {'name':'排序', 'value': [{'n':'最新','v':'latest'},{'n':'热门','v':'trending'},{'n':'好评','v':'rating'}]}
        }

    def homeContent(self, filter=None):
        classes = [{'type_id':'1','type_name':'TV番剧'}, {'type_id':'2','type_name':'剧场动画'}, {'type_id':'5','type_name':'特摄剧场'}]
        fs = {}
        for c in classes:
            fs[c['type_id']] = list(self._filter_values().keys())
        text = self._page(self.HOST + '/')
        return {'class': classes, 'filter': self._filter_values(), 'list': self._cards(text)[:40]}

    def homeVideoContent(self):
        return self.homeContent(None)

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        tid, pg = str(tid or '1'), str(pg or '1')
        # 兼容影视仓：筛选通常从 extend 传入，也兼容 filter 直接传 dict
        q = {'page': pg, 'size': '24', 'categoryId': tid, 'enabled': 'true', 'sortMode': 'latest', 'sortDesc': 'true'}
        opt = extend if isinstance(extend, dict) else (filter if isinstance(filter, dict) else {})
        if isinstance(opt, str):
            try: opt = json.loads(opt)
            except Exception: opt = {}
        for key in ('tag','tags','year','initial','status','sortMode','sort'):
            val = opt.get(key, '') if isinstance(opt, dict) else ''
            if isinstance(val, (list, tuple)): val = ','.join(map(str, val))
            if val not in ('', None, '全部'):
                if key == 'tag': key = 'tags'
                if key == 'sort': key = 'sortMode'
                q[key] = str(val)
        if 'sortMode' not in q: q['sortMode'] = 'latest'
        path = '/api/video?' + '&'.join(quote(str(k)) + '=' + quote(str(v)) for k,v in q.items())
        data = self._api_json(path)
        body = data.get('data') or {}
        current = int(body.get('current') or body.get('page') or (int(pg) if pg.isdigit() else 1))
        limit = int(body.get('size') or body.get('pageSize') or 24)
        total = int(body.get('total') or body.get('totalCount') or 0)
        pages = int(body.get('pages') or body.get('totalPages') or ((total + limit - 1) // limit if total else 1))
        return {'page': current, 'pagecount': pages, 'limit': limit, 'total': total, 'list': self._api_records(data)}

    def detailContent(self, ids):
        if isinstance(ids, (list, tuple)):
            vid = str(ids[0]) if ids else ''
        else:
            vid = str(ids or '')
        vid = re.search(r'\d+', vid).group(0) if re.search(r'\d+', vid) else vid
        text = self._page(self.HOST + '/anime/mal/' + vid)
        title = ''
        mt = re.search(r'<title>(.*?)</title>', text, re.S | re.I)
        if mt:
            raw_title = _html.unescape(mt.group(1))
            # 页面标题可能出现 UTF-8 被错误按 Latin-1 解码的 SSR 片段
            try:
                fixed = raw_title.encode('latin1').decode('utf-8')
                if any('一' <= c <= '鿿' for c in fixed): raw_title = fixed
            except Exception:
                pass
            title = re.sub(r'\s*-\s*青空次元.*$', '', raw_title).strip()
        if not title:
            mt = re.search(r'(?:title|name):["\']([^"\']+)', text, re.I)
            title = _html.unescape(mt.group(1)) if mt else ('动漫 ' + vid)
        pic = self._pic(text)
        eps = []
        # SSR 数据同时含 episodeId（真实播放接口 ID）和 episodeLabel；
        # href 中的 01/02 只是显示序号，不能拿来请求播放接口。
        for m in re.finditer(r'episodeId:(\d+),videoId:\d+.*?episodeLabel:["\']([^"\']+)', text, re.S | re.I):
            eid = m.group(1)
            name = re.sub(r'\s+', '', _html.unescape(m.group(2)))
            if not any(x.split('$', 1)[1] == eid for x in eps):
                eps.append(name + '$' + eid)
        if not eps:
            for i, eid in enumerate(re.findall(r'episodeId:(\d+)', text), 1):
                eps.append('第%02d集$%s' % (i, eid))
        return {'list':[{'vod_id':vid, 'vod_name':title, 'vod_pic':pic, 'vod_content':'', 'vod_play_from':'青空次元', 'vod_play_url':'#'.join(eps)}]}

    def searchContent(self, key, quick=False, pg='1'):
        # 搜索页参数在不同前端版本间有变化，依次尝试常见形式
        pg = str(pg or '1')
        for path in ['/anime/explore?keyword=%s&page=%s' % (quote(str(key)), quote(pg)), '/search?keyword=%s&page=%s' % (quote(str(key)), quote(pg))]:
            text = self._page(self.HOST + path)
            cards = self._cards(text)
            if cards: return {'page': int(pg) if pg.isdigit() else 1, 'pagecount': 9999, 'limit':24, 'total':999999, 'list':cards[:24]}
        return {'page':1, 'pagecount':1, 'limit':24, 'total':0, 'list':[]}

    def playerContent(self, flag, ids, vipFlags=None):
        eid = str(ids or '')
        if isinstance(ids, (list, tuple)): eid = str(ids[0]) if ids else ''
        m = re.search(r'\d+', eid)
        if not m: return {'parse':1, 'url':'', 'header':{}}
        eid = m.group(0)
        url = self.API + '/api/video/episode/' + eid + '/play?lineCode=anime_jp_m3u8'
        r = self._get(url, api=True)
        play = ''
        try: play = (r.json().get('data') or {}).get('playUrl') or ''
        except Exception: pass
        return {'parse':0, 'jx':0, 'url':play, 'header':{'User-Agent':self.UA, 'Referer':self.HOST + '/', 'Origin':self.HOST, 'format':'application/x-mpegURL'}}

    def localProxy(self, param):
        return [404, 'text/plain', b'', {}]

    def getName(self):
        return '青空次元'


if __name__ == '__main__':
    s = Spider(); s.init()
    print(json.dumps(s.homeContent(), ensure_ascii=False)[:1000])
    print(s.detailContent(['4631']))
    print(s.playerContent('', '64454'))
    s.destroy()
