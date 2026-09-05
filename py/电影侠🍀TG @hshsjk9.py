# -*- coding: utf-8 -*-
import sys
import os
import re
import json
import time
import hmac
import hashlib
import threading
import unicodedata
import urllib.parse
import requests

sys.path.append('..')
try:
    from base.spider import Spider
except ImportError:
    class Spider:
        def fetch(self, url, headers=None, **kw):
            t = kw.pop('timeout', 20)
            r = requests.get(url, headers=headers, timeout=t, verify=False, **kw)
            r.encoding = 'utf-8'
            return r

_CAT_CACHE = {}
_SESS = None
_CAT_FILE = '/sdcard/Download/电影侠_cat.json'
_SPLIT_FILE = '/sdcard/Download/电影侠_split.json'
_SPLIT_CACHE = None
_SPLIT_BUILDING = False
_VC = 'https://vcache.mjrlin.cn'
_VC_KEY = b'ayt5wy5afwmwrpb19k9s3psx3dymyd0n'
_VC_IV = b'b3t069ijy7pirw0j'
_VC_HASH = 'te@9fs#5tbf8#dx7zw8nx'
_VC_UA = 'com.kkdyC1V260805.T180309/3.5.0 Dalvik/2.1.0 (Linux; U; Android 11; KB2000 Build/RP1A.201005.001)'


def _cat_load():
    try:
        if os.path.exists(_CAT_FILE):
            return json.load(open(_CAT_FILE, encoding='utf-8'))
    except Exception:
        pass
    return {}


def _cat_save(d):
    try:
        json.dump(d, open(_CAT_FILE, 'w', encoding='utf-8'))
    except Exception:
        pass


