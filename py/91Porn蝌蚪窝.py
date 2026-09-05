# -*- coding: utf-8 -*-
"""
91蝌蚪窝爬虫 (修复版)
站点: https://91kdw.cc
修复内容:
  - 移除自建 HTTP 代理服务（TVBox 环境不支持）
  - 改用 TVBox 标准 localProxy 处理图片/媒体代理
  - 修复返回格式
"""
import sys, re, base64, time, random, html, json
from urllib.parse import unquote, quote, urljoin
import requests

sys.path.append('..')
from base.spider import Spider as BaseSpider

# ===== 纯 Python AES-128 =====
_sbox = bytes([
    0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
    0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
    0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
    0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
    0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
    0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
    0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
    0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
    0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
    0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
    0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
    0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
    0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
    0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
    0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
    0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16])
_inv_sbox = bytes([
    0x52,0x09,0x6a,0xd5,0x30,0x36,0xa5,0x38,0xbf,0x40,0xa3,0x9e,0x81,0xf3,0xd7,0xfb,
    0x7c,0xe3,0x39,0x82,0x9b,0x2f,0xff,0x87,0x34,0x8e,0x43,0x44,0xc4,0xde,0xe9,0xcb,
    0x54,0x7b,0x94,0x32,0xa6,0xc2,0x23,0x3d,0xee,0x4c,0x95,0x0b,0x42,0xfa,0xc3,0x4e,
    0x08,0x2e,0xa1,0x66,0x28,0xd9,0x24,0xb2,0x76,0x5b,0xa2,0x49,0x6d,0x8b,0xd1,0x25,
    0x72,0xf8,0xf6,0x64,0x86,0x68,0x98,0x16,0xd4,0xa4,0x5c,0xcc,0x5d,0x65,0xb6,0x92,
    0x6c,0x70,0x48,0x50,0xfd,0xed,0xb9,0xda,0x5e,0x15,0x46,0x57,0xa7,0x8d,0x9d,0x84,
    0x90,0xd8,0xab,0x00,0x8c,0xbc,0xd3,0x0a,0xf7,0xe4,0x58,0x05,0xb8,0xb3,0x45,0x06,
    0xd0,0x2c,0x1e,0x8f,0xca,0x3f,0x0f,0x02,0xc1,0xaf,0xbd,0x03,0x01,0x13,0x8a,0x6b,
    0x3a,0x91,0x11,0x41,0x4f,0x67,0xdc,0xea,0x97,0xf2,0xcf,0xce,0xf0,0xb4,0xe6,0x73,
    0x96,0xac,0x74,0x22,0xe7,0xad,0x35,0x85,0xe2,0xf9,0x37,0xe8,0x1c,0x75,0xdf,0x6e,
    0x47,0xf1,0x1a,0x71,0x1d,0x29,0xc5,0x89,0x6f,0xb7,0x62,0x0e,0xaa,0x18,0xbe,0x1b,
    0xfc,0x56,0x3e,0x4b,0xc6,0xd2,0x79,0x20,0x9a,0xdb,0xc0,0xfe,0x78,0xcd,0x5a,0xf4,
    0x1f,0xdd,0xa8,0x33,0x88,0x07,0xc7,0x31,0xb1,0x12,0x10,0x59,0x27,0x80,0xec,0x5f,
    0x60,0x51,0x7f,0xa9,0x19,0xb5,0x4a,0x0d,0x2d,0xe5,0x7a,0x9f,0x93,0xc9,0x9c,0xef,
    0xa0,0xe0,0x3b,0x4d,0xae,0x2a,0xf5,0xb0,0xc8,0xeb,0xbb,0x3c,0x83,0x53,0x99,0x61,
    0x17,0x2b,0x04,0x7e,0xba,0x77,0xd6,0x26,0xe1,0x69,0x14,0x63,0x55,0x21,0x0c,0x7d])
_rcon = [0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x80,0x1b,0x36]

def _xtime(a):
    return ((a << 1) ^ 0x1b) & 0xff if a & 0x80 else (a << 1) & 0xff
def _gf_mul(a, b):
    r = 0
    for _ in range(8):
        if b & 1: r ^= a
        a = _xtime(a); b >>= 1
    return r
