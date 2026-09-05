# coding=utf-8
"""
目标站: 30剧集网 (30juz.com)
完整版爬虫 - 支持分类浏览、图片显示、完整集数列表（含第1集）、播放解析
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
        self.site_url = "http://www.30juz.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': self.site_url,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        # 硬编码分类
        self.categories = [
            {"type_id": "5", "type_name": "短剧"},
            {"type_id": "3", "type_name": "动漫"},
        ]

    def _fix_url(self, url):
        """补全URL"""
        if not url:
            return ""
        url = url.strip()
        if url.startswith("//"):
            return "http:" + url
        if url.startswith("/"):
            return self.site_url + url
        if not url.startswith("http"):
            return urllib.parse.urljoin(self.site_url + "/", url)
        return url

    def _get_real_pic(self, elem):
        """提取真实图片地址"""
        if not elem:
            return ""
        # 按优先级提取
        for attr in ['data-original', 'data-src', 'src', 'data-lazy-src']:
            val = elem.get(attr, '')
            if val and not val.startswith('data:') and 'loading' not in val.lower():
                return self._fix_url(val)
        # 从style中提取
        style = elem.get('style', '')
        bg_match = re.search(r'background(?:-image)?:\s*url\(([^)]+)\)', style)
        if bg_match:
            return self._fix_url(bg_match.group(1).strip('"').strip("'"))
        # 从父级style提取
        parent = elem.parent
        if parent:
            style = parent.get('style', '')
            bg_match = re.search(r'background(?:-image)?:\s*url\(([^)]+)\)', style)
            if bg_match:
                return self._fix_url(bg_match.group(1).strip('"').strip("'"))
        return ""

    def _parse_video_list(self, html, max_count=0):
        """解析视频列表页"""
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'html.parser')
        results = []
        seen = set()
        
        for item in soup.select('.myui-vodlist__box'):
            if max_count and len(results) >= max_count:
                break
                
            a = item.select_one('a.myui-vodlist__thumb')
            if not a:
                continue
            
            href = a.get('href', '')
            vod_match = re.search(r'/(duanju|dongman)/(\d+)-', href)
            if not vod_match:
                continue
            
            vid = vod_match.group(2)
            if vid in seen:
                continue
            seen.add(vid)
            
            title = a.get('title', '') or a.get_text(strip=True)
            if not title:
                continue
            
            pic = self._get_real_pic(a)
            
            remark = ''
            pic_text = a.select_one('.pic-text')
            if pic_text:
                remark = pic_text.get_text(strip=True)
            
            if not remark:
                detail = item.select_one('.myui-vodlist__detail')
                if detail:
                    for p in detail.select('.text-muted, .text'):
                        text = p.get_text(strip=True)
                        if any(k in text for k in ['更新至', '已完结', '集', '共']):
                            remark = text
                            break
            
            results.append({
                "vod_id": vid,
                "vod_name": title.strip(),
                "vod_pic": pic,
                "vod_remarks": remark
            })
        
        return results

    def homeContent(self, filter):
        """首页内容"""
        url = self.site_url + "/"
        resp = self.fetch(url, headers=self.headers, timeout=10)
        video_list = []
        if resp:
            video_list = self._parse_video_list(resp.text, 30)
        return {"class": self.categories, "list": video_list, "filters": {}}

    def homeVideoContent(self):
        return self.homeContent(False)

    def categoryContent(self, tid, pg, filter, extend):
        """分类页内容"""
        page = int(pg) if pg else 1
        
        # 尝试多种URL格式
        urls_to_try = []
        if page == 1:
            urls_to_try.append(f"{self.site_url}/list/{tid}.html")
        urls_to_try.append(f"{self.site_url}/list/{tid}-page{page}.html")
        urls_to_try.append(f"{self.site_url}/vodshow/{tid}-{page}.html")
        urls_to_try.append(f"{self.site_url}/vodtype/{tid}-{page}.html")
        
        html_text = ""
        for url in urls_to_try:
            resp = self.fetch(url, headers=self.headers, timeout=10)
            if resp:
                html_text = resp.text
                break
        
        if not html_text:
            return {"list": [], "page": page, "pagecount": 1, "limit": 24, "total": 0}
        
        video_list = self._parse_video_list(html_text)
        
        # 解析总页数
        pagecount = page
        soup = BeautifulSoup(html_text, 'html.parser')
        for a in soup.select('.myui-page a, .page a, .pagination a'):
            text = a.get_text(strip=True)
            if text.isdigit():
                num = int(text)
                if num > pagecount:
                    pagecount = num
        
        return {
            "list": video_list,
            "page": page,
            "pagecount": pagecount,
            "limit": 24,
            "total": len(video_list) * pagecount
        }

    def detailContent(self, ids):
        """详情页 - 显示完整集数（含第1集）"""
        if not ids:
            return {"list": []}
        
        vod_id = ids[0]
        url = f"{self.site_url}/duanju/{vod_id}-0-1.html"
        resp = self.fetch(url, headers=self.headers, timeout=10)
        if not resp:
            return {"list": []}
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # === 基本信息 ===
        title_elem = soup.select_one('.myui-content__title h1, .vod-title, h1')
        vod_name = title_elem.get_text(strip=True) if title_elem else vod_id
        
        img_elem = soup.select_one('.myui-content__thumb img, .vod-pic img, .detail-pic img')
        vod_pic = self._get_real_pic(img_elem) if img_elem else ""
        
        content_elem = soup.select_one('.myui-content__desc, .vod-content, .detail-content')
        vod_content = content_elem.get_text(' ', strip=True) if content_elem else ""
        
        # 演员
        vod_actor = ''
        actor_elem = soup.select_one('.myui-content__actor, .vod-actor, .actor')
        if actor_elem:
            vod_actor = actor_elem.get_text(strip=True).replace('主演：', '').strip()
        
        # 导演
        vod_director = ''
        director_elem = soup.select_one('.myui-content__director, .vod-director, .director')
        if director_elem:
            vod_director = director_elem.get_text(strip=True).replace('导演：', '').strip()
        
        # 年份
        vod_year = ''
        year_elem = soup.select_one('.myui-content__year, .vod-year, .year')
        if year_elem:
            vod_year = year_elem.get_text(strip=True).replace('年份：', '').strip()
        
        # === 提取完整集数（含第1集） ===
        play_from_list = []
        play_url_list = []
        
        # 方法1：从所有链接中提取
        all_links = soup.select('a[href*="/duanju/"]')
        episodes = []
        episode_set = set()
        
        for a in all_links:
            href = a.get('href', '')
            match = re.search(r'/duanju/(\d+)-0-(\d+)\.html', href)
            if not match:
                continue
            vid = match.group(1)
            ep_num = int(match.group(2))
            # 只过滤 ep_num = 0 的无效链接，保留第1集
            if vid != vod_id or ep_num < 1:
                continue
            if ep_num in episode_set:
                continue
            episode_set.add(ep_num)
            
            ep_name = a.get_text(strip=True)
            if not ep_name or ep_name in ['播放', '详情', '立即播放']:
                ep_name = f"第{ep_num}集"
            full_url = self._fix_url(href)
            episodes.append((ep_num, ep_name, full_url))
        
        if episodes:
            episodes.sort(key=lambda x: x[0])
            ep_list = [f"{name}${url}" for _, name, url in episodes]
            play_from_list.append('默认线路')
            play_url_list.append('#'.join(ep_list))
            print(f"[30剧集网] 找到 {len(episodes)} 个播放链接（含第1集）")
        
        # 方法2：从播放列表区域查找
        if not episodes:
            play_blocks = soup.select('.myui-content__playlist, .play-list, .vod-play-list, .playlist, .myui-panel_bd ul')
            for block in play_blocks:
                block_eps = []
                for a in block.select('a[href*="/duanju/"]'):
                    href = a.get('href', '')
                    match = re.search(r'/duanju/(\d+)-0-(\d+)\.html', href)
                    if not match:
                        continue
                    vid = match.group(1)
                    ep_num = int(match.group(2))
                    if vid != vod_id or ep_num < 1:
                        continue
                    if ep_num in episode_set:
                        continue
                    episode_set.add(ep_num)
                    ep_name = a.get_text(strip=True) or f"第{ep_num}集"
                    full_url = self._fix_url(href)
                    block_eps.append((ep_num, ep_name, full_url))
                if block_eps:
                    block_eps.sort(key=lambda x: x[0])
                    ep_list = [f"{name}${url}" for _, name, url in block_eps]
                    play_from_list.append('默认线路')
                    play_url_list.append('#'.join(ep_list))
                    break
        
        # 方法3：自动构造（兜底方案）
        if not episodes:
            page_text = soup.get_text()
            total_eps = 0
            
            patterns = [
                r'共(\d+)集',
                r'更新至(\d+)集',
                r'全(\d+)集',
                r'(\d+)集全',
                r'已完结[^\d]*(\d+)集',
            ]
            for pattern in patterns:
                match = re.search(pattern, page_text)
                if match:
                    total_eps = int(match.group(1))
                    break
            
            # 如果没找到，尝试从已有的集数中推断
            if not total_eps and '已完结' in page_text:
                ep_nums = re.findall(r'/duanju/{}[-_]0[-_](\d+)\.html'.format(vod_id), page_text)
                if ep_nums:
                    total_eps = max([int(n) for n in ep_nums])
                else:
                    total_eps = 30
            
            # 如果还是没找到，尝试从"共X集"或"更新至X集"文本中提取
            if not total_eps:
                # 查找页面中所有数字+集的组合
                all_numbers = re.findall(r'(\d+)\s*集', page_text)
                if all_numbers:
                    total_eps = max([int(n) for n in all_numbers])
            
            if total_eps > 0:
                ep_list = []
                # 从第1集开始构造
                for i in range(1, total_eps + 1):
                    ep_url = f"{self.site_url}/duanju/{vod_id}-0-{i}.html"
                    ep_list.append(f"第{i}集${ep_url}")
                if ep_list:
                    play_from_list.append('默认线路')
                    play_url_list.append('#'.join(ep_list))
                print(f"[30剧集网] 自动构造 {total_eps} 集（含第1集）")
        
        # 如果还是没有集数，使用默认播放地址
        if not play_url_list:
            # 尝试直接使用详情页作为播放地址
            play_from_list.append('默认源')
            play_url_list.append(f"播放${url}")
        
        vod_play_from = '$$$'.join(play_from_list) if play_from_list else '默认源'
        vod_play_url = '$$$'.join(play_url_list) if play_url_list else f"播放${vod_id}"
        
        result = [{
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
        }]
        
        return {"list": result}

    def searchContent(self, key, quick, pg="1"):
        """搜索功能"""
        page = int(pg) if pg else 1
        encoded_key = urllib.parse.quote(key)
        url = f"{self.site_url}/sousuo--page{page}.html?wd={encoded_key}"
        
        resp = self.fetch(url, headers=self.headers, timeout=10)
        if not resp:
            return {"list": [], "page": page, "pagecount": 1}
        
        video_list = self._parse_video_list(resp.text)
        return {"list": video_list, "page": page, "pagecount": 1}

    def playerContent(self, flag, id, vipFlags):
        """播放解析 - 深度解析视频地址"""
        play_url = self._fix_url(id)
        print(f"[30剧集网] 播放解析: {play_url}")
        
        # 如果是直链，直接返回
        if re.search(r'\.(m3u8|mp4|flv|mkv|ts)(\?|$)', play_url, re.I):
            return {"parse": 0, "url": play_url, "header": self.headers}
        
        headers = dict(self.headers)
        headers['Referer'] = self.site_url + '/'
        
        max_depth = 8
        visited = set()
        
        def _extract(url, depth):
            if depth > max_depth or url in visited:
                return None
            visited.add(url)
            
            # 直链检测
            if re.search(r'\.(m3u8|mp4|flv|mkv|ts)(\?|$)', url, re.I):
                return url
            
            resp = self.fetch(url, headers=headers, timeout=15)
            if not resp:
                return None
            
            html = resp.text
            
            # 1. player_aaaa（30剧集网常用）
            match = re.search(r'var\s+player_aaaa\s*=\s*({[^;]+})', html, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    link = data.get('link', '')
                    if link:
                        next_url = self._fix_url(link)
                        if next_url != url:
                            result = _extract(next_url, depth + 1)
                            if result:
                                return result
                    url_val = data.get('url', '')
                    if url_val:
                        next_url = self._fix_url(url_val)
                        if re.search(r'\.(m3u8|mp4|flv)', next_url, re.I):
                            return next_url
                        if next_url != url:
                            result = _extract(next_url, depth + 1)
                            if result:
                                return result
                except Exception as e:
                    print(f"[30剧集网] player_aaaa解析失败: {e}")
            
            # 2. play / video / src / playUrl / file 变量
            for var in ['play', 'video', 'src', 'playUrl', 'file']:
                match = re.search(r'var\s+{}\s*=\s*["\']([^"\']+)["\']'.format(var), html, re.I)
                if match:
                    next_url = self._fix_url(match.group(1))
                    if re.search(r'\.(m3u8|mp4|flv)', next_url, re.I):
                        return next_url
                    if next_url != url:
                        result = _extract(next_url, depth + 1)
                        if result:
                            return result
            
            # 3. video / source 标签
            for tag in ['video', 'source']:
                match = re.search(r'<{}[^>]+src="([^"]+)"'.format(tag), html, re.I)
                if match:
                    return self._fix_url(match.group(1))
            
            # 4. iframe
            iframe = re.search(r'<iframe[^>]+src="([^"]+)"', html, re.I)
            if iframe:
                iframe_url = self._fix_url(iframe.group(1))
                if iframe_url != url:
                    result = _extract(iframe_url, depth + 1)
                    if result:
                        return result
            
            # 5. 直接匹配 m3u8/mp4/flv
            for ext in ['m3u8', 'mp4', 'flv']:
                match = re.search(r'(https?://[^\s"\']+\.{}[^\s"\']*)'.format(ext), html, re.I)
                if match:
                    return match.group(1)
            
            # 6. 播放器配置
            config_patterns = [
                r'video\s*[:=]\s*["\']([^"\']+\.(?:m3u8|mp4|flv)[^"\']*)["\']',
                r'url\s*[:=]\s*["\']([^"\']+\.(?:m3u8|mp4|flv)[^"\']*)["\']',
                r'file\s*[:=]\s*["\']([^"\']+\.(?:m3u8|mp4|flv)[^"\']*)["\']',
                r'src\s*[:=]\s*["\']([^"\']+\.(?:m3u8|mp4|flv)[^"\']*)["\']',
                r'playUrl\s*[:=]\s*["\']([^"\']+\.(?:m3u8|mp4|flv)[^"\']*)["\']',
            ]
            for pattern in config_patterns:
                match = re.search(pattern, html, re.I)
                if match:
                    return self._fix_url(match.group(1))
            
            # 7. data-video 属性
            data_video = re.search(r'data-video=["\']([^"\']+)["\']', html)
            if data_video:
                next_url = self._fix_url(data_video.group(1))
                if re.search(r'\.(m3u8|mp4|flv)', next_url, re.I):
                    return next_url
                if next_url != url:
                    result = _extract(next_url, depth + 1)
                    if result:
                        return result
            
            # 8. 页面跳转
            redirect = re.search(r'window\.location\.href\s*=\s*["\']([^"\']+)["\']', html)
            if redirect:
                next_url = self._fix_url(redirect.group(1))
                if next_url != url:
                    result = _extract(next_url, depth + 1)
                    if result:
                        return result
            
            # 9. meta refresh 跳转
            meta_refresh = re.search(r'<meta[^>]+http-equiv=["\']refresh["\'][^>]+content=["\'][^;]+;\s*url=([^"\']+)["\']', html, re.I)
            if meta_refresh:
                next_url = self._fix_url(meta_refresh.group(1))
                if next_url != url:
                    result = _extract(next_url, depth + 1)
                    if result:
                        return result
            
            # 10. 查找 json 格式的播放配置
            json_match = re.search(r'<script[^>]*>.*?({[^<]*"(?:url|video|src|file)"[^<]*})', html, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group(1))
                    for key in ['url', 'video', 'src', 'file']:
                        if key in data:
                            next_url = self._fix_url(data[key])
                            if re.search(r'\.(m3u8|mp4|flv)', next_url, re.I):
                                return next_url
                            if next_url != url:
                                result = _extract(next_url, depth + 1)
                                if result:
                                    return result
                except:
                    pass
            
            return None
        
        # 开始递归解析
        final_url = _extract(play_url, 0)
        
        if final_url:
            final_url = self._fix_url(final_url)
            if re.search(r'\.(m3u8|mp4|flv|mkv|ts)', final_url, re.I):
                print(f"[30剧集网] 解析成功: {final_url}")
                return {"parse": 0, "url": final_url, "header": headers}
            else:
                # 可能还有跳转
                return self.playerContent(flag, final_url, vipFlags)
        
        # 如果播放URL是详情页本身（第1集），尝试特殊处理
        if '/duanju/' in play_url and '-0-1.html' in play_url:
            print(f"[30剧集网] 检测到第1集（详情页），尝试从页面提取播放地址")
            # 获取详情页内容
            resp = self.fetch(play_url, headers=headers, timeout=10)
            if resp:
                html = resp.text
                # 查找页面中的第一个播放链接
                first_play = re.search(r'<a[^>]+href="([^"]*\/duanju\/[^"]*-0-(\d+)\.html)"', html)
                if first_play:
                    ep_num = int(first_play.group(2))
                    if ep_num > 1:
                        play_url = self._fix_url(first_play.group(1))
                        print(f"[30剧集网] 从详情页找到播放链接: {play_url}")
                        return self.playerContent(flag, play_url, vipFlags)
        
        # 解析失败时使用第三方解析接口
        if '30juz.com' in play_url:
            parse_url = f"https://jx.aidouer.net/?url={urllib.parse.quote(play_url)}"
            print(f"[30剧集网] 使用第三方解析: {parse_url}")
            return {"parse": 0, "url": parse_url, "header": headers}
        
        print(f"[30剧集网] 所有解析方法失败")
        return {"parse": 1, "url": play_url, "header": headers}