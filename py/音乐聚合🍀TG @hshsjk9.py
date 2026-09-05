# -*- coding: utf-8 -*-
import re
import json
import base64
import urllib.parse

try:
    import requests as _requests
    _HAS_REQUESTS = True
except Exception:
    _requests = None
    _HAS_REQUESTS = False

try:
    from base.spider import Spider as _BaseSpider
except Exception:
    class _BaseSpider:
        pass


def _log(*args):
    try:
        print("音乐聚合", *args)
    except Exception:
        pass


def _b64encode(s):
    try:
        return base64.b64encode(str(s).encode("utf-8")).decode("ascii")
    except Exception:
        return ""


def _b64decode(s):
    try:
        return base64.b64decode(str(s)).decode("utf-8")
    except Exception:
        return ""


SITE = "https://music.iqwq.cn"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/150.0.0.0 Safari/537.36")

DEFAULT_HEADERS = {
    "User-Agent": UA,
    "Referer": SITE,
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

# 分类：数字 ID -> (平台标识, 显示名称)
_CATEGORY = {
    "1": ("qq",    "QQ音乐"),
    "2": ("1ting", "一听"),
}

# 每个平台的最佳搜索关键词 (经过实测, 返回有效结果)
# QQ音乐: 用具体歌名/热门词返回结果更多 (通用词如"流行"返回很少)
_PLATFORM_KEYWORDS = {
    "qq": [
        "孤勇者", "如愿", "稻香", "告白气球", "成都",
        "起风了", "漠河舞厅", "大鱼", "十年", "光年之外",
        "小半", "青花瓷", "演员", "童话", "遇见",
    ],
    "1ting": [
        "流行", "经典", "华语", "民谣", "治愈",
        "励志", "摇滚", "抖音", "怀旧", "轻音乐",
        "伤感", "纯音乐", "古风", "电子", "爵士",
    ],
}

# 每个平台的筛选选项 (QQ音乐用实测可用的关键词)
_PLATFORM_FILTERS = {
    "qq": [
        {"n": "孤勇者", "v": "孤勇者"}, {"n": "如愿", "v": "如愿"},
        {"n": "稻香", "v": "稻香"}, {"n": "告白气球", "v": "告白气球"},
        {"n": "成都", "v": "成都"}, {"n": "起风了", "v": "起风了"},
        {"n": "漠河舞厅", "v": "漠河舞厅"}, {"n": "大鱼", "v": "大鱼"},
        {"n": "十年", "v": "十年"}, {"n": "光年之外", "v": "光年之外"},
        {"n": "青花瓷", "v": "青花瓷"}, {"n": "演员", "v": "演员"},
        {"n": "小半", "v": "小半"}, {"n": "童话", "v": "童话"},
        {"n": "遇见", "v": "遇见"},
    ],
    "1ting": [
        {"n": "流行", "v": "流行"}, {"n": "经典", "v": "经典"},
        {"n": "华语", "v": "华语"}, {"n": "民谣", "v": "民谣"},
        {"n": "治愈", "v": "治愈"}, {"n": "励志", "v": "励志"},
        {"n": "摇滚", "v": "摇滚"}, {"n": "抖音", "v": "抖音"},
        {"n": "怀旧", "v": "怀旧"}, {"n": "轻音乐", "v": "轻音乐"},
        {"n": "伤感", "v": "伤感"}, {"n": "纯音乐", "v": "纯音乐"},
        {"n": "古风", "v": "古风"}, {"n": "电子", "v": "电子"},
        {"n": "爵士", "v": "爵士"},
    ],
}


class Spider(_BaseSpider):
    """双站音乐聚合 —— QQ音乐 + 一听"""

    name = "音乐聚合"

    def init(self, extend=""):
        _log("init ->", extend)
        self.host = SITE
        self.header = dict(DEFAULT_HEADERS)
        self.timeout = 15
        if _HAS_REQUESTS:
            self.session = _requests.Session()
            self.session.headers.update(self.header)

    def getName(self):
        return self.name

    def destroy(self):
        pass

    def isVideoFormat(self, url):
        if not url:
            return False
        return bool(re.search(r'\.(mp3|m4a|aac|ogg|wav)(\?|$)', url, re.I))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None

    # 网络请求
    def _http_post(self, url, data):
        """POST 请求，返回文本"""
        try:
            hdrs = dict(self.header)
            if _HAS_REQUESTS:
                sess = getattr(self, "session", None) or _requests
                r = sess.post(url, data=data, headers=hdrs,
                              timeout=self.timeout, verify=False)
                r.encoding = "utf-8"
                return r.text
            import urllib.request
            post_data = urllib.parse.urlencode(data).encode("utf-8")
            req = urllib.request.Request(url, data=post_data, headers=hdrs)
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as exc:
            _log("post err", exc)
            return ""

    # 搜索: iqwq.cn 聚合API
    def _search_songs(self, keyword, platform, page):
        """通过 iqwq.cn 搜索, 只返回有有效URL的歌曲"""
        try:
            data = {
                "input": str(keyword),
                "filter": "name",
                "type": platform,
                "page": str(page),
            }
            text = self._http_post(SITE, data)
            if not text:
                return []
            result = json.loads(text)
            raw_songs = result.get("data", []) or []

            valid = []
            for song in raw_songs:
                url = song.get("url", "") or ""
                if not url:
                    continue
                # 确保URL是音频格式
                if not re.search(r'\.(mp3|m4a|aac|ogg|wav)(\?|$)', url, re.I):
                    continue
                valid.append(song)
            return valid
        except Exception as exc:
            _log("search err", exc)
            return []

    def _song_to_vod(self, song, platform):
        """将搜索结果转换为 vod 格式"""
        title = song.get("title", "") or "未知"
        author = song.get("author", "") or ""
        pic = song.get("pic", "") or ""
        url = song.get("url", "") or ""
        lrc = song.get("lrc", "") or ""
        if isinstance(lrc, list):
            lrc = "\n".join(str(x) for x in lrc)

        # 修复图片URL格式 (如 https:////xxx -> https://xxx)
        if pic:
            pic = re.sub(r"^(https?:)//+", r"\1//", pic)

        song_info = json.dumps({
            "url": url,
            "title": title,
            "author": author,
            "pic": pic,
            "lrc": lrc,
            "type": platform,
        }, ensure_ascii=False)
        vod_id = _b64encode(song_info)

        return {
            "vod_id": vod_id,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": author,
        }

    # 首页
    def homeContent(self, filter=False):
        """首页：分类列表 + 推荐歌曲"""
        try:
            classes = [
                {"type_id": "1", "type_pid": "0", "type_name": "QQ音乐"},
                {"type_id": "2", "type_pid": "0", "type_name": "一听"},
            ]

            # 筛选: 每个平台使用各自的关键词
            filters = {}
            for tid, (platform, _) in _CATEGORY.items():
                kw_values = _PLATFORM_FILTERS.get(platform, [])
                if kw_values:
                    filters[tid] = [{
                        "key": "kw",
                        "name": "关键词",
                        "value": kw_values,
                    }]

            result = {"class": classes, "list": []}
            if filter:
                result["filters"] = filters

            # 推荐歌曲: 从两个平台各取一部分, 去重
            try:
                all_songs = []
                seen = set()
                # QQ音乐 - 用"孤勇者"+"如愿"两个关键词 (每首6-7首高质量歌曲)
                for kw in ["孤勇者", "如愿"]:
                    qq_songs = self._search_songs(kw, "qq", 1)
                    for s in qq_songs:
                        sig = f"{s.get('title','')}_{s.get('author','')}"
                        if sig not in seen:
                            seen.add(sig)
                            all_songs.append(("qq", s))
                # 一听 - 用"流行"关键词 (返回10首)
                ting_songs = self._search_songs("流行", "1ting", 1)
                for s in ting_songs:
                    sig = f"{s.get('title','')}_{s.get('author','')}"
                    if sig not in seen:
                        seen.add(sig)
                        all_songs.append(("1ting", s))
                result["list"] = [self._song_to_vod(s, p) for p, s in all_songs[:20]]
            except Exception:
                pass

            return result
        except Exception as exc:
            _log("homeContent err", exc)
            return {"class": [], "list": []}

    def homeVideoContent(self):
        """首页推荐"""
        result = {"list": []}
        try:
            all_songs = []
            seen = set()
            for kw in ["孤勇者", "如愿"]:
                qq_songs = self._search_songs(kw, "qq", 1)
                for s in qq_songs:
                    sig = f"{s.get('title','')}_{s.get('author','')}"
                    if sig not in seen:
                        seen.add(sig)
                        all_songs.append(("qq", s))
            ting_songs = self._search_songs("流行", "1ting", 1)
            for s in ting_songs:
                sig = f"{s.get('title','')}_{s.get('author','')}"
                if sig not in seen:
                    seen.add(sig)
                    all_songs.append(("1ting", s))
            result["list"] = [self._song_to_vod(s, p) for p, s in all_songs[:10]]
        except Exception:
            pass
        return result

    # 分类
    def categoryContent(self, tid, pg, filter=False, extend=None):
        """分类内容：各平台歌曲列表 (不足时自动加载更多关键词)"""
        extend = extend or {}
        try:
            page = int(pg) if pg else 1
        except Exception:
            page = 1

        platform = "qq"
        if str(tid) in _CATEGORY:
            platform, _ = _CATEGORY[str(tid)]

        # 获取关键词
        keyword = extend.get("kw", "") if extend else ""

        result = {
            "list": [],
            "page": page,
            "pagecount": 10,
            "limit": 20,
            "total": 200,
        }

        try:
            all_songs = []
            seen = set()

            def _add_songs(songs):
                for s in songs:
                    title = s.get("title", "")
                    author = s.get("author", "")
                    sig = f"{title}_{author}"
                    if sig not in seen:
                        seen.add(sig)
                        all_songs.append(s)

            if keyword:
                # 用户指定了关键词, 直接搜索
                songs = self._search_songs(keyword, platform, page)
                _add_songs(songs)
            else:
                # 没有指定关键词, 按页加载不同关键词
                keywords = _PLATFORM_KEYWORDS.get(platform, ["孤勇者"])
                # 每页加载3个关键词的结果, 确保数量和品种充足
                per_page = 3 if platform == "qq" else 2
                start_idx = (page - 1) * per_page
                kw_to_try = keywords[start_idx:start_idx + per_page]
                # 如果不足, 循环使用
                if len(kw_to_try) < per_page:
                    for kw in keywords:
                        if len(kw_to_try) >= per_page:
                            break
                        if kw not in kw_to_try:
                            kw_to_try.append(kw)

                for kw in kw_to_try:
                    songs = self._search_songs(kw, platform, 1)
                    _add_songs(songs)
                    if len(all_songs) >= 15:
                        break

            # 如果结果还是太少, 追加更多关键词
            if len(all_songs) < 8:
                keywords = _PLATFORM_KEYWORDS.get(platform, ["推荐"])
                for kw in keywords:
                    if kw == keyword:
                        continue
                    songs = self._search_songs(kw, platform, 1)
                    _add_songs(songs)
                    if len(all_songs) >= 15:
                        break

            if all_songs:
                result["list"] = [self._song_to_vod(s, platform) for s in all_songs]
                result["limit"] = len(all_songs)
                result["total"] = max(200, len(all_songs) * 10)
        except Exception as exc:
            _log("categoryContent err", exc)

        return result

    # 详情
    def detailContent(self, ids):
        """歌曲详情：解码 vod_id, 返回播放信息"""
        if not ids:
            return {"list": []}

        try:
            vid = str(ids)
            if isinstance(ids, (list, tuple)):
                vid = str(ids[0])
            vid = vid.split("$")[-1].strip()

            song_json = _b64decode(vid)
            if not song_json:
                return {"list": []}

            song = json.loads(song_json)
            title = song.get("title", "") or "未知"
            author = song.get("author", "") or ""
            pic = song.get("pic", "") or ""
            url = song.get("url", "") or ""
            lrc = song.get("lrc", "") or ""
            song_type = song.get("type", "") or "音乐"

            play_url = f"{title}${vid}"

            vod = {
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": author,
                "vod_year": "",
                "vod_area": song_type,
                "vod_content": f"歌手: {author}\n平台: {song_type}" if author else f"平台: {song_type}",
                "vod_play_from": "音乐播放",
                "vod_play_url": play_url,
            }
            return {"list": [vod]}
        except Exception as exc:
            _log("detailContent err", exc)
            return {"list": []}

    # 播放
    def playerContent(self, flag, id, vipFlags):
        """获取播放地址 — 直接返回音频直链, parse=0"""
        _log("playerContent ->", str(id)[:50] if id else "")
        try:
            vid = str(id).split("$")[-1].strip()

            song_json = _b64decode(vid)
            if song_json:
                song = json.loads(song_json)
                url = song.get("url", "")
                if url:
                    _log("播放地址:", url[:80])
                    return {
                        "parse": 0,
                        "url": url,
                        "header": {"User-Agent": UA, "Referer": SITE},
                        "playUrl": "",
                    }
        except Exception as exc:
            _log("playerContent err", exc)

        return {"parse": 0, "url": "", "header": {}, "playUrl": ""}

    # 搜索
    def searchContent(self, key, quick, pg="1"):
        """搜索歌曲 — 遍历两个平台合并结果, 去重"""
        if not key:
            return {"list": []}
        try:
            page = int(pg) if pg else 1

            vod_list = []
            seen_titles = set()

            for platform in ["qq", "1ting"]:
                songs = self._search_songs(key, platform, page)
                for song in songs:
                    title = song.get("title", "")
                    author = song.get("author", "")
                    sig = f"{title}_{author}"
                    if sig not in seen_titles:
                        seen_titles.add(sig)
                        vod_list.append(self._song_to_vod(song, platform))
                if len(vod_list) >= 20:
                    break

            return {"list": vod_list}
        except Exception as exc:
            _log("searchContent err", exc)
            return {"list": []}

    # 音乐接口 (MusicTvBoxMobile / MusicFree 兼容)
    def search(self, query, page, type):
        """音乐搜索接口"""
        data = []
        try:
            pg = int(page) if page else 1
            platform = "qq"
            if isinstance(type, str) and type in [p[0] for p in _CATEGORY.values()]:
                platform = type

            songs = self._search_songs(query, platform, pg)
            for song in songs:
                title = song.get("title", "") or "未知"
                author = song.get("author", "") or ""
                pic = song.get("pic", "") or ""
                url = song.get("url", "") or ""
                lrc = song.get("lrc", "")
                if isinstance(lrc, list):
                    lrc = "\n".join(str(x) for x in lrc)

                # 修复图片URL格式
                if pic:
                    pic = re.sub(r"^(https?:)//+", r"\1//", pic)

                song_info = json.dumps({
                    "url": url, "title": title, "author": author,
                    "pic": pic, "lrc": lrc, "type": platform,
                }, ensure_ascii=False)
                vod_id = _b64encode(song_info)

                data.append({
                    "id": vod_id,
                    "title": title,
                    "artist": author,
                    "artwork": pic,
                    "album": platform,
                    "ext": "",
                })
        except Exception:
            pass
        return {"isEnd": True, "data": data}

    def getMediaSource(self, id, ext, quality):
        """获取音频播放地址"""
        result = {"url": ""}
        try:
            song_json = _b64decode(str(id))
            if song_json:
                song = json.loads(song_json)
                url = song.get("url", "")
                if url:
                    result["url"] = url
                    result["headers"] = {"User-Agent": UA, "Referer": SITE}
        except Exception:
            pass
        return result

    def getLyric(self, id, ext):
        """获取歌词"""
        result = {"lyric": ""}
        try:
            song_json = _b64decode(str(id))
            if song_json:
                song = json.loads(song_json)
                result["lyric"] = song.get("lrc", "")
        except Exception:
            pass
        return result


if __name__ == "__main__":
    spider = Spider()
    spider.init()

    print("=" * 60)
    print(f"  {spider.getName()} — 测试")
    print("=" * 60)

    # 1. 首页
    print("\n[首页]")
    home = spider.homeContent(True)
    print(f"  分类: {len(home['class'])}")
    for c in home["class"]:
        print(f"    {c['type_id']} {c['type_name']}")
    print(f"  推荐: {len(home['list'])} 首")
    for item in home["list"][:3]:
        print(f"    [{item['vod_remarks'][:15]}] {item['vod_name'][:30]}")
        print(f"    pic: {item['vod_pic'][:80]}")

    # 2. 各分类
    for tid, name in [("1", "QQ音乐"), ("2", "一听")]:
        print(f"\n[分类 - {name}]")
        cat = spider.categoryContent(tid, 1, True, {})
        print(f"  歌曲数: {len(cat['list'])}")
        for item in cat["list"][:3]:
            print(f"    [{item['vod_remarks'][:15]}] {item['vod_name'][:30]}")

    # 3. 详情+播放
    print("\n[详情+播放]")
    if home["list"]:
        first = home["list"][0]
        detail = spider.detailContent([first["vod_id"]])
        if detail["list"]:
            vod = detail["list"][0]
            print(f"  标题: {vod['vod_name']}")
            print(f"  歌手: {vod['vod_remarks']}")
            print(f"  平台: {vod['vod_area']}")
            play_url = vod.get("vod_play_url", "")
            play_id = play_url.split("$")[-1] if "$" in play_url else play_url
            player = spider.playerContent("音乐播放", play_id, None)
            print(f"  parse: {player.get('parse')}")
            print(f"  播放: {player.get('url', '')[:80]}")

    # 4. 搜索
    print("\n[搜索 - 周杰伦]")
    search = spider.searchContent("周杰伦", False, "1")
    print(f"  结果: {len(search['list'])} 首")
    for item in search["list"][:5]:
        print(f"    [{item['vod_remarks'][:15]}] {item['vod_name'][:30]}")

    # 5. 音乐接口
    print("\n[音乐搜索 - 晴天 (QQ)]")
    ms = spider.search("晴天", 1, "qq")
    print(f"  结果: {len(ms.get('data', []))} 首")
    if ms.get("data"):
        d = ms["data"][0]
        print(f"  标题: {d['title']}")
        print(f"  歌手: {d['artist']}")
        print(f"  图片: {d['artwork'][:80]}")
        src = spider.getMediaSource(d["id"], "", "")
        print(f"  播放: {src.get('url', '')[:80]}")

    # 6. 无requests测试
    print("\n[无 requests 环境]")
    import music_station as mod
    mod._requests = None
    mod._HAS_REQUESTS = False
    s2 = mod.Spider()
    s2.init()
    c2 = s2.categoryContent("1", 1, True, {})
    print(f"  QQ音乐: {len(c2['list'])} 首")
    if c2["list"]:
        d2 = s2.detailContent([c2["list"][0]["vod_id"]])
        if d2["list"]:
            pu = d2["list"][0].get("vod_play_url", "")
            pid = pu.split("$")[-1] if "$" in pu else pu
            p2 = s2.playerContent("音乐播放", pid, None)
            print(f"  播放: {p2.get('url', '')[:80]}")

    print("\n" + "=" * 60)
    print("  测试完成!")
    print("=" * 60)