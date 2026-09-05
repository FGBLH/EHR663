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
        self.site = 'https://www.qmao.net'
        self.session = requests.Session()
        self.ua = 'Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'
        self.session.headers.update({'User-Agent': self.ua})
        self.cateManual = {
            '电影': '1',
            '电视剧': '2',
            '动漫': '3',
            '短剧': '4',
        }
        self._m = chr(0x661f) + chr(0x6cb3)

    def _clean(self, text):
        if not text:
            return ''
        text = re.sub(r'<[^>]+>', '', text)
        text = html_module.unescape(text)
        text = text.replace('\xa0', ' ').replace('&nbsp;', ' ')
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
        return '七猫短剧'

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
        for m in re.finditer(r'href="/voddetail/(\d+)\.html"', html):
            vid = m.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            snippet = html[m.start():m.start()+800]
            # 标题：分类页 BrowseList，首页 FeaturedList，搜索页 MTagBookList
            title = ''
            tm = re.search(r'(BrowseList|FeaturedList|MTagBookList)_bookName[^>]*>(.*?)</a>', snippet, re.DOTALL)
            if tm:
                title = self._clean(tm.group(2))
            if not title:
                tm = re.search(r'title="([^"]*)"', snippet)
                if tm:
                    title = self._clean(tm.group(1))
            # 封面
            pic = ''
            pm = re.search(r'src="([^"]*\.(?:jpg|webp)[^"]*)"', snippet)
            if pm:
                pic = pm.group(1).strip()
                if not pic.startswith('http'):
                    pic = self.site + pic
            # 备注
            note = ''
            nm = re.search(r'(BrowseList|FeaturedList)_(?:lastChapter|tagsBox)[^>]*>(.*?)</(?:a|div)', snippet, re.DOTALL)
            if nm:
                note = self._clean(nm.group(2))
            if not note:
                nm = re.search(r'(BrowseList|FeaturedList)_bookViewCount[^>]*>([^<]+)<', snippet)
                if nm:
                    note = self._clean(nm.group(2))
            # 搜索页：从 img alt 获取集数
            if not note:
                am = re.search(r'alt="([^"]*(?:集|完结)[^"]*)"', snippet)
                if am:
                    note = self._clean(am.group(1))
            if title:
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
        url = f'{self.site}/vodtype/{tid}.html'
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

        # 播放页获取 player_aaaa
        play_html = self._get(f'{self.site}/vodplay/{vid}-1-1.html')
        pd = {}
        if play_html:
            m = re.search(r'var player_aaaa=(\{[^<]+\})', play_html)
            if m:
                try:
                    pd = json.loads(m.group(1))
                except:
                    pass

        # 详情页
        detail_html = self._get(f'{self.site}/voddetail/{vid}.html')

        # 标题
        title = pd.get('vod_data', {}).get('vod_name', '')
        if not title:
            m2 = re.search(r'dramaDetail_bookName[^>]*>([^<]+)<', detail_html)
            if m2:
                title = self._clean(m2.group(1))
        if not title:
            m2 = re.search(r'<title>([^<]+)', detail_html)
            if m2:
                title = self._clean(re.sub(r'\s*[-–—].*$', '', m2.group(1)))

        # 封面
        pic = ''
        m2 = re.search(r'dramaDetail_bookCover[^>]*>\s*<img[^>]*src="([^"]*)"', detail_html)
        if m2:
            pic = m2.group(1).strip()
            if not pic.startswith('http'):
                pic = self.site + pic

        # 标签/类型
        vod_class = ''
        m2 = re.search(r'dramaDetail_tagsBox[^>]*>(.*?)</div>', detail_html, re.DOTALL)
        if m2:
            vod_class = self._clean(m2.group(1))
        if not vod_class:
            vod_class = pd.get('vod_data', {}).get('vod_class', '')

        # 演员
        actor = pd.get('vod_data', {}).get('vod_actor', '')

        # 导演
        director = pd.get('vod_data', {}).get('vod_director', '')
        if director:
            director = self._m + '、' + director
        else:
            director = self._m

        # 播放列表 - 从播放页提取集数
        play_from = []
        play_url_list = []

        if play_html:
            # 提取所有线路
            tabs = re.findall(r'episode_tabBtn[^>]*data-sid="(\d+)"[^>]*data-from="([^"]*)"[^>]*>([^<]*)<', play_html)
            if not tabs:
                tabs = re.findall(r'episode_tabBtn[^>]*>([^<]*)<', play_html)
                if tabs:
                    tabs = [(str(i+1), '', t) for i, t in enumerate(tabs)]

            # 提取集数链接
            episodes = []
            for em in re.finditer(r'<a[^>]*class="CatalogList_linkBox"[^>]*href="(/vodplay/[^"]+)"', play_html):
                ep_href = em.group(1)
                # 在 </a> 前提取集数编号
                snippet = play_html[em.start():em.start()+600]
                num = re.search(r'>\s*(?:<[^>]*>\s*)*(\d+)\s*</a>', snippet)
                if num:
                    ep_num = num.group(1).strip()
                    episodes.append(f'第{ep_num}集${ep_href}')
                else:
                    episodes.append(f'播放${ep_href}')
            # 备用：data-part
            if not episodes:
                for em in re.finditer(r'href="(/vodplay/[^"]+)"[^>]*data-part="([^"]*)"', play_html):
                    episodes.append(f'{em.group(2)}${em.group(1)}')
            if not episodes:
                for em in re.finditer(r'href="(/vodplay/[^"]+)"[^>]*>([^<]*)<', play_html):
                    if em.group(2).strip():
                        episodes.append(f'{em.group(2).strip()}${em.group(1)}')

            if episodes:
                line_name = tabs[0][2] if tabs else '默认'
                if not line_name:
                    line_name = tabs[0][1] or '默认'
                play_from.append(self._clean(line_name))
                play_url_list.append('#'.join(episodes))

        # 如果没有从播放页拿到集数，用 player_aaaa 的 URL 直接播放
        if not play_from and pd:
            url = pd.get('url', '')
            from_flag = pd.get('from', '')
            if url:
                play_from.append(from_flag or '默认')
                play_url_list.append(f'播放${url}')

        vod = {
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': pic,
            'type_name': vod_class,
            'vod_year': '',
            'vod_area': '',
            'vod_remarks': '',
            'vod_actor': actor,
            'vod_director': director,
            'vod_content': '',
            'vod_play_from': '$$$'.join(play_from),
            'vod_play_url': '$$$'.join(play_url_list)
        }
        result['list'].append(vod)
        return result

    def playerContent(self, flag, id, vipFlags):
        result = {}
        try:
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
        url = f'{self.site}/vodsearch/-------------.html?wd={wd}'
        html = self._get(url)
        if html:
            result['list'] = self._extract_list(html)
        return result

    def localProxy(self, params):
        return [200, "video/MP2T", {}, ""]
