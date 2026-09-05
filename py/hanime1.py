# -*- coding: utf-8 -*-
# 官网: https://hanime1.me

import sys,re,json
from urllib.parse import quote
sys.path.append('..')
try:
    from base.spider import Spider as _B
except ImportError:
    class _B:
        def fetch(self,u,h=None,**k):
            import requests as rq;k.pop('timeout',None)
            r=rq.get(u,headers=h,timeout=15,**k);r.encoding='utf-8';return r

import requests as R
H=bytes([104, 116, 116, 112, 115, 58, 47, 47, 104, 97, 110, 105, 109, 101, 49, 46, 99, 111, 109]).decode()
U="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

class Spider(_B):
    def init(self,e=""):
        self._s=R.Session()
        self._s.headers.update({"User-Agent":U,"Accept-Language":"zh-TW,zh;q=0.9"})

    def getName(self):return"Hanime1"
    def isVideoFormat(self,u):return".mp4"in u
    def manualVideoCheck(self):return False

    def _get(self,u,timeout=15):
        if not u.startswith("http"):u=H+u
        try:
            r=self._s.get(u,timeout=timeout);r.raise_for_status()
            r.encoding='utf-8';return r.text
        except Exception as e:print(f"[H1]{u[:60]}->{e}");return""

    def _cards(self,h):
        v=[]
        for m in re.finditer(
            r'<div title="([^"]*)"[^>]*class="video-item-container[^"]*">'
            r'.*?<a href="([^"]+)"[^>]*class="video-link"'
            r'.*?<img[^>]*src="([^"]+)"',
            h,re.DOTALL):
            vid=re.search(r'v=(\d+)',m.group(2))
            v.append({
                "vod_id":m.group(2) if m.group(2).startswith("http")else H+m.group(2),
                "vod_name":m.group(1),
                "vod_pic":m.group(3),
                "vod_remarks":"",
            })
        return v

    def _tags(self):
        """动态抓取搜索页全部标签"""
        h=self._get(H+"/search")
        tags=re.findall(r'<input name="tags\[\]" type="checkbox" value="([^"]+)"',h)
        return list(dict.fromkeys(tags))  # 去重保序

    def homeContent(self,filter=False):
        cs=[{"type_id":"__all__","type_name":"全部影片"}]
        for t in self._tags():
            cs.append({"type_id":t,"type_name":t})
        return{"class":cs}

    def homeVideoContent(self):
        h=self._get(H)
        return{"list":self._cards(h)}

    def categoryContent(self,tid,pg=1,filter=False,extend=None):
        try:
            pn=max(int(str(pg)),1)
            if tid=="__all__":
                url=f"{H}/search?page={pn}"
            elif tid.startswith("http"):
                url=tid+f"&page={pn}"
            else:
                url=f"{H}/search?tags%5B%5D={quote(tid)}&page={pn}"
            h=self._get(url)
            if not h:return{"list":[],"page":pg,"pagecount":1}
            pages=re.findall(r'page=(\d+)',h)
            pc=max(int(p)for p in pages)if pages else pn
            v=self._cards(h)
            return{"list":v,"page":pn,"pagecount":pc,"limit":len(v),"total":pc*len(v)if v else 0}
        except Exception as e:print(f"[H1]cat:{e}");return{"list":[],"page":pg,"pagecount":1}

    def detailContent(self,ids):
        url=ids[0]if ids[0].startswith("http")else H+ids[0]
        h=self._get(url)
        if not h:return{"list":[]}
        tm=re.search(r'<title>(.*?)</title>',h)
        title=tm.group(1).split("&nbsp;-&nbsp;")[0].strip()if tm else""
        pm=re.search(r'poster="([^"]+)"',h)
        pic=pm.group(1)if pm else""
        sources=re.findall(r'<source src="([^"]+)"[^>]*size="([^"]+)"',h)
        pf=[];pu=[]
        for src,sz in sources:
            pf.append(f"{sz}p")
            pu.append(f"{sz}p${src}")
        if not sources:
            mp4s=re.findall(r'https?://[^\s"<>]+\.mp4[^\s"<>]*',h)
            for i,mp in enumerate(mp4s):
                pf.append(f"线路{i+1}")
                pu.append(f"线路{i+1}${mp}")
        return{"list":[{"vod_id":url,"vod_name":title,"vod_pic":pic,
            "type_name":"","vod_year":"","vod_area":"","vod_remarks":"",
            "vod_actor":"","vod_director":"","vod_content":"",
            "vod_play_from":"$$$".join(pf),"vod_play_url":"$$$".join(pu)}]}

    def playerContent(self,flag,id,vipFlags=None):
        if id and".mp4"in id:
            return{"url":id,"header":json.dumps({"User-Agent":U,"Referer":H+"/"})}
        d=self.detailContent([id])
        if d and d.get("list"):
            us=d["list"][0].get("vod_play_url","").split("$$$")
            if us:
                f=us[0];url=f.split("$",1)[1]if"$"in f else f
                return{"url":url,"header":json.dumps({"User-Agent":U,"Referer":H+"/"})}
        return{"url":""}

    def searchContent(self,key,quick=False,pg=1):
        try:
            pn=max(int(str(pg)),1)
            h=self._get(f"{H}/search?search={quote(key)}&page={pn}")
            if not h:return{"list":[]}
            v=self._cards(h)
            pages=re.findall(r'page=(\d+)',h)
            pc=max(int(p)for p in pages)if pages else pn
            return{"list":v,"page":pn,"pagecount":pc,"limit":len(v),"total":pc*len(v)if v else 0}
        except Exception as e:print(f"[H1]search:{e}");return{"list":[]}

    def localProxy(self,param):pass
