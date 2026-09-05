# coding=utf-8
# !/usr/bin/python
"""
韩剧巴士 影视爬虫
站点: https://www.hanju84.cc/
适配: TVBox / 影视仓 / OK影视 等空壳影视 APP (Python 爬虫接口)

功能: 分类 / 子分类(筛选器) / 分页 / 详情 / 播放 / 搜索 / 封面

URL 规则 (苹果CMS 自定义模板, 12 段):
  /show-{tid}-{area}-{by}-{class}-{lang}-{letter}-{x}-{size}-{page}-{x}-{weekday}-{year}.html
   idx:   0     1      2    3       4      5       6    7      8     9    10        11
  详情:  /v-{vid}.html
  播放:  /p-{vid}-{源序号}-{集序号}.html
  搜索:  /s-{wd}----------{page}---.html   (14 段, wd=idx0, page=idx10)
"""
import sys
import re
import json
import time
import gzip
import zlib
import ssl
import html as html_module
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    BaseSpider = object


class Spider(BaseSpider):
    name = '韩剧巴士'
    host = 'https://www.hanju84.cc'

    # 备用域名, 主域名失效时依次探测
    backup_hosts = [
        'https://www.hanju84.cc',
        'https://hanju84.cc',
        'https://m.hanju84.cc',
    ]

    UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
          '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')

    # ---------------- 父分类 ----------------
    CATEGORIES = [
        {'type_id': '2', 'type_name': '韩剧'},
        {'type_id': '1', 'type_name': '韩国电影'},
        {'type_id': '3', 'type_name': '综艺'},
        {'type_id': '4', 'type_name': '动漫'},
        {'type_id': '20', 'type_name': '理论片'},
        {'type_id': '27', 'type_name': '短剧'},
    ]

    # ---------------- 父分类 -> 子分类(真实 type_id) ----------------
    SUB_TYPES = {
        '2': [('全部', ''), ('韩国剧', '16'), ('国产剧', '12'), ('香港剧', '13'),
              ('日本剧', '15'), ('欧美剧', '17'), ('泰国剧', '19')],
        '1': [('全部', ''), ('剧情片', '10'), ('喜剧片', '6'), ('动作片', '5'),
              ('爱情片', '7'), ('恐怖片', '9'), ('科幻片', '8'),
              ('纪录片', '22'), ('动画片', '33')],
        '3': [('全部', ''), ('日韩综艺', '25'), ('内地综艺', '23'),
              ('港台综艺', '24'), ('欧美综艺', '26')],
        '4': [('全部', ''), ('日韩动漫', '30'), ('国产动漫', '28'), ('欧美动漫', '31')],
        '20': [],
        '27': [],
    }

    # ---------------- 各分类默认剧情标签(内置兜底, init 时会用真实抓取覆盖) ----------------
    DEFAULT_CLASS = {
        '2': ['喜剧', '爱情', '剧情', '奇幻', '悬疑', '惊悚', '犯罪', '家庭', '动作', '古装', '科幻', '恐怖'],
        '1': ['喜剧', '剧情', '爱情', '动作', '科幻', '悬疑', '犯罪', '惊悚', '冒险', '奇幻', '恐怖', '战争', '灾难'],
        '3': ['选秀', '情感', '访谈', '播报', '旅游', '音乐', '美食', '纪实', '曲艺', '生活', '游戏互动', '财经', '求职'],
        '4': ['奇幻', '战斗', '玄幻', '穿越', '科幻', '武侠', '热血', '耽美', '搞笑'],
        '20': ['理论', '动作', '爱情', '喜剧', '恐怖', '科幻', '剧情', '战争', '犯罪'],
        '27': ['重生', '民国', '穿越', '年代', '现代', '言情', '反转', '爽文', '女恋',
               '总裁', '闪婚', '离婚', '都市', '脑洞', '古装', '仙侠'],
    }

    DEFAULT_YEAR = ['2026', '2025', '2024', '2023', '2022', '2021',
                    '2020', '2019', '2018', '2017', '2016']

    AREA_LIST = ['韩国', '中国大陆', '中国香港', '中国台湾', '日本', '美国', '泰国', '英国', '法国', '其它']

    BY_LIST = [('最近更新', 'time'), ('最多播放', 'hits'), ('最好评', 'score')]

    _debug = False
    _filter_cache = {}

    # ==================================================================
    # 基础工具
    # ==================================================================
    def _log(self, msg):
        if self._debug:
            print('[%s] %s' % (self.name, msg))

    def getName(self):
        return self.name

    def init(self, extend=''):
        self._filter_cache = {}
        try:
            self._check_host()
        except Exception as e:
            self._log('域名探测失败: %s' % e)
        try:
            self._load_filters()
        except Exception as e:
            self._log('筛选器抓取失败, 使用内置默认值: %s' % e)
        return self

    def isVideoFormat(self, url):
        if not url:
            return False
        u = url.lower().split('?')[0]
        return any(u.endswith(x) for x in ('.m3u8', '.mp4', '.flv', '.ts', '.mkv', '.avi', '.m4a'))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return

    def _headers(self, referer=None):
        return {
            'User-Agent': self.UA,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Referer': referer or (self.host + '/'),
            'Connection': 'close',
        }

    def _ctx(self):
        """复用同一个 SSLContext, 避免频繁创建导致资源耗尽"""
        ctx = getattr(self, '_ssl_ctx', None)
        if ctx is None:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            self._ssl_ctx = ctx
        return ctx

    def _fetch(self, url, referer=None, retries=2, timeout=20):
        """通用请求, 内置 gzip 解压 / 重试 / 忽略证书"""
        for i in range(retries + 1):
            resp = None
            try:
                req = urllib.request.Request(url, headers=self._headers(referer))
                resp = urllib.request.urlopen(req, timeout=timeout, context=self._ctx())
                body = resp.read()
                enc = (resp.headers.get('Content-Encoding') or '').lower()
                if enc == 'gzip':
                    body = gzip.decompress(body)
                elif enc == 'deflate':
                    try:
                        body = zlib.decompress(body)
                    except Exception:
                        body = zlib.decompress(body, -zlib.MAX_WBITS)
                return body.decode('utf-8', 'replace')
            except Exception as e:
                self._log('请求失败(%d/%d) %s -> %s' % (i + 1, retries + 1, url, e))
                if i < retries:
                    time.sleep(0.6)
            finally:
                if resp is not None:
                    try:
                        resp.close()
                    except Exception:
                        pass
        return ''

    def _check_host(self):
        """主域名不可用时自动切换备用域名, 顺便缓存首页 HTML"""
        for h in self.backup_hosts:
            html = self._fetch(h + '/', referer=h + '/', retries=0, timeout=10)
            if html and '韩剧' in html:
                self.host = h.rstrip('/')
                self._home_html = html
                self._home_time = time.time()
                self._log('当前域名: %s' % self.host)
                return
        self._log('全部域名探测失败, 保持默认: %s' % self.host)

    def _get_home(self):
        """首页 HTML 缓存 60 秒, 避免 init 与 homeContent 重复请求"""
        if getattr(self, '_home_html', '') and time.time() - getattr(self, '_home_time', 0) < 60:
            return self._home_html
        html = self._fetch(self.host + '/')
        if html:
            self._home_html = html
            self._home_time = time.time()
        return html

    @staticmethod
    def _clean(text):
        if not text:
            return ''
        text = html_module.unescape(str(text))
        text = re.sub(r'<[^>]+>', ' ', text)
        return re.sub(r'\s+', ' ', text).strip()

    def _fix_url(self, url):
        if not url:
            return ''
        url = url.strip()
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('/'):
            return self.host + url
        if not url.startswith('http'):
            return self.host + '/' + url
        return url

    # ==================================================================
    # URL 构造
    # ==================================================================
    def _show_url(self, tid, area='', by='', cls='', year='', page=1):
        """构造 12 段筛选 URL"""
        f = [''] * 12
        f[0] = str(tid)
        f[1] = urllib.parse.quote(area) if area else ''
        f[2] = by or ''
        f[3] = urllib.parse.quote(cls) if cls else ''
        f[8] = str(page) if page and int(page) > 1 else ''
        f[11] = year or ''
        return '%s/show-%s.html' % (self.host, '-'.join(f))

    def _search_url(self, wd, page=1):
        """构造 14 段搜索 URL, wd=idx0, page=idx10"""
        f = [''] * 14
        f[0] = urllib.parse.quote(wd)
        f[10] = str(page) if page and int(page) > 1 else ''
        return '%s/s-%s.html' % (self.host, '-'.join(f))

    # ==================================================================
    # 筛选器 (子分类) 抓取
    # ==================================================================
    def _parse_filter_values(self, html, tid):
        """从分类页解析 剧情标签 / 年份"""
        cls = [urllib.parse.unquote(x) for x in
               re.findall(r'href="/show-%s---([^-"]*?)--------\.html"' % re.escape(str(tid)), html) if x]
        years = [urllib.parse.unquote(x) for x in
                 re.findall(r'href="/show-%s-----------([^-"]+)\.html"' % re.escape(str(tid)), html) if x]
        # 去重保序
        cls = list(dict.fromkeys(cls))
        years = list(dict.fromkeys(years))
        return cls, years

    def _load_filters(self):
        """并发抓取每个父分类页面, 提取真实子分类(筛选器)值"""
        def work(cat):
            tid = cat['type_id']
            try:
                html = self._fetch(self._show_url(tid), retries=1, timeout=12)
                if not html:
                    return tid, None
                return tid, self._parse_filter_values(html, tid)
            except Exception:
                return tid, None

        results = {}
        try:
            with ThreadPoolExecutor(max_workers=6) as ex:
                for tid, val in ex.map(work, self.CATEGORIES):
                    if val and val[0]:
                        results[tid] = val
        except Exception:
            for cat in self.CATEGORIES:
                tid, val = work(cat)
                if val and val[0]:
                    results[tid] = val
        self._filter_cache = results
        self._log('筛选器抓取完成: %s' % list(results.keys()))

    def _build_filters(self):
        filters = {}
        for cat in self.CATEGORIES:
            tid = cat['type_id']
            cached = self._filter_cache.get(tid)
            cls_vals = cached[0] if cached and cached[0] else self.DEFAULT_CLASS.get(tid, [])
            year_vals = cached[1] if cached and cached[1] else self.DEFAULT_YEAR

            items = []

            # 1) 子分类 (真实二级 type_id)
            subs = self.SUB_TYPES.get(tid) or []
            if subs:
                items.append({
                    'key': 'tid',
                    'name': '子分类',
                    'value': [{'n': n, 'v': v} for n, v in subs],
                })

            # 2) 剧情标签
            if cls_vals:
                items.append({
                    'key': 'class',
                    'name': '剧情',
                    'value': [{'n': '全部', 'v': ''}] + [{'n': c, 'v': c} for c in cls_vals],
                })

            # 3) 地区
            items.append({
                'key': 'area',
                'name': '地区',
                'value': [{'n': '全部', 'v': ''}] + [{'n': a, 'v': a} for a in self.AREA_LIST],
            })

            # 4) 年份
            items.append({
                'key': 'year',
                'name': '年份',
                'value': [{'n': '全部', 'v': ''}] + [{'n': y, 'v': y} for y in year_vals],
            })

            # 5) 排序
            items.append({
                'key': 'by',
                'name': '排序',
                'value': [{'n': '默认', 'v': ''}] + [{'n': n, 'v': v} for n, v in self.BY_LIST],
            })

            filters[tid] = items
        return filters

    # ==================================================================
    # 列表解析
    # ==================================================================
    def _parse_list(self, html):
        """以 cover_box 为锚点分块解析, 兼容标签属性内换行"""
        vods = []
        if not html:
            return vods
        seen = set()

        for blk in re.findall(r'<div[^>]*class="[^"]*cover_box[^"]*"[^>]*>([\s\S]{0,900}?)</h6>', html):
            m = re.search(r'href="/v-(\d+)\.html"', blk)
            if not m:
                continue
            vid = m.group(1)
            if vid in seen:
                continue
            tm = re.search(r'class="[^"]*title[^"]*"[^>]*>([\s\S]*?)</a>', blk)
            name = self._clean(tm.group(1)) if tm else ''
            if not name:
                continue
            pm = (re.search(r'data-bg=["\']([^"\']+)["\']', blk)
                  or re.search(r'data-original=["\']([^"\']+)["\']', blk)
                  or re.search(r'data-src=["\']([^"\']+)["\']', blk)
                  or re.search(r'<img[^>]+src=["\']([^"\']+)["\']', blk))
            rm = re.search(r'class="[^"]*label[^"]*"[^>]*>([\s\S]*?)</span>', blk)
            seen.add(vid)
            vods.append({
                'vod_id': vid,
                'vod_name': name,
                'vod_pic': self._fix_url(pm.group(1) if pm else ''),
                'vod_remarks': self._clean(rm.group(1) if rm else ''),
            })
        if vods:
            return vods

        # 兜底: 全局宽松匹配
        for vid, title in re.findall(
                r'<a[^>]*class="[^"]*title[^"]*"[^>]*href="/v-(\d+)\.html"[^>]*>([\s\S]*?)</a>', html):
            if vid in seen:
                continue
            seen.add(vid)
            pm = re.search(r'href="/v-%s\.html"[^>]*?data-bg=["\']([^"\']+)["\']' % vid, html)
            vods.append({
                'vod_id': vid,
                'vod_name': self._clean(title),
                'vod_pic': self._fix_url(pm.group(1) if pm else ''),
                'vod_remarks': '',
            })
        return vods

    @staticmethod
    def _parse_pagecount(html, cur_page=1):
        if not html:
            return cur_page
        total = cur_page
        m = re.search(r'href="/type-\d+-(\d+)\.html">\s*尾页', html)
        if m:
            return max(int(m.group(1)), cur_page)
        m = re.search(r'href="/s-[^"]*?-(\d+)---\.html">\s*尾页', html)
        if m:
            return max(int(m.group(1)), cur_page)
        for n in re.findall(r'href="/type-\d+-(\d+)\.html"', html):
            total = max(total, int(n))
        for n in re.findall(r'href="/s-[^"]*?-(\d+)---\.html"', html):
            total = max(total, int(n))
        return total

    # ==================================================================
    # 首页
    # ==================================================================
    def homeContent(self, filter=True):
        try:
            if not self._filter_cache:
                try:
                    self._load_filters()
                except Exception:
                    pass
            vods = self._parse_list(self._get_home())
            return {
                'class': self.CATEGORIES,
                'filters': self._build_filters(),
                'list': vods,
                'parse': 0,
                'jx': 0,
            }
        except Exception as e:
            self._log('homeContent 异常: %s' % e)
            return {'class': self.CATEGORIES, 'filters': self._build_filters(), 'list': []}

    def homeVideoContent(self):
        try:
            return {'list': self._parse_list(self._get_home())}
        except Exception:
            return {'list': []}

    # ==================================================================
    # 分类 / 筛选 / 分页
    # ==================================================================
    def categoryContent(self, tid, pg, filter=True, extend=None):
        try:
            page = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1
            if isinstance(extend, str):
                try:
                    extend = json.loads(extend) if extend else {}
                except Exception:
                    extend = {}
            extend = extend or {}

            real_tid = str(extend.get('tid') or '').strip() or str(tid)
            cls = str(extend.get('class') or '').strip()
            area = str(extend.get('area') or '').strip()
            year = str(extend.get('year') or '').strip()
            by = str(extend.get('by') or '').strip()

            url = self._show_url(real_tid, area=area, by=by, cls=cls, year=year, page=page)
            self._log('分类请求: %s' % url)
            html = self._fetch(url)
            vods = self._parse_list(html)
            pagecount = self._parse_pagecount(html, page)
            if not vods and page > 1:
                pagecount = page

            return {
                'list': vods,
                'page': page,
                'pagecount': pagecount,
                'limit': len(vods) or 36,
                'total': pagecount * (len(vods) or 36),
            }
        except Exception as e:
            self._log('categoryContent 异常: %s' % e)
            return {'list': [], 'page': 1, 'pagecount': 1, 'limit': 36, 'total': 0}

    # ==================================================================
    # 详情
    # ==================================================================
    def detailContent(self, ids):
        try:
            vid = str(ids[0] if isinstance(ids, (list, tuple)) else ids)
            vid = re.sub(r'\D', '', vid) or vid
            url = '%s/v-%s.html' % (self.host, vid)
            html = self._fetch(url)
            if not html:
                return {'list': []}

            # 标题
            name = ''
            m = re.search(r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>\s*<a[^>]*>([\s\S]*?)</a>', html)
            if m:
                name = self._clean(m.group(1))
            if not name:
                m = re.search(r'<title>(.*?)</title>', html, re.S)
                if m:
                    name = self._clean(m.group(1)).split('_')[0].split('-')[0].strip()

            # 封面
            pic = ''
            m = re.search(r'<img[^>]+src="([^"]+)"[^>]*class="[^"]*cover[^"]*"', html)
            if not m:
                m = re.search(r'<img[^>]*class="[^"]*cover[^"]*"[^>]+src="([^"]+)"', html)
            if m:
                pic = self._fix_url(m.group(1))

            # 更新状态 / 评分
            remarks = ''
            m = re.search(r'class="[^"]*rating[^"]*"[^>]*>([\s\S]*?)</span>[\s\S]{0,60}?'
                          r'class="[^"]*label[^"]*"[^>]*>([\s\S]*?)</span>', html)
            if m:
                remarks = self._clean(m.group(2))
            else:
                m = re.search(r'class="[^"]*label[^"]*"[^>]*>([\s\S]*?)</span>', html)
                if m:
                    remarks = self._clean(m.group(1))

            # 概要行: 韩国 · 2026 · 韩国 | 导演:xx | 主演:xx
            area = year = ''
            m = re.search(r'<p[^>]*id="see_more"[^>]*>([\s\S]*?)</p>', html)
            if m:
                info = self._clean(re.sub(r'<span[^>]*class="[^"]*see_more[^"]*"[^>]*>[\s\S]*?</span>',
                                          '', m.group(1)))
                head = info.split('|')[0]
                parts = [p.strip() for p in head.split('·') if p.strip()]
                if parts:
                    area = parts[0]
                for p in parts:
                    if re.fullmatch(r'(19|20)\d{2}', p):
                        year = p
                        break

            # 详细信息块
            def pick(label):
                mm = re.search(r'class="[^"]*item[^"]*"[^>]*>\s*%s\s*[：:]\s*</span>([\s\S]*?)</p>'
                               % label, html)
                return self._clean(mm.group(1)).replace('\xa0', ' ').strip() if mm else ''

            director = pick('导演')
            actor = pick('主演')
            writer = pick('编剧')
            alias = pick('又名')
            content = pick('剧情')
            # 站点部分条目简介被过滤成只剩标点, 判定为无效
            if content in ('暂无简介，敬请期待', '') or \
                    len(re.findall(r'[\u4e00-\u9fa5\uac00-\ud7a3a-zA-Z0-9]', content)) < 6:
                content = ''
            extra = []
            if alias:
                extra.append('又名: %s' % alias)
            if writer and writer != '未知':
                extra.append('编剧: %s' % writer)
            if extra:
                content = ('　'.join(extra) + ('\n' + content if content else ''))

            # 分类名
            type_name = ''
            m = re.search(r'<li[^>]*class="current"[^>]*>\s*<a[^>]*href="/show-\d+-[^"]*"[^>]*>([\s\S]*?)</a>',
                          html)
            if m:
                type_name = self._clean(m.group(1))

            # 播放源名称
            sources = []
            m = re.search(r'<ul[^>]*class="[^"]*play_from[^"]*"[^>]*>([\s\S]*?)</ul>', html)
            if m:
                for li in re.findall(r'<li[^>]*>([\s\S]*?)</li>', m.group(1)):
                    nm = self._clean(re.sub(r'<span[^>]*class="[^"]*badge[^"]*"[^>]*>[\s\S]*?</span>', '', li))
                    sources.append(nm or '线路')

            # 播放列表
            play_from, play_url = [], []
            blocks = re.findall(r'<ul[^>]*class="[^"]*play_list[^"]*"[^>]*>([\s\S]*?)</ul>', html)
            for i, blk in enumerate(blocks):
                eps = re.findall(r'href="(/p-[\d\-]+\.html)"[^>]*>([^<]*)</a>', blk)
                if not eps:
                    eps = [(h, t) for t, h in re.findall(r'title="([^"]*)"\s+href="(/p-[\d\-]+\.html)"', blk)]
                items = []
                for href, txt in eps:
                    txt = self._clean(txt) or '播放'
                    txt = txt.replace('$', ' ').replace('#', ' ')
                    items.append('%s$%s' % (txt, href))
                if items:
                    play_from.append(sources[i] if i < len(sources) else ('线路%d' % (i + 1)))
                    play_url.append('#'.join(items))

            if not play_from:
                play_from = ['默认']
                play_url = ['正片$/p-%s-1-1.html' % vid]

            vod = {
                'vod_id': vid,
                'vod_name': name or '未知',
                'vod_pic': pic,
                'type_name': type_name,
                'vod_year': year,
                'vod_area': area,
                'vod_remarks': remarks,
                'vod_actor': actor or '未知',
                'vod_director': director or '未知',
                'vod_content': content or '暂无简介',
                'vod_play_from': '$$$'.join(play_from),
                'vod_play_url': '$$$'.join(play_url),
            }
            return {'list': [vod]}
        except Exception as e:
            self._log('detailContent 异常: %s' % e)
            return {'list': []}

    # ==================================================================
    # 播放
    # ==================================================================
    def playerContent(self, flag, id, vipFlags=None):
        play_header = {'User-Agent': self.UA, 'Referer': self.host + '/'}
        try:
            path = str(id or '')
            page_url = self._fix_url(path)
            html = self._fetch(page_url, referer=self.host + '/')

            real = ''
            # 1) iframe: /addons/dplayer/?url=xxx.m3u8
            m = re.search(r'<iframe[^>]+src="([^"]+)"', html)
            if m:
                src = html_module.unescape(m.group(1))
                q = re.search(r'[?&]url=([^&"\']+)', src)
                if q:
                    real = urllib.parse.unquote(q.group(1))
                elif self.isVideoFormat(src):
                    real = src
                else:
                    real = self._fix_url(src)

            # 2) player_data / player_aaaa
            if not real or not real.startswith('http'):
                m = re.search(r'var\s+player_\w+\s*=\s*(\{[\s\S]*?\})\s*[;<]', html)
                if m:
                    try:
                        data = json.loads(m.group(1))
                        u = data.get('url', '')
                        enc = data.get('encrypt', 0)
                        if enc == 1:
                            u = urllib.parse.unquote(u)
                        elif enc == 2:
                            import base64
                            u = urllib.parse.unquote(base64.b64decode(u).decode('utf-8', 'replace'))
                        if u:
                            real = u
                    except Exception:
                        pass

            # 3) 兜底: 页面里直接找 m3u8 / mp4
            if not real:
                m = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
                if not m:
                    m = re.search(r'(https?://[^\s"\'<>]+\.(?:mp4|flv|ts))', html)
                if m:
                    real = m.group(1)

            if not real:
                return {'parse': 1, 'playUrl': '', 'url': page_url,
                        'header': json.dumps(play_header), 'jx': 0}

            real = self._fix_url(real)
            parse = 0 if self.isVideoFormat(real) else 1
            return {'parse': parse, 'playUrl': '', 'url': real,
                    'header': json.dumps(play_header), 'jx': 0}
        except Exception as e:
            self._log('playerContent 异常: %s' % e)
            return {'parse': 1, 'playUrl': '', 'url': self._fix_url(str(id)),
                    'header': json.dumps(play_header), 'jx': 0}

    # ==================================================================
    # 搜索
    # ==================================================================
    def searchContent(self, key, quick=False, pg='1'):
        try:
            page = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1
            url = self._search_url(key, page)
            html = self._fetch(url)
            if not html and page == 1:
                html = self._fetch('%s/s--------------.html?wd=%s' % (self.host, urllib.parse.quote(key)))
            vods = self._parse_list(html)
            pagecount = self._parse_pagecount(html, page)
            return {
                'list': vods,
                'page': page,
                'pagecount': pagecount,
                'limit': len(vods) or 16,
                'total': pagecount * (len(vods) or 16),
            }
        except Exception as e:
            self._log('searchContent 异常: %s' % e)
            return {'list': [], 'page': 1, 'pagecount': 1, 'limit': 16, 'total': 0}

    def searchContentPage(self, key, quick=False, pg='1'):
        return self.searchContent(key, quick, pg)

    # ==================================================================
    # 本地代理 (封面兜底)
    # ==================================================================
    def localProxy(self, param):
        try:
            if not param:
                return None
            url = param.get('url') if isinstance(param, dict) else param
            if not url or not str(url).startswith('http'):
                return None
            req = urllib.request.Request(url, headers=self._headers())
            with urllib.request.urlopen(req, timeout=15, context=self._ctx()) as r:
                return [200, r.headers.get('Content-Type', 'application/octet-stream'), r.read()]
        except Exception:
            return None


# ======================================================================
# 本地自测
# ======================================================================
if __name__ == '__main__':
    import io
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

    sp = Spider()
    sp._debug = True
    sp.init()

    print('\n================ 1. 首页 & 分类 ================')
    home = sp.homeContent(True)
    print('域名:', sp.host)
    print('父分类:', ' | '.join('%s(%s)' % (c['type_name'], c['type_id']) for c in home['class']))
    print('首页推荐: %d 条' % len(home['list']))
    for v in home['list'][:3]:
        print('   %-20s id=%-8s 备注=%-10s 封面=%s' %
              (v['vod_name'], v['vod_id'], v['vod_remarks'], v['vod_pic'][:60]))

    print('\n================ 2. 子分类(筛选器) ================')
    for tid, fs in home['filters'].items():
        nm = next(c['type_name'] for c in home['class'] if c['type_id'] == tid)
        print('【%s】' % nm)
        for f in fs:
            vals = '/'.join(x['n'] for x in f['value'][:14])
            print('   %-5s %-4s: %s%s' % (f['key'], f['name'], vals,
                                          ' ...' if len(f['value']) > 14 else ''))

    print('\n================ 3. 分类分页 ================')
    r = sp.categoryContent('2', '1')
    print('韩剧 P1: %d 条, 共 %d 页' % (len(r['list']), r['pagecount']))
    print('   ', [v['vod_name'] for v in r['list'][:4]])
    r2 = sp.categoryContent('2', '2')
    print('韩剧 P2: %d 条' % len(r2['list']), [v['vod_name'] for v in r2['list'][:4]])

    print('\n================ 4. 子分类 + 组合筛选 ================')
    r3 = sp.categoryContent('2', '1', True, {'tid': '16', 'class': '爱情'})
    print('韩剧>韩国剧+爱情: %d 条, 共 %d 页' % (len(r3['list']), r3['pagecount']),
          [v['vod_name'] for v in r3['list'][:3]])
    r4 = sp.categoryContent('1', '1', True, {'tid': '5', 'year': '2024'})
    print('电影>动作片+2024: %d 条, 共 %d 页' % (len(r4['list']), r4['pagecount']),
          [v['vod_name'] for v in r4['list'][:3]])
    r5 = sp.categoryContent('2', '1', True, {'by': 'hits', 'year': '2025'})
    print('韩剧+最多播放+2025: %d 条' % len(r5['list']), [v['vod_name'] for v in r5['list'][:3]])

    print('\n================ 5. 详情 ================')
    vid = r['list'][0]['vod_id']
    d = sp.detailContent([vid])
    v = d['list'][0]
    for k in ('vod_name', 'vod_year', 'vod_area', 'vod_remarks', 'vod_actor',
              'vod_director', 'type_name'):
        print('   %-14s %s' % (k, v[k]))
    print('   %-14s %s' % ('vod_pic', v['vod_pic']))
    print('   %-14s %s' % ('vod_content', v['vod_content'][:80]))
    print('   %-14s %s' % ('vod_play_from', v['vod_play_from']))
    print('   %-14s %s' % ('首源前3集', v['vod_play_url'].split('$$$')[0].split('#')[:3]))

    print('\n================ 6. 播放 ================')
    ep = v['vod_play_url'].split('$$$')[0].split('#')[0].split('$')[-1]
    p = sp.playerContent(v['vod_play_from'].split('$$$')[0], ep)
    print('   parse=%s' % p['parse'])
    print('   url  =%s' % p['url'])

    print('\n================ 7. 搜索 ================')
    s = sp.searchContent('爱情', False, '1')
    print('第1页: %d 条, 共 %d 页' % (len(s['list']), s['pagecount']))
    for x in s['list'][:4]:
        print('   %-20s id=%-8s %s' % (x['vod_name'], x['vod_id'], x['vod_pic'][:55]))
    s2 = sp.searchContent('爱情', False, '2')
    print('第2页: %d 条' % len(s2['list']), [x['vod_name'] for x in s2['list'][:3]])

    print('\n完成 ✅')
