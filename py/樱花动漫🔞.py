# -*- coding: utf-8 -*-
"""
樱花动漫 (www.91yhdm.com) 爬虫
适配 TVBox / 影视仓 / OK影视 等空壳影视 APP
"""

import sys
import re
import json
import time
import base64
from urllib.parse import quote, unquote, urljoin

import requests as rq

sys.path.append('..')
try:
    from base.spider import Spider
except ImportError:
    class Spider:
        def fetch(self, url, headers=None, **kw):
            kw.pop('timeout', None)
            r = rq.get(url, headers=headers, timeout=15, **kw)
            r.encoding = 'utf-8'
            return r


HOST = "https://www.91yhdm.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

# vodshow 12 段位: key -> 下标
FILTER_SLOT = {
    "tid":    0,   # 子分类(子 type_id) —— 直接替换分类 id
    "area":   1,   # 地区
    "by":     2,   # 排序
    "class":  3,   # 剧情/类型（本站真正的子分类）
    "lang":   4,   # 语言
    "letter": 5,   # 字母
    "plot":   6,
    "state":  7,
    "page":   8,   # 页码
    "tag":    9,
    "version": 10,
    "year":   11,  # 年份
}
SLOT_KEY = {v: k for k, v in FILTER_SLOT.items()}

# 页面分组名 -> 筛选 key（兜底映射，主逻辑靠 URL 段位自动推断）
GROUP_KEY = {
    "类型": "tid",
    "剧情": "class",
    "地区": "area",
    "年份": "year",
    "年代": "year",
    "语言": "lang",
    "字母": "letter",
    "排序": "by",
    "版本": "version",
    "状态": "state",
}
GROUP_ORDER = ["class", "tid", "area", "year", "lang", "by", "letter"]

# 站点支持但页面未渲染的排序（实测 hits/score/time 均生效）
SORT_FILTER = {
    "key": "by",
    "name": "排序",
    "value": [
        {"n": "最新", "v": "time"},
        {"n": "人气", "v": "hits"},
        {"n": "评分", "v": "score"},
    ],
}

# 兜底分类（导航解析失败时使用）
DEFAULT_CLASSES = [
    {"type_id": "1",  "type_name": "国内动漫"},
    {"type_id": "2",  "type_name": "日韩动漫"},
    {"type_id": "3",  "type_name": "欧美动漫"},
    {"type_id": "20", "type_name": "动漫电影"},
]


