#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys, json, re, requests
from urllib.parse import quote, unquote
sys.path.append('..')
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):

    def getName(self):
        return "黑料网"

    def isVideoFormat(self, url):
        if not url:
            return False
        if url.startswith(('novel://', 'text://', 'pics://', 'book_', 'comic_')):
            return False
        return '.mp4' in url or '.m3u8' in url or '.ts' in url

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
        'Referer': 'https://heiliao.com/',
    }
    host = 'https://heiliao.com'
    cat_map = {
        'hlcg': '最新黑料', 'jrrs': '今日热瓜', 'jqrm': '热门黑料', 'lsdg': '经典黑料',
        'xycg': '校园黑料', 'whhl': '网红黑料', 'fczq': '反差专区', 'ycsq': '原创社区',
        'mxcw': '明星丑闻', 'mrds': '每日大赛', 'qqqw': '全球奇闻', 'ttsq': '推特社区',
        'ysdj': '影视短剧', 'whhj': '网黄合集', 'shxw': '社会新闻', 'thzq': '探花专区',
        'cpcd': '厕拍抄底', 'yqby': '有求必应', 'syzy': '深夜综艺', 'djbl': '独家爆料',
        'jqxs': '黑料小说', 'gchl': '官场爆料', 'hlkt': '黑料课堂', 'hlbg': '黑料爆改',
        'ttzz': '桃图杂志', 'mrrb': '日榜黑料', 'zbjx': '周榜精选', 'ybrg': '月榜热瓜',
    }
    ad_ids = {'39668', '8148', '8147', '8150', '8146', '38757', '41525', '109358', '109356'}
    ad_keywords = ('黑料网最新入口', '黑料网海外主站', '黑料APP', '获取最新地址', '发送任意内容至')

    def init(self, extend=""):
        self.session = requests.Session()

    def _get(self, url):
        try:
            r = self.session.get(url, headers=self.headers, timeout=20)
            r.encoding = r.apparent_encoding or 'utf-8'
            return r.text
        except:
            return ''

    def _clean_pic(self, pic):
        if not pic:
            return ''
        if pic.startswith('http'):
            abs_url = pic
        elif pic.startswith('/'):
            abs_url = f'{self.host}{pic}'
        else:
            abs_url = f'{self.host}/{pic}'
        return f"{self.getProxyUrl()}&url={quote(abs_url, safe='')}"

    def _parse_list(self, html):
        items = []
        if not html:
            return items
        pat = r'<div[^>]*class="video-item"[^>]*>(.*?)(?=<div[^>]*class="video-item"[^>]*>|<div[^>]*class="[^"]*page[^"]*"|<div[^>]*class="[^"]*pagination[^"]*"|$)'
        for block in re.finditer(pat, html, re.S):
            b = block.group(1)
            pid_m = re.search(r'archives/(\d+)/', b)
            if not pid_m:
                continue
            pid = pid_m.group(1)
            if pid in self.ad_ids:
                continue
            pic_m = re.search(r'z-image-loader-url=["\']([^"\']+)["\']', b)
            pic = pic_m.group(1).strip() if pic_m else ''
            if not pic:
                continue
            alt_m = re.search(r'alt=["\']([^"\']+)["\']', b)
            title = alt_m.group(1).strip() if alt_m else ''
            if not title:
                continue
            items.append({"vod_id": pid, "vod_name": title, "vod_pic": self._clean_pic(pic)})
        return items

    def _parse_pagecount(self, html):
        if not html:
            return 1
        nums = re.findall(r'/page/(\d+)/', html)
        return max(int(n) for n in nums) if nums else 1

    def homeContent(self, filter):
        try:
            cats = [{'type_id': k, 'type_name': v} for k, v in self.cat_map.items()]
            return {"class": cats, "list": [], "filters": {}}
        except:
            return {"class": [], "filters": {}, "list": [], "page": 1, "pagecount": 1}

    def homeVideoContent(self):
        try:
            html = self._get(self.host)
            return {"list": self._parse_list(html)[:20]}
        except:
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg) if pg else 1
            url = f"{self.host}/{tid}/" if page == 1 else f"{self.host}/{tid}/page/{page}/"
            html = self._get(url)
            return {"page": page, "pagecount": self._parse_pagecount(html), "list": self._parse_list(html)}
        except:
            return {"page": int(pg) if pg else 1, "pagecount": 1, "list": []}

    def detailContent(self, ids):
        try:
            vid = ids[0]
            html = self._get(f"{self.host}/archives/{vid}")
            if not html:
                return {"list": []}
            title_m = re.search(r'<h1[^>]*class="[^"]*detail-title[^"]*"[^>]*>(.*?)</h1>', html, re.S)
            title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip() if title_m else f"黑料{vid}"

            cs = re.search(r'<div[^>]*class="[^"]*editormd-preview[^"]*"[^>]*>(.*?)(?=<div[^>]*class="[^"]*article-tags|<div[^>]*class="[^"]*article-meta|</article|$)', html, re.S)
            content = cs.group(1) if cs else ''

            img_urls = []
            for m in re.finditer(r'z-image-loader-url=["\']([^"\']+)["\']', content):
                u = m.group(1).strip()
                if not u or not u.startswith('http'):
                    continue
                if 'pic.uforxk.cn' not in u and 'upload_01' not in u:
                    continue
                am = re.search(r'alt=["\']([^"\']*)["\']', content[m.end():m.end()+200])
                alt = am.group(1).strip() if am else ''
                if alt and len(alt) >= 20 and re.fullmatch(r'[0-9a-fA-F]+', alt):
                    continue
                img_urls.append(self._clean_pic(u))

            video_eps_main = []
            video_eps_backup = []
            cover_pic = ''
            dp_idx = 0
            for dp in re.finditer(r"<div[^>]*class=\"[^\"]*dplayer[^\"]*\"[^>]*config='([^']*)'", html):
                cfg_str = dp.group(1).replace('&quot;', '"').replace('&amp;', '&')
                try:
                    cfg = json.loads(cfg_str)
                    v = cfg.get('video', {})
                    if dp_idx == 0 and v.get('pic'):
                        cover_pic = self._clean_pic(v.get('pic'))
                    urls = v.get('urls', [])
                    ep_name = f"第{dp_idx+1}集"
                    ep_raw_title = v.get('title', '') or ''
                    m_ep = re.search(r'(\d+)$', ep_raw_title)
                    if m_ep:
                        ep_name = f"第{int(m_ep.group(1))}集"
                    if urls:
                        video_eps_main.append(f"{ep_name}${urls[0].get('url', '')}")
                        if len(urls) > 1:
                            video_eps_backup.append(f"{ep_name}${urls[1].get('url', '')}")
                    elif v.get('url'):
                        video_eps_main.append(f"{ep_name}${v.get('url')}")
                    dp_idx += 1
                except:
                    continue

            raw_text = re.sub(r'<[^>]+>', '\n', content)
            raw_text = re.sub(r'\n{3,}', '\n\n', raw_text).strip()
            text_parts = []
            for line in raw_text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                if any(kw in line for kw in self.ad_keywords):
                    continue
                if line.startswith('黑料网') and '最新入口' in line:
                    continue
                if '海外主站' in line or '中转' in line:
                    continue
                text_parts.append(line)
            full_text = '\n'.join(text_parts)

            pic = cover_pic or (img_urls[0] if img_urls else '')

            from_names = []
            ep_parts = []
            if video_eps_main:
                from_names.append('视频')
                ep_parts.append('#'.join(video_eps_main))
                if video_eps_backup:
                    from_names.append('备用')
                    ep_parts.append('#'.join(video_eps_backup))
            if img_urls:
                from_names.append('图文')
                ep_parts.append(f'图片$pics://{"&&".join(img_urls)}')
            if from_names:
                vod = {
                    "vod_id": vid, "vod_name": title, "vod_remarks": "",
                    "vod_pic": pic, "vod_content": full_text[:500],
                    "vod_play_from": "$$$".join(from_names),
                    "vod_play_url": "$$$".join(ep_parts),
                }
            else:
                short = full_text[:300]
                vod = {
                    "vod_id": vid, "vod_name": title, "vod_remarks": "",
                    "vod_pic": pic, "vod_content": full_text[:500],
                    "vod_play_from": "文字",
                    "vod_play_url": f"阅读${short}",
                }
            return {"list": [vod]}
        except:
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg) if pg else 1
            kw = quote(key)
            url = f"{self.host}/?s={kw}" if page == 1 else f"{self.host}/page/{page}/?s={kw}"
            html = self._get(url)
            return {"list": self._parse_list(html), "page": page}
        except:
            return {"list": [], "page": int(pg) if pg else 1}

    def playerContent(self, flag, id, vipFlags):
        try:
            if flag == '视频' or flag == '备用':
                return {"parse": 0, "url": id, "header": self.headers, "position": "0"}
            if flag == '图文' or id.startswith('pics://'):
                return {"parse": 0, "playUrl": "", "url": id.replace('图片', ''), "header": self.headers, "position": "0"}
            if flag == '文字' or '阅读' in id:
                content = id.replace('阅读', '')
                if '$$$' in content:
                    content = content.split('$$$')[-1]
                nj = json.dumps({"title": content[:50], "content": content}, ensure_ascii=False)
                return {"parse": 0, "url": f"novel://{nj}", "header": "", "vod_player": "书", "position": "0"}
            if id.startswith('pics://'):
                return {"parse": 0, "playUrl": "", "url": id, "header": self.headers, "position": "0"}
            if id.startswith('http'):
                return {"parse": 0, "url": id, "header": self.headers, "position": "0"}
            return {"parse": 0, "url": id, "header": self.headers, "position": "0"}
        except:
            return {"parse": 0, "url": "", "position": "0"}

    def _img_decrypt(self, data):
        try:
            from Crypto.Cipher import AES
            from Crypto.Util.Padding import unpad
            key = ''.join(chr(int(c)) for c in '102_53_100_57_54_53_100_102_55_53_51_51_54_50_55_48'.split('_')).encode('utf-8')
            iv = ''.join(chr(int(c)) for c in '57_55_98_54_48_51_57_52_97_98_99_50_102_98_101_49'.split('_')).encode('utf-8')
            cipher = AES.new(key, AES.MODE_CBC, iv)
            dec = cipher.decrypt(data)
            dec = unpad(dec, AES.block_size)
            return dec
        except:
            return data

    def localProxy(self, param):
        try:
            url = param.get('url', '')
            if not url:
                return [404, 'text/plain', b'not found']
            url = unquote(url)
            r = self.session.get(url, headers={'User-Agent': self.headers['User-Agent'], 'Referer': self.host + '/'}, timeout=15, verify=False)
            data = r.content
            if not data:
                return [404, 'text/plain', b'not found']
            dec = self._img_decrypt(data)
            if dec[:2] == b'\xff\xd8':
                data, ct = dec, 'image/jpeg'
            elif dec[:4] == b'\x89PNG':
                data, ct = dec, 'image/png'
            elif dec[:4] == b'RIFF' and dec[8:12] == b'WEBP':
                data, ct = dec, 'image/webp'
            elif data[:2] == b'\xff\xd8':
                ct = 'image/jpeg'
            elif data[:4] == b'\x89PNG':
                ct = 'image/png'
            elif data[:4] == b'RIFF' and data[8:12] == b'WEBP':
                ct = 'image/webp'
            else:
                ct = r.headers.get('Content-Type', 'image/jpeg')
            return [200, ct, data, {'Content-Length': str(len(data))}]
        except:
            return [404, 'text/plain', b'not found']
