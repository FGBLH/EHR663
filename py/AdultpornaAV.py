# -*- coding: utf-8 -*-
import re,json,requests
from urllib.parse import quote,urljoin
try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider:
        def __init__(self):
            return None

class Spider(BaseSpider):
    def __init__(self):
        self.host='https://www.adultporna-av107.com'
        self.session=requests.Session()
        self.headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36','Referer':self.host+'/zzzz','Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}
        self.classes=[('每日最新','/topic/'),('国产视频','/t/163/'),('网曝黑料','/t/232/'),('主播大秀','/t/236/'),('AV解说','/t/233/'),('国产自拍','/t/48/'),('抖阴视频','/t/231/'),('国模私拍','/t/45/'),('空姐模特','/t/67/'),('91制片厂','/t/131/'),('糖心VLOG','/t/128/'),('日本有码','/label/sortjp/'),('国产传媒','/label/sortcnseries/'),('番号专区','/label/sortseries/')]

    def init(self,extend=''):
        return None

    def getName(self):
        return 'AdultPorna'

    def isVideoFormat(self,url):
        return str(url).split('?')[0].lower().endswith(('.m3u8','.mp4','.flv','.avi','.mkv','.mov'))

    def manualVideoCheck(self):
        return True

    def destroy(self):
        return None

    def _get(self,url):
        u=url if str(url).startswith('http') else urljoin(self.host,url)
        r=self.session.get(u,headers=self.headers,timeout=15,verify=False)
        r.encoding=r.apparent_encoding or 'utf-8'
        return r.text

    def _url(self,u):
        return urljoin(self.host,u.replace('\\/','/')) if u else ''

    def _txt(self,s):
        return re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',s or '')).strip()

    def _pic(self,s):
        m=re.search(r'<img[^>]+(?:data-original|data-src|data-lazyload|src)=["\']([^"\']+)["\']',s,re.I)
        return self._url(m.group(1)) if m else ''

    def _parse_list(self,html):
        arr=[];seen=set()
        blocks=re.findall(r'<a[^>]+href=["\'](/voddetail/(\d+)/?)["\'][^>]*>.*?</a>',html,re.I|re.S)
        for href,vid in blocks:
            if vid in seen: continue
            i=html.find(href);chunk=html[max(0,i-800):i+2500]
            tm=re.search(r'<a[^>]+href=["\']'+re.escape(href)+r'["\'][^>]*(?:title=["\']([^"\']+)["\'])?',chunk,re.I|re.S)
            am=re.search(r'<img[^>]+alt=["\']([^"\']+)["\']',chunk,re.I)
            name=(tm.group(1) if tm and tm.group(1) else '') or (am.group(1) if am else '') or vid
            sm=re.search(r'<small[^>]*>(.*?)</small>',chunk,re.I|re.S)
            arr.append({'vod_id':vid,'vod_name':self._txt(name),'vod_pic':self._pic(chunk),'vod_remarks':self._txt(sm.group(1)) if sm else ''})
            seen.add(vid)
        return arr

    def homeContent(self,filter=False):
        html=self._get('/zzzz')
        return {'class':[{'type_id':i,'type_name':n} for n,i in self.classes],'list':self._parse_list(html),'filters':{}}

    def homeVideoContent(self):
        return {'list':self._parse_list(self._get('/zzzz'))}

    def categoryContent(self,tid,pg,filter,extend):
        tid=str(tid);pg=str(pg or '1')
        path=tid if tid.startswith('/') else '/t/'+tid.strip('/')+'/'
        if pg!='1': path=path.rstrip('/')+'/page/'+pg+'/'
        html=self._get(path)
        data=self._parse_list(html)
        return {'list':data,'page':int(pg),'pagecount':999 if data else int(pg),'limit':24,'total':999999}

    def detailContent(self,ids):
        vid=str(ids[0]).strip('/').split('/')[-1]
        html=self._get('/voddetail/'+vid+'/')
        name='';pic='';content=''
        for p in [r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',r'<h1[^>]*>(.*?)</h1>',r'title=["\']([^"\']+)["\']']:
            m=re.search(p,html,re.I|re.S)
            if m and self._txt(m.group(1)): name=self._txt(m.group(1));break
        m=re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',html,re.I)
        pic=self._url(m.group(1)) if m else self._pic(html)
        em=re.search(r'(?:剧情|简介|介绍|详情)[^<]*</[^>]+>\s*<[^>]+>(.*?)</',html,re.I|re.S)
        content=self._txt(em.group(1)) if em else name
        plays=[]
        for href in re.findall(r'href=["\'](/v/'+re.escape(vid)+r'/?[^"\']*)["\']',html,re.I):
            if href not in plays: plays.append(href)
        if not plays: plays=['/v/'+vid+'/']
        vod={'vod_id':vid,'vod_name':name or vid,'vod_pic':pic,'type_name':'','vod_year':'','vod_area':'','vod_remarks':'','vod_actor':'','vod_director':'','vod_content':content,'vod_play_from':'播放','vod_play_url':'#'.join(['第%d集$%s'%(i+1,self._url(u)) for i,u in enumerate(plays)])}
        return {'list':[vod]}

    def searchContent(self,key,quick,pg='1'):
        html=self._get('/s/?wd='+quote(str(key)))
        data=self._parse_list(html)
        return {'list':data,'page':int(pg or 1),'pagecount':1,'limit':24,'total':len(data)}

    def playerContent(self,flag,id,vipFlags):
        pid=str(id)
        url=pid if pid.startswith('http') else self._url('/v/'+pid.strip('/').split('/')[-1]+'/')
        if self.isVideoFormat(url): return {'parse':0,'playUrl':'','url':url,'header':self.headers}
        html=self._get(url)
        m=re.search(r'player_aaaa\s*=\s*(\{.*?\})\s*<',html,re.I|re.S) or re.search(r'player_aaaa\s*=\s*(\{.*?\})',html,re.I|re.S)
        play=''
        if m:
            try:
                play=json.loads(m.group(1).replace('\\/','/')).get('url','')
            except json.JSONDecodeError:
                mm=re.search(r'["\']url["\']\s*:\s*["\']([^"\']+)["\']',m.group(1));play=mm.group(1).replace('\\/','/') if mm else ''
        if not play:
            mm=re.search(r'(https?:\\?/\\?/[^"\']+?\.(?:m3u8|mp4)[^"\']*)',html,re.I);play=mm.group(1).replace('\\/','/') if mm else url
        return {'parse':0 if self.isVideoFormat(play) else 1,'playUrl':'','url':play,'header':self.headers}

    def localProxy(self,param):
        return [404,'text/plain','']