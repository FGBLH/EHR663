# -*- coding: utf-8 -*-
import sys
import re
import html as html_mod
import urllib.parse
import requests

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    def getName(self):
        return "美剧天堂"

    def init(self, context, extend=""):
        self.host = "https://www.meijutt.cc"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
            'Referer': self.host,
        }
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update(self.headers)

    def destroy(self):
        try:
            self.session.close()
        except:
            pass

    def _get(self, url, timeout=10):
        if url.startswith('/'):
            url = self.host + url
        try:
            r = self.session.get(url, timeout=timeout, verify=False, allow_redirects=True)
            r.encoding = 'utf-8'
            return r
        except:
            return None

    def _post(self, url, data, timeout=10):
        if url.startswith('/'):
            url = self.host + url
        try:
            headers = dict(self.headers)
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
            r = self.session.post(url, data=data, headers=headers, timeout=timeout, verify=False, allow_redirects=True)
            r.encoding = 'utf-8'
            return r
        except:
            return None

    def _clean(self, text):
        return re.sub(r'\s+', ' ', text).strip() if text else ''

    def _extract_text(self, html_str):
        text = re.sub(r'<[^>]+>', '', html_str).strip() if html_str else ''
        return html_mod.unescape(text)

    # ==================== 首页 ====================
    def homeContent(self, filter):
        classes = [
            {"type_id": "1", "type_name": "魔幻科幻"},
            {"type_id": "2", "type_name": "灵异惊悚"},
            {"type_id": "3", "type_name": "都市情感"},
            {"type_id": "4", "type_name": "犯罪历史"},
            {"type_id": "5", "type_name": "选秀综艺"},
            {"type_id": "6", "type_name": "动漫卡通"},
        ]
        return {"class": classes, "filters": {}}

    def homeVideoContent(self):
        r = self._get('/')
        if not r:
            return {"list": []}
        return self._parse_home_list(r.text)

    def _parse_home_list(self, html):
        videos = []
        seen = set()
        items = re.findall(
            r'<a href="(/meijutt/(\d+)\.html)"[^>]*title="([^"]*)"',
            html, re.S
        )
        for href, vid, title in items:
            if vid in seen:
                continue
            seen.add(vid)
            pic_match = re.search(
                rf'<a href="{re.escape(href)}"[^>]*>.*?<img[^>]*src="(https?://[^"]*)"',
                html, re.S
            )
            pic = pic_match.group(1) if pic_match else ''
            videos.append({
                "vod_id": href,
                "vod_name": title,
                "vod_pic": pic,
            })
            if len(videos) >= 20:
                break
        return {"list": videos}

    # ==================== 分类 ====================
    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg) if str(pg).isdigit() else 1
        if pg == 1:
            url = f'/mjtt/{tid}.html'
        else:
            url = f'/mjtt/{tid}-{pg}.html'
        r = self._get(url)
        if not r:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 20, "total": 0}
        return self._parse_category_list(r.text, pg)

    def _parse_category_list(self, html, pg):
        videos = []
        items = re.findall(
            r'<div class="bor_img3_right">\s*<a href="(/meijutt/\d+\.html)"[^>]*title="([^"]*)"[^>]*>'
            r'<img[^>]*data-original="([^"]*)"[^>]*>.*?</a>\s*<em>([\d.]+)</em>',
            html, re.S
        )
        for href, title, pic, score in items:
            videos.append({
                "vod_id": href,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": f"评分 {score}",
            })
        page_match = re.search(r'href="[^"]*-(\d+)\.html"[^>]*>\s*末页', html)
        if not page_match:
            page_match = re.search(r'href="[^"]*-(\d+)\.html"[^>]*>\s*>', html)
        if not page_match:
            page_match = re.search(r'共(\d+)页', html)
        pagecount = int(page_match.group(1)) if page_match else pg
        return {
            "list": videos,
            "page": pg,
            "pagecount": pagecount,
            "limit": 20,
            "total": pagecount * 20,
        }

    # ==================== 详情 ====================
    def detailContent(self, ids):
        try:
            vod_id = ids[0] if isinstance(ids, list) else ids
            if not vod_id.startswith('http'):
                vod_id = self.host + vod_id
            r = self._get(vod_id)
            if not r:
                return {"list": []}
            return self._parse_detail(r.text, vod_id)
        except Exception:
            return {"list": []}

    def _parse_detail(self, html, url):
        vod = {}
        m = re.search(r'<div class="info-title"><span>(【.*?】)</span><h1>([^<]+)</h1>\((\d{4})\)</div>', html)
        if m:
            vod['vod_name'] = m.group(2).strip()
            vod['vod_year'] = m.group(3)
            vod['vod_area'] = re.sub(r'[\[\]【】]', '', m.group(1)).strip()
        else:
            m2 = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
            if m2:
                vod['vod_name'] = m2.group(1).strip()
        pic_match = re.search(r'<img[^>]*(?:data-src|data-original|src)="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"', html)
        if pic_match:
            vod['vod_pic'] = pic_match.group(1)
        li_items = re.findall(r'<li>(.*?)</li>', html, re.S)
        for li in li_items:
            clean = self._extract_text(li)
            if clean.startswith('主演：'):
                actors = clean.replace('主演：', '').replace('更多>>', '').strip()
                if actors and actors not in ('内详', ''):
                    vod['vod_actor'] = actors
            elif clean.startswith('小分类：'):
                vod['vod_type'] = clean.replace('小分类：', '').strip()
            elif clean.startswith('地区：'):
                area_text = clean.replace('地区：', '').strip()
                area_match = re.match(r'([^\s更新]+)', area_text)
                if area_match:
                    vod['vod_area'] = area_match.group(1)
            elif clean.startswith('状态：'):
                vod['vod_remarks'] = clean.replace('状态：', '').strip()
            elif '电视台：' in clean:
                channel = clean.split('电视台：', 1)[-1].split('单集')[0].strip()
                if channel:
                    remarks = vod.get('vod_remarks', '')
                    vod['vod_remarks'] = f"{channel} / {remarks}" if remarks else channel
        desc_parts = re.findall(r'<p[^>]*>(.*?)</p>', html, re.S)
        for part in desc_parts:
            clean = self._extract_text(part)
            if len(clean) > 30 and '下载' not in clean and 'magnet' not in clean and 'gurl' not in clean:
                vod['vod_content'] = clean
                break
        sources = {}
        tab_labels = re.findall(r'<label[^>]*>\s*([^<]+)\s*<em>\[(\d+)\]</em>', html)
        tab_ids = re.findall(r'id="play_(\d+)"', html)
        tab_splits = re.split(r'<div class="tabs-list[^"]*"\s*id="play_\d+"', html)
        for i, play_id in enumerate(tab_ids):
            tab_name = tab_labels[i][0].strip() if i < len(tab_labels) else f'线路{i+1}'
            section = tab_splits[i + 1] if i + 1 < len(tab_splits) else ''
            end = re.search(r'<div class="tabs-list|<div class="o_list_cn', section)
            if end:
                section = section[:end.start()]
            episodes = re.findall(r'href="(/meijuplay/[^"]+)"[^>]*>([^<]+)', section)
            if episodes:
                ep_list = []
                for ep_url, ep_name in episodes:
                    ep_list.append(f"{ep_name}${self.host}{ep_url}")
                sources[tab_name] = ep_list
        gvar_matches = re.findall(r'var\s+GvodUrls\d+\s*=\s*"([^"]*)"', html)
        for gvar in gvar_matches:
            parts = gvar.split('###')
            for part in parts:
                if '$' not in part:
                    continue
                name_url = part.split('$', 1)
                if len(name_url) != 2:
                    continue
                name = self._clean(name_url[0]) or '下载链接'
                link_url = name_url[1]
                if 'pan.quark.cn' in link_url:
                    src = '夸克网盘'
                elif 'pan.xunlei.com' in link_url:
                    src = '迅雷网盘'
                elif 'pan.baidu.com' in link_url:
                    src = '百度网盘'
                elif link_url.startswith('ed2k://'):
                    src = 'ed2k'
                elif link_url.startswith('magnet:'):
                    src = '磁力'
                else:
                    src = '其他'
                if src not in sources:
                    sources[src] = []
                ep = f"{name}${link_url}"
                if ep not in sources[src]:
                    sources[src].append(ep)
        source_names = []
        source_urls = []
        download_order = ['夸克网盘', '迅雷网盘', '百度网盘', 'ed2k', '磁力', '其他']
        streaming = [k for k in sources if k not in download_order and sources[k]]
        downloads = [k for k in download_order if k in sources and sources[k]]
        for src_name in streaming + downloads:
            source_names.append(src_name)
            source_urls.append('#'.join(sources[src_name]))
        vod['vod_play_from'] = '$$$'.join(source_names) if source_names else '美剧天堂'
        vod['vod_play_url'] = '$$$'.join(source_urls) if source_urls else ''
        return {"list": [vod]}

    # ==================== 播放 ====================
    def playerContent(self, flag, id, vipFlags):
        if '/meijuplay/' in id:
            m3u8 = self._get_m3u8(id)
            if m3u8:
                return {"parse": 0, "url": m3u8, "header": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
                    "Referer": "https://www.meijutt.cc/"
                }}
        return {"parse": 0, "url": id, "header": {}}

    def _get_m3u8(self, play_url):
        try:
            r = self._get(play_url)
            if not r:
                return None
            m = re.search(r'var\s+now\s*=\s*(?:unescape\()?["\']([^"\']+)', r.text)
            if m:
                url = m.group(1)
                if '%' in url:
                    url = urllib.parse.unquote(url)
                if '.m3u8' in url:
                    return url
            m2 = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', r.text)
            if m2:
                return m2.group(1)
            iframe = re.search(r'iframe[^>]*src="([^"]*dm\.html[^"]*)"', r.text)
            if iframe:
                r2 = self._get(iframe.group(1))
                if r2:
                    m3 = re.search(r'var\s+now\s*=\s*(?:unescape\()?["\']([^"\']+)', r2.text)
                    if m3:
                        url = m3.group(1)
                        if '%' in url:
                            url = urllib.parse.unquote(url)
                        if '.m3u8' in url:
                            return url
        except Exception:
            pass
        return None