class Spider(Spider):

    # ================================================================ 基础
    def init(self, extend=""):
        self.host = HOST
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": HOST + "/",
        }
        self._session = rq.Session()
        self._session.trust_env = False
        self._session.headers.update(self.headers)
        self._cache = {}
        self._cache_ts = 0
        self._last_req = 0.0
        return self

    def getName(self):
        return "樱花动漫"

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|flv|mkv|avi|ts|m4a)(\?|$)', str(url), re.I))

    def manualVideoCheck(self):
        return False

    def action(self, action):
        pass

    def destroy(self):
        pass

    def localProxy(self, param):
        pass

    # ================================================================ 请求
    def _throttle(self, gap=0.35):
        """轻量节流，避免连续请求被站点风控"""
        wait = gap - (time.time() - self._last_req)
        if wait > 0:
            time.sleep(wait)
        self._last_req = time.time()

    def _get(self, url, timeout=15, tries=2):
        for i in range(tries):
            try:
                self._throttle()
                r = self._session.get(url, headers=self.headers,
                                      timeout=timeout, verify=False)
                r.encoding = 'utf-8'
                if r.status_code == 200 and r.text:
                    return r.text
            except Exception:
                pass
            # 备用通道（TVBox 环境下 base.Spider.fetch）
            try:
                r = self.fetch(url, headers=self.headers, timeout=timeout)
                txt = r.text if hasattr(r, 'text') else str(r)
                if txt:
                    return txt
            except Exception:
                pass
            time.sleep(0.6 * (i + 1))
        return ""

    # ================================================================ 工具
    @staticmethod
    def _s(text, pattern, idx=1, default=""):
        m = re.search(pattern, text or '', re.S)
        return m.group(idx).strip() if m else default

    @staticmethod
    def _clean(text):
        text = re.sub(r'<!--[\s\S]*?-->', '', text or '')
        text = re.sub(r'<[^>]+>', ' ', text)
        text = (text.replace('&nbsp;', ' ').replace('&amp;', '&')
                    .replace('&quot;', '"').replace('&#39;', "'")
                    .replace('&lt;', '<').replace('&gt;', '>'))
        return re.sub(r'\s+', ' ', text).strip()

    @staticmethod
    def _abs(url):
        if not url:
            return ""
        url = url.strip()
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('http'):
            return url
        return urljoin(HOST + '/', url)

    @classmethod
    def _pic(cls, url):
        """过滤 lazyload 占位图"""
        if not url or 'load.gif' in url or url.endswith('/statics/img/load.gif'):
            return ""
        return cls._abs(url)

    # ========================================================== URL 构造
    @staticmethod
    def build_show(tid, page=1, extend=None):
        """构造 12 段 vodshow 筛选 URL"""
        segs = [''] * 12
        segs[0] = str(tid)
        for k, v in (extend or {}).items():
            slot = FILTER_SLOT.get(k)
            if slot is None:
                continue
            v = str(v).strip()
            if not v or v in ('全部', '0'):
                continue
            segs[slot] = v          # tid 时会直接覆盖段位[0]
        if page and int(page) > 1:
            segs[8] = str(int(page))
        return "%s/vodshow/%s.html" % (
            HOST, '-'.join(quote(x, safe='') for x in segs))

    @staticmethod
    def build_type(tid, page=1):
        if page and int(page) > 1:
            return Spider.build_show(tid, page)
        return "%s/vodtypehtml/%s.html" % (HOST, tid)

    @staticmethod
    def build_search(key, page=1):
        """构造 14 段 vodsearch URL，段位[0]=wd 段位[10]=page"""
        segs = [''] * 14
        segs[0] = str(key)
        if page and int(page) > 1:
            segs[10] = str(int(page))
        return "%s/vodsearch/%s.html" % (
            HOST, '-'.join(quote(x, safe='') for x in segs))

    # ========================================================== 列表解析
    def _parse_list(self, html):
        """解析影片卡片（网格页 + 搜索列表页通用），含封面"""
        items, seen = [], set()
        if not html:
            return items

        # 主匹配：带 data-original 懒加载封面的缩略图块
        for m in re.finditer(
                r'<a\s+class="[^"]*stui-vodlist__thumb[^"]*"\s+'
                r'href="/vodhtml/(\d+)\.html"\s+'
                r'title="([^"]*)"\s+'
                r'data-original="([^"]*)"[^>]*>([\s\S]{0,400}?)</a>', html):
            vid, name, pic, inner = m.groups()
            if vid in seen:
                continue
            seen.add(vid)
            items.append({
                "vod_id": vid,
                "vod_name": self._clean(name),
                "vod_pic": self._pic(pic),
                "vod_remarks": self._clean(
                    self._s(inner, r'<span class="pic-text[^"]*">([\s\S]*?)</span>')),
            })
        if items:
            return items

        # 兜底1：属性顺序不定
        for m in re.finditer(
                r'<a\s+class="[^"]*stui-vodlist__thumb[^"]*"[^>]*?'
                r'href="/vodhtml/(\d+)\.html"[^>]*?>([\s\S]{0,500}?)</a>', html):
            vid, blk = m.group(1), m.group(0)
            if vid in seen:
                continue
            seen.add(vid)
            items.append({
                "vod_id": vid,
                "vod_name": self._clean(self._s(blk, r'title="([^"]*)"')),
                "vod_pic": self._pic(self._s(blk, r'data-original="([^"]*)"')
                                     or self._s(blk, r'data-src="([^"]*)"')),
                "vod_remarks": self._clean(
                    self._s(blk, r'<span class="pic-text[^"]*">([\s\S]*?)</span>')),
            })
        if items:
            return items

        # 兜底2：只取标题行
        for vid, name in re.findall(
                r'class="title text-overflow"><a[^>]+href="/vodhtml/(\d+)\.html"[^>]*'
                r'title="([^"]*)"', html):
            if vid in seen:
                continue
            seen.add(vid)
            items.append({"vod_id": vid, "vod_name": self._clean(name),
                          "vod_pic": "", "vod_remarks": ""})
        return items

    @staticmethod
    def _parse_pagecount(html, default=0):
        """读取总页数：优先 <span class="num">1/129</span>，其次尾页链接"""
        m = re.search(r'<span class="num">\s*\d+\s*/\s*(\d+)\s*</span>', html or '')
        if m:
            return int(m.group(1))
        nums = []
        for seg in re.findall(r'href="/vodshow/([^"]+)\.html"', html or ''):
            parts = unquote(seg).split('-')
            if len(parts) >= 9 and parts[8].isdigit():
                nums.append(int(parts[8]))
        for seg in re.findall(r'href="/vodsearch/([^"]+)\.html"', html or ''):
            parts = unquote(seg).split('-')
            if len(parts) >= 11 and parts[10].isdigit():
                nums.append(int(parts[10]))
        return max(nums) if nums else default

    # ======================================================= 分类 / 筛选
    def _parse_filters(self, tid):
        """
        解析某父分类页的全部筛选器（子分类/地区/年份/语言/字母）。
        注意: 本站「按类型」「按剧情」两块被 HTML 注释包裹，但链接依然有效，
              因此这里直接在原始 HTML（含注释）上解析。
        """
        html = self._get(self.build_type(tid))
        if not html:
            return []

        groups = {}
        for m in re.finditer(
                r'<span class="text-muted">\s*按([^<]{1,8}?)\s*</span>([\s\S]*?)</ul>', html):
            gname = self._clean(m.group(1))
            body = m.group(2)

            values, seen = [], set()
            key = None
            for href, label in re.findall(
                    r'<a\s+href="(/vodshow/[^"]+\.html)"[^>]*>([^<]+)</a>', body):
                label = self._clean(label)
                if not label:
                    continue

                segs = unquote(href[len('/vodshow/'):-len('.html')]).split('-')
                if len(segs) < 12:
                    continue

                # 与本分类基准对比，定位该分组占用的段位
                val, slot = "", None
                for i, sv in enumerate(segs):
                    if not sv:
                        continue
                    if i == 0:
                        if sv != str(tid):      # 子 type_id 切换
                            val, slot = sv, 0
                            break
                        continue
                    if i == 8:                  # 页码段忽略
                        continue
                    val, slot = sv, i
                    break

                if slot is not None and key is None:
                    key = SLOT_KEY.get(slot)
                if label == '全部':
                    val = ""
                if val in seen:
                    continue
                seen.add(val)
                values.append({"n": label, "v": val})

            if key is None:
                key = GROUP_KEY.get(gname)
            if not key or len(values) < 2:
                continue
            if values[0]["v"] != "":
                values.insert(0, {"n": "全部", "v": ""})
            groups[key] = {"key": key, "name": gname, "value": values}

        # 站点未渲染排序块，但段位[2]有效 —— 主动补上
        if "by" not in groups:
            g = dict(SORT_FILTER)
            g["value"] = [{"n": "默认", "v": ""}] + list(SORT_FILTER["value"])
            groups["by"] = g

        out = [groups[k] for k in GROUP_ORDER if k in groups]
        out += [v for k, v in groups.items() if k not in GROUP_ORDER]
        return out

    def _load_home(self, force=False):
        """抓导航分类 + 逐个父分类抓子分类筛选器 + 首页推荐"""
        if self._cache and not force and (time.time() - self._cache_ts) < 1800:
            return self._cache

        html = self._get(HOST + "/")

        classes = []
        nav = self._s(html, r'<ul class="stui-header__menu[^"]*">([\s\S]*?)</ul>')
        # 注意：nav 里可能混有被注释的项，先剔除注释
        nav = re.sub(r'<!--[\s\S]*?-->', '', nav or '')
        for href, name in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>', nav):
            m = re.search(r'/vod(?:typehtml|show)/(\d+)', href)
            if not m:
                continue                      # 过滤 首页 / 热播 / 专题 / 明星
            name = self._clean(name)
            if not name or name == '首页':
                continue
            if any(c["type_id"] == m.group(1) for c in classes):
                continue
            classes.append({"type_id": m.group(1), "type_name": name})

        if not classes:
            classes = list(DEFAULT_CLASSES)

        filters = {}
        for c in classes:
            try:
                f = self._parse_filters(c["type_id"])
                if f:
                    filters[c["type_id"]] = f
            except Exception:
                continue

        self._cache = {
            "class": classes,
            "filters": filters,
            "list": self._parse_list(html),
        }
        self._cache_ts = time.time()
        return self._cache

    # ================================================================ 接口
    def homeContent(self, filter=True):
        try:
            data = self._load_home()
            return {"class": data["class"],
                    "filters": data["filters"],
                    "list": data["list"]}
        except Exception:
            return {"class": list(DEFAULT_CLASSES), "filters": {}, "list": []}

    def homeVideoContent(self):
        try:
            data = self._load_home()
            lst = data.get("list") or self._parse_list(self._get(HOST + "/"))
            return {"list": lst}
        except Exception:
            return {"list": []}

    def categoryContent(self, tid, pg=1, filter=False, extend=None):
        try:
            pn = max(int(str(pg) or 1), 1)
            extend = extend or {}
            active = {k: v for k, v in extend.items()
                      if v and str(v).strip() not in ('全部', '0', '')}

            # 首页无筛选走 vodtypehtml（站点默认入口），其余一律走 vodshow
            if pn == 1 and not active:
                url = self.build_type(tid, 1)
            else:
                url = self.build_show(tid, pn, active)

            html = self._get(url)
            items = self._parse_list(html)

            # vodtypehtml 偶发异常时回退 vodshow
            if not items and pn == 1 and not active:
                html = self._get(self.build_show(tid, 1))
                items = self._parse_list(html)

            if not items:
                # 已翻过尾页：pagecount 收敛到上一页，通知壳子停止加载
                return {"list": [], "page": pn, "pagecount": max(pn - 1, 1),
                        "limit": 36, "total": 0}

            pagecount = self._parse_pagecount(html, default=0)
            if not pagecount:
                pagecount = pn + 1 if len(items) >= 30 else pn
            pagecount = max(pagecount, pn)
            return {"list": items, "page": pn, "pagecount": pagecount,
                    "limit": len(items), "total": pagecount * len(items)}
        except Exception:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 36, "total": 0}

    def detailContent(self, ids):
        try:
            vid = str(ids[0]) if isinstance(ids, (list, tuple)) else str(ids)
            vid = re.sub(r'\D', '', vid)
            if not vid:
                return {"list": []}

            html = self._get("%s/vodhtml/%s.html" % (HOST, vid))
            if not html:
                return {"list": []}

            detail = self._s(html, r'<div class="stui-content__detail">([\s\S]*?)<div class="play-btn') \
                or self._s(html, r'<div class="stui-content__detail">([\s\S]{0,4000})')

            name = self._clean(self._s(detail, r'<h1[^>]*>([\s\S]*?)</h1>')) \
                or self._clean(self._s(html, r'<h1[^>]*>([\s\S]*?)</h1>'))

            pic = self._pic(
                self._s(html, r'<div class="stui-content__thumb">[\s\S]{0,400}?data-original="([^"]+)"')
                or self._s(html, r'<meta property="og:image" content="([^"]+)"'))

            def field(label):
                blk = self._s(detail, r'<span class="text-muted[^"]*">\s*%s：\s*</span>([\s\S]*?)(?:<span class="split-line">|</p>)' % label)
                return self._clean(blk)

            type_name = field('类型')
            area = field('地区')
            year = field('年份')
            actor = field('主演')
            director = field('导演')
            update = field('更新')

            # 年份兜底：类型行里的 4 位数字
            if not re.fullmatch(r'(19|20)\d{2}', year or ''):
                year = self._s(detail, r'年份：\s*</span>\s*<a[^>]*>\s*((?:19|20)\d{2})')

            # 备注（更新至xx集）
            remarks = self._clean(
                self._s(html, r'<div class="stui-content__thumb">[\s\S]{0,600}?'
                              r'<span class="pic-text[^"]*">([\s\S]*?)</span>')) \
                or (('更新：' + update) if update else '')

            # 完整剧情简介（#desc 面板），页面顶部那段是截断的
            content = self._clean(
                self._s(html, r'id="desc"[\s\S]{0,800}?<div class="stui-pannel_bd">\s*'
                              r'<p[^>]*>([\s\S]*?)</p>'))
            if not content:
                content = self._clean(
                    self._s(detail, r'<p class="desc[^"]*">([\s\S]*?)</p>'))
                content = re.sub(r'^简介：\s*', '', content)
                content = re.sub(r'\s*详情\s*$', '', content)

            # ---- 播放线路 ----
            play_from, play_url = [], []
            tabs = self._s(html, r'<ul class="nav nav-tabs[^"]*">([\s\S]*?)</ul>')
            from_names = [self._clean(re.sub(r'<small>[\s\S]*?</small>', '', x))
                          for x in re.findall(r'<a[^>]+data-toggle="tab"[^>]*>([\s\S]*?)</a>',
                                              tabs or '')]

            for i, ul in enumerate(re.findall(
                    r'<ul class="stui-content__playlist[^"]*">([\s\S]*?)</ul>', html)):
                eps = []
                for href, label in re.findall(
                        r'<a[^>]+href="(/vodplay/[^"]+\.html)"[^>]*>([^<]*)</a>', ul):
                    label = self._clean(label) or ('第%d集' % (len(eps) + 1))
                    label = label.replace('$', '_').replace('#', '_')
                    eps.append("%s$%s" % (label, href))
                if not eps:
                    continue
                fname = from_names[i] if i < len(from_names) else ""
                fname = re.sub(r'[$#]', '', fname) or ("线路%d" % (i + 1))
                play_from.append(fname)
                play_url.append("#".join(eps))

            vod = {
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic,
                "vod_year": year,
                "vod_area": area,
                "type_name": type_name,
                "vod_remarks": remarks,
                "vod_actor": actor,
                "vod_director": director,
                "vod_content": content,
                "vod_play_from": "$$$".join(play_from),
                "vod_play_url": "$$$".join(play_url),
            }
            return {"list": [vod]}
        except Exception:
            return {"list": []}

    def searchContent(self, key, quick=False, pg=1):
        try:
            pn = max(int(str(pg) or 1), 1)
            html = self._get(self.build_search(key, pn))
            items = self._parse_list(html)

            # 回退：表单 GET 形式
            if not items and pn == 1:
                html = self._get("%s/vodsearch/-------------.html?wd=%s"
                                 % (HOST, quote(str(key))))
                items = self._parse_list(html)

            if not items:
                return {"list": [], "page": pn, "pagecount": max(pn - 1, 1),
                        "limit": 10, "total": 0}

            pagecount = self._parse_pagecount(html, default=0)
            if not pagecount:
                pagecount = pn + 1 if len(items) >= 10 else pn
            pagecount = max(pagecount, pn)
            return {"list": items, "page": pn, "pagecount": pagecount,
                    "limit": len(items), "total": pagecount * len(items)}
        except Exception:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 10, "total": 0}

    def playerContent(self, flag, id, vipFlags=None):
        headers = {"User-Agent": UA, "Referer": HOST + "/"}
        try:
            pid = str(id or "")
            if '$' in pid:
                pid = pid.split('$')[-1]

            # 已是直链
            if pid.startswith('http') and self.isVideoFormat(pid):
                return {"parse": 0, "playUrl": "", "url": pid, "header": headers}

            url = pid if pid.startswith('http') else self._abs(pid)
            html = self._get(url)

            real = ""
            m = re.search(r'player_aaaa\s*=\s*(\{[\s\S]*?\})\s*</script>', html)
            if m:
                raw = m.group(1)
                try:
                    j = json.loads(raw)
                except Exception:
                    j = {"url": self._s(raw, r'"url"\s*:\s*"([^"]*)"'),
                         "encrypt": self._s(raw, r'"encrypt"\s*:\s*"?(\d)"?')}
                real = str(j.get('url', '')).replace('\\/', '/')
                enc = str(j.get('encrypt', '0'))
                try:
                    if enc == '1':
                        real = unquote(real)
                    elif enc == '2':
                        real = unquote(base64.b64decode(real).decode('utf-8', 'ignore'))
                except Exception:
                    pass

            # 兜底：iframe / 裸 m3u8
            if not real:
                src = self._s(html, r'<iframe[^>]+src="([^"]+)"')
                if src:
                    mm = re.search(r'[?&]url=([^&"\']+)', src)
                    real = unquote(mm.group(1)) if mm else self._abs(src)
            if not real:
                real = self._s(html, r'(https?://[^\s"\'\\]+\.m3u8[^\s"\'\\]*)')

            if not real:
                return {"parse": 1, "playUrl": "", "url": url, "header": headers}

            real = self._abs(real)
            parse = 0 if self.isVideoFormat(real) else 1
            return {"parse": parse, "playUrl": "", "url": real, "header": headers}
        except Exception:
            return {"parse": 1, "playUrl": "", "url": str(id), "header": headers}


