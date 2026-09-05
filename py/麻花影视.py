#coding=utf-8
import sys
import re
import json
import html as html_module
import requests
sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
    def __init__(self):
        super().__init__()
        self.site = 'https://www.jxuma.com'
        self.session = requests.Session()
        self.ua = 'Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'
        self.session.headers.update({'User-Agent': self.ua})
        self.cateManual = {
            '电影': '1',
            '电视剧': '2',
            '综艺': '3',
            '动漫': '4',
            '短剧': '36',
        }
        self._m = chr(0x661f) + chr(0x6cb3)

    def _clean(self, text):
        if not text:
            return ''
        text = re.sub(r'<[^>]+>', '', text)
        text = html_module.unescape(text)
        text = text.replace('\xa0', ' ')
        text = ' '.join(text.split())
        return text.strip()

    def _get(self, url):
        try:
            r = self.session.get(url, timeout=15, headers={'Referer': self.site})
            r.encoding = 'utf-8'
            return r.text
        except:
            return ''

    def init(self, extend=''):
        pass

    def getName(self):
        return '麻花影视'

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def homeContent(self, filter):
        result = {'class': [], 'filters': {}, 'list': [], 'parse': 0, 'jx': 0}
        for k, v in self.cateManual.items():
            result['class'].append({'type_id': str(v), 'type_name': k})
        return result

    def _extract_list(self, html):
        videos = []
        seen = set()
        for m in re.finditer(r'href="/umo/(\d+)\.html"[^>]*?title="([^"]*)"', html):
            vid = m.group(1)
            title = m.group(2).strip()
            if vid in seen or not title:
                continue
            snippet = html[m.start():m.start()+400]
            pm = re.search(r'data-original="([^"]*)"', snippet)
            pic = pm.group(1).strip() if pm else ''
            if vid in seen:
                continue
            seen.add(vid)
            note = ''
            nm = re.search(r'pic-text text-right">([^<]*)', snippet)
            if nm:
                note = nm.group(1).strip()
            videos.append({
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': pic,
                'vod_remarks': note
            })
        return videos

    def homeVideoContent(self):
        result = {'list': [], 'parse': 0, 'jx': 0}
        html = self._get(self.site)
        if html:
            result['list'] = self._extract_list(html)
        return result

    def categoryContent(self, tid, pg, filter, extend):
        result = {'list': [], 'parse': 0, 'jx': 0}
        page = int(pg) if pg else 1
        url = f'{self.site}/jxk/{tid}.html'
        html = self._get(url)
        if html:
            result['list'] = self._extract_list(html)
        result['page'] = page
        result['pagecount'] = page + 1 if result['list'] else page
        result['limit'] = len(result['list'])
        result['total'] = len(result['list'])
        return result

    def detailContent(self, ids):
        result = {'list': [], 'parse': 0, 'jx': 0}
        vid = ''
        if isinstance(ids, list):
            vid = ids[0] if ids else ''
        elif ids:
            vid = str(ids)
        if not vid:
            return result
        # 用播放页第一集来获取 player_aaaa 数据
        html = self._get(f'{self.site}/aey/{vid}/1-1.html')
        if not html:
            return result

        # 提取 player_aaaa
        pd = {}
        m = re.search(r'var player_aaaa=(\{[^<]+\})', html)
        if m:
            try:
                pd = json.loads(m.group(1))
            except:
                pass

        # 从详情页获取更多信息
        detail_html = self._get(f'{self.site}/umo/{vid}.html')

        # 标题
        title = pd.get('vod_data', {}).get('vod_name', '')
        if not title:
            m2 = re.search(r'<h1[^>]*class="title"[^>]*>([^<]*)', detail_html)
            if m2:
                title = self._clean(m2.group(1))
        if not title:
            m2 = re.search(r'<title>([^<]+)', detail_html)
            if m2:
                title = self._clean(re.sub(r'\s*[-–—].*$', '', m2.group(1)))

        # 封面
        pic = ''
        m2 = re.search(r'data-original="([^"]+)"[^>]*class="[^"]*cover[^"]*"', detail_html)
        if not m2:
            m2 = re.search(r'data-original="([^"]+)"[^>]*rel="nofollow"', detail_html)
        if m2:
            pic = m2.group(1).strip()

        # 类型、地区、年份、语言、主演、导演、简介
        def extract_info(pattern, text):
            m3 = re.search(pattern, text)
            if m3:
                return self._clean(m3.group(1))
            return ''

        vod_class = extract_info(r'类型：</span>(.*?)(?:</a>|<span)', detail_html)
        area = extract_info(r'地区：</span>(.*?)(?:</a>|<span)', detail_html)
        year = extract_info(r'年份：</span>(.*?)(?:</a>|<span)', detail_html)
        lang = extract_info(r'语言：</span>(.*?)(?:</a>|<span)', detail_html)
        actor = extract_info(r'主演：</span>(.*?)(?:</p>|</div>)', detail_html)
        if not actor:
            actor = pd.get('vod_data', {}).get('vod_actor', '')
        director = extract_info(r'导演：</span>(.*?)(?:</p>|</div>)', detail_html)
        if not director:
            director = pd.get('vod_data', {}).get('vod_director', '')
        if director:
            director = self._m + '、' + director
        else:
            director = self._m

        desc = extract_info(r'detail-sketch">(.*?)</span>', detail_html)

        # 播放列表 - 从详情页提取所有线路和集数
        play_from = []
        play_url_list = []

        # 提取线路名（在 playlist data-toggle="tab" 里）
        line_names = re.findall(r'playlist\d+" data-toggle="tab"[^>]*rel="nofollow">([^<]+)<', detail_html)
        # 如果没找到，尝试提取 pannel__head 里的文字
        if not line_names:
            line_names = re.findall(r'pannel__head[^>]*>([^<]*)<', detail_html)

        # 提取每个播放面板的链接
        link_groups = re.findall(r'tab-pane fade[^>]*>(.*?)</ul>', detail_html, re.DOTALL)

        for i, group_html in enumerate(link_groups):
            line_name = line_names[i] if i < len(line_names) else f'线路{i+1}'
            line_name = self._clean(line_name)
            episodes = []
            for em in re.finditer(r'href="(/aey/\d+/(\d+-\d+)\.html)"[^>]*>([^<]*)<', group_html):
                ep_href = em.group(1)
                ep_label = em.group(3).strip()
                if ep_label and ep_href:
                    episodes.append(f'{ep_label}${ep_href}')
            if episodes:
                play_from.append(line_name)
                play_url_list.append('#'.join(episodes))

        # 把华为云排到第一个（1080p）
        for i, name in enumerate(play_from):
            if '华为' in name and i > 0:
                play_from.insert(0, play_from.pop(i))
                play_url_list.insert(0, play_url_list.pop(i))
                break

        # 备用：如果详情页没有找到播放列表，直接用播放页的 URL
        if not play_from and pd:
            url = pd.get('url', '')
            from_flag = pd.get('from', '')
            if url:
                play_from.append(from_flag or '线路①')
                play_url_list.append(f'播放${url}')

        vod = {
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': pic,
            'type_name': vod_class,
            'vod_year': year,
            'vod_area': area,
            'vod_lang': lang,
            'vod_remarks': '',
            'vod_actor': actor,
            'vod_director': director,
            'vod_content': desc,
            'vod_play_from': '$$$'.join(play_from),
            'vod_play_url': '$$$'.join(play_url_list)
        }
        result['list'].append(vod)
        return result

    def playerContent(self, flag, id, vipFlags):
        result = {}
        try:
            # id 格式: /aey/119317/1-1.html
            play_url = id
            if not play_url.startswith('http'):
                play_url = self.site + play_url

            html = self._get(play_url)
            m = re.search(r'var player_aaaa=(\{[^<]+\})', html)
            if m:
                pd = json.loads(m.group(1))
                url = pd.get('url', '')
                if url:
                    result['parse'] = 0
                    result['url'] = url
                    result['jx'] = 0
                    result['header'] = {
                        'User-Agent': self.ua,
                        'Referer': self.site + '/'
                    }
                    return result

            # 备用：嗅探
            result['parse'] = 1
            result['url'] = play_url
            result['jx'] = 0
            result['header'] = {
                'User-Agent': self.ua,
                'Referer': self.site + '/'
            }
        except Exception as e:
            print(f'playerContent error: {e}')

        if not result:
            result = {'parse': 1, 'url': '', 'jx': 0, 'header': {}}
        return result

    def searchContent(self, key, quick, pg='1'):
        result = {'list': [], 'parse': 0, 'jx': 0}
        wd = requests.utils.quote(key)
        url = f'{self.site}/search/-------------.html?wd={wd}'
        html = self._get(url)
        if html:
            result['list'] = self._extract_list(html)
        return result

    def localProxy(self, params):
        return [200, "video/MP2T", {}, ""]
