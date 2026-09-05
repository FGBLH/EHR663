# -*- coding: utf-8 -*-
import sys
import re
import json
import base64
import threading
import requests
import urllib3
import os
import time
import random
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import unquote, quote, urljoin

urllib3.disable_warnings()
sys.path.append('..')
from base.spider import Spider as BaseSpider

# ===== 纯 Python AES-128 工具 =====
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
        a = _xtime(a)
        b >>= 1
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
    for i in range(4):
        w.append([key[4*i], key[4*i+1], key[4*i+2], key[4*i+3]])
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

# ===== 全局代理服务 =====
_proxy_port = 0
_proxy_started = False
_proxy_session = requests.Session()
_proxy_session.verify = False
_proxy_headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://hscka.cc/',
}
class _ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
class _ProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            real_url = unquote(self.path[1:])
            if not real_url or not real_url.startswith('http'):
                self.send_response(404); self.end_headers(); return
            r = _proxy_session.get(real_url, headers=_proxy_headers, timeout=20, verify=False)
            ct = r.headers.get('Content-Type', 'image/jpeg')
            self.send_response(200)
            self.send_header('Content-Type', ct)
            self.send_header('Content-Length', len(r.content))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(r.content)
        except BrokenPipeError:
            pass
        except Exception:
            self.send_response(404); self.end_headers()
    def log_message(self, format, *args): pass
def _find_free_port():
    import socket
    sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sk.bind(('127.0.0.1', 0))
    port = sk.getsockname()[1]
    sk.close()
    return port
