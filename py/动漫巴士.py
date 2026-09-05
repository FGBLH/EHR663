# -*- coding: utf-8 -*-


import sys
import re
import json
import time
from urllib.parse import quote, unquote, urljoin

import requests as rq

sys.path.append('..')
try:
    from base.spider import Spider
except ImportError:
    class Spider:
        def fetch(self, url, headers=None, **kw):
            kw.pop('timeout', None)
            r = rq.get(url, headers=headers, timeout=15, **kw)
            r.encoding = 'utf-8'
            return r

HOST = "https://dm845.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

FILTER_SLOT = {
    "class": 3,
    "area": 1,
    "by": 2,
    "lang": 4,
    "letter": 5,
    "year": 11,
}
GROUP_KEY = {
    "类型": "class",
    "剧情": "class",
    "地区": "area",
    "年代": "year",
    "年份": "year",
    "排序": "by",
    "语言": "lang",
    "字母": "letter",
}
SORT_VALUE = {"按时间": "time", "按人气": "hits", "按评分": "score"}


class Spider(Spider):

    def init(self, extend=""):
        self.host = HOST
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": HOST + "/",
        }
        self._session = rq.Session()
        self._session.trust_env = False
        self._session.headers.update(self.headers)
        self._cache = {}
        self._cache_ts = 0
        return self

    def getName(self):
        return "动漫巴士"

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|flv|mkv|avi|ts)(\?|$)', str(url), re.I))

    def manualVideoCheck(self):
        return False

    def action(self, action):
        pass

    def destroy(self):
        pass

    def localProxy(self, param):
        pass

    def _get(self, url, timeout=15):
        try:
            r = self._session.get(url, headers=self.headers, timeout=timeout, verify=False)
            r.encoding = 'utf-8'
            return r.text
        except Exception:
            try:
                r = self.fetch(url, headers=self.headers, timeout=timeout)
                txt = r.text if hasattr(r, 'text') else str(r)
                return txt
            except Exception:
                return ""

    @staticmethod
    def _s(text, pattern, idx=1, default=""):
        m = re.search(pattern, text, re.S)
        return m.group(idx).strip() if m else default

    @staticmethod
    def _clean(text):
        text = re.sub(r'<[^>]+>', '', text or '')
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
        text = text.replace('&quot;', '"').replace('&#39;', "'")
        text = text.replace('&lt;', '<').replace('&gt;', '>')
        return re.sub(r'\s+', ' ', text).strip()

    @staticmethod
    def _abs(url):
        if not url:
            return ""
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('http'):
            return url
        return urljoin(HOST + '/', url)

    @staticmethod
    def build_show(tid, page=1, extend=None):
        segs = [''] * 12
        segs[0] = str(tid)
        if page and int(page) > 1:
            segs[8] = str(page)
        for k, v in (extend or {}).items():
            slot = FILTER_SLOT.get(k)
            if slot is None or not v or v in ('全部', '0'):
                continue
            segs[slot] = str(v)
        return "%s/show-%s.html" % (HOST, '-'.join(quote(s, safe='') for s in segs))

    @staticmethod
    def build_list(tid, page=1):
        if page and int(page) > 1:
            return "%s/list-%s-%s.html" % (HOST, tid, page)
        return "%s/list-%s.html" % (HOST, tid)

    @staticmethod
    def build_search(key, page=1):
        segs = [''] * 14
        segs[0] = key
        if page and int(page) > 1:
            segs[10] = str(page)
        return "%s/s-%s.html" % (HOST, '-'.join(quote(s, safe='') for s in segs))

    def _parse_list(self, html):
        items, seen = [], set()
        if not html:
            return items

        blocks = re.findall(
            r'<a\s+href="/v/(\d+)\.html"\s+class="cover[^"]*"[^>]*?data-bg="([^"]*)"[^>]*?>'
            r'[\s\S]{0,400}?'
            r'<a\s+class="title"\s+href="/v/\1\.html"\s+title="([^"]*)"[^>]*>[\s\S]*?</a>'
            r'(?:\s*<span\s+class="desc">([^<]*)</span>)?',
            html)
        for vid, pic, name, remark in blocks:
            if vid in seen:
                continue
            seen.add(vid)
            items.append({
                "vod_id": vid,
                "vod_name": self._clean(name),
                "vod_pic": self._abs(pic),
                "vod_remarks": self._clean(remark),
            })
        if items:
            return items

        for m in re.finditer(r'<div class="item">([\s\S]*?)</div>', html):
            blk = m.group(1)
            vid = self._s(blk, r'/v/(\d+)\.html')
            if not vid or vid in seen:
                continue
            pic = self._s(blk, r'data-bg="([^"]+)"') or self._s(blk, r'src="([^"]+\.(?:jpg|jpeg|png|webp|gif))"')
            name = self._s(blk, r'class="title"[^>]*title="([^"]+)"') or self._s(blk, r'class="title"[^>]*>([^<]+)<')
            if not name:
                continue
            seen.add(vid)
            items.append({
                "vod_id": vid,
                "vod_name": self._clean(name),
                "vod_pic": self._abs(pic),
                "vod_remarks": self._clean(self._s(blk, r'class="desc">([^<]*)<')),
            })
        if items:
            return items

        for vid, name in re.findall(r'<a class="title" href="/v/(\d+)\.html" title="([^"]*)"', html):
            if vid in seen:
                continue
            seen.add(vid)
            items.append({"vod_id": vid, "vod_name": self._clean(name),
                          "vod_pic": "", "vod_remarks": ""})
        return items

    @staticmethod
    def _parse_pagecount(html, default=1):
        m = re.search(r'href="[^"]*?/list-\d+-(\d+)\.html"[^>]*>\s*尾页', html)
        if m:
            return int(m.group(1))
        nums = [int(x) for x in re.findall(r'/list-\d+-(\d+)\.html', html)]
        nums += [int(x) for x in re.findall(r'/s-[^"]*?-(\d+)---\.html', html)]
        return max(nums) if nums else default

    def _load_home(self, force=False):
        """抓取导航分类 + 每个父分类下的子分类（筛选器）"""
        if self._cache and not force and (time.time() - self._cache_ts) < 1800:
            return self._cache

        html = self._get(HOST + "/")
        classes = []
        nav = self._s(html, r'<ul class="nav_row">([\s\S]*?)</ul>')
        for href, name in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>', nav or ''):
            m = re.search(r'/list-(\d+)\.html', href)
            if not m:
                continue
            name = self._clean(name)
            if not name or name in ('首页',):
                continue
            classes.append({"type_id": m.group(1), "type_name": name})

        if not classes:
            classes = [{"type_id": "28", "type_name": "国漫"},
                       {"type_id": "30", "type_name": "日漫"},
                       {"type_id": "31", "type_name": "欧美动漫"},
                       {"type_id": "33", "type_name": "电影"}]

        filters = {}
        for c in classes:
            f = self._parse_filters(c["type_id"])
            if f:
                filters[c["type_id"]] = f

        self._cache = {"class": classes, "filters": filters,
                       "list": self._parse_list(html)}
        self._cache_ts = time.time()
        return self._cache

    def _parse_filters(self, tid):
        html = self._get(self.build_list(tid))
        if not html:
            return []
        blk = self._s(html, r'<ul class="list_filter"[^>]*>([\s\S]*?)</ul>')
        if not blk:
            return []

        out = []
        for gname, body in re.findall(r'<div><span>([^<]+)</span>([\s\S]*?)</div>', blk):
            gname = self._clean(gname)
            key = GROUP_KEY.get(gname)
            values, seen = [], set()
            for href, label in re.findall(r'<a[^>]*?href="(/show-[^"]+)"[^>]*>([^<]+)</a>', body):
                label = self._clean(label)
                if not label:
                    continue
                segs = unquote(href[len('/show-'):-len('.html')]).split('-')
                val = ""
                slot_hit = None
                for i, s in enumerate(segs):
                    if i == 0 or not s:
                        continue
                    val, slot_hit = s, i
                    break
                if key is None and slot_hit is not None:
                    for k, v in FILTER_SLOT.items():
                        if v == slot_hit:
                            key = k
                            break
                if label in ('全部',):
                    val = ""
                elif not val:
                    val = SORT_VALUE.get(label, label)
                if val in seen:
                    continue
                seen.add(val)
                values.append({"n": label, "v": val})

            if not key or len(values) < 2:
                continue
            if key == 'by' and values and values[0]["v"]:
                values.insert(0, {"n": "默认", "v": ""})
            out.append({"key": key, "name": gname, "value": values})
        return out

    def homeContent(self, filter=True):
        try:
            data = self._load_home()
            return {"class": data["class"],
                    "filters": data["filters"],
                    "list": data["list"]}
        except Exception:
            return {"class": [], "filters": {}, "list": []}

    def homeVideoContent(self):
        try:
            data = self._load_home()
            lst = data.get("list") or []
            if not lst:
                lst = self._parse_list(self._get(HOST + "/"))
            return {"list": lst}
        except Exception:
            return {"list": []}

    def categoryContent(self, tid, pg=1, filter=False, extend=None):
        try:
            pn = max(int(str(pg) or 1), 1)
            extend = extend or {}
            active = {k: v for k, v in extend.items()
                      if v and str(v) not in ('全部', '0', '')}
            url = self.build_show(tid, pn, active) if active else self.build_list(tid, pn)
            html = self._get(url)
            items = self._parse_list(html)

            if not items and active and pn == 1:
                html = self._get(self.build_list(tid, pn))
                items = self._parse_list(html)

            if not items:
                return {"list": [], "page": pn, "pagecount": pn, "limit": 36, "total": 0}

            pagecount = self._parse_pagecount(html, default=0)
            if not pagecount:
                pagecount = pn + 1 if len(items) >= 36 else pn
            pagecount = max(pagecount, pn)
            return {"list": items, "page": pn, "pagecount": pagecount,
                    "limit": len(items), "total": pagecount * len(items)}
        except Exception:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 36, "total": 0}

    def detailContent(self, ids):
        try:
            vid = str(ids[0]) if isinstance(ids, list) else str(ids)
            vid = re.sub(r'\D', '', vid)
            if not vid:
                return {"list": []}
            html = self._get("%s/v/%s.html" % (HOST, vid))
            if not html:
                return {"list": []}

            name = self._clean(self._s(html, r'<h1 class="v_title">\s*<a[^>]*>([\s\S]*?)</a>')) \
                or self._clean(self._s(html, r'<h1[^>]*>([\s\S]*?)</h1>'))
            pic = self._abs(self._s(html, r'<div class="cover">\s*<img[^>]+src="([^"]+)"')
                            or self._s(html, r'<meta property="og:image" content="([^"]+)"'))

            desc_html = self._s(html, r'<p class="v_desc">([\s\S]*?)</p>')
            remarks = self._clean(self._s(desc_html, r'<span class="desc">([^<]*)</span>'))
            parts = [self._clean(p) for p in
                     re.split(r'<em[^>]*class="hr"[^>]*>\s*\|\s*</em>', desc_html or '')]
            parts = [p for p in parts if p]
            year, area, tags = "", "", ""
            iy = next((i for i, p in enumerate(parts)
                       if re.fullmatch(r'(19|20)\d{2}', p)), -1)
            if iy >= 0:
                year = parts[iy]
                if iy + 1 < len(parts):
                    area = parts[iy + 1]
                if iy + 2 < len(parts):
                    tags = ','.join(parts[iy + 2:])
            else:
                for p in parts:
                    if ',' in p and not tags:
                        tags = p

            intro_blk = self._s(html, r'<div id="intro">([\s\S]*?)<div class="show_more"') \
                or self._s(html, r'<div id="intro">([\s\S]*?)</div>')
            content, alias = "", ""
            for p in re.findall(r'<p>([\s\S]*?)</p>', intro_blk or ''):
                t = self._clean(p)
                if t.startswith('又名'):
                    alias = t
                elif t.startswith('剧情') or len(t) > len(content):
                    content = t
            content = re.sub(r'^剧情[:：]\s*', '', content)
            if alias:
                content = (alias + '\n' + content).strip()


            tab = self._s(html, r'<ul class="tab_control play_from">([\s\S]*?)</ul>')
            from_names = [self._clean(re.sub(r'\(\d+\)\s*$', '', x))
                          for x in re.findall(r'<li[^>]*>([^<]+)</li>', tab or '')]

            play_from, play_url = [], []
            lists = re.findall(r'<ul class="play_list[^"]*">([\s\S]*?)</ul>', html)
            for i, ul in enumerate(lists):
                eps = []
                for m in re.finditer(r'<a\s+title="([^"]*)"\s+href="(/p/[^"]+\.html)"[^>]*>([^<]*)</a>', ul):
                    ep_name = self._clean(m.group(1) or m.group(3))
                    eps.append("%s$%s" % (ep_name, m.group(2)))
                if not eps:
                    for m in re.finditer(r'<a[^>]+href="(/p/[^"]+\.html)"[^>]*>([^<]+)</a>', ul):
                        eps.append("%s$%s" % (self._clean(m.group(2)), m.group(1)))
                if not eps:
                    continue
                fname = from_names[i] if i < len(from_names) else ("线路%d" % (i + 1))
                play_from.append(fname or ("线路%d" % (i + 1)))
                play_url.append("#".join(eps))

            vod = {
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic,
                "vod_year": year,
                "vod_area": area,
                "type_name": tags,
                "vod_remarks": remarks,
                "vod_actor": "",
                "vod_director": "",
                "vod_content": content,
                "vod_play_from": "$$$".join(play_from),
                "vod_play_url": "$$$".join(play_url),
            }
            return {"list": [vod]}
        except Exception:
            return {"list": []}

    def searchContent(self, key, quick=False, pg=1):
        try:
            pn = max(int(str(pg) or 1), 1)
            html = self._get(self.build_search(key, pn))
            items = self._parse_list(html)
            if not items and pn == 1:
                html = self._get("%s/s--------------.html?wd=%s" % (HOST, quote(str(key))))
                items = self._parse_list(html)
            if not items:
                return {"list": [], "page": pn, "pagecount": pn, "limit": 16, "total": 0}

            pagecount = self._parse_pagecount(html, default=0)
            if not pagecount:
                pagecount = pn + 1 if len(items) >= 16 else pn
            pagecount = max(pagecount, pn)
            return {"list": items, "page": pn, "pagecount": pagecount,
                    "limit": len(items), "total": pagecount * len(items)}
        except Exception:
            return {"list": [], "page": pg}

    def playerContent(self, flag, id, vipFlags=None):
        headers = {"User-Agent": UA, "Referer": HOST + "/"}
        try:
            pid = str(id or "")
            if '$' in pid:
                pid = pid.split('$')[-1]
            if pid.startswith('http') and self.isVideoFormat(pid):
                return {"parse": 0, "playUrl": "", "url": pid, "header": headers}
            url = pid if pid.startswith('http') else self._abs(pid)
            html = self._get(url)
            real = ""
            m = re.search(r'<iframe[^>]*?src="([^"]+)"', html, re.S)
            if m:
                src = m.group(1).strip()
                mm = re.search(r'[?&]url=([^&"\']+)', src)
                real = unquote(mm.group(1)) if mm else self._abs(src)
            if not real:
                m = re.search(r'player_aaaa\s*=\s*(\{[\s\S]*?\})\s*</script>', html)
                if m:
                    try:
                        real = json.loads(m.group(1)).get('url', '')
                    except Exception:
                        real = self._s(m.group(1), r'"url"\s*:\s*"([^"]+)"')
                    real = real.replace('\\/', '/')
            if not real:
                real = self._s(html, r'(https?://[^\s"\']+\.m3u8[^\s"\']*)')
            if not real:
                return {"parse": 1, "playUrl": "", "url": url, "header": headers}
            parse = 0 if self.isVideoFormat(real) else 1
            return {"parse": parse, "playUrl": "", "url": real, "header": headers}
        except Exception:
            return {"parse": 1, "playUrl": "", "url": str(id), "header": headers}
