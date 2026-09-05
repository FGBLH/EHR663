# -*- coding: utf-8 -*-
import sys
import re
import json
import base64
import hashlib
import time
from urllib.parse import urljoin, quote

sys.path.append('..')
try:
    from base.spider import Spider
except ImportError:
    class Spider:
        def fetch(self, url, headers=None, **kw):
            import requests as rq
            kw.pop('timeout', None)
            r = rq.get(url, headers=headers, timeout=15, **kw)
            r.encoding = 'utf-8'
            return r

HOST = "https://hqvod.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

CATEGORIES = {
    "1": "电影", "2": "剧集", "3": "动漫", "4": "综艺", "5": "短剧",
}

_KEY = bytes.fromhex('4f6464664a6b74456247753767437639')
_IV = bytes.fromhex('6f6b6a75745533526a4770577142385a')
SBOX = bytes([0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16])
ISBOX = [0] * 256
for _i in range(256):
    ISBOX[SBOX[_i]] = _i
_G9 = [0] * 256
_G11 = [0] * 256
_G13 = [0] * 256
_G14 = [0] * 256
def _gm(_a, _b):
    _r = 0
    for _ in range(8):
        if _b & 1:
            _r ^= _a
        _h = _a & 0x80
        _a = (_a << 1) & 0xff
        if _h:
            _a ^= 0x1b
        _b >>= 1
    return _r
for _i in range(256):
    _G9[_i] = _gm(_i, 9)
    _G11[_i] = _gm(_i, 11)
    _G13[_i] = _gm(_i, 13)
    _G14[_i] = _gm(_i, 14)
def _ks(_k):
    _w = [int.from_bytes(_k[i:i+4], 'big') for i in range(0, 16, 4)]
    _rc = 1
    for _i in range(4, 44):
        _t = _w[_i-1]
        if _i % 4 == 0:
            _t = ((SBOX[(_t>>16)&255] << 24) | (SBOX[(_t>>8)&255] << 16) | (SBOX[_t&255] << 8) | SBOX[(_t>>24)&255]) ^ (_rc << 24)
            _rc = ((_rc << 1) ^ (0x11B if _rc & 0x80 else 0))
        _w.append(_w[_i-4] ^ _t)
    return b''.join(_x.to_bytes(4, 'big') for _x in _w)
_RK = _ks(_KEY)
def _db(_b):
    _s = list(_b)
    for _i in range(16):
        _s[_i] ^= _RK[160+_i]
    for _r in range(9, -1, -1):
        _s[1], _s[5], _s[9], _s[13] = _s[13], _s[1], _s[5], _s[9]
        _s[2], _s[6], _s[10], _s[14] = _s[10], _s[14], _s[2], _s[6]
        _s[3], _s[7], _s[11], _s[15] = _s[7], _s[11], _s[15], _s[3]
        for _i in range(16):
            _s[_i] = ISBOX[_s[_i]]
        for _i in range(16):
            _s[_i] ^= _RK[_r*16+_i]
        if _r > 0:
            for _c in range(4):
                _i = _c * 4
                _a0, _a1, _a2, _a3 = _s[_i], _s[_i+1], _s[_i+2], _s[_i+3]
                _s[_i] = _G14[_a0] ^ _G11[_a1] ^ _G13[_a2] ^ _G9[_a3]
                _s[_i+1] = _G9[_a0] ^ _G14[_a1] ^ _G11[_a2] ^ _G13[_a3]
                _s[_i+2] = _G13[_a0] ^ _G9[_a1] ^ _G14[_a2] ^ _G11[_a3]
                _s[_i+3] = _G11[_a0] ^ _G13[_a1] ^ _G9[_a2] ^ _G14[_a3]
    return bytes(_s)
def _dec(_b64):
    _data = base64.b64decode(_b64)
    try:
        from Crypto.Cipher import AES as _CA
        _d = _CA.new(_KEY, _CA.MODE_CBC, _IV).decrypt(_data)
    except:
        _out = bytearray()
        _prev = _IV
        for _i in range(0, len(_data), 16):
            _blk = _data[_i:_i+16]
            _p = _db(_blk)
            for _j in range(16):
                _out.append(_p[_j] ^ _prev[_j])
            _prev = _blk
        _d = bytes(_out)
    _pad = _d[-1] if _d else 0
    if 0 < _pad <= 16 and _d[-_pad:] == bytes([_pad]) * _pad:
        _d = _d[:-_pad]
    return _d

