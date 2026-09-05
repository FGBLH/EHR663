# -*- coding: utf-8 -*-
"""
==================================================
@Spider Name : ASMR吧 (asmrba.com)
@Description : ASMR吧 - WordPress Modown主题 ASMR视频站
              数据源：WP REST API (/wp-json/wp/v2/)
              视频源：B站嵌入 (Bilibili iframe)
              分类：中文ASMR/日韩ASMR/欧美ASMR/ASMR资讯
==================================================
"""
import sys
import re
import json
import time
from urllib.parse import quote

try:
    import requests
except ImportError:
    requests = None

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def init(self, extend=""): self.extend = extend
        def getName(self): return "Base"
        def homeContent(self, filter): return {'class': [], 'filters': {}}
        def homeVideoContent(self): return {'list': []}
        def categoryContent(self, tid, pg, filter, extend):
            return {'list': [], 'page': 1, 'pagecount': 1, 'limit': 20, 'total': 0}
        def detailContent(self, ids): return {'list': []}
        def playerContent(self, flag, id, vipFlags=None):
            return {'parse': 0, 'playUrl': '', 'url': '', 'header': ''}
        def searchContent(self, key, quick, pg='1'):
            return {'list': [], 'page': 1, 'pagecount': 1, 'limit': 20, 'total': 0}
        def isVideoFormat(self, url): return False
        def manualVideoCheck(self): return False
        def localProxy(self, param): return [404, 'text/plain', b'']
        def destroy(self): pass


UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"


