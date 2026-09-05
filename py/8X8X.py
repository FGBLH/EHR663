# -*- coding: utf-8 -*-
# 8x8x官网: https://www.7xb38c.com/

import sys,re,json,base64
from urllib.parse import quote
sys.path.append('..')
try:
    from base.spider import Spider as _Base
except ImportError:
    class _Base:
        def fetch(self,url,headers=None,**kw):
            import requests as rq
            kw.pop('timeout',None);r=rq.get(url,headers=headers,timeout=15,**kw)
            r.encoding='utf-8';return r

try:
    import curl_cffi.requests as cr
    _HAS_CFFI=True
except ImportError:
    _HAS_CFFI=False
    import requests as cr

_H=[104,116,116,112,115,58,47,47,119,119,119,46,51,97,98,102,117,103,57,50,100,46,99,111,109]
H=bytes(_H).decode()
U="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
CATS={1:"大陆",2:"日韩",3:"欧美",4:"动漫",5:"三级"}
TC=None

# ── 动态发现 body path ──
def _discover_body(session):
    """从 SPA 壳中提取 body 路径前缀, 失败返回默认值"""
    try:
        kw={"timeout":10}
        if _HAS_CFFI:kw["impersonate"]="chrome120"
        r=session.get(H+"/",**kw)
        r.raise_for_status()
        js_name=re.search(r'src=/assets/(app\.[a-f0-9]+\.js)',r.text)
        if not js_name:return"/cou345w"
        r2=session.get(H+"/assets/"+js_name.group(1),**kw)
        r2.raise_for_status()
        seg=re.search(r'atob\("([^"]+)"\)',r2.text)
        if not seg:return"/cou345w"
        return"/"+base64.b64decode(seg.group(1)).decode()
    except Exception as e:
        print(f"[8x8x] body discover failed: {e}, using default")
        return"/cou345w"


