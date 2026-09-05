# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""
官网：https://av3698.cc/
"""
import re
import json
import time
import urllib.parse

try:
    import requests
    import urllib3
    urllib3.disable_warnings()
except ImportError:
    requests = None

try:
    import sys
    sys.path.append('..')
    from base.spider import Spider as BaseSpider
except ImportError:
    BaseSpider = object

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
HOST = 'https://av3698.cc'

_session = None


def _get_session():
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            'User-Agent': UA,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        })
    return _session


def _http_get(url, timeout=15):
    """GET → str（requests 优先，urllib 兜底）"""
    if requests is not None:
        try:
            r = _get_session().get(url, timeout=timeout, verify=False)
            return r.text
        except Exception:
            return ''
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': UA,
            'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        })
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.read().decode('utf-8', errors='replace')
    except Exception:
        return ''
_CATS = [
    (1, '日韩无码', 54), (2, '国产主播', 55), (3, '日韩精品', 57), (4, '欧美劲爆', 58),
    (5, '成人动漫', 59), (6, '自拍偷拍', 60), (7, '伦理影片', 61), (8, '视频二区', 69),
    (9, '巨乳尤物', 70), (10, '颜射系列', 71), (11, '口交视频', 72), (12, '自慰系列', 73),
    (13, '教师学生', 74), (14, '群P换妻', 75), (15, 'AI换脸', 76), (16, '视频三区', 56),
    (17, '中文字幕', 62), (18, '人妻系列', 63), (19, '制服诱惑', 64), (20, '强奸乱伦', 65),
    (21, '无码流出', 66), (22, '主播诱惑', 67), (23, '在线观看', 68), (24, '视频四区', 77),
    (25, '熟女专区', 78), (26, '欧美专区', 79), (27, '调教捆绑', 80), (28, '情趣丝袜', 81),
    (29, '抖阴短视', 82), (30, '素人探花', 83), (31, '国模私拍', 84), (32, 'SWAG', 85),
    (33, '91大神', 86), (34, '麻豆传媒', 87), (35, '蜜桃传媒', 88), (36, '国产传媒', 89),
    (37, '视频五区', 90), (38, '野战车震', 91), (39, 'SM调教', 92), (40, '家庭乱伦', 93),
    (41, '百合女同', 94), (42, '学生空姐', 95), (43, '撸管必看', 96), (44, '偷情少妇', 97),
    (45, '萝莉幼齿', 98), (46, '嫩模大秀', 99), (47, '原味内衣', 100), (48, '视频六区', 101),
    (49, '韩系主播', 102), (50, '情侣自拍', 103), (51, '美腿丝袜', 104), (52, '超碰在线', 105),
    (53, '福利导航', 106), (54, '视频七区', 107), (55, '网红主播', 108), (56, '足控专区', 109),
    (57, '视频八区', 110), (58, '抖阴直播', 111), (59, '九色视频', 112), (60, '香蕉视频', 113),
    (61, '视频九区', 114), (62, '红杏视频', 115), (63, '杏吧视频', 116), (64, '草榴视频', 117),
    (65, '色影视界', 118), (66, '人人视频', 119), (67, '视频十区', 120), (68, '女仆咖啡', 121),
    (69, '露出调教', 122), (70, '温泉旅馆', 123), (71, '紧身旗袍', 124), (72, '在线影视', 125),
    (73, '里番动漫', 126), (74, '三级剧情', 127), (75, '明星换脸', 128), (76, '男男专区', 129),
    (77, '主播热舞', 130), (78, '素人自拍', 131),
]


def _http_get(url, timeout=15):
    """urllib GET → str"""
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': UA,
            'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        })
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.read().decode('utf-8', errors='replace')
    except Exception:
        return ''


class Spider(BaseSpider):
    host = HOST
    name = 'AV3698'

    def init(self, cfg):
        pass

    def getName(self):
        return self.name

    def isVideoFormat(self, url):
        if not url:
            return False
        return '.m3u8' in url or '.mp4' in url

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def localProxy(self, param):
        if not param or not param.startswith('http'):
            return [500, 'text/plain', '']
        try:
            import urllib.request
            req = urllib.request.Request(param, headers={'User-Agent': UA})
            resp = urllib.request.urlopen(req, timeout=20)
            data = resp.read()
            ctype = resp.headers.get('Content-Type', 'application/octet-stream')
            return [200, ctype, data]
        except Exception as e:
            return [502, 'text/plain', str(e).encode()]

    # ---------- 首页 ----------
    def homeContent(self, filter):
        classes = [{'type_id': str(cid), 'type_name': name} for cid, name, _ in _CATS]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        html = _http_get(HOST + '/')
        items = self._parse_cards(html)
        if not items:
            # 备用: 分类1
            html = _http_get(HOST + '/?source=external&category=54')
            items = self._parse_cards(html)
        return {'list': items}

    # ---------- 分类 ----------
    def categoryContent(self, tid, pg, filter, extend):
        cat_id = self._cat_id(tid)
        if cat_id is None:
            return {'list': [], 'page': 1, 'pagecount': 1}
        url = f'{HOST}/?q=&source=external&category={cat_id}&page={pg}'
        html = _http_get(url)
        items = self._parse_cards(html)

        # 页数
        m = re.search(r'第\s*(\d+)\s*/\s*(\d+)\s*页', html)
        pagecount = int(m.group(2)) if m else 1

        return {'list': items, 'page': int(pg), 'pagecount': pagecount}

    def _cat_id(self, tid):
        try:
            tid = int(str(tid).split(':')[-1])
        except Exception:
            return None
        for cid, _, cat in _CATS:
            if cid == tid:
                return cat
        return None

    # ---------- 卡片解析 ----------
    def _parse_cards(self, html):
        items = []
        for m in re.finditer(r'<article class="media-card">([\s\S]*?)</article>', html):
            box = m.group(1)
            hm = re.search(r'href="(/xwatch/\d+)"', box)
            if not hm:
                continue
            vid = hm.group(1)
            title_m = re.search(r'class="card-title"[^>]*>([^<]+)</a>', box)
            title = title_m.group(1).strip() if title_m else vid
            pic_m = re.search(r'<img[^>]+src="([^"]+)"', box)
            pic = pic_m.group(1) if pic_m else ''
            dur_m = re.search(r'class="duration"[^>]*>([^<]+)<', box)
            remark = dur_m.group(1).strip() if dur_m else ''
            # 封面解码为原图直链
            if 'cached-thumb?url=' in pic:
                u = re.search(r'url=([^&"]+)', pic)
                if u:
                    pic = urllib.parse.unquote(u.group(1))
            items.append({
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': pic,
                'vod_remarks': remark,
            })
        return items

    # ---------- 详情 ----------
    def detailContent(self, ids):
        try:
            did = str(ids[0] if isinstance(ids, list) else ids)
        except Exception:
            return {'list': []}
        if not did.startswith('/'):
            did = '/xwatch/' + did
        html = _http_get(HOST + did)
        if not html:
            return {'list': []}

        title_m = re.search(r'<title>([^<]+)', html)
        title = title_m.group(1).replace(' · av3698.cc', '').strip() if title_m else did

        # 播放地址
        stream = ''
        m = re.search(r'data-stream="([^"]+)"', html)
        if m:
            stream = m.group(1)
        # 备用: 页面内 m3u8
        if not stream:
            m2 = re.search(r'https?://[^"\'\s\\]+\.m3u8[^"\'\s\\]*', html)
            if m2:
                stream = m2.group(0)

        pic = ''
        pm = re.search(r'poster="([^"]+)"', html)
        if pm:
            pic = pm.group(1)

        if not stream:
            return {'list': []}

        vod = {
            'vod_id': did,
            'vod_name': title or did,
            'vod_pic': pic,
            'vod_content': title or did,
            'vod_play_from': 'av3698',
            'vod_play_url': f'直链${stream}',
            'vod_remarks': 'M3U8',
        }
        return {'list': [vod]}

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg=1):
        kw = urllib.parse.quote(key)
        url = f'{HOST}/?q={kw}'
        html = _http_get(url)
        items = self._parse_cards(html)
        if not items:
            url = f'{HOST}/?source=home&q={kw}'
            html = _http_get(url)
            items = self._parse_cards(html)
        return {'list': items}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags=None):
        return {
            'parse': 0,
            'url': id,
            'jx': 0,
            'header': {
                'User-Agent': UA,
                'Referer': HOST + '/',
            }
        }


# ---------- 本地测试 ----------
if __name__ == '__main__':
    sp = Spider()
    print('=== homeContent ===')
    hc = sp.homeContent(True)
    print(f'分类: {len(hc["class"])}')

    print('\n=== categoryContent (日韩无码) ===')
    cc = sp.categoryContent('1', 1, {}, '')
    print(f'视频: {len(cc["list"])}, 页数: {cc["pagecount"]}')
    if cc['list']:
        print(f'  例: {cc["list"][0]["vod_name"][:40]}')

    print('\n=== detailContent ===')
    d = sp.detailContent([cc['list'][0]['vod_id']])
    if d['list']:
        it = d['list'][0]
        print(f'  标题: {it["vod_name"][:40]}')
        print(f'  播放: {it["vod_play_url"][:80]}')

    print('\n=== searchContent (HEYZO) ===')
    sc = sp.searchContent('HEYZO', False)
    print(f'结果: {len(sc["list"])} 条')
