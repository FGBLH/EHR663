# -*- coding: utf-8 -*-
import sys
import re
import json
import base64
import requests
from urllib.parse import quote

try:
    from base.spider import Spider
except ImportError:
    class Spider:
        pass

HOST = 'https://www.aeete.com'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
CATEGORIES = [
    {"type_id": "neidi", "type_name": "国产剧"},
    {"type_id": "oumei", "type_name": "美剧"},
    {"type_id": "hanju", "type_name": "韩剧"},
    {"type_id": "riju", "type_name": "日剧"},
    {"type_id": "yataiju", "type_name": "泰剧"},
    {"type_id": "wangju", "type_name": "网剧"},
    {"type_id": "taiju", "type_name": "台剧"},
    {"type_id": "tvbgj", "type_name": "港剧"},
    {"type_id": "yingju", "type_name": "英剧"},
    {"type_id": "waiju", "type_name": "外剧"},
    {"type_id": "duanju", "type_name": "短剧"},
]


class Spider(Spider):
    def init(self, extend=None):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': UA})

    def _s(self):
        if not hasattr(self, 'session'):
            self.init()
        return self.session

    def _get(self, url):
        for _ in range(3):
            try:
                r = self._s().get(url, timeout=10)
                if r.status_code == 200:
                    r.encoding = 'utf-8'
                    return r
            except Exception:
                pass
        return None

    def _pagecount(self, n):
        return max(1, -(-n // 12))

    def _items(self, t):
        rows = []
        for m in re.finditer(r'<li[^>]*data-href="(/Tv/[a-z]+/[a-z0-9_]+/)"[^>]*>.*?<a href="[^"]*"[^>]*class="pic"[^>]*><img src="(https?://[^"]+)"[^>]*alt="([^"]+)"[^>]*>(?:<button class="hdtag">([^<]+)</button>)?.*?<h2 class="title"><a href="[^"]*"[^>]*>([^<]+)</a>', t, re.DOTALL):
            rows.append({'vod_id': m.group(1), 'vod_name': m.group(5).strip(), 'vod_pic': m.group(2), 'vod_remarks': (m.group(4) or '').strip()})
        return rows

    def homeContent(self, filter=False):
        return {'class': CATEGORIES}

    def homeVideoContent(self):
        r = self._get(HOST + '/Tv/index.html')
        if not r:
            return {'list': []}
        return {'list': self._items(r.text)[:20]}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        try:
            pg = int(pg or 1)
        except Exception:
            pg = 1
        slug = str(tid)
        url = HOST + '/Tv/' + slug + ('/index%d.html' % pg if pg > 1 else '/index.html')
        r = self._get(url)
        if not r:
            return {'list': [], 'page': pg, 'pagecount': 1}
        rows = self._items(r.text)
        total = self._pagecount(len(rows))
        pm = re.findall(r'/index(\d+)\.html', r.text)
        if pm:
            total = max(total, max(int(x) for x in pm))
        return {'list': rows, 'page': pg, 'pagecount': total}

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
        if not vid.startswith('/Tv/'):
            vid = '/Tv/' + vid.strip('/') + '/'
        r = self._get(HOST + vid)
        if not r:
            return {'list': []}
        t = r.text
        title = re.search(r'<a href="https?://[^"]+\.(?:jpg|jpeg|png|webp)" title="([^"]+)"', t)
        pic = re.search(r'<div class="cover"><a href="(https?://[^"]+)"', t)
        name = title.group(1) if title else ''
        if not name:
            tm = re.search(r'《([^》]+)》', t)
            name = tm.group(1) if tm else ''
        vod = {
            'vod_id': vid,
            'vod_name': name,
            'vod_pic': pic.group(1) if pic else '',
            'vod_remarks': '',
            'vod_content': '',
        }
        lines = re.findall(r'<h2[^>]*>.*?《[^》]+》([^：<]+)线路', t)
        li_set = re.findall(r'<h2[^>]*>.*?<i class="icon-film"></i>([^<]+)', t)
        line_names = [re.sub(r'[《『][^》』]+[》』]|线路|线$|：|:', '', x.strip()).strip() for x in li_set]
        line_names = [x for x in line_names if x]
        groups = re.findall(r'<li id="(\d+)"><a[^>]+href="([^"]*play-(\d+)-(\d+)\.html)"[^>]*>([^<]+)</a>', t)
        by_line = {}
        for li_id, href, line, idx, label in groups:
            by_line.setdefault(line, []).append((int(idx), href, label.strip()))
        plays = []
        froms = []
        seen = {}
        for line in sorted(by_line.keys(), key=int):
            eps = sorted(by_line[line])
            ln = '线路%s' % (int(line) + 1)
            if int(line) < len(line_names) and line_names[int(line)]:
                ln = line_names[int(line)]
            if ln in seen:
                seen[ln] += 1
                ln = '%s%d' % (ln, seen[ln])
            else:
                seen[ln] = 1
            froms.append(ln)
            plays.append('#'.join('%s$%s' % (e[2], HOST + e[1]) for e in eps))
        vod['vod_play_from'] = '$$$'.join(froms)
        vod['vod_play_url'] = '$$$'.join(plays)
        return {'list': [vod]}

    def searchContent(self, key, quick=False):
        r = self._get(HOST + '/auete4so.php?searchword=' + quote(str(key)))
        if not r or '系统安全验证' in r.text:
            return {'list': []}
        return {'list': self._items(r.text)}

    def playerContent(self, flag, pid, vipFlags=None):
        pid = str(pid)
        if '$' in pid:
            pid = pid.rsplit('$', 1)[1]
        r = self._get(pid)
        if not r:
            return {'parse': 0, 'url': pid, 'header': {'User-Agent': UA}}
        m = re.search(r'var now=base64decode\("([^"]+)"\)', r.text)
        if not m:
            m = re.search(r'var now=base64decode\(\'([^\']+)\'\)', r.text)
        if not m:
            return {'parse': 0, 'url': pid, 'header': {'User-Agent': UA}}
        try:
            u = base64.b64decode(m.group(1)).decode('utf-8', 'ignore')
        except Exception:
            u = pid
        if not u.startswith('http'):
            u = pid
        return {'parse': 0, 'url': u, 'header': {'User-Agent': UA, 'Referer': HOST + '/'}}

    def localProxy(self, param):
        return [404, 'text/plain', '']