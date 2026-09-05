# -*- coding: utf-8 -*-
"""
八戒影视 Spider（hipy / CatVod 类爬虫框架适配）
本资源来源于互联网公开渠道，仅可用于个人学习爬虫技术。
严禁将其用于任何商业用途，下载后请于 24 小时内删除，
搜索结果均来自源站，作者不承担任何责任。

使用方式：
  - 作为 CatVod / hipy 爬虫模块：由框架加载 Spider 类并调用其接口。
  - 独立运行（python bajie_spider.py）：仅执行 init() 自测，验证能否
    成功拉取 domainPath、获取 visitorInfo 的 userId/token。
"""

import sys
import json
import urllib3
import concurrent.futures
from urllib.parse import quote
from typing import Dict, List, Any, Optional
import time

try:
    import requests  # 独立运行时用 requests 实现 fetch/post
except Exception:  # pragma: no cover
    requests = None

# hipy / CatVod 框架中由 base.spider 提供 Spider 基类；
# 独立运行时 base 包可能不存在，做兼容处理。
try:
    from base.spider import Spider as _BaseSpider
except Exception:  # pragma: no cover
    class _BaseSpider:  # 占位基类，仅用于独立运行自测
        pass

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
sys.path.append("..")


def _req(self, method, url, **kw):
    """独立运行时的 requests 兜底实现，框架加载时会提供原生 fetch/post。"""
    if requests is None:
        raise RuntimeError("requests 未安装，且当前不在 hipy/CatVod 框架中运行")
    resp = requests.request(method, url, verify=False, timeout=15, **kw)
    class _R:
        pass
    r = _R()
    r.status_code = resp.status_code
    r.text = resp.text
    r.content = resp.content
    r._resp = resp
    def json():
        return resp.json()
    r.json = json
    return r

def _fetch(self, url, **kw):
    return _req(self, "GET", url, **kw)

def _post(self, url, data=None, **kw):
    headers = kw.pop("headers", None)
    return _req(self, "POST", url, data=data, headers=headers, **kw)