_mul_e = bytes(_gf_mul(0x0e, i) for i in range(256))
_mul_b = bytes(_gf_mul(0x0b, i) for i in range(256))
_mul_d = bytes(_gf_mul(0x0d, i) for i in range(256))
_mul_9 = bytes(_gf_mul(0x09, i) for i in range(256))
_key_schedules = {}

def _key_schedule(key):
    k = bytes(key)
    if k in _key_schedules: return _key_schedules[k]
    w = []
    for i in range(4): w.append([key[4*i], key[4*i+1], key[4*i+2], key[4*i+3]])
    for i in range(4, 44):
        temp = w[i-1][:]
        if i % 4 == 0:
            temp = temp[1:] + temp[:1]
            temp = [_sbox[b] for b in temp]
            temp[0] ^= _rcon[i//4 - 1]
        w.append([w[i-4][j] ^ temp[j] for j in range(4)])
    _key_schedules[k] = w
    return w

def _dec_block(block, w):
    s0,s1,s2,s3,s4,s5,s6,s7,s8,s9,s10,s11,s12,s13,s14,s15 = block
    s0 ^= w[40][0]; s1 ^= w[40][1]; s2 ^= w[40][2]; s3 ^= w[40][3]
    s4 ^= w[41][0]; s5 ^= w[41][1]; s6 ^= w[41][2]; s7 ^= w[41][3]
    s8 ^= w[42][0]; s9 ^= w[42][1]; s10^= w[42][2]; s11^= w[42][3]
    s12^= w[43][0]; s13^= w[43][1]; s14^= w[43][2]; s15^= w[43][3]
    box = _inv_sbox
    for rnd in range(9, 0, -1):
        t0=box[s0]; t1=box[s13]; t2=box[s10]; t3=box[s7]
        t4=box[s4]; t5=box[s1]; t6=box[s14]; t7=box[s11]
        t8=box[s8]; t9=box[s5]; t10=box[s2]; t11=box[s15]
        t12=box[s12]; t13=box[s9]; t14=box[s6]; t15=box[s3]
        rk=w[rnd*4]; t0^=rk[0]; t1^=rk[1]; t2^=rk[2]; t3^=rk[3]
        rk=w[rnd*4+1]; t4^=rk[0]; t5^=rk[1]; t6^=rk[2]; t7^=rk[3]
        rk=w[rnd*4+2]; t8^=rk[0]; t9^=rk[1]; t10^=rk[2]; t11^=rk[3]
        rk=w[rnd*4+3]; t12^=rk[0]; t13^=rk[1]; t14^=rk[2]; t15^=rk[3]
        s0 =_mul_e[t0]^_mul_b[t1]^_mul_d[t2]^_mul_9[t3]
        s1 =_mul_9[t0]^_mul_e[t1]^_mul_b[t2]^_mul_d[t3]
        s2 =_mul_d[t0]^_mul_9[t1]^_mul_e[t2]^_mul_b[t3]
        s3 =_mul_b[t0]^_mul_d[t1]^_mul_9[t2]^_mul_e[t3]
        s4 =_mul_e[t4]^_mul_b[t5]^_mul_d[t6]^_mul_9[t7]
        s5 =_mul_9[t4]^_mul_e[t5]^_mul_b[t6]^_mul_d[t7]
        s6 =_mul_d[t4]^_mul_9[t5]^_mul_e[t6]^_mul_b[t7]
        s7 =_mul_b[t4]^_mul_d[t5]^_mul_9[t6]^_mul_e[t7]
        s8 =_mul_e[t8]^_mul_b[t9]^_mul_d[t10]^_mul_9[t11]
        s9 =_mul_9[t8]^_mul_e[t9]^_mul_b[t10]^_mul_d[t11]
        s10=_mul_d[t8]^_mul_9[t9]^_mul_e[t10]^_mul_b[t11]
        s11=_mul_b[t8]^_mul_d[t9]^_mul_9[t10]^_mul_e[t11]
        s12=_mul_e[t12]^_mul_b[t13]^_mul_d[t14]^_mul_9[t15]
        s13=_mul_9[t12]^_mul_e[t13]^_mul_b[t14]^_mul_d[t15]
        s14=_mul_d[t12]^_mul_9[t13]^_mul_e[t14]^_mul_b[t15]
        s15=_mul_b[t12]^_mul_d[t13]^_mul_9[t14]^_mul_e[t15]
    t0=box[s0]; t1=box[s13]; t2=box[s10]; t3=box[s7]
    t4=box[s4]; t5=box[s1]; t6=box[s14]; t7=box[s11]
    t8=box[s8]; t9=box[s5]; t10=box[s2]; t11=box[s15]
    t12=box[s12]; t13=box[s9]; t14=box[s6]; t15=box[s3]
    rk=w[0]; t0^=rk[0]; t1^=rk[1]; t2^=rk[2]; t3^=rk[3]
    rk=w[1]; t4^=rk[0]; t5^=rk[1]; t6^=rk[2]; t7^=rk[3]
    rk=w[2]; t8^=rk[0]; t9^=rk[1]; t10^=rk[2]; t11^=rk[3]
    rk=w[3]; t12^=rk[0]; t13^=rk[1]; t14^=rk[2]; t15^=rk[3]
    return bytes([t0,t1,t2,t3,t4,t5,t6,t7,t8,t9,t10,t11,t12,t13,t14,t15])

def _aes_cbc_decrypt(data, key, iv):
    if not data or len(data) % 16: return data
    n = len(data) // 16
    w = _key_schedule(key)
    out = bytearray(len(data))
    prev = iv
    for i in range(n):
        block = data[i*16:(i+1)*16]
        dec = _dec_block(block, w)
        for j in range(16):
            out[i*16+j] = dec[j] ^ prev[j]
        prev = block
    pad = out[-1]
    if 1 <= pad <= 16:
        return bytes(out[:-pad])
    return bytes(out)


# ===== 主 Spider 类 =====
class Spider(BaseSpider):
    host = 'https://91kdw.cc'
    session = requests.Session()
    _cached_categories = []
    _debug = True

    def _log(self, msg):
        if self._debug:
            print(f'[91kdw] {msg}')

    def getName(self): return '91kdw'
    def isVideoFormat(self, url):
        if not url: return False
        return '.m3u8' in url or '.mp4' in url or '.ts' in url or url.startswith('magnet:')
    def manualVideoCheck(self): return False
    def destroy(self): pass

    def localProxy(self, param):
        """TVBox 标准图片/媒体代理"""
        url = param
        if not url or not url.startswith('http'):
            return [500, 'text/plain', 'error: invalid url']
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': self.host + '/',
            }
            r = self.session.get(url, headers=headers, timeout=15, stream=True)
            if r.status_code != 200:
                return [r.status_code, 'text/plain', 'proxy error']
            ct = r.headers.get('Content-Type', 'application/octet-stream')
            # Read up to 10MB
            data = r.content
            return [200, ct, data]
        except Exception as e:
            self._log(f'localProxy error: {e}')
            return [500, 'text/plain', str(e)]

    def init(self, extend=''):
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        })
        text = self._fetch(self.host)
        if not text:
            return
        # 处理防采集等待页面（5秒盾）
        cron_match = re.search(r'<img\s+src="(/cron\.php\?id=\d+)"', text)
        if cron_match:
            cron_url = self.host + cron_match.group(1)
            self._log(f'检测到防采集保护，初始化会话: {cron_url}')
            self._fetch(cron_url)
            time.sleep(3)
            text = self._fetch(self.host)
        if text:
            self._cached_categories = self._load_categories(text)

    def _get_headers(self, referer=None):
        h = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        h['Referer'] = referer if referer else self.host + '/'
        return h

    def _fetch(self, url, referer=None, retries=3):
        for attempt in range(retries):
            try:
                if attempt > 0:
                    time.sleep(random.uniform(1, 2))
                r = self.session.get(url, headers=self._get_headers(referer), timeout=30)
                r.encoding = 'utf-8'
                if r.status_code == 200:
                    return r.text
                elif r.status_code in [403, 429, 503]:
                    self._log(f'被拦截 [{r.status_code}]，重试 {attempt+1}: {url}')
                    continue
                else:
                    self._log(f'失败 [{r.status_code}]: {url}')
                    return ''
            except requests.exceptions.Timeout:
                self._log(f'超时，重试 {attempt+1}: {url}')
            except Exception as e:
                self._log(f'异常 [{e}]，重试 {attempt+1}: {url}')
        return ''

    @staticmethod
    def _decode_b64(encoded_str):
        if not encoded_str: return ''
        clean = encoded_str.strip()
        try:
            raw = base64.b64decode(clean, validate=False)
            for enc in ['utf-8', 'gbk', 'gb18030']:
                try:
                    decoded = raw.decode(enc)
                    try: decoded = unquote(decoded)
                    except: pass
                    return decoded
                except: continue
        except: pass
        return clean

    def _extract_encrypted_title(self, raw_text):
        if not raw_text: return ''
        b64_match = re.search(r"d\s*\(\s*['\"]([A-Za-z0-9+/=]{8,})['\"]\s*\)", raw_text, re.I)
        if b64_match:
            decoded = self._decode_b64(b64_match.group(1))
            if decoded and '<' not in decoded and 'script' not in decoded.lower() and len(decoded) < 50:
                return decoded.strip()
        return ''

    def _load_categories(self, text):
        if not text: return []
        cats = []
        seen_tid = set()
        seen_name = set()
        for m in re.finditer(r'href="(/list/(\d+)-1\.html)"[^>]*>(.*?)</a>', text, re.S):
            path, tid, content = m.groups()
            if tid in seen_tid: continue
            name = self._extract_encrypted_title(content)
            if not name:
                clean = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.S | re.I)
                clean = re.sub(r'<[^>]+>', '', clean).strip()
                clean = html.unescape(clean).strip()
                name = clean
            if not name or len(name) > 30 or '<' in name or 'script' in name.lower():
                continue
            if name in seen_name: continue
            seen_tid.add(tid); seen_name.add(name)
            cats.append({'type_id': tid, 'type_name': name})
        self._log(f'分类: {len(cats)} 个')
        # 过滤掉无用分类
        skip_names = ['欧美色情', '日本BT', '国产BT']
        cats = [c for c in cats if c['type_name'] not in skip_names]
        self._log(f'过滤后: {len(cats)} 个')
        return cats

    def _extract_title(self, fragment):
        if not fragment: return ''
        title = self._extract_encrypted_title(fragment)
        if title: return title
        clean = re.sub(r'<script[^>]*>.*?</script>', '', fragment, flags=re.S | re.I)
        clean = re.sub(r'<[^>]+>', '', clean).strip()
        clean = html.unescape(clean).strip()
        if not clean or 'script' in clean.lower():
            return ''
        return clean

    def _parse_list(self, html):
        items = []
        seen_ids = set()
        # Split on thumbnail group divs (each card starts with <div class="thumbnail group">)
        cards = re.split(r'<div class="thumbnail group">', html)
        for card in cards[1:]:  # Skip everything before first card
            # Extract video ID
            link_m = re.search(r'/video/(\d+)\.html', card)
            if not link_m: continue
            vid = link_m.group(1)
            if vid in seen_ids: continue
            seen_ids.add(vid)
            # Extract image
            img_m = re.search(r'<img[^>]+(?:src|data-src)="([^"]+)"', card)
            pic = img_m.group(1) if img_m else ''
            # Extract title from d('base64')
            d_m = re.search(r"d\s*\(\s*['\"]([A-Za-z0-9+/=]{10,})['\"]\s*\)", card)
            if d_m:
                decoded = self._decode_b64(d_m.group(1))
                if decoded and '<' not in decoded and len(decoded) < 100:
                    title = decoded.strip()
                else:
                    title = '未知标题'
            else:
                title = '未知标题'
            items.append({
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': pic,
                'vod_remarks': '',
            })
        self._log(f'解析列表: {len(items)} 个视频')
        return items

    def _get_list(self, tid, page):
        url = f'{self.host}/list/{tid}-{page}.html'
        html = self._fetch(url, referer=f'{self.host}/list/{tid}-1.html')
        return self._parse_list(html) if html else []

    def homeContent(self, filter):
        try:
            text = self._fetch(self.host)
            if text: self._cached_categories = self._load_categories(text)
            cats = self._cached_categories or []
            items = self._get_list(cats[0]['type_id'], 1) if cats else []
            return {'class': cats, 'list': items}
        except Exception as e:
            self._log(f'homeContent: {e}')
            return {'class': [], 'list': []}

    def homeVideoContent(self):
        if self._cached_categories:
            return {'list': self._get_list(self._cached_categories[0]['type_id'], 1)}
        return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg) if pg else 1
            items = self._get_list(tid, page)
            total_page = page + 1
            if page == 1:
                html = self._fetch(f'{self.host}/list/{tid}-1.html')
                if html:
                    pages = re.findall(r'/list/\d+-(\d+)\.html', html)
                    if pages: total_page = max(int(p) for p in pages)
            return {'list': items, 'page': page, 'pagecount': total_page}
        except Exception as e:
            self._log(f'categoryContent: {e}')
            return {'list': [], 'page': int(pg) if pg else 1, 'pagecount': 1}

    def _fetch_detail(self, vid):
        url = f'{self.host}/video/{vid}.html'
        html = self._fetch(url, referer=self.host)
        if not html:
            for alt in [f'/torrent/{vid}.html', f'/v/{vid}.html', f'/movie/{vid}.html']:
                html = self._fetch(f'{self.host}{alt}', referer=self.host)
                if html: break
        if not html: return None
        return self._parse_detail(html, vid)

    def _parse_detail(self, html, vid):
        title = ''
        m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
        if m:
            d_m = re.search(r"d\s*\(\s*['\"]([A-Za-z0-9+/=]{10,})['\"]\s*\)", m.group(1))
            if d_m: title = self._decode_b64(d_m.group(1))
        if not title:
            m = re.search(r'<title>([^<]+)</title>', html)
            if m: title = m.group(1).strip()
        # Cover
        cover = ''
        m = re.search(r'property="og:image"[^>]*content="([^"]+)"', html)
        if m: cover = m.group(1)
        # Play URL from playFilteredHLS() - second string parameter
        play_urls = []
        seen_urls = set()
        def _add(label, u):
            if u in seen_urls: return
            seen_urls.add(u)
            play_urls.append(f'{label}${u}')
        # Extract from playFilteredHLS() calls
        for m in re.finditer(r"""playFilteredHLS\s*\([^)]*['\"](https?://[^\"']+\.php[^\"']*)['\"]""", html):
            _add('播放', m.group(1))
        # Extract from iframes with play.php
        for src in set(re.finditer(r'<iframe[^>]+(?:src|data-src)="([^"]*play\.php[^"]*)"', html)):
            _add('播放', src.group(1))
        # Direct media links
        for media in set(re.finditer(r'https?://[^\s"\'<>]+\.(?:m3u8|mp4|flv|ts)(?:\?[^\s"\'<>]*)?', html)):
            _add('直链', media.group(0))
        # Fallback: any play.php URL
        if not play_urls:
            for p in re.finditer(r"""['"](https?://[^"']*play\.php[^"']*)['"]""", html):
                _add('备用', p.group(1))
        if not play_urls:
            self._log(f'无播放链接: {vid}')
            return None
        sources = [p.split('$', 1)[0] for p in play_urls]
        urls = [p for p in play_urls]
        return {
            'vod_id': vid,
            'vod_name': title or vid,
            'vod_pic': cover,
            'vod_play_from': '$$$'.join(sources),
            'vod_play_url': '#'.join(urls),
        }

    def detailContent(self, ids):
        try:
            vid = str(ids[0] if isinstance(ids, list) else ids)
            if vid.startswith('magnet:'):
                return {'list': [{'vod_id': vid, 'vod_name': '磁力资源', 'vod_play_from': '磁力', 'vod_play_url': f'磁力${vid}'}]}
            detail = self._fetch_detail(vid)
            return {'list': [detail]} if detail else {'list': []}
        except Exception as e:
            self._log(f'detailContent: {e}')
            return {'list': []}

    def playerContent(self, flag, id, vipFlags=None):
        try:
            return {'parse': 0, 'url': id, 'header': {'Referer': self.host, 'User-Agent': 'Mozilla/5.0'}}
        except Exception as e:
            self._log(f'playerContent: {e}')
            return {'parse': 0, 'url': '', 'header': {}}

    def searchContent(self, key, quick, pg='1'):
        try:
            page = int(pg) if pg else 1
            url = f'{self.host}/search.php?content={quote(key)}&type=1&page={page}'
            html = self._fetch(url, referer=self.host)
            items = self._parse_list(html) if html else []
            if not items:
                url = f'{self.host}/search.php?content={quote(key)}&type=2&page={page}'
                html = self._fetch(url, referer=self.host)
                items = self._parse_list(html) if html else []
            return {'list': items, 'page': page, 'pagecount': page + 1}
        except Exception as e:
            self._log(f'searchContent: {e}')
            return {'list': [], 'page': int(pg) if pg else 1, 'pagecount': 1}
