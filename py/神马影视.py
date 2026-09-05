# coding=utf-8
import re, json, requests, urllib3
from urllib.parse import quote
from lxml import etree
from base.spider import Spider

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class Spider(Spider):
    def __init__(self):
        self.name = "smys"
        self.host = "https://www.china-eae.com"
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
        r = requests.get(url, headers=self.header, params=params, timeout=15, verify=False)
        r.encoding = 'utf-8'
        return r.text

    def _post(self, url, data=None):
        r = requests.post(url, headers=self.header, data=data, timeout=15, verify=False)
        r.encoding = 'utf-8'
        return r.text

    def _fix_url(self, url):
        if not url:
            return ''
        url = url.strip().strip('`')
        if url.startswith('/img.php?url='):
            url = url[len('/img.php?url='):]
        url = url.strip().strip('`')
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('/'):
            return self.host + url
        return url

    def _parse_pic(self, elem):
        pic = ''
        if elem is None:
            return pic
        # 元素自身可能带 data-original（列表页的 a 标签）
        pic = elem.get('data-original') or elem.get('data-src') or ''
        if not pic and elem.tag == 'img':
            pic = elem.get('src', '')
        if not pic:
            imgs = elem.xpath('.//img')
            if imgs:
                pic = imgs[0].get('data-original') or imgs[0].get('data-src') or imgs[0].get('src', '')
        if pic and pic.startswith('data:image'):
            pic = ''
        return self._fix_url(pic)

    def _parse_text(self, elem):
        if elem is None:
            return ''
        return ''.join(elem.itertext()).strip()

    def _extract_id(self, href):
        m = re.search(r'/about/(\d+)\.html', href)
        return m.group(1) if m else ''

    def _parse_list_item(self, item):
        thumb = item.xpath('.//a[contains(@class, "stui-vodlist__thumb")]')
        if not thumb:
            return None
        thumb = thumb[0]
        href = thumb.get('href', '')
        vod_id = self._extract_id(href)
        if not vod_id:
            return None
        vod_name = thumb.get('title', '').strip()
        if not vod_name:
            title_a = item.xpath('.//h4[contains(@class, "title")]/a')
            if title_a:
                vod_name = self._parse_text(title_a[0])
        vod_pic = self._parse_pic(thumb)

        remark = ''
        pic_text = item.xpath('.//span[contains(@class, "pic-text")]/text()')
        if pic_text:
            remark = pic_text[0].strip()

        return {
            "vod_id": vod_id,
            "vod_name": vod_name,
            "vod_pic": vod_pic,
            "vod_remarks": remark
        }

    def homeContent(self, filter):
        result = {"class": []}
        classes = [
            {"type_name": "电影", "type_id": "dianying"},
            {"type_name": "电视剧", "type_id": "dianshiju"},
            {"type_name": "综艺片", "type_id": "zongyipian"},
            {"type_name": "动漫片", "type_id": "dongmanpian"},
            {"type_name": "预告片", "type_id": "yugaopian"},
            {"type_name": "体育赛事", "type_id": "tiyusaishi"},
            {"type_name": "短剧大全", "type_id": "duanjudaquan"},
            {"type_name": "电影解说", "type_id": "dianyingjieshuo"}
        ]
        result["class"] = classes

        area_vals = [
            {"n": "全部", "v": ""}, {"n": "大陆", "v": "大陆"},
            {"n": "香港", "v": "香港"}, {"n": "台湾", "v": "台湾"},
            {"n": "美国", "v": "美国"}, {"n": "日本", "v": "日本"},
            {"n": "韩国", "v": "韩国"}, {"n": "泰国", "v": "泰国"},
            {"n": "英国", "v": "英国"}, {"n": "法国", "v": "法国"},
            {"n": "德国", "v": "德国"}, {"n": "意大利", "v": "意大利"},
            {"n": "西班牙", "v": "西班牙"}, {"n": "加拿大", "v": "加拿大"},
            {"n": "印度", "v": "印度"}, {"n": "其他", "v": "其他"}
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
            {"n": "古装", "v": "古装"}, {"n": "历史", "v": "历史"},
            {"n": "运动", "v": "运动"}, {"n": "儿童", "v": "儿童"},
            {"n": "网络电影", "v": "网络电影"}, {"n": "纪录片", "v": "纪录片"}
        ]
        year_vals = [{"n": "全部", "v": ""}]
        for y in range(2026, 1989, -1):
            year_vals.append({"n": str(y), "v": str(y)})
        year_vals.append({"n": "80年代", "v": "80年代"})
        year_vals.append({"n": "更早", "v": "更早"})

        lang_vals = [
            {"n": "全部", "v": ""}, {"n": "国语", "v": "国语"},
            {"n": "粤语", "v": "粤语"}, {"n": "闽南语", "v": "闽南语"},
            {"n": "英语", "v": "英语"}, {"n": "日语", "v": "日语"},
            {"n": "韩语", "v": "韩语"}, {"n": "法语", "v": "法语"},
            {"n": "德语", "v": "德语"}, {"n": "其它", "v": "其它"}
        ]
        letter_vals = [{"n": "全部", "v": ""}]
        for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            letter_vals.append({"n": c, "v": c})
        letter_vals.append({"n": "0-9", "v": "0-9"})
        order_vals = [
            {"n": "最新", "v": "time"},
            {"n": "最热", "v": "hits"},
            {"n": "评分", "v": "score"}
        ]

        filters = {}
        for c in classes:
            filters[c['type_id']] = [
                {"key": "area", "name": "地区", "value": area_vals},
                {"key": "class", "name": "类型", "value": class_vals},
                {"key": "lang", "name": "语言", "value": lang_vals},
                {"key": "letter", "name": "字母", "value": letter_vals},
                {"key": "year", "name": "年份", "value": year_vals},
                {"key": "order", "name": "排序", "value": order_vals}
            ]
        result["filters"] = filters
        return result

    def homeVideoContent(self):
        videos = []
        try:
            html = self._get(self.host)
            root = etree.HTML(html)
            videos = self._parse_video_list(root)
        except Exception:
            pass
        return {"list": videos}

    def _parse_video_list(self, root):
        videos = []
        if root is None:
            return videos
        items = root.xpath('//div[contains(@class, "stui-vodlist__box")]')
        seen = set()
        for item in items:
            try:
                video = self._parse_list_item(item)
                if video and video.get('vod_id') and video['vod_id'] not in seen:
                    seen.add(video['vod_id'])
                    videos.append(video)
            except Exception:
                pass
        return videos

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
            letter = extend.get('letter', '')
            order = extend.get('order', 'time')

            # URL 规则：/lstd/{tid}/area/{area}/by/{order}/class/{class}/lang/{lang}/letter/{letter}/year/{year}/page/{pg}.html
            segments = [f"/lstd/{tid}"]
            if area:
                segments.append(f"area/{quote(area)}")
            if order:
                segments.append(f"by/{quote(order)}")
            if cls:
                segments.append(f"class/{quote(cls)}")
            if lang:
                segments.append(f"lang/{quote(lang)}")
            if letter:
                segments.append(f"letter/{quote(letter)}")
            if year:
                segments.append(f"year/{quote(year)}")
            if int(pg) > 1:
                segments.append(f"page/{pg}")
            url = self.host + '/'.join(segments) + ".html"

            html = self._get(url)
            root = etree.HTML(html)
            videos = self._parse_video_list(root)

            total_pages = 1
            # 解析分页，页码文本形如 "1/1665"
            page_texts = root.xpath('//text()[contains(., "/")]')
            for t in page_texts:
                tm = re.search(r'(\d+)\s*/\s*(\d+)', t)
                if tm:
                    total_pages = max(total_pages, int(tm.group(2)))
                    break
            # 兜底：取最大页码链接
            links = root.xpath('//a[contains(@href, "/page/")]')
            for link in links:
                tm = re.search(r'/page/(\d+)\.html', link.get('href', ''))
                if tm:
                    total_pages = max(total_pages, int(tm.group(1)))

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
            detail_url = f"{self.host}/about/{vod_id}.html"
            html = self._get(detail_url)
            root = etree.HTML(html)

            # 标题
            vod_name = ''
            title_elem = root.xpath('//div[contains(@class, "stui-content__detail")]/h1[contains(@class, "title")]')
            if title_elem:
                # 去掉评分 span
                for span in title_elem[0].xpath('.//span'):
                    span.getparent().remove(span)
                vod_name = self._parse_text(title_elem[0])
            if not vod_name:
                title = root.xpath('//title/text()')
                if title:
                    vod_name = title[0].split('-')[0].strip()
            vod_name = vod_name.strip()

            # 封面
            vod_pic = ''
            thumb_img = root.xpath('//div[contains(@class, "stui-content__thumb")]//img')
            if thumb_img:
                vod_pic = self._parse_pic(thumb_img[0])

            # 信息行
            info_lines = root.xpath('//div[contains(@class, "stui-content__detail")]/p[contains(@class, "data")]')

            def _line_text_containing(keyword):
                for line in info_lines:
                    txt = self._parse_text(line)
                    if keyword in txt:
                        return txt
                return ''

            # 类型/地区/年份（在同一行）
            first_line = _line_text_containing('类型')
            vod_type = ''
            vod_area = ''
            vod_year = ''
            if first_line:
                m = re.search(r'类型[：:]\s*([^\s&]+)', first_line)
                if m:
                    vod_type = m.group(1).strip()
                m = re.search(r'地区[：:]\s*([^\s&]+)', first_line)
                if m:
                    vod_area = m.group(1).strip()
                m = re.search(r'年份[：:]\s*(\d{4})', first_line)
                if m:
                    vod_year = m.group(1)

            # 主演
            vod_actor = ''
            actor_line = None
            for line in info_lines:
                txt = self._parse_text(line)
                if '主演' in txt:
                    actor_line = line
                    break
            if actor_line is not None:
                actors = actor_line.xpath('.//a/text()')
                vod_actor = ' '.join([a.strip() for a in actors if a.strip()])

            # 导演
            vod_director = ''
            director_line = None
            for line in info_lines:
                txt = self._parse_text(line)
                if '导演' in txt:
                    director_line = line
                    break
            if director_line is not None:
                directors = director_line.xpath('.//a/text()')
                vod_director = ' '.join([d.strip() for d in directors if d.strip()])

            # 更新/状态
            vod_remarks = ''
            for line in info_lines:
                txt = self._parse_text(line)
                if '更新' in txt:
                    m = re.search(r'更新[：:]\s*([^\n]+)', txt)
                    if m:
                        vod_remarks = m.group(1).strip()
                    break

            # 简介
            vod_content = ''
            desc_elem = root.xpath('//div[contains(@class, "stui-content__detail")]/p[contains(@class, "desc")]')
            if desc_elem:
                # 去掉“详情”链接
                for a in desc_elem[0].xpath('.//a'):
                    a.getparent().remove(a)
                vod_content = self._parse_text(desc_elem[0])
                vod_content = re.sub(r'^[\s\n]*简介[：:]\s*', '', vod_content)
            if not vod_content:
                desc_p = root.xpath('//div[@id="desc"]//p[contains(@class, "col-pd")]')
                if desc_p:
                    vod_content = self._parse_text(desc_p[0]).strip()

            # 播放源
            vod_play_from = []
            vod_play_url = []
            source_boxes = root.xpath('//div[contains(@class, "stui-pannel-box") and contains(@class, "playlist")]')
            for box in source_boxes:
                head = box.xpath('.//div[contains(@class, "stui-pannel__head")]//h3[contains(@class, "title")]')
                if not head:
                    continue
                source_name = self._parse_text(head[0]).strip()
                source_name = re.sub(r'\s+', ' ', source_name)
                if not source_name:
                    continue
                links = box.xpath('.//ul[contains(@class, "stui-content__playlist")]//a')
                play_list = []
                for a in links:
                    ep_name = self._parse_text(a)
                    href = a.get('href', '')
                    if not ep_name or not href:
                        continue
                    play_list.append(f"{ep_name}${self._fix_url(href)}")
                if play_list:
                    vod_play_from.append(source_name)
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
                "vod_remarks": vod_remarks,
                "vod_play_from": vod_play_from_str,
                "vod_play_url": vod_play_url_str
            }
            return {'list': [detail]}
        except Exception:
            return {'list': []}

    def _extract_player_url(self, html):
        # 常见 AppleCMS 播放器变量
        for pattern in [
            r'var\s+player_aaaa\s*=\s*\{',
            r'var\s+player_data\s*=\s*\{',
            r'var\s+player\s*=\s*\{',
            r'var\s+config\s*=\s*\{',
        ]:
            m = re.search(pattern, html)
            if m:
                start = m.end() - 1
                depth = 1
                i = start + 1
                while i < len(html) and depth > 0:
                    if html[i] == '{':
                        depth += 1
                    elif html[i] == '}':
                        depth -= 1
                    i += 1
                try:
                    data = json.loads(html[start:i])
                    url = data.get('url') or data.get('video', {}).get('url', '')
                    if url:
                        return url
                except Exception:
                    pass
        # 直接提取 m3u8/mp4
        m = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', html)
        if m:
            return m.group(1)
        m = re.search(r'["\'](https?://[^"\']+\.(?:mp4|flv|ts))["\']', html)
        if m:
            return m.group(1)
        # iframe
        m = re.search(r'<iframe[^>]+src\s*=\s*["\']([^"\']+)["\']', html)
        if m:
            return m.group(1)
        return None

    def playerContent(self, flag, id, vipFlags):
        try:
            html = self._get(id)
            real_url = self._extract_player_url(html)
            if real_url:
                real_url = self._fix_url(real_url)
                parse_flag = 0 if self.isVideoFormat(real_url) else 1
                return {"parse": parse_flag, "playUrl": "", "url": real_url, "header": json.dumps(self.header)}
            return {"parse": 1, "playUrl": "", "url": id, "header": json.dumps(self.header)}
        except Exception:
            return {"parse": 0, "playUrl": "", "url": ""}

    def searchContent(self, key, quick, pg='1'):
        videos = []
        try:
            params = {"wd": key}
            if int(pg) > 1:
                params["page"] = pg
            url = f"{self.host}/msfw/search/-------------.html"
            html = self._get(url, params=params)
            root = etree.HTML(html)
            videos = self._parse_video_list(root)

            total_pages = 1
            page_texts = root.xpath('//text()[contains(., "/")]')
            for t in page_texts:
                tm = re.search(r'(\d+)\s*/\s*(\d+)', t)
                if tm:
                    total_pages = max(total_pages, int(tm.group(2)))
                    break
            links = root.xpath('//a[contains(@href, "/page/")]')
            for link in links:
                tm = re.search(r'/page/(\d+)\.html', link.get('href', ''))
                if tm:
                    total_pages = max(total_pages, int(tm.group(1)))

            return {
                'list': videos,
                'page': int(pg),
                'pagecount': total_pages,
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