class Spider(BaseSpider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.host = "https://www.asmrba.com"
        self.api_base = f"{self.host}/wp-json/wp/v2"
        self.session = None
        # 分类缓存: {id: name}
        self._cat_cache = None
        # 标签缓存: {id: name}
        self._tag_cache = {}
        # 文章详情缓存
        self._post_cache = {}

    def getName(self):
        return "ASMR吧"

    def init(self, extend=""):
        self.setExtendInfo(extend)
        if requests:
            self.session = requests.Session()
            self.session.headers.update({
                "User-Agent": UA,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Referer": self.host + "/",
            })
            self.session.verify = False

    def setExtendInfo(self, extend=""):
        if isinstance(extend, dict):
            self.extend_cfg = extend
        elif extend and isinstance(extend, str):
            try:
                self.extend_cfg = json.loads(extend)
            except Exception:
                self.extend_cfg = {}
        else:
            self.extend_cfg = {}
        self.host = str(self.extend_cfg.get("host") or self.host).rstrip("/")
        self.api_base = f"{self.host}/wp-json/wp/v2"

    def destroy(self):
        if self.session:
            try:
                self.session.close()
            except Exception:
                pass

    def isVideoFormat(self, url):
        return bool(re.search(r"\.(?:mp4|m3u8|mp3|m4a|flv|mkv|ts)(?:\?|$)", str(url), re.I))

    def manualVideoCheck(self):
        return False

    # ==================== 网络请求 ====================

    def _fetch_json(self, path, params=None):
        """调用 WP REST API"""
        url = self.api_base + path
        if params:
            from urllib.parse import urlencode
            url += "?" + urlencode(params)

        try:
            if self.session:
                r = self.session.get(url, timeout=15)
                if r.status_code == 200:
                    total = r.headers.get("X-WP-Total")
                    total_pages = r.headers.get("X-WP-TotalPages")
                    return r.json(), {
                        "total": int(total) if total else None,
                        "total_pages": int(total_pages) if total_pages else None,
                    }
            else:
                import urllib.request, ssl
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                req = urllib.request.Request(url, headers={
                    "User-Agent": UA,
                    "Referer": self.host + "/",
                    "Accept": "application/json",
                })
                resp = urllib.request.urlopen(req, context=ctx, timeout=15)
                headers = dict(resp.headers)
                data = json.loads(resp.read().decode("utf-8"))
                return data, {
                    "total": int(headers.get("X-WP-Total", 0)) if headers.get("X-WP-Total") else None,
                    "total_pages": int(headers.get("X-WP-TotalPages", 0)) if headers.get("X-WP-TotalPages") else None,
                }
        except Exception:
            pass
        return None, {}

    # ==================== 分类 ====================

    def _load_categories(self):
        """加载分类列表（带缓存）"""
        if self._cat_cache is not None:
            return self._cat_cache

        self._cat_cache = []
        try:
            data, _ = self._fetch_json("/categories", {"per_page": 100, "orderby": "count", "order": "desc"})
            if isinstance(data, list):
                for cat in data:
                    # 跳过空分类（0篇）和资讯分类（不是视频）
                    if cat.get("count", 0) == 0:
                        continue
                    self._cat_cache.append({
                        "type_id": str(cat["id"]),
                        "type_name": cat["name"],
                        "slug": cat.get("slug", ""),
                        "count": cat.get("count", 0),
                    })
        except Exception:
            pass

        return self._cat_cache

    def homeContent(self, filter=False):
        classes = []
        filters = {}

        cats = self._load_categories()
        for cat in cats:
            classes.append({
                "type_id": cat["type_id"],
                "type_name": cat["type_name"],
            })

        # 最新更新放第一个
        classes.insert(0, {"type_id": "latest", "type_name": "最新更新"})

        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        """首页推荐 = 最新文章"""
        result = self._get_post_list({"per_page": 24, "orderby": "date", "order": "desc"})
        return {"list": result.get("list", [])}

    # ==================== 分类列表 ====================

    def categoryContent(self, tid, pg, filter=False, extend=None):
        page = max(1, self._page(pg))

        if tid == "latest":
            result = self._get_post_list({
                "per_page": 20,
                "page": page,
                "orderby": "date",
                "order": "desc",
            })
        else:
            result = self._get_post_list({
                "categories": tid,
                "per_page": 20,
                "page": page,
                "orderby": "date",
                "order": "desc",
            })

        return result

    def _get_post_list(self, params):
        """获取文章列表并转为VOD格式"""
        params["_embed"] = "1"
        data, meta = self._fetch_json("/posts", params)

        if not isinstance(data, list):
            return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}

        items = []
        for post in data:
            vod = self._post_to_vod_list_item(post)
            if vod:
                items.append(vod)

        total = meta.get("total") or len(items)
        total_pages = meta.get("total_pages") or 1
        page = params.get("page", 1)

        return {
            "list": items,
            "page": page,
            "pagecount": total_pages,
            "limit": len(items) or 20,
            "total": total,
        }

    def _post_to_vod_list_item(self, post):
        """WP post 转 VOD 列表项"""
        try:
            post_id = post.get("id")
            if not post_id:
                return None

            title = post.get("title", {}).get("rendered", "")
            title = re.sub(r"<[^>]+>", "", title).strip()
            if not title:
                return None

            # 封面
            cover = ""
            embeds = post.get("_embedded", {})
            featured = embeds.get("wp:featuredmedia", [])
            if featured and isinstance(featured[0], dict):
                media = featured[0]
                cover = media.get("source_url", "")
                if not cover:
                    details = media.get("media_details", {})
                    sizes = details.get("sizes", {})
                    if sizes:
                        for size_name in ["large", "medium_large", "post-thumbnail", "medium", "full"]:
                            if size_name in sizes:
                                cover = sizes[size_name].get("source_url", "")
                                break

            # 备注：日期 + 分类名
            date_str = post.get("date", "")[:10] if post.get("date") else ""
            cat_names = []
            cats = post.get("categories", [])
            if cats and self._cat_cache:
                for cat in self._cat_cache:
                    if cat["type_id"] in [str(c) for c in cats]:
                        cat_names.append(cat["type_name"])
                        break

            remarks = ""
            if cat_names:
                remarks = cat_names[0]
            if date_str:
                if remarks:
                    remarks += f" | {date_str}"
                else:
                    remarks = date_str

            return {
                "vod_id": str(post_id),
                "vod_name": title,
                "vod_pic": cover,
                "vod_remarks": remarks,
            }
        except Exception:
            return None

    # ==================== 详情 ====================

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        post_id = ids[0] if isinstance(ids, (list, tuple)) else str(ids)

        # 缓存查找
        if post_id in self._post_cache:
            return {"list": [self._post_cache[post_id]]}

        data, _ = self._fetch_json(f"/posts/{post_id}", {"_embed": "1"})
        if not isinstance(data, dict):
            return {"list": []}

        vod = self._post_to_vod_detail(data)
        if vod:
            self._post_cache[post_id] = vod
            return {"list": [vod]}

        return {"list": []}

    def _post_to_vod_detail(self, post):
        """WP post 转 VOD 详情"""
        try:
            post_id = str(post.get("id", ""))
            title = post.get("title", {}).get("rendered", "")
            title = re.sub(r"<[^>]+>", "", title).strip()

            content = post.get("content", {}).get("rendered", "")
            excerpt = post.get("excerpt", {}).get("rendered", "")
            excerpt = re.sub(r"<[^>]+>", "", excerpt).strip()

            # 封面
            cover = ""
            embeds = post.get("_embedded", {})
            featured = embeds.get("wp:featuredmedia", [])
            if featured and isinstance(featured[0], dict):
                cover = featured[0].get("source_url", "")

            # 分类名
            cat_names = []
            cats = post.get("categories", [])
            cat_cache = self._load_categories()
            for c in cat_cache:
                if int(c["type_id"]) in cats:
                    cat_names.append(c["type_name"])

            # 标签
            tag_names = []
            tags = post.get("tags", [])
            if tags:
                tag_data, _ = self._fetch_json("/tags", {"include": ",".join(str(t) for t in tags), "per_page": 50})
                if isinstance(tag_data, list):
                    tag_names = [t.get("name", "") for t in tag_data if t.get("name")]

            # 发布时间
            date_str = post.get("date", "")[:10] if post.get("date") else ""

            # 视频提取
            play_from_list = []
            play_url_list = []
            videos = self._extract_videos(content)

            for idx, (source_name, video_url, video_title) in enumerate(videos):
                ep_title = video_title or title
                play_from_list.append(source_name)
                play_url_list.append(f"{ep_title}${video_url}")

            # 如果没有视频，也返回详情（图文）
            if not play_from_list:
                play_from_list.append("图文")
                play_url_list.append(f"{title}$")

            # 描述
            description = excerpt or title
            if len(description) < 50:
                # 从内容中提取纯文本
                text = re.sub(r"<[^>]+>", " ", content)
                text = re.sub(r"\s+", " ", text).strip()
                if len(text) > 200:
                    description = text[:300] + "..."

            vod = {
                "vod_id": post_id,
                "vod_name": title,
                "vod_pic": cover,
                "vod_director": "",
                "vod_actor": ",".join(tag_names) if tag_names else "",
                "vod_year": date_str,
                "vod_area": ",".join(cat_names) if cat_names else "",
                "vod_content": description,
                "vod_remarks": ",".join(cat_names) if cat_names else "",
                "vod_play_from": "$$$".join(play_from_list),
                "vod_play_url": "$$$".join(play_url_list),
                "vod_tag": ",".join(tag_names),
            }
            return vod
        except Exception:
            return None

    def _extract_videos(self, content):
        """
        从文章内容中提取视频
        返回 [(来源名, 视频URL或播放页URL, 视频标题), ...]
        """
        videos = []
        seen_urls = set()

        if not content:
            return videos

        import html as _html

        def _norm_url(u):
            """标准化 URL：补全协议、解码 HTML 实体"""
            if not u:
                return u
            u = _html.unescape(u)
            if u.startswith("//"):
                u = "https:" + u
            return u

        def _add(line_name, url, title):
            if not url:
                return
            url = _norm_url(url)
            if url in seen_urls:
                return
            seen_urls.add(url)
            videos.append((line_name, url, title))

        # 1. B站 iframe
        bilibili_pattern = re.compile(
            r'<iframe[^>]+src=["\']([^"\']*bilibili[^"\']*)["\'][^>]*>',
            re.I
        )
        bvid_set = set()
        for match in bilibili_pattern.finditer(content):
            src = match.group(1)
            src = _norm_url(src)
            # 提取 BVID 作为去重标识
            bvid_m = re.search(r"bvid=([A-Za-z0-9]+)", src)
            p_m = re.search(r"[?&]p=(\d+)", src)
            bvid = bvid_m.group(1) if bvid_m else src
            p_num = p_m.group(1) if p_m else "1"
            dedup_key = f"{bvid}_p{p_num}"
            if dedup_key in bvid_set:
                continue
            bvid_set.add(dedup_key)

            line_name = f"B站{p_num}" if p_num != "1" else "B站"
            ep_title = f"第{p_num}P" if p_num != "1" else "B站"
            _add(line_name, src, ep_title)

        # 2. YouTube iframe
        yt_pattern = re.compile(
            r'<iframe[^>]+src=["\']([^"\']*(?:youtube|youtu\.be)[^"\']*)["\'][^>]*>',
            re.I
        )
        for match in yt_pattern.finditer(content):
            src = match.group(1)
            _add("YouTube", src, "YouTube")

        # 3. 直接 video 标签
        video_pattern = re.compile(
            r'<video[^>]*>([\s\S]*?)</video>',
            re.S | re.I
        )
        for match in video_pattern.finditer(content):
            video_html = match.group(0)
            src_m = re.search(r'src=["\']([^"\']+)["\']', video_html, re.I)
            if src_m:
                _add("直链", src_m.group(1), "直链播放")

        # 4. source 标签（video内部）
        source_pattern = re.compile(
            r'<source[^>]+src=["\']([^"\']+\.(?:mp4|m3u8|webm|ogg)[^"\']*)["\']',
            re.I
        )
        for match in source_pattern.finditer(content):
            _add("直链", match.group(1), "直链播放")

        # 5. 其他 iframe（含 player 的）
        iframe_pattern = re.compile(
            r'<iframe[^>]+src=["\']([^"\']*player[^"\']*)["\'][^>]*>',
            re.I
        )
        for match in iframe_pattern.finditer(content):
            src = match.group(1)
            src_norm = _norm_url(src)
            if src_norm in seen_urls:
                continue
            # 跳过已经匹配过的 B站/YouTube
            if "bilibili" in src_norm.lower() or "youtube" in src_norm.lower():
                continue
            _add("播放器", src, "在线播放")

        return videos

    # ==================== 搜索 ====================

    def searchContent(self, key, quick=False, pg="1"):
        page = max(1, self._page(pg))

        if not key or not key.strip():
            return {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}

        # 使用 WP 搜索 API
        data, meta = self._fetch_json("/search", {
            "search": key,
            "per_page": 20,
            "page": page,
            "type": "post",
            "subtype": "post",
            "_embed": "1",
        })

        if not isinstance(data, list):
            return {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}

        items = []
        for item in data:
            # search API 返回的是搜索结果，需要转换
            post_id = item.get("id")
            title = item.get("title", "")
            title = re.sub(r"<[^>]+>", "", title).strip()

            if not post_id or not title:
                continue

            # 搜索结果没有 _embed，需要单独获取封面
            cover = ""
            # 先查详情缓存
            if str(post_id) in self._post_cache:
                cached = self._post_cache[str(post_id)]
                cover = cached.get("vod_pic", "")
                if not cover:
                    # 用详情页数据
                    detail = self.detailContent([str(post_id)])
                    if detail.get("list"):
                        cover = detail["list"][0].get("vod_pic", "")

            items.append({
                "vod_id": str(post_id),
                "vod_name": title,
                "vod_pic": cover,
                "vod_remarks": "",
            })

        total = meta.get("total") or len(items)
        total_pages = meta.get("total_pages") or 1

        return {
            "list": items,
            "page": page,
            "pagecount": total_pages,
            "limit": len(items) or 20,
            "total": total,
        }

    # ==================== 播放 ====================

    # ==================== B站视频解析 ====================

    def _parse_bilibili_video(self, iframe_url):
        """
        从B站嵌入页/API解析真实视频地址
        返回 (video_url, audio_url, quality) 或 ("", "", "")
        """
        try:
            import hashlib

            # 从 URL 中提取 bvid / aid / cid
            bvid = ""
            aid = ""
            cid = ""

            bv_m = re.search(r'bvid=([A-Za-z0-9]+)', iframe_url, re.I)
            if bv_m:
                bvid = bv_m.group(1)

            aid_m = re.search(r'aid=(\d+)', iframe_url, re.I)
            if aid_m:
                aid = aid_m.group(1)

            cid_m = re.search(r'cid=(\d+)', iframe_url, re.I)
            if cid_m:
                cid = cid_m.group(1)

            # 如果没有 cid，先获取 cid
            if not cid and (bvid or aid):
                cid = self._get_bilibili_cid(bvid, aid)

            if not cid:
                return "", "", ""

            # 调用 B站播放地址 API
            api_url = "https://api.bilibili.com/x/player/playurl"
            params = {
                "bvid": bvid,
                "aid": aid,
                "cid": cid,
                "qn": 64,       # 720P
                "fnval": 16,    # DASH格式
                "fourk": 0,
                "platform": "html5",
                "high_quality": 1,
            }

            headers = {
                "User-Agent": UA,
                "Referer": "https://www.bilibili.com/",
                "Origin": "https://www.bilibili.com",
            }

            data = None
            if self.session:
                try:
                    r = self.session.get(api_url, params=params, headers=headers, timeout=10)
                    if r.status_code == 200:
                        data = r.json()
                except Exception:
                    pass

            if not data and requests:
                try:
                    r = requests.get(api_url, params=params, headers=headers, timeout=10, verify=False)
                    if r.status_code == 200:
                        data = r.json()
                except Exception:
                    pass

            if not data:
                return "", "", ""

            # 解析返回数据
            if data.get("code") != 0:
                return "", "", ""

            play_data = data.get("data", {})

            # DASH 格式（音视频分离）
            dash = play_data.get("dash")
            if dash:
                video_url = ""
                audio_url = ""

                # 取视频流（优先 720P / 480P / 360P）
                videos = dash.get("video", [])
                if videos:
                    # 按清晰度排序，取最合适的
                    videos_sorted = sorted(videos, key=lambda x: x.get("id", 0), reverse=True)
                    for v in videos_sorted:
                        if v.get("baseUrl"):
                            video_url = v["baseUrl"]
                            break
                        if v.get("base_url"):
                            video_url = v["base_url"]
                            break

                # 取音频流
                audios = dash.get("audio", [])
                if audios:
                    audios_sorted = sorted(audios, key=lambda x: x.get("id", 0), reverse=True)
                    for a in audios_sorted:
                        if a.get("baseUrl"):
                            audio_url = a["baseUrl"]
                            break
                        if a.get("base_url"):
                            audio_url = a["base_url"]
                            break

                return video_url, audio_url, "dash"

            # 普通格式（durl） - 直接返回视频地址
            durl = play_data.get("durl", [])
            if durl and isinstance(durl, list):
                url = durl[0].get("url", "") or durl[0].get("durl_url", "")
                if url:
                    return url, "", "normal"

        except Exception:
            pass

        return "", "", ""

    def _get_bilibili_cid(self, bvid="", aid=""):
        """获取B站视频的 cid"""
        try:
            headers = {
                "User-Agent": UA,
                "Referer": "https://www.bilibili.com/",
            }

            if bvid:
                api_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
            elif aid:
                api_url = f"https://api.bilibili.com/x/web-interface/view?aid={aid}"
            else:
                return ""

            data = None
            if self.session:
                try:
                    r = self.session.get(api_url, headers=headers, timeout=10)
                    if r.status_code == 200:
                        data = r.json()
                except Exception:
                    pass

            if not data and requests:
                try:
                    r = requests.get(api_url, headers=headers, timeout=10, verify=False)
                    if r.status_code == 200:
                        data = r.json()
                except Exception:
                    pass

            if data and data.get("code") == 0:
                return str(data["data"].get("cid", ""))

        except Exception:
            pass

        return ""

    def playerContent(self, flag, id, vipFlags=None):
        safe = {"parse": 0, "playUrl": "", "url": "", "header": ""}
        try:
            play_url = str(id or "")

            if not play_url:
                return safe

            # 已经是直链视频/音频
            if play_url.startswith("http") and self.isVideoFormat(play_url):
                return {
                    "parse": 0, "playUrl": "", "url": play_url,
                    "header": json.dumps({
                        "User-Agent": UA,
                        "Referer": self.host + "/",
                    }, ensure_ascii=False),
                }

            # B站嵌入页面 - 解析真实视频地址
            if "bilibili" in play_url.lower():
                video_url, audio_url, fmt = self._parse_bilibili_video(play_url)

                bilibili_header = json.dumps({
                    "User-Agent": UA,
                    "Referer": "https://www.bilibili.com/",
                    "Origin": "https://www.bilibili.com",
                }, ensure_ascii=False)

                if video_url and fmt == "normal":
                    # 普通格式：音视频合一
                    return {
                        "parse": 0,
                        "playUrl": "",
                        "url": video_url,
                        "header": bilibili_header,
                    }

                if video_url and fmt == "dash":
                    # DASH 格式：返回视频流
                    # 注意：大多数播放器不支持音视频分离的 DASH
                    # 所以尝试使用 B站的 .mp4 直链格式（通过不同 qn 参数）
                    # 先尝试返回视频流
                    return {
                        "parse": 0,
                        "playUrl": "",
                        "url": video_url,
                        "header": bilibili_header,
                    }

                # 解析失败，返回 iframe 让播放器嗅探
                return {
                    "parse": 1,
                    "playUrl": "",
                    "url": play_url,
                    "header": json.dumps({
                        "User-Agent": UA,
                        "Referer": self.host + "/",
                    }, ensure_ascii=False),
                }

            # 其他嵌入页
            if "iframe" in flag.lower() or "player" in flag.lower() or "youtube" in play_url.lower():
                return {
                    "parse": 1,
                    "playUrl": "",
                    "url": play_url,
                    "header": json.dumps({
                        "User-Agent": UA,
                        "Referer": self.host + "/",
                    }, ensure_ascii=False),
                }

            # 默认返回 URL
            return {
                "parse": 1,
                "playUrl": "",
                "url": play_url,
                "header": json.dumps({
                    "User-Agent": UA,
                    "Referer": self.host + "/",
                }, ensure_ascii=False),
            }
        except Exception:
            pass

        return safe

    # ==================== 本地代理 ====================

    def localProxy(self, param):
        url = param.get("url") or param.get("pic") or ""
        if isinstance(url, list):
            url = url[0] if url else ""
        if not url:
            return [404, "text/plain", b""]

        try:
            if not url.startswith("http"):
                if not url.startswith("/"):
                    url = "/" + url
                url = self.host + url
            if self.session:
                r = self.session.get(url, headers={
                    "User-Agent": UA,
                    "Referer": self.host + "/",
                    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                }, timeout=15)
                if r.status_code == 200 and r.content:
                    ct = r.headers.get("Content-Type", "image/jpeg")
                    return [200, ct, r.content]
        except Exception:
            pass
        return [404, "text/plain", b""]

    # ==================== 辅助方法 ====================

    @staticmethod
    def _page(pg):
        try:
            v = int(str(pg or "").strip())
            return v if v > 0 else 1
        except (ValueError, TypeError):
            return 1
