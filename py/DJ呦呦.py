# -*- coding: utf-8 -*-
# 兼容 OK影视/影视仓   
# 其它影视壳自测

from base.spider import Spider
import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import quote


class Spider(Spider):
    def getName(self):
        return "DJ呦呦"

    def init(self, extend=""):
        pass

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def homeContent(self, filter):
        result = {}
        result['filters'] = {}
        cateId = [
            {"type_name": "最近更新-专辑", "type_id": "ablum_i1"},
            {"type_name": "最新加入-专辑", "type_id": "ablum_i2"},
            {"type_name": "热门DJ-专辑", "type_id": "ablum_i3"},
            {"type_name": "独家舞曲", "type_id": "exclusive_115"},
            {"type_name": "迪高串烧", "type_id": "djlist_1"},
            {"type_name": "慢摇串烧", "type_id": "djlist_2"},
            {"type_name": "慢歌串烧", "type_id": "djlist_3"},
            {"type_name": "中文Remix", "type_id": "djlist_4"},
            {"type_name": "外文Remix", "type_id": "djlist_5"},
            {"type_name": "中文DISCO", "type_id": "djlist_9"},
            {"type_name": "外文DISCO", "type_id": "djlist_10"}
        ]
        result['class'] = cateId
        return result

    def homeVideoContent(self):
        return self.categoryContent("ablum_i1", 1, False, {})

    # ---------- 分类列表 ----------

    def categoryContent(self, tid, pg, filter, extend):
        result = {
            'list': [],
            'page': pg,
            'pagecount': 9999,
            'limit': 30,
            'total': 999999
        }
        path, cid = self._split_type(tid)

        try:
            if path == 'ablum':
                videos = self._category_ablum(cid, pg)
            elif path == 'exclusive':
                videos = self._category_songlist('exclusive', cid, pg)
            elif path == 'djlist':
                videos = self._category_songlist('djlist', cid, pg)
            else:
                videos = []

            result['list'] = videos
        except Exception:
            pass

        return result

    def _split_type(self, tid):
        # 格式: ablum_i1, exclusive_115, djlist_1
        if '_' in tid:
            path, cid = tid.split('_', 1)
            return path, cid
        return 'ablum', tid

    def _category_ablum(self, cid, pg):
        url = f"https://www.djuu.com/ablum/{cid}_{pg}.html"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.djuu.com/ablum/'
        }
        r = requests.get(url, headers=headers, timeout=10)
        r.encoding = 'utf-8'
        soup = BeautifulSoup(r.text, 'html.parser')

        videos = []
        container = soup.select_one('.djshow_contentlist')
        if container:
            for table in container.find_all('table', recursive=False):
                rows = table.find_all('tr')
                if not rows:
                    continue

                first_row = rows[0]
                img_a = first_row.find('a', href=re.compile(r'/ablum/\d+\.html'))
                if not img_a:
                    continue

                img = img_a.find('img')
                pic = (img.get('src') or '') if img else ''
                ablum_url = img_a.get('href', '')
                m = re.search(r'/ablum/(\d+)\.html', ablum_url)
                if not m:
                    continue

                name_a = table.find('a', class_='djshow_contentlist_name')
                name = name_a.get_text(strip=True) if name_a else '未知DJ'

                msgs = table.find_all('td', class_='djshow_contentlist_msg')
                area = msgs[0].get_text(strip=True) if len(msgs) > 0 else ''
                hot = msgs[2].get_text(strip=True) if len(msgs) > 2 else ''
                remarks = f"{area} | 热度:{hot}" if area and hot else (area or hot)

                videos.append({
                    "vod_id": m.group(1),
                    "vod_name": name,
                    "vod_pic": pic,
                    "vod_remarks": remarks
                })
        return videos

    def _category_songlist(self, path, cid, pg):
        url = f"https://www.djuu.com/{path}/{cid}_{pg}.html"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': f'https://www.djuu.com/{path}/'
        }
        r = requests.get(url, headers=headers, timeout=10)
        r.encoding = 'utf-8'
        soup = BeautifulSoup(r.text, 'html.parser')

        videos = []
        seen = set()
        for div in soup.find_all('div', class_='isgood_list'):
            img_a = div.find('a', href=re.compile(r'/play/\d+\.html'))
            title_a = div.find('p', class_='t1')
            if title_a:
                title_a = title_a.find('a', href=re.compile(r'/play/\d+\.html'))
            if not img_a or not title_a:
                continue

            m = re.search(r'/play/(\d+)\.html', img_a.get('href', ''))
            if not m:
                continue
            sid = m.group(1)
            if sid in seen:
                continue
            seen.add(sid)

            name = title_a.get('title') or title_a.get_text(strip=True)
            img = img_a.find('img')
            pic = (img.get('src') or '') if img else ''
            # 兼容懒加载
            if not pic:
                pic = (img.get('data-src') or '') if img else ''

            # 时长/大小作为备注
            spans = div.find_all('span')
            info = ' | '.join([s.get_text(strip=True) for s in spans[:3]])

            videos.append({
                "vod_id": f"song_{sid}",
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": info
            })
        return videos

    # ---------- 详情 ----------

    def detailContent(self, ids):
        rid = ids[0] if isinstance(ids, (list, tuple)) else ids
        result = {}

        try:
            if isinstance(rid, str) and rid.startswith('song_'):
                sid = rid.replace('song_', '', 1)
                vod = self._song_detail(sid)
            else:
                vod = self._ablum_detail(rid)
            result['list'] = [vod]
        except Exception as e:
            result['list'] = [{
                "vod_id": rid,
                "vod_name": "加载失败",
                "vod_content": f"加载失败: {str(e)}",
                "vod_remarks": "加载失败",
                "vod_actor": "未知",
                "vod_play_from": "DJ呦呦",
                "vod_play_url": "",
                "vod_pic": ""
            }]

        return result

    def _ablum_detail(self, rid):
        vod_name, pic, content = self._ablum_info(rid)
        songs = self._ablum_songs(rid)

        play_arr = []
        for song in songs:
            name = re.sub(r'[$#]', '', song.get('name', '')).strip()
            sid = song.get('id', '')
            if name and sid:
                play_arr.append(f"{name}${sid}")

        return {
            "vod_id": rid,
            "vod_name": vod_name,
            "vod_pic": pic,
            "vod_content": content if content else "暂无简介",
            "vod_remarks": f"歌曲 : {len(songs)}首",
            "vod_actor": vod_name,
            "vod_play_from": "DJ呦呦",
            "vod_play_url": "#".join(play_arr)
        }

    def _song_detail(self, sid):
        # 单曲详情：直接进入播放页取信息
        url = f"https://www.djuu.com/play/{sid}.html"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.djuu.com/'
        }
        r = requests.get(url, headers=headers, timeout=10)
        r.encoding = 'utf-8'
        soup = BeautifulSoup(r.text, 'html.parser')

        # 歌曲名
        name = ''
        h1 = soup.find('h1')
        if h1:
            name = h1.get_text(strip=True)
        if not name:
            m = re.search(r"var music = \{[^}]*name:\s*'([^']+)'", r.text)
            name = m.group(1) if m else '未知歌曲'

        # 封面：优先取播放器区域 / 旋转封面 / 模糊背景，避免取到广告图
        pic = self._extract_play_pic(soup)

        # 简介：取播放页信息
        content = ''
        info = soup.select_one('.djshow_djmsg_content') or soup.select_one('.play_info')
        if info:
            content = info.get_text('\n', strip=True)

        return {
            "vod_id": f"song_{sid}",
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content if content else "暂无简介",
            "vod_remarks": "单曲",
            "vod_actor": name,
            "vod_play_from": "DJ呦呦",
            "vod_play_url": f"{name}${sid}"
        }

    def _ablum_info(self, rid):
        url = f"https://www.djuu.com/ablum/{rid}.html"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.djuu.com/ablum/'
        }
        r = requests.get(url, headers=headers, timeout=10)
        r.encoding = 'utf-8'
        soup = BeautifulSoup(r.text, 'html.parser')

        h1 = soup.find('h1')
        vod_name = h1.get_text(strip=True) if h1 else '未知DJ'
        vod_name = re.sub(r'<[^>]+>', '', vod_name)

        pic = ''
        for img in soup.find_all('img', src=re.compile(r'img\.djuu\.com')):
            src = img.get('src') or ''
            pic = src or pic
            if 'ablum' in pic or 'dj_album' in pic:
                break

        content = ''
        info_div = soup.select_one('.djshow_djmsg_content')
        if info_div:
            content = info_div.get_text('\n', strip=True)

        return vod_name, pic, content

    def _ablum_songs(self, rid, max_pages=10, max_songs=300):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': f'https://www.djuu.com/ablum/{rid}.html'
        }

        songs = []
        for pg in range(1, max_pages + 1):
            url = f"https://www.djuu.com/ablum/{rid}_1_{pg}.html"
            try:
                r = requests.get(url, headers=headers, timeout=10)
                r.encoding = 'utf-8'
                soup = BeautifulSoup(r.text, 'html.parser')

                page_songs = []
                seen = set(s['id'] for s in songs)
                for a in soup.find_all('a', href=re.compile(r'/play/(\d+)\.html')):
                    sid = re.search(r'/play/(\d+)\.html', a.get('href', ''))
                    if not sid:
                        continue
                    song_id = sid.group(1)
                    if song_id in seen:
                        continue
                    title = a.get('title') or a.get_text(strip=True)
                    if title:
                        page_songs.append({'id': song_id, 'name': title})
                        seen.add(song_id)

                if not page_songs:
                    break

                songs.extend(page_songs)
                if len(songs) >= max_songs:
                    songs = songs[:max_songs]
                    break

            except Exception:
                continue

        return songs

    # ---------- 播放 ----------

    def _extract_play_pic(self, soup):
        """从播放页提取歌曲封面，优先排除广告图"""
        pic = ''
        for selector in ['#mcover', 'img.blur', '.play_detail img', '.play_p2 img', '.play_ct img']:
            el = soup.select_one(selector)
            if el and el.name == 'img':
                pic = el.get('src') or ''
            elif el:
                img = el.find('img')
                pic = (img.get('src') or '') if img else ''
            if pic:
                break
        # fallback：取包含 cover 且非 advert 的第一张图
        if not pic:
            for img in soup.find_all('img', src=re.compile(r'img\.djuu\.com')):
                src = img.get('src') or ''
                if 'cover' in src and 'advert' not in src:
                    pic = src
                    break
        # 最后兜底
        if not pic:
            first = soup.find('img', src=re.compile(r'img\.djuu\.com'))
            pic = (first.get('src') or '') if first else ''
        return pic

    def playerContent(self, flag, id, vipFlags):
        result = {}
        rid = id
        if isinstance(rid, str) and rid.startswith('song_'):
            rid = rid.replace('song_', '', 1)

        url = f"https://www.djuu.com/play/{rid}.html"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.djuu.com/'
        }

        try:
            r = requests.get(url, headers=headers, timeout=10)
            r.encoding = 'utf-8'
            html = r.text
            soup = BeautifulSoup(html, 'html.parser')

            # 歌曲名
            name = ''
            h1 = soup.find('h1')
            if h1:
                name = h1.get_text(strip=True)
            if not name:
                m = re.search(r"var music = \{[^}]*name:\s*'([^']+)'", html)
                name = m.group(1) if m else ''

            # 封面
            pic = self._extract_play_pic(soup)

            m = re.search(r"var music = \{[^}]*file:\s*'([^']+)'", html)
            if m:
                file_path = m.group(1)
                if file_path.startswith('http'):
                    play_url = file_path
                else:
                    play_url = f"https://mp4.djuu.com/{file_path}.m4a"
                result["parse"] = 0
                result["jx"] = 0
                result["playUrl"] = ""
                result["url"] = play_url
                result["header"] = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://www.djuu.com/"
                }
                result["pic"] = pic
                result["name"] = name
                return result

        except Exception:
            pass

        result["parse"] = 0
        result["jx"] = 0
        result["playUrl"] = ""
        result["url"] = ""
        result["header"] = {}
        result["pic"] = ""
        result["name"] = ""
        return result

    # ---------- 搜索 ----------

    def searchContent(self, key, quick, pg=1):
        result = {
            'list': [],
            'page': pg,
            'pagecount': 9999,
            'limit': 30,
            'total': 999999
        }
        wd = quote(key)
        url = f"https://www.djuu.com/search?musicname={wd}&page={pg}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.djuu.com/'
        }

        try:
            r = requests.get(url, headers=headers, timeout=10)
            r.encoding = 'utf-8'
            soup = BeautifulSoup(r.text, 'html.parser')

            videos = []
            seen = set()
            # 搜索结果为表格行，每行一个 isgood_list
            for tr in soup.find_all('tr', class_='sbg'):
                a = tr.find('a', href=re.compile(r'/play/\d+\.html'))
                if not a:
                    continue
                m = re.search(r'/play/(\d+)\.html', a.get('href', ''))
                if not m:
                    continue
                song_id = m.group(1)
                if song_id in seen:
                    continue
                seen.add(song_id)

                title = a.get('title') or a.get_text(strip=True)
                if not title:
                    continue

                pic = ''
                img = tr.find('img')
                if img:
                    pic = img.get('src') or ''
                    if not pic:
                        pic = img.get('data-src') or ''

                remarks = ''
                spans = tr.find_all('span', class_='sc_2')
                if spans:
                    remarks = ' | '.join([s.get_text(strip=True) for s in spans])

                videos.append({
                    "vod_id": f"song_{song_id}",
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remarks
                })

            result['list'] = videos
        except Exception:
            pass

        return result

    def searchContentPage(self, key, quick, pg):
        return self.searchContent(key, quick, pg)

    def localProxy(self, param):
        return {}
