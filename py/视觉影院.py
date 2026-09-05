# -*- coding: utf-8 -*-
import re, json, requests
from urllib.parse import quote
from lxml import etree
from base.spider import Spider

class Spider(Spider):
    def __init__(self):
        self.name = "sypfjy"
        self.host = "https://www.sypfjy.com"
        self.header = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': self.host
        }

    def getName(self):
        return self.name

    def init(self, extend=''):
        pass

    def _get(self, url, params=None):
        r = requests.get(url, headers=self.header, params=params, timeout=20)
        r.encoding = 'utf-8'
        return r.text

    def _post(self, url, data=None):
        r = requests.post(url, headers=self.header, data=data, timeout=20)
        r.encoding = 'utf-8'
        return r.text

    def _fix_url(self, url):
        if not url:
            return ''
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('/'):
            return self.host + url
        return url

    def _parse_pic(self, elem):
        if elem is None:
            return ''
        if elem.tag == 'img':
            pic = elem.get('data-src') or elem.get('src', '')
        else:
            imgs = elem.xpath('.//img')
            pic = (imgs[0].get('data-src') or imgs[0].get('src', '')) if imgs else ''
        if pic and pic.startswith('data:image'):
            pic = ''
        return self._fix_url(pic)

    def _parse_text(self, elem):
        if elem is None:
            return ''
        return ''.join(elem.itertext()).strip()

    def _build_vodshow(self, tid, area, order, cls, lang, page, year):
        """12 段位 URL: type-area-order-class-lang-_-_-_-page-_-_-year
        默认排序 time 不写入 URL（留空）"""
        def q(v):
            return quote(v) if v else ''
        # 默认排序不写
        order_v = q(order) if order and order != 'time' else ''
        # 页码 1 不写（留空默认）
        page_v = str(page) if int(page) > 1 else ''
        segs = [str(tid), q(area), order_v, q(cls), q(lang), '', '', '', page_v, '', '', q(year)]
        return f"{self.host}/vodshow/{'-'.join(segs)}.html"

    def _parse_list_item(self, item):
        a = item.xpath('.//div[contains(@class,"video-name")]//a')
        if not a:
            return None
        a = a[0]
        href = a.get('href', '')
        m = re.search(r'/voddetail/(\d+)\.html', href)
        if not m:
            return None
        vid = m.group(1)
        vod_name = a.get('title', '').strip() or (a.text or '').strip()
        vod_pic = self._parse_pic(item)
        caption = item.xpath('.//div[contains(@class,"module-item-caption")]//text()')
        parts = [s.strip() for s in caption if s.strip()]
        vod_remarks = ' / '.join(parts[-2:]) if len(parts) >= 2 else (parts[-1] if parts else '')
        return {"vod_id": vid, "vod_name": vod_name, "vod_pic": vod_pic, "vod_remarks": vod_remarks}

    def homeContent(self, filter):
        classes = [
            {"type_name": "电视剧", "type_id": "2"},
            {"type_name": "电影", "type_id": "dianying"},
            {"type_name": "动漫", "type_id": "dongman"},
            {"type_name": "短剧", "type_id": "remenduanju"},
            {"type_name": "综艺", "type_id": "zongyi"},
            {"type_name": "体育", "type_id": "tiyusaishi"}
        ]
        filters = {}
        order_vals = [{"n": "时间排序", "v": "time"}, {"n": "人气排序", "v": "hits"}, {"n": "评分排序", "v": "score"}]
        area_vals = [{"n": "全部", "v": ""}, {"n": "内地", "v": "内地"}, {"n": "中国", "v": "中国"}, {"n": "香港", "v": "香港"}, {"n": "台湾", "v": "台湾"}, {"n": "韩国", "v": "韩国"}, {"n": "日本", "v": "日本"}, {"n": "美国", "v": "美国"}, {"n": "泰国", "v": "泰国"}, {"n": "英国", "v": "英国"}, {"n": "新加坡", "v": "新加坡"}, {"n": "其他", "v": "其他"}]
        class_vals = [{"n": "全部", "v": ""}, {"n": "古装", "v": "古装"}, {"n": "战争", "v": "战争"}, {"n": "青春偶像", "v": "青春偶像"}, {"n": "喜剧", "v": "喜剧"}, {"n": "家庭", "v": "家庭"}, {"n": "犯罪", "v": "犯罪"}, {"n": "动作", "v": "动作"}, {"n": "奇幻", "v": "奇幻"}, {"n": "剧情", "v": "剧情"}, {"n": "历史", "v": "历史"}, {"n": "经典", "v": "经典"}, {"n": "科幻", "v": "科幻"}, {"n": "悬疑", "v": "悬疑"}, {"n": "爱情", "v": "爱情"}, {"n": "惊悚", "v": "惊悚"}, {"n": "恐怖", "v": "恐怖"}, {"n": "灾难", "v": "灾难"}, {"n": "网络", "v": "网络"}, {"n": "商战", "v": "商战"}, {"n": "乡村", "v": "乡村"}, {"n": "情景", "v": "情景"}, {"n": "武侠", "v": "武侠"}, {"n": "冒险", "v": "冒险"}, {"n": "谍战", "v": "谍战"}, {"n": "其他", "v": "其他"}]
        lang_vals = [{"n": "全部", "v": ""}, {"n": "国语", "v": "国语"}, {"n": "英语", "v": "英语"}, {"n": "粤语", "v": "粤语"}, {"n": "闽南语", "v": "闽南语"}, {"n": "韩语", "v": "韩语"}, {"n": "日语", "v": "日语"}, {"n": "其他", "v": "其他"}]
        year_vals = [{"n": "全部", "v": ""}, {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"}, {"n": "2024", "v": "2024"}, {"n": "2023", "v": "2023"}, {"n": "2022", "v": "2022"}, {"n": "2021", "v": "2021"}, {"n": "2020", "v": "2020"}, {"n": "2019", "v": "2019"}, {"n": "2018", "v": "2018"}, {"n": "2017", "v": "2017"}, {"n": "2016", "v": "2016"}, {"n": "2015", "v": "2015"}]
        for c in classes:
            filters[c['type_id']] = [
                {"key": "area", "name": "地区", "value": area_vals},
                {"key": "class", "name": "类型", "value": class_vals},
                {"key": "lang", "name": "语言", "value": lang_vals},
                {"key": "year", "name": "年份", "value": year_vals},
                {"key": "order", "name": "排序", "value": order_vals}
            ]
        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        videos = []
        try:
            html = self._get(self.host)
            root = etree.HTML(html)
            for item in root.xpath('//div[contains(@class, "module-item")]'):
                try:
                    v = self._parse_list_item(item)
                    if v:
                        videos.append(v)
                except Exception:
                    pass
        except Exception:
            pass
        return {"list": videos}

    def categoryContent(self, tid, pg, filter, extend):
        videos = []
        try:
            if isinstance(extend, str) and extend:
                try: extend = json.loads(extend)
                except: extend = {}
            elif not extend:
                extend = {}
            area = extend.get('area', '')
            cls = extend.get('class', '')
            year = extend.get('year', '')
            lang = extend.get('lang', '')
            order = extend.get('order', 'time')
            if order in ('hits_week', 'hits_month'): order = 'hits'
            elif order not in ('time', 'hits', 'score'): order = 'time'
            url = self._build_vodshow(tid, area, order, cls, lang, pg, year)
            html = self._get(url)
            root = etree.HTML(html)
            for item in root.xpath('//div[contains(@class, "module-item")]'):
                try:
                    v = self._parse_list_item(item)
                    if v:
                        videos.append(v)
                except Exception:
                    pass
            # 去重
            seen = set()
            unique = []
            for v in videos:
                if v['vod_id'] not in seen:
                    seen.add(v['vod_id'])
                    unique.append(v)
            # 总页数
            pm = 1
            for m in re.finditer(r'href="(/vodshow/[^"]*?-(\d+)-[^"]*)"', html):
                pm = max(pm, int(m.group(2)))
            if pm < 1:
                m = re.search(r'第(\d+)页.*尾页', html)
                if m: pm = int(m.group(1))
            limit = len(unique) if unique else 24
            return {'list': unique, 'page': int(pg), 'pagecount': pm, 'limit': limit, 'total': pm * limit}
        except Exception:
            return {'list': [], 'page': 1, 'pagecount': 0, 'limit': 0, 'total': 0}

    def detailContent(self, ids):
        try:
            vod_id = ids[0]
            html = self._get(f"{self.host}/voddetail/{vod_id}.html")
            root = etree.HTML(html)
            title = root.xpath('//h1[@class="page-title"]/text()')
            vod_name = title[0].strip() if title else ''
            if not vod_name:
                ts = root.xpath('//title/text()')
                if ts: vod_name = ts[0].split('-')[0].strip()
            pic_a = root.xpath('//div[contains(@class,"video-cover")]//img')
            vod_pic = ''
            if pic_a:
                pic = pic_a[0].get('data-src') or pic_a[0].get('src', '')
                if not pic.startswith('data:image'): vod_pic = self._fix_url(pic)
            year_a = root.xpath('//a[contains(@href,"/vodsearch/year/")]')
            vod_year = ''
            if year_a:
                m = re.search(r'(\d{4})', year_a[0].text or '')
                if m: vod_year = m.group(1)
            if not vod_year:
                yl = root.xpath('//a[contains(@href,"/vodshow/")]')
                for t in yl:
                    m = re.search(r'^(\d{4})\s*$', (t.text or '').strip())
                    if m: vod_year = m.group(1); break
            area_a = root.xpath('//a[contains(@href,"/vodshow/")]')
            area_k = ['中国大陆', '中国香港', '中国台湾', '香港', '台湾', '内地', '韩国', '日本', '美国', '泰国', '英国', '新加坡', '法国']
            vod_area = ''
            for t in area_a:
                txt = (t.text or '').strip()
                if re.match(r'^\d{4}$', txt): continue
                for k in area_k:
                    if k in txt:
                        if k == '香港': vod_area = '中国香港'
                        elif k == '台湾': vod_area = '中国台湾'
                        elif k == '内地': vod_area = '中国大陆'
                        else: vod_area = txt
                        break
                if vod_area: break
            def _ef(label):
                p = html.find('class="video-info-itemtitle">%s</span>' % label)
                if p < 0: return ''
                end = html.find('class="video-info-items"', p+1)
                if end < 0: end = p + 800
                seg = html[p:end]
                names = [x.strip() for x in re.findall(r'href="[^"]*/vodsearch/[^"]+"[^>]*>([^<]+)<', seg)]
                if not names:
                    d = re.search(r'class="video-info-item"[^>]*>([^<]*)<', seg)
                    if d: return d.group(1).strip()
                return ' '.join(names)
            vod_actor = _ef('主演：')
            vod_director = _ef('导演：')
            sq = root.xpath('//p[@class="sqjj_a"]')
            vod_content = ''
            if sq: vod_content = self._parse_text(sq[0])
            if not vod_content:
                zk = root.xpath('//p[@class="zkjj_a"]')
                if zk: vod_content = self._parse_text(zk[0])
            vod_content = re.sub(r'\[收起部分\]|\[展开全部\]', '', vod_content)
            vod_content = re.sub(r'\s+', '', vod_content).strip()
            tabs = re.findall(r'data-dropdown-value="([^"]+)"', html)
            sections = re.split(r'\bid="glist-\d+"', html)
            froms = []; urls = []
            for idx, sec in enumerate(sections):
                if idx >= len(tabs): break
                name = tabs[idx].strip()
                if not name or name == 'http下载': continue
                eps = re.findall(r'href="(/vodplay/[^"]+)"[^>]*>(?:<span>)?([^<]*)(?:</span>)?</a>', sec)
                if not eps: continue
                pl = []
                for h, t in eps:
                    txt = t.strip()
                    if not txt:
                        mm = re.search(r'/vodplay/\d+-\d+-(\d+)\.html', h)
                        txt = '第%d集' % int(mm.group(1)) if mm else h
                    pl.append(f"{txt}${self._fix_url(h)}")
                if pl:
                    froms.append(name); urls.append("#".join(pl))
            return {'list': [{"vod_id": vod_id, "vod_name": vod_name, "vod_pic": vod_pic,
                "vod_year": vod_year, "vod_area": vod_area, "vod_actor": vod_actor,
                "vod_director": vod_director, "vod_content": vod_content,
                "vod_play_from": "$$$".join(froms) if froms else "默认",
                "vod_play_url": "$$$".join(urls) if urls else ""}]}
        except Exception:
            return {'list': []}

    def playerContent(self, flag, id, vipFlags):
        try:
            html = self._get(id)
            m = re.search(r'player_aaaa=({.*?})\s*</script>', html, re.S)
            if m:
                try:
                    d = json.loads(m.group(1))
                    url = d.get('url', '')
                    if url:
                        if url.startswith('//'): url = 'https:' + url
                        return {"parse": 0 if self.isVideoFormat(url) else 1, "playUrl": "", "url": url, "header": json.dumps(self.header)}
                except: pass
            ifr = re.search(r'<iframe[^>]+src\s*=\s*"([^"]+)"', html)
            if ifr:
                u = self._fix_url(ifr.group(1))
                return {"parse": 0 if self.isVideoFormat(u) else 1, "playUrl": "", "url": u, "header": json.dumps(self.header)}
            m3u8 = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', html)
            if m3u8: return {"parse": 0, "playUrl": "", "url": m3u8.group(1), "header": json.dumps(self.header)}
            mp4 = re.search(r'["\'](https?://[^"\']+\.(?:mp4|flv|ts))["\']', html)
            if mp4: return {"parse": 0, "playUrl": "", "url": mp4.group(1), "header": json.dumps(self.header)}
            return {"parse": 0, "playUrl": "", "url": ""}
        except Exception:
            return {"parse": 0, "playUrl": "", "url": ""}

    def searchContent(self, key, quick, pg='1'):
        videos = []
        try:
            html = self._get(f"{self.host}/vodsearch.html", params={"wd": key, "pg": pg})
            parts = html.split('<div class="module-search-item">')
            for p in parts[1:]:
                vm = re.search(r'href="(/voddetail/(\d+)\.html)"', p)
                if not vm: continue
                nm = re.search(r'<h3><a href="/voddetail/\d+\.html" title="([^"]+)"', p)
                pm = re.search(r'data-src="([^"]+)"', p)
                rm = re.search(r'video-serial"[^>]*>([^<]+)<', p)
                videos.append({"vod_id": vm.group(2),
                    "vod_name": nm.group(1) if nm else '',
                    "vod_pic": self._fix_url(pm.group(1)) if pm else '',
                    "vod_remarks": rm.group(1).strip() if rm else ''})
            tm = re.search(r'<strong class="mac_total">(\d+)</strong>', html)
            total = int(tm.group(1)) if tm else len(videos)
            pc = max(1, (total + (len(videos) or 1) - 1) // (len(videos) or 1))
            return {'list': videos, 'page': int(pg), 'pagecount': pc, 'limit': len(videos), 'total': total}
        except Exception:
            return {'list': [], 'page': 1, 'pagecount': 0, 'limit': 0, 'total': 0}

    def isVideoFormat(self, url):
        return any(url.lower().endswith(f) for f in ['.m3u8', '.mp4', '.flv', '.ts'])

    def manualVideoCheck(self): pass
    def localProxy(self, params): return None
    def destroy(self): pass
