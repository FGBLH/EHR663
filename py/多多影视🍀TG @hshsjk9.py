# -*- coding: utf-8 -*-
import sys, re, time, json, hashlib, base64
from urllib.parse import quote
sys.path.append('..')
try:
    from base.spider import Spider
except:
    class Spider: pass

HOSTS = ['https://323433ssdfd.top', 'https://duoduosdf12223234334.top', 'https://xds2435u23422342342u.top', 'https://dduotv01.top']
HOST = HOSTS[0]
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36'
F = 'WF-2c064bc5b3400788f31b848849bc3a60f835423ba2dfe69d7ea93974c216e4f2'
SK = 'WEB-50a8e9c84a1dc05669a692ded99a2dac46527229e607a7be15db88dbc59059d1'
ID = 'com.web.player'
W = 'ddtvf65f3a83d6d9ad6f'
XC = '8f3d2a1c7b6e5d4c9a0b1f2e3d4c5b6a'
CATEGORIES = [{'type_id': '1', 'type_name': '电影'}, {'type_id': '2', 'type_name': '剧集'}, {'type_id': '3', 'type_name': '动漫'}, {'type_id': '4', 'type_name': '综艺'}]

def _vint(n):
    out = b''
    while True:
        b = n & 0x7f
        n >>= 7
        if n:
            out += bytes([b | 0x80])
        else:
            out += bytes([b])
            break
    return out

def _pb(url, vf, ts):
    sig = hashlib.sha256(('finger=%s&id=%s&nonce=%s&sk=%s&time=%s&v=1' % (F, ID, '0' * 32, SK, ts)).encode()).hexdigest().upper()
    b = b'\x0a' + _vint(len(url)) + url.encode()
    b += b'\x12' + _vint(len(vf)) + vf.encode()
    b += b'\x18' + _vint(ts)
    b += b'\x22' + _vint(32) + b'0' * 32
    b += b'\x2a' + _vint(64) + sig.encode()
    b += b'\x32' + _vint(14) + b'com.web.player'
    b += b'\x38\x01'
    return b

def _parse_pb(b):
    i, fields = 0, {}
    while i < len(b):
        tag = b[i]; i += 1
        f = tag >> 3; w = tag & 7
        if w == 0:
            v = 0; s = 0
            while True:
                x = b[i]; i += 1
                v |= (x & 0x7f) << s
                if not x & 0x80: break
                s += 7
            fields[f] = v
        elif w == 2:
            ln = 0; s2 = 0
            while True:
                x = b[i]; i += 1
                ln |= (x & 0x7f) << s2
                if not x & 0x80: break
                s2 += 7
            fields[f] = b[i:i + ln].decode('utf-8', errors='replace')
            i += ln
        elif w == 5:
            i += 4
    return fields

class Spider(Spider):
    def __init__(self):
        self.h = {'web-sign': W, 'X-Client': XC, 'User-Agent': UA}
        self._host = HOST

    def init(self, extend=""):
        self.__init__()

    def _fetch(self, url, params=None, headers=None, data=None, method='GET'):
        hosts = [self._host] + [h for h in HOSTS if h != self._host]
        for host in hosts:
            u = url.replace(HOST, host, 1) if HOST in url else url
            try:
                import requests
                kw = dict(timeout=6, verify=False)
                if method == 'POST':
                    r = requests.post(u, params=params, headers=headers, data=data, **kw)
                else:
                    r = requests.get(u, params=params, headers=headers, **kw)
                if r.status_code == 200:
                    self._host = host
                    return r.content
            except Exception:
                pass
            try:
                import urllib.request, ssl
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                if params:
                    u += ('&' if '?' in u else '?') + '&'.join('%s=%s' % (k, quote(str(v))) for k, v in params.items())
                req = urllib.request.Request(u, data=data, headers=headers or {})
                r = urllib.request.urlopen(req, timeout=6, context=ctx)
                self._host = host
                return r.read()
            except Exception:
                pass
        return b''

    def _get(self, path, params=None):
        for _ in range(2):
            r = self._fetch(HOST + path, params=params, headers=self.h)
            if r:
                try:
                    return json.loads(r)
                except Exception:
                    pass
            time.sleep(0.3)
        return {}

    def _norm(self, v):
        return {'vod_id': v.get('vod_id'), 'vod_name': v.get('vod_name'), 'vod_pic': v.get('vod_pic'), 'vod_remarks': v.get('vod_remarks')}

    def homeContent(self, filter=False):
        j = self._get('/api.php/web/index/home')
        d = j.get('data') or {}
        cats = []
        vids = []
        for c in d.get('categories') or []:
            cats.append({'type_id': str(c.get('type_id')), 'type_name': c.get('type_name')})
            for v in c.get('videos') or []:
                vids.append(self._norm(v))
        return {'class': cats, 'list': vids}

    def homeVideoContent(self):
        j = self._get('/api.php/web/index/home')
        d = j.get('data') or {}
        vids = []
        for c in d.get('categories') or []:
            for v in c.get('videos') or []:
                vids.append(self._norm(v))
        return {'list': vids}

    def categoryContent(self, tid, pg=1, filter=False, extend=""):
        name = next((c['type_name'] for c in CATEGORIES if c['type_id'] == str(tid)), '电影')
        j = self._get('/api.php/web/filter/vod', {'type_name': name, 'page': pg, 'sort': 'hits'})
        data = j.get('data') or []
        vids = [self._norm(v) for v in data]
        return {'list': vids, 'page': pg, 'pagecount': 9999, 'limit': 18, 'total': 9999}

    def detailContent(self, ids):
        j = self._get('/api.php/web/vod/get_detail', {'vod_id': ids[0]})
        d = (j.get('data') or [{}])[0]
        v = {'vod_id': d.get('vod_id'), 'vod_name': d.get('vod_name'), 'vod_pic': d.get('vod_pic'),
             'type_name': d.get('type_name'), 'vod_year': d.get('vod_year'), 'vod_area': d.get('vod_area'),
             'vod_remarks': d.get('vod_remarks'), 'vod_actor': d.get('vod_actor'), 'vod_director': d.get('vod_director'),
             'vod_content': d.get('vod_content'), 'vod_play_from': d.get('vod_play_from'), 'vod_play_url': d.get('vod_play_url')}
        return {'list': [v]}

    def searchContent(self, key, quick=False, pg='1'):
        j = self._get('/api.php/web/search/index', {'wd': key, 'page': pg, 'limit': 15})
        data = j.get('data') or []
        return {'list': [self._norm(v) for v in data]}

    def playerContent(self, flag, id, vipFlags=None):
        ts = int(time.time() * 1000)
        body = _pb(id, flag, ts)
        h = dict(self.h)
        h['Content-Type'] = 'application/x-protobuf'
        h['Accept'] = 'application/x-protobuf'
        for _ in range(2):
            try:
                r = self._fetch(HOST + '/api.php/web/decode/url', headers=h, data=body, method='POST')
                fields = _parse_pb(r)
                if fields.get(1) == 1 and fields.get(3):
                    return {'parse': 0, 'url': fields[3]}
            except Exception:
                pass
            time.sleep(0.3)
        return {}

    def destroy(self):
        pass