def _start_proxy():
    global _proxy_port, _proxy_started
    if _proxy_started: return
    _proxy_port = _find_free_port()
    server = _ThreadedHTTPServer(('127.0.0.1', _proxy_port), _ProxyHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _proxy_started = True

# ===== Spider 类 =====
class Spider(BaseSpider):
    session = requests.Session()
    host = 'https://hscka.cc'

    def __init__(self):
        super().__init__()
        self._categories_cache = None
        self._m3u_lock = threading.Lock()
        self._debug = True  # 开启调试日志
        
        # ===== 持久化存储配置 =====
        self._data_dir = '/sdcard' if os.path.exists('/sdcard') else '.'
        self._saved_data_file = os.path.join(self._data_dir, '.hscka_saved.json')
        # 加载已保存数据: {vid: {name, url, pic, cat, type, time}}
        self._saved_videos = self._load_saved_data()
        self._log(f'已加载历史记录: {len(self._saved_videos)} 条')

    def _log(self, msg):
        if self._debug:
            print(f'[hscka] {msg}')

    def _load_saved_data(self):
        """从JSON文件加载已保存的视频记录"""
        if os.path.exists(self._saved_data_file):
            try:
                with open(self._saved_data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception as e:
                self._log(f'加载历史数据失败: {e}')
        return {}

    def _save_data(self):
        """保存视频记录到JSON文件"""
        try:
            with open(self._saved_data_file, 'w', encoding='utf-8') as f:
                json.dump(self._saved_videos, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self._log(f'保存历史数据失败: {e}')

    def getName(self): return 'hscka'
    def isVideoFormat(self, url):
        if not url: return False
        return '.m3u8' in url or '.mp4' in url or '.ts' in url or url.startswith('magnet:')
    def manualVideoCheck(self): return False
    def destroy(self): pass

    def localProxy(self, param):
        return [404, 'text/plain', '']

    def init(self, extend=''):
        self.session.verify = False
        self.session.headers.update(self._get_headers())
        _start_proxy()
        text = self._fetch(self.host)
        if text:
            self._load_categories(text)

    def _get_headers(self, referer=None):
        """获取完整的请求头，模拟真实浏览器"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        }
        if referer:
            headers['Referer'] = referer
        else:
            headers['Referer'] = self.host + '/'
        return headers

    def _proxy_url(self, url):
        if not url: return ''
        if url.startswith('http://127.0.0.1'):
            return url
        return f'http://127.0.0.1:{_proxy_port}/{quote(url, safe="")}'

    def _fetch(self, url, referer=None, retries=3):
        """增强版请求，支持重试和随机延迟"""
        for attempt in range(retries):
            try:
                if referer is None:
                    referer = self.host + '/'
                headers = self._get_headers(referer)
                if attempt > 0:
                    time.sleep(random.uniform(0.5, 1.5))
                r = self.session.get(url, headers=headers, timeout=30, verify=False)
                r.encoding = 'utf-8'
                if r.status_code == 200:
                    return r.text
                elif r.status_code in [403, 429, 503]:
                    self._log(f'请求被拦截 [{r.status_code}]，第{attempt+1}次重试: {url}')
                    continue
                else:
                    self._log(f'请求失败 [{r.status_code}]: {url}')
                    return ''
            except requests.exceptions.Timeout:
                self._log(f'请求超时，第{attempt+1}次重试: {url}')
            except Exception as e:
                self._log(f'请求异常 [{e}]，第{attempt+1}次重试: {url}')
        return ''

    @staticmethod
    def _decode_b64(encoded_str):
        try:
            raw = base64.b64decode(encoded_str)
            return raw.decode('utf-8')
        except:
            return encoded_str

    # ----- 分类加载 -----
    def _load_categories(self, text):
        if not text:
            return []
        cats = []
        seen = set()
        pattern = r'href="(/list/\d+-\d+\.html)"[^>]*>\s*<script[^>]*>document\.write\(d\(\'([A-Za-z0-9+/=]+)\'\)\);</script>'
        for path, b64_name in re.findall(pattern, text, re.S):
            name = self._decode_b64(b64_name)
            name = re.sub(r'<[^>]+>', '', name).strip()
            if not name or name in seen:
                continue
            seen.add(name)
            tid = path.split('/')[-1].split('-')[0]
            cats.append({'type_id': tid, 'type_name': name})
        self._categories_cache = cats
        return cats

    def _get_category_name(self, tid):
        for cat in self._categories_cache or []:
            if cat['type_id'] == tid:
                return cat['type_name']
        return tid

    # ----- 列表解析 -----
    def _parse_list(self, html):
        items = []
        cards = re.findall(r'<div class="item item-post">\s*(.*?)\s*</div>', html, re.S)
        for card in cards:
            a_match = re.search(r'<a href="([^"]+)"', card)
            if not a_match:
                continue
            href = a_match.group(1)

            img_match = re.search(r'<img[^>]+(?:data-original|src)="([^"]+)"', card)
            pic = img_match.group(1) if img_match else ''

            title = ''
            title_match = re.search(r'<h3 class="name">(.*?)</h3>', card, re.S)
            if title_match:
                title_raw = title_match.group(1)
                b64 = re.search(r"document\.write\(d\('([A-Za-z0-9+/=]+)'\)\)", title_raw)
                if b64:
                    title = self._decode_b64(b64.group(1))
                    title = re.sub(r'<[^>]+>', '', title).strip()
                else:
                    title = re.sub(r'<[^>]+>', '', title_raw).strip()

            if href.startswith('magnet:'):
                items.append({
                    'vod_id': href,
                    'vod_name': title or '磁力资源',
                    'vod_pic': self._proxy_url(pic),
                    'vod_remarks': '磁力',
                })
            elif '/torrent/' in href:
                vid = href.split('/')[-1].replace('.html', '')
                items.append({
                    'vod_id': vid,
                    'vod_name': title,
                    'vod_pic': self._proxy_url(pic),
                    'vod_remarks': '磁力',
                })
            elif '/video/' in href:
                vid = href.split('/')[-1].replace('.html', '')
                items.append({
                    'vod_id': vid,
                    'vod_name': title,
                    'vod_pic': self._proxy_url(pic),
                    'vod_remarks': '',
                })
        return items

    def _get_list(self, tid, page):
        url = f'{self.host}/list/{tid}-{page}.html'
        html = self._fetch(url, referer=f'{self.host}/list/{tid}-1.html')
        if not html:
            return []
        return self._parse_list(html)

    # ----- 首页 -----
    def homeContent(self, filter):
        try:
            text = self._fetch(self.host)
            if text:
                self._load_categories(text)
            cats = self._categories_cache or []
            items = []
            if cats:
                items = self._get_list(cats[0]['type_id'], 1)
            return {
                'class': cats,
                'filters': {},
                'type': '影视',
                'list': items,
                'page': 1,
                'pagecount': 1,
                'limit': len(items),
                'total': len(items)
            }
        except Exception as e:
            self._log(f'homeContent 异常: {e}')
            return {
                'class': [], 'filters': {}, 'type': '影视',
                'list': [], 'page': 1, 'pagecount': 1, 'limit': 0, 'total': 0
            }

    def homeVideoContent(self):
        if self._categories_cache:
            return {'list': self._get_list(self._categories_cache[0]['type_id'], 1)}
        return {'list': []}

    # ----- 分类内容 -----
    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg) if pg else 1
            items = self._get_list(tid, page)
            total_page = page + 1
            if page == 1:
                html = self._fetch(f'{self.host}/list/{tid}-1.html')
                if html:
                    pages = re.findall(r'/list/\d+-(\d+)\.html', html)
                    if pages:
                        total_page = max(int(p) for p in pages)

            cat_name = self._get_category_name(tid)
            # 后台导出到M3U和TXT（持久化去重）
            threading.Thread(target=self._export_page_to_files, args=(items, cat_name), daemon=True).start()

            return {
                'list': items, 'page': page, 'pagecount': total_page,
                'limit': len(items), 'total': total_page * len(items)
            }
        except Exception as e:
            self._log(f'categoryContent 异常: {e}')
            return {
                'list': [], 'page': int(pg) if pg else 1,
                'pagecount': 1, 'limit': 0, 'total': 0
            }

    # ===== 文件导出（M3U + 磁力TXT，持久化去重） =====
    def _export_page_to_files(self, items, cat_name):
        """导出当前页视频到M3U和TXT，支持跨会话去重和替换"""
        if not items:
            return
        
        safe_name = re.sub(r'[\\/:*?"<>|]', '_', cat_name)
        updated = False
        
        # 遍历当前页item，更新持久化数据
        for item in items:
            vid = item['vod_id']
            play_url = self._resolve_play_url(item)
            if not play_url:
                continue
            
            is_magnet = vid.startswith('magnet:')
            existing = self._saved_videos.get(vid)
            
            # 如果已存在且URL完全相同 -> 忽略（跳过）
            if existing and existing.get('url') == play_url:
                continue
            
            # 否则：新增或替换（更新）
            self._saved_videos[vid] = {
                'name': item['vod_name'],
                'url': play_url,
                'pic': item.get('vod_pic', ''),
                'cat': cat_name,
                'type': 'magnet' if is_magnet else 'video',
                'time': datetime.now().isoformat()
            }
            updated = True
            action = '新增' if not existing else '替换'
            self._log(f'{action}记录: {item["vod_name"][:30]}... ({vid[:20]}...)')
        
        if not updated:
            self._log(f'分类[{cat_name}]无新数据，跳过写入')
            return
        
        # 保存JSON索引
        self._save_data()
        
        with self._m3u_lock:
            # ---- 重写该分类的M3U文件（只含非磁力视频）----
            m3u_file = os.path.join(self._data_dir, f'{safe_name}.m3u')
            with open(m3u_file, 'w', encoding='utf-8') as f:
                f.write('#EXTM3U\n')
                count = 0
                for vid, data in self._saved_videos.items():
                    if data.get('cat') == cat_name and data.get('type') != 'magnet':
                        f.write(f'#EXTINF:-1 tvg-logo="{data["pic"]}" group-title="{cat_name}",{data["name"]}\n')
                        f.write(f'{data["url"]}\n')
                        count += 1
                self._log(f'已重写M3U: {m3u_file} ({count}条)')
            
            # ---- 重写磁力链接TXT文件（汇总所有分类的磁力）----
            txt_file = os.path.join(self._data_dir, '磁力链接.txt')
            with open(txt_file, 'w', encoding='utf-8') as f:
                f.write('# ==========================================\n')
                f.write('# 磁力链接汇总文件\n')
                f.write(f'# 生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
                f.write('# 提示: 请使用支持云播放/离线下载的播放器或迅雷打开\n')
                f.write('# ==========================================\n\n')
                
                mag_count = 0
                for vid, data in self._saved_videos.items():
                    if data.get('type') == 'magnet':
                        f.write(f'【{data["name"]}】\n')
                        f.write(f'{data["url"]}\n')
                        f.write(f'# 分类: {data.get("cat", "未知")} | 保存时间: {data.get("time", "未知")}\n')
                        f.write('-' * 50 + '\n')
                        mag_count += 1
                self._log(f'已重写磁力TXT: {txt_file} ({mag_count}条)')

    def _resolve_play_url(self, item):
        vid = item['vod_id']
        if vid.startswith('magnet:'):
            return vid
        detail = self._fetch_detail(vid)
        if not detail or not detail.get('vod_play_url'):
            return ''
        first_line = detail['vod_play_url'].split('#')[0]
        if '$' in first_line:
            return first_line.split('$', 1)[1]
        return first_line

    # ----- 详情 (核心修复：移除'在线播放'，统一用'备用播放') -----
    def _fetch_detail(self, vid):
        if vid.startswith('magnet:'):
            return {'vod_play_url': f'磁力${vid}'}

        url_patterns = [
            f'{self.host}/video/{vid}.html',
            f'{self.host}/torrent/{vid}.html',
            f'{self.host}/v/{vid}.html',
            f'{self.host}/movie/{vid}.html',
            f'{self.host}/play/{vid}.html',
        ]
        
        for url in url_patterns:
            self._log(f'尝试获取详情: {url}')
            html = self._fetch(url, referer=self.host)
            if html and ('video' in html or 'play' in html or 'magnet' in html or 'm3u8' in html or 'mp4' in html):
                result = self._parse_detail(html, vid, url)
                if result and result.get('vod_play_url'):
                    self._log(f'成功解析详情: {vid}')
                    return result
        
        self._log(f'无法获取详情: {vid}')
        return None

    def _parse_detail(self, html, vid, base_url):
        """增强版详情解析：移除'在线播放'，统一为'备用播放'，增强各类链接提取"""
        title = ''
        m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
        if m:
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if not title:
            m = re.search(r'<title>([^<]+)</title>', html)
            if m:
                title = m.group(1).strip()

        cover = ''
        m = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', html)
        if m:
            cover = m.group(1)
        if not cover:
            m = re.search(r'<img[^>]*class="thumb"[^>]*src="([^"]+)"', html)
            if m:
                cover = m.group(1)
        if not cover:
            m = re.search(r'<img[^>]*class="poster"[^>]*src="([^"]+)"', html)
            if m:
                cover = m.group(1)

        play_urls = []
        seen_urls = set()  # 用于去重
        
        def _add_url(label, url):
            """辅助函数：添加播放链接，自动去重"""
            if url in seen_urls:
                return False
            seen_urls.add(url)
            play_urls.append(f'{label}${url}')
            self._log(f'解析到[{label}]: {url[:80]}...')
            return True

        # 1. 磁力链接
        for mag in set(re.findall(r'magnet:\?xt=urn:btih:[A-Za-z0-9]+[^\s"\'<>]*', html)):
            _add_url('磁力', mag)

        # 3. 备用播放：相对路径的 play.php
        for link in set(re.findall(r'href=["\']?(/[^"\'<>\s]*play\.php[^"\'<>\s]*)', html)):
            full_link = urljoin(base_url, link)
            _add_url('备用播放', full_link)

        # 4. 备用播放：引号中的 play.php（更宽松的匹配）
        for link in set(re.findall(r'["\']([^"\']*play\.php[^"\']*)["\']', html)):
            if link.startswith('http'):
                _add_url('备用播放', link)

        # 5. iframe（支持单双引号、data-src）
        iframe_pattern = r'<iframe[^>]+(?:src|data-src)=["\']([^"\']+)["\']'
        for src in set(re.findall(iframe_pattern, html)):
            if any(k in src for k in ['play.php', 'm3u8', 'mp4', 'embed', 'player']):
                full_src = src if src.startswith('http') else urljoin(base_url, src)
                _add_url('外链', full_src)

        # 6. 媒体直链（支持带参数）
        for media in set(re.findall(r'https?://[^\s"\'<>]+\.(?:m3u8|mp4|flv|mkv|ts)(?:\?[^\s"\'<>]*)?', html)):
            _add_url('直链', media)

        # 7. 从 script 标签中提取 JSON/变量中的播放链接
        script_tags = re.findall(r'<script[^>]*>(.*?)</script>', html, re.S)
        for script in script_tags:
            # 提取 JSON 中的 url/src/playUrl/videoUrl 字段
            for match in re.findall(r'["\'](?:url|src|playUrl|videoUrl|file|source)["\']\s*:\s*["\']([^"\']+)["\']', script):
                if any(ext in match for ext in ['.m3u8', '.mp4', 'play.php', 'magnet:', '.flv', '.ts']):
                    full_match = match if match.startswith('http') else urljoin(base_url, match)
                    _add_url('JS解析', full_match)
            
            # 提取 base64 编码的链接
            for b64 in re.findall(r'["\']([A-Za-z0-9+/]{20,}={0,2})["\']', script):
                try:
                    decoded = base64.b64decode(b64).decode('utf-8')
                    if decoded.startswith('http') and any(ext in decoded for ext in ['.m3u8', '.mp4', 'play.php', '.flv']):
                        _add_url('Base64解码', decoded)
                except:
                    pass
            
            # 提取 AES 加密的数据
            aes_pattern = r'["\']([A-Za-z0-9+/]{50,}={0,2})["\']'
            for aes_b64 in re.findall(aes_pattern, script):
                try:
                    raw = base64.b64decode(aes_b64)
                    if len(raw) % 16 == 0 and len(raw) >= 16:
                        common_keys = [
                            (b'1234567890123456', b'1234567890123456'),
                            (b'0123456789abcdef', b'0123456789abcdef'),
                        ]
                        for key, iv in common_keys:
                            try:
                                decrypted = _aes_cbc_decrypt(raw, key, iv)
                                dec_str = decrypted.decode('utf-8')
                                if dec_str.startswith('http') and any(ext in dec_str for ext in ['.m3u8', '.mp4', 'play.php']):
                                    _add_url('AES解码', dec_str)
                                    break
                            except:
                                continue
                except:
                    pass

        # 8. 从 video/source 标签提取
        for media in set(re.findall(r'<(?:video|source)[^>]+src=["\']([^"\']+)["\']', html)):
            if any(ext in media for ext in ['.m3u8', '.mp4', '.flv', '.ts']):
                full_media = media if media.startswith('http') else urljoin(base_url, media)
                _add_url('HTML5', full_media)

        # 9. 从 a 标签的 data-url / data-src / data-link 提取
        for media in set(re.findall(r'<a[^>]+(?:data-url|data-src|data-link)=["\']([^"\']+)["\']', html)):
            if any(ext in media for ext in ['.m3u8', '.mp4', 'play.php', 'magnet:']):
                full_media = media if media.startswith('http') else urljoin(base_url, media)
                _add_url('数据属性', full_media)

        # 10. 从 onclick 属性提取
        for onclick in set(re.findall(r'onclick=["\'][^"\']*(https?://[^"\'<>]+)["\']', html)):
            if any(ext in onclick for ext in ['.m3u8', '.mp4', 'play.php']):
                _add_url('点击播放', onclick)

        if not play_urls:
            self._log(f'未找到任何播放链接: {vid}')
            return None

        self._log(f'共解析到 {len(play_urls)} 个播放源')
        
        # 构建 TVBox 标准格式的播放数据
        sources = []
        urls = []
        for i, pu in enumerate(play_urls):
            if '$' in pu:
                source_name, url = pu.split('$', 1)
            else:
                source_name = f'线路{i+1}'
                url = pu
            sources.append(source_name)
            urls.append(f'{source_name}${url}')

        return {
            'vod_id': vid,
            'vod_name': title or vid,
            'vod_pic': self._proxy_url(cover) if cover else '',
            'vod_play_from': '$$$'.join(sources),
            'vod_play_url': '#'.join(urls),
            'vod_content': title or '',
        }

    def detailContent(self, ids):
        try:
            vid = str(ids[0] if isinstance(ids, list) else ids)
            if vid.startswith('magnet:'):
                return {
                    'list': [{
                        'vod_id': vid,
                        'vod_name': '磁力资源',
                        'vod_pic': '',
                        'vod_play_from': '磁力',
                        'vod_play_url': f'磁力${vid}',
                        'vod_content': '磁力链接（建议配合云播放/离线下载使用）',
                    }]
                }
            detail = self._fetch_detail(vid)
            if not detail:
                self._log(f'detailContent 获取详情失败: {vid}')
                return {'list': []}
            return {'list': [detail]}
        except Exception as e:
            self._log(f'detailContent 异常: {e}')
            return {'list': []}

    # ----- 播放 -----
    def playerContent(self, flag, id, vipFlags=None):
        try:
            if id.startswith('magnet:'):
                return {'parse': 0, 'url': id, 'header': {}}

            # 外部播放链接，直接返回让播放器请求
            if 'play.php' in id or 'm3u8' in id or 'mp4' in id or 'flv' in id or 'ts' in id:
                return {
                    'parse': 0,
                    'url': id,
                    'header': {
                        'Referer': self.host,
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Origin': self.host,
                    }
                }

            return {
                'parse': 0,
                'url': id,
                'header': {
                    'Referer': self.host,
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                }
            }
        except Exception as e:
            self._log(f'playerContent 异常: {e}')
            return {'parse': 0, 'url': '', 'header': {}}

    # ----- 搜索 -----
    def searchContent(self, key, quick, pg='1'):
        try:
            page = int(pg) if pg else 1
            # 视频搜索
            url = f'{self.host}/search.php?content={quote(key)}&type=1&page={page}'
            html = self._fetch(url, referer=self.host)
            items = self._parse_list(html) if html else []
            if not items:
                # 磁力搜索
                url = f'{self.host}/search.php?content={quote(key)}&type=2&page={page}'
                html = self._fetch(url, referer=self.host)
                items = self._parse_list(html) if html else []
            return {
                'list': items, 'page': page, 'pagecount': page + 1,
                'limit': len(items), 'total': page * len(items)
            }
        except Exception as e:
            self._log(f'searchContent 异常: {e}')
            return {'list': [], 'page': int(pg) if pg else 1, 'pagecount': 1, 'limit': 0, 'total': 0}