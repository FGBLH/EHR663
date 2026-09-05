# coding=utf-8
import re
import json
import requests
from urllib.parse import quote
from lxml import etree
from base.spider import Spider


class Spider(Spider):
    def __init__(self):
        self.name = "btdy"
        self.host = "https://dy.8ttv.cn"
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
        r = requests.get(url, headers=self.header, params=params, timeout=15)
        r.encoding = 'utf-8'
        return r.text

    def _post(self, url, data=None):
        r = requests.post(url, headers=self.header, data=data, timeout=15)
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

    @staticmethod
    def _parse_text(elem):
        if elem is None:
            return ''
        return ''.join(elem.itertext()).strip()

    def _parse_pic(self, elem):
        pic = ''
        if elem is None:
            return pic
        if elem.tag == 'img':
            pic = elem.get('data-original') or elem.get('data-src') or elem.get('src', '')
        else:
            imgs = elem.xpath('.//img')
            if imgs:
                pic = imgs[0].get('data-original') or imgs[0].get('data-src') or imgs[0].get('src', '')
        if not pic:
            return ''
        if pic.startswith('data:image') or 'alicdn.com' in pic:
            return ''
        return self._fix_url(pic)

    def _parse_poster_item(self, a):
        href = a.get('href', '')
        m = re.search(r'/detail/id/(\d+)\.html', href)
        if not m:
            return None
        vod_id = m.group(1)
        vod_name = a.get('title', '').strip()
        if not vod_name:
            t = a.xpath('.//div[contains(@class,"module-poster-item-title")]/text()')
            vod_name = t[0].strip() if t else ''
        vod_pic = self._parse_pic(a)
        remark = a.xpath('.//div[contains(@class,"module-item-note")]/text()')
        vod_remarks = remark[0].strip() if remark else ''
        return {
            "vod_id": vod_id,
            "vod_name": vod_name,
            "vod_pic": vod_pic,
            "vod_remarks": vod_remarks
        }

    def homeContent(self, filter):
        result = {"class": []}
        classes = [
            {"type_name": "电影", "type_id": "1"},
            {"type_name": "电视剧", "type_id": "2"},
            {"type_name": "综艺", "type_id": "3"},
            {"type_name": "动漫", "type_id": "4"},
            {"type_name": "短剧", "type_id": "5"},
            {"type_name": "纪录片", "type_id": "20"}
        ]
        result["class"] = classes

        area_vals = [
            {"n": "全部", "v": ""},
            {"n": "中国大陆", "v": "中国大陆"},
            {"n": "中国香港", "v": "中国香港"},
            {"n": "中国台湾", "v": "中国台湾"},
            {"n": "美国", "v": "美国"},
            {"n": "日本", "v": "日本"},
            {"n": "韩国", "v": "韩国"},
            {"n": "泰国", "v": "泰国"},
            {"n": "英国", "v": "英国"},
            {"n": "法国", "v": "法国"},
            {"n": "德国", "v": "德国"},
            {"n": "意大利", "v": "意大利"},
            {"n": "西班牙", "v": "西班牙"},
            {"n": "加拿大", "v": "加拿大"},
            {"n": "印度", "v": "印度"},
            {"n": "其他", "v": "其他"}
        ]
        class_vals = [
            {"n": "全部", "v": ""},
            {"n": "喜剧", "v": "喜剧"},
            {"n": "爱情", "v": "爱情"},
            {"n": "恐怖", "v": "恐怖"},
            {"n": "动作", "v": "动作"},
            {"n": "科幻", "v": "科幻"},
            {"n": "剧情", "v": "剧情"},
            {"n": "战争", "v": "战争"},
            {"n": "警匪", "v": "警匪"},
            {"n": "犯罪", "v": "犯罪"},
            {"n": "动画", "v": "动画"},
            {"n": "奇幻", "v": "奇幻"},
            {"n": "武侠", "v": "武侠"},
            {"n": "冒险", "v": "冒险"},
            {"n": "枪战", "v": "枪战"},
            {"n": "悬疑", "v": "悬疑"},
            {"n": "惊悚", "v": "惊悚"},
            {"n": "经典", "v": "经典"},
            {"n": "青春", "v": "青春"},
            {"n": "文艺", "v": "文艺"},
            {"n": "微电影", "v": "微电影"},
            {"n": "古装", "v": "古装"},
            {"n": "历史", "v": "历史"},
            {"n": "运动", "v": "运动"},
            {"n": "农村", "v": "农村"},
            {"n": "儿童", "v": "儿童"},
            {"n": "网络电影", "v": "网络电影"},
            {"n": "短剧", "v": "短剧"},
            {"n": "纪录片", "v": "纪录片"},
            {"n": "综艺", "v": "综艺"},
            {"n": "动漫", "v": "动漫"}
        ]
        year_vals = [{"n": "全部", "v": ""}]
        for y in range(2026, 1989, -1):
            year_vals.append({"n": str(y), "v": str(y)})
        year_vals.append({"n": "其他", "v": "其他"})
        by_vals = [
            {"n": "最新", "v": "time"},
            {"n": "最热", "v": "hits"},
            {"n": "高分", "v": "score"}
        ]

        filters = {}
        for c in classes:
            filters[c['type_id']] = [
                {"key": "class", "name": "类型", "value": class_vals},
                {"key": "area", "name": "地区", "value": area_vals},
                {"key": "year", "name": "年份", "value": year_vals},
                {"key": "by", "name": "排序", "value": by_vals}
            ]
        result["filters"] = filters
        return result

    def homeVideoContent(self):
        videos = []
        try:
            html = self._get(self.host)
            root = etree.HTML(html)
            items = root.xpath('//a[contains(@class,"module-poster-item") and contains(@class,"module-item")]')
            seen = set()
            for a in items:
                try:
                    video = self._parse_poster_item(a)
                    if video and video['vod_id'] not in seen:
                        videos.append(video)
                        seen.add(video['vod_id'])
                except Exception:
                    pass
        except Exception:
            pass
        return {"list": videos}

    def categoryContent(self, tid, pg, filter, extend):
        videos = []
        try:
            if isinstance(extend, str) and extend:
                try:
                    extend = json.loads(extend)
                except Exception:
                    extend = {}
            elif not extend:
                extend = {}

            cls = extend.get('class', '')
            area = extend.get('area', '')
            year = extend.get('year', '')
            by = extend.get('by', 'time')

            segments = []
            if cls:
                segments.append(f"class/{quote(cls)}")
            if area:
                segments.append(f"area/{quote(area)}")
            if year:
                segments.append(f"year/{year}")
            if by:
                segments.append(f"by/{quote(by)}")

            url = f"{self.host}/index.php/vod/show/"
            if segments:
                url += '/'.join(segments) + '/'
            url += f"id/{tid}"
            if int(pg) > 1:
                url += f"/page/{pg}"
            url += ".html"

            html = self._get(url)
            root = etree.HTML(html)
            items = root.xpath('//a[contains(@class,"module-poster-item") and contains(@class,"module-item")]')
            for a in items:
                try:
                    video = self._parse_poster_item(a)
                    if video:
                        videos.append(video)
                except Exception:
                    pass

            total_pages = 1
            page_hrefs = root.xpath('//a[contains(@class,"page-link")]/@href')
            for href in page_hrefs:
                m = re.search(r'/page/(\d+)\.html', href)
                if m:
                    total_pages = max(total_pages, int(m.group(1)))

            return {
                'list': videos,
                'page': int(pg),
                'pagecount': total_pages,
                'limit': len(videos),
                'total': total_pages * len(videos) if videos else total_pages * 36
            }
        except Exception:
            return {'list': [], 'page': 1, 'pagecount': 0, 'limit': 0, 'total': 0}

    def detailContent(self, ids):
        try:
            vod_id = ids[0]
            detail_url = f"{self.host}/index.php/vod/detail/id/{vod_id}.html"
            html = self._get(detail_url)
            root = etree.HTML(html)

            vod_name = ''
            h1 = root.xpath('//div[contains(@class,"module-info-heading")]//h1/text()')
            if h1:
                vod_name = h1[0].strip()
            if not vod_name:
                title = root.xpath('//title/text()')
                if title:
                    vod_name = title[0].split('-')[0].strip()

            vod_pic = ''
            poster = root.xpath('//div[contains(@class,"module-info-poster")]')
            if poster:
                vod_pic = self._parse_pic(poster[0])

            vod_year = ''
            vod_area = ''
            area_set = {'中国大陆', '中国香港', '中国台湾', '美国', '日本', '韩国', '泰国',
                        '英国', '法国', '德国', '意大利', '西班牙', '加拿大', '印度', '其他'}
            for a in root.xpath('//div[contains(@class,"module-info-tag")]//a'):
                txt = self._parse_text(a)
                title = a.get('title', '')
                if not vod_year and (re.match(r'^\d{4}$', txt) or re.match(r'^\d{4}$', title)):
                    vod_year = txt or title
                if not vod_area and txt in area_set:
                    vod_area = txt

            vod_actor = ''
            vod_director = ''
            info_items = root.xpath('//div[contains(@class,"module-info-item")]')
            for item in info_items:
                label = item.xpath('.//span[contains(@class,"module-info-item-title")]/text()')
                if not label:
                    continue
                label_text = label[0].strip()
                content_elems = item.xpath('.//div[contains(@class,"module-info-item-content")]')
                if not content_elems:
                    continue
                content = content_elems[0]
                if '导演' in label_text:
                    directors = content.xpath('.//a/text()')
                    vod_director = ' '.join([d.strip() for d in directors if d.strip()])
                elif '主演' in label_text:
                    actors = content.xpath('.//a/text()')
                    vod_actor = ' '.join([a.strip() for a in actors if a.strip()])

            vod_content = ''
            intro = root.xpath('//div[contains(@class,"module-info-introduction-content")]//p')
            if intro:
                vod_content = self._parse_text(intro[0])
                vod_content = re.sub(r'\[.*?\]', '', vod_content).strip()

            vod_play_from = []
            vod_play_url = []
            source_tabs = root.xpath('//div[@id="y-playList"]//div[contains(@class,"module-tab-item")]')
            list_boxes = root.xpath('//div[contains(@class,"module-list") and contains(@class,"tab-list")]')

            for idx, tab in enumerate(source_tabs):
                source_name = tab.get('data-dropdown-value', '').strip()
                if not source_name:
                    spans = tab.xpath('.//span')
                    source_name = self._parse_text(spans[0]) if spans else ''
                source_name = re.sub(r'\s+', ' ', source_name).strip()
                if not source_name:
                    continue
                if idx >= len(list_boxes):
                    continue
                box = list_boxes[idx]
                links = box.xpath('.//a[contains(@class,"module-play-list-link")]')
                play_list = []
                for a in links:
                    ep_name = ''
                    spans = a.xpath('.//span/text()')
                    if spans:
                        ep_name = spans[0].strip()
                    if not ep_name:
                        ep_name = a.get('title', '').strip()
                    href = a.get('href', '')
                    if not ep_name or not href:
                        continue
                    play_list.append(f"{ep_name}${self._fix_url(href)}")
                if play_list:
                    vod_play_from.append(source_name)
                    vod_play_url.append('#'.join(play_list))

            if not vod_play_from:
                links = root.xpath('//div[contains(@class,"module-play-list")]//a[contains(@class,"module-play-list-link")]')
                play_list = []
                for a in links:
                    ep_name = ''
                    spans = a.xpath('.//span/text()')
                    if spans:
                        ep_name = spans[0].strip()
                    if not ep_name:
                        ep_name = a.get('title', '').strip()
                    href = a.get('href', '')
                    if ep_name and href:
                        play_list.append(f"{ep_name}${self._fix_url(href)}")
                if play_list:
                    vod_play_from.append("默认")
                    vod_play_url.append('#'.join(play_list))

            detail = {
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_year": vod_year,
                "vod_area": vod_area,
                "vod_actor": vod_actor,
                "vod_director": vod_director,
                "vod_content": vod_content,
                "vod_play_from": "$$$".join(vod_play_from),
                "vod_play_url": "$$$".join(vod_play_url)
            }
            return {'list': [detail]}
        except Exception:
            return {'list': []}

    def _extract_player_data(self, html):
        try:
            m = re.search(r'var\s+player_aaaa\s*=\s*\{', html)
            if not m:
                return None
            start = m.end() - 1
            depth = 1
            i = start + 1
            while i < len(html) and depth > 0:
                if html[i] == '{':
                    depth += 1
                elif html[i] == '}':
                    depth -= 1
                i += 1
            data = json.loads(html[start:i])
            return data
        except Exception:
            return None

    def playerContent(self, flag, id, vipFlags):
        try:
            html = self._get(id)
            data = self._extract_player_data(html)
            if data and data.get('url'):
                real_url = data['url']
                if real_url.startswith('//'):
                    real_url = 'https:' + real_url
                parse_flag = 0 if self.isVideoFormat(real_url) else 1
                return {"parse": parse_flag, "playUrl": "", "url": real_url, "header": json.dumps(self.header)}

            iframe_match = re.search(r'<iframe[^>]+src\s*=\s*"([^"]+)"', html)
            if iframe_match:
                real_url = iframe_match.group(1)
                real_url = self._fix_url(real_url)
                parse_flag = 0 if self.isVideoFormat(real_url) else 1
                return {"parse": parse_flag, "playUrl": "", "url": real_url, "header": json.dumps(self.header)}

            m3u8_match = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', html)
            if m3u8_match:
                return {"parse": 0, "playUrl": "", "url": m3u8_match.group(1), "header": json.dumps(self.header)}

            mp4_match = re.search(r'["\'](https?://[^"\']+\.(?:mp4|flv|ts))["\']', html)
            if mp4_match:
                return {"parse": 0, "playUrl": "", "url": mp4_match.group(1), "header": json.dumps(self.header)}

            return {"parse": 1, "playUrl": "", "url": id, "header": json.dumps(self.header)}
        except Exception:
            return {"parse": 0, "playUrl": "", "url": ""}

    def searchContent(self, key, quick, pg='1'):
        videos = []
        try:
            url = f"{self.host}/index.php/vod/search/wd/{quote(key)}.html"
            html = self._get(url)
            root = etree.HTML(html)
            items = root.xpath('//div[contains(@class,"module-card-item")]')
            for item in items:
                try:
                    a = item.xpath('.//div[contains(@class,"module-card-item-title")]//a')[0]
                    href = a.get('href', '')
                    m = re.search(r'/detail/id/(\d+)\.html', href)
                    if not m:
                        continue
                    vod_id = m.group(1)
                    vod_name = self._parse_text(a)
                    poster_a = item.xpath('.//a[contains(@class,"module-card-item-poster")]')
                    vod_pic = self._parse_pic(poster_a[0]) if poster_a else ''
                    remark = item.xpath('.//div[contains(@class,"module-item-note")]/text()')
                    vod_remarks = remark[0].strip() if remark else ''
                    videos.append({
                        "vod_id": vod_id,
                        "vod_name": vod_name,
                        "vod_pic": vod_pic,
                        "vod_remarks": vod_remarks
                    })
                except Exception:
                    pass
            return {
                'list': videos,
                'page': int(pg),
                'pagecount': 1,
                'limit': len(videos),
                'total': len(videos)
            }
        except Exception:
            return {'list': [], 'page': 1, 'pagecount': 0, 'limit': 0, 'total': 0}

    def isVideoFormat(self, url):
        return any(url.lower().endswith(fmt) for fmt in ['.m3u8', '.mp4', '.flv', '.ts'])

    def manualVideoCheck(self):
        pass

    def localProxy(self, params):
        return None

    def destroy(self):
        pass
