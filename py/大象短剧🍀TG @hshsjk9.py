# coding=utf-8
"""
目标站: 大象短剧 (m.nmshop.net)
修复：1.剧集倒序；2.日韩分类卡屏闪退；解析容错+单页上限
"""
import re
import sys
import json
import urllib.parse
from bs4 import BeautifulSoup

sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
    def init(self, extend=""):
        self.site_url = "https://m.nmshop.net"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            'Referer': self.site_url,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9'
        }
        self.categories = self._fetch_categories()

    def _fetch_categories(self):
        try:
            resp = self.fetch(self.site_url, headers=self.headers)
            if not resp:
                return self._default_categories()
            soup = BeautifulSoup(resp.text, 'html.parser')
            nav_links = soup.select('.stui-header__menu li a')
            categories = []
            seen = set()
            for a in nav_links:
                href = a.get('href', '')
                match = re.search(r'/zixun/(\d+)\.html', href)
                if not match:
                    continue
                tid = match.group(1)
                name = a.get_text(strip=True)
                if not name or tid in seen or name == '首页':
                    continue
                seen.add(tid)
                categories.append({"type_id": tid, "type_name": name})
            if categories:
                return categories
        except Exception as e:
            print(f"[大象短剧] 获取分类失败: {e}")
        return self._default_categories()

    def _default_categories(self):
        return [
            {"type_id": "1", "type_name": "电影"},
            {"type_id": "2", "type_name": "电视剧"},
            {"type_id": "3", "type_name": "综艺"},
            {"type_id": "4", "type_name": "动漫"},
            {"type_id": "30", "type_name": "日韩"},
            {"type_id": "36", "type_name": "MV专区"},
        ]

    def _fix_url(self, url):
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if not url.startswith("http"):
            return urllib.parse.urljoin(self.site_url + "/", url)
        return url

    # ================= 首页推荐 =================
    def homeContent(self, filter):
        url = self.site_url + "/"
        resp = self.fetch(url, headers=self.headers)
        video_list = []
        if resp:
            soup = BeautifulSoup(resp.text, 'html.parser')
            items = soup.select('.stui-vodlist__box')
            for item in items:
                try:
                    link = item.select_one('a.stui-vodlist__thumb')
                    if not link:
                        continue
                    href = link.get('href', '')
                    vod_id = re.search(r'/(?:weihu|v)/(\d+)\.html', href)
                    if not vod_id:
                        continue
                    vod_id = vod_id.group(1)
                    title = link.get('title', '') or link.get('alt', '')
                    if not title:
                        title_elem = item.select_one('.stui-vodlist__detail h4 a')
                        if title_elem:
                            title = title_elem.get('title', '') or title_elem.get_text(strip=True)
                    if not title:
                        continue
                    pic = link.get('data-original', '')
                    if not pic:
                        style = link.get('style', '')
                        bg_match = re.search(r'url\(([^)]+)\)', style)
                        if bg_match:
                            pic = bg_match.group(1).strip('"\'')
                    pic = self._fix_url(pic)
                    if not pic:
                        continue
                    remark = ''
                    remark_elem = item.select_one('.pic-text')
                    if remark_elem:
                        remark = remark_elem.get_text(strip=True)
                    video_list.append({
                        "vod_id": vod_id,
                        "vod_name": title,
                        "vod_pic": pic,
                        "vod_remarks": remark
                    })
                    if len(video_list) >= 24:
                        break
                except Exception:
                    continue
        return {"class": self.categories, "list": video_list, "filters": {}}

    def homeVideoContent(self):
        return self.homeContent(False)

    # ================= 分类列表【强容错修复闪退】 =================
    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if page == 1:
            url = f"{self.site_url}/zixun/{tid}.html"
        else:
            url = f"{self.site_url}/zixun/{tid}-{page}.html"

        resp = self.fetch(url, headers=self.headers)
        if not resp:
            return {"list": [], "page": page, "pagecount": 1, "limit": 24, "total": 0}

        soup = BeautifulSoup(resp.text, 'html.parser')
        video_list = []
        items = soup.select('.stui-vodlist__box')
        if not items:
            items = soup.select('.stui-vodlist li')

        for item in items:
            try:
                link = item.select_one('a.stui-vodlist__thumb')
                if not link:
                    continue
                href = link.get('href', '')
                vod_id = re.search(r'/(?:weihu|v)/(\d+)\.html', href)
                if not vod_id:
                    continue
                vod_id = vod_id.group(1)
                title = link.get('title', '') or link.get('alt', '')
                if not title:
                    title_elem = item.select_one('.stui-vodlist__detail h4 a')
                    if title_elem:
                        title = title_elem.get('title', '') or title_elem.get_text(strip=True)
                if not title or len(title.strip()) < 2:
                    continue
                pic = link.get('data-original', '')
                if not pic:
                    style = link.get('style', '')
                    bg_match = re.search(r'url\(([^)]+)\)', style)
                    if bg_match:
                        pic = bg_match.group(1).strip('"\'')
                pic = self._fix_url(pic)
                if not pic:
                    continue
                remark = ''
                remark_elem = item.select_one('.pic-text')
                if remark_elem:
                    remark = remark_elem.get_text(strip=True)
                video_list.append({
                    "vod_id": vod_id,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remark
                })
                if len(video_list) >= 24:
                    break
            except Exception:
                continue

        pagecount = page
        pagination = soup.select('.stui-page a, .page a')
        if pagination:
            nums = []
            for a in pagination:
                txt = a.get_text(strip=True)
                if txt.isdigit():
                    nums.append(int(txt))
            if nums:
                pagecount = max(nums)

        return {
            "list": video_list,
            "page": page,
            "pagecount": pagecount,
            "limit": 24,
            "total": 0
        }

    # ================= 详情页【新增反转剧集顺序】 =================
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = ids[0]
        trial_urls = [
            f"{self.site_url}/weihu/{vod_id}.html",
            f"{self.site_url}/v/{vod_id}.html"
        ]
        resp = None
        use_url = ""
        for u in trial_urls:
            r = self.fetch(u, headers=self.headers)
            if r and r.status_code == 200 and len(r.text) > 300:
                resp = r
                use_url = u
                break
        if not resp:
            print("[大象短剧] 两个详情链接全部请求失败")
            return {"list": []}

        soup = BeautifulSoup(resp.text, 'html.parser')

        vod_name = ''
        title_elem = soup.select_one('.stui-content__title h1,h1')
        if title_elem:
            vod_name = title_elem.get_text(strip=True)
        if not vod_name:
            t_tag = soup.select_one('title')
            if t_tag:
                t_txt = t_tag.get_text(strip=True)
                vod_name = re.sub(r'[-|_]\s*大象短剧.*$', '', t_txt).strip()
        if not vod_name:
            vod_name = f"视频{vod_id}"

        vod_pic = ''
        img_elem = soup.select_one('.stui-content__thumb img')
        if img_elem:
            vod_pic = img_elem.get('data-original','') or img_elem.get('src','')
        vod_pic = self._fix_url(vod_pic)

        vod_content = ''
        content_elem = soup.select_one('.stui-content__desc,.vod-content,.detail-content')
        if content_elem:
            vod_content = content_elem.get_text(' ', strip=True)

        vod_actor, vod_director, vod_year = "","",""
        info_block = soup.select_one('.stui-content__detail')
        if info_block:
            info_text = info_block.get_text(strip=True)
            actor_m = re.search(r'主演[:：]\s*([^导演地区年份]{3,40})',info_text)
            if actor_m:
                vod_actor = actor_m.group(1).strip()
            dir_m = re.search(r'导演[:：]\s*([^主演地区年份]{2,25})',info_text)
            if dir_m:
                vod_director = dir_m.group(1).strip()
            yr_m = re.search(r'(\d{4})',info_text)
            if yr_m:
                vod_year = yr_m.group(1)

        play_from_list = []
        play_url_list = []
        play_blocks = soup.select('.stui-content__playlist,.stui-play__list,ul.playlist')
        if play_blocks:
            for idx,blk in enumerate(play_blocks):
                line_name = f"线路{idx+1}"
                name_elem = blk.select_one('.play-title,.line-name')
                if name_elem:
                    line_name = name_elem.get_text(strip=True)
                eps = []
                for a in blk.select('a'):
                    href = a.get('href','')
                    if not href or 'javascript' in href:
                        continue
                    ep_name = a.get_text(strip=True) or f"第{len(eps)+1}集"
                    full_ep = self._fix_url(href)
                    eps.append(f"{ep_name}${full_ep}")
                # ===核心修复：翻转集数顺序===
                if len(eps) > 1:
                    eps.reverse()
                if eps:
                    play_from_list.append(line_name)
                    play_url_list.append('#'.join(eps))

        if not play_url_list:
            play_from_list.append("默认源")
            play_url_list.append(f"播放${use_url}")

        vod_play_from = '$$$'.join(play_from_list)
        vod_play_url = '$$$'.join(play_url_list)

        result_item = {
            "vod_id": vod_id,
            "vod_name": vod_name,
            "vod_pic": vod_pic,
            "vod_content": vod_content,
            "vod_actor": vod_actor,
            "vod_director": vod_director,
            "vod_area": "",
            "vod_year": vod_year,
            "vod_play_from": vod_play_from,
            "vod_play_url": vod_play_url
        }
        return {"list": [result_item]}

    # ================= 搜索 =================
    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        encoded_key = urllib.parse.quote(key)
        url = f"{self.site_url}/search.php?wd={encoded_key}"
        if page > 1:
            url += f"&page={page}"

        resp = self.fetch(url, headers=self.headers)
        if not resp:
            return {"list": [], "page": page, "pagecount": 1}

        soup = BeautifulSoup(resp.text, 'html.parser')
        video_list = []
        items = soup.select('.stui-vodlist__box')
        if not items:
            items = soup.select('.stui-vodlist li')

        for item in items:
            try:
                link = item.select_one('a.stui-vodlist__thumb')
                if not link:
                    continue
                href = link.get('href', '')
                vod_id = re.search(r'/(?:weihu|v)/(\d+)\.html', href)
                if not vod_id:
                    continue
                vod_id = vod_id.group(1)
                title = link.get('title', '') or link.get('alt', '')
                if not title:
                    title_elem = item.select_one('.stui-vodlist__detail h4 a')
                    if title_elem:
                        title = title_elem.get('title', '') or title_elem.get_text(strip=True)
                if not title:
                    continue
                pic = link.get('data-original', '')
                if not pic:
                    style = link.get('style', '')
                    bg_match = re.search(r'url\(([^)]+)\)', style)
                    if bg_match:
                        pic = bg_match.group(1).strip('"\'')
                pic = self._fix_url(pic)
                if not pic:
                    continue
                remark = ''
                remark_elem = item.select_one('.pic-text')
                if remark_elem:
                    remark = remark_elem.get_text(strip=True)
                video_list.append({
                    "vod_id": vod_id,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remark
                })
                if len(video_list) >= 24:
                    break
            except Exception:
                continue

        pagecount = page
        pagination = soup.select('.stui-page a, .page a')
        if pagination:
            nums = []
            for a in pagination:
                txt = a.get_text(strip=True)
                if txt.isdigit():
                    nums.append(int(txt))
            if nums:
                pagecount = max(nums)

        return {"list": video_list, "page": page, "pagecount": pagecount}

    # ================= 播放解析 =================
    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 0, "playUrl": "", "url": ""}

        play_url = self._fix_url(id)
        headers = dict(self.headers)
        headers['Referer'] = self.site_url + '/'
        max_depth = 8

        def _extract(url, depth):
            if depth > max_depth:
                return None
            lowurl = url.lower()
            if lowurl.endswith(".m3u8") or lowurl.endswith(".mp4"):
                return url
            resp = self.fetch(url, headers=headers)
            if not resp:
                return None
            html = resp.text
            iframe_r = re.search(r'<iframe[^>]+src="([^"]+)"', html)
            if iframe_r:
                nxt = self._fix_url(iframe_r.group(1))
                if nxt != url:
                    return _extract(nxt, depth+1)
            pa_reg = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\});', html, re.DOTALL)
            if pa_reg:
                try:
                    jdata = json.loads(pa_reg.group(1))
                    for k in ("url","link"):
                        val = jdata.get(k,"")
                        if val:
                            val = self._fix_url(val)
                            vl = val.lower()
                            if ".m3u8" in vl or ".mp4" in vl:
                                return val
                            if val != url:
                                return _extract(val, depth+1)
                except Exception:
                    pass
            direct_m3u8 = re.search(r'https?://[^"\']+\.m3u8[^"\']*',html)
            if direct_m3u8:
                return direct_m3u8.group(0)
            direct_mp4 = re.search(r'https?://[^"\']+\.mp4[^"\']*',html)
            if direct_mp4:
                return direct_mp4.group(0)
            return None

        final = _extract(play_url,0)
        if final:
            final = self._fix_url(final)
            return {
                "parse":0,
                "playUrl":"",
                "url":final,
                "header":headers
            }
        else:
            return {
                "parse":1,
                "playUrl":"",
                "url":play_url,
                "header":headers
            }
