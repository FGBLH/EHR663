# -*- coding: utf-8 -*-
"""
juok3.top (剧OK) 爬虫
- 首页: /api/filter API 获取推荐
- 分类: /api/filter?catId= /type= API
- 详情: /api/detail?cat=&id= API
- 搜索: /api/search?q=关键词
- 播放: 官源链接 + 解析线路, 需要WebView解析
"""
import sys
import re
import json
from urllib.parse import urljoin, quote

sys.path.append('..')
try:
    from base.spider import Spider
except ImportError:
    class Spider:
        def fetch(self, url, headers=None, **kw):
            import requests as rq
            kw.pop('timeout', None)
            r = rq.get(url, headers=headers, timeout=15, **kw)
            r.encoding = 'utf-8'
            return r

def _(x): return x

HOST = "https://juok3.top"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# 分类映射: type_id -> (catId, type参数, 中文名)
CLASS_MAP = {
    "movie":   (1, None, "电影"),
    "tv":      (2, None, "电视剧"),
    "variety": (3, None, "综艺"),
    "anime":   (4, None, "动漫"),
    "short":   (2, "短剧", "短剧"),  # type=短剧, cat用2
}

# 外部解析线路 (拼接URL) - 从 mojiez.net 提取的38个解析接口
PARSE_APIS = [
    {"name": "默认接口", "url": "https://jx.xmflv.com/?url="},
    {"name": "789解析1", "url": "https://jiexi.789jiexi.icu:4433/?url="},
    {"name": "789解析2", "url": "https://jiexi.789jiexi.com/?url="},
    {"name": "我看VIP", "url": "https://a.wkvip.net/?url="},
    {"name": "8090", "url": "https://www.8090g.cn/?url="},
    {"name": "极速解析", "url": "https://jx.2s0.cn/player/?url="},
    {"name": "super", "url": "https://super.playr.top/?url="},
    {"name": "fongmi", "url": "https://json.fongmi.cc/web?url="},
    {"name": "8090备用", "url": "https://www.8090g.cn/jiexi/?url="},
    {"name": "M3U8解析", "url": "https://jx.m3u8.tv/jx/jx.php?url="},
    {"name": "Jn1解析", "url": "https://yparse.jn1.cc/index.php?url="},
    {"name": "CK解析", "url": "https://www.ckplayer.vip/jiexi/?url="},
    {"name": "Player-JY", "url": "https://jx.playerjy.com/?url="},
    {"name": "HLS解析", "url": "https://jx.hls.one/?url="},
    {"name": "冰豆解析", "url": "https://bd.jx.cn/?url="},
    {"name": "剖元解析", "url": "https://www.pouyun.com/?url="},
    {"name": "973解析", "url": "https://jx.973973.xyz/?url="},
    {"name": "七哥解析", "url": "https://jx.nnxv.cn/tv.php?url="},
    {"name": "PlayM3U8", "url": "https://www.playm3u8.cn/jiexi.php?url="},
    {"name": "937解析", "url": "https://bfq.937auth.vip?url="},
    {"name": "芒果TV专线", "url": "https://video.isyour.love/player/getplayer?url="},
    {"name": "M1907", "url": "https://im1907.top/?jx="},
    {"name": "夜幕解析", "url": "https://www.yemu.xyz/?url="},
    {"name": "盘古解析", "url": "https://www.pangujiexi.com/jiexi/?url="},
    {"name": "Yparse", "url": "https://jx.yparse.com/index.php?url="},
    {"name": "搜影片名称", "url": "https://z1.m1907.top/?jx="},
    {"name": "超清VIP", "url": "https://jx.xmflv.cc/?url="},
    {"name": "vip视频解析1", "url": "https://www.8090.la/8090/?url="},
    {"name": "vip接口2", "url": "http://jiexi44.qmbo.cn/jiexi/?url="},
    {"name": "vip视频解析3", "url": "https://jx.parwix.com:4433/player/?url="},
    {"name": "全能VIP解析", "url": "http://api.apii.top/?v="},
    {"name": "备用线路1", "url": "https://svip.bljiex.cc/?v="},
    {"name": "备用线路2", "url": "https://yparse.ik9.cc/index.php?url="},
    {"name": "爱豆", "url": "https://jx.aidouer.net/?url="},
    {"name": "YT", "url": "https://jx.yangtu.top/?url="},
    {"name": "qianqi", "url": "https://api.qianqi.net/vip/?url="},
    {"name": "花旗解析", "url": "https://www.huaqi.live/?url="},
]

# 平台名称映射
PLATFORM_NAMES = {
    "qiyi": "爱奇艺", "iqiyi": "爱奇艺",
    "imgo": "芒果TV", "mgtv": "芒果TV",
    "qq": "腾讯视频", "v.qq": "腾讯视频",
    "youku": "优酷",
    "leshi": "乐视", "le": "乐视",
    "sohu": "搜狐",
    "bilibili": "B站",
    "1905": "1905",
    "pptv": "PPTV",
    "xigua": "西瓜视频",
    "douyin": "抖音",
    "kuaishou": "快手",
}

# 搜索缓存: 用于保存苹果CMS搜索结果的播放信息
_search_cache = {}


class Spider(Spider):

    def init(self, extend=""):
        self._load_config()

    def _load_config(self):
        """从 /api/config 加载解析线路等配置 (已禁用, 使用固定配置)"""
        pass

    def getName(self):
        return "juok3"

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url or ".flv" in url

    def manualVideoCheck(self):
        return True

    def _cover(self, raw):
        """统一封面URL"""
        if not raw:
            return ""
        if raw.startswith("//"):
            return "https:" + raw
        return raw

    def _year(self, pubdate):
        """从pubdate提取年份"""
        if pubdate and len(pubdate) >= 4:
            return pubdate[:4]
        return ""

    def _build_filter_url(self, tid, pg=1):
        """构建分类API URL"""
        info = CLASS_MAP.get(tid)
        if not info:
            return None
        cat_id, type_name, _ = info
        params = []
        if cat_id is not None:
            params.append(f"catId={cat_id}")
        if type_name:
            params.append(f"type={quote(type_name)}")
        params.append(f"page={pg}")
        params.append("size=24")
        return f"{HOST}/api/filter?{'&'.join(params)}"

    def _items_from_filter(self, data, cat_id=None):
        """从 /api/filter 返回的JSON中提取影片列表"""
        items = []
        movies = data.get("movies", [])
        for m in movies:
            vid = f"detail:{cat_id or 2}:{m.get('id', '')}"
            cover = self._cover(m.get("cdncover") or m.get("cover", ""))
            # 构建备注信息
            remarks = ""
            if m.get("upinfo"):
                remarks = str(m["upinfo"])
            elif m.get("total"):
                remarks = f"{m['total']}集"
            # 电影等没有upinfo时, 用年份+地区
            if not remarks:
                year = self._year(m.get("pubdate", ""))
                area = ""
                if m.get("area"):
                    if isinstance(m["area"], list) and m["area"]:
                        area = m["area"][0]
                    else:
                        area = str(m["area"])
                parts = [p for p in [year, area] if p]
                if parts:
                    remarks = " ".join(parts)
            items.append({
                "vod_id": vid,
                "vod_name": m.get("title", "").strip(),
                "vod_pic": cover,
                "vod_remarks": remarks,
                "vod_year": self._year(m.get("pubdate", "")),
            })
        return items

    def _extract_items_from_search_api(self, data):
        """从搜索API返回的JSON中提取影片列表"""
        global _search_cache
        items = []
        results = data.get("results", [])
        for item in results:
            if "vod_name" in item:
                # 苹果CMS格式 (外部源)
                vod_id = str(item.get("vod_id", ""))
                if not vod_id:
                    continue
                source_key = item.get("sourceKey", "")
                vid = f"search:{vod_id}:{source_key}"
                pic = item.get("vod_pic", "")
                if pic and pic.startswith("//"):
                    pic = "https:" + pic
                # 缓存播放信息用于详情页
                _search_cache[vid] = {
                    "vod_name": item.get("vod_name", "").strip(),
                    "vod_pic": pic,
                    "vod_remarks": item.get("vod_remarks", ""),
                    "vod_year": item.get("vod_year", ""),
                    "vod_play_url": item.get("vod_play_url", ""),
                    "vod_play_from": item.get("vod_play_from", ""),
                }
                items.append({
                    "vod_id": vid,
                    "vod_name": item.get("vod_name", "").strip(),
                    "vod_pic": pic,
                    "vod_remarks": item.get("vod_remarks", ""),
                    "vod_year": item.get("vod_year", ""),
                })
            elif "title" in item:
                # 360kan格式
                title = item.get("title", "").replace("<b>", "").replace("</b>", "").strip()
                cat_id = item.get("cat_id", "")
                en_id = item.get("en_id", "")
                if not cat_id or not en_id:
                    continue
                vid = f"detail:{cat_id}:{en_id}"
                pic = item.get("cover", "")
                if pic and pic.startswith("//"):
                    pic = "https:" + pic
                items.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": item.get("cat_name", ""),
                })
        return items

    def homeContent(self, filter=False):
        classes = []
        for k, v in CLASS_MAP.items():
            classes.append({"type_id": k, "type_name": v[2]})
        return {"class": classes}

    def homeVideoContent(self):
        try:
            # 首页推荐: 从多个分类各取一些, 凑够50部左右
            all_items = []
            # 电影20条
            for cat_id, size in [(1, 20), (2, 15), (3, 8), (4, 7)]:
                url = f"{HOST}/api/filter?catId={cat_id}&page=1&size={size}"
                r = self.fetch(url, headers={"User-Agent": UA}, timeout=15000)
                text = r.text if hasattr(r, 'text') else str(r)
                data = json.loads(text)
                items = self._items_from_filter(data, cat_id=cat_id)
                all_items.extend(items)
            return {"list": all_items}
        except:
            return {"list": []}

    def categoryContent(self, tid, pg=1, filter=False, extend=None):
        """分类内容 - 调用 /api/filter API"""
        try:
            pn = 1
            try:
                pn = max(int(str(pg)), 1)
            except:
                pass

            api_url = self._build_filter_url(tid, pn)
            if not api_url:
                return {"list": [], "page": pn, "pagecount": 1, "limit": 24, "total": 0}

            r = self.fetch(api_url, headers={"User-Agent": UA}, timeout=30000)
            text = r.text if hasattr(r, 'text') else str(r)
            data = json.loads(text)

            cat_id = CLASS_MAP.get(tid, (None, None, None))[0]
            items = self._items_from_filter(data, cat_id=cat_id)

            total = data.get("total", 0)
            # 估算总页数
            pagecount = (total // 24) + (1 if total % 24 else 0) if total else 1

            return {
                "list": items,
                "page": pn,
                "pagecount": max(pagecount, pn),
                "limit": 24,
                "total": total,
            }
        except Exception:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 0}

    def detailContent(self, ids):
        """详情页 - 调用 /api/detail API"""
        try:
            vid = str(ids[0]) if ids else ""
            if not vid:
                return {"list": []}

            # 苹果CMS搜索结果的直接播放
            if vid.startswith("search:"):
                return self._detail_from_search(vid)

            if not vid.startswith("detail:"):
                return {"list": []}

            parts = vid.split(":", 2)
            if len(parts) != 3:
                return {"list": []}

            cat_id, hash_id = parts[1], parts[2]
            if not cat_id or not hash_id:
                return {"list": []}

            # 调用详情API
            detail_url = f"{HOST}/api/detail?cat={cat_id}&id={hash_id}"
            r = self.fetch(detail_url, headers={"User-Agent": UA, "Referer": HOST}, timeout=30000)
            text = r.text if hasattr(r, 'text') else str(r)
            data = json.loads(text)

            if data.get("errno") != 0 or not data.get("data"):
                return {"list": []}

            d = data["data"]

            # 基本信息
            title = d.get("title", "")
            cover = self._cover(d.get("cdncover") or d.get("cover", ""))
            year = self._year(d.get("pubdate", ""))
            area = ", ".join(d.get("area", [])) if isinstance(d.get("area"), list) else str(d.get("area", ""))
            type_name = ", ".join(d.get("moviecategory", [])) if isinstance(d.get("moviecategory"), list) else str(d.get("moviecategory", ""))
            director = ", ".join(d.get("director", [])) if isinstance(d.get("director"), list) else str(d.get("director", ""))
            actor = ", ".join(d.get("actor", [])) if isinstance(d.get("actor"), list) else str(d.get("actor", ""))
            content = d.get("description", "")
            total = d.get("total", 0)
            upinfo = d.get("upinfo", "")
            remarks = str(upinfo) if upinfo else (f"{total}集" if total else "")

            # 收集所有平台的播放信息
            allepi = d.get("allepidetail", {})
            pld = d.get("playlinksdetail", {})

            # 平台名称映射辅助函数
            def _platform_name(site):
                return PLATFORM_NAMES.get(site, site)

            # 处理多集剧集 (TV series) - 有allepidetail时取第一个平台
            if allepi:
                first_site = list(allepi.keys())[0]
                episodes = allepi[first_site]
                pf_list = []
                pu_list = []
                for api in PARSE_APIS:
                    ep_list = []
                    for ep in episodes:
                        ep_num = ep.get("playlink_num", "")
                        ep_url = ep.get("url", "")
                        if not ep_url:
                            continue
                        parse_url = api["url"] + ep_url
                        ep_list.append(f"第{ep_num}集${parse_url}")
                    if ep_list:
                        pf_list.append(api["name"])
                        pu_list.append("#".join(ep_list))

            # 处理单集电影/短剧 - 列出所有平台的default_url
            elif pld:
                pf_list = []
                pu_list = []
                # 收集所有有default_url的平台
                platforms = []
                for site, info in pld.items():
                    default_url = info.get("default_url", "")
                    if default_url:
                        platforms.append((site, default_url))
                if not platforms:
                    return {"list": []}

                for api in PARSE_APIS:
                    ep_list = []
                    for site, url in platforms:
                        if not url:
                            continue
                        parse_url = api["url"] + url
                        ep_list.append(f"{_platform_name(site)}${parse_url}")
                    if ep_list:
                        pf_list.append(api["name"])
                        pu_list.append("#".join(ep_list))

            else:
                return {"list": []}

            vod = {
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": cover,
                "vod_year": year,
                "vod_area": area,
                "vod_class": type_name,
                "vod_director": director,
                "vod_actor": actor,
                "vod_content": content,
                "vod_remarks": remarks,
                "vod_play_from": "$$$".join(pf_list),
                "vod_play_url": "$$$".join(pu_list),
            }
            return {"list": [vod]}
        except Exception:
            return {"list": []}

    def _detail_from_search(self, vid):
        """处理搜索结果的直接播放(苹果CMS格式)"""
        global _search_cache
        try:
            cached = _search_cache.get(vid, {})
            if not cached or not cached.get("vod_play_url"):
                return {"list": []}
            # 从缓存构造详情
            return {
                "list": [{
                    "vod_id": vid,
                    "vod_name": cached.get("vod_name", ""),
                    "vod_pic": cached.get("vod_pic", ""),
                    "vod_remarks": cached.get("vod_remarks", ""),
                    "vod_year": cached.get("vod_year", ""),
                    "vod_play_from": cached.get("vod_play_from", "播放"),
                    "vod_play_url": cached.get("vod_play_url", ""),
                }]
            }
        except:
            return {"list": []}

    def searchContent(self, key, quick=False, pg=1):
        """搜索 - 调用API"""
        try:
            pn = 1
            try:
                pn = int(str(pg))
            except:
                pass
            url = f"{HOST}/api/search?q={quote(key)}"
            if pn > 1:
                url += f"&page={pn}"
            r = self.fetch(url, headers={
                "User-Agent": UA,
                "Accept": "application/json, text/plain, */*",
                "Referer": HOST + "/",
            }, timeout=30000)
            text = r.text if hasattr(r, 'text') else str(r)
            data = json.loads(text)
            items = self._extract_items_from_search_api(data)
            return {"list": items, "page": pn}
        except:
            return {"list": [], "page": 1}

    def playerContent(self, flag, id, vipFlags=None):
        """播放 - 官源返回原始URL让壳子解析, 解析线路返回拼接URL"""
        url = str(id) if id else str(flag)
        if not url:
            return {"url": ""}
        # 去掉名称前缀
        if "$" in url:
            parts = url.split("$", 1)
            url = parts[1]

        # 如果是搜索结果的vod_id
        if url.startswith("search:"):
            return self._player_from_search(url)

        # m3u8直链直接播
        if url.startswith("http") and self.isVideoFormat(url):
            return {"url": url}

        # 视频站链接
        if url.startswith("http"):
            return {
                "url": url,
                "parse": 1,
                "header": {"User-Agent": UA}
            }
        return {"url": url, "parse": 1, "header": {"User-Agent": UA}}

    def _player_from_search(self, vid):
        """从搜索结果恢复播放链接"""
        global _search_cache
        try:
            cached = _search_cache.get(vid, {})
            play_url = cached.get("vod_play_url", "")
            if not play_url:
                return {"url": ""}
            # vod_play_url 格式: 第1集$URL#第2集$URL
            # playerContent 传入的 id 已经是单集URL (带$前缀)
            # 如果 vid 中没有 $ , 返回第一集
            if "$" in vid:
                # 这种情况不应该发生, playerContent 已经处理了 $
                return {"url": ""}
            # 返回第一集URL
            first_ep = play_url.split("#")[0]
            if "$" in first_ep:
                url = first_ep.split("$")[1]
            else:
                url = first_ep
            if url.startswith("http"):
                return {"url": url, "parse": 0 if self.isVideoFormat(url) else 1}
            return {"url": url}
        except:
            return {"url": ""}

    def localProxy(self, param):
        pass
