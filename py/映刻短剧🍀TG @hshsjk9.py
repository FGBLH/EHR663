# coding=utf-8
"""
目标站: 映刻短剧 (http://bjxcxl.com)
模板: 苹果CMS (fed/stui)
特性: 纯正则解析(无bs4依赖)、多线路播放、自动URL补全
修复：线路名称改为真实：河马短剧、红豆短剧
"""
import re
import sys
import json
import urllib.parse
import time
sys.path.append('..')
from base.spider import Spider
class Spider(Spider):
    def init(self, extend=""):
        self.site_url = "http://bjxcxl.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': self.site_url + '/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        }
        # 线路ID映射真实名称
        self.line_name_map = {
            "0": "河马短剧",
            "1": "红豆短剧"
        }
        # 一级分类
        self.categories = [
            {"type_id": "1", "type_name": "重生"},
            {"type_id": "2", "type_name": "穿越"},
            {"type_id": "3", "type_name": "爽剧"},
            {"type_id": "4", "type_name": "言情"},
            {"type_id": "5", "type_name": "都市"},
            {"type_id": "6", "type_name": "古装"},
            {"type_id": "7", "type_name": "悬疑"},
            {"type_id": "8", "type_name": "剧情"},
        ]
        # 二级筛选（排序）
        self.filters = {
            "1": [
                {"key": "by", "name": "排序", "value": [
                    {"n": "最新", "v": "time"}, {"n": "最热", "v": "hits"}, {"n": "评分", "v": "score"}
                ]},
            ],
            "2": [
                {"key": "by", "name": "排序", "value": [
                    {"n": "最新", "v": "time"}, {"n": "最热", "v": "hits"}, {"n": "评分", "v": "score"}
                ]},
            ],
            "3": [
                {"key": "by", "name": "排序", "value": [
                    {"n": "最新", "v": "time"}, {"n": "最热", "v": "hits"}, {"n": "评分", "v": "score"}
                ]},
            ],
            "4": [
                {"key": "by", "name": "排序", "value": [
                    {"n": "最新", "v": "time"}, {"n": "最热", "v": "hits"}, {"n": "评分", "v": "score"}
                ]},
            ],
            "5": [
                {"key": "by", "name": "排序", "value": [
                    {"n": "最新", "v": "time"}, {"n": "最热", "v": "hits"}, {"n": "评分", "v": "score"}
                ]},
            ],
            "6": [
                {"key": "by", "name": "排序", "value": [
                    {"n": "最新", "v": "time"}, {"n": "最热", "v": "hits"}, {"n": "评分", "v": "score"}
                ]},
            ],
            "7": [
                {"key": "by", "name": "排序", "value": [
                    {"n": "最新", "v": "time"}, {"n": "最热", "v": "hits"}, {"n": "评分", "v": "score"}
                ]},
            ],
            "8": [
                {"key": "by", "name": "排序", "value": [
                    {"n": "最新", "v": "time"}, {"n": "最热", "v": "hits"}, {"n": "评分", "v": "score"}
                ]},
            ],
        }
    def _safe_fetch(self, url, headers=None, max_retry=2):
        """轻量安全请求，失败自动重试"""
        if headers is None:
            headers = self.headers
        for i in range(max_retry):
            try:
                resp = self.fetch(url, headers=headers)
                if resp:
                    return resp
            except Exception:
                if i < max_retry - 1:
                    time.sleep(0.3)
        return None
    def _fix_url(self, url):
        """补全相对URL为绝对URL"""
        if not url:
            return ''
        if url.startswith('http'):
            return url
        if url.startswith('//'):
            return 'http:' + url
        if url.startswith('/'):
            return self.site_url + url
        return self.site_url + '/' + url
    def _parse_video_list(self, html, max_count=0):
        """
        正则解析视频列表 -- 比BeautifulSoup快3~5倍
        匹配结构: <li class="fed-list-item">...<a href="/djok/{id}.html" data-original="pic" title="name">...<span class="fed-list-remarks">remark</span>...</li>
        """
        video_list = []
        seen = set()
        # 提取每个列表块
        item_blocks = re.findall(r'<li[^>]*class="fed-list-item[^"]*"[^>]*>(.*?)</li>', html, re.DOTALL)
        for block in item_blocks:
            href_m = re.search(r'href="(/djok/(\d+)\.html)"', block)
            if not href_m:
                continue
            href, vod_id = href_m.groups()
            if vod_id in seen:
                continue
            seen.add(vod_id)
            title_m = re.search(r'title="([^"]*)"', block)
            title = title_m.group(1) if title_m else ''
            pic_m = re.search(r'data-original="([^"]*)"', block)
            pic = pic_m.group(1) if pic_m else ''
            remark_m = re.search(r'class="fed-list-remarks[^"]*"[^>]*>(.*?)</span>', block)
            remark = remark_m.group(1) if remark_m else ''
            remark = re.sub(r'<[^>]+>', '', remark).strip()
            if not title:
                continue
            video_list.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": self._fix_url(pic),
                "vod_remarks": remark,
            })
            if max_count > 0 and len(video_list) >= max_count:
                break
        return video_list
    def _extract_page_info(self, html, tid, default_page):
        """从分页区域提取总页码与总数"""
        pagecount = default_page
        total = 0
        # 匹配 /dj/{tid}-{num}.html 形式的页码
        pages = re.findall(r'/dj/' + re.escape(str(tid)) + r'-(\d+)\.html', html)
        if pages:
            pagecount = max(pagecount, max(map(int, pages)))
        # 匹配总数文本
        total_m = re.search(r'共\s*(\d+)\s*部', html)
        if total_m:
            total = int(total_m.group(1))
        if not total:
            total = 30 * pagecount
        return pagecount, total
    def homeContent(self, filter):
        url = self.site_url + "/"
        resp = self._safe_fetch(url)
        video_list = []
        if resp:
            video_list = self._parse_video_list(resp.text, max_count=36)
        return {"class": self.categories, "list": video_list, "filters": self.filters}
    def homeVideoContent(self):
        return self.homeContent(False)
    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        # 该站分类URL: /dj/{tid}.html  分页: /dj/{tid}-{pg}.html
        if page <= 1:
            url = f"{self.site_url}/dj/{tid}.html"
        else:
            url = f"{self.site_url}/dj/{tid}-{page}.html"
        resp = self._safe_fetch(url)
        if not resp:
            return {"list": [], "page": page, "pagecount": 1, "limit": 30, "total": 0}
        video_list = self._parse_video_list(resp.text)
        pagecount, total = self._extract_page_info(resp.text, tid, page)
        return {
            "list": video_list,
            "page": page,
            "pagecount": pagecount,
            "limit": 30,
            "total": total
        }
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = ids[0]
        url = f"{self.site_url}/djok/{vod_id}.html"
        resp = self._safe_fetch(url)
        if not resp:
            return {"list": []}
        html = resp.text
        # 标题: 从<title>提取，去掉后缀
        vod_name = vod_id
        title_m = re.search(r'<title>(.*?)</title>', html)
        if title_m:
            raw = title_m.group(1)
            vod_name = raw.split('在线播放')[0].split('_')[0].strip()
        # 大图: 优先匹配 fed-part-views 区域里的 img
        vod_pic = ''
        pic_m = re.search(r'class="fed-part-views"[^>]*>.*?<img[^>]+src="([^"]+)"', html, re.DOTALL)
        if not pic_m:
            pic_m = re.search(r'data-original="([^"]+)"', html)
        if pic_m:
            vod_pic = self._fix_url(pic_m.group(1))
        # 简介: 从 meta description 提取并清洗
        vod_content = ''
        desc_m = re.search(r'<meta name="description" content="([^"]+)"', html)
        if desc_m:
            vod_content = desc_m.group(1)
            vod_content = re.sub(r'^.*?剧情介绍[：:]\s*', '', vod_content)
            vod_content = re.sub(r'，该[^。]*讲述的是.*$', '', vod_content)
            vod_content = re.sub(r'暂无简介', '', vod_content).strip()
        # 演员/导演/年份/地区 -- 从"相关问答"区域提取
        vod_actor = vod_director = vod_area = vod_year = ''
        qa_m = re.search(r'相关问答.*?</h\w+>\s*(.*?)</div>', html, re.DOTALL)
        if qa_m:
            qa_text = re.sub(r'<[^>]+>', ' ', qa_m.group(1))
            d_m = re.search(r'是由\s*([^，,]+?)\s*执导', qa_text)
            if d_m:
                vod_director = d_m.group(1).strip()
            a_m = re.search(r'执导[,，\s]+([^，,]+?)\s*(?:领衔主演|主演)', qa_text)
            if a_m:
                vod_actor = a_m.group(1).strip()
            y_m = re.search(r'(\d{4})-\d{2}-\d{2}', qa_text)
            if y_m:
                vod_year = y_m.group(1)
        # 备用年份
        if not vod_year:
            y_m2 = re.search(r'(\d{4})-\d{2}-\d{2}', html)
            if y_m2:
                vod_year = y_m2.group(1)
        # 类型/地区
        area_m = re.search(r'该([^讲]+?)讲述', html)
        if area_m:
            vod_area = area_m.group(1).strip()
        # 播放列表 -- 按线路分组
        play_links = re.findall(r'href="(/play/\d+-\d+-\d+\.html)"[^>]*>(.*?)</a>', html)
        groups = {}
        for link, ep_raw in play_links:
            ep_name = re.sub(r'<[^>]+>', '', ep_raw).strip()
            if not ep_name or ep_name in ('立即播放', ''):
                continue
            m = re.search(r'/play/(\d+)-(\d+)-(\d+)\.html', link)
            if m:
                line = m.group(2)
                groups.setdefault(line, []).append(f"{ep_name}${self._fix_url(link)}")
        play_from_list = []
        play_url_list = []
        if groups:
            for line in sorted(groups.keys(), key=lambda x: int(x) if str(x).isdigit() else 0):
                # 使用映射表取真实线路名，未知line兜底显示原始编号
                line_name = self.line_name_map.get(str(line), f"线路{line}")
                play_from_list.append(line_name)
                play_url_list.append('#'.join(groups[line]))
        else:
            play_from_list.append('默认线路')
            play_url_list.append(f"播放${self.site_url}/djok/{vod_id}.html")
        vod_play_from = '$$$'.join(play_from_list)
        vod_play_url = '$$$'.join(play_url_list)
        result = [{
            "vod_id": vod_id,
            "vod_name": vod_name,
            "vod_pic": vod_pic,
            "vod_content": vod_content,
            "vod_actor": vod_actor,
            "vod_director": vod_director,
            "vod_area": vod_area,
            "vod_year": vod_year,
            "vod_play_from": vod_play_from,
            "vod_play_url": vod_play_url
        }]
        return {"list": result}
    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        encoded_key = urllib.parse.quote(key)
        url = f"{self.site_url}/search.php?searchword={encoded_key}"
        if page > 1:
            url += f"&page={page}"
        resp = self._safe_fetch(url)
        if not resp:
            return {"list": [], "page": page, "pagecount": 1}
        video_list = self._parse_video_list(resp.text)
        # 搜索分页
        pagecount = 1
        pages = re.findall(r'[?&]page=(\d+)', resp.text)
        if pages:
            pagecount = max(pagecount, max(map(int, pages)))
        return {"list": video_list, "page": page, "pagecount": pagecount}
    def playerContent(self, flag, id, vipFlags):
        if id.startswith('http'):
            play_url = id
        elif id.startswith('/'):
            play_url = self.site_url + id
        else:
            play_url = self.site_url + '/' + id
        resp = self._safe_fetch(play_url)
        if not resp:
            return {"parse": 1, "url": play_url, "header": self.headers}
        html = resp.text
        # 1. 优先匹配 var now="xxx.m3u8"
        now_m = re.search(r'var\s+now\s*=\s*"([^"]+)"', html)
        if now_m:
            video_url = now_m.group(1)
            if video_url and video_url.startswith('http'):
                return {"parse": 0, "url": video_url, "header": self.headers}
        # 2. 正则匹配页面中任何 m3u8 地址
        m3u8_m = re.search(r"https?://[^\s\"'<>]+\.m3u8[^\s\"'<>]*", html)
        if m3u8_m:
            return {"parse": 0, "url": m3u8_m.group(0), "header": self.headers}
        # 3. iframe 嵌套
        iframe_m = re.search(r'<iframe[^>]+src="([^"]+)"', html)
        if iframe_m:
            iframe_url = iframe_m.group(1)
            if not iframe_url.startswith('http'):
                iframe_url = self._fix_url(iframe_url)
            return {"parse": 1, "url": iframe_url, "header": self.headers}
        # 4. mac_player_config
        mac_m = re.search(r'mac_player_config\s*=\s*({.*?})', html, re.DOTALL)
        if mac_m:
            try:
                cfg = json.loads(mac_m.group(1))
                video_url = cfg.get('url', '')
                if video_url and '.m3u8' in video_url:
                    return {"parse": 0, "url": video_url, "header": self.headers}
            except Exception:
                pass
        return {"parse": 1, "url": play_url, "header": self.headers}