if __name__ == '__main__':
    import urllib3
    urllib3.disable_warnings()
    s = Spider()
    s.init()
    print("=" * 60)
    home = s.homeContent(True)
    print("分类:", [c['type_name'] + '/' + c['type_id'] for c in home['class']])
    for tid, fl in home['filters'].items():
        print("  筛选[%s]:" % tid, [(f['name'], len(f['value'])) for f in fl])
    print("首页推荐:", len(home['list']), home['list'][:2])
    print("=" * 60)
    cat = s.categoryContent('30', 2)
    print("分类页2:", len(cat['list']), "共%s页" % cat['pagecount'], cat['list'][:2])
    print("=" * 60)
    for tid, ext in [('30', {"class": "奇幻"}),
                     ('30', {"class": "奇幻", "by": "hits"}),
                     ('33', {"class": "科幻", "year": "2024"}),
                     ('28', {"class": "玄幻", "by": "score"})]:
        c = s.categoryContent(tid, 2, True, ext)
        print("筛选 tid=%s %s 第2页:" % (tid, ext), len(c['list']),
              "共%s页" % c['pagecount'], [i['vod_name'] for i in c['list'][:4]])

    print("=" * 60)
    vid = (cat['list'] or [{}])[0].get('vod_id', '108620')
    det = s.detailContent([vid])['list'][0]
    print("详情:", det['vod_name'], '|', det['vod_year'], det['vod_area'],
          '|', det['vod_remarks'], '|', det['type_name'])
    print("封面:", det['vod_pic'])
    print("简介:", det['vod_content'][:80])
    print("线路:", det['vod_play_from'])
    print("首线路集数:", len(det['vod_play_url'].split('$$$')[0].split('#')))
    print("=" * 60)
    sr = s.searchContent('海贼', pg=1)
    print("搜索:", len(sr['list']), "共%s页" % sr.get('pagecount'),
          [i['vod_name'] for i in sr['list'][:5]])
    print("=" * 60)
    ep = det['vod_play_url'].split('$$$')[0].split('#')[0]
    print("播放测试:", ep)
    print(s.playerContent(det['vod_play_from'].split('$$$')[0], ep.split('$')[-1]))
