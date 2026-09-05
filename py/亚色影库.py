#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
import requests
from urllib.parse import quote, urljoin
try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None
try:
    from base.spider import Spider as BaseSpider
except Exception:
    BaseSpider = object

class Spider(BaseSpider):
    BASE_URL = 'https://www.yasetube.com'
    HEADERS = {'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36','Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8','Accept-Language':'zh-CN,zh;q=0.9,en;q=0.8','Referer':'https://www.yasetube.com/'}
    CATS = {'nvce':'女厕偷拍','fc2-ppv':'FC2 PPV','me':'Mesubuta系列','milf':'MILF人妻无码','dalu':'自拍偷拍','madou':'品牌传媒'}

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def getName(self):
        return '亚色影库'

    def init(self, extend=''):
        return None

    def isVideoFormat(self, url):
        return any(x in url.lower() for x in ['.m3u8','.mp4','.flv','.mkv','.avi','.ts'])

    def manualVideoCheck(self):
        return True

    def destroy(self):
        return None

    def _get(self, url):
        url = url if str(url).startswith('http') else urljoin(self.BASE_URL, url)
        try:
            r = self.session.get(url, timeout=12, verify=False, allow_redirects=True)
            if not r.encoding or r.encoding.lower() == 'iso-8859-1':
                r.encoding = 'utf-8'
            return r.text
        except requests.RequestException:
            return ''

    def _soup(self, html):
        return BeautifulSoup(html, 'html.parser') if BeautifulSoup else None

    def _txt(self, s):
        return re.sub(r'\s+', ' ', s or '').strip()

    def _abs(self, u):
        if not u:
            return ''
        if u.startswith('//'):
            return 'https:' + u
        return urljoin(self.BASE_URL, u)

    def _meta(self, html, name):
        m = re.search(r'<meta[^>]+(?:property|name)=["\']%s["\'][^>]+content=["\']([^"\']+)' % re.escape(name), html, re.I)
        return self._txt(m.group(1)) if m else ''

    def _id(self, url):
        url = self._abs(url).split('?')[0].rstrip('/')
        return url.replace(self.BASE_URL + '/', '')

    def _parse_list(self, html):
        arr = []
        if BeautifulSoup and html:
            soup = self._soup(html)
            for a in soup.select('article.loop-video.thumb-block a[href]'):
                href = self._abs(a.get('href'))
                if '/video/' not in href:
                    continue
                img = a.select_one('img')
                title = self._txt(a.get('title') or (img.get('alt') if img else '') or (a.select_one('header.entry-header span').get_text(' ', strip=True) if a.select_one('header.entry-header span') else ''))
                pic = self._abs((img.get('data-src') or img.get('src') or img.get('data-original')) if img else '')
                remark = self._txt(' '.join([x.get_text(' ', strip=True) for x in a.select('span.hd-video,span.views,span.duration')]))
                if title and href:
                    arr.append({'vod_id':self._id(href),'vod_name':title,'vod_pic':pic,'vod_remarks':remark})
        if not arr:
            for it in re.findall(r'<article[^>]+loop-video[\s\S]*?</article>', html, re.I):
                h = re.search(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*title=["\']([^"\']+)', it, re.I)
                p = re.search(r'<img[^>]+(?:data-src|src)=["\']([^"\']+)', it, re.I)
                if h:
                    arr.append({'vod_id':self._id(h.group(1)),'vod_name':self._txt(h.group(2)),'vod_pic':self._abs(p.group(1)) if p else '','vod_remarks':'HD' if 'hd-video' in it else ''})
        seen, out = set(), []
        for v in arr:
            if v['vod_id'] not in seen:
                seen.add(v['vod_id'])
                out.append(v)
        return out

    def _cats(self):
        html = self._get('/categories')
        classes = []
        if BeautifulSoup and html:
            soup = self._soup(html)
            for a in soup.select('a[href*="/video/category/"]'):
                href = a.get('href') or ''
                slug = href.rstrip('/').split('/')[-1]
                name = self._txt(a.get('title') or a.get_text(' ', strip=True))
                if slug and name and slug not in [x['type_id'] for x in classes]:
                    classes.append({'type_id':slug,'type_name':name})
        if not classes:
            classes = [{'type_id':k,'type_name':v} for k,v in self.CATS.items()]
        return classes[:30]

    def homeContent(self, filter=False):
        return {'class':self._cats(),'filters':{},'list':self.homeVideoContent()['list']}

    def homeVideoContent(self):
        return {'list':self._parse_list(self._get('/'))[:20]}

    def categoryContent(self, tid, pg, filter, ext):
        pg = str(pg or '1')
        if tid in ['latest','home','']:
            url = '/' if pg == '1' else '/page/%s/' % pg
        else:
            url = '/video/category/%s/' % tid if pg == '1' else '/video/category/%s/page/%s/' % (tid, pg)
        return {'page':int(pg),'pagecount':999,'limit':20,'total':999,'list':self._parse_list(self._get(url))}

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) else ids
        url = vid if str(vid).startswith('http') else self.BASE_URL + '/' + str(vid).lstrip('/')
        html = self._get(url)
        name = self._meta(html, 'og:title')
        pic = self._meta(html, 'og:image')
        desc = self._meta(html, 'og:description')
        if BeautifulSoup and html:
            soup = self._soup(html)
            h = soup.select_one('h1.entry-title')
            if h:
                name = self._txt(h.get_text(' ', strip=True)) or name
            im = soup.select_one('meta[itemprop="thumbnailUrl"]')
            if im and im.get('content'):
                pic = im.get('content') or pic
            ds = soup.select_one('meta[itemprop="description"]')
            if ds and ds.get('content'):
                desc = ds.get('content') or desc
        play = self._find_play(html) or url
        vod = {'vod_id':vid,'vod_name':name or str(vid),'vod_pic':self._abs(pic),'type_name':'','vod_year':'','vod_area':'','vod_actor':'','vod_director':'','vod_content':desc or name or '','vod_play_from':'嗅探','vod_play_url':'正片$%s' % play}
        return {'list':[vod]}

    def searchContent(self, key, quick, pg='1'):
        pg = str(pg or '1')
        kw = quote(key)
        url = '/?s=%s' % kw if pg == '1' else '/page/%s/?s=%s' % (pg, kw)
        return {'page':int(pg),'pagecount':999,'limit':20,'total':999,'list':self._parse_list(self._get(url))}

    def playerContent(self, flag, id, vipFlags):
        u = self._abs(id)
        if self.isVideoFormat(u):
            return {'parse':0,'playUrl':'','url':u,'header':self.HEADERS}
        html = self._get(u)
        play = self._find_play(html)
        if play and self.isVideoFormat(play):
            return {'parse':0,'playUrl':'','url':play,'header':self.HEADERS}
        return {'parse':1,'playUrl':'','url':u,'header':self.HEADERS}

    def _find_play(self, html):
        if not html:
            return ''
        pats = [r'<source[^>]+src=["\']([^"\']+)',r'<video[^>]+src=["\']([^"\']+)',r'(https?:\\?/\\?/[^"\'<>]+?\.(?:m3u8|mp4)(?:\?[^"\'<>]*)?)',r'file["\']?\s*[:=]\s*["\']([^"\']+)',r'url["\']?\s*[:=]\s*["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)']
        for p in pats:
            m = re.search(p, html, re.I)
            if m:
                return self._abs(m.group(1).replace('\\/','/'))
        return ''