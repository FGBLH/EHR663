# coding=utf-8
import re, json, requests
from urllib.parse import quote
from lxml import etree
from base.spider import Spider

class Spider(Spider):
    def __init__(self):
        self.name = "webstar"
        self.host = "https://www.webstar.cn"
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

    def _parse_text(self, elem):
        if elem is None:
            return ''
        return ''.join(elem.itertext()).strip()

    def _parse_list_item(self, item):
        a = item.xpath('.//a[contains(@class, "myui-vodlist__thumb")]')
        if not a:
            return None
        a = a[0]
        href = a.get('href', '')
        m = re.search(r'/voddetail/(\d+)\.html', href)
        if not m:
            return None
        vod_id = m.group(1)
        vod_name = a.get('title', '').strip()
        if not vod_name:
            t = item.xpath('.//h4[contains(@class, "title")]//a/text()')
            vod_name = t[0].strip() if t else ''
        vod_pic = a.get('data-original', '')
        if not vod_pic:
            vod_pic = a.get('data-src', '')
        if not vod_pic:
            img = a.xpath('.//img')
            if img:
                vod_pic = img[0].get('data-original', '') or img[0].get('data-src', '') or img[0].get('src', '')
        vod_pic = self._fix_url(vod_pic)
        if vod_pic and vod_pic.startswith('data:image'):
            vod_pic = ''
        remark = item.xpath('.//span[contains(@class, "pic-text")]/text()')
        vod_remarks = remark[0].strip() if remark else ''
        if not vod_remarks:
            score = item.xpath('.//span[contains(@class, "pic-tag-top")]/text()')
            vod_remarks = score[0].strip() if score else ''
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
            {"type_name": "短剧", "type_id": "20"},
            {"type_name": "动画", "type_id": "35"}
        ]
        result["class"] = classes
        filters = {}
        area_vals = [
            {"n": "全部", "v": ""}, {"n": "大陆", "v": "大陆"},
            {"n": "香港", "v": "香港"}, {"n": "台湾", "v": "台湾"},
            {"n": "美国", "v": "美国"}, {"n": "法国", "v": "法国"},
            {"n": "英国", "v": "英国"}, {"n": "日本", "v": "日本"},
            {"n": "韩国", "v": "韩国"}, {"n": "德国", "v": "德国"},
            {"n": "泰国", "v": "泰国"}, {"n": "印度", "v": "印度"},
            {"n": "意大利", "v": "意大利"}, {"n": "西班牙", "v": "西班牙"},
            {"n": "加拿大", "v": "加拿大"}, {"n": "其他", "v": "其他"}
        ]
        class_vals = [
            {"n": "全部", "v": ""}, {"n": "喜剧", "v": "喜剧"},
            {"n": "爱情", "v": "爱情"}, {"n": "恐怖", "v": "恐怖"},
            {"n": "动作", "v": "动作"}, {"n": "科幻", "v": "科幻"},
            {"n": "剧情", "v": "剧情"}, {"n": "战争", "v": "战争"},
            {"n": "警匪", "v": "警匪"}, {"n": "犯罪", "v": "犯罪"},
            {"n": "动画", "v": "动画"}, {"n": "奇幻", "v": "奇幻"},
            {"n": "武侠", "v": "武侠"}, {"n": "冒险", "v": "冒险"},
            {"n": "枪战", "v": "枪战"}, {"n": "悬疑", "v": "悬疑"},
            {"n": "惊悚", "v": "惊悚"}, {"n": "经典", "v": "经典"},
            {"n": "青春", "v": "青春"}, {"n": "文艺", "v": "文艺"},
            {"n": "微电影", "v": "微电影"}, {"n": "古装", "v": "古装"},
            {"n": "历史", "v": "历史"}, {"n": "运动", "v": "运动"},
            {"n": "农村", "v": "农村"}, {"n": "儿童", "v": "儿童"},
            {"n": "网络电影", "v": "网络电影"}
        ]
        year_vals = [
            {"n": "全部", "v": ""}, {"n": "2026", "v": "2026"},
            {"n": "2025", "v": "2025"}, {"n": "2024", "v": "2024"},
            {"n": "2023", "v": "2023"}, {"n": "2022", "v": "2022"},
            {"n": "2021", "v": "2021"}, {"n": "2020", "v": "2020"},
            {"n": "2019", "v": "2019"}, {"n": "2018", "v": "2018"},
            {"n": "2017", "v": "2017"}, {"n": "2016", "v": "2016"},
            {"n": "2015", "v": "2015"}, {"n": "2014", "v": "2014"},
            {"n": "2013", "v": "2013"}, {"n": "2012", "v": "2012"},
            {"n": "2011", "v": "2011"}, {"n": "2010", "v": "2010"},
            {"n": "2009", "v": "2009"}, {"n": "2008", "v": "2008"},
            {"n": "2007", "v": "2007"}, {"n": "2006", "v": "2006"},
            {"n": "2005", "v": "2005"}, {"n": "2004", "v": "2004"},
            {"n": "2003", "v": "2003"}, {"n": "2002", "v": "2002"},
            {"n": "2001", "v": "2001"}, {"n": "2000", "v": "2000"}
        ]
        lang_vals = [
            {"n": "全部", "v": ""}, {"n": "国语", "v": "国语"},
            {"n": "英语", "v": "英语"}, {"n": "粤语", "v": "粤语"},
            {"n": "闽南语", "v": "闽南语"}, {"n": "韩语", "v": "韩语"},
            {"n": "日语", "v": "日语"}, {"n": "法语", "v": "法语"},
            {"n": "德语", "v": "德语"}, {"n": "其它", "v": "其它"}
        ]
        order_vals = [
            {"n": "时间", "v": "time"}, {"n": "人气", "v": "hits"},
            {"n": "评分", "v": "score"}
        ]
        for c in classes:
            filters[c['type_id']] = [
                {"key": "area", "name": "地区", "value": area_vals},
                {"key": "class", "name": "类型", "value": class_vals},
                {"key": "year", "name": "年份", "value": year_vals},
                {"key": "lang", "name": "语言", "value": lang_vals},
                {"key": "order", "name": "排序", "value": order_vals}
            ]
        result["filters"] = filters
        return result

    def homeVideoContent(self):
        videos = []
        try:
            html = self._get(self.host)
            root = etree.HTML(html)
            items = root.xpath('//div[contains(@class, "myui-vodlist__box")]')
            for item in items:
                try:
                    video = self._parse_list_item(item)
                    if video:
                        videos.append(video)
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
            area = extend.get('area', '')
            cls = extend.get('class', '')
            year = extend.get('year', '')
            lang = extend.get('lang', '')
            order = extend.get('order', 'time')
            area = quote(area) if area else ''
            cls = quote(cls) if cls else ''
            year = quote(year) if year else ''
            lang = quote(lang) if lang else ''
            order = quote(order) if order else 'time'
            # 456电影网 vodshow URL 12 段：0类型 1地区 2排序 3类型 4语言 5字母 6-7空 8页码 9-10空 11年份
            segments = [str(tid), area, order, cls, lang, '', '', '', str(pg), '', '', year]
            url = f"{self.host}/vodshow/{'-'.join(segments)}.html"
            html = self._get(url)
            root = etree.HTML(html)
            items = root.xpath('//div[contains(@class, "myui-vodlist__box")]')
            for item in items:
                try:
                    video = self._parse_list_item(item)
                    if video:
                        videos.append(video)
                except Exception:
                    pass
            total_pages = 1
            page_links = root.xpath('//ul[contains(@class,"myui-page")]//a/@href')
            for href in page_links:
                m = re.search(r'/(?:vodshow|vodsearch)/[^-]*(?:-[^-]*)*-(\d+)---\.html', href)
                if m:
                    total_pages = max(total_pages, int(m.group(1)))
            if not page_links:
                # 无分页时默认只一页
                total_pages = 1
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
            detail_url = f"{self.host}/voddetail/{vod_id}.html"
            html = self._get(detail_url)
            root = etree.HTML(html)

            vod_name = ''
            title_elem = root.xpath('//div[contains(@class,"myui-content__detail")]//h1[@class="title"]')
            if title_elem:
                vod_name = self._parse_text(title_elem[0])
            if not vod_name:
                title = root.xpath('//title/text()')
                if title:
                    vod_name = title[0].split('_')[0].strip()

            vod_pic = ''
            thumb = root.xpath('//div[contains(@class,"myui-content__thumb")]//img')
            if thumb:
                vod_pic = thumb[0].get('data-original', '') or thumb[0].get('data-src', '') or thumb[0].get('src', '')
            vod_pic = self._fix_url(vod_pic)

            vod_year = ''
            vod_area = ''
            data_ps = root.xpath('//div[contains(@class,"myui-content__detail")]//p[contains(@class,"data")]')
            for p in data_ps:
                txt = self._parse_text(p)
                if '年份：' in txt and not vod_year:
                    year_links = p.xpath('.//a/text()')
                    for y in year_links:
                        y = y.strip()
                        if re.match(r'^\d{4}$', y):
                            vod_year = y
                            break
                if '地区：' in txt and not vod_area:
                    area_links = p.xpath('.//a/text()')
                    for a in area_links:
                        a = a.strip()
                        if a:
                            vod_area = a
                            break

            vod_actor = ''
            actor_elem = root.xpath('//div[contains(@class,"myui-content__detail")]//p[contains(@class,"data") and contains(.,"主演：")]')
            if actor_elem:
                actors = actor_elem[0].xpath('.//a/text()')
                vod_actor = ' '.join([a.strip() for a in actors if a.strip()])

            vod_director = ''
            director_elem = root.xpath('//div[contains(@class,"myui-content__detail")]//p[contains(@class,"data") and contains(.,"导演：")]')
            if director_elem:
                directors = director_elem[0].xpath('.//a/text()')
                vod_director = ' '.join([d.strip() for d in directors if d.strip()])

            vod_content = ''
            desc_elem = root.xpath('//div[contains(@class,"text-collapse")]//span[contains(@class,"data")]')
            if desc_elem:
                vod_content = self._parse_text(desc_elem[0])
            if not vod_content:
                desc_elem = root.xpath('//div[contains(@class,"text-collapse")]')
                if desc_elem:
                    vod_content = self._parse_text(desc_elem[0])
            vod_content = re.sub(r'想要看更多的.*$', '', vod_content).strip()

            vod_play_from = []
            vod_play_url = []
            # 先尝试带 tab 的播放列表结构
            source_tabs = root.xpath('//div[contains(@class,"myui-panel__head")]//ul[contains(@class,"nav-tabs")]//a')
            tab_panes = root.xpath('//div[contains(@class,"tab-content")]//div[contains(@class,"tab-pane")]')
            if source_tabs and tab_panes:
                for idx, tab in enumerate(source_tabs):
                    source_name = self._parse_text(tab)
                    source_name = re.sub(r'\s+', ' ', source_name).strip()
                    if not source_name:
                        source_name = f"线路{idx + 1}"
                    if idx < len(tab_panes):
                        pane = tab_panes[idx]
                    else:
                        continue
                    links = pane.xpath('.//ul[contains(@class,"myui-content__list")]//a')
                    play_list = []
                    for a in links:
                        ep_name = a.text or a.get('title', '')
                        ep_name = ep_name.strip()
                        href = a.get('href', '')
                        if not ep_name or not href:
                            continue
                        play_url = self._fix_url(href)
                        play_list.append(f"{ep_name}${play_url}")
                    if play_list:
                        vod_play_from.append(source_name)
                        vod_play_url.append("#".join(play_list))
            else:
                # 兜底：直接取播放地址列表
                links = root.xpath('//ul[contains(@class,"myui-content__list")]//a')
                play_list = []
                for a in links:
                    ep_name = a.text or a.get('title', '')
                    ep_name = ep_name.strip()
                    href = a.get('href', '')
                    if not ep_name or not href:
                        continue
                    play_url = self._fix_url(href)
                    play_list.append(f"{ep_name}${play_url}")
                if play_list:
                    vod_play_from.append("默认")
                    vod_play_url.append("#".join(play_list))

            if vod_play_from:
                vod_play_from_str = "$$$".join(vod_play_from)
                vod_play_url_str = "$$$".join(vod_play_url)
            else:
                vod_play_from_str = "默认"
                vod_play_url_str = ""

            detail = {
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_year": vod_year,
                "vod_area": vod_area,
                "vod_actor": vod_actor,
                "vod_director": vod_director,
                "vod_content": vod_content,
                "vod_play_from": vod_play_from_str,
                "vod_play_url": vod_play_url_str
            }
            return {'list': [detail]}
        except Exception:
            return {'list': []}

    def _extract_player_url(self, html):
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
            player_data = json.loads(html[start:i])
            return player_data.get('url', '')
        except Exception:
            return None

    def playerContent(self, flag, id, vipFlags):
        try:
            html = self._get(id)
            real_url = self._extract_player_url(html)
            if real_url:
                real_url = real_url.replace('\\/', '/')
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
                real_url = m3u8_match.group(1)
                return {"parse": 0, "playUrl": "", "url": real_url, "header": json.dumps(self.header)}
            mp4_match = re.search(r'["\'](https?://[^"\']+\.(?:mp4|flv|ts))["\']', html)
            if mp4_match:
                real_url = mp4_match.group(1)
                return {"parse": 0, "playUrl": "", "url": real_url, "header": json.dumps(self.header)}
            return {"parse": 1, "playUrl": "", "url": id, "header": json.dumps(self.header)}
        except Exception:
            return {"parse": 0, "playUrl": "", "url": ""}

    def searchContent(self, key, quick, pg='1'):
        videos = []
        try:
            qkey = quote(key)
            if str(pg) == '1':
                url = f"{self.host}/vodsearch/{qkey}-------------.html"
            else:
                url = f"{self.host}/vodsearch/{qkey}--------{pg}---.html"
            html = self._get(url)
            root = etree.HTML(html)
            items = root.xpath('//div[contains(@class, "myui-vodlist__box")]')
            for item in items:
                try:
                    video = self._parse_list_item(item)
                    if video:
                        videos.append(video)
                except Exception:
                    pass
            total_pages = 1
            page_links = root.xpath('//ul[contains(@class,"myui-page")]//a/@href')
            for href in page_links:
                m = re.search(r'/vodsearch/[^/]+-(\d+)---\.html', href)
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

    def isVideoFormat(self, url):
        return any(url.lower().endswith(fmt) for fmt in ['.m3u8', '.mp4', '.flv', '.ts'])

    def manualVideoCheck(self):
        pass

    def localProxy(self, params):
        return None

    def destroy(self):
        pass
