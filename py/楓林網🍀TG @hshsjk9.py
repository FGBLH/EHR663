# coding=utf-8
"""
目标站: 楓林網 (imaple8.tv)
站点: https://imaple8.tv/
框架: 苹果CMS (maccms) + MYUI 模板
功能: 分类/首页/搜索/详情/播放解析（player_aaaa -> 直链 m3u8）
"""
import re
import sys
import json
import urllib.parse
from collections import OrderedDict
from bs4 import BeautifulSoup

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    def init(self, extend=""):
        self.site_url = "https://imaple8.tv"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': self.site_url + '/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
        }
        self.categories = self._fetch_categories()

    # ================= 分类 =================
    def _fetch_categories(self):
        try:
            resp = self.fetch(self.site_url + "/", headers=self.headers)
            if not resp:
                return self._default_categories()
            soup = BeautifulSoup(resp.text, 'html.parser')
            # 主导航里的 /vodtype/{tid}.html 才是大类（排除跳外站的成人/直播）
            exclude = ['首頁', '首页', '成人', '色色主播', 'APP', '留言', '客服']
            cats = []
            seen = set()
            for a in soup.select('a[href*="/vodtype/"]'):
                href = a.get('href', '')
                m = re.search(r'/vodtype/(\d+)\.html', href)
                if not m:
                    continue
                tid = m.group(1)
                name = a.get_text(strip=True)
                if not name or tid in seen or name in exclude:
                    continue
                # 只保留站内链接（外站如 go.ztv.tw 直接跳过）
                if href.startswith('http') and self.site_url not in href:
                    continue
                seen.add(tid)
                cats.append({"type_id": tid, "type_name": name})
            if cats:
                return cats
        except Exception as e:
            print(f"[楓林網] 获取分类失败: {e}")
        return self._default_categories()

    def _default_categories(self):
        return [
            {"type_id": "1", "type_name": "電影"},
            {"type_id": "2", "type_name": "電視劇"},
            {"type_id": "3", "type_name": "綜藝"},
            {"type_id": "4", "type_name": "動漫"},
        ]

    # ================= 工具 =================
    def _fix_url(self, url):
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("http"):
            return url
        return urllib.parse.urljoin(self.site_url + "/", url)

    def _parse_video_list(self, html):
        if not html:
            return []
        soup = BeautifulSoup(html, 'html.parser')
        results = []
        seen = set()
        for a in soup.select('a[href*="/voddetail/"]'):
            href = a.get('href', '')
            m = re.search(r'/voddetail/(\d+)\.html', href)
            if not m:
                continue
            vid = m.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            title = a.get('title') or a.get_text(strip=True)
            if not title:
                continue

            # 封面提取顺序:
            # 1) 锚点自身可能是懒加载图 (data-original / data-src)
            # 2) 子 <img> 的 data-original/src
            # 3) 锚点 style 里的 background:url()
            # 4) 向上找父级容器里的 img / background
            pic = a.get('data-original') or a.get('data-src') or ''
            img = a.select_one('img')
            if not pic and img:
                pic = img.get('data-original') or img.get('src', '')
            if not pic:
                style = a.get('style', '')
                bg = re.search(r'url\(([^)]+)\)', style)
                if bg:
                    pic = bg.group(1).strip('"').strip("'")
            if not pic:
                parent = a.parent
                for _ in range(3):
                    if not parent:
                        break
                    pimg = parent.select_one('img')
                    if pimg:
                        pic = pimg.get('data-original') or pimg.get('src', '')
                        if pic:
                            break
                    pstyle = parent.get('style', '')
                    bg = re.search(r'url\(([^)]+)\)', pstyle)
                    if bg:
                        pic = bg.group(1).strip('"').strip("'")
                        break
                    parent = parent.parent

            # 备注(画质/状态): 列表项内的 .pic-text / .myui-vodlist__text / .note
            remark = ''
            item = a
            for _ in range(4):
                if not item:
                    break
                note = item.select_one('.pic-text, .myui-vodlist__text, .note, .remark')
                if note:
                    remark = note.get_text(strip=True)
                    break
                item = item.parent
            # 去掉评分之类干扰，只保留常见画质/状态词
            if remark and re.search(r'(HD|中字|國語|粵語|完結|更新|集|P|分)', remark):
                pass
            else:
                remark = ''

            results.append({
                "vod_id": vid,
                "vod_name": title.strip(),
                "vod_pic": self._fix_url(pic),
                "vod_remarks": remark
            })
        return results

    # ================= 首页 =================
    def homeContent(self, filter):
        resp = self.fetch(self.site_url + "/", headers=self.headers)
        video_list = []
        if resp:
            video_list = self._parse_video_list(resp.text)
            video_list = video_list[:30]
        return {"class": self.categories, "list": video_list, "filters": {}}

    def homeVideoContent(self):
        return self.homeContent(False)

    # ================= 分类 =================
    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if page <= 1:
            url = f"{self.site_url}/vodtype/{tid}.html"
        else:
            url = f"{self.site_url}/vodtype/{tid}-{page}.html"
        resp = self.fetch(url, headers=self.headers)
        if not resp:
            return {"list": [], "page": page, "pagecount": 1, "limit": 24, "total": 0}
        html = resp.text
        video_list = self._parse_video_list(html)

        # 翻页: .myui-page a 里的 /vodtype/{tid}-N.html 取最大 N
        pagecount = page
        soup = BeautifulSoup(html, 'html.parser')
        nums = []
        for a in soup.select('.myui-page a'):
            m = re.search(r'/vodtype/%s-(\d+)\.html' % re.escape(tid), a.get('href', ''))
            if m:
                nums.append(int(m.group(1)))
        if nums:
            pagecount = max(nums)

        return {
            "list": video_list,
            "page": page,
            "pagecount": pagecount,
            "limit": 24,
            "total": len(video_list) * pagecount
        }

    # ================= 详情 =================
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = ids[0]
        url = f"{self.site_url}/voddetail/{vod_id}.html"
        resp = self.fetch(url, headers=self.headers)
        if not resp:
            return {"list": []}
        html = resp.text
        soup = BeautifulSoup(html, 'html.parser')
        text = soup.get_text(' ', strip=True)

        # 标题
        title_elem = soup.select_one('h1.title') or soup.select_one('h1')
        vod_name = title_elem.get_text(strip=True) if title_elem else vod_id

        # 封面
        vod_pic = ''
        img_elem = soup.select_one('.myui-content__thumb img')
        if img_elem:
            vod_pic = img_elem.get('data-original') or img_elem.get('src', '')
        vod_pic = self._fix_url(vod_pic)

        # 简介(优先 meta description)
        vod_content = ''
        meta = soup.find('meta', attrs={'name': 'description'})
        if meta and meta.get('content'):
            vod_content = meta.get('content').strip()

        # 主演/导演/年份/地区
        def _field(label):
            m = re.search(label + r'[:：]\s*([^<\s]+)', text)
            return m.group(1).strip() if m else ''

        vod_actor = _field('主演')
        vod_director = _field('導演')
        vod_year = _field('年份')
        vod_area = _field('地區')

        # 播放列表: 按 /vodplay/{id}-{from}-{n}.html 的 from 分组
        lines = OrderedDict()
        for a in soup.select('a[href*="/vodplay/"]'):
            m = re.search(r'/vodplay/(\d+)-(\d+)-(\d+)\.html', a.get('href', ''))
            if not m:
                continue
            frm = m.group(2)
            name = a.get_text(strip=True) or f"第{m.group(3)}集"
            full = self._fix_url(a.get('href'))
            lines.setdefault(frm, [])
            # 同一线路内按 url 去重
            if not any(full == u for _, u in lines[frm]):
                lines[frm].append((name, full))

        play_from_list = []
        play_url_list = []
        for i, (frm, eps) in enumerate(lines.items(), 1):
            play_from_list.append(f"线路{i}")
            play_url_list.append('#'.join(f"{n}${u}" for n, u in eps))

        vod_play_from = '$$$'.join(play_from_list) if play_from_list else '默认源'
        vod_play_url = '$$$'.join(play_url_list) if play_url_list else f"播放${vod_id}"

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": vod_name,
            "vod_pic": vod_pic,
            "vod_content": vod_content,
            "vod_actor": vod_actor,
            "vod_director": vod_director,
            "vod_area": vod_area,
            "vod_year": vod_year,
            "vod_play_from": vod_play_from,
            "vod_play_url": vod_play_url
        }]}

    # ================= 搜索 =================
    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        encoded_key = urllib.parse.quote(key)
        url = f"{self.site_url}/vodsearch/-------------.html?wd={encoded_key}"
        if page > 1:
            url += f"&page={page}"
        resp = self.fetch(url, headers=self.headers)
        if not resp:
            return {"list": [], "page": page, "pagecount": 1}
        video_list = self._parse_video_list(resp.text)
        return {"list": video_list, "page": page, "pagecount": 1}

    # ================= 播放解析 =================
    def playerContent(self, flag, id, vipFlags):
        """
        递归解析播放地址:
        - player_aaaa.url 直链(m3u8/mp4)
        - player_aaaa.link 跳转
        - iframe 深度递归
        - video / source 标签
        - 直接匹配 m3u8
        - 最大递归深度 8
        """
        play_url = self._fix_url(id)

        if re.search(r'\.(m3u8|mp4|flv)(\?|$)', play_url, re.I):
            return {"parse": 0, "url": play_url, "header": self.headers}

        headers = dict(self.headers)
        headers['Referer'] = self.site_url + '/'
        max_depth = 8

        def _extract(url, depth):
            if depth > max_depth:
                return None
            if re.search(r'\.(m3u8|mp4|flv)(\?|$)', url, re.I):
                return url

            resp = self.fetch(url, headers=headers)
            if not resp:
                return None
            html = resp.text

            # 1. player_aaaa 变量（兼容 `};` 与 `}</script>` 两种结尾）
            match = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*;?\s*</script>', html, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    link = data.get('link', '')
                    if link:
                        next_url = self._fix_url(link)
                        if next_url != url:
                            return _extract(next_url, depth + 1)
                    url_val = data.get('url', '')
                    if url_val:
                        if re.search(r'\.(m3u8|mp4|flv)', url_val, re.I):
                            return url_val
                        next_url = self._fix_url(url_val)
                        if next_url != url:
                            return _extract(next_url, depth + 1)
                except Exception as e:
                    print(f"[楓林網] 解析 player_aaaa 失败: {e}")

            # 2. iframe
            iframe = re.search(r'<iframe[^>]+src="([^"]+)"', html)
            if iframe:
                iframe_url = self._fix_url(iframe.group(1))
                if iframe_url != url:
                    return _extract(iframe_url, depth + 1)

            # 3. video 标签
            video_src = re.search(r'<video[^>]+src="([^"]+)"', html)
            if video_src:
                return video_src.group(1)

            # 4. source 标签
            source_src = re.search(r'<source[^>]+src="([^"]+)"', html)
            if source_src:
                return source_src.group(1)

            # 5. 直接匹配 m3u8
            m3u8 = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', html)
            if m3u8:
                return m3u8.group(1)

            # 6. 其它常见播放变量
            for pat in [
                r'var\s+playurl\s*=\s*["\']([^"\']+)["\']',
                r'var\s+url\s*=\s*["\']([^"\']+)["\']',
                r'var\s+video\s*=\s*["\']([^"\']+)["\']',
                r'var\s+src\s*=\s*["\']([^"\']+)["\']',
            ]:
                m = re.search(pat, html, re.I)
                if m and re.search(r'\.(m3u8|mp4|flv)', m.group(1), re.I):
                    return m.group(1)

            # 7. 页面里的 /vodplay/{id} 链接再递归（仅匹配路径，排除 ?query 误判）
            for nl in re.findall(r'<a[^>]+href="([^"]*\/vodplay\/\d+[^"]*)"', html):
                next_url = self._fix_url(nl)
                if next_url != url:
                    r = _extract(next_url, depth + 1)
                    if r:
                        return r

            return None

        final_url = _extract(play_url, 0)
        if final_url:
            final_url = self._fix_url(final_url)
            if re.search(r'\.(m3u8|mp4|flv)', final_url, re.I):
                return {"parse": 0, "url": final_url, "header": headers}
            return self.playerContent(flag, final_url, vipFlags)

        # 兜底: 交给客户端解析
        return {"parse": 1, "url": play_url, "header": headers}
