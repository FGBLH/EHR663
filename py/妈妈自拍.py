# -*- coding: utf-8 -*-
"""
妈妈自拍全集(spider for mmzp18.lol) 终极修复版
修复：分类视频分配不均匀问题，强化 data.js 提取与智能分配
"""
import sys
import re
import json
import requests
import urllib3
import time
import random
from urllib.parse import urljoin, urlparse

urllib3.disable_warnings()
sys.path.append('..')
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    hosts = ['https://mmzp18.lol']
    host = hosts[0]
    session = None
    _debug = True
    _categories = []
    _all_videos = {}          # {分类名: [视频对象列表]}
    _data_loaded = False
    _cookie = {}

    AD_TITLE_FILTER = ['广告', '推广', '合作', 'APP', '下载', '注册', '菠菜', '博彩', '棋牌']
    AD_DOMAIN_FILTER = ['doubleclick', 'adservice', 'adsystem', 'adnxs', 'openx', 'casalemedia']

    FALLBACK_CATEGORIES = [
        '国产精品', '华语精品', '黑料吃瓜', '欧美大屌',
        '动漫禁漫', '学生合集', '乱伦精品', '探花约炮',
        '日本无码', '主播网红'
    ]

    def _log(self, msg):
        if self._debug:
            print(f'[mmzp] {msg}')

    def getName(self):
        return '妈妈自拍全集'

    def isVideoFormat(self, url):
        return url and ('.m3u8' in url or '.mp4' in url or '.ts' in url)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        if self.session:
            self.session.close()

    def localProxy(self, param):
        EMPTY_GIF = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
        if not param or not param.startswith('http'):
            return [200, 'image/gif', EMPTY_GIF]
        try:
            r = self.session.get(param, headers={'User-Agent': 'Mozilla/5.0', 'Referer': self.host + '/'}, timeout=(10, 15))
            r.raise_for_status()
            return [200, r.headers.get('Content-Type', 'application/octet-stream'), r.content]
        except:
            return [200, 'image/gif', EMPTY_GIF]

    def _get_headers(self, referer=None):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': referer or self.host + '/',
        }
        if self._cookie:
            headers['Cookie'] = '; '.join([f'{k}={v}' for k, v in self._cookie.items()])
        return headers

    def _fetch(self, url, referer=None, retries=3, allow_redirects=False):
        for attempt in range(retries):
            try:
                if attempt > 0:
                    time.sleep(random.uniform(0.5, 1.5))
                r = self.session.get(url, headers=self._get_headers(referer),
                                    timeout=(10, 20), verify=False,
                                    allow_redirects=allow_redirects)
                if r.cookies:
                    self._cookie.update(r.cookies.get_dict())
                if r.status_code in (301, 302, 303, 307, 308):
                    location = r.headers.get('Location', '')
                    if location:
                        location = urljoin(url, location)
                        if self._is_same_domain(location) and not self._is_ad_domain(location):
                            return self._fetch(location, referer=referer, allow_redirects=False)
                        else:
                            self._log(f'阻止跳转: {location}')
                            return ''
                    return ''
                elif r.status_code == 200:
                    r.encoding = 'utf-8'
                    return r.text
                else:
                    self._log(f'请求失败 [{r.status_code}] {url}')
                    return ''
            except Exception as e:
                self._log(f'请求异常 {e}，重试 {attempt+1}')
                continue
        return ''

    def _is_same_domain(self, url):
        try:
            return urlparse(url).netloc == urlparse(self.host).netloc
        except:
            return False

    def _is_ad_domain(self, url):
        return any(ad in url.lower() for ad in self.AD_DOMAIN_FILTER)

    # ========== 核心解析：强化 videosData 提取 ==========
    def _extract_js_var(self, text, var_name):
        """括号计数精确截取变量值"""
        # 支持 var / let / const / window.xxx 等多种赋值方式
        pattern = rf'(?:var\s+|let\s+|const\s+|window\.)?{re.escape(var_name)}\s*=\s*'
        match = re.search(pattern, text)
        if not match:
            return None
        start = match.end()
        while start < len(text) and text[start] in ' \t\n\r':
            start += 1
        if start >= len(text) or text[start] not in '[{':
            return None
        open_char = text[start]
        close_char = ']' if open_char == '[' else '}'
        stack = 0
        in_str = False
        escape = False
        for i in range(start, len(text)):
            c = text[i]
            if escape:
                escape = False
                continue
            if c == '\\':
                escape = True
                continue
            if c in ('"', "'"):
                if not in_str:
                    in_str = c
                elif in_str == c:
                    in_str = False
                continue
            if in_str:
                continue
            if c == open_char:
                stack += 1
            elif c == close_char:
                stack -= 1
                if stack == 0:
                    return text[start:i+1]
        return None

    def _safe_json_parse(self, js_str):
        """JSON解析容错"""
        cleaned = re.sub(r'//.*?\n|/\*.*?\*/', '', js_str, flags=re.S)
        cleaned = cleaned.replace("'", '"')
        cleaned = re.sub(r',\s*([}\]])', r'\1', cleaned)
        try:
            return json.loads(cleaned)
        except:
            return None

    def _parse_data_js(self, text):
        categories = []
        videos_data = {}

        # 提取 categories
        cats_raw = self._extract_js_var(text, 'categories')
        if cats_raw:
            cats_list = self._safe_json_parse(cats_raw)
            if isinstance(cats_list, list):
                for c in cats_list:
                    if isinstance(c, dict) and 'name' in c:
                        name = c['name']
                        if not any(k in name for k in self.AD_TITLE_FILTER):
                            categories.append({'type_id': name, 'type_name': name, 'type': 'vod'})

        # 提取 videosData
        vd_raw = self._extract_js_var(text, 'videosData')
        if vd_raw:
            vd = self._safe_json_parse(vd_raw)
            if isinstance(vd, dict):
                videos_data = vd

        return categories, videos_data

    def _extract_video_objects_robust(self, text):
        """通用提取所有 {name, url, video} 简单对象（无嵌套）"""
        objects = []
        # 匹配内部无嵌套大括号且必须包含 name 和 video 字段
        pattern = r'\{([^{}]*?"name"\s*:\s*"[^"]*"[^{}]*?"video"\s*:\s*"[^"]*"[^{}]*?)\}'
        matches = re.findall(pattern, text, re.S)
        for m in matches:
            try:
                json_str = '{' + m + '}'
                json_str = json_str.replace("'", '"')
                json_str = re.sub(r',\s*}', '}', json_str)
                obj = json.loads(json_str)
                if 'name' in obj and 'video' in obj:
                    objects.append(obj)
            except:
                continue
        return objects

    def _load_data(self):
        if self._data_loaded:
            return
        try:
            self._fetch(self.host + '/', allow_redirects=True)

            # 1. 从 data.js 标准提取（优先）
            js_url = urljoin(self.host, '/data.js')
            js_text = self._fetch(js_url)
            if js_text:
                cats, vids = self._parse_data_js(js_text)
                if cats:
                    self._categories = cats
                if vids:
                    self._all_videos = vids
                    self._log(f'标准解析成功：{len(cats)}个分类，{sum(len(v) for v in vids.values())}个视频')
                else:
                    self._log('videosData 解析失败，启用通用提取')

            # 2. 通用提取 + 智能分配
            if not self._all_videos:
                # 先确定分类（有则用，无则用备用）
                if not self._categories:
                    self._categories = [{'type_id': c, 'type_name': c, 'type': 'vod'} for c in self.FALLBACK_CATEGORIES]

                # 从 data.js 或首页脚本提取所有视频对象
                all_objs = []
                if js_text:
                    all_objs = self._extract_video_objects_robust(js_text)
                if not all_objs:
                    home_html = self._fetch(self.host + '/')
                    if home_html:
                        scripts = re.findall(r'<script[^>]*>(.*?)</script>', home_html, re.S)
                        for scr in scripts:
                            all_objs.extend(self._extract_video_objects_robust(scr))
                self._log(f'通用提取到 {len(all_objs)} 个视频对象')

                # 分配策略：优先使用对象中的 category/tag 字段，否则按标题关键词，再否则轮流分配
                organized = {cat['type_id']: [] for cat in self._categories}
                no_cat_objs = []

                for obj in all_objs:
                    cat_field = obj.get('category') or obj.get('tag')
                    if cat_field:
                        # 找到匹配的分类
                        assigned = False
                        for cat in self._categories:
                            if cat['type_id'] == cat_field or cat_field in cat['type_id']:
                                organized[cat['type_id']].append(obj)
                                assigned = True
                                break
                        if not assigned:
                            # 尝试模糊匹配
                            for cat in self._categories:
                                if cat['type_id'] in cat_field or cat_field in cat['type_id']:
                                    organized[cat['type_id']].append(obj)
                                    assigned = True
                                    break
                        if not assigned:
                            no_cat_objs.append(obj)
                    else:
                        no_cat_objs.append(obj)

                # 对于无法识别的视频，按顺序轮流分配到所有分类（避免全部堆在第一个）
                if no_cat_objs and self._categories:
                    for i, obj in enumerate(no_cat_objs):
                        cat_idx = i % len(self._categories)
                        cat_name = self._categories[cat_idx]['type_id']
                        organized[cat_name].append(obj)

                self._all_videos = organized
                total_assigned = sum(len(v) for v in organized.values())
                self._log(f'分配完毕，总计 {total_assigned} 个视频')

            # 3. 终极保底：确保每个分类都有键
            if not self._categories:
                self._categories = [{'type_id': c, 'type_name': c, 'type': 'vod'} for c in self.FALLBACK_CATEGORIES]
            for cat in self._categories:
                if cat['type_id'] not in self._all_videos:
                    self._all_videos[cat['type_id']] = []

            self._data_loaded = True
            self._log(f'最终状态：{len(self._categories)}个分类，各分类视频数量：{ {k:len(v) for k,v in self._all_videos.items()} }')
        except Exception as e:
            self._log(f'加载数据异常: {e}')
            self._categories = [{'type_id': c, 'type_name': c, 'type': 'vod'} for c in self.FALLBACK_CATEGORIES]
            self._all_videos = {c['type_id']: [] for c in self._categories}
            self._data_loaded = True

    def init(self, extend=''):
        self._log('初始化...')
        if self.session:
            self.session.close()
        self.session = requests.Session()
        self._load_data()

    def _filter_video(self, video):
        name = video.get('name') or video.get('vod_name') or ''
        return not any(k in name for k in self.AD_TITLE_FILTER)

    def _format_video(self, video):
        return {
            'vod_id': video.get('video') or video.get('vod_id') or '',
            'vod_name': video.get('name') or video.get('vod_name') or '未知',
            'vod_pic': urljoin(self.host, video.get('url') or '') if video.get('url') else '',
            'vod_remarks': '',
        }

    # ---------- 首页 ----------
    def homeContent(self, filter=False):
        try:
            self._load_data()
            home_list = []
            for vids in self._all_videos.values():
                for v in vids:
                    if self._filter_video(v):
                        home_list.append(self._format_video(v))
                    if len(home_list) >= 30:
                        break
                if len(home_list) >= 30:
                    break
            return {'class': self._categories, 'list': home_list}
        except Exception as e:
            self._log(f'homeContent 异常: {e}')
            return {'class': [], 'list': []}

    def homeVideoContent(self):
        return self.homeContent()

    # ---------- 分类列表 ----------
    def categoryContent(self, tid, pg, filter=False, extend=''):
        try:
            self._load_data()
            page = int(pg) if pg else 1
            cat_name = str(tid)
            vids = self._all_videos.get(cat_name, [])
            # 极少情况：分类无缓存，实时抓取分类页
            if not vids:
                cat_url = urljoin(self.host, f'/category.html?type={cat_name}')
                html = self._fetch(cat_url)
                if html:
                    objs = self._extract_video_objects_robust(html)
                    if not objs:
                        vid_links = re.findall(r'vid=([^&"\']+)', html)
                        objs = [{'name': '未知', 'video': vid, 'url': ''} for vid in vid_links]
                    vids = objs
                    self._all_videos[cat_name] = vids
            filtered = [self._format_video(v) for v in vids if self._filter_video(v)]
            per_page = 24
            total = len(filtered)
            total_pages = max(1, (total + per_page - 1) // per_page)
            start = (page - 1) * per_page
            return {'list': filtered[start:start+per_page], 'page': page, 'pagecount': total_pages}
        except Exception as e:
            self._log(f'categoryContent 异常: {e}')
            return {'list': [], 'page': 1, 'pagecount': 1}

    # ---------- 播放地址 ----------
    def _get_play_url(self, video_obj):
        vid = video_obj.get('video') or video_obj.get('vod_id') or ''
        if not vid:
            return None
        if vid.startswith('http') and self.isVideoFormat(vid):
            return vid
        for key in ['play_url', 'm3u8', 'src']:
            if video_obj.get(key) and self.isVideoFormat(video_obj[key]):
                return video_obj[key]
        play_url = urljoin(self.host, f'/play.html?vid={vid}')
        html = self._fetch(play_url)
        if html:
            m3u8 = self._extract_m3u8(html)
            if m3u8:
                return m3u8
            for iframe in re.findall(r'<iframe[^>]+src="([^"]*)"', html):
                iframe_url = urljoin(self.host, iframe)
                iframe_html = self._fetch(iframe_url)
                if iframe_html:
                    m3u8 = self._extract_m3u8(iframe_html)
                    if m3u8:
                        return m3u8
        return None

    def _extract_m3u8(self, html):
        patterns = [
            r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)',
            r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*)',
            r'["\'](?:url|src)["\']\s*:\s*["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)',
            r'file:\s*["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)',
        ]
        for pat in patterns:
            match = re.search(pat, html, re.I)
            if match:
                url = match.group(1).replace('\\/', '/')
                if self.isVideoFormat(url) and not self._is_ad_domain(url):
                    return url
        return None

    def detailContent(self, ids):
        try:
            self._load_data()
            vid = str(ids[0] if isinstance(ids, list) else ids)
            target = None
            for vids in self._all_videos.values():
                for v in vids:
                    if str(v.get('video')) == vid:
                        target = v
                        break
                if target:
                    break
            if not target:
                target = {'video': vid, 'name': vid, 'url': ''}
            play_url = self._get_play_url(target)
            vod_play_from = '默认'
            vod_play_url = ''
            if play_url:
                vod_play_url = f'默认${play_url}'
            return {'list': [{
                'vod_id': vid,
                'vod_name': target.get('name', '未知'),
                'vod_pic': urljoin(self.host, target.get('url', '')) if target.get('url') else '',
                'vod_play_from': vod_play_from,
                'vod_play_url': vod_play_url
            }]}
        except Exception as e:
            self._log(f'detailContent 异常: {e}')
            return {'list': [{'vod_id': '', 'vod_name': '错误', 'vod_play_from': '', 'vod_play_url': ''}]}

    def playerContent(self, flag, id, vipFlags=None):
        if id:
            id = id.replace('\\/', '/')
        if any(ad in id.lower() for ad in self.AD_DOMAIN_FILTER):
            return {'parse': 0, 'url': '', 'header': {}}
        if id.startswith('http') and ('.m3u8' in id or '.mp4' in id):
            return {'parse': 0, 'url': id, 'header': {'Referer': self.host}}
        return {'parse': 1, 'url': id, 'header': {'Referer': self.host}}

    def searchContent(self, key, quick, pg='1'):
        try:
            self._load_data()
            page = int(pg)
            results = []
            for vids in self._all_videos.values():
                for v in vids:
                    if key in (v.get('name') or '') and self._filter_video(v):
                        results.append(self._format_video(v))
            per_page = 24
            total = len(results)
            total_pages = max(1, (total + per_page - 1) // per_page)
            start = (page - 1) * per_page
            return {'list': results[start:start+per_page], 'page': page, 'pagecount': total_pages}
        except Exception as e:
            self._log(f'searchContent 异常: {e}')
            return {'list': [], 'page': 1, 'pagecount': 1}
