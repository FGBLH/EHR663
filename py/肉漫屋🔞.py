# coding=utf-8
# 肉漫屋 (rouman5.com) 漫画T4源

import sys
sys.path.append('..')
from base.spider import BaseSpider
import requests
import re
import html
import hashlib
import base64
import io
from urllib.parse import quote, unquote

HOST = 'https://rouman5.com'
TIMEOUT = 20
PROXY_TYPE = 'rouman5'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,'
              'image/avif,image/webp,image/apng,*/*;q=0.8,'
              'application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}


class Spider(BaseSpider):
    host = HOST
    searchable = True
    filterable = False
    session = requests.Session()
    session.headers.update(HEADERS)

    def getName(self):
        return '肉漫屋'

    def init(self, extend=''):
        pass

    def _fetch_url(self, url, **kwargs):
        try:
            r = self.session.get(url, timeout=TIMEOUT, verify=False, **kwargs)
            r.encoding = r.apparent_encoding or 'utf-8'
            return r.text
        except Exception:
            return ''

    # 列表卡片解析（/books 列表与 /search 搜索结果共用）
    # 卡片结构: <a href="/books/{slug}"> ... <div style="background-image:url(&quot;封面&quot;)"> ... 书名 至: 第X話 ...
    def _parse_book_cards(self, page_html):
        items = []
        seen = set()
        for m in re.finditer(r'<a[^>]*href="(/books/[A-Za-z0-9_\-]+)"', page_html):
            path = m.group(1)
            if path in seen:
                continue
            s = m.start()
            e = page_html.find('</a>', m.end())
            block = page_html[s:e] if e > 0 else page_html[s:s + 1500]
            block = html.unescape(block)  # 还原 &quot; 等 HTML 实体
            bg = re.search(r'background-image\s*:\s*url\(\s*["\']?([^)\'"]+)', block)
            pic = bg.group(1) if bg else ''
            # 书名优先取标题 div (class 含 truncate / line-clamp)，干净无日期噪声
            mt = re.search(r'<div[^>]*class="[^"]*(?:truncate|line-clamp)[^"]*"[^>]*>([^<]+)</div>', block)
            if mt:
                name = mt.group(1).strip()
            else:
                txt = re.sub(r'<[^>]+>', ' ', block)
                txt = re.sub(r'\s+', ' ', txt).strip()
                # 书名位于 "至:" (更新话数提示) 之前
                name = txt.split('至:')[0].strip() if '至:' in txt else txt
            if not name:
                name = path.split('/')[-1]
            seen.add(path)
            items.append({
                'vod_id': path.split('/')[-1],
                'vod_name': name,
                'vod_pic': pic,
                'vod_remarks': '',
            })
        return items

    def homeContent(self, filter):
        # 站点分类由 /books?continued= 的三种状态决定: '' 全部 / false 完结 / true 连载
        classes = [
            {'type_name': '全部', 'type_id': 'all'},
            {'type_name': '完结', 'type_id': 'completed'},
            {'type_name': '连载', 'type_id': 'ongoing'},
        ]
        # 首页推荐墙放 list（漫画源首页由 homeContent 提供，对齐能用的魅色MM）
        try:
            page_html = self._fetch_url('%s/home' % self.host)
            items = self._parse_book_cards(page_html)
        except Exception:
            items = []
        return {'class': classes, 'filters': {}, 'list': items}

    def homeVideoContent(self):
        # 漫画源首页墙由 homeContent 提供，这里返回空（对齐魅色MM，播放器对漫画源 0 参调用）
        return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg) if str(pg).isdigit() else 1
        # 分类映射 continued 参数: 全部='' / 完结='false' / 连载='true'
        continued = {'all': '', 'completed': 'false', 'ongoing': 'true'}.get(tid, '')
        url = '%s/books?continued=%s&page=%d' % (self.host, continued, pg)
        page_html = self._fetch_url(url)
        items = self._parse_book_cards(page_html)
        if not items or len(items) < 24:
            pagecount = pg
        else:
            pagecount = pg + 1
        return {'list': items, 'page': pg, 'pagecount': pagecount,
                'limit': len(items), 'total': len(items)}

    def detailContent(self, ids):
        bid = ids[0] if isinstance(ids, list) else ids
        bid = str(bid).strip()
        m = re.search(r'/books/([A-Za-z0-9_\-]+)', bid)
        if m:
            bid = m.group(1)
        url = '%s/books/%s' % (self.host, bid)
        page_html = self._fetch_url(url)
        if not page_html:
            return {'list': []}
        # 标题: 优先 h1，回退 <title> 去站点后缀
        title = ''
        mh = re.search(r'<h1[^>]*>([^<]+)</h1>', page_html)
        if mh:
            title = mh.group(1).strip()
        else:
            mt = re.search(r'<title>([^<]+)</title>', page_html)
            if mt:
                title = mt.group(1).replace(' - 肉漫屋', '').replace(' | 肉漫屋', '').strip()
        # 封面
        cover = ''
        mc = re.search(r'"image"\s*:\s*"(https?://[^"]+)"', page_html)
        if mc:
            cover = mc.group(1)
        # 章节: /books/{slug}/{index}，index 从 0 起，第 0 话即第 1 话
        chs = sorted(set(int(x) for x in re.findall(
            r'/books/%s/(\d+)' % re.escape(bid), page_html)))
        play_from = '漫画'
        play_url = '#'.join('第%d话$%s/books/%s/%d' % (i + 1, self.host, bid, i)
                            for i in chs)
        return {'list': [{
            'vod_id': bid,
            'vod_name': title,
            'vod_pic': cover,
            'vod_content': '',
            'vod_remarks': '共%d话' % len(chs) if chs else '',
            'vod_play_from': play_from,
            'vod_play_url': play_url,
            'type': 'comic',
        }]}

    def searchContent(self, key, quick, pg=1):
        pg = int(pg) if str(pg).isdigit() else 1
        url = '%s/search?term=%s&page=%d' % (self.host, requests.utils.quote(key), pg)
        page_html = self._fetch_url(url)
        items = self._parse_book_cards(page_html)
        if not items or len(items) < 24:
            pagecount = pg
        else:
            pagecount = pg + 1
        return {'list': items, 'page': pg, 'pagecount': pagecount,
                'limit': len(items), 'total': len(items)}

    # 阅读页 -> 章节图片列表 (pics:// 协议，图片用 && 连接)
    # 阅读页为 Next.js RSC: 每张图是一个组件, 带 {"imageUrl":"...","ind":N}。
    # 文档流顺序可能乱序, 真实顺序由 ind 决定, 故按 ind 重排。
    # 图片被纵向切成 c 条后整条反转打乱 (还原逻辑见官方 JS、参照 jmtt):
    #   c = md5( atob( base64路径去扩展名 ) ).digest()[-1] % 10 + 5
    # CDN 的 sr:1 图即被打乱版本, 还原须在服务端完成, 故每张图经本地代理
    # (localProxy) 下载并按需还原后再返回给播放器。
    def get_proxy_image_url(self, img_url):
        base = self.getProxyUrl()
        if not base:
            base = 'http://127.0.0.1:9978/proxy?do=py'
        return base + '&type=' + PROXY_TYPE + '&url=' + quote(img_url, safe='')

    def playerContent(self, flag, id, vipFlags=None):
        raw = id if id.startswith('http') else self.host + id
        page_html = self._fetch_url(raw)
        if not page_html:
            return {'parse': 0, 'url': '', 'jx': 0}
        # RSC 中引号为转义形式 \" ，先还原再解析 (ind, imageUrl) 配对
        h = page_html.replace('\\"', '"')
        pairs = []
        for m in re.finditer(
                r'"imageUrl"\s*:\s*"(https://r\d\.rmcdn[^\s"]+)"\s*,\s*"ind"\s*:\s*(\d+)', h):
            pairs.append((int(m.group(2)), m.group(1)))
        if not pairs:
            # 兜底: 无 ind 时按文档流顺序直接取图片 (jpg/webp/png)
            imgs = re.findall(r'https://r[0-9]\.rmcdn[^\s"\'<>]+\.(?:webp|jpg|jpeg|png)', page_html)
            seen = []
            for i in imgs:
                if i not in seen:
                    seen.append(i)
            pairs = list(enumerate(seen))
        # 去重 (同一 ind 取首次), 按 ind 升序 -> 真实阅读顺序
        by_ind = {}
        for ind, u in pairs:
            by_ind.setdefault(ind, u)
        ordered = [by_ind[k] for k in sorted(by_ind.keys())]
        if not ordered:
            return {'parse': 0, 'url': '', 'jx': 0}
        # 每张图走本地代理, 由 localProxy 下载并按需还原切片
        proxied = [self.get_proxy_image_url(u) for u in ordered]
        return {'parse': 0, 'url': 'pics://' + '&&'.join(proxied), 'jx': 0}

    # 还原被打乱的图片 (sr:1)。将图纵向切成 c 条后整条反转重排:
    #   dest[l] = source[c-1-l], 首条额外承载余数 h 像素
    # 该变换是官方客户端 canvas.drawImage 逻辑的精确复刻。
    def _descramble(self, data, url):
        from PIL import Image
        im = Image.open(io.BytesIO(data)).convert('RGB')
        W, H = im.size
        # c = md5( atob( base64路径去扩展名 ) ).digest()[-1] % 10 + 5
        seg = url.split('/')[-1].split('.')[0]
        seg += '=' * (-len(seg) % 4)
        s3 = base64.b64decode(seg).decode('latin1')
        c = hashlib.md5(s3.encode('utf-8')).digest()[-1] % 10 + 5
        h = H % c
        p = H // c
        new = Image.new('RGB', (W, H))
        for l in range(c):
            hh = p + (h if l == 0 else 0)
            dy = p * l + (h if l > 0 else 0)
            sy = H - p * (l + 1) - h
            strip = im.crop((0, sy, W, sy + hh))
            new.paste(strip, (0, dy))
        buf = io.BytesIO()
        new.save(buf, 'JPEG', quality=92)
        return buf.getvalue()

    # 本地图片代理: 框架对 pics:// 中的代理 URL 回调此方法
    def localProxy(self, params):
        try:
            if params.get('type') != PROXY_TYPE:
                return [404, 'text/plain', 'not found']
            img_url = params.get('url', '')
            if not img_url:
                return [400, 'text/plain', 'missing url']
            img_url = unquote(img_url)
            r = self.session.get(img_url, headers={
                'User-Agent': HEADERS['User-Agent'],
                'Referer': self.host + '/',
            }, timeout=TIMEOUT, verify=False)
            if r.status_code != 200:
                return [404, 'text/plain', 'image not found']
            data = r.content
            if 'sr:1' in img_url:
                # 切片打乱图: 还原后输出 JPEG
                try:
                    data = self._descramble(data, img_url)
                    mime = 'image/jpeg'
                except Exception:
                    # 还原失败降级: 返回原图, 避免整页空白
                    if data[:2] == b'\xff\xd8':
                        mime = 'image/jpeg'
                    elif data[:4] == b'\x89PNG':
                        mime = 'image/png'
                    elif data[:4] == b'RIFF' and data[8:12] == b'WEBP':
                        mime = 'image/webp'
                    else:
                        mime = 'image/jpeg'
            else:
                if data[:2] == b'\xff\xd8':
                    mime = 'image/jpeg'
                elif data[:4] == b'\x89PNG':
                    mime = 'image/png'
                elif data[:4] == b'RIFF' and data[8:12] == b'WEBP':
                    mime = 'image/webp'
                else:
                    mime = 'image/jpeg'
            return [200, mime, data, {'Content-Length': str(len(data))}]
        except Exception:
            return [500, 'text/plain', 'proxy error']
