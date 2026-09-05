# coding: utf-8
# 站点: 蝶卡影视网 (https://www.diekawang.com)


import json
import base64
import re
from urllib.parse import quote, urljoin, unquote

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):

    def __init__(self):
        # __init__ 只做本地初始化，禁止网络请求，保证壳子首页秒出 class。
        self.extend = ""
        self.host = "https://www.diekawang.com"
        self.classes = [
            {"type_id": "1", "type_name": "电影"},
            {"type_id": "2", "type_name": "电视剧"},
            {"type_id": "3", "type_name": "综艺"},
            {"type_id": "4", "type_name": "动漫"},
            {"type_id": "457", "type_name": "短剧"},
            {"type_id": "462", "type_name": "体育"},
        ]
        self.filters = {
            "1": [
                {"key": "cate", "name": "类型", "value": [
                    {"n": "全部", "v": "0"},
                    {"n": "动作片", "v": "9"},
                    {"n": "喜剧片", "v": "10"},
                    {"n": "爱情片", "v": "11"},
                    {"n": "恐怖片", "v": "12"},
                    {"n": "剧情片", "v": "13"},
                    {"n": "科幻片", "v": "14"},
                    {"n": "惊悚片", "v": "15"},
                    {"n": "奇幻片", "v": "16"},
                    {"n": "动画片", "v": "17"},
                    {"n": "悬疑片", "v": "18"},
                    {"n": "冒险片", "v": "19"},
                    {"n": "纪录片", "v": "20"},
                    {"n": "战争片", "v": "21"},
                    {"n": "倫理片", "v": "460"},
                ]},
            ],
            "2": [
                {"key": "cate", "name": "类型", "value": [
                    {"n": "全部", "v": "0"},
                    {"n": "国产剧", "v": "22"},
                    {"n": "香港剧", "v": "23"},
                    {"n": "台湾剧", "v": "24"},
                    {"n": "欧美剧", "v": "25"},
                    {"n": "日本剧", "v": "26"},
                    {"n": "韩国剧", "v": "27"},
                    {"n": "泰国剧", "v": "28"},
                    {"n": "海外剧", "v": "29"},
                ]},
            ],
            "3": [
                {"key": "cate", "name": "类型", "value": [
                    {"n": "全部", "v": "0"},
                    {"n": "大陆综艺", "v": "30"},
                    {"n": "港台综艺", "v": "31"},
                    {"n": "日韩综艺", "v": "32"},
                    {"n": "欧美综艺", "v": "33"},
                    {"n": "海外综艺", "v": "34"},
                ]},
            ],
            "4": [
                {"key": "cate", "name": "类型", "value": [
                    {"n": "全部", "v": "0"},
                    {"n": "国产动漫", "v": "35"},
                    {"n": "日韩动漫", "v": "36"},
                    {"n": "欧美动漫", "v": "37"},
                    {"n": "海外动漫", "v": "38"},
                    {"n": "港台动漫", "v": "459"},
                ]},
            ],
            "457": [
                {"key": "cate", "name": "类型", "value": [
                    {"n": "全部", "v": "0"},
                    {"n": "漫剧", "v": "540"},
                    {"n": "玄幻", "v": "541"},
                    {"n": "剧情", "v": "542"},
                    {"n": "女性成长", "v": "543"},
                    {"n": "权谋", "v": "544"},
                    {"n": "豪门", "v": "545"},
                    {"n": "齐幻", "v": "546"},
                    {"n": "宫斗", "v": "547"},
                    {"n": "脑洞", "v": "548"},
                    {"n": "科幻", "v": "549"},
                    {"n": "冒险", "v": "550"},
                    {"n": "仙侠", "v": "551"},
                    {"n": "喜剧", "v": "552"},
                    {"n": "动作", "v": "553"},
                    {"n": "悬疑", "v": "554"},
                    {"n": "战神", "v": "555"},
                    {"n": "刑侦", "v": "556"},
                    {"n": "求生", "v": "557"},
                    {"n": "商战", "v": "558"},
                    {"n": "恐怖", "v": "559"},
                    {"n": "武侠", "v": "560"},
                    {"n": "爱情", "v": "561"},
                    {"n": "AI漫剧", "v": "562"},
                ]},
            ],
            "462": [
                {"key": "cate", "name": "类型", "value": [
                    {"n": "全部", "v": "0"},
                ]},
            ],
        }
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36",
            "Referer": self.host + "/",
        }

    def getName(self):
        return "蝶卡影视"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    # ==================== 内部工具模块 ====================

    def _cleanText(self, text):
        """清洗 HTML 标签和空白字符"""
        if not text:
            return ""
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _absUrl(self, url):
        """补全相对 URL"""
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("http"):
            return url
        return urljoin(self.host, url)

    def _decodeFile(self, file_str):
        """解码播放文件 URL: 去掉3字符前缀 -> base64解码 -> URL反编码"""
        if not file_str or len(file_str) <= 3:
            return ""
        try:
            raw = file_str[3:]
            decoded = base64.b64decode(raw).decode('utf-8', 'ignore')
            return unquote(decoded)
        except Exception:
            return ""

    def _makePlayHeader(self, url):
        """空防盗链头优先: 只保留 UA，避免 EXO 把错误 Referer/Origin 透传给第三方 CDN 分片"""
        return {"User-Agent": self.headers.get("User-Agent", "Mozilla/5.0")}

    def _parseListCards(self, html):
        """
        解析列表页卡片 (多级兜底)
        主选择器: div.moon-list-item > a.item.goLinklist
        语义锚点: href="/vod/player/0/{id}"
        兜底: 全页扫描 /vod/player/0/ 链接块
        """
        result = []
        seen_ids = set()

        # 主选择器: 匹配完整的卡片块
        # Pattern 1: 标准 moon-list-item 结构
        cards = re.findall(
            r'<div[^>]*class="[^"]*moon-list-item[^"]*"[^>]*>\s*'
            r'<a[^>]*href="/vod/player/0/(\d+)"[^>]*>(.*?)</a>',
            html, re.S
        )
        for vid, block in cards:
            if vid in seen_ids:
                continue
            # 提取标题: p.name 或 .item-title
            name = re.search(r'class="[^"]*name[^"]*item-title[^"]*"[^>]*>(.*?)</p>', block, re.S)
            if not name:
                name = re.search(r'class="[^"]*item-title[^"]*"[^>]*>(.*?)</p>', block, re.S)
            name = self._cleanText(name.group(1)) if name else ""
            if not name:
                continue
            # 提取图片: data-original > data-src > src
            pic = re.search(r'data-original="([^"]+)"', block)
            if not pic:
                pic = re.search(r'data-src="([^"]+)"', block)
            if not pic:
                pic = re.search(r'src="([^"]+)"', block)
            pic = self._absUrl(pic.group(1)) if pic else ""
            # 提取评分/备注: label.rate
            remark = re.search(r'class="[^"]*rate[^"]*"[^>]*>(.*?)</label>', block, re.S)
            remark = self._cleanText(remark.group(1)) if remark else ""
            # 打包轻量字段到 vod_id
            vod_id = vid + '|$|' + name + '|$|' + pic + '|$|' + remark
            result.append({
                "vod_id": vod_id,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": remark,
            })
            seen_ids.add(vid)

        # 兜底: 如果主选择器没匹配到，全页扫描 player 链接
        if not result:
            blocks = re.findall(
                r'<a[^>]*href="/vod/player/0/(\d+)"[^>]*class="[^"]*(?:item|goLinklist)[^"]*"[^>]*>(.*?)</a>',
                html, re.S
            )
            for vid, block in blocks:
                if vid in seen_ids:
                    continue
                name = re.search(r'<p[^>]*>(.*?)</p>', block, re.S)
                name = self._cleanText(name.group(1)) if name else ""
                if not name:
                    continue
                pic = re.search(r'data-original="([^"]+)"', block)
                if not pic:
                    pic = re.search(r'src="([^"]+)"', block)
                pic = self._absUrl(pic.group(1)) if pic else ""
                remark = re.search(r'class="[^"]*rate[^"]*"[^>]*>(.*?)</label>', block, re.S)
                remark = self._cleanText(remark.group(1)) if remark else ""
                vod_id = vid + '|$|' + name + '|$|' + pic + '|$|' + remark
                result.append({
                    "vod_id": vod_id,
                    "vod_name": name,
                    "vod_pic": pic,
                    "vod_remarks": remark,
                })
                seen_ids.add(vid)

        return result

    def _parseSearchCards(self, html):
        """
        解析搜索结果卡片
        主选择器: a.moon-item.seachlist
        语义锚点: href="/vod/player/0/{id}"
        """
        result = []
        seen_ids = set()

        cards = re.findall(
            r'<a[^>]*href="/vod/player/0/(\d+)"[^>]*class="[^"]*seachlist[^"]*"[^>]*>(.*?)</a>',
            html, re.S
        )
        for vid, block in cards:
            if vid in seen_ids:
                continue
            # 标题: h2
            name = re.search(r'<h2[^>]*>(.*?)</h2>', block, re.S)
            name = self._cleanText(name.group(1)) if name else ""
            if not name:
                continue
            # 图片
            pic = re.search(r'data-src="([^"]+)"', block)
            if not pic:
                pic = re.search(r'src="([^"]+)"', block)
            pic = self._absUrl(pic.group(1)) if pic else ""
            # 信息: label-list 中的 span (年份/类型/地区)
            info_spans = re.findall(r'<span[^>]*>(.*?)</span>', block, re.S)
            info_parts = [self._cleanText(s) for s in info_spans if self._cleanText(s)]
            remark = " ".join(info_parts[:3]) if info_parts else ""
            vod_id = vid + '|$|' + name + '|$|' + pic + '|$|' + remark
            result.append({
                "vod_id": vod_id,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": remark,
            })
            seen_ids.add(vid)

        return result

    def _getPageCount(self, html, default=99):
        """从"尾页"链接中提取总页数"""
        # 尾页链接格式: href="/vod/list/{last_page}/{type}/{sub_type}"
        last_page = re.search(r'href="/vod/list/(\d+)/\d+/\d+"[^>]*>[^<]*尾页', html)
        if last_page:
            try:
                return int(last_page.group(1))
            except ValueError:
                pass
        return default

    def _isNoResultPage(self, html):
        """检测无结果页 (排除 Vue 模板中的暂无数据占位符)"""
        no_result_patterns = [
            r'没有找到您想要的结果',
            r'没有找到.*结果',
            r'搜索无结果',
            r'暂无影片',
            r'没有搜到',
            r'无搜索结果',
        ]
        for pattern in no_result_patterns:
            if re.search(pattern, html):
                return True
        return False

    # ==================== 核心接口方法 ====================

    def homeContent(self, filter):
        """首页入口零网络，只返回本地 class/filters"""
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        """首页推荐数据"""
        try:
            url = f"{self.host}/vod/list/1/1/0"
            res = self.fetch(url, headers=self.headers)
            html = res.text
            return {"list": self._parseListCards(html)}
        except Exception:
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        """
        分类列表: /vod/list/{page}/{parent_type}/{sub_type}
        动态消费 pg 和 extend.cate
        """
        page = str(pg) if pg else "1"
        extend = extend or {}
        sub_type = extend.get("cate", "0") or "0"

        url = f"{self.host}/vod/list/{page}/{tid}/{sub_type}"
        try:
            res = self.fetch(url, headers=self.headers)
            html = res.text

            items = self._parseListCards(html)
            # 无结果检测: 仅在卡片为空时检查无结果提示
            if not items and self._isNoResultPage(html):
                return {
                    "list": [],
                    "page": int(page),
                    "pagecount": 1,
                    "limit": 10,
                    "total": 0,
                }
            pagecount = self._getPageCount(html)
            return {
                "list": items,
                "page": int(page),
                "pagecount": pagecount,
                "limit": 10,
                "total": pagecount * 10,
            }
        except Exception:
            return {
                "list": [],
                "page": int(page),
                "pagecount": 1,
                "limit": 10,
                "total": 0,
            }

    def detailContent(self, ids):
        """
        详情页: /vod/player/0/{vod_id}
        提取 temLineList JSON 构建播放树
        提取 vod 元信息 (name, pic, year, area, actor, director, score)
        """
        raw = str(ids[0])
        ps = raw.split('|$|')
        vod_id = ps[0]
        old_name = ps[1] if len(ps) > 1 else ''
        old_pic = ps[2] if len(ps) > 2 else ''
        old_remark = ps[3] if len(ps) > 3 else ''

        url = f"{self.host}/vod/player/0/{vod_id}"
        try:
            res = self.fetch(url, headers=self.headers)
            html = res.text
        except Exception:
            # 网络失败时返回列表阶段缓存的字段
            return {"list": [{
                "vod_id": raw,
                "vod_name": old_name or "视频",
                "vod_pic": old_pic,
                "vod_remarks": old_remark,
                "vod_play_from": "播放",
                "vod_play_url": "播放$" + vod_id,
            }]}

        # 提取 temLineList JSON
        vod_name = old_name
        vod_pic = old_pic
        vod_year = ""
        vod_area = ""
        vod_actor = ""
        vod_director = ""
        vod_score = ""
        vod_content = ""
        vod_remarks = old_remark

        # 提取名称: H1 标签 > item变量 > 列表缓存
        h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
        if h1_match:
            vod_name = self._cleanText(h1_match.group(1)) or vod_name

        # 提取图片: item变量 imgUrl > data-original
        img_match = re.search(r'imgUrl:\s*["\']([^"\']+)', html)
        if img_match:
            vod_pic = self._absUrl(img_match.group(1).replace('\\/', '/'))
        elif not vod_pic:
            img_match2 = re.search(r'data-original="([^"]+)"', html)
            if img_match2:
                vod_pic = self._absUrl(img_match2.group(1))

        # 提取评分: label-list 中的 din-condensed
        score_match = re.search(r'class="[^"]*din-condensed[^"]*"[^>]*>(.*?)</span>', html, re.S)
        if score_match:
            vod_score = self._cleanText(score_match.group(1))

        # 提取年份和地区: label-list 中的 span
        label_section = re.search(r'class="label-list"[^>]*>(.*?)</div>', html, re.S)
        if label_section:
            spans = re.findall(r'<span[^>]*>(.*?)</span>', label_section.group(1), re.S)
            span_texts = [self._cleanText(s) for s in spans if self._cleanText(s)]
            for txt in span_texts:
                if re.match(r'^\d{4}$', txt):
                    vod_year = txt
                elif txt != vod_score:
                    if not vod_area:
                        vod_area = txt

        # 提取导演: worker-name 标签后的内容
        director_section = re.search(
            r'class="worker-name"[^>]*>\s*导演\s*</a>\s*<div[^>]*>(.*?)</div>', html, re.S
        )
        if director_section:
            vod_director = self._cleanText(director_section.group(1))

        # 提取演员: worker-name 标签后的内容
        actor_section = re.search(
            r'class="worker-name"[^>]*>\s*演员\s*</a>\s*<div[^>]*>(.*?)</div>', html, re.S
        )
        if actor_section:
            vod_actor = self._cleanText(actor_section.group(1))

        # 从 meta keywords 提取演员 (兜底)
        if not vod_actor:
            meta_kw = re.search(r'<meta\s+name="keywords"\s+content="([^"]+)"', html)
            if meta_kw:
                kw_parts = meta_kw.group(1).split(',')
                # keywords 格式: 站名,剧名,类型,子类型,,演员列表
                if len(kw_parts) >= 6:
                    vod_actor = kw_parts[5]

        # 构建播放树
        play_from_list = []
        play_url_list = []

        tem_line_match = re.search(r'temLineList\s*=\s*(\[.*?\])\s*;', html, re.S)
        if tem_line_match:
            try:
                line_data = json.loads(tem_line_match.group(1))
                # 按 tag 分组 (通常只有一组)
                lines = {}
                line_order = []
                for ep in line_data:
                    tag = ep.get("tag", "播放") or "播放"
                    if tag not in lines:
                        lines[tag] = []
                        line_order.append(tag)
                    ep_name = ep.get("name", "") or ep.get("subTitle", "") or "播放"
                    ep_file = ep.get("file", "")
                    lines[tag].append(f"{ep_name}${ep_file}")

                for tag in line_order:
                    play_from_list.append(tag)
                    play_url_list.append("#".join(lines[tag]))
            except (json.JSONDecodeError, Exception):
                pass

        # 兜底: 如果没有提取到播放树，返回嗅探
        if not play_from_list:
            play_from_list.append("播放")
            play_url_list.append(f"播放${vod_id}")

        vod = {
            "vod_id": raw,
            "vod_name": vod_name or "视频",
            "vod_pic": vod_pic,
            "vod_year": vod_year,
            "vod_area": vod_area,
            "vod_actor": vod_actor,
            "vod_director": vod_director,
            "vod_score": vod_score,
            "vod_remarks": vod_remarks or vod_score,
            "vod_content": vod_content or vod_remarks,
            "vod_play_from": "$$$".join(play_from_list),
            "vod_play_url": "$$$".join(play_url_list),
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        """
        搜索: /public/auto/search1.html?keyword={keyword}
        搜索无分页，全部结果在第一页返回
        """
        if not key:
            return {"list": [], "page": 1}
        try:
            url = f"{self.host}/public/auto/search1.html?keyword={quote(key)}"
            res = self.fetch(url, headers=self.headers)
            html = res.text
            items = self._parseSearchCards(html)
            return {"list": items, "page": 1}
        except Exception:
            return {"list": [], "page": 1}

    def playerContent(self, flag, id, vipFlags):
        """
        播放解析: 解码 file 值获取 m3u8 直链
        file 格式: 3字符前缀 + base64(URL编码的m3u8地址)
        解码后返回 parse:0 直链
        """
        # 如果 id 本身是 m3u8/mp4 直链
        if id.endswith((".m3u8", ".mp4")) or id.startswith("http"):
            return {
                "parse": 0,
                "url": id,
                "header": self._makePlayHeader(id),
            }

        # 纯数字 ID 兜底: 嗅探
        if id.isdigit():
            return {
                "parse": 1,
                "url": f"{self.host}/vod/player/0/{id}",
                "header": self.headers,
            }

        # 解码 file 值
        decoded_url = self._decodeFile(id)
        if decoded_url and decoded_url.startswith("http"):
            return {
                "parse": 0,
                "url": decoded_url,
                "header": self._makePlayHeader(decoded_url),
            }

        # 解码失败，降级嗅探
        return {
            "parse": 1,
            "url": id,
            "header": self.headers,
        }

    def localProxy(self, param):
        pass

    def isVideoFormat(self, url):
        return bool(re.match(r'.*\.(m3u8|mp4)(\?.*)?$', url, re.I))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass
