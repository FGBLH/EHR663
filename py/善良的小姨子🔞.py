#!/usr/bin/python
# -*- coding: utf-8 -*-
import re,json,requests
from urllib.parse import quote
try:
    from base.spider import Spider
except:
    class Spider: pass
S=requests.Session(); C={}; P={}
S.headers.update({"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"})
try:
    from requests.adapters import HTTPAdapter
    S.mount("http://",HTTPAdapter(pool_connections=10,pool_maxsize=30,max_retries=1)); S.mount("https://",HTTPAdapter(pool_connections=10,pool_maxsize=30,max_retries=1))
except Exception: pass
class Spider(Spider):
    def getName(self): return "妻子的姐姐"
    def init(self,extend=""):
        self.host="https://qzdjj804.qzdjj2.my"
        self.path="/jj"
        self.headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36","Referer":self.host+self.path+"/"}
        self.session=S; self.cache=C; self.play_cache=P; self.session.headers.update(self.headers)
        self.classes=[{"type_id":"6","type_name":"精品推荐"},{"type_id":"7","type_name":"国产精品"},{"type_id":"8","type_name":"主播秀色"},{"type_id":"9","type_name":"日本有码"},{"type_id":"10","type_name":"日本无码"},{"type_id":"11","type_name":"中文字幕"},{"type_id":"22","type_name":"性感人妻"},{"type_id":"23","type_name":"强奸乱伦"},{"type_id":"24","type_name":"欧美情色"},{"type_id":"25","type_name":"三级伦理"},{"type_id":"26","type_name":"卡通动漫"},{"type_id":"41","type_name":"颜值少女"},{"type_id":"42","type_name":"网红主播"},{"type_id":"43","type_name":"女同专属"},{"type_id":"44","type_name":"VR专区"},{"type_id":"45","type_name":"韩国主播"},{"type_id":"46","type_name":"网曝黑料"},{"type_id":"47","type_name":"探花约炮"},{"type_id":"48","type_name":"泄密流出"},{"type_id":"49","type_name":"口爆颜射"},{"type_id":"50","type_name":"制服丝袜"},{"type_id":"51","type_name":"SM另类"},{"type_id":"52","type_name":"AV解说"},{"type_id":"73","type_name":"无码专区"},{"type_id":"74","type_name":"名优女优"},{"type_id":"75","type_name":"中文字幕"},{"type_id":"76","type_name":"变态另类"},{"type_id":"77","type_name":"强奸乱伦"},{"type_id":"78","type_name":"熟人作案"},{"type_id":"79","type_name":"国产盗摄"},{"type_id":"80","type_name":"精品偷拍"},{"type_id":"81","type_name":"成人自拍"},{"type_id":"82","type_name":"欧美精品"},{"type_id":"83","type_name":"熟女人妻"}]
    def _get(self,url):
        if url in self.cache: return self.cache[url]
        r=self.session.get(url,timeout=4,allow_redirects=True); r.encoding="utf-8"; t=r.text; self.cache[url]=t; return t
    def _fix(self,u):
        if not u: return ""
        if u.startswith("//"): return "https:"+u
        if u.startswith("/"): return self.host+u
        return u
    def _pic(self,u):
        u=self._fix((u or "").replace("amp;","")); u=u.replace(":3519/","/"); return re.sub(r"^http://(15260503\.top/)",r"https://\1",u)
    def _clean(self,s): return re.sub(r"<[^>]+>|&nbsp;|\s+"," ",s or "").strip()
    def _safe(self,t): return not re.search("未成年|萝莉|少女|幼女|幼|童颜",t or "")
    def _parse_play(self,url):
        if url in self.play_cache: return self.play_cache[url]
        html=self._get(url); u=""; m=re.search(r"player_(?:aaaa|data)\s*=\s*(\{[\s\S]*?\})",html,re.I)
        if m:
            try: u=json.loads(m.group(1)).get("url","").replace("\\/","/")
            except Exception: u=""
        if not u:
            m=re.search(r"https?://[^'\"<>\\]+\.m3u8[^'\"<>\\]*",html,re.I); u=m.group(0).replace("\\/","/") if m else ""
        if u and ".m3u8" in u: self.play_cache[url]=u
        return u
    def _parse_list(self,html):
        out=[]; seen=set()
        for li in re.findall(r"<li[\s\S]*?</li>",html,re.I):
            m=re.search(r"href=[\"']([^\"']*/voddetail/(\d+)\.html)[\"']",li,re.I)
            if not m or m.group(2) in seen: continue
            title=re.search(r"title=[\"']([^\"']+)[\"']",li,re.I)
            img=re.search(r"<img[\s\S]*?src=[\"']([^\"']+)[\"'][\s\S]*?(?:alt=[\"']([^\"']*)[\"'])?",li,re.I)
            name=self._clean(title.group(1) if title else (img.group(2) if img and len(img.groups())>1 else ""))
            if not name or name=="妻子的姐姐" or not self._safe(name): continue
            pic=self._pic(img.group(1) if img else "")
            p=re.search(r"<p[^>]*>([\s\S]*?)</p>",li,re.I); remark=self._clean(p.group(1)) if p else ""
            seen.add(m.group(2)); out.append({"vod_id":self._fix(m.group(1)),"vod_name":name,"vod_pic":pic,"vod_remarks":remark})
        return out
    def homeContent(self,filter): return {"class":self.classes,"list":self._parse_list(self._get(self.host+self.path+"/vodtype/9.html"))}
    def homeVideoContent(self): return {"list":self._parse_list(self._get(self.host+self.path+"/vodtype/9.html"))}
    def categoryContent(self,tid,pg,filter,extend):
        pg=str(pg or "1"); url=self.host+self.path+f"/vodtype/{tid}.html" if pg=="1" else self.host+self.path+f"/vodtype/{tid}-{pg}.html"
        html=self._get(url); total=999
        m=re.search(r"当前\s*\d+\s*/\s*(\d+)\s*页",html)
        if m: total=int(m.group(1))
        return {"page":int(pg),"pagecount":total,"limit":20,"total":total*20,"list":self._parse_list(html)}
    def detailContent(self,ids):
        url=ids[0]; html=self._get(url); vod={"vod_id":url}
        n=re.search(r"<h1[^>]*>([\s\S]*?)</h1>|<title>([\s\S]*?)-",html,re.I); vod["vod_name"]=self._clean((n.group(1) or n.group(2)) if n else "")
        img=re.search(r"detail-poster[\s\S]*?<img[\s\S]*?src=[\"']([^\"']+)[\"']",html,re.I) or re.search(r"<img[\s\S]*?src=[\"']([^\"']+)[\"'][\s\S]*?alt=[\"']"+re.escape(vod.get("vod_name","")),html,re.I)
        vod["vod_pic"]=self._pic(img.group(1) if img else "")
        vod["type_name"]=self._clean(" ".join(re.findall(r"vodtype/\d+\.html[\s\S]*?>([^<]+)<",html,re.I)))
        desc=re.search(r"剧情介绍[\s\S]*?<p[^>]*>([\s\S]*?)</p>",html,re.I); vod["vod_content"]=self._clean(desc.group(1)) if desc else vod.get("vod_name","")
        tabs=[self._clean(x) for x in re.findall(r"detail-tab[^>]*>[\s\S]*?<span[^>]*>([\s\S]*?)</span>",html,re.I)] or ["播放"]
        play_from=[]; play_url=[]
        lists=re.findall(r"<ul[^>]+detail-play-list[^>]*>([\s\S]*?)</ul>",html,re.I)
        for i,ul in enumerate(lists or [html]):
            eps=[]
            for h,t in re.findall(r"<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>([\s\S]*?)</a>",ul,re.I):
                if "vodplay" in h:
                    pu=self._fix(h); self._parse_play(pu); eps.append(f"{self._clean(t) or '播放'}${pu}")
            if eps: play_from.append(tabs[i] if i<len(tabs) else f"线路{i+1}"); play_url.append("#".join(eps))
        vod["vod_play_from"]="$$$".join(play_from); vod["vod_play_url"]="$$$".join(play_url)
        return {"list":[vod]}
    def searchContent(self,key,quick,pg="1"):
        html=self._get(self.host+self.path+"/vodsearch/"+quote(key)+"----------"+str(pg)+"---.html")
        if not self._parse_list(html): html=self._get(self.host+self.path+"/index.php/vod/search.html?wd="+quote(key)+"&page="+str(pg))
        return {"list":self._parse_list(html)}
    def playerContent(self,flag,id,vipFlags):
        if id in self.play_cache: return {"parse":0,"url":self.play_cache[id]}
        u=self._parse_play(id)
        if u: return {"parse":0,"url":u}
        return {"parse":1,"url":id,"header":json.dumps(self.headers)}