# coding=utf-8
# !/python
import sys
import json
import re
import requests
import base64
from urllib.parse import unquote, quote, urljoin, urlparse
from base.spider import Spider

sys.path.append("..")

# ---------- 站点配置 ----------
xurl = "https://bkpk82.baokuanpk.cc"
api_url = xurl + "/api.php/provide/vod/"

headerx = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Connection': 'keep-alive'
}

# ---------- 广告关键词（用于 m3u8 清洗） ----------
AD_KEYWORDS = [
    "新葡京", "澳门新葡京", "新葡京娱乐城", "新葡京娱乐场",
    "澳门赌场", "澳门威尼斯人", "永利皇宫", "美高梅", "金沙娱乐场",
    "金沙赌场", "葡京娱乐场", "葡京赌场", "新濠天地", "新濠影汇",
    "银河娱乐", "星际娱乐", "英皇娱乐", "永利澳门", "美高梅中国",
    "老虎机", "pg电子", "cq9", "cq9电子", "跳高高", "麻将胡了",
    "赏金女王", "寻宝黄金城", "水果机", "糖果派对",
    "棋牌", "开元棋牌", "真人视讯", "百家乐", "体育下注",
    "外围投注", "足彩", "滚球", "六合彩", "时时彩",
    "赌场", "casino", "娱乐城", "博彩", "彩票", "投注",
    "充值送", "首存", "返水", "vip通道", "快速提现",
    "注册即送", "高赔率", "资金安全", "百万提款",
    "澳门威尼斯", "澳门金沙", "澳门银河", "永利娱乐",
]

# ---------- 热门搜索标签 ----------
HOT_TAGS = [
    "网袜", "导师", "纤细", "美腿", "清纯", "小姐", "菊花", "爆菊",
    "求饶", "短裙", "浴场", "迷晕", "嫖妓", "旅馆", "正妹", "紧身",
    "白皙", "老婆", "中出", "女模", "按摩", "阴道", "淫荡", "手机",
    "开档", "拍摄", "海滩", "沙滩", "奴隶", "惩罚", "精液", "午睡",
    "嫂子", "上位", "秘书", "上班", "强迫", "男友", "甜蜜", "温柔",
    "暴力", "撕烂", "日逼", "女星", "卖淫", "夜班", "尾随", "色狼",
    "痴汉", "偶遇", "巨乳", "调教", "萝莉", "自慰", "妈妈", "母子",
    "黑人", "强奸", "熟女", "偷拍", "人妖", "迷奸", "足交", "伪娘",
    "女儿", "幼女", "黑丝", "内射", "破处", "丝袜", "抖音", "国产",
    "绳子", "美臀", "哥哥", "禽兽", "灌倒", "做客", "狗链", "主妇",
    "美鲍", "偷约", "技师", "美人", "处女", "清秀", "新娘", "跳蛋",
    "诱奸", "学生", "日本", "空姐", "丝足",
]

