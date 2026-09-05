# -*- coding: utf-8 -*-
#!/usr/bin/python
"""
蜜桃AV
地址: https://20260807bb-bnm.mitaoava02.top
"""

import sys, re, json, base64, html, time, random
from urllib.parse import quote, unquote, urljoin

try:
    import requests
except ImportError:
    requests = None
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def init(self, extend=""): pass
        def homeContent(self, filter): pass
        def homeVideoContent(self): pass
        def categoryContent(self, tid, pg, filter, extend): pass
        def detailContent(self, ids): pass
        def playerContent(self, flag, id, vipFlags=None): pass
        def searchContent(self, key, quick, pg='1'): pass
        def isVideoFormat(self, url): pass
        def manualVideoCheck(self): pass
        def localProxy(self, param): pass


def fix_url(url, host):
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return urljoin(host, url)
    if url.startswith("http"):
        return url
    return urljoin(host, "/" + url)


def clean_text(text):
    if not text:
        return ""
    return html.unescape(re.sub(r"<[^>]+>", "", str(text))).strip()


class Spider(BaseSpider):
    def __init__(self):
        super().__init__()
        self.host = "https://20260807bb-bnm.mitaoava02.top"
        self.name = "蜜桃AV"
        self.s = requests.Session() if requests else None
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/",
        }
        self.cms_type = "v10"
        self.content_type = "video"
        self.seen_ids = set()
        if self.s:
            self.s.headers.update(self.headers)
            self.s.verify = False

    def init(self, extend=""):
        if extend and extend.startswith("http"):
            self.host = extend.rstrip("/")
            self.headers["Referer"] = self.host + "/"
            if self.s:
                self.s.headers.update(self.headers)

    def getName(self):
        return self.name

    def isVideoFormat(self, url):
        return any(x in url for x in [".m3u8", ".mp4", ".flv", ".ts", ".mkv", ".avi", ".wmv", ".mov"])

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        EMPTY_GIF = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
        if not param or not param.startswith('http'):
            return [200, 'image/gif', EMPTY_GIF, {}]
        try:
            r = self.s.get(param, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
            return [200, r.headers.get('Content-Type', 'application/octet-stream'), r.content, {}]
        except:
            return [200, 'image/gif', EMPTY_GIF, {}]

    def _fetch(self, url, referer=None, retries=3, timeout=15):
        if not self.s:
            return ''
        for attempt in range(retries):
            try:
                if attempt > 0:
                    time.sleep(random.uniform(0.5, 1.5))
                headers = dict(self.headers)
                if referer:
                    headers['Referer'] = referer
                r = self.s.get(url, headers=headers, timeout=timeout, verify=False)
                r.encoding = r.apparent_encoding if r.apparent_encoding else 'utf-8'
                if r.status_code == 200:
                    if "Just a moment" in r.text or "cf-browser-verification" in r.text:
                        continue
                    return r.text
                elif r.status_code in [403, 429, 503]:
                    continue
            except Exception:
                continue
        return ''

    def homeContent(self, filter):
        try:
            classes = [
                {'type_name': '国产无码', 'type_id': 'guochanwuma'},
                {'type_name': '日本口爆', 'type_id': 'ribenkoujiao'},
                {'type_name': '日本无码', 'type_id': 'ribenwuma'},
                {'type_name': '日本群交', 'type_id': 'ribenqunhuan'},
                {'type_name': '国产热门', 'type_id': 'guochanremen'},
                {'type_name': '海边偷拍', 'type_id': 'haibiantoupai'},
                {'type_name': '偷情车震', 'type_id': 'touqingchezhen'},
                {'type_name': '污污动漫', 'type_id': 'wuwudongman'},
                {'type_name': '拉拉群交', 'type_id': 'lalaqunjiao'},
                {'type_name': 'Gay群交', 'type_id': 'gayqunjiao'},
                {'type_name': '欧美精选', 'type_id': 'oumeijingxuan'},
                {'type_name': '自慰手淫', 'type_id': 'ziweishouyin'},
                {'type_name': 'N女群欢', 'type_id': 'nnvqunhuan'},
                {'type_name': '美臀诱惑', 'type_id': 'meitunyouhuo'},
                {'type_name': '麻豆传媒', 'type_id': 'madouchuanmei'},
                {'type_name': '天美传媒', 'type_id': 'tianmeichuanmei'},
                {'type_name': '皇家华人', 'type_id': 'huangjiahuaren'},
                {'type_name': '精东影业', 'type_id': 'jingdongyingye'},
                {'type_name': '起点传媒', 'type_id': 'qidianchuanmei'},
            ]
            filters = {}
            return {'class': classes, 'filters': filters}
        except Exception:
            return {'class': [], 'filters': {}}

    def homeVideoContent(self):
        return self.categoryContent('guochanwuma', '1', False, {})

    def categoryContent(self, tid, pg, filter, extend):
        try:
            result = {'list': [], 'page': int(pg), 'pagecount': 1, 'limit': 24, 'total': 0}
            page = int(pg) if pg else 1
            if page > 1:
                url = f"{self.host}/index.php/vod/type/id/{tid}/page/{page}.html"
            else:
                url = f"{self.host}/index.php/vod/type/id/{tid}.html"
            
            html_text = self._fetch(url)
            if not html_text:
                return result
            
            videos = self._parse_list(html_text)
            
            total_pages = page + 1
            page_nums = re.findall(r'/page/(\d+)\.html', html_text)
            if page_nums:
                total_pages = max(int(p) for p in page_nums)
            
            result.update({
                'list': videos,
                'page': page,
                'pagecount': total_pages,
                'limit': len(videos),
                'total': 999999
            })
            return result
        except Exception:
            return {'list': [], 'page': int(pg), 'pagecount': 1, 'limit': 24, 'total': 0}

    def _parse_list(self, html_text):
        if not html_text:
            return []
        videos = []
        seen = set()
        
        cards = re.findall(
            r'<li[^>]*class="[^"]*content-item[^"]*"[^>]*>(.*?)</li>',
            html_text, re.S | re.I
        )
        if not cards:
            cards = re.findall(
                r'<a[^>]*class="[^"]*video-pic[^"]*"[^>]*>(.*?)</a>',
                html_text, re.S | re.I
            )
        if not cards:
            cards = re.findall(
                r'<a[^>]*href="[^"]*/detail/id/\d+\.html"[^>]*>(.*?)</a>',
                html_text, re.S | re.I
            )
        
        for card in cards:
            try:
                href_match = re.search(r'href="(/index\.php/vod/detail/id/(\d+)\.html)"', card)
                if not href_match:
                    href_match = re.search(r'href="(/[^"]*detail/id/(\d+)[^"]*)"', card)
                if not href_match:
                    continue
                
                href = href_match.group(1)
                vid = href_match.group(2)
                if not vid or vid in seen:
                    continue
                seen.add(vid)
                
                title = ''
                for t_pat in [
                    r'<a[^>]*title="([^"]+)"',
                    r'<h\d[^>]*class="[^"]*video-title[^"]*"[^>]*>.*?<a[^>]*title="([^"]+)"',
                    r'<h\d[^>]*>.*?<a[^>]*>(.*?)</a>',
                ]:
                    m = re.search(t_pat, card, re.S | re.I)
                    if m:
                        title = clean_text(m.group(1))
                        if title:
                            break
                
                pic = ''
                for p_pat in [
                    r'data-src="([^"]+)"',
                    r'data-original="([^"]+)"',
                    r'src="([^"]+)"',
                    r'background:\s*url\(([^)]+)\)',
                ]:
                    m = re.search(p_pat, card, re.I)
                    if m:
                        pic = m.group(1).strip().strip('"').strip("'")
                        pic = fix_url(pic, self.host)
                        if pic:
                            break
                
                remark = ''
                m = re.search(r'<span[^>]*class="[^"]*note[^"]*"[^>]*>(.*?)</span>', card, re.S | re.I)
                if m:
                    remark = clean_text(m.group(1))
                
                videos.append({
                    'vod_id': href,
                    'vod_name': title or vid,
                    'vod_pic': pic,
                    'vod_remarks': remark
                })
            except Exception:
                continue
        
        return videos

    def detailContent(self, ids):
        try:
            vid = ids[0] if isinstance(ids, list) else ids
            result = {'list': []}
            
            if vid.startswith('http'):
                url = vid
            else:
                url = f"{self.host}/index.php/vod/detail/id/{vid}.html"
            
            html_text = self._fetch(url)
            
            if not html_text or 'player' not in html_text.lower():
                play_url = f"{self.host}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
                html_text = self._fetch(play_url, referer=url)
                if html_text:
                    url = play_url
            
            if not html_text:
                return result
            
            title = ''
            for t_pat in [r'<h1[^>]*>(.*?)</h1>', r'<dt>(.*?)</dt>']:
                m = re.search(t_pat, html_text, re.S | re.I)
                if m:
                    title = clean_text(m.group(1))
                    if title:
                        break
            if not title:
                m = re.search(r'<title>(.*?)</title>', html_text, re.S | re.I)
                if m:
                    title = clean_text(m.group(1)).split('-')[0].split('_')[0]
            
            cover = ''
            for c_pat in [
                r'<div[^>]*class="[^"]*detail_left[^"]*"[^>]*>.*?<img[^>]+src="([^"]+)"',
                r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"',
                r'<img[^>]+data-original="([^"]+)"',
                r'background:\s*url\(([^)]+)\)',
            ]:
                m = re.search(c_pat, html_text, re.S | re.I)
                if m:
                    cover = fix_url(m.group(1), self.host)
                    if cover:
                        break
            
            content = ''
            m = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]+)"', html_text, re.S | re.I)
            if m:
                content = m.group(1)
            
            play_urls = self._extract_video_urls(html_text, url)
            if play_urls:
                sources = []
                urls = []
                for label, purl in play_urls:
                    sources.append(label)
                    urls.append(f'{label}${purl}')
                vod_play_from = '$$$'.join(sources)
                vod_play_url = '$$$'.join(urls)
            else:
                vod_play_from = '默认线路'
                play_page = f"{self.host}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
                vod_play_url = f'正片${play_page}'
            
            result['list'].append({
                'vod_id': vid,
                'vod_name': title or vid,
                'vod_pic': cover,
                'vod_content': content,
                'vod_play_from': vod_play_from,
                'vod_play_url': vod_play_url,
            })
            return result
        except Exception:
            return {'list': []}

    def _extract_video_urls(self, html_text, page_url):
        play_urls = []
        seen_urls = set()
        
        def add_url(label, url):
            if not url or url in seen_urls:
                return
            seen_urls.add(url)
            play_urls.append((label, url))
        
        panels = re.findall(
            r'<div[^>]*class="[^"]*play-btn-groupa[^"]*"[^>]*>(.*?)</div>',
            html_text, re.S | re.I
        )
        for panel in panels:
            items = re.findall(
                r'<div[^>]*class="[^"]*item[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                panel, re.S | re.I
            )
            for href, name in items:
                href = clean_text(href)
                name = clean_text(name)
                if not href or 'javascript' in href:
                    continue
                if href.startswith('http') and not href.startswith(self.host):
                    if '/vod/play/' not in href and '/index.php/vod/play/' not in href:
                        continue
                full_url = href if href.startswith('http') else urljoin(self.host, href)
                if '/vod/play/' in full_url or '/index.php/vod/play/' in full_url:
                    label = name or '在线播放'
                    if full_url not in seen_urls:
                        seen_urls.add(full_url)
                        play_urls.append((label, full_url))
        
        scripts = re.findall(r'<script[^>]*>(.*?)</script>', html_text, re.S | re.I)
        for script in scripts:
            for var_name in ['player_data', 'player_aaaa', 'playerConfig', 'player', 'videoInfo', 'vodData']:
                pattern = rf'var\s+{re.escape(var_name)}\s*=\s*(\{{.*?\}});'
                m = re.search(pattern, script, re.S)
                if m:
                    try:
                        pdata = json.loads(m.group(1))
                        
                        def find_url(obj):
                            if isinstance(obj, str):
                                if obj.startswith('http') and self.isVideoFormat(obj):
                                    return obj
                                decoded = unquote(obj)
                                if decoded.startswith('http') and self.isVideoFormat(decoded):
                                    return decoded
                            elif isinstance(obj, dict):
                                for k in ['url', 'src', 'file', 'video', 'm3u8', 'mp4', 'link', 'play_url']:
                                    if k in obj:
                                        res = find_url(obj[k])
                                        if res:
                                            return res
                                for k in obj:
                                    res = find_url(obj[k])
                                    if res:
                                        return res
                            elif isinstance(obj, list):
                                for item in obj:
                                    res = find_url(item)
                                    if res:
                                        return res
                            return None
                        
                        found = find_url(pdata)
                        if found:
                            add_url('主线路', found)
                    except Exception:
                        pass
        
        simple_vars = ['now', 'playurl', 'play_url', 'video_url', 'vod_url', 'url', 'src', 'file']
        for var in simple_vars:
            m = re.search(rf'var\s+{re.escape(var)}\s*=\s*["\']([^"\']+)["\']', html_text)
            if m:
                u = m.group(1).strip()
                if u.startswith('http'):
                    add_url('直连', unquote(u))
        
        for pattern in [r'videoSources\s*:\s*(\[.*?\])', r'sources\s*:\s*(\[.*?\])', r'playlist\s*:\s*(\[.*?\])']:
            m = re.search(pattern, html_text, re.S)
            if m:
                try:
                    vs = json.loads(m.group(1))
                    for item in vs:
                        if isinstance(item, dict):
                            u = item.get('file', '') or item.get('src', '') or item.get('url', '')
                            if u.startswith('http'):
                                add_url('多码率', unquote(u))
                        elif isinstance(item, str) and item.startswith('http'):
                            add_url('多码率', unquote(item))
                except Exception:
                    pass
        
        for player_pat in [
            r'wvPlayer\.play\s*\(\s*["\']([^"\']+)["\']',
            r'new\s+DPlayer\s*\(.*?\s+url\s*:\s*["\']([^"\']+)["\']',
            r'video\s*\{[^}]*src\s*:\s*["\']([^"\']+)["\']',
        ]:
            m = re.search(player_pat, html_text, re.S)
            if m:
                u = m.group(1)
                if u.startswith('http'):
                    add_url('播放器', unquote(u))
        
        m = re.search(r'location\.href\s*=\s*["\']([^"\']+)["\']', html_text)
        if m:
            u = m.group(1)
            if u.startswith('http') and self.isVideoFormat(u):
                add_url('跳转', unquote(u))
        
        for m in re.finditer(r'<video[^>]+src=["\']([^"\']+)["\']', html_text, re.I):
            u = m.group(1)
            if u.startswith('http'):
                add_url('VIDEO标签', unquote(u))
        
        for m in re.finditer(r'<source[^>]+src=["\']([^"\']+)["\'][^>]*type=["\']([^"\']+)["\']', html_text, re.I):
            u, t = m.group(1), m.group(2)
            if u.startswith('http'):
                label = 'MP4' if 'mp4' in t else 'M3U8' if 'mpegURL' in t or 'm3u8' in t else '媒体'
                add_url(f'{label}源', unquote(u))
        
        direct_links = re.findall(r'(https?://[^\s"\'<>]+\.(?:m3u8|mp4|flv|ts|mkv|avi)(?:\?[^\s"\'<>]*)?)', html_text)
        for link in set(direct_links):
            add_url('页面提取', unquote(link))
        
        if not play_urls:
            iframe_srcs = re.findall(r'<iframe[^>]+(?:src|data-src)=["\']([^"\']+)["\']', html_text, re.I)
            for src in set(iframe_srcs):
                if any(k in src for k in ['play', 'm3u8', 'embed', 'player', 'video', 'vod']):
                    full = fix_url(src, self.host) if not src.startswith('http') else src
                    iframe_html = self._fetch(full, referer=page_url)
                    if iframe_html:
                        inner_urls = self._extract_video_urls(iframe_html, full)
                        for label, url in inner_urls:
                            add_url(f'嵌套-{label}', url)
                    if not any(u == full for _, u in play_urls):
                        add_url('嵌套页', full)
        
        if not play_urls:
            for b64 in re.findall(r'["\']([A-Za-z0-9+/]{40,}={0,2})["\']', html_text):
                try:
                    decoded = self._b64decode(b64)
                    if decoded.startswith('http') and self.isVideoFormat(decoded):
                        add_url('Base64', decoded)
                except Exception:
                    pass
        
        if not play_urls:
            m = re.search(r'eval\((.*?)\)', html_text, re.S)
            if m:
                try:
                    unpacked = self._unpack_eval(m.group(1), html_text)
                    if unpacked and unpacked.startswith('http'):
                        add_url('Eval解密', unpacked)
                    else:
                        add_url('eval加密', 'eval://' + page_url)
                except Exception:
                    add_url('eval加密', 'eval://' + page_url)
        
        return play_urls

    def playerContent(self, flag, id, vipFlags=None):
        try:
            result = {'parse': 0, 'playUrl': '', 'url': '', 'header': ''}
            if not id:
                return result
            
            if self.isVideoFormat(id):
                result['url'] = id
                result['header'] = json.dumps({
                    'Referer': self.host + '/',
                    'User-Agent': self.headers['User-Agent'],
                    'Accept': '*/*',
                    'Accept-Language': 'zh-CN,zh;q=0.9'
                })
                return result
            
            if id.startswith('magnet:'):
                result['parse'] = 1
                result['url'] = id
                return result
            
            if id.startswith('eval://'):
                real_url = id.replace('eval://', '')
                html_text = self._fetch(real_url)
                if html_text:
                    m = re.search(r'eval\((.*?)\)', html_text, re.S)
                    if m:
                        unpacked = self._unpack_eval(m.group(1), html_text)
                        if unpacked and self.isVideoFormat(unpacked):
                            result['url'] = unpacked
                            result['header'] = json.dumps({
                                'Referer': real_url,
                                'User-Agent': self.headers['User-Agent']
                            })
                            return result
                result['parse'] = 1
                result['url'] = real_url
                result['header'] = json.dumps({
                    'Referer': real_url,
                    'User-Agent': self.headers['User-Agent']
                })
                return result
            
            if 'play' in id or 'player' in id or 'embed' in id:
                html_text = self._fetch(id, referer=self.host + '/')
                if html_text:
                    inner = self._extract_video_urls(html_text, id)
                    if inner:
                        for label, url in inner:
                            if self.isVideoFormat(url):
                                result['url'] = url
                                result['header'] = json.dumps({
                                    'Referer': id,
                                    'User-Agent': self.headers['User-Agent']
                                })
                                return result
                    for pat in [r'var\s+player_[a-z]+\s*=\s*(\{.*?\});', r'player_[a-z]+\s*=\s*(\{.*?\})']:
                        m = re.search(pat, html_text, re.S)
                        if m:
                            try:
                                pdata = json.loads(m.group(1))
                                raw = pdata.get('url', '')
                                if raw:
                                    decoded = unquote(raw)
                                    if decoded.startswith('http'):
                                        result['url'] = decoded
                                        result['header'] = json.dumps({
                                            'Referer': id,
                                            'User-Agent': self.headers['User-Agent']
                                        })
                                        return result
                            except:
                                pass
                    m = re.search(r'var\s+now\s*=\s*["\']([^"\']+)["\']', html_text)
                    if m:
                        result['url'] = m.group(1)
                        result['header'] = json.dumps({
                            'Referer': id,
                            'User-Agent': self.headers['User-Agent']
                        })
                        return result
                    m = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html_text, re.I)
                    if m:
                        src = m.group(1)
                        if not src.startswith('http'):
                            src = urljoin(self.host, src)
                        result['url'] = src
                        result['parse'] = 1
                        result['header'] = json.dumps({
                            'Referer': id,
                            'User-Agent': self.headers['User-Agent']
                        })
                        return result
                result['parse'] = 1
                result['url'] = id
                result['header'] = json.dumps({
                    'Referer': id,
                    'User-Agent': self.headers['User-Agent']
                })
                return result
            
            result['url'] = id
            result['header'] = json.dumps({
                'Referer': self.host + '/',
                'User-Agent': self.headers['User-Agent']
            })
            return result
        except Exception:
            return {'parse': 0, 'playUrl': '', 'url': id, 'header': ''}

    def searchContent(self, key, quick, pg="1"):
        try:
            result = {'list': [], 'page': int(pg), 'pagecount': 1, 'limit': 24, 'total': 0}
            page = int(pg) if pg else 1
            url = f"{self.host}/index.php/vod/search.html?wd={quote(key)}&page={page}"
            html_text = self._fetch(url)
            videos = self._parse_list(html_text) if html_text else []
            result.update({
                'list': videos,
                'page': page,
                'pagecount': page + 1,
                'limit': len(videos),
                'total': 999999
            })
            return result
        except Exception:
            return {'list': [], 'page': int(pg), 'pagecount': 1, 'limit': 24, 'total': 0}

    def _b64decode(self, s):
        try:
            padding = 4 - len(s) % 4
            if padding != 4:
                s += '=' * padding
            decoded = base64.b64decode(s)
            return decoded.decode('utf-8', errors='strict')
        except Exception:
            return ''

    def _unpack_eval(self, eval_code, full_html):
        try:
            m = re.search(r"eval\(function\(p,a,c,k,e,d\)\{.*?\}\((.*?)\)\)", full_html, re.S)
            if not m:
                return None
            return None
        except Exception:
            return None

    def liveContent(self, url):
        pass