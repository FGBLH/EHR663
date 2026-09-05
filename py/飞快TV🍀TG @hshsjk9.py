# -*- coding: utf-8 -*-
# !/usr/bin/python

import sys
import json
import re
import base64
import datetime
import time
from urllib.parse import quote_plus, unquote
from lxml import etree

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    def getName(self):
        return "飞快"

    def init(self, extend=""):
        self.host = "https://feikuai.in"
        self.default_pic = "https://pic.rmb.bdstatic.com/bjh/user/default.png"
        self._home_cache = []
        self._home_cache_time = 0

    # ============================================================
    # 首页
    # ============================================================
    def homeContent(self, filter):
        _r1 = {}
        _c1 = {
            "电影": "1",
            "剧集": "2",
            "综艺": "3",
            "动漫": "4"
        }
        _c2 = [{'type_name': _k1, 'type_id': _v1} for _k1, _v1 in _c1.items()]
        _r1['class'] = _c2
        # 返回空筛选器，不显示任何筛选选项
        _r1['filters'] = {}
        return _r1

    def homeVideoContent(self):
        now = int(time.time())
        if self._home_cache and now - self._home_cache_time < 300:
            return {'list': self._home_cache[:30]}

        _l1 = []
        try:
            _r2 = self.fetch(self.host + "/", headers=self._get_header())
            if not _r2 or not _r2.text:
                return {'list': _l1}

            _h1 = self._parse_dom(_r2)
            if not _h1:
                return {'list': _l1}

            _x1 = _h1.xpath(
                '//div[contains(@class, "module-focus")]//a[contains(@href, "/voddetail/")] | '
                '//div[contains(@class, "module-hot")]//a[contains(@href, "/voddetail/")] | '
                '//div[contains(@class, "module-recommend")]//a[contains(@href, "/voddetail/")] | '
                '//div[contains(@class, "module-items") and contains(@class, "module-poster-items")]//a[contains(@href, "/voddetail/")]'
            )

            _s1 = set()
            for _a1 in _x1:
                _v1 = self._parse_item(_a1)
                if _v1 and _v1["vod_id"] not in _s1:
                    _s1.add(_v1["vod_id"])
                    _l1.append(_v1)

            _l1 = _l1[:30]
            self._home_cache = _l1
            self._home_cache_time = now
        except Exception:
            pass
        return {'list': _l1}

    # ============================================================
    # 分类列表
    # ============================================================
    def categoryContent(self, tid, pg, filter, extend):
        if tid == '0':
            return self.homeVideoContent()

        _r3 = {'list': [], 'page': pg, 'pagecount': 9999, 'limit': 24, 'total': 999999}
        try:
            _e1 = json.loads(extend) if extend and isinstance(extend, str) else {}
            _u2 = self._build_category_url(tid, pg, _e1)
        except Exception:
            _u2 = f'{self.host}/vodshow/{tid}--------{pg}---.html'

        _h2 = self._get_header().copy()
        _h2['Referer'] = f'{self.host}/vodtype/{tid}.html'

        _r4 = self.fetch(_u2, headers=_h2)
        if not _r4 or not _r4.text:
            return _r3

        _h3 = self._parse_dom(_r4)
        _v2 = []
        _s2 = set()

        try:
            _l2 = _h3.xpath('//div[contains(@class, "module-items") and contains(@class, "module-poster-items")]//a[contains(@href, "/voddetail/")]') or \
                  _h3.xpath('//a[contains(@class, "module-poster-item") and contains(@href, "/voddetail/")]') or \
                  _h3.xpath('//div[contains(@class, "module-card-items")]//a[contains(@href, "/voddetail/")]')

            for _a2 in _l2:
                _v3 = self._parse_item(_a2)
                if _v3 and _v3["vod_id"] not in _s2:
                    _s2.add(_v3["vod_id"])
                    _v2.append(_v3)
        except Exception:
            pass

        _r3['pagecount'] = self._get_pagecount(_h3)
        _r3['list'] = _v2
        return _r3

    # ============================================================
    # 详情页
    # ============================================================
    def detailContent(self, ids):
        if not ids:
            return {'list': []}

        _t1 = str(ids[0]).strip()
        _u3 = f'{self.host}/voddetail/{_t1}.html'

        try:
            _r5 = self.fetch(_u3, headers=self._get_header())
            if not _r5 or not _r5.text:
                return {'list': []}
            _h4 = self._parse_dom(_r5)
            if not _h4:
                return {'list': []}
        except Exception:
            return {'list': []}

        _t2 = _h4.xpath('//h1/text() | //div[contains(@class, "module-info-heading")]//h1/text()')
        _t3 = _t2[0].strip() if _t2 else ''

        _p1 = self._get_img(_h4)
        _d1 = self._get_desc(_h4)

        _actor = self._get_text(_h4, '//div[contains(@class, "module-info-item") and contains(text(), "主演")]//span/text()')
        _director = self._get_text(_h4, '//div[contains(@class, "module-info-item") and contains(text(), "导演")]//span/text()')
        _year = self._get_text(_h4, '//div[contains(@class, "module-info-item") and contains(text(), "年份")]//span/text()')
        _area = self._get_text(_h4, '//div[contains(@class, "module-info-item") and contains(text(), "地区")]//span/text()')
        _type = self._get_text(_h4, '//div[contains(@class, "module-info-item") and contains(text(), "类型")]//span/text()')

        _v4 = {
            "vod_id": _t1,
            "vod_name": _t3,
            "vod_pic": _p1,
            "type_name": _type,
            "vod_year": _year,
            "vod_area": _area,
            "vod_remarks": "",
            "vod_actor": _actor,
            "vod_director": _director,
            "vod_content": _d1
        }

        _f1, _l3 = self._get_sources(_h4, _t1)

        if not _f1 or not _l3:
            _f1 = ['飞快']
            _l3 = [f'播放${self.host}/voddetail/{_t1}.html']

        _v4['vod_play_from'] = '$$$'.join(_f1) if _f1 else ""
        _v4['vod_play_url'] = '$$$'.join(_l3)
        return {'list': [_v4]}

    # ============================================================
    # 搜索
    # ============================================================
    def searchContent(self, key, quick, pg='1'):
        _v5 = []
        try:
            _p2 = str(pg)
            _u4 = f'{self.host}/vodsearch/-------------.html?wd={quote_plus(key)}&page={_p2}'
            _h5 = self._get_header().copy()
            _h5['Referer'] = f'{self.host}/vodsearch/-------------.html?wd={quote_plus(key)}'

            _r6 = self.fetch(_u4, headers=_h5)
            if not _r6 or not _r6.text:
                return {'list': []}

            _h6 = self._parse_dom(_r6)
            _i1 = _h6.xpath('//div[contains(@class, "module-items") and contains(@class, "module-poster-items")]//a[contains(@href, "/voddetail/")]') or \
                  _h6.xpath('//a[contains(@class, "module-poster-item") and contains(@href, "/voddetail/")]') or \
                  _h6.xpath('//a[contains(@href, "/voddetail/")]')

            _s3 = set()
            for _a3 in _i1:
                _v6 = self._parse_item(_a3)
                if _v6 and _v6["vod_id"] not in _s3:
                    _s3.add(_v6["vod_id"])
                    _v5.append(_v6)
        except Exception:
            pass
        return {'list': _v5}

    # ============================================================
    # 播放
    # ============================================================
    def playerContent(self, flag, id, vipFlags):
        if isinstance(id, str) and id.startswith('push://'):
            return {"parse": 0, "url": id}

        if '.m3u8' in id or '.mp4' in id:
            return {"parse": 0, "url": id, "header": self._get_header()}

        _u5 = f'{self.host}/vodplay/{id}.html'
        _v7 = _u5

        try:
            _r7 = self.fetch(_u5, headers=self._get_header(), timeout=45)
            if not _r7 or not _r7.text:
                return {"parse": 1, "url": _v7, "header": self._get_header()}

            _p3 = r'(?:var\s+)?player_[a-zA-Z0-9_]+\s*=\s*(\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\})(?=\s*</script>)'
            _m1 = re.search(_p3, _r7.text, re.S)
            if _m1:
                try:
                    _d2 = json.loads(_m1.group(1))
                    _v7 = _d2.get('url') or ''
                    _v7 = self._decode_str(_v7, str(_d2.get('encrypt', '0')))
                    if _v7.startswith('//'):
                        _v7 = 'https:' + _v7
                    if _v7.endswith('.m3u8'):
                        return {"parse": 1, "url": _v7, "header": self._get_header()}
                except Exception:
                    pass

            _iframe = re.search(r'<iframe[^>]*src="([^"]+)"', _r7.text)
            if _iframe:
                _v7 = _iframe.group(1)
                if _v7.startswith('//'):
                    _v7 = 'https:' + _v7
                return {"parse": 1, "url": _v7, "header": self._get_header()}

        except Exception:
            pass

        return {"parse": 1, "url": _v7, "header": self._get_header()}

    # ============================================================
    # 辅助方法
    # ============================================================

    def _parse_item(self, a_element):
        try:
            _h7 = a_element.xpath('./@href')[0] if a_element.xpath('./@href') else ''
            _m2 = re.search(r'/voddetail/(\d+)\.html', _h7)
            if not _m2:
                return None
            _s4 = _m2.group(1)

            _t4 = (a_element.xpath('.//div[contains(@class, "module-poster-item-title")]//text()') or
                   a_element.xpath('.//div[contains(@class, "module-card-item-title")]/a//text()') or
                   a_element.xpath('./@title') or
                   a_element.xpath('.//img/@alt'))
            _n1 = _t4[0].strip() if _t4 else f"视频_{_s4}"

            _i2 = self._get_img(a_element)

            _r8 = a_element.xpath('.//div[contains(@class, "module-item-note")]//text()')
            _r9 = ''.join([x.strip() for x in _r8 if x.strip()]) if _r8 else ""

            return {
                "vod_id": _s4,
                "vod_name": _n1,
                "vod_pic": _i2,
                "vod_remarks": _r9
            }
        except Exception:
            return None

    def _get_img(self, element):
        _i3 = (element.xpath('.//img[contains(@class, "lazy")]/@data-original') or
               element.xpath('.//img[contains(@class, "lazy")]/@src') or
               element.xpath('.//img/@data-original') or
               element.xpath('.//img/@src'))
        if _i3:
            _i4 = _i3[0]
            if _i4.startswith('/'):
                _i4 = self.host + _i4
            elif _i4.startswith('//'):
                _i4 = 'https:' + _i4
            return _i4
        return self.default_pic

    def _get_desc(self, root):
        try:
            _d3 = root.xpath('//div[contains(@class, "module-info-introduction-content")]//text()')
            _d4 = '\n'.join([x.strip() for x in _d3 if x.strip()]) if _d3 else ''
            if not _d4:
                _d3 = root.xpath('//div[contains(@class, "desc")]//text()')
                _d4 = '\n'.join([x.strip() for x in _d3 if x.strip()]) if _d3 else ''
            return _d4
        except Exception:
            return ''

    def _get_text(self, root, xpath_expr):
        try:
            _t = root.xpath(xpath_expr)
            return _t[0].strip() if _t else ''
        except Exception:
            return ''

    def _parse_dom(self, rsp):
        try:
            _p4 = etree.HTMLParser(encoding='utf-8', recover=True, remove_blank_text=True)
            if hasattr(rsp, 'content'):
                return etree.HTML(rsp.content, parser=_p4)
            return etree.HTML(rsp.text.encode('utf-8', errors='ignore'), parser=_p4)
        except Exception:
            return None

    # ===== 构建分类URL（无筛选）=====
    def _build_category_url(self, tid, pg, ext):
        """构建分类URL，不包含任何筛选参数"""
        return f'{self.host}/vodshow/{tid}--------{pg}---.html'

    def _get_pagecount(self, root):
        try:
            _page_text = root.xpath('//div[@id="page"]//text()')
            if _page_text:
                _text = ''.join(_page_text)
                _m = re.search(r'(\d+)\s*页', _text)
                if _m:
                    return int(_m.group(1))
                _m = re.search(r'尾页</a>\s*<a[^>]*href="[^"]*/(\d+)---\.html', _text)
                if _m:
                    return int(_m.group(1))
            _tail = root.xpath('//a[contains(text(), "尾页")]/@href')
            if _tail:
                _m = re.search(r'/(\d+)---\.html', _tail[0])
                if _m:
                    return int(_m.group(1))
        except Exception:
            pass
        return 9999

    # ============================================================
    # 获取播放线路
    # ============================================================
    def _get_sources(self, root, tid):
        _f2 = []
        _l4 = []
        self._get_normal_sources(root, tid, _f2, _l4)
        self._get_pan_sources(root, tid, _f2, _l4)
        return _f2, _l4

    def _get_normal_sources(self, root, tid, playFrom, playList):
        try:
            _e4 = root.xpath('//div[contains(@class, "module-play-list")]//a[contains(@href, "/vodplay/")] | '
                             '//ul[contains(@class, "module-play-list")]//a[contains(@href, "/vodplay/")]')

            _g1 = {}
            for _a4 in _e4:
                try:
                    _h8 = _a4.xpath('./@href')[0] if _a4.xpath('./@href') else ''
                    _m3 = re.search(r'/vodplay/(\d+)-(\d+)-(\d+)\.html', _h8)
                    if not _m3:
                        continue
                    _v8, _s5, _e5 = _m3.groups()
                    if _v8 != tid:
                        continue
                    _n2 = ''.join(_a4.xpath('string(.)')).strip()
                    if not _n2 or _n2 in ('立即播放', '收藏', '追更', '分享', '报错', '下载'):
                        continue
                    if _s5 not in _g1:
                        _g1[_s5] = []
                    _g1[_s5].append(f"{_n2}${_v8}-{_s5}-{_e5}")
                except Exception:
                    continue

            _l5 = root.xpath('//div[contains(@class, "module-tab-items-box")]//div[contains(@class, "module-tab-item")]//span/text()')
            _l5 = [x.strip() for x in _l5 if x.strip()]

            for _i, _s7 in enumerate(_g1.keys()):
                _s8 = _l5[_i] if _i < len(_l5) else f"线路{_i+1}"
                if _g1[_s7]:
                    playFrom.append(_s8)
                    playList.append('#'.join(_g1[_s7]))
        except Exception:
            pass

    def _get_pan_sources(self, root, tid, playFrom, playList):
        try:
            _d5 = root.xpath('//div[@id="download-list"]')
            if not _d5:
                return

            _p6 = {
                '百度网盘': '百度网盘',
                '夸克网盘': '夸克网盘',
                '迅雷云盘': '迅雷云盘',
                '阿里云盘': '阿里云盘',
                '天翼云盘': '天翼云盘',
                'UC网盘': 'UC网盘',
                '115网盘': '115网盘',
                '移动云盘': '移动云盘'
            }

            _t5 = root.xpath('//div[@id="y-downList"]//div[contains(@class, "module-tab-item")]')

            for _t6 in _t5:
                try:
                    _s9 = ''.join(_t6.xpath('.//span/text()')).strip()
                    if not _s9 or _s9 == '磁力链接':
                        continue

                    _s10 = _p6.get(_s9, _s9)

                    _t7 = _t6.xpath('./@data-index')
                    if not _t7:
                        continue
                    _t8 = _t7[0]

                    _c4 = root.xpath(f'//div[@id="tab-content-{_t8}"]//div[@class="module-row-info"]//a')

                    _e6 = []
                    for _i6, _l6 in enumerate(_c4, 1):
                        try:
                            _u6 = _l6.xpath('./@href')
                            if not _u6:
                                continue
                            _u7 = _u6[0].strip()

                            _h9 = _l6.xpath('.//h4/text()')
                            if _h9:
                                _e7 = _h9[0].strip()
                                _e7 = re.sub(r'@一键搜片-\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}$', '', _e7).strip()
                            else:
                                _e7 = f"资源{_i6}"

                            if not _u7.startswith(('http://', 'https://')):
                                if _u7.startswith('//'):
                                    _u8 = 'https:' + _u7
                                elif _u7.startswith('/'):
                                    _u8 = self.host + _u7
                                else:
                                    continue
                            else:
                                _u8 = _u7

                            _e6.append(f"{_e7}$push://{_u8}")
                        except Exception:
                            continue

                    if _e6:
                        playFrom.append(_s10)
                        playList.append('#'.join(_e6))
                except Exception:
                    continue
        except Exception:
            pass

    def _decode_str(self, raw, encrypt):
        try:
            if not raw:
                return ''
            _e8 = str(encrypt or '0').strip()
            if _e8 == '1':
                _t9 = unquote(raw)
            elif _e8 == '2':
                try:
                    _b2 = base64.b64decode(raw + '===')
                    _t9 = unquote(_b2.decode('utf-8', errors='ignore'))
                except Exception:
                    _t9 = unquote(raw)
            else:
                _t9 = raw

            _t9 = re.sub(r'%u([0-9a-fA-F]{4})',
                         lambda _m5: chr(int(_m5.group(1), 16)), _t9)
            return _t9
        except Exception:
            return raw

    # ============================================================
    # 通用方法
    # ============================================================
    def _get_header(self):
        return {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive"
        }

    def localProxy(self, params):
        pass

    def isVideoFormat(self, url):
        return url

    def manualVideoCheck(self):
        return []

    def destroy(self):
        pass