class Spider(_BaseSpider):
    host: str = ""
    userid: str = ""
    episode_list: List = []
    _cache: Dict = {}  # 简单缓存

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        # 框架会注入 fetch/post；独立运行时绑定 requests 兜底实现
        if not hasattr(self, "fetch"):
            self.fetch = _fetch.__get__(self)
        if not hasattr(self, "post"):
            self.post = _post.__get__(self)
        self._cache = {}

    headers = {
        "User-Agent": "okhttp/4.12.0",
        "Connection": "Keep-Alive",
        "Accept-Encoding": "gzip",
        "Content-Type": "application/json;charset=UTF-8",
        "Cache-Control": "no-cache",
        "token": "",
        "deviceId": "",
        "client": "app",
        "deviceType": "Android",
    }

    # ---------- 辅助方法 ----------
    def _safe_get(self, data: Dict, key: str, default: Any = "") -> Any:
        """安全获取字典值，避免 KeyError"""
        return data.get(key, default)

    def _build_video_item(self, data: Dict, extra_fields: Optional[List[str]] = None) -> Dict:
        """
        构建标准的视频项字典
        :param data: 原始数据
        :param extra_fields: 额外需要提取的字段列表
        """
        base_item = {
            "vod_id": self._safe_get(data, "id"),
            "vod_name": self._safe_get(data, "name", "未知影片"),
            "vod_pic": self._safe_get(data, "cover", ""),
            "vod_remarks": self._safe_get(data, "area", ""),
            "vod_year": self._safe_get(data, "year", ""),
        }
        
        # 添加额外字段
        if extra_fields:
            for field in extra_fields:
                base_item[f"vod_{field}"] = self._safe_get(data, field, "")
        
        return base_item

    def _safe_request(self, url: str, payload: Dict = None, method: str = "POST", 
                      max_retries: int = 3, retry_delay: int = 1) -> Optional[Dict]:
        """
        安全的请求方法，带重试机制
        :param url: 请求地址
        :param payload: 请求数据
        :param method: 请求方法 GET/POST
        :param max_retries: 最大重试次数
        :param retry_delay: 重试延迟（秒）
        """
        for attempt in range(max_retries):
            try:
                if method.upper() == "POST":
                    resp = self.post(
                        url,
                        data=json.dumps(payload) if payload else None,
                        headers=self.headers,
                    )
                else:
                    resp = self.fetch(url, headers=self.headers)
                
                if resp.status_code == 200:
                    result = resp.json()
                    # 检查业务状态码
                    code = result.get("code", 200)
                    if code in (200, 0):
                        return result
                    else:
                        msg = result.get("msg", result.get("message", "未知错误"))
                        print(f"[API错误] code={code}, msg={msg}")
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                            continue
                        return None
                else:
                    print(f"[HTTP错误] status={resp.status_code}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    return None
            except Exception as e:
                print(f"[请求失败] 尝试 {attempt + 1}/{max_retries}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                raise
        return None

    def _get_cache(self, key: str, ttl: int = 300) -> Optional[Any]:
        """获取缓存"""
        if key in self._cache:
            cache_data, timestamp = self._cache[key]
            if time.time() - timestamp < ttl:
                return cache_data
            else:
                del self._cache[key]
        return None

    def _set_cache(self, key: str, value: Any):
        """设置缓存"""
        self._cache[key] = (value, time.time())

    # ---------- 框架接口 ----------
    def init(self, extend=""):
        """初始化爬虫，获取域名配置和认证信息"""
        self.headers["deviceId"] = "2d590b9842d064a1"
        
        # 拉取域名路径配置（支持通过 BAJIE_HOST 环境变量手动指定，跳过远程配置）
        import os
        cfg_host = os.environ.get("BAJIE_HOST", "").strip()
        if cfg_host:
            self.host = cfg_host
            print(f"[init] 使用环境变量指定 host: {self.host}")
        else:
            try:
                resp = self.fetch(
                    "http://osstexll.oss-rg-china-mainland.aliyuncs.com/domainPath.json",
                    headers={
                        "User-Agent": "okhttp/4.12.0",
                        "Connection": "Keep-Alive",
                        "Accept-Encoding": "gzip",
                    },
                )
                j = resp.json()
                if isinstance(j, dict) and j.get("status") in (403, 401, 400):
                    raise RuntimeError(
                        "domainPath.json 被源站拒绝访问(status=%s)：%s。 "
                        "可在可访问该地址的网络环境下运行，或通过环境变量 "
                        "BAJIE_HOST=http://xxx 手动指定 host 后重试。"
                        % (j.get("status"), j.get("detail") or j.get("title"))
                    )
                urls = j.get("url") if isinstance(j, dict) else None
                if not urls:
                    raise RuntimeError("domainPath.json 返回结构异常，未找到 url 字段：" + str(j)[:200])
                self.host = urls[0]
                print(f"[init] 从远程配置获取 host: {self.host}")
            except Exception as e:
                print(f"[init] 获取域名配置失败: {e}")
                raise
        
        # 获取游客用户信息（userId / token）
        try:
            resp = self.fetch(f"{self.host}/api/v1/app/user/visitorInfo", headers=self.headers)
            data = resp.json().get("data", {})
            self.userid = data.get("id", "")
            self.headers["token"] = data.get("token", "")
            print(f"[init] 获取游客信息成功, userid: {self.userid}")
        except Exception as e:
            print(f"[init] 获取游客信息失败: {e}")
            raise

    def homeContent(self, filter):
        """获取首页分类列表"""
        cache_key = "home_content"
        cached = self._get_cache(cache_key, ttl=600)  # 10分钟缓存
        if cached:
            return cached
        
        try:
            result = self._safe_request(
                f"{self.host}/api/v1/app/screen/screenType",
                method="POST"
            )
            
            if not result:
                return {"class": []}
            
            data = result.get("data", [])
            classes = [
                {
                    "type_id": self._safe_get(i, "id"),
                    "type_name": self._safe_get(i, "name", "未命名分类")
                } 
                for i in data if self._safe_get(i, "id")
            ]
            
            print(f"[homeContent] 获取到 {len(classes)} 个分类")
            result_data = {"class": classes}
            self._set_cache(cache_key, result_data)
            return result_data
        except Exception as e:
            print(f"[homeContent] 获取分类失败: {e}")
            return {"class": []}

    def homeVideoContent(self):
        """获取首页推荐内容"""
        cache_key = "home_video"
        cached = self._get_cache(cache_key, ttl=300)  # 5分钟缓存
        if cached:
            return cached
        
        try:
            result = self._safe_request(
                f"{self.host}/api/v1/app/recommend/recommendList",
                method="POST"
            )
            
            if not result:
                return {"list": []}
            
            data = result.get("data", [])
            videos = []
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                future_to_id = {
                    executor.submit(
                        self._safe_request,
                        f"{self.host}/api/v1/app/recommend/recommendSubList",
                        {"condition": item["id"], "pageNum": 1, "pageSize": 6}
                    ): item["id"]
                    for item in data if item.get("id")
                }
                
                for future in concurrent.futures.as_completed(future_to_id):
                    try:
                        result = future.result()
                        if result:
                            for video in result.get("data", {}).get("records", []):
                                videos.append(self._build_video_item(video))
                    except Exception as e:
                        print(f"[homeVideoContent] 请求失败 for item {future_to_id[future]}: {e}")
            
            print(f"[homeVideoContent] 获取到 {len(videos)} 个推荐视频")
            result_data = {"list": videos}
            self._set_cache(cache_key, result_data)
            return result_data
        except Exception as e:
            print(f"[homeVideoContent] 获取推荐失败: {e}")
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        """
        获取分类内容
        :param tid: 分类ID
        :param pg: 页码
        :param filter: 筛选条件
        :param extend: 扩展参数
        """
        cache_key = f"category_{tid}_{pg}"
        cached = self._get_cache(cache_key, ttl=120)  # 2分钟缓存
        if cached:
            return cached
        
        try:
            payload = {
                "condition": {
                    "classify": "",
                    "region": "",
                    "sreecnTypeEnum": "NEWEST",
                    "typeId": tid,
                    "year": "",
                },
                "pageNum": int(pg),
                "pageSize": 40,
            }
            
            result = self._safe_request(
                f"{self.host}/api/v1/app/screen/screenMovie",
                payload=payload,
                method="POST"
            )
            
            if not result:
                return {"list": [], "page": pg}
            
            records = result.get("data", {}).get("records", [])
            
            videos = []
            for i in records:
                video_item = self._build_video_item(i, ["area", "year"])
                videos.append(video_item)
            
            print(f"[categoryContent] tid={tid}, pg={pg}, 获取到 {len(videos)} 个视频")
            result_data = {"list": videos, "page": pg}
            self._set_cache(cache_key, result_data)
            return result_data
        except Exception as e:
            print(f"[categoryContent] 获取分类内容失败 (tid={tid}, pg={pg}): {e}")
            return {"list": [], "page": pg}

    def searchContent(self, key, quick, pg="1"):
        """搜索内容"""
        cache_key = f"search_{key}_{pg}"
        cached = self._get_cache(cache_key, ttl=60)  # 1分钟缓存
        if cached:
            return cached
        
        try:
            payload = {"condition": {"value": key}, "pageNum": int(pg), "pageSize": 40}
            
            result = self._safe_request(
                f"{self.host}/api/v1/app/search/searchMovie",
                payload=payload,
                method="POST"
            )
            
            if not result:
                return {"list": [], "page": pg}
            
            records = result.get("data", {}).get("records", [])
            
            videos = []
            for i in records:
                video_item = self._build_video_item(i, ["area", "year", "desc"])
                videos.append(video_item)
            
            print(f"[searchContent] key='{key}', pg={pg}, 找到 {len(videos)} 个结果")
            result_data = {"list": videos, "page": pg}
            self._set_cache(cache_key, result_data)
            return result_data
        except Exception as e:
            print(f"[searchContent] 搜索失败 (key='{key}', pg={pg}): {e}")
            return {"list": [], "page": pg}

    def detailContent(self, ids):
        """获取影片详情 - 支持短剧特殊处理"""
        try:
            video_id = ids[0] if ids else ""
            if not video_id:
                return {"list": []}
            
            cache_key = f"detail_{video_id}"
            cached = self._get_cache(cache_key, ttl=600)  # 10分钟缓存
            if cached:
                return cached
            
            # 获取影片详情和播放列表
            payload = {"id": video_id, "source": 0, "typeId": "M17", "userId": self.userid}
            result = self._safe_request(
                f"{self.host}/api/v1/app/play/movieDetails",
                payload=payload,
                method="POST"
            )
            
            if not result:
                return {"list": []}
            
            data = result.get("data", {})
            if not data:
                print(f"[detailContent] 影片 {video_id} 无数据")
                return {"list": []}
            
            # 获取影片描述
            desc_result = self._safe_request(
                f"{self.host}/api/v1/app/play/movieDesc",
                payload={"id": video_id, "typeId": "M17"},
                method="POST"
            )
            d2 = desc_result.get("data", {}) if desc_result else {}
            
            # 构建详情数据
            video_detail = self._build_detail_data(video_id, data, d2)
            
            print(f"[detailContent] 获取影片 {video_detail['vod_name']} 详情成功")
            result_data = {"list": [video_detail]}
            self._set_cache(cache_key, result_data)
            return result_data
        except Exception as e:
            print(f"[detailContent] 获取详情失败 (ids={ids}): {e}")
            return {"list": []}

    def _build_detail_data(self, video_id: str, data: Dict, desc_data: Dict) -> Dict:
        """构建影片详情数据，包含短剧特殊处理"""
        currentplayerid = data.get("playerId", 0)
        episode_list = data.get("episodeList", [])
        movie_player_list = data.get("moviePlayerList", [])
        
        play_urls = []
        show = []
        
        # 判断是否为短剧
        is_short_drama = self._is_short_drama(data, movie_player_list)
        
        # 处理播放列表
        if is_short_drama:
            play_urls, show = self._build_short_drama_playlist(
                video_id, movie_player_list, currentplayerid
            )
        else:
            play_urls, show = self._build_normal_playlist(
                video_id, episode_list, movie_player_list, currentplayerid
            )
        
        # 兜底：如果没有生成任何播放源
        if not play_urls:
            show = ["默认源"]
            play_urls = [f"第1集$1@0@{video_id}@virtual"]
        
        # 构建返回数据
        video = {
            "vod_id": desc_data.get("id", video_id),
            "vod_name": desc_data.get("name", data.get("name", "未知影片")),
            "vod_pic": desc_data.get("cover", data.get("cover", "")),
            "vod_content": desc_data.get("introduce", data.get("introduce", "")),
            "vod_year": desc_data.get("year", data.get("year", "")),
            "vod_area": desc_data.get("area", data.get("area", "")),
            "vod_remarks": "",
            "vod_score": desc_data.get("score", data.get("score", "")),
            "type_name": desc_data.get("classify", data.get("classify", "")),
            "vod_director": desc_data.get("director", data.get("director", "")),
            "vod_play_from": "$$$".join(show),
            "vod_play_url": "$$$".join(play_urls),
        }
        
        return video

    def _is_short_drama(self, data: Dict, player_list: List) -> bool:
        """判断是否为短剧"""
        # 通过类型ID判断
        type_id = data.get("typeId", "")
        if type_id == "M16":
            return True
        
        # 通过类型名称判断
        type_name = data.get("typeName", "") or data.get("classify", "")
        if "短剧" in type_name:
            return True
        
        # 通过播放源名称判断
        short_drama_keywords = ["合集", "短剧", "RO", "分集"]
        for pl in player_list:
            pl_name = pl.get("moviePlayerName", "")
            for keyword in short_drama_keywords:
                if keyword in pl_name:
                    return True
        
        # 通过集数判断（短剧通常集数较多）
        for pl in player_list:
            episode_total = pl.get("episodeTotal", 0)
            if episode_total > 80:  # 超过80集可能是短剧
                return True
        
        return False

    def _build_short_drama_playlist(self, video_id: str, player_list: List, 
                                    current_id: int) -> tuple:
        """构建短剧播放列表"""
        play_urls = []
        show = []
        
        # 按播放源分组，每个播放源独立显示
        for pl in player_list:
            pl_id = pl.get("id")
            episode_total = pl.get("episodeTotal")
            pl_name = pl.get("moviePlayerName", "未知源")
            
            if episode_total is None or episode_total == 0:
                continue
            
            # 生成该播放源的剧集列表
            pu = [
                f"第{ep}集${ep}@{pl_id}@{video_id}@virtual"
                for ep in range(1, min(episode_total + 1, 500))  # 短剧最多500集
            ]
            if pu:
                play_urls.append("#".join(pu))
                show.append(pl_name)
        
        return play_urls, show

    def _build_normal_playlist(self, video_id: str, episode_list: List, 
                              player_list: List, current_id: int) -> tuple:
        """构建普通剧集播放列表"""
        play_urls = []
        show = []
        
        # 优先使用真实分集
        if episode_list and len(episode_list) > 0:
            # 找到当前播放源名称
            current_source_name = "默认源"
            for pl in player_list:
                if pl.get("id") == current_id:
                    current_source_name = pl.get("moviePlayerName", "默认源")
                    break
            
            # 生成真实分集播放列表
            play_url = [
                f"{ep.get('episode', str(idx+1))}${video_id}@{current_id}@{ep.get('id', '')}@episode"
                for idx, ep in enumerate(episode_list)
            ]
            play_urls.append("#".join(play_url))
            show.append(current_source_name)
            
            # 添加其他播放源（如果有）
            for pl in player_list:
                pl_id = pl.get("id")
                if pl_id == current_id:
                    continue
                pl_name = pl.get("moviePlayerName", "未知源")
                if pl_name not in show:
                    ep_total = pl.get("episodeTotal", len(episode_list))
                    if ep_total and ep_total > 0:
                        pu = [
                            f"第{ep}集${ep}@{pl_id}@{video_id}@virtual"
                            for ep in range(1, min(ep_total + 1, 200))
                        ]
                        if pu:
                            play_urls.append("#".join(pu))
                            show.append(pl_name)
        else:
            # 没有真实分集，使用虚拟分集
            for pl in player_list:
                pl_id = pl.get("id")
                episode_total = pl.get("episodeTotal")
                pl_name = pl.get("moviePlayerName", "默认源")
                
                if episode_total and episode_total > 0:
                    pu = [
                        f"第{ep}集${ep}@{pl_id}@{video_id}@virtual"
                        for ep in range(1, min(episode_total + 1, 200))
                    ]
                    if pu:
                        play_urls.append("#".join(pu))
                        show.append(pl_name)
                        break  # 只取第一个有效的播放源
        
        return play_urls, show

    def playerContent(self, flag, id, vipflags):
        """获取播放地址"""
        try:
            parts = id.split("@")
            if len(parts) < 4:
                print(f"[playerContent] 无效的播放ID格式: {id}")
                return {"jx": "0", "parse": "0", "url": "", "header": {}}
            
            param, playerid, param2, param3 = parts[0], parts[1], parts[2], parts[3]
            
            # 构建请求参数
            if param3 == "virtual":
                payload = {
                    "episodeIndex": str(max(0, int(param) - 1)),
                    "id": int(param2),
                    "playerId": playerid,
                    "source": 0,
                    "typeId": "M16",
                    "userId": self.userid,
                }
            else:
                payload = {
                    "episodeId": param2,
                    "id": param,
                    "playerId": playerid,
                    "source": 0,
                    "typeId": "M16",
                    "userId": self.userid,
                }
            
            # 获取播放详情
            result = self._safe_request(
                f"{self.host}/api/v1/app/play/movieDetails",
                payload=payload,
                method="POST"
            )
            
            if not result:
                return {"jx": "0", "parse": "0", "url": "", "header": {}}
            
            data = result.get("data", {})
            parse_url = data.get("url", "")
            playerid = data.get("playerId", playerid)
            
            if not parse_url:
                print(f"[playerContent] 未获取到播放URL")
                return {"jx": "0", "parse": "0", "url": "", "header": {}}
            
            # 解析实际播放地址
            analysis_result = self._safe_request(
                f"{self.host}/api/v1/app/play/analysisMovieUrl"
                f"?playerUrl={quote(parse_url, safe='')}&playerId={playerid}",
                method="GET"
            )
            
            url = analysis_result.get("data", "") if analysis_result else ""
            
            print(f"[playerContent] 获取播放地址成功")
            return {
                "jx": "0",
                "parse": "0",
                "url": url,
                "header": {
                    "User-Agent": (
                        "Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) "
                        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 "
                        "Mobile/15E148 Safari/604.1"
                    )
                },
            }
        except Exception as e:
            print(f"[playerContent] 获取播放地址失败: {e}")
            return {"jx": "0", "parse": "0", "url": "", "header": {}}

    # ---------- 框架预留接口 ----------
    def getName(self):
        return "八戒影视"

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        pass

    def destroy(self):
        print("[destroy] 爬虫已销毁")
        self._cache.clear()

    def localProxy(self, param):
        pass


# ---------- 独立运行自测 ----------
if __name__ == "__main__":
    print("=" * 60)
    print("八戒影视爬虫 - 独立测试")
    print("=" * 60)
    
    sp = Spider()
    
    # 1. 测试初始化
    print("\n[测试1] 初始化...")
    try:
        sp.init()
        print("✅ 初始化成功")
        print(f"   host    = {sp.host}")
        print(f"   userid  = {sp.userid}")
        print(f"   token   = {(sp.headers.get('token') or '')[:24]}...")
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        sys.exit(1)
    
    # 2. 测试首页分类
    print("\n[测试2] 获取首页分类...")
    try:
        result = sp.homeContent(None)
        classes = result.get("class", [])
        print(f"✅ 获取到 {len(classes)} 个分类")
        if classes:
            print(f"   前5个分类: {[(c['type_name'], c['type_id']) for c in classes[:5]]}")
    except Exception as e:
        print(f"❌ 获取分类失败: {e}")
    
    # 3. 测试推荐内容
    print("\n[测试3] 获取推荐内容...")
    try:
        result = sp.homeVideoContent()
        videos = result.get("list", [])
        print(f"✅ 获取到 {len(videos)} 个推荐视频")
        if videos:
            print(f"   首个视频: {videos[0].get('vod_name', 'N/A')}")
    except Exception as e:
        print(f"❌ 获取推荐失败: {e}")
    
    # 4. 测试分类内容
    print("\n[测试4] 获取分类内容 (tid=1)...")
    try:
        result = sp.categoryContent("1", "1", None, None)
        videos = result.get("list", [])
        print(f"✅ 获取到 {len(videos)} 个视频")
        if videos:
            sample = videos[0]
            print(f"   示例: {sample.get('vod_name', 'N/A')} ({sample.get('vod_year', '未知年份')})")
    except Exception as e:
        print(f"❌ 获取分类内容失败: {e}")
    
    # 5. 测试搜索
    print("\n[测试5] 搜索 '电影'...")
    try:
        result = sp.searchContent("电影", False, "1")
        videos = result.get("list", [])
        print(f"✅ 找到 {len(videos)} 个结果")
        if videos:
            print(f"   首个结果: {videos[0].get('vod_name', 'N/A')}")
    except Exception as e:
        print(f"❌ 搜索失败: {e}")
    
    # 6. 测试获取详情（如果推荐列表有数据）
    if videos:
        print("\n[测试6] 获取视频详情...")
        try:
            video_id = videos[0].get("vod_id")
            if video_id:
                result = sp.detailContent([video_id])
                detail_list = result.get("list", [])
                if detail_list:
                    detail = detail_list[0]
                    print(f"✅ 获取详情成功")
                    print(f"   名称: {detail.get('vod_name', 'N/A')}")
                    print(f"   播放源: {detail.get('vod_play_from', 'N/A')}")
                    play_urls = detail.get('vod_play_url', '').split('$$$')
                    print(f"   播放列表数: {len(play_urls)}")
                    if play_urls:
                        first_playlist = play_urls[0].split('#')
                        print(f"   第一个播放列表集数: {len(first_playlist)}")
                else:
                    print("❌ 获取详情返回空数据")
            else:
                print("❌ 视频ID为空")
        except Exception as e:
            print(f"❌ 获取详情失败: {e}")
    
    print("\n" + "=" * 60)
    print("所有测试完成！")
    print("=" * 60)