class Spider(Spider):
    def getName(self):
        return "爆款片库"

    def init(self, extend):
        self.host = xurl
        self.session = requests.Session()
        self.session.headers.update(headerx)
        self.use_api = False
        self._check_api_available()

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    # ========== 检测API是否可用 ==========
    def _check_api_available(self):
        try:
            test_url = api_url + "?ac=list&t=1&pg=1"
            res = requests.get(test_url, headers=headerx, timeout=5)
            if res.status_code == 200:
                data = res.json()
                if data.get('code') == 1 and data.get('list'):
                    self.use_api = True
                    print(f"[_check_api] API可用，切换到API模式")
                    return
        except Exception as e:
            print(f"[_check_api] API检测失败: {e}")
        print(f"[_check_api] API不可用，使用HTML解析模式")

    # ========== 首页视频 ==========
    def homeVideoContent(self):
        if self.use_api:
            return self._api_home_video()
        return self._html_home_video()

    def _api_home_video(self):
        videos = []
        try:
            res = requests.get(api_url + "?ac=list&pg=1", headers=headerx, timeout=10)
            data = res.json()
            if data.get('code') == 1:
                for item in data.get('list', [])[:30]:
                    videos.append({
                        "vod_id": str(item.get('vod_id', '')),
                        "vod_name": item.get('vod_name', ''),
                        "vod_pic": item.get('vod_pic', ''),
                        "vod_remarks": item.get('vod_remarks', '')
                    })
            print(f"[_api_home] API获取 {len(videos)} 条视频")
        except Exception as e:
            print(f"[_api_home] API错误: {e}")
        return {'list': videos}

    def _html_home_video(self):
        videos = []
        try:
            res = requests.get(xurl + '/bb/', headers=headerx, timeout=10)
            res.encoding = "utf-8"
            html = res.text
            if len(html) < 500:
                return {'list': []}
            videos = self._extract_videos_from_html(html)
            print(f"[_html_home] HTML获取 {len(videos)} 条视频")
        except Exception as e:
            print(f"[_html_home] HTML错误: {e}")
        return {'list': videos[:30]}

    # ========== 通用视频卡片提取器 ==========
    def _extract_videos_from_html(self, html):
        videos = []
        if not html or len(html) < 500:
            return videos

        # 精确匹配
        pattern = re.compile(
            r'<div[^>]*class=["\'][^"\']*vod[^"\']*["\'][^>]*>.*?'
            r'<div[^>]*class=["\'][^"\']*vod-img[^"\']*["\'][^>]*>.*?'
            r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>.*?'
            r'<img[^>]*data-original=["\']([^"\']+)["\'][^>]*>.*?'
            r'</a>.*?'
            r'<div[^>]*class=["\'][^"\']*vod-txt[^"\']*["\'][^>]*>.*?'
            r'<a[^>]*>(.*?)</a>.*?'
            r'</div>.*?</div>',
            re.S | re.I
        )

        matches = pattern.findall(html)
        print(f"[_extract] 精确模式匹配到 {len(matches)} 条")

        for href, img, title in matches:
            title = re.sub(r'<[^>]+>', '', title).strip()
            if not title or len(title) < 2:
                continue
            if img.startswith('//'):
                img = 'http:' + img
            elif not img.startswith('http'):
                img = urljoin(xurl, img)

            if not any(v['vod_id'] == href for v in videos):
                videos.append({
                    "vod_id": href,
                    "vod_name": title,
                    "vod_pic": img,
                    "vod_remarks": ""
                })

        # 备用规则
        if not videos:
            links = re.finditer(r'<a[^>]*href=["\']([^"\']*(?:/detail/id/)[^"\']*)["\'][^>]*>(.*?)</a>', html, re.S|re.I)
            for link in links:
                href = link.group(1)
                inner = link.group(2)
                start = max(link.start()-1000, 0)
                end = min(link.end()+1000, len(html))
                context = html[start:end]
                img_match = re.search(r'data-original=["\']([^"\']+)["\']', context, re.I)
                img = img_match.group(1) if img_match else ''
                title = re.sub(r'<[^>]+>', '', inner).strip()
                if not title:
                    continue
                if img.startswith('//'):
                    img = 'http:' + img
                elif img and not img.startswith('http'):
                    img = urljoin(xurl, img)
                if not any(v['vod_id'] == href for v in videos):
                    videos.append({
                        "vod_id": href,
                        "vod_name": title,
                        "vod_pic": img,
                        "vod_remarks": ""
                    })
            print(f"[_extract] 备用规则匹配到 {len(videos)} 条")

        print(f"[_extract] 最终提取 {len(videos)} 条视频")
        return videos

    # ========== 分类列表（已删除指定分类） ==========
    def homeContent(self, filter):
        result = {'class': [], 'filters': {}}

        class_list = [
            {'type_id': '/bb/index.php/vod/type/id/29.html', 'type_name': '国产自拍'},
            {'type_id': '/bb/index.php/vod/type/id/30.html', 'type_name': '国产偷拍'},
            {'type_id': '/bb/index.php/vod/type/id/33.html', 'type_name': '短视频'},
            {'type_id': '/bb/index.php/vod/type/id/35.html', 'type_name': '国产主播'},
            {'type_id': '/bb/index.php/vod/type/id/80.html', 'type_name': '国产女王'},
            {'type_id': '/bb/index.php/vod/type/id/81.html', 'type_name': '国产女奴'},
            {'type_id': '/bb/index.php/vod/type/id/83.html', 'type_name': '福利姬'},
            {'type_id': '/bb/index.php/vod/type/id/84.html', 'type_name': '抖阴视频'},
            {'type_id': '/bb/index.php/vod/type/id/85.html', 'type_name': '国模私拍'},
            {'type_id': '/bb/index.php/vod/type/id/88.html', 'type_name': '国产乱伦'},
            {'type_id': '/bb/index.php/vod/type/id/91.html', 'type_name': '网曝系列'},
            {'type_id': '/bb/index.php/vod/type/id/107.html', 'type_name': '台湾辣妹'},
            {'type_id': '/bb/index.php/vod/type/id/108.html', 'type_name': '唯美港姐'},
            {'type_id': '/bb/index.php/vod/type/id/109.html', 'type_name': '国产探花'},
            {'type_id': '/bb/index.php/vod/type/id/110.html', 'type_name': '野外露出'},
            {'type_id': '/bb/index.php/vod/type/id/26.html', 'type_name': '国产精品'},
            {'type_id': '/bb/index.php/vod/type/id/27.html', 'type_name': '国产传媒'},
            {'type_id': '/bb/index.php/vod/type/id/101.html', 'type_name': '有码精品'},
            {'type_id': '/bb/index.php/vod/type/id/116.html', 'type_name': '欺辱凌辱'},
            {'type_id': '/bb/index.php/vod/type/id/117.html', 'type_name': 'AV解说'},
            {'type_id': '/bb/index.php/vod/type/id/118.html', 'type_name': '有码VR'},
            {'type_id': '/bb/index.php/vod/type/id/48.html', 'type_name': '美乳巨乳'},
            {'type_id': '/bb/index.php/vod/type/id/59.html', 'type_name': '丝袜美腿'},
            {'type_id': '/bb/index.php/vod/type/id/46.html', 'type_name': '口爆颜射'},
            {'type_id': '/bb/index.php/vod/type/id/50.html', 'type_name': '强奸乱伦'},
            {'type_id': '/bb/index.php/vod/type/id/93.html', 'type_name': '多人运动'},
            {'type_id': '/bb/index.php/vod/type/id/52.html', 'type_name': '制服诱惑'},
            {'type_id': '/bb/index.php/vod/type/id/43.html', 'type_name': '女仆'},
            {'type_id': '/bb/index.php/vod/type/id/31.html', 'type_name': '人妻熟女'},
            {'type_id': '/bb/index.php/vod/type/id/58.html', 'type_name': 'cosplay'},
            {'type_id': '/bb/index.php/vod/type/id/34.html', 'type_name': '潮吹喷射'},
            {'type_id': '/bb/index.php/vod/type/id/47.html', 'type_name': '萝莉少女'},
            {'type_id': '/bb/index.php/vod/type/id/44.html', 'type_name': '素人'},
            {'type_id': '/bb/index.php/vod/type/id/53.html', 'type_name': '女同性恋'},
            {'type_id': '/bb/index.php/vod/type/id/32.html', 'type_name': 'SM重口味'},
            {'type_id': '/bb/index.php/vod/type/id/45.html', 'type_name': '熟女'},
            {'type_id': '/bb/index.php/vod/type/id/55.html', 'type_name': '教师'},
            {'type_id': '/bb/index.php/vod/type/id/62.html', 'type_name': '无码VR'},
            {'type_id': '/bb/index.php/vod/type/id/76.html', 'type_name': '制服无码'},
            {'type_id': '/bb/index.php/vod/type/id/86.html', 'type_name': '女优明星'},
            {'type_id': '/bb/index.php/vod/type/id/102.html', 'type_name': '无码精品'},
            {'type_id': '/bb/index.php/vod/type/id/51.html', 'type_name': '日本中字'},
            {'type_id': '/bb/index.php/vod/type/id/104.html', 'type_name': '欧美精品'},
            {'type_id': '/bb/index.php/vod/type/id/103.html', 'type_name': '动漫精品'},
            {'type_id': '/bb/index.php/vod/type/id/39.html', 'type_name': '综合三级'},
            {'type_id': '/bb/index.php/vod/type/id/82.html', 'type_name': '韩国精品'},
            {'type_id': '/bb/index.php/vod/type/id/42.html', 'type_name': '恐怖色情'},
            {'type_id': '/bb/index.php/vod/type/id/54.html', 'type_name': '人兽性交'},
            {'type_id': '/bb/index.php/vod/type/id/61.html', 'type_name': 'AI换脸'},
        ]
        result['class'] = class_list

        if filter and HOT_TAGS:
            result['filters'] = {
                "tags": [{"n": t, "v": t} for t in HOT_TAGS[:50]]
            }

        print(f"[homeContent] 返回 {len(result['class'])} 个分类")
        return result

    # ========== 分类列表 ==========
    def categoryContent(self, cid, pg, filter, ext):
        if self.use_api:
            return self._api_category_content(cid, pg, filter, ext)
        return self._html_category_content(cid, pg, filter, ext)

    def _api_category_content(self, cid, pg, filter, ext):
        result = {}
        videos = []
        try:
            pg = int(pg) if pg else 1
            tid = cid
            m = re.search(r'id/(\d+)', cid)
            if m:
                tid = m.group(1)
            url = api_url + f"?ac=list&t={tid}&pg={pg}"
            res = requests.get(url, headers=headerx, timeout=10)
            data = res.json()
            if data.get('code') == 1:
                for item in data.get('list', []):
                    videos.append({
                        "vod_id": str(item.get('vod_id', '')),
                        "vod_name": item.get('vod_name', ''),
                        "vod_pic": item.get('vod_pic', ''),
                        "vod_remarks": item.get('vod_remarks', '')
                    })
                result['page'] = data.get('page', pg)
                result['pagecount'] = data.get('pagecount', 9999)
                result['limit'] = data.get('limit', 20)
                result['total'] = data.get('total', 999999)
            print(f"[_api_category] 获取 {len(videos)} 条, 页码:{pg}")
        except Exception as e:
            print(f"[_api_category] 错误: {e}")
            result['page'] = pg
            result['pagecount'] = 9999
            result['limit'] = 20
            result['total'] = 999999
        result['list'] = videos
        return result

    def _html_category_content(self, cid, pg, filter, ext):
        result = {}
        videos = []
        if cid and cid.isdigit():
            cid = f'/bb/index.php/vod/type/id/{cid}.html'
        url = self._build_page_url(cid, pg)
        print(f"[_html_category] 请求: {url}")
        try:
            res = requests.get(url=url, headers=headerx, timeout=10)
            res.encoding = "utf-8"
            html = res.text
            if len(html) >= 500:
                videos = self._extract_videos_from_html(html)
            print(f"[_html_category] 提取 {len(videos)} 条视频")
        except Exception as e:
            print(f"[_html_category] 错误: {e}")
        result['list'] = videos
        result['page'] = pg
        result['pagecount'] = 9999
        result['limit'] = 90
        result['total'] = 999999
        return result

    def _build_page_url(self, cid, pg):
        if not cid:
            return xurl + '/bb/'
        if cid.startswith('http'):
            base = cid
        else:
            if not cid.startswith('/'):
                cid = '/' + cid
            base = xurl + cid
        if pg == "" or int(pg) <= 1:
            return base
        pg = int(pg)
        if base.endswith('.html'):
            return base[:-5] + '-' + str(pg) + '.html'
        sep = '&' if '?' in base else '?'
        return base + sep + 'page=' + str(pg)

    # ========== 视频详情（全集提取） ==========
    def detailContent(self, ids):
        did = ids[0]
        if self.use_api and did.isdigit():
            return self._api_detail_content(did)
        return self._html_detail_content(did)

    def _api_detail_content(self, did):
        videos = []
        result = {}
        try:
            url = api_url + f"?ac=detail&ids={did}"
            res = requests.get(url, headers=headerx, timeout=10)
            data = res.json()
            if data.get('code') == 1 and data.get('list'):
                item = data['list'][0]
                play_url = item.get('vod_play_url', '')
                videos.append({
                    "vod_id": str(item.get('vod_id', '')),
                    "vod_name": item.get('vod_name', ''),
                    "vod_pic": item.get('vod_pic', ''),
                    "type_name": item.get('type_name', ''),
                    "vod_year": str(item.get('vod_year', '')),
                    "vod_area": item.get('vod_area', ''),
                    "vod_remarks": item.get('vod_remarks', ''),
                    "vod_actor": item.get('vod_actor', ''),
                    "vod_director": item.get('vod_director', ''),
                    "vod_content": item.get('vod_content', ''),
                    'vod_play_from': item.get('vod_play_from', '直链播放'),
                    "vod_play_url": play_url
                })
        except Exception as e:
            print(f"[_api_detail] 错误: {e}")
        result['list'] = videos
        return result

    def _html_detail_content(self, did):
        videos = []
        result = {}
        try:
            if did.isdigit():
                did = f'/bb/index.php/vod/detail/id/{did}.html'
            elif not did.startswith('/'):
                did = '/' + did
            detail_url = xurl + did if not did.startswith('http') else did
            print(f"[_html_detail] 请求详情页: {detail_url}")

            res = requests.get(url=detail_url, headers=headerx, timeout=10)
            res.encoding = "utf-8"
            html = res.text
            if len(html) < 500:
                return result

            title = ""
            title_match = re.search(r'<h3[^>]*class=["\'][^"\']*title[^"\']*["\'][^>]*>(.*?)</h3>', html, re.S | re.I)
            if title_match:
                title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
            if not title:
                title_match = re.search(r'<title>(.*?)</title>', html, re.I)
                if title_match:
                    title = title_match.group(1).split('-')[0].strip()

            pic = ""
            pic_match = re.search(r'<img[^>]*class=["\'][^"\']*lazy[^"\']*["\'][^>]*data-original=["\']([^"\']+)["\']', html, re.I)
            if pic_match:
                pic = pic_match.group(1)
            if not pic:
                pic_match = re.search(r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']', html, re.I)
                if pic_match:
                    pic = pic_match.group(1)
            if pic:
                if pic.startswith('//'):
                    pic = 'http:' + pic
                elif not pic.startswith('http'):
                    pic = urljoin(detail_url, pic)

            vod_play_url = ""
            play_from = "naixx"

            # 全集提取
            playlist_html = ""
            match_playlist = re.search(r'<ul[^>]*class=["\'][^"\']*(?:playlist|play.list|play.url)[^"\']*["\'][^>]*>(.*?)</ul>', html, re.S | re.I)
            if match_playlist:
                playlist_html = match_playlist.group(1)

            episodes = []
            if playlist_html:
                items = re.findall(r'<a[^>]*href=["\']([^"\']*vod/play/[^"\']*)["\'][^>]*>(.*?)</a>', playlist_html, re.S|re.I)
                for href, name in items:
                    name = re.sub(r'<[^>]+>', '', name).strip()
                    if not name:
                        name = "正片"
                    episodes.append((name, href))
            else:
                all_plays = re.findall(r'href=["\']([^"\']*/vod/play/id/\d+/sid/\d+/nid/\d+\.html)["\'][^>]*>(.*?)</a>', html, re.S|re.I)
                seen = set()
                for href, name in all_plays:
                    if href in seen:
                        continue
                    seen.add(href)
                    name = re.sub(r'<[^>]+>', '', name).strip()
                    if not name:
                        name = "第{}集".format(len(episodes)+1)
                    episodes.append((name, href))

            if not episodes:
                id_match = re.search(r'id/(\d+)', did)
                if id_match:
                    vid = id_match.group(1)
                    default_path = f"/bb/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
                    episodes.append(("正片", default_path))

            if episodes:
                vod_play_url = "#".join([f"{name}${path}" for name, path in episodes])
                print(f"[_html_detail] 提取到 {len(episodes)} 集")
            else:
                play_match = re.search(r'href=["\']([^"\']*/vod/play/[^"\']*)["\'][^>]*>立即播放', html, re.I)
                if play_match:
                    vod_play_url = "正片$" + play_match.group(1)

            print(f"[_html_detail] 标题:{title}, 图片:{pic[:40] if pic else '无'}, 集数:{len(episodes) if episodes else 0}")

            videos.append({
                "vod_id": did,
                "vod_name": title,
                "vod_pic": pic,
                "type_name": "",
                "vod_year": "",
                "vod_area": "",
                "vod_remarks": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_content": "",
                'vod_play_from': play_from,
                "vod_play_url": vod_play_url
            })
        except Exception as e:
            print(f"[_html_detail] 错误: {e}")
            import traceback
            traceback.print_exc()
        result['list'] = videos
        return result

    # ================== 强化版13层视频地址解析（修复干扰链接） ==================
    def _get_m3u8_from_play_page(self, play_page_path):
        """
        强力提取播放页真实视频地址，优先解析 player_xxxx 变量，排除非播放器干扰
        """
        try:
            play_url_full = xurl + play_page_path if not play_page_path.startswith('http') else play_page_path
            print(f"[_get_m3u8] 请求播放页: {play_url_full}")

            res = requests.get(play_url_full, headers=headerx, timeout=10)
            res.encoding = "utf-8"
            html = res.text
            if len(html) < 500:
                return "", "naixx"

            # ---------- 策略1：精准提取 player_XXXX 变量（平衡大括号匹配） ----------
            player_vars = re.finditer(
                r'var\s+(player_\w+)\s*=\s*(\{.*?\});(?=\s*</script|\s*$|var\s+)',
                html, re.S
            )
            for m in player_vars:
                var_name = m.group(1)
                start = m.group(2)
                brace_count = 0
                json_str = ''
                for i, ch in enumerate(start):
                    json_str += ch
                    if ch == '{':
                        brace_count += 1
                    elif ch == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            break
                if not json_str.endswith('}'):
                    json_str += '}'
                json_str = json_str.replace('\\/', '/')
                try:
                    data = json.loads(json_str)
                    raw_url = data.get('url', '')
                    if raw_url and ('baokuanpk.cc' not in raw_url):
                        url = self._decrypt_obfuscated_url(raw_url)
                        if url.startswith('http'):
                            print(f"[策略1] 从 {var_name} 提取: {url[:60]}")
                            return url, data.get('from', 'naixx')
                except Exception as e:
                    print(f"[策略1] JSON解析失败: {e}")

            # ---------- 策略2：限定在 player_xxxx 附近提取 url（局部搜索） ----------
            player_positions = [(m.start(), m.end()) for m in re.finditer(r'var\s+player_\w+\s*=', html)]
            if player_positions:
                for start_pos, _ in player_positions:
                    search_window = html[start_pos:start_pos+3000]
                    url_match = re.search(r'"url"\s*:\s*"(https?[^"]+)"', search_window)
                    if url_match:
                        raw_url = url_match.group(1).replace('\\/', '/')
                        if 'baokuanpk.cc' not in raw_url:
                            url = self._decrypt_obfuscated_url(raw_url)
                            if url.startswith('http'):
                                from_match = re.search(r'"from"\s*:\s*"([^"]+)"', search_window)
                                from_src = from_match.group(1) if from_match else 'naixx'
                                print(f"[策略2] player附近提取: {url[:60]}")
                                return url, from_src

            # ---------- 策略3：全局 "url":"..." 但排除干扰链接 ----------
            for url_match in re.finditer(r'"url"\s*:\s*"(https?[^"]+)"', html):
                raw_url = url_match.group(1).replace('\\/', '/')
                if 'baokuanpk.cc' in raw_url:
                    continue
                url = self._decrypt_obfuscated_url(raw_url)
                if url.startswith('http') and ('.m3u8' in url or '.mp4' in url or 'vostrely' in url or 'stream' in url):
                    print(f"[策略3] 全局匹配 (过滤后): {url[:60]}")
                    from_match = re.search(r'"from"\s*:\s*"([^"]+)"', html)
                    return url, from_match.group(1) if from_match else 'naixx'

            # ---------- 策略4: video/source 标签 ----------
            for tag in ['video', 'source']:
                m = re.search(rf'<{tag}[^>]*src=["\']([^"\']+)["\']', html, re.I)
                if m:
                    url = self._decrypt_obfuscated_url(m.group(1))
                    if url.startswith('http') and 'baokuanpk.cc' not in url:
                        print(f"[策略4] {tag}标签: {url[:60]}")
                        return url, 'naixx'

            # ---------- 策略5: iframe ----------
            iframe_match = re.search(r'<iframe[^>]*src=["\']([^"\']+)["\']', html, re.I)
            if iframe_match:
                url = self._decrypt_obfuscated_url(iframe_match.group(1))
                if '.m3u8' in url or '.mp4' in url:
                    print(f"[策略5] iframe直链: {url[:60]}")
                    return url, 'naixx'

            # ---------- 策略6: 所有 m3u8 链接 ----------
            m3u8_list = re.findall(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html, re.I)
            if m3u8_list:
                url = self._decrypt_obfuscated_url(m3u8_list[0])
                print(f"[策略6] m3u8兜底: {url[:60]}")
                return url, 'naixx'

            # ---------- 策略7: mp4 链接 ----------
            mp4_list = re.findall(r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*)', html, re.I)
            if mp4_list:
                url = self._decrypt_obfuscated_url(mp4_list[0])
                print(f"[策略7] mp4兜底: {url[:60]}")
                return url, 'naixx'

            # ---------- 策略8: Base64 加密 ----------
            b64_match = re.search(r'(?:atob|btoa|base64Decode)\s*\(\s*["\']([A-Za-z0-9+/=]+)["\']\s*\)', html)
            if b64_match:
                try:
                    decoded = base64.b64decode(b64_match.group(1)).decode('utf-8')
                    if decoded.startswith('http') and 'baokuanpk.cc' not in decoded:
                        print(f"[策略8] Base64解码: {decoded[:60]}")
                        return decoded, 'naixx'
                except:
                    pass

            # ---------- 策略9: 自定义解密函数 ----------
            decrypt_match = re.search(r'(?:decrypt|decodeURI)\s*\(\s*["\']([^"\']+)["\']\s*\)', html)
            if decrypt_match:
                raw = decrypt_match.group(1)
                url = self._decrypt_obfuscated_url(raw)
                if url.startswith('http') and 'baokuanpk.cc' not in url:
                    print(f"[策略9] 自定义解密: {url[:60]}")
                    return url, 'naixx'

            # ---------- 策略10: location.href ----------
            loc_match = re.search(r'window\.location\.href\s*=\s*["\']([^"\']+)["\']', html)
            if loc_match:
                loc = loc_match.group(1)
                if '.m3u8' in loc or '.mp4' in loc:
                    print(f"[策略10] location跳转: {loc[:60]}")
                    return loc, 'naixx'

            # ---------- 策略11: meta refresh ----------
            meta_match = re.search(r'<meta[^>]+http-equiv=["\']refresh["\'][^>]+content=["\']\d+;\s*url=([^"\']+)["\']', html, re.I)
            if meta_match:
                meta_url = meta_match.group(1)
                if '.m3u8' in meta_url or '.mp4' in meta_url:
                    print(f"[策略11] meta refresh: {meta_url[:60]}")
                    return meta_url, 'naixx'

            print(f"[_get_m3u8] 所有策略均未找到有效播放地址")
            return "", "naixx"
        except Exception as e:
            print(f"[_get_m3u8] 错误: {e}")
            return "", "naixx"

    # ========== 通用混淆解密 ==========
    def _decrypt_obfuscated_url(self, raw_url):
        if not raw_url:
            return raw_url
        url = raw_url.strip()
        # 1. Base64 整串解码
        if re.match(r'^[A-Za-z0-9+/=]+$', url) and len(url) % 4 == 0:
            try:
                decoded = base64.b64decode(url).decode('utf-8')
                if decoded.startswith('http'):
                    print(f"[_decrypt] Base64->{decoded[:60]}")
                    return decoded
            except:
                pass
        # 2. URL解码
        try:
            decoded = unquote(url)
            if decoded != url and decoded.startswith('http'):
                print(f"[_decrypt] URL解码->{decoded[:60]}")
                return decoded
        except:
            pass
        # 3. 反斜杠转义
        cleaned = url.replace('\\/', '/')
        if cleaned != url:
            print(f"[_decrypt] 转义清理->{cleaned[:60]}")
            return cleaned
        return url

    # ========== 搜索 ==========
    def searchContent(self, key, quick):
        return self.searchContentPage(key, quick, '1')

    def searchContentPage(self, key, quick, page):
        if self.use_api:
            return self._api_search(key, quick, page)
        return self._html_search(key, quick, page)

    def _api_search(self, key, quick, page):
        result = {}
        videos = []
        try:
            url = api_url + f"?ac=list&wd={quote(key)}&pg={page}"
            res = requests.get(url, headers=headerx, timeout=10)
            data = res.json()
            if data.get('code') == 1:
                for item in data.get('list', []):
                    videos.append({
                        "vod_id": str(item.get('vod_id', '')),
                        "vod_name": item.get('vod_name', ''),
                        "vod_pic": item.get('vod_pic', ''),
                        "vod_remarks": item.get('vod_remarks', '')
                    })
                result['page'] = data.get('page', page)
                result['pagecount'] = data.get('pagecount', 9999)
                result['limit'] = data.get('limit', 20)
                result['total'] = data.get('total', 999999)
            print(f"[_api_search] 找到 {len(videos)} 条")
        except Exception as e:
            print(f"[_api_search] 错误: {e}")
            result['page'] = page
            result['pagecount'] = 9999
            result['limit'] = 20
            result['total'] = 999999
        result['list'] = videos
        return result

    def _html_search(self, key, quick, page):
        result = {}
        videos = []
        try:
            search_url = xurl + f'/bb/index.php/vod/search.html?wd={quote(key)}&page={page}'
            res = requests.get(search_url, headers=headerx, timeout=10)
            res.encoding = "utf-8"
            html = res.text
            if len(html) > 500:
                videos = self._extract_videos_from_html(html)
            print(f"[_html_search] 找到 {len(videos)} 条")
        except Exception as e:
            print(f"[_html_search] 错误: {e}")
        result['list'] = videos
        result['page'] = page
        result['pagecount'] = 9999
        result['limit'] = 90
        result['total'] = 999999
        return result

    # ================= 本地代理 + 广告清洗 =================
    def localProxy(self, params):
        if params.get('type') == "m3u8":
            return self._proxy_m3u8(params)
        elif params.get('type') == "media":
            return self._proxy_media(params)
        elif params.get('type') == "ts":
            return self._proxy_ts(params)
        return [404, "text/plain", "unsupported type"]

    def _proxy_m3u8(self, params):
        url = params.get('url', '')
        referer = params.get('referer', xurl)
        if not url:
            return [404, "text/plain", "no url"]
        text = self._get_m3u8_content(url, referer)
        if not text:
            return [404, "text/plain", "m3u8 download failed"]
        # 广告清洗 + 相对路径转绝对
        cleaned = self._clean_m3u8(text, url, referer)
        return [200, "application/vnd.apple.mpegurl", cleaned]

    def _proxy_media(self, params):
        return [404, "text/plain", "not supported"]

    def _proxy_ts(self, params):
        return [404, "text/plain", "not supported"]

    def _get_m3u8_content(self, url, referer):
        try:
            headers = {
                'User-Agent': headerx['User-Agent'],
                "Referer": referer,
                "Origin": xurl
            }
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                resp.encoding = 'utf-8'
                return resp.text
        except Exception as e:
            print(f"[_get_m3u8] 失败: {e}")
        return None

    def _clean_m3u8(self, m3u8_text, m3u8_url='', referer='', skip_seconds=25):
        """广告清洗核心：去除广告片段，同时将相对路径转为绝对URL"""
        text = (m3u8_text or '').replace('\r', '')
        # 处理多级 m3u8（主播放列表）
        if '#EXT-X-STREAM-INF' in text:
            out = []
            last_stream = False
            for raw in text.splitlines():
                line = raw.strip()
                if not line:
                    continue
                if line.startswith('#'):
                    out.append(line)
                    last_stream = line.startswith('#EXT-X-STREAM-INF')
                else:
                    abs_url = urljoin(m3u8_url, line)
                    if last_stream or '.m3u8' in line.lower():
                        out.append(self._proxy_m3u8_url(abs_url, referer))
                    else:
                        out.append(abs_url)
                    last_stream = False
            return '\n'.join(out) + '\n'

        # 解析媒体分片
        header, segments, tail, media_sequence, target_duration = self._parse_m3u8_segments(text)
        if not segments:
            return self._convert_to_absolute_urls(text, m3u8_url)  # 无分片时仅转绝对路径

        # 识别主路径（用于区分正片和广告）
        marker = self._main_path_marker(m3u8_url)
        stat = {}
        for seg in segments:
            key = self._segment_host_key(seg['uri'], m3u8_url)
            stat[key] = stat.get(key, 0.0) + float(seg.get('dur') or 0)
        main_key = max(stat.items(), key=lambda x: x[1])[0] if stat else ('', '')
        total_dur = sum(stat.values()) or 0
        main_dur = stat.get(main_key, 0)

        cleaned = []
        removed = 0
        for idx, seg in enumerate(segments):
            key = self._segment_host_key(seg['uri'], m3u8_url)
            is_front = idx < 12
            abs_uri = urljoin(m3u8_url, seg.get('uri', ''))
            is_ad = self._is_ad_segment(seg['uri'], seg.get('dur'), seg.get('tags'))
            if marker and marker not in urlparse(abs_uri).path.lower():
                is_ad = True
            tags_text = '\n'.join(seg.get('tags') or []).upper()
            if is_front and 'METHOD=NONE' in tags_text and marker and marker not in urlparse(abs_uri).path.lower():
                is_ad = True
            if (not is_ad) and is_front and total_dur > 0 and main_dur >= total_dur * 0.6:
                if key != main_key and stat.get(key, 0) <= 90:
                    is_ad = True
            if is_ad:
                removed += 1
                continue
            seg['_idx'] = idx
            cleaned.append(seg)

        # 如果没删到广告，尝试跳过前 N 秒的非主流片段
        if removed == 0 and len(segments) > 4:
            acc = 0.0
            cut = 0
            for idx, seg in enumerate(segments[:12]):
                key = self._segment_host_key(seg['uri'], m3u8_url)
                if key == main_key and acc >= 3:
                    break
                acc += float(seg.get('dur') or target_duration or 3)
                cut = idx + 1
                if acc >= skip_seconds:
                    break
            if cut > 0 and cut < len(segments):
                first_key = self._segment_host_key(segments[0]['uri'], m3u8_url)
                if first_key != main_key:
                    cleaned = segments[cut:]
                    removed = cut

        if not cleaned:
            cleaned = segments
            removed = 0

        # 重新组装 m3u8，转绝对路径
        new_lines = []
        has_m3u = False
        for line in header:
            if line.startswith('#EXTM3U'):
                has_m3u = True
            if line.startswith('#EXT-X-MEDIA-SEQUENCE') or line.startswith('#EXT-X-START'):
                continue
            if line.startswith('#EXT-X-KEY') and 'METHOD=NONE' in line.upper() and removed > 0:
                continue
            new_lines.append(line)
        if not has_m3u:
            new_lines.insert(0, '#EXTM3U')
        first_idx = cleaned[0].get('_idx', removed) if cleaned else removed
        new_lines.append(f'#EXT-X-MEDIA-SEQUENCE:{media_sequence + first_idx}')

        for seg in cleaned:
            for tag in seg.get('tags') or []:
                if tag.startswith('#EXT-X-KEY') or tag.startswith('#EXT-X-MAP'):
                    def _fix_uri(m):
                        return 'URI="' + urljoin(m3u8_url, m.group(1)) + '"'
                    tag = re.sub(r'URI="([^"]+)"', _fix_uri, tag)
                new_lines.append(tag)
            new_lines.append(urljoin(m3u8_url, seg.get('uri', '')))
        if tail:
            for line in tail:
                if line.startswith('#EXT-X-ENDLIST'):
                    new_lines.append(line)
        elif '#EXT-X-ENDLIST' in text:
            new_lines.append('#EXT-X-ENDLIST')
        print(f"[_clean_m3u8] 原片段:{len(segments)} 删除广告:{removed} 保留:{len(cleaned)}")
        return '\n'.join(new_lines) + '\n'

    def _parse_m3u8_segments(self, text):
        lines = [x.strip() for x in text.replace('\r', '').split('\n') if x.strip()]
        header, segments, tail = [], [], []
        pending_tags = []
        media_sequence = 0
        target_duration = 0
        started = False
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith('#EXT-X-MEDIA-SEQUENCE'):
                try:
                    media_sequence = int(line.split(':', 1)[1])
                except:
                    pass
                if not started:
                    header.append(line)
                else:
                    pending_tags.append(line)
            elif line.startswith('#EXT-X-TARGETDURATION'):
                try:
                    target_duration = float(line.split(':', 1)[1])
                except:
                    pass
                if not started:
                    header.append(line)
                else:
                    pending_tags.append(line)
            elif line.startswith('#EXTINF'):
                started = True
                dur = target_duration or 3.0
                m = re.search(r'#EXTINF:\s*([\d.]+)', line)
                if m:
                    try:
                        dur = float(m.group(1))
                    except:
                        pass
                tags = pending_tags + [line]
                pending_tags = []
                uri = ''
                j = i + 1
                while j < len(lines):
                    if lines[j].startswith('#'):
                        tags.append(lines[j])
                        j += 1
                        continue
                    uri = lines[j]
                    break
                if uri:
                    segments.append({'tags': tags, 'uri': uri, 'dur': dur})
                    i = j
                else:
                    tail.extend(tags)
            elif line.startswith('#EXT-X-ENDLIST'):
                tail.append(line)
            elif line.startswith('#'):
                if started:
                    pending_tags.append(line)
                else:
                    header.append(line)
            else:
                started = True
                dur = target_duration or 3.0
                segments.append({'tags': pending_tags, 'uri': line, 'dur': dur})
                pending_tags = []
            i += 1
        return header, segments, tail, media_sequence, target_duration

    def _segment_host_key(self, uri, base_url):
        try:
            full = urljoin(base_url, uri)
            p = urlparse(full)
            path = re.sub(r'/[^/]*$', '/', p.path or '/')
            return (p.netloc.lower(), path.lower())
        except:
            return ('', '')

    def _main_path_marker(self, m3u8_url):
        try:
            p = urlparse(m3u8_url).path
            m = re.search(r'(/\d{8}/[^/]+/\d+kb/hls/)', p)
            if m:
                return m.group(1).lower()
            m = re.search(r'(/\d{8}/[^/]+/)', p)
            if m:
                return m.group(1).lower()
        except:
            pass
        return ''

    def _is_ad_segment(self, uri, dur=0, prev_tags=None):
        u = (uri or '').strip().lower()
        if not u:
            return False
        if any(kw in u for kw in AD_KEYWORDS):
            return True
        ad_paths = ['ad', 'ads', 'advert', 'sponsor', 'preroll', '/gg/', '_gg', 'gg_', '/adv/', '/ad/', '/ads/', 'banner', 'promo']
        if any(p in u for p in ad_paths):
            return True
        try:
            if 0 < float(dur) <= 1.2:
                return True
        except:
            pass
        return False

    def _convert_to_absolute_urls(self, m3u8_text, base_url):
        """将m3u8内的相对路径转为绝对URL（兜底）"""
        lines = m3u8_text.splitlines()
        result = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                result.append(line)
            else:
                abs_url = urljoin(base_url, stripped)
                result.append(abs_url)
        return '\n'.join(result)

    def _proxy_m3u8_url(self, url, referer=''):
        """生成代理播放链接"""
        try:
            if hasattr(self, 'getProxyUrl'):
                return self.getProxyUrl() + '&type=m3u8&url=' + quote(url, safe='') + '&referer=' + quote(referer or xurl, safe='')
        except:
            pass
        return url

    # ================= 播放解析（使用代理以确保广告过滤） =================
    def playerContent(self, flag, id, vipFlags):
        # 判断是否为播放页路径
        is_play_page = False
        play_path = id
        if not id.startswith('http'):
            if '/vod/play/' in id or id.startswith('/'):
                is_play_page = True

        if is_play_page:
            m3u8_url, _ = self._get_m3u8_from_play_page(play_path)
            if not m3u8_url:
                print(f"[playerContent] 未提取到播放地址，id={id}")
                return {"parse": 0, "playUrl": "", "url": ""}
        else:
            m3u8_url = id

        # 最后一次解密
        m3u8_url = self._decrypt_obfuscated_url(m3u8_url)

        # 使用代理链接（代理内部会进行广告清洗）
        proxy_url = self._proxy_m3u8_url(m3u8_url, xurl + '/')
        media_header = {
            "User-Agent": headerx['User-Agent'],
            "Referer": xurl + '/',
            "Origin": xurl
        }
        print(f"[playerContent] 最终代理地址: {proxy_url[:80]}")
        return {
            "parse": 0,
            "playUrl": "",
            "url": proxy_url,
            "header": json.dumps(media_header, ensure_ascii=False)
        }
