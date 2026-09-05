# coding=utf-8
#!/usr/bin/env python3
"""TVBox / 影视仓 Python 源: 悦听吧有声书。"""

import base64
import hashlib
import html as html_lib
import json
import random
import re
import sys
import time
from urllib.parse import unquote, urljoin

import requests

sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider(object):
        pass


class Spider(BaseSpider):
    site = 'http://www.yuetingba.cn'
    _assl_marker = 'xMiP5W1DHBxC5PwQ5oj5QfRn0tsT5UBk'
    _assl_key = 'le95G3hnFDJsBE+1/v9eYw=='
    _assl_iv = 'IvswQFEUdKYf+d1wKpYLTg=='

    def __init__(self):
        try:
            super().__init__()
        except TypeError:
            pass
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ),
            'Referer': self.site + '/',
        })
        self.cateManual = {
            '玄幻': '1', '都市': '4', '历史': '2', '名著': '6',
            '女频': '7', '科幻': '5', '武侠': '3', '评书': 'a', '社科': '8',
        }
        self._runtime_cache = {}

    def init(self, extend=''):
        pass

    def getName(self):
        return '悦听吧'

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def homeContent(self, filter):
        return {
            'class': [
                {'type_id': value, 'type_name': name}
                for name, value in self.cateManual.items()
            ],
            'filters': {}, 'list': [], 'parse': 0, 'jx': 0,
        }

    def homeVideoContent(self):
        result = {'list': [], 'parse': 0, 'jx': 0}
        try:
            result['list'] = self._parse_books(self._get('/').text)[:30]
        except Exception as error:
            print('homeVideoContent error: %s' % error)
        return result

    def categoryContent(self, tid, pg, filter, extend):
        page = self._page_number(pg)
        result = {'list': [], 'parse': 0, 'jx': 0, 'page': page}
        try:
            page_html = self._get('/book/%s/%s' % (tid, page)).text
            result['list'] = self._parse_books(page_html)
            total_match = re.search(r'共\s*(\d+)\s*条', page_html)
            total = int(total_match.group(1)) if total_match else len(result['list'])
            result['total'] = total
            result['limit'] = 10
            result['pagecount'] = max(page, (total + 9) // 10)
        except Exception as error:
            print('categoryContent error: %s' % error)
            result.update({'total': 0, 'limit': 10, 'pagecount': page})
        return result

    def detailContent(self, ids):
        result = {'list': [], 'parse': 0, 'jx': 0}
        book_id = ids[0] if ids else ''
        if not book_id:
            return result
        book_id = self._book_id(book_id)
        try:
            first_html = self._get('/book/detail/%s/0' % book_id).text
            title = self._first_text(first_html, r'<h1[^>]*>(.*?)</h1>')
            if not title:
                title = self._first_text(first_html, r'book-detail-title[^>]*>(.*?)</h2>')
            pic_match = re.search(
                r'<div class="books-detail-img">.*?<img[^>]+src=["\']([^"\']+)',
                first_html, re.S,
            )
            pic = urljoin(self.site, pic_match.group(1)) if pic_match else ''
            author = self._field(first_html, '作\s*者')
            category = self._field(first_html, '分\s*类')
            speaker = self._field(first_html, '演\s*播')
            status = self._field(first_html, '状\s*态')
            count = self._field(first_html, '集\s*数')
            desc_match = re.search(
                r'内容简介：</h4>.*?text-desc-content[^>]*>\s*<p>(.*?)</p>',
                first_html, re.S,
            )
            desc = self._clean(desc_match.group(1)) if desc_match else ''

            offsets = sorted({
                int(value) for value in re.findall(
                    r'/book/detail/%s/(\d+)' % re.escape(book_id), first_html
                )
            }) or [0]
            episodes = self._parse_episodes(first_html)
            seen = {episode_id for _, episode_id in episodes}
            for offset in offsets:
                if offset == 0:
                    continue
                page_html = self._get('/book/detail/%s/%s' % (book_id, offset)).text
                for episode in self._parse_episodes(page_html):
                    if episode[1] not in seen:
                        episodes.append(episode)
                        seen.add(episode[1])

            vod = {
                'vod_id': book_id,
                'vod_name': title,
                'vod_pic': pic,
                'type_name': category,
                'vod_year': '',
                'vod_area': '',
                'vod_remarks': ('%s · %s集' % (status, count)).strip(' ·'),
                'vod_actor': speaker,
                'vod_director': author,
                'vod_content': desc,
                'vod_play_from': '悦听吧',
                'vod_play_url': '#'.join(
                    '%s$%s' % (self._play_name(name), episode_id)
                    for name, episode_id in episodes
                ),
            }
            result['list'].append(vod)
        except Exception as error:
            print('detailContent error: %s' % error)
        return result

    def playerContent(self, flag, id, vipFlags):
        try:
            audio_url = self._resolve_audio(id)
            return {
                'parse': 0,
                'url': audio_url,
                'jx': 0,
                'header': {
                    'User-Agent': self.session.headers['User-Agent'],
                    'Referer': self.site + '/',
                },
            }
        except Exception as error:
            print('playerContent error: %s' % error)
            return {'parse': 1, 'url': id, 'jx': 0, 'header': {}}

    def searchContent(self, key, quick, pg='1'):
        page = self._page_number(pg)
        result = {'list': [], 'parse': 0, 'jx': 0, 'page': page}
        try:
            response = self._get('/Search', params={
                'type': '1', 'name': key, 'pageIndex': page,
            })
            result['list'] = self._parse_books(response.text)
            total_match = re.search(r'共\s*(\d+)\s*条', response.text)
            total = int(total_match.group(1)) if total_match else len(result['list'])
            result.update({
                'total': total,
                'limit': 10,
                'pagecount': max(page, (total + 9) // 10),
            })
        except Exception as error:
            print('searchContent error: %s' % error)
            result.update({'total': 0, 'limit': 10, 'pagecount': page})
        return result

    def localProxy(self, params):
        return [200, 'audio/mpeg', {}, '']

    def _get(self, path, **kwargs):
        url = path if path.startswith('http') else urljoin(self.site + '/', path.lstrip('/'))
        response = self.session.get(url, timeout=20, **kwargs)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or 'utf-8'
        return response

    def _parse_books(self, page_html):
        videos = []
        seen = set()
        pattern = re.compile(
            r'<div[^>]+class="[^"]*section-box-list-item[^"]*"[^>]*>(.*?)'
            r'(?=<div[^>]+class="[^"]*section-box-list-item|</section>|<div class="pagelist")',
            re.S,
        )
        for block in pattern.findall(page_html):
            link = re.search(r'href=["\']/book/detail/([^/"\']+)/\d+["\']', block)
            title = re.search(
                r'box-list-item-text-title[^>]*>\s*<a[^>]*>(.*?)</a>', block, re.S
            )
            image = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', block)
            if not link or not title:
                continue
            book_id = link.group(1)
            if book_id in seen:
                continue
            seen.add(book_id)
            author_speaker = [self._clean(value) for value in re.findall(
                r'<span[^>]+title=["\']([^"\']+)["\']', block
            )]
            remark = ' / '.join(author_speaker[:2])
            videos.append({
                'vod_id': book_id,
                'vod_name': self._clean(title.group(1)),
                'vod_pic': urljoin(self.site, image.group(1)) if image else '',
                'vod_remarks': remark,
            })
        return videos

    def _parse_episodes(self, page_html):
        episodes = []
        for episode_id, block in re.findall(
            r'<div id="item_([0-9a-f-]{36})" class="ting-list-content-item">(.*?)</div>\s*</div>',
            page_html, re.S | re.I,
        ):
            titles = re.findall(r'<a[^>]+title="([^"]+)"', block, re.S)
            name = self._clean(titles[-1]) if titles else episode_id
            episodes.append((name, episode_id))
        return episodes

    def _resolve_audio(self, episode_id):
        data = self._get(
            '/api/app/docs-listen/%s/ting-with-efi' % episode_id
        ).json()
        book_id = data['bookId']
        ting_no = int(data.get('tingNo') or 1)
        offset = ((ting_no - 1) // 200) * 200
        runtime = self._book_runtime(book_id, offset)

        plain_id = data['id'].replace('-', '')
        compact_time = re.sub(r'[-:T. ]', '', data['creationTime']).ljust(20, '0')
        key = bytes(
            (ord(plain_id[index]) + int(compact_time[index % 20])) & 0xff
            for index in range(len(plain_id))
        )
        iv = bytes(
            (ord(plain_id[index]) + int(compact_time[index - 1])) & 0xff
            for index in range(20, 4, -1)
        )
        source_path = self._aes_decrypt(data['efi'], key, iv).decode('utf-8').strip()
        filename = unquote(source_path.rstrip('/').split('/')[-1])
        server = self._pick_server(runtime['servers'], book_id)

        path = source_path
        if '_p' in server['Name']:
            path = '/%s_%s/%s' % (runtime['py'], book_id, filename)
        elif '_b' in server['Name']:
            path = '/myfiles/host/listen/booksdir/%s_%s/%s' % (
                runtime['py'], book_id, filename,
            )

        expires = int(time.time()) + 600
        signature = hashlib.md5(
            ('%s|%s|%s' % (filename, expires, self._assl_marker)).encode('utf-8')
        ).hexdigest()
        host = '%s://%s:%s' % (server['Scheme'], server['Value'], server['Port'])
        return '%s%s?token=%s&expire=%s' % (host, path, signature, expires)

    def _book_runtime(self, book_id, offset):
        cached = self._runtime_cache.get(book_id)
        if cached and time.time() - cached['cached_at'] < 1800:
            return cached
        page_html = self._get('/book/detail/%s/%s' % (book_id, offset)).text
        assl = self._js_var(page_html, 'assl').replace(self._assl_marker, '')
        servers = json.loads(self._aes_decrypt(
            assl, base64.b64decode(self._assl_key), base64.b64decode(self._assl_iv)
        ).decode('utf-8'))
        runtime = {
            'servers': servers,
            'py': self._js_var(page_html, 'py'),
            'cached_at': time.time(),
        }
        self._runtime_cache[book_id] = runtime
        return runtime

    @staticmethod
    def _pick_server(servers, book_id):
        available = [
            item for item in servers
            if str(item.get('AsType')) == '1' and item.get('Type') == 'A'
        ]
        group = book_id.split('-')[4]
        dedicated = [
            item for item in available
            if item.get('BookIds') and group in item['BookIds']
        ]
        if dedicated:
            available = dedicated
        else:
            available = [
                item for item in available
                if int(item.get('Ratio') or 0) > 0
                and not str(item.get('BookIds') or '').strip()
            ]
        if not available:
            raise ValueError('没有可用的音频服务器')
        weights = [max(0, int(item.get('Ratio') or 0)) for item in available]
        return random.choices(available, weights=weights or None, k=1)[0]

    @staticmethod
    def _aes_decrypt(cipher_text, key, iv):
        encrypted = base64.b64decode(re.sub(r'\s+', '', cipher_text))
        try:
            from Crypto.Cipher import AES
            padded = AES.new(key, AES.MODE_CBC, iv).decrypt(encrypted)
        except ImportError:
            try:
                from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            except ImportError:
                raise RuntimeError('需要 pycryptodome 或 cryptography 才能解析音频')
            decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
            padded = decryptor.update(encrypted) + decryptor.finalize()
        padding_size = padded[-1]
        if padding_size < 1 or padding_size > 16:
            raise ValueError('AES 填充无效')
        return padded[:-padding_size]

    @staticmethod
    def _js_var(page_html, name):
        match = re.search(
            r'\b(?:var|let|const)\s+%s\s*=\s*["\']([^"\']*)["\']' % re.escape(name),
            page_html,
        )
        if not match:
            raise ValueError('页面缺少参数: %s' % name)
        return html_lib.unescape(match.group(1))

    @staticmethod
    def _field(page_html, label):
        match = re.search(
            r'text-desc-title[^>]*>\s*%s：?\s*</span>\s*'
            r'<span[^>]*text-desc-content[^>]*>(.*?)</span>' % label,
            page_html, re.S,
        )
        return Spider._clean(match.group(1)) if match else ''

    @staticmethod
    def _first_text(page_html, pattern):
        match = re.search(pattern, page_html, re.S)
        return Spider._clean(match.group(1)) if match else ''

    @staticmethod
    def _clean(value):
        value = re.sub(r'<br\s*/?>', '\n', value or '', flags=re.I)
        value = re.sub(r'<[^>]+>', '', value)
        value = html_lib.unescape(value)
        return re.sub(r'[ \t\r\f\v]+', ' ', value).strip()

    @staticmethod
    def _page_number(value):
        try:
            return max(1, int(value or 1))
        except (TypeError, ValueError):
            return 1

    @staticmethod
    def _book_id(value):
        match = re.search(r'/book/detail/([^/]+)/', value or '')
        return match.group(1) if match else value

    @staticmethod
    def _play_name(name):
        return (name or '').replace('$', '￥').replace('#', '﹟')
