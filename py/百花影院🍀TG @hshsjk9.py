# -*- coding: utf-8 -*-
# 百花影院 www.balidwipa.com — OK影视 / TvBox Python 源
# 基于 PyramidStore (CatVod) Spider 接口
# 站点类型：苹果CMS (MacCMS)
# v3: 性能优化 - 预编译正则 / 跳过被劫持首页 / 收紧搜索窗口 / 单次合并正则

import sys
sys.path.append('..')
from base.spider import Spider
import json
import re
from urllib.parse import quote, unquote


class Spider(Spider):

    HOST = "https://www.balidwipa.com"

    CATE = {
        "电影": "1",
        "电视剧": "2",
        "综艺": "3",
        "动漫": "4",
    }

    YEAR_FILTERS = [
        {"n": "全部", "v": ""},
        {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"},
        {"n": "2024", "v": "2024"}, {"n": "2023", "v": "2023"},
        {"n": "2022", "v": "2022"}, {"n": "2021", "v": "2021"},
        {"n": "2020", "v": "2020"}, {"n": "2019", "v": "2019"},
        {"n": "2018", "v": "2018"}, {"n": "2017", "v": "2017"},
        {"n": "2016", "v": "2016"}, {"n": "2015", "v": "2015"},
        {"n": "更早", "v": "more"},
    ]

    UA = "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36"

    # ── 预编译正则（类常量，避免每次调用重新编译） ──
    RE_LIST_TITLE = re.compile(r'href="/yiy/(\d+)\.html"[^>]*>(.*?)</a>', re.S)
    RE_IMG_SRC = re.compile(r'<img[^>]*(?:data-src|data-original|src)="(https?://[^"]*)"')
    RE_PLAY_TAB = re.compile(r'href="[^"]*#playlist(\d+)"[^>]*>\s*([^<]*)\s*</a>', re.S)
    RE_PLAY_EP = re.compile(r'href="/play/(\d+)-(\d+)-(\d+)\.html"[^>]*>\s*([^<]*)\s*</a>', re.S)
    RE_OG_IMAGE = re.compile(r'<meta[^>]*og:image[^>]*content="([^"]+)"', re.I)
    RE_OG_IMAGE2 = re.compile(r'<meta[^>]*content="([^"]+)"[^>]*og:image', re.I)
    RE_DOUBAO_IMG = re.compile(r'(?:src|data-src|data-original)="(https?://[^"]*doubaocdn[^"]*)"')
    RE_MEDIA_M3U8 = re.compile(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', re.I)
    RE_MEDIA_MP4 = re.compile(r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*)', re.I)
    RE_PLAYER_AAAA = re.compile(r'player_aaaa\s*=\s*(\{.*?\})\s*[;<]', re.S)
    RE_PLAYER_DATA = re.compile(r'player_data\s*=\s*(\{.*?\})\s*[;<]', re.S)
    RE_H1 = re.compile(r'<h1[^>]*>(.*?)</h1>', re.S)
    RE_TITLE_TAG = re.compile(r'<title>([^<]*)</title>')
    RE_BH_TYPE = re.compile(r'href="/bh/\d+\.html"[^>]*>([^<]+)</a>')
    RE_YEAR = re.compile(r'year=(\d+)')
    RE_AREA = re.compile(r'area=([^&"]+)')
    RE_SCORE = re.compile(r'(\d+\.?\d*)\s*分')
    REM_TAG = re.compile(r'<[^>]+>')
    RE_A_LINK = re.compile(r'>([^<]+)</a>')

    def getName(self):
        return "百花影院"

    def init(self, extend=""):
        pass

    # ════════════ 首页 ════════════

    def homeContent(self, filter):
        result = {}
        classes = [{'type_name': n, 'type_id': self.CATE[n]} for n in self.CATE]
        result['class'] = classes
        if filter:
            filters = {}
            for name, cid in self.CATE.items():
                filters[cid] = [{"key": "year", "name": "年份", "value": self.YEAR_FILTERS}]
            result['filters'] = filters
        return result

    def homeVideoContent(self):
        # 首页已被劫持为赌博站，直接请求分类页（省 1 次 HTTP 请求）
        result = {'list': []}
        try:
            html = self._fetch_html(self.HOST + "/bh/1.html")
            videos = self._parse_list_html(html)
            result = {'list': videos[:30]}
        except:
            pass
        return result

    # ════════════ 分类列表 ════════════

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        result = {'list': [], 'page': page, 'pagecount': 1, 'limit': 30, 'total': 0}
        try:
            year = extend.get('year', '') if extend else ''
            if year and year != '全部' and year != '':
                url = "{0}/search.php?searchtype=5&tid={1}&year={2}&order=time&page={3}".format(
                    self.HOST, tid, year, page)
            elif page <= 1:
                url = "{0}/bh/{1}.html".format(self.HOST, tid)
            else:
                url = "{0}/bh/{1}-{2}.html".format(self.HOST, tid, page)

            html = self._fetch_html(url)
            result['list'] = self._parse_list_html(html)
            pagecount = self._parse_pagecount(html)
            result['pagecount'] = pagecount if pagecount else 9999
            result['total'] = 999999
        except:
            pass
        return result

    # ════════════ 详情 ════════════

    def detailContent(self, array):
        try:
            return self._detail_inner(array)
        except Exception as e:
            vod_id = str(array[0]) if array else ""
            vod = {
                "vod_id": vod_id, "vod_name": "解析异常", "vod_pic": "",
                "type_name": "", "vod_year": "", "vod_area": "", "vod_remarks": "",
                "vod_actor": "", "vod_director": "", "vod_content": str(e)[:200],
                "vod_play_from": "默认线路",
                "vod_play_url": "播放$" + vod_id + "___0___0"
            }
            return {'list': [vod]}

    def _detail_inner(self, array):
        vod_id = str(array[0])
        html = self._fetch_html("{0}/yiy/{1}.html".format(self.HOST, vod_id))
        if not html or len(html) < 200:
            raise Exception("详情页获取失败")

        # 标题
        title = self.RE_H1.search(html)
        title = self.REM_TAG.sub('', title.group(1)).strip() if title else ""
        if not title:
            m = self.RE_TITLE_TAG.search(html)
            title = m.group(1).strip() if m else ""

        # 分类名 / 年份 / 地区 / 评分
        type_name = self._m(self.RE_BH_TYPE, html)
        year = self._m(self.RE_YEAR, html)
        m = self.RE_AREA.search(html)
        area = unquote(m.group(1)) if m else ""
        m = self.RE_SCORE.search(html)
        score = m.group(1) if m else ""

        # 导演 / 主演
        director = self._extract_links_by_keyword(html, '导演')
        actor = self._extract_links_by_keyword(html, '主演')

        # 简介
        content = ""
        m = re.search(r'(?:剧情|简介)[：:]\s*(.*?)(?:</p>|</div>|<br|###|<h)', html, re.S)
        if m:
            content = self.REM_TAG.sub('', m.group(1)).replace('&nbsp;', ' ').strip()
            if len(content) > 500:
                content = content[:500] + '...'

        # 封面图（优先 og:image，其次 doubaocdn，快速短路）
        pic = self._extract_detail_pic(html)

        # 备注
        remarks = ""
        m = re.search(r'更新[：:]\s*([0-9\-: ]+)', html)
        if m:
            remarks = m.group(1).strip()

        vod = {
            "vod_id": vod_id, "vod_name": title, "vod_pic": pic,
            "type_name": type_name, "vod_year": year, "vod_area": area,
            "vod_remarks": remarks, "vod_actor": actor, "vod_director": director,
            "vod_content": content, "vod_score": score,
        }
        vod["vod_play_from"], vod["vod_play_url"] = self._parse_play_list(html, vod_id)
        return {'list': [vod]}

    # ════════════ 搜索 ════════════

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        result = {'list': []}
        try:
            if page <= 1:
                url = "{0}/search.php?searchword={1}".format(self.HOST, quote(key))
            else:
                url = "{0}/search.php?searchword={1}&page={2}".format(self.HOST, quote(key), page)
            html = self._fetch_html(url)
            result = {'list': self._parse_list_html(html)}
        except:
            pass
        return result

    # ════════════ 播放解析 ════════════

    def playerContent(self, flag, id, vipFlags):
        result = {"parse": 1, "url": "", "header": ""}
        try:
            parts = id.split("___")
            if len(parts) < 3:
                return {"parse": 0, "url": id, "header": ""}
            vod_id, sid, nid = parts[0], parts[1], parts[2]

            play_url = "{0}/play/{1}-{2}-{3}.html".format(self.HOST, vod_id, sid, nid)
            html = self._fetch_html(play_url)

            # 1. MacCMS player_aaaa
            player_json = self._extract_player_data(html)
            if player_json and player_json.get('url', ''):
                real_url = player_json['url']
                encrypt = player_json.get('encrypt', 0)
                if encrypt == 1:
                    real_url = unquote(real_url)
                elif encrypt == 2:
                    real_url = self._aes_decrypt(real_url, html)
                result = {"parse": 0, "playUrl": "", "url": real_url,
                          "header": json.dumps(self._play_header())}
            else:
                # 2. 直接提取媒体 URL
                media_url = self._extract_media_url(html)
                if media_url:
                    result = {"parse": 0, "url": media_url,
                              "header": json.dumps(self._play_header())}
                else:
                    # 3. 嗅探播放页
                    result = {"parse": 1, "url": play_url, "header": ""}
        except:
            pass
        return result

    # ════════════ 辅助：网络 ════════════

    def _headers(self):
        return {
            "User-Agent": self.UA,
            "Referer": self.HOST + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

    def _play_header(self):
        return {"User-Agent": self.UA, "Referer": self.HOST + "/"}

    def _fetch_html(self, url):
        rsp = self.fetch(url, headers=self._headers(), timeout=10)
        try:
            rsp.encoding = rsp.apparent_encoding or 'utf-8'
        except:
            pass
        return rsp.text

    # ════════════ 辅助：列表解析（性能关键路径） ════════════

    def _parse_list_html(self, html):
        """
        解析列表页。图片和标题是兄弟标签，图片紧邻标题前。
        用单次 finditer 遍历标题链接，向前 400 字符找最近 img。
        """
        videos = []
        seen = set()

        for m in self.RE_LIST_TITLE.finditer(html):
            vid = m.group(1)
            if vid in seen:
                continue
            name = self.REM_TAG.sub('', m.group(2)).strip()
            if not name:
                continue
            seen.add(vid)

            # 向前 400 字符找最近的 img（图片通常紧邻标题前）
            backward = html[max(0, m.start() - 400):m.start()]
            imgs = self.RE_IMG_SRC.findall(backward)
            pic = imgs[-1] if imgs else ""

            videos.append({
                "vod_id": str(vid), "vod_name": name,
                "vod_pic": pic, "vod_remarks": ""
            })

        return videos

    def _parse_pagecount(self, html):
        pages = re.findall(r'/bh/\d+-(\d+)\.html', html)
        if pages:
            nums = [int(p) for p in pages if int(p) > 0]
            if nums:
                return max(nums)
        pages2 = re.findall(r'page=(\d+)', html)
        if pages2:
            nums = [int(p) for p in pages2 if int(p) > 0]
            if nums:
                return max(nums)
        return 0

    # ════════════ 辅助：详情页解析 ════════════

    def _extract_detail_pic(self, html):
        """快速短路：og:image → doubaocdn → 任意非图标 img"""
        m = self.RE_OG_IMAGE.search(html) or self.RE_OG_IMAGE2.search(html)
        if m:
            return m.group(1)
        m = self.RE_DOUBAO_IMG.search(html)
        if m:
            return m.group(1)
        m = re.search(r'url\((https?://[^)]*doubaocdn[^)]*)\)', html)
        if m:
            return m.group(1)
        for m in re.finditer(r'<img[^>]*src="(https?://[^"]*)"', html):
            src = m.group(1)
            if not re.search(r'(icon|logo|favicon|avatar|loading|placeholder|blank)', src, re.I):
                return src
        return ""

    def _parse_play_list(self, html, vod_id):
        """解析播放线路和剧集（该站通常只有 1 条线路，但代码兼容多线路）"""
        tab_matches = self.RE_PLAY_TAB.findall(html)
        ep_matches = self.RE_PLAY_EP.findall(html)

        if tab_matches and ep_matches:
            play_from_list = []
            play_url_list = []
            for tab_id, tab_name in tab_matches:
                tab_name = tab_name.strip() or ("线路" + str(tab_id))
                sid_expected = int(tab_id) - 1
                if sid_expected < 0:
                    sid_expected = int(tab_id)
                items = []
                for vodid, sid, nid, ep_name in ep_matches:
                    if int(sid) == sid_expected:
                        ep_name = ep_name.strip()
                        if not ep_name:
                            ep_name = "第" + str(int(nid) + 1).zfill(2) + "集"
                        items.append("{0}${1}___{2}___{3}".format(ep_name, vodid, sid, nid))
                if items:
                    play_from_list.append(tab_name)
                    play_url_list.append("#".join(items))
            if play_from_list:
                return "$$$".join(play_from_list), "$$$".join(play_url_list)

        if ep_matches:
            items = []
            for vodid, sid, nid, ep_name in ep_matches:
                ep_name = ep_name.strip()
                if not ep_name:
                    ep_name = "第" + str(int(nid) + 1).zfill(2) + "集"
                items.append("{0}${1}___{2}___{3}".format(ep_name, vodid, sid, nid))
            if items:
                return "默认线路", "#".join(items)

        return "默认线路", "播放$" + vod_id + "___0___0"

    def _extract_links_by_keyword(self, html, keyword):
        """位置法提取导演/主演，收紧块大小到 1500 字符"""
        idx = html.find(keyword)
        if idx == -1:
            idx = html.find(keyword.replace('：', ':'))
        if idx == -1:
            return ""

        chunk = html[idx: idx + 1500]
        stop_words = ['主演', '导演', '上映', '更新', '状态', '语言',
                      '编剧', '类型', '地区', '年份', '频道', '剧情',
                      '简介', '播放', '专辑', '豆瓣']
        stop_words = [w for w in stop_words if w != keyword]

        kw_len = len(keyword)
        min_pos = len(chunk)
        for sw in stop_words:
            pos = chunk.find(sw, kw_len)
            if pos != -1 and pos < min_pos:
                min_pos = pos

        block = chunk[:min_pos]
        names = self.RE_A_LINK.findall(block)
        return ' '.join(n.strip() for n in names if n.strip() and n.strip() != '/')

    # ════════════ 辅助：播放器 ════════════

    def _extract_player_data(self, html):
        for pat in (self.RE_PLAYER_AAAA, self.RE_PLAYER_DATA):
            m = pat.search(html)
            if m:
                try:
                    return json.loads(m.group(1))
                except:
                    pass
        m = re.search(r'(player_\w+)\s*=\s*(\{[^}]+\})', html, re.S)
        if m:
            try:
                return json.loads(m.group(2))
            except:
                pass
        return {}

    def _extract_media_url(self, html):
        m = self.RE_MEDIA_M3U8.search(html) or self.RE_MEDIA_MP4.search(html)
        if not m:
            m = re.search(r'(https?://[^\s"\'<>]+\.flv[^\s"\'<>]*)', html, re.I)
        return m.group(1) if m else ""

    def _aes_decrypt(self, encrypted, html):
        try:
            key_match = re.search(r'key\s*[:=]\s*["\']([A-Za-z0-9]{16})["\']', html)
            key = key_match.group(1) if key_match else "28fd7d0f7dac4156"
            from Crypto.Cipher import AES
            import base64
            cipher = AES.new(key.encode(), AES.MODE_ECB)
            decrypted = cipher.decrypt(base64.b64decode(encrypted))
            pad = decrypted[-1]
            return decrypted[:-pad].decode('utf-8', errors='ignore')
        except:
            return encrypted

    # ════════════ 通用 ════════════

    def _m(self, regex, text):
        """正则取 group(1)，预编译版"""
        m = regex.search(text)
        return m.group(1) if m else ""

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def localProxy(self, param):
        return [200, "video/MP2T", "", ""]