class Spider(Spider):
    host = 'https://www.dyx00.com'
    pic_cdn = 'https://vres.cyscyy.com'
    ua = 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'
    skip = ('搜索', '百度', '搜狗', '神马', '360', 'baidu', 'google', 'sogou', 'kuaishou', '快手')
    wm = ('kkys', 'kekys', '可可影视')
    classes = [
        {'type_name': '今日更新', 'type_id': 'new'},
        {'type_name': '电影', 'type_id': '1'},
        {'type_name': '连续剧', 'type_id': '2'},
        {'type_name': '动漫', 'type_id': '3'},
        {'type_name': '综艺纪录', 'type_id': '4'},
        {'type_name': '短剧', 'type_id': '6'},
    ]
    filters = {}

    def init(self, extend=''):
        self._token = ''
        self._token_t = 0
        self._cat_cache = {}

    def _get(self, u, timeout=6):
        global _SESS
        h = {'User-Agent': self.ua, 'Referer': self.host + '/'}
        if _SESS is None:
            _SESS = requests.Session()
        try:
            r = _SESS.get(u, headers=h, timeout=timeout, verify=False)
            r.encoding = 'utf-8'
            return r.text
        except Exception:
            return ''

    def _clean(self, s):
        return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', unicodedata.normalize('NFKC', s or ''))).strip()

    def _is_wm(self, s):
        t = (s or '').lower()
        return any(w in t for w in self.wm)

    def _pic(self, p):
        if not p or 'logo_placeholder' in p:
            return ''
        return p if p.startswith('http') else self.pic_cdn + p

    def _parse_items(self, html):
        out, seen = [], set()
        for m in re.finditer(r'<a[^>]*href="(/detail/(\d+)\.html)"[^>]*class="v-item"[^>]*>(.*?)</a>', html, re.S):
            vid, inner = m.group(2), m.group(3)
            if vid in seen:
                continue
            title = remark = ''
            for t in re.findall(r'class="v-item-title[^"]*"[^>]*>(.*?)</div>', inner, re.S):
                c = self._clean(t)
                if c and not self._is_wm(c):
                    title = c
                    break
            rb = re.search(r'class="v-item-bottom"[^>]*>(.*?)</div>', inner, re.S)
            if rb:
                remark = self._clean(rb.group(1))
            pic = ''
            for im in re.findall(r'data-original="([^"]+\.(?:jpg|png|webp|jpeg)[^"]*)"', inner):
                pic = self._pic(im)
                if pic:
                    break
            if title and pic:
                seen.add(vid)
                out.append({'vod_id': vid, 'vod_name': title, 'vod_pic': pic, 'vod_remarks': remark})
        return out

    def getName(self):
        return '电影侠'

    def isVideoFormat(self, u):
        return any(x in u for x in ('.m3u8', '.mp4', '.flv'))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def homeContent(self, filter=False):
        return {'class': self.classes, 'filters': self.filters, 'list': []}

    def homeVideoContent(self):
        html = self._get(self.host + '/')
        return {'list': self._parse_items(html) if html else []}

    def _api_detail(self, vid):
        try:
            from Crypto.Cipher import AES
            from Crypto.Util.Padding import unpad
        except Exception:
            return ''
        try:
            path = '/v2/vod/detail.capi'
            params = {'vodId': str(vid), 'os': 'android', 'appId': 'kkdy', 'userLevel': '0'}
            ts = int(time.time() * 1000)
            data = '&'.join('%s=%s' % (k, params[k]) for k in sorted(params))
            ss = 'get|%s|%s|%d|appId=kkdy&deviceCreatedAt=1785930051138&deviceId=d2c2f3345d9b2b12|' % (path, data, ts)
            sign = hmac.new(_VC_HASH.encode(), ss.encode(), hashlib.sha1).hexdigest()
            h = {'User-Agent': _VC_UA, 'appId': 'kkdy', 'os': 'android', 'appVersion': '3.5.0', 'package': 'com.kkdyC1V260805.T180309', 'deviceId': 'd2c2f3345d9b2b12', 'deviceCreatedAt': '1785930051138', 'channelId': 'c1', 'ts': str(ts), 'sign': sign}
            global _SESS
            if _SESS is None:
                _SESS = requests.Session()
            r = _SESS.get(_VC + path, params=params, headers=h, timeout=8, verify=False)
            if r.headers.get('Encrypted') == '1':
                j = json.loads(unpad(AES.new(_VC_KEY, AES.MODE_CBC, _VC_IV).decrypt(r.content), 16))
                d = j.get('data') or {}
                return str(d.get('channelId') or '')
        except Exception:
            pass
        return ''

    def _build_split(self):
        import concurrent.futures as cf
        items = {}
        pgs = list(range(1, 31))
        def gp(pg):
            h = self._get('%s/new/%d.html' % (self.host, pg), timeout=15)
            return pg, self._parse_items(h) if h else []
        with cf.ThreadPoolExecutor(10) as ex:
            for pg, lst in ex.map(gp, pgs):
                if not lst:
                    break
                for it in lst:
                    items[it['vod_id']] = it
        buckets = {'1': [], '2': [], '3': [], '4': [], '6': []}
        ids = list(items)
        def one(v):
            return v, self._api_detail(v)
        with cf.ThreadPoolExecutor(12) as ex:
            for v, ch in ex.map(one, ids):
                if ch in buckets:
                    buckets[ch].append(items[v])
        return buckets

    def _get_split(self):
        global _SPLIT_CACHE, _SPLIT_BUILDING
        now = time.time()
        if _SPLIT_CACHE and now - _SPLIT_CACHE.get('t', 0) < 86400:
            return _SPLIT_CACHE['b']
        try:
            if os.path.exists(_SPLIT_FILE):
                d = json.load(open(_SPLIT_FILE, encoding='utf-8'))
                if d.get('t', 0) and now - d['t'] < 86400:
                    _SPLIT_CACHE = d
                    return d['b']
        except Exception:
            pass
        if not _SPLIT_BUILDING:
            _SPLIT_BUILDING = True
            def _bg():
                global _SPLIT_CACHE, _SPLIT_BUILDING
                try:
                    b = self._build_split()
                    d = {'t': time.time(), 'b': b}
                    _SPLIT_CACHE = d
                    try:
                        json.dump(d, open(_SPLIT_FILE, 'w', encoding='utf-8'))
                    except Exception:
                        pass
                except Exception:
                    pass
                finally:
                    _SPLIT_BUILDING = False
            threading.Thread(target=_bg, daemon=True).start()
        return None

    def categoryContent(self, tid, pg=1, filter=False, extend=''):
        pg = int(pg or 1)
        if str(tid) in ('1', '2', '3', '4', '6'):
            b = self._get_split()
            if b is not None:
                b = b.get(str(tid), [])
                total = len(b)
                pagecount = max(1, (total + 23) // 24)
                if pg > pagecount:
                    return {'page': pg, 'pagecount': pagecount, 'limit': 24, 'total': total, 'list': []}
                return {'page': pg, 'pagecount': pagecount, 'limit': 24, 'total': total, 'list': b[(pg - 1) * 24:pg * 24]}
        key = str(tid) if str(tid) != 'new' else 'new_%d' % pg
        now = time.time()
        hit = _CAT_CACHE.get(key)
        if not hit or now - hit['t'] > 300:
            fd = _cat_load()
            fh = fd.get(key) if isinstance(fd, dict) else None
            if fh and now - fh.get('t', 0) < 86400:
                hit = {'h': fh.get('h', ''), 't': fh.get('t', 0)}
            else:
                if str(tid) == 'new':
                    html = self._get('%s/new/%d.html' % (self.host, pg), timeout=15)
                else:
                    html = self._get('%s/channel/%s.html' % (self.host, tid), timeout=15)
                hit = {'h': html, 't': now}
                if html:
                    _CAT_CACHE[key] = hit
                    fd[key] = {'h': html, 't': now}
                    _cat_save(fd)
        html = hit['h']
        if str(tid) == 'new':
            if pg < 40:
                def _pf():
                    try:
                        k2 = 'new_%d' % (pg + 1)
                        if k2 not in _CAT_CACHE:
                            h2 = self._get('%s/new/%d.html' % (self.host, pg + 1), timeout=6)
                            if h2:
                                _CAT_CACHE[k2] = {'h': h2, 't': time.time()}
                                fd = _cat_load()
                                fd[k2] = {'h': h2, 't': time.time()}
                                _cat_save(fd)
                    except Exception:
                        pass
                threading.Thread(target=_pf, daemon=True).start()
            return {'page': pg, 'pagecount': 999, 'limit': 24, 'total': 99999, 'list': self._parse_items(html) if html else []}
        if pg > 1:
            return {'page': pg, 'pagecount': 1, 'limit': 0, 'total': 48, 'list': []}
        return {'page': 1, 'pagecount': 1, 'limit': 48, 'total': 48, 'list': self._parse_items(html) if html else []}

    def detailContent(self, ids):
        vid = str(ids[0])
        html = self._get('%s/detail/%s.html' % (self.host, vid))
        if not html:
            return {'list': []}
        vod = {'vod_id': vid}
        ts = re.search(r'class="detail-title"[^>]*>(.*?)</div>', html, re.S)
        parts = []
        if ts:
            for s in re.findall(r'<strong[^>]*>(.*?)</strong>', ts.group(1), re.S):
                c = self._clean(s)
                if c and not self._is_wm(c):
                    parts.append(c)
        vod['vod_name'] = ''.join(parts).strip()
        if not vod['vod_name']:
            m = re.search(r'<title>([^<]+?)(?:-|_|高清|免费)', html)
            vod['vod_name'] = self._clean(m.group(1)) if m else ''
        pic = ''
        for im in re.findall(r'data-original="([^"]+\.(?:jpg|png|webp|jpeg)[^"]*)"', html):
            pic = self._pic(im)
            if pic:
                break
        vod['vod_pic'] = pic
        vod['vod_remarks'] = vod['vod_year'] = vod['vod_area'] = vod['vod_director'] = vod['vod_actor'] = vod['vod_content'] = ''
        for label, content in re.findall(r'class="detail-info-row"[^>]*>.*?class="detail-info-row-side"[^>]*>(.*?)</div>.*?class="detail-info-row-main"[^>]*>(.*?)</div>', html, re.S):
            label = self._clean(label)
            content = self._clean(content)
            if '导演' in label:
                vod['vod_director'] = content
            elif '演员' in label or '主演' in label:
                vod['vod_actor'] = content
            elif '状态' in label:
                vod['vod_remarks'] = content
            elif '地区' in label:
                vod['vod_area'] = content
            elif '年份' in label:
                vod['vod_year'] = content
        dc = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', html)
        vod['vod_content'] = self._clean(dc.group(1)) if dc else ''
        links = list(dict.fromkeys(re.findall(r'href="(/play/%s-\d+-\d+\.html)"' % vid, html)))
        pf, pu = [], []
        if links:
            ph = self._get(self.host + links[0])
            if ph:
                names = []
                for it in re.findall(r'<a[^>]*class="source-item[^"]*"[^>]*>(.*?)</a>', ph, re.S):
                    lb = re.search(r'source-item-label[^>]*>([^<]+)<', it)
                    sb = re.search(r'source-item-sublabel[^>]*>([^<]+)<', it)
                    lb = self._clean(lb.group(1)) if lb else ''
                    sb = self._clean(sb.group(1)) if sb else ''
                    names.append('%s(%s)' % (lb, sb) if lb and sb else (lb or '线路%d' % (len(names) + 1)))
                epl = re.findall(r'<div class="episode-list"[^>]*>(.*?)</div>', ph, re.S)
                lines = []
                for i, el in enumerate(epl[:len(names)]):
                    nm = names[i]
                    if self._is_wm(nm) or any(k in nm.lower() for k in self.skip):
                        continue
                    eps = []
                    for eu, ein in re.findall(r'<a[^>]*href="(/play/\d+-\d+-\d+\.html)"[^>]*>(.*?)</a>', el, re.S):
                        en = self._clean(ein) or '第%d集' % (len(eps) + 1)
                        eps.append('%s$%s' % (en, eu))
                    if eps:
                        lines.append((nm, '#'.join(eps)))
                if lines:
                    lines.sort(key=lambda x: 0 if ('蓝光' in x[0] and '高清' in x[0]) else (1 if '蓝光3' in x[0] else 2))
                    pf = [x[0] for x in lines]
                    pu = [x[1] for x in lines]
            if not pf:
                pf.append('线路1')
                pu.append('#'.join('第%d集$%s' % (i + 1, u) for i, u in enumerate(links)))
        vod['vod_play_from'] = '$$$'.join(pf)
        vod['vod_play_url'] = '$$$'.join(pu)
        return {'list': [vod]}

    def searchContent(self, key, quick, pg='1'):
        if not self._token or time.time() - self._token_t > 300:
            h = self._get(self.host + '/')
            m = re.search(r'name="t"[^>]*value="([^"]+)"', h or '')
            self._token = m.group(1) if m else ''
            self._token_t = time.time()
        if not self._token:
            return {'list': []}
        url = '%s/search?k=%s&t=%s' % (self.host, urllib.parse.quote(key, safe=''), urllib.parse.quote(self._token, safe=''))
        if str(pg) != '1':
            url += '&page=%s' % pg
        html = self._get(url)
        videos, seen = [], set()
        if html:
            for m in re.finditer(r'<a[^>]*href="(/detail/(\d+)\.html)"[^>]*class="search-result-item"[^>]*>(.*?)</a>', html, re.S):
                vid, inner = m.group(2), m.group(3)
                if vid in seen:
                    continue
                title = ''
                for attr in ('title', 'alt'):
                    tm = re.search(r'%s="([^"]+)"' % attr, inner)
                    if tm:
                        c = self._clean(tm.group(1))
                        if c and not self._is_wm(c):
                            title = c
                            break
                if not title:
                    for t in re.findall(r'class="[^"]*search-result-item-title[^"]*"[^>]*>(.*?)</div>', inner, re.S):
                        c = self._clean(t)
                        if c and not self._is_wm(c):
                            title = c
                            break
                fb = re.search(r'class="search-result-item-footer"[^>]*>(.*?)</div>', inner, re.S)
                pic = ''
                for im in re.findall(r'data-original="([^"]+\.(?:jpg|png|webp|jpeg)[^"]*)"', inner):
                    pic = self._pic(im)
                    if pic:
                        break
                if title and pic:
                    seen.add(vid)
                    videos.append({'vod_id': vid, 'vod_name': title, 'vod_pic': pic, 'vod_remarks': self._clean(fb.group(1)) if fb else ''})
        return {'list': videos}

    def playerContent(self, flag, id, vipFlags=None):
        u = str(id)
        if not u.startswith('http'):
            u = self.host + u
        html = self._get(u)
        url = ''
        m = re.search(r'playSource\s*=\s*\{[\s\S]*?src:\s*"([^"]+)"', html or '')
        if not m:
            m = re.search(r'playSource\s*\.\s*src\s*=\s*["\']([^"\']+)["\']', html or '')
        if not m:
            m = re.search(r'src\s*:\s*["\'](https?://[^"\']+\.(?:m3u8|mp4)[^"\']*)["\']', html or '', re.I)
        if m:
            url = m.group(1).replace('\\/', '/')
        if not url:
            vm = re.search(r'/play/(\d+)-', u)
            if vm:
                vid = vm.group(1)
                dh = self._get('%s/detail/%s.html' % (self.host, vid))
                for lu in re.findall(r'href="(/play/%s-\d+-\d+\.html)"' % vid, dh or ''):
                    if lu in u:
                        continue
                    ph2 = self._get(self.host + lu)
                    m2 = re.search(r'playSource\s*=\s*\{[\s\S]*?src:\s*"([^"]+)"', ph2 or '')
                    if not m2:
                        m2 = re.search(r'src\s*:\s*["\'](https?://[^"\']+\.(?:m3u8|mp4)[^"\']*)["\']', ph2 or '', re.I)
                    if m2:
                        url = m2.group(1).replace('\\/', '/')
                        break
        return {'parse': 0, 'url': url, 'header': {'User-Agent': self.ua, 'Referer': self.host + '/'}}