# ============================================================ 本地自测
if __name__ == '__main__':
    import urllib3
    urllib3.disable_warnings()

    s = Spider()
    s.init()

    print("=" * 72)
    home = s.homeContent(True)
    print("分类:", [c['type_name'] + '/' + c['type_id'] for c in home['class']])
    for tid, fl in home['filters'].items():
        print("  筛选[%s]: %s" % (tid, [(f['name'], f['key'], len(f['value'])) for f in fl]))
    print("首页推荐:", len(home['list']))
    if home['list']:
        print("  样例:", home['list'][0])

    print("=" * 72)
    cat = s.categoryContent('2', 1)
    print("分类第1页:", len(cat['list']), "共%s页" % cat['pagecount'])
    cat2 = s.categoryContent('2', 3)
    print("分类第3页:", len(cat2['list']), [i['vod_name'] for i in cat2['list'][:4]])

    print("=" * 72)
    for tid, ext in [('2', {"class": "科幻"}),
                     ('2', {"class": "科幻", "by": "hits"}),
                     ('1', {"area": "大陆", "year": "2025"}),
                     ('20', {"lang": "国语"}),
                     ('3', {"letter": "A"})]:
        c = s.categoryContent(tid, 2, True, ext)
        print("筛选 tid=%-3s %-34s 第2页: %2d 条 共%s页 %s"
              % (tid, str(ext), len(c['list']), c['pagecount'],
                 [i['vod_name'] for i in c['list'][:3]]))

    print("=" * 72)
    vid = (cat['list'] or [{"vod_id": "3791"}])[0]['vod_id']
    det = s.detailContent([vid])['list'][0]
    print("详情:", det['vod_name'], '|', det['vod_year'], det['vod_area'],
          '|', det['vod_remarks'])
    print("类型:", det['type_name'])
    print("封面:", det['vod_pic'])
    print("主演:", det['vod_actor'][:60])
    print("简介:", det['vod_content'][:100])
    print("线路:", det['vod_play_from'])
    print("各线路集数:", [len(x.split('#')) for x in det['vod_play_url'].split('$$$')])

    print("=" * 72)
    sr = s.searchContent('海贼', pg=1)
    print("搜索第1页:", len(sr['list']), "共%s页" % sr['pagecount'],
          [i['vod_name'] for i in sr['list'][:4]])
    print("封面:", (sr['list'] or [{}])[0].get('vod_pic'))
    sr2 = s.searchContent('海贼', pg=2)
    print("搜索第2页:", len(sr2['list']), [i['vod_name'] for i in sr2['list'][:4]])

    print("=" * 72)
    for i, froms in enumerate(det['vod_play_from'].split('$$$')):
        ep = det['vod_play_url'].split('$$$')[i].split('#')[0]
        print("播放[%s] %s -> %s" % (froms, ep.split('$')[0],
                                     s.playerContent(froms, ep.split('$')[-1])))