class Spider(Spider):
    def init(self, extend=""):
        global HOST
        if extend and extend.startswith('http'):
            HOST = extend.rstrip('/')

    def homeContent(self, filter=False):
        r = {"class": [], "list": []}
        for k, v in CATEGORIES.items():
            r["class"].append({"type_id": k, "type_name": v})
        return r

    def homeVideoContent(self):
        try:
            r = self.fetch(HOST, headers={"User-Agent": UA}, timeout=15000)
            h = r.text if hasattr(r, 'text') else str(r)
            return {"list": self._items(h)}
        except:
            return {"list": []}

    def categoryContent(self, tid, pg=1, filter=False, extend=""):
        pn = 1
        try:
            pn = max(int(str(pg)), 1)
        except:
            pass
        try:
            url = f"{HOST}/fenlei/{tid}" + (f"-{pn}.html" if pn > 1 else ".html")
            r = self.fetch(url, headers={"User-Agent": UA}, timeout=30000)
            h = r.text if hasattr(r, 'text') else str(r)
            items = self._items(h)
            return {
                "page": pn,
                "pagecount": self._pagecount(h, pn),
                "limit": 30,
                "total": len(items),
                "list": items
            }
        except:
            return {"page": pn, "pagecount": 1, "limit": 30, "total": 0, "list": []}

    def detailContent(self, ids):
        if isinstance(ids, list):
            vid = ids[0] if ids else ""
        else:
            vid = str(ids) if ids else ""
        m = re.search(r'(\d+)', str(vid))
        vid = m.group(1) if m else ""
        if not vid:
            return {"list": []}
        try:
            r = self.fetch(f"{HOST}/xiangqing/{vid}.html", headers={"User-Agent": UA}, timeout=30000)
            h = r.text if hasattr(r, 'text') else str(r)
        except:
            return {"list": []}

        d = {
            "vod_id": vid, "vod_name": "", "vod_pic": "", "vod_year": "",
            "vod_area": "", "vod_class": "", "vod_director": "", "vod_actor": "",
            "vod_content": "", "vod_remarks": "", "vod_play_from": "", "vod_play_url": ""
        }

        tn = re.search(r'<title>(.*?)</title>', h)
        if tn:
            nm = re.search(r'《(.*?)》', tn.group(1))
            d["vod_name"] = nm.group(1) if nm else re.split(r'[_-]', tn.group(1))[0].strip()[:50]

        p = re.search(r"this-pic-bj\" style=\"background-image: url\('([^']+)'\)", h)
        if not p:
            p = re.search(r'data-src="(https?://[^"]+\.(?:jpg|jpeg|png|webp|avif))"', h, re.I)
        if p:
            d["vod_pic"] = self._p(p.group(1))

        dm = re.search(r'name="description" content="([^"]*)"', h)
        if dm:
            d["vod_content"] = dm.group(1).strip()[:500]

        for kw, key in [('年份', 'vod_year'), ('地区', 'vod_area'), ('状态', 'vod_remarks')]:
            m2 = re.search(r'<em class="cor4">' + kw + r'：</em>(?:<[^>]+>)*\s*([^<]+)', h)
            if m2:
                d[key] = m2.group(1).strip()
        cm = re.search(r'<em class="cor4">类型：</em>([\s\S]{0,80}?)</li>', h)
        if cm:
            d["vod_class"] = re.sub(r'<[^>]+>', '', cm.group(1)).strip()
        am = re.search(r'<em class="cor4">主演：</em>([\s\S]{0,80}?)</li>', h)
        if am:
            d["vod_actor"] = re.sub(r'<[^>]+>', '', am.group(1)).strip()
        dr = re.search(r'<strong class="r6">导演:</strong>([\s\S]{0,80}?)(?:</li>|</div>)', h)
        if dr:
            d["vod_director"] = re.sub(r'<[^>]+>', '', dr.group(1)).strip()

        ls = re.findall(r'<a class="swiper-slide">[^<]*<i[^>]*></i>&nbsp;([^<]+)<span', h)
        boxes = re.findall(r'<div class="anthology-list-box[^"]*">([\s\S]*?)</div></div>', h)
        pf, pu = [], []
        for i, box in enumerate(boxes):
            eps = re.findall(r'href="/bofang/(\d+-\d+-\d+)\.html"[^>]*>([^<]+)</a>', box)
            if eps:
                name = ls[i] if i < len(ls) else f"线路{i+1}"
                pf.append(name)
                pu.append("#".join([f"{e.strip()}${HOST}/index.php/bofang/{p}.html" for p, e in eps]))
        if pf:
            d["vod_play_from"] = "$$$".join(pf)
            d["vod_play_url"] = "$$$".join(pu)

        return {"list": [d]}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            url = f"{HOST}/sousuo/-------------.html?wd={quote(key)}"
            r = self.fetch(url, headers={"User-Agent": UA}, timeout=30000)
            h = r.text if hasattr(r, 'text') else str(r)
            return {"list": self._items(h)}
        except:
            return {"list": []}

    def playerContent(self, flag, id, vipFlags=None):
        u = str(id)
        if not u.startswith('http'):
            return {"parse": 0, "url": ""}
        try:
            import requests as _rq
            _s = _rq.Session()
            _s.headers.update({'User-Agent': UA})
            _s.get(u, timeout=15000)
            r = _s.get(u, timeout=15000)
            h = r.text
            i = h.find('player_aaaa')
            if i >= 0:
                st = h.find('{', i)
                dp = 0
                for j in range(st, len(h)):
                    if h[j] == '{':
                        dp += 1
                    elif h[j] == '}':
                        dp -= 1
                        if dp == 0:
                            break
                d = json.loads(h[st:j+1])
                if d.get("url"):
                    pu = self._pe(d["url"], u)
                    if pu:
                        return {"parse": 0, "url": pu}
        except:
            pass
        return {"parse": 0, "url": u}

    def _pe(self, enc, u):
        try:
            m = re.search(r'/bofang/(\d+)-(\d+)-(\d+)\.html', u)
            if not m:
                return ""
            vid, sid, nid = m.group(1), m.group(2), m.group(3)
            nu = re.sub(r'-(\d+)\.html$', lambda x: '-' + str(int(x.group(1)) + 1) + '.html', u)
            uv = enc + '&next=//' + nu.split('//', 1)[1]
            def _rc4(_k, _d):
                _S = list(range(256)); _j = 0
                for _i in range(256):
                    _j = (_j + _S[_i] + _k[_i % len(_k)]) % 256
                    _S[_i], _S[_j] = _S[_j], _S[_i]
                _i = _j = 0; _o = bytearray()
                for _c in _d:
                    _i = (_i + 1) % 256; _j = (_j + _S[_i]) % 256
                    _S[_i], _S[_j] = _S[_j], _S[_i]
                    _o.append(_c ^ _S[(_S[_i] + _S[_j]) % 256])
                return bytes(_o)
            def _m5(_x):
                return hashlib.md5(_x.encode()).hexdigest()
            _ck = _m5(uv)[-20:] + ' P'
            _ep = lambda _x: base64.b64encode(_rc4(_ck.encode(), _x)).decode()
            _ts = int(time.time())
            import requests as _rq
            _data = 'url=' + quote(uv, safe='') + '&key=' + quote(_ep(_m5(uv + 'stray').encode()), safe='') + '&vkey=' + quote(_ep((str(_ts) + _m5(_ck + 'stray')).encode()), safe='') + '&ckey=' + quote(_ep(_m5('xn--2p1a.bfapi.cyou' + 'stray').encode()), safe='')
            _hd = {
                'User-Agent': UA,
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Referer': 'https://xn--2p1a.bfapi.cyou/player/?url=' + quote(enc) + '&next=//' + nu.split('//', 1)[1]
            }
            _j = _rq.post('https://xn--2p1a.bfapi.cyou/player/api.php', data=_data, headers=_hd, timeout=15000).json()
            if _j.get('code') == 200 and _j.get('url'):
                _pt = _dec(_j['url'])
                if _pt and (b'.m3u8' in _pt or b'.mp4' in _pt):
                    return _pt.decode()
        except:
            pass
        return ""

    def localProxy(self, param):
        pass

    def _pagecount(self, html, current_page=1):
        mp = current_page
        for p in re.findall(r'href="/fenlei/\d+-(\d+)\.html"', html):
            try:
                mp = max(mp, int(p))
            except:
                pass
        if 'title="下一页"' in html and mp <= current_page:
            mp = current_page + 1
        return mp

    def _p(self, url):
        if not url:
            return url
        return 'https://pl3.vvvvvvvv.top/api/play?url=' + quote(url, safe='')

    def _items(self, html):
        items, seen = [], set()
        for m in re.finditer(r'href="/xiangqing/(\d+)\.html"[^>]*title="([^"]*)"', html):
            vid = m.group(1)
            if vid in seen:
                continue
            name = m.group(2).strip()
            if not name or len(name) > 100:
                continue
            after = html[m.end():m.end() + 1500]
            cover = re.search(r'data-src="(https?://[^"]+\.(?:jpg|jpeg|png|webp|avif))"', after, re.I)
            if not cover:
                cover = re.search(r'src="(https?://[^"]+\.(?:jpg|jpeg|png|webp|avif))"', after, re.I)
            remark = re.search(r'public-list-prb[^>]*>([^<]+)<', after)
            seen.add(vid)
            items.append({
                "vod_id": vid,
                "vod_name": name[:50],
                "vod_pic": self._p(cover.group(1)) if cover else "",
                "vod_remarks": remark.group(1).strip() if remark else "",
            })
        return items