class Spider(_Base):
    def init(self,extend=""):
        self._s=cr.Session()
        self._s.headers.update({"User-Agent":U,"Accept-Language":"zh-CN,zh;q=0.9"})
        self._s.verify=False
        # ★ 动态发现 body path
        self._bd=_discover_body(self._s)
        print(f"[8x8x] body path: {self._bd}")

    def getName(self):return"8x8x"
    def isVideoFormat(self,u):return".m3u8"in u or".mp4"in u
    def manualVideoCheck(self):return False

    def _get(self,url,timeout=15):
        if not url.startswith("http"):url=H+self._bd+url
        try:
            kw={"timeout":timeout}
            if _HAS_CFFI:kw["impersonate"]="chrome120"
            r=self._s.get(url,**kw);r.raise_for_status()
            if hasattr(r,'encoding'):r.encoding='utf-8'
            return r.text
        except Exception as e:
            print(f"[8x8x]GET {url[:60]} -> {e}")
            return""

    def _tags(self):
        global TC
        if TC is not None:return TC
        h=self._get("/");g={}
        if not h:TC=g;return g
        for gm in re.finditer(r'<div class=tag-group data-group-id=\d+><span class=tag-group-label>([^<]+)</span>(.*?)</div>',h,re.DOTALL):
            gn=gm.group(1);inner=gm.group(2)
            ts=re.findall(r'<a href=(/tags/[^/]+/)\s[^>]*>([^<]+)</a>',inner)
            if ts:g[gn]=ts
        TC=g;return g

    def _cards(self,h):
        v=[]
        for m in re.finditer(r'<a href=(/vd/(\d+)/)\s[^>]*>(.*?)</a>',h,re.DOTALL):
            inner=m.group(3)
            tm=re.search(r'<div class=card-title>(.*?)</div>',inner)
            im=re.search(r'data-src=([^\s>]+)',inner)
            v.append({"vod_id":m.group(1),"vod_name":tm.group(1)if tm else"N/A","vod_pic":im.group(1)if im else"","vod_remarks":""})
        return v

    def homeContent(self,filter=False):
        t=self._tags();cs=[]
        for cid,cn in sorted(CATS.items()):cs.append({"type_id":str(cid),"type_name":cn})
        for gn in sorted(t.keys()):
            for url,name in t[gn]:cs.append({"type_id":url,"type_name":f"[{gn}] {name}"})
        return{"class":cs}

    def homeVideoContent(self):
        h=self._get("/")
        return{"list":self._cards(h)[:30]if h else[]}

    def categoryContent(self,tid,pg=1,filter=False,extend=None):
        try:
            pn=max(int(str(pg)),1)
            base=tid.rstrip("/")if tid.startswith("/tags/")else f"/category/{int(tid)}"
            h=self._get(f"{base}/page/{pn}/")
            if not h:return{"list":[],"page":pg,"pagecount":1}
            mp=re.search(r'data-max=(\d+)',h);pc=int(mp.group(1))if mp else pn
            v=self._cards(h)
            return{"list":v,"page":pn,"pagecount":pc,"limit":len(v),"total":pc*len(v)if v else 0}
        except Exception as e:print(f"[8x8x]cat:{e}");return{"list":[],"page":pg,"pagecount":1}

    def detailContent(self,ids):
        vid=ids[0]
        if not vid.startswith("/vd/"):vid=f"/vd/{vid.strip('/')}/"
        h=self._get(vid)
        if not h:return{"list":[]}
        tm=re.search(r'<title>(.*?)</title>',h);title=tm.group(1).replace(" - 8x8x","")if tm else""
        pm=re.search(r'data-poster=([^\s>]+)',h);pic=pm.group(1).strip('"').strip("'")if pm else""
        mm=re.search(r'data-m3u8=([^\s>]+)',h)
        if not mm:return{"list":[{"vod_id":ids[0],"vod_name":title,"vod_pic":pic}]}
        m3u8_path=mm.group(1).strip('"').strip("'")
        pf=[];pu=[]
        for i,rn in enumerate(["data-route1","data-route2","data-route3"],1):
            rm=re.search(rf'{rn}=([^\s>]+)',h)
            if rm:
                rt=rm.group(1).strip('"').strip("'")
                full_m3u8=rt.rstrip("/")+"/"+m3u8_path.lstrip("/")
                pf.append(f"线路{i}")
                pu.append(f"线路{i}${full_m3u8}")
        return{"list":[{"vod_id":ids[0],"vod_name":title,"vod_pic":pic,"type_name":"","vod_year":"","vod_area":"","vod_remarks":"","vod_actor":"","vod_director":"","vod_content":"","vod_play_from":"$$$".join(pf),"vod_play_url":"$$$".join(pu)}]}

    def playerContent(self,flag,id,vipFlags=None):
        if id and".m3u8"in id:return{"url":id,"header":json.dumps({"User-Agent":U,"Referer":H+"/"})}
        d=self.detailContent([id])
        if d and d.get("list"):
            urls=d["list"][0].get("vod_play_url","").split("$$$")
            if urls:
                first=urls[0]
                if"$"in first:first=first.split("$",1)[1]
                return{"url":first,"header":json.dumps({"User-Agent":U,"Referer":H+"/"})}
        return{"url":""}

    def searchContent(self,key,quick=False,pg=1):
        try:
            pn=max(int(str(pg)),1)
            url=f"{H}/api/search/video?keyword={quote(key)}&page={pn}"
            kw={"timeout":15}
            if _HAS_CFFI:kw["impersonate"]="chrome120"
            r=self._s.get(url,**kw);r.raise_for_status()
            data=r.json()
            if data.get("code")!=0:return{"list":[]}
            dl=data.get("data",{})
            videos=[]
            for item in dl.get("list",[]):
                videos.append({"vod_id":f"/vd/{item['id']}/","vod_name":item.get("title",""),"vod_pic":item.get("litpic",""),"vod_remarks":item.get("typename","")})
            return{"list":videos,"page":pn,"pagecount":dl.get("total_pages",pn),"limit":len(videos),"total":dl.get("total",0)}
        except Exception as e:print(f"[8x8x]search:{e}");return{"list":[],"page":pg,"pagecount":1}

    def localProxy(self,param):pass
