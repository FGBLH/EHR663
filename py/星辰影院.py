import requests
from bs4 import BeautifulSoup
import re
import sys
import json
import urllib.parse
from base.spider import Spider
from urllib.parse import quote, urljoin

sys.path.append('..')

xurl = "http://www.dgpengcheng.com"
headers = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 13; M2102J2SC Build/TKQ1.221114.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/144.0.7559.31 Mobile Safari/537.36',
    'Referer': xurl,
}

class Spider(Spider):
    global xurl, headers

    def getName(self):
        return "星辰影院"

    def init(self, extend):
        pass

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def homeContent(self, filter):
        classes = [
            {"type_id": "1", "name": "电影"},
            {"type_id": "2", "name": "电视剧"},
            {"type_id": "3", "name": "综艺"},
            {"type_id": "4", "name": "动漫"},
            {"type_id": "28", "name": "纪录片"}
        ]
        return {'class': classes}

    def _parse_video_items(self, soup):
        videos = []
        seen_ids = set()

        for li in soup.select('li'):
            a_tag = li.select_one('a.stui-vodlist__thumb')
            if not a_tag:
                continue

            href = a_tag.get('href', '')
            if not href:
                continue
            vod_id = href if 'http' in href else xurl + href
            if vod_id in seen_ids:
                continue
            seen_ids.add(vod_id)

            img = a_tag.select_one('img')
            title = a_tag.get('title', '')
            if not title and img:
                title = img.get('alt', '')
            if not title:
                title = a_tag.get_text(strip=True)
            if not title:
                continue

            pic = a_tag.get('data-original', '')
            if not pic and img:
                pic = img.get('data-original') or img.get('src', '')
            if pic and not pic.startswith('http'):
                pic = xurl + ('' if pic.startswith('/') else '/') + pic

            remark = ''
            remark_span = a_tag.select_one('span.pic-text')
            if remark_span:
                remark = remark_span.get_text(strip=True)

            videos.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark
            })
        return videos

    def homeVideoContent(self):
        return {'list': self._parse_video_items(BeautifulSoup(requests.get(xurl, headers=headers).text, 'lxml'))}

    def categoryContent(self, cid, pg, filter, ext):
        page = int(pg) if pg else 1
        url = f"{xurl}/vtype/{cid}-{page}.html"
        videos = self._parse_video_items(BeautifulSoup(requests.get(url, headers=headers).text, 'lxml'))
        return {
            'list': videos,
            'page': page,
            'pagecount': 999,
            'limit': 90,
            'total': 9999
        }

    def detailContent(self, ids):
        did = ids[0]
        if not did.startswith('http'):
            did = urljoin(xurl, did)
        resp = requests.get(did, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, 'lxml')
        info = {'vod_id': did}

        thumb = soup.select_one('.stui-content__thumb img')
        if thumb:
            pic = thumb.get('data-original') or thumb.get('src', '')
            if pic and pic.startswith('//'):
                pic = 'https:' + pic
            elif pic and not pic.startswith('http'):
                pic = urljoin(xurl, pic)
            info['vod_pic'] = pic

        detail_div = soup.select_one('.stui-content')
        if detail_div:
            title_h1 = detail_div.select_one('h3.title')
            if title_h1:
                raw_title = title_h1.get_text(strip=True).replace('\n', '')
                info['vod_name'] = raw_title

            for p in detail_div.select('p.data'):
                text = p.get_text(strip=True)
                if '主演：' in text:
                    info['vod_actor'] = text.split('主演：')[-1].strip()
                if '类型：' in text:
                    info['type_name'] = text.split('类型：')[-1].strip()
                if '导演：' in text:
                    info['vod_director'] = text.split('导演：')[-1].strip()
                if '状态：' in text:
                    info['vod_remarks'] = text.split('状态：')[-1].strip()
                if '年代：' in text:
                    info['vod_year'] = text.split('年代：')[-1].strip()
                if '地区：' in text:
                    info['vod_area'] = text.split('地区：')[-1].strip()

        content_div = soup.select_one('.detail-content')
        if content_div:
            p = content_div.find('p')
            if p:
                text = p.get_text(strip=True)
            else:
                text = content_div.get_text(strip=True)
            text = re.sub(r'^简介[：:]\s*', '', text)
            info['vod_content'] = text
        else:
            info['vod_content'] = ''

        filter_lines = ['猜您喜欢', '同类型']
        filter_titles = ['1080P', 'дрр滈凊']
        ktabs = []
        klists = []
        seen_lines = set()

        line_items = soup.select('.stui-pannel__head h3')
        playlist_containers = soup.select('.stui-content__playlist')

        for idx, tab in enumerate(line_items):
            if idx >= len(playlist_containers):
                break
            line_name = tab.get_text(strip=True)
            if not line_name or line_name in filter_lines:
                continue
            if line_name in seen_lines:
                continue
            container = playlist_containers[idx]
            episode_links = container.select('li a')
            if not episode_links:
                continue
            klist = []
            for ep in episode_links:
                ep_name = ep.get_text(strip=True)
                ep_link = ep.get('href', '')
                if ep_name in filter_titles:
                    continue
                if ep_name and ep_link:
                    klist.append(f'{ep_name}${ep_link}')
            if klist:
                seen_lines.add(line_name)
                ktabs.append(line_name)
                klists.append('#'.join(klist))

        info["vod_play_from"] = '$$$'.join(ktabs)
        info["vod_play_url"] = '$$$'.join(klists)

        return {'list': [info]}

    def playerContent(self, flag, id, vipFlags):
        try:
            play_url = id if id.startswith(('http://', 'https://')) else xurl + id
            html = requests.get(play_url, headers=headers, timeout=10).text

            pattern = r'var\s+player_\w+\s*=\s*(\{[^;]+?\})\s*(?:;|</script)'
            match = re.search(pattern, html, re.DOTALL)
            video_url = ''
            if match:
                try:
                    json_str = match.group(1).strip()
                    json_str = re.sub(r',\s*}', '}', json_str)
                    data = json.loads(json_str)
                    video_url = data.get('url', '')
                except Exception:
                    pass

            if not video_url:
                m3u8_match = re.search(r'["\']url["\']\s*:\s*["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', html)
                if m3u8_match:
                    video_url = m3u8_match.group(1)

            if video_url:
                parse = 0 if re.search(r'\.(m3u8|mp4|mkv|flv|ts)$', video_url, re.I) else 1
                if parse:
                    video_url = play_url
            else:
                parse = 1
                video_url = play_url

            return {"parse": parse, "playUrl": "", "url": video_url, "header": headers}
        except Exception as e:
            print(f"player error: {e}")
            return {"parse": 1, "playUrl": "", "url": xurl + id, "header": headers}

    def searchContent(self, key, quick, page='1'):
        page = int(page) if page else 1
        encoded_key = urllib.parse.quote(key, safe='')
        url = f"{xurl}/vodsearch/{encoded_key}----------{page}---.html"
        soup = BeautifulSoup(requests.get(url, headers=headers).text, 'lxml')
        videos = self._parse_video_items(soup)
        return {
            'list': videos,
            'page': page,
            'pagecount': 60,
            'limit': 30,
            'total': 999999
        }

    def localProxy(self, params):
        if params['type'] == "m3u8":
            return self.proxyM3u8(params)
        elif params['type'] == "media":
            return self.proxyMedia(params)
        elif params['type'] == "ts":
            return self.proxyTs(params)
        return None