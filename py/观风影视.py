#coding=utf-8
import sys
import re
import json
import requests
sys.path.append('..')
from base.spider import Spider

class Spider(Spider):

    def __init__(self):
        super().__init__()
        self.site = 'https://www.cd-zj.com'
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.cd-zj.com/'
        })
        self.cateManual = {
            '\u7535\u5f71': '1',
            '\u7535\u89c6\u5267': '2',
            '\u7efc\u827a': '3',
            '\u52a8\u6f2b': '4',
            '\u70ed\u95e8\u77ed\u5267': '5',
            '\u817e\u8bafSVIP': 'label/qq',
            '\u4f18\u9177SVIP': 'label/youku',
            'B\u7ad9SVIP': 'label/bli',
        }

    def init(self, extend=""):
        pass

    def getName(self):
        return "\u67ab\u53f64K\u5907\u7528"

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def _clean(self, text):
        if not text:
            return ''
        text = re.sub(r'<[^>]+>', '', text)
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('\u3000', ' ')
        text = ' '.join(text.split())
        return text.strip()

    def _get(self, url):
        try:
            r = self.session.get(url, timeout=15)
            r.encoding = 'utf-8'
            return r.text
        except:
            return ''

    def getVid(self, url):
        if not url:
            return ''
        m = re.search(r'/detail/(\d+)\.html', url)
        if m:
            return m.group(1)
        m = re.search(r'/play/(\d+)-', url)
        if m:
            return m.group(1)
        return ''

    def homeContent(self, filter):
        result = {'class': [], 'filters': {}, 'list': [], 'parse': 0, 'jx': 0}
        for k, v in self.cateManual.items():
            result['class'].append({'type_id': str(v), 'type_name': k})
        return result

    def homeVideoContent(self):
        videos = []
        try:
            html = self._get(self.site)
            seen = set()
            for m in re.finditer(r'class="public-list-exp"[^>]*href="([^"]+)"[^>]*title="([^"]*)"', html):
                href = m.group(1)
                title = m.group(2)
                vid = self.getVid(href)
                if not vid or vid in seen:
                    continue
                seen.add(vid)
                snippet = html[m.start():m.start()+500]
                pic = ''
                pm = re.search(r'data-src="([^"]+)"', snippet)
                if pm:
                    pic = pm.group(1).replace('&amp;', '&')
                note = ''
                nm = re.search(r'ft2">([^<]+)<', snippet)
                if nm:
                    note = nm.group(1)
                if title:
                    videos.append({
                        'vod_id': vid,
                        'vod_name': title,
                        'vod_pic': pic,
                        'vod_remarks': note
                    })
        except Exception as e:
            print(f'homeVideoContent error: {e}')
        return {'list': videos, 'parse': 0, 'jx': 0}

    def categoryContent(self, tid, pg, filter, extend):
        result = {'list': [], 'parse': 0, 'jx': 0}
        page = int(pg) if pg else 1
        try:
            if str(tid).startswith('label/'):
                if page == 1:
                    url = f'{self.site}/{tid}.html'
                else:
                    url = f'{self.site}/{tid}-{page}.html'
            else:
                if page == 1:
                    url = f'{self.site}/type/{tid}.html'
                else:
                    url = f'{self.site}/type/{tid}-{page}.html'

            html = self._get(url)
            seen = set()
            for m in re.finditer(r'class="public-list-exp"[^>]*href="([^"]+)"[^>]*title="([^"]*)"', html):
                href = m.group(1)
                title = m.group(2)
                vid = self.getVid(href)
                if not vid or vid in seen:
                    continue
                seen.add(vid)
                snippet = html[m.start():m.start()+500]
                pic = ''
                pm = re.search(r'data-src="([^"]+)"', snippet)
                if pm:
                    pic = pm.group(1).replace('&amp;', '&')
                note = ''
                nm = re.search(r'ft2">([^<]+)<', snippet)
                if nm:
                    note = nm.group(1)
                if title:
                    result['list'].append({
                        'vod_id': vid,
                        'vod_name': title,
                        'vod_pic': pic,
                        'vod_remarks': note
                    })
        except Exception as e:
            print(f'categoryContent error: {e}')

        result['page'] = page
        result['pagecount'] = page + 1 if len(result['list']) > 0 else page
        result['limit'] = len(result['list'])
        result['total'] = len(result['list'])
        return result

    def detailContent(self, ids):
        result = {'list': [], 'parse': 0, 'jx': 0}
        vid = ids[0] if ids else ''
        if not vid:
            return result
        try:
            html = self._get(f'{self.site}/detail/{vid}.html')

            title = ''
            tm = re.search(r'<title>\u300a(.+?)\u300b', html)
            if tm:
                title = tm.group(1)
            if not title:
                tm = re.search(r'<title>([^<]+)', html)
                if tm:
                    title = self._clean(tm.group(1))

            pic = ''
            pm = re.search(r'lazy1[^>]*data-src="([^"]+)"', html)
            if pm:
                pic = pm.group(1).replace('&amp;', '&')

            desc = ''
            dm = re.search(r'<meta name="description" content="(.+?)"', html)
            if dm:
                desc = dm.group(1).replace('\u5267\u60c5\u4ecb\u7ecd\uff1a', '').strip()

            actor = ''
            director = ''
            info = re.search(r'slide-info(.*?)(?:anthology|swiper)', html, re.DOTALL)
            if info:
                block = info.group(1)
                am = re.search(r'\u4e3b\u6f14[:\uff1a]\s*([^\n<]+)', block)
                if am:
                    actor = am.group(1).strip()
                dm2 = re.search(r'\u5bfc\u6f14[:\uff1a]\s*([^\n<]+)', block)
                if dm2:
                    director = dm2.group(1).strip()

            play_from = []
            play_url = []

            # \u627e anthology-tab \u533a\u5757\u5185\u7684\u6240\u6709 <a class="swiper-slide">
            tab_block = re.search(r'class="anthology-tab[^"]*"[^>]*>(.*?)</div>\s*</div>', html, re.DOTALL)
            if tab_block:
                tabs = re.findall(r'<a[^>]*class="swiper-slide"[^>]*>(.*?)</a>', tab_block.group(1), re.DOTALL)
            else:
                tabs = []

            # \u627e\u6240\u6709 anthology-list-box \u533a\u5757
            panels = re.findall(r'class="anthology-list-box[^"]*"[^>]*>(.*?)</div>\s*</div>', html, re.DOTALL)

            for i, tab in enumerate(tabs):
                tab_name = self._clean(tab) or f'\u7ebf\u8def{i+1}'
                play_from.append(tab_name)
                episodes = []
                if i < len(panels):
                    for em in re.finditer(r'<a[^>]*href="([^"]+)"[^>]*>([^<]+)<', panels[i]):
                        ep_href = em.group(1)
                        ep_name = em.group(2).strip()
                        if ep_name and ep_href:
                            episodes.append(f'{ep_name}${ep_href}')
                play_url.append('#'.join(episodes))

            vod = {
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': pic,
                'type_name': '',
                'vod_year': '',
                'vod_area': '',
                'vod_remarks': '',
                'vod_actor': actor,
                'vod_director': director if director else bytes.fromhex('e6989fe6b2b3').decode('utf-8'),
                'vod_content': desc,
                'vod_play_from': '$$$'.join(play_from) if play_from else '',
                'vod_play_url': '$$$'.join(play_url) if play_url else ''
            }
            result['list'].append(vod)
        except Exception as e:
            print(f'detailContent error: {e}')
        return result

    def playerContent(self, flag, id, vipFlags):
        result = {}
        try:
            play_url = id
            if id and not id.startswith('http'):
                play_url = self.site + id

            html = self._get(play_url)

            # \u4f18\u5148\u4ece player_aaaa JSON \u63d0\u53d6 m3u8 \u76f4\u94fe
            m = re.search(r'player_aaaa\s*=\s*(\{.+?\})\s*<', html)
            if m:
                try:
                    data = json.loads(m.group(1))
                    m3u8 = data.get('url', '')
                    if m3u8 and '.m3u8' in m3u8:
                        result['parse'] = 0
                        result['url'] = m3u8
                        result['jx'] = 0
                        result['header'] = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                            'Referer': self.site + '/'
                        }
                        return result
                except:
                    pass

            # \u5907\u7528: \u4ece\u9875\u9762\u4e2d\u627e m3u8 \u94fe\u63a5
            m = re.search(r'url":\s*"(https?://[^"]*\.m3u8[^"]*)"', html)
            if m:
                result['parse'] = 0
                result['url'] = m.group(1).replace('\\/', '/')
                result['jx'] = 0
                result['header'] = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Referer': self.site + '/'
                }
                return result

            # \u5907\u7528: iframe
            m = re.search(r'<iframe[^>]+src="([^"]+)"', html)
            if m:
                result['parse'] = 1
                result['url'] = m.group(1)
                result['jx'] = 0
                result['header'] = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Referer': self.site + '/'
                }
            else:
                result['parse'] = 1
                result['url'] = play_url
                result['jx'] = 0
                result['header'] = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Referer': self.site + '/'
                }
        except Exception as e:
            print(f'playerContent error: {e}')
            result['parse'] = 1
            result['url'] = id
            result['jx'] = 0
            result['header'] = {}
        return result

    def searchContent(self, key, quick, pg='1'):
        result = {'list': [], 'parse': 0, 'jx': 0}
        page = int(pg) if pg else 1
        try:
            url = f'{self.site}/cupfox-search/-------------.html'
            params = {'wd': key}
            if page > 1:
                params['page'] = page

            html = self._get(url)
            seen = set()
            for m in re.finditer(r'href="(/detail/\d+\.html)"[^>]*title="([^"]*)"', html):
                href = m.group(1)
                title = m.group(2)
                vid = self.getVid(href)
                if not vid or vid in seen:
                    continue
                seen.add(vid)
                snippet = html[m.start():m.start()+500]
                pic = ''
                pm = re.search(r'data-src="([^"]+)"', snippet)
                if pm:
                    pic = pm.group(1).replace('&amp;', '&')
                note = ''
                nm = re.search(r'ft2">([^<]+)<', snippet)
                if nm:
                    note = nm.group(1)
                if title:
                    result['list'].append({
                        'vod_id': vid,
                        'vod_name': title,
                        'vod_pic': pic,
                        'vod_remarks': note
                    })
        except Exception as e:
            print(f'searchContent error: {e}')
        return result

    def localProxy(self, params):
        return [200, "video/MP2T", {}, ""]
