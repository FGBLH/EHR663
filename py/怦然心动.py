# -*- coding: utf-8 -*-
# 爬虫源: 怦然心动 (prshinezenx.blog)
# 站点类型: SPA + 服务端渲染，数据通过 Base64 编码嵌入 HTML
# 开发者: AI Assistant
# 日期: 2026-07-22

import re
import json
import base64
from urllib.parse import urljoin, quote

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://prshinezenx.blog"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9"
        }
        # 分类列表（从首页提取，本地硬编码保证首页秒出）
        self.classes = [
            {"type_id": "43", "type_name": "国产精选"},
            {"type_id": "31", "type_name": "束缚玩法"},
            {"type_id": "35", "type_name": "中字专区"},
            {"type_id": "33", "type_name": "女优精选"},
            {"type_id": "53", "type_name": "传媒拍摄"},
            {"type_id": "29", "type_name": "变性纪实"},
            {"type_id": "21", "type_name": "同志日常"},
            {"type_id": "23", "type_name": "百合情境"},
            {"type_id": "39", "type_name": "欧美精选"},
            {"type_id": "45", "type_name": "虚拟换脸"},
            {"type_id": "47", "type_name": "少女幻想"},
            {"type_id": "49", "type_name": "主播日记"},
            {"type_id": "51", "type_name": "约会实录"},
            {"type_id": "55", "type_name": "伦理剧场"},
            {"type_id": "57", "type_name": "黑料档案"},
            {"type_id": "63", "type_name": "自拍实录"},
        ]
        # 无筛选功能
        self.filters = {}

    def getName(self):
        return "怦然心动"

    def getDependence(self):
        return []

    def init(self, extend=""):
        """初始化，零网络"""
        pass

    def _fetch(self, url):
        """请求页面，返回 HTML 文本"""
        try:
            rsp = self.fetch(url, headers=self.headers, timeout=15000)
            if rsp and hasattr(rsp, 'text'):
                return rsp.text
            return None
        except Exception:
            return None

    def _extract_vod_data(self, html):
        """从 HTML 中提取 window.__vod_data__ 的 Base64 数据并解码"""
        if not html:
            return None
        pattern = r"const binaryStr = atob\('([^']+)'\)"
        match = re.search(pattern, html)
        if not match:
            return None
        base64_str = match.group(1)
        try:
            json_str = base64.b64decode(base64_str).decode('utf-8')
            return json.loads(json_str)
        except Exception:
            return None

    def _parse_list(self, items):
        """解析视频列表项，打包数据到 vod_id 以便详情页快速展示"""
        if not items:
            return []
        result = []
        for item in items:
            vod_id = str(item.get("vod_id", ""))
            if not vod_id:
                continue
            vod_name = item.get("vod_name", "未知标题")
            vod_pic = item.get("vod_pic", "")
            if vod_pic and not vod_pic.startswith("http"):
                vod_pic = urljoin(self.host, vod_pic)
            vod_remark = item.get("vod_duration", "")
            type_id = str(item.get("type_id", ""))
            # 打包数据到 vod_id，方便详情页快速返回
            packed_id = f"{vod_id}|$|{vod_name}|$|{vod_pic}|$|{vod_remark}|$|{type_id}"
            result.append({
                "vod_id": packed_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_remarks": vod_remark,
            })
        return result

    def homeContent(self, filter=False):
        """首页：返回分类列表，零网络"""
        return {
            "class": self.classes,
            "filters": self.filters if filter else {}
        }

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        """首页推荐视频"""
        html = self._fetch(self.host + "/")
        if not html:
            return {"list": []}
        data = self._extract_vod_data(html)
        if not data:
            return {"list": []}
        items = data.get("other_request_data", {}).get("random_list", [])
        if not items:
            items = data.get("request_data", {}).get("list", [])
        return {"list": self._parse_list(items[:20])}

    def categoryContent(self, tid, pg=1, filter=False, extend=None):
        """分类列表页"""
        page = pg or 1
        url = f"{self.host}/vodlist/type/{tid}/keyword/all/orderby/default/page/{page}.html"
        html = self._fetch(url)
        if not html:
            return {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}

        data = self._extract_vod_data(html)
        if not data:
            return {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}

        items = data.get("request_data", {}).get("list", [])
        total = data.get("request_data", {}).get("total", 0)
        limit = data.get("limit", 20)
        total_pages = (total + limit - 1) // limit if total > 0 else 1

        return {
            "list": self._parse_list(items),
            "page": page,
            "pagecount": total_pages,
            "limit": limit,
            "total": total
        }

    def detailContent(self, ids):
        """视频详情 - 从打包的 vod_id 中解析数据，快速返回"""
        if not ids:
            return {"list": []}
        raw = str(ids[0])

        # 解析打包的数据: vod_id|$|vod_name|$|vod_pic|$|vod_remark|$|type_id
        parts = raw.split("|$|")
        if len(parts) >= 5:
            vod_id = parts[0]
            vod_name = parts[1] if len(parts) > 1 else "未知标题"
            vod_pic = parts[2] if len(parts) > 2 else ""
            vod_remark = parts[3] if len(parts) > 3 else ""
            type_id = parts[4] if len(parts) > 4 else ""
        else:
            # 兼容旧格式：直接传数字ID
            vod_id = raw
            vod_name = ""
            vod_pic = ""
            vod_remark = ""
            type_id = ""

        # 获取播放地址：请求详情页提取 vod_play_url
        if type_id:
            detail_url = f"{self.host}/voddetail/type/{type_id}/id/{vod_id}.html"
        else:
            detail_url = f"{self.host}/voddetail/type/all/id/{vod_id}.html"

        html = self._fetch(detail_url)
        play_page = ""
        if html:
            data = self._extract_vod_data(html)
            if data:
                vod_info = data.get("vod_info", {})
                play_page = vod_info.get("vod_play_url", "")
                if not vod_name:
                    vod_name = vod_info.get("vod_name", "未知标题")
                if not vod_pic:
                    vod_pic = vod_info.get("vod_pic", "")
                if not vod_remark:
                    vod_remark = vod_info.get("vod_duration", "")

        if not play_page:
            return {
                "list": [{
                    "vod_id": vod_id,
                    "vod_name": vod_name or "未知标题",
                    "vod_pic": vod_pic,
                    "vod_remarks": vod_remark,
                    "vod_content": "",
                    "vod_play_from": "播放",
                    "vod_play_url": ""
                }]
            }

        # 如果是 ao jie xi 包装，提取真实 m3u8
        if "aojiexi.com" in play_page:
            match = re.search(r'url=([^&]+)', play_page)
            if match:
                real_url = match.group(1)
                real_url = re.sub(r'%([0-9A-Fa-f]{2})', lambda m: chr(int(m.group(1), 16)), real_url)
                play_page = real_url

        # 构造播放数据：单线路单集
        # 格式参考 tmcrownxlift 成功案例
        return {
            "list": [{
                "vod_id": vod_id,
                "vod_name": vod_name or "未知标题",
                "vod_pic": vod_pic,
                "vod_remarks": vod_remark,
                "vod_content": "",
                "vod_play_from": "播放",
                "vod_play_url": "播放$" + play_page
            }]
        }

    def searchContent(self, key, quick=False, pg="1"):
        """搜索"""
        if not key:
            return {"list": []}
        page = pg or 1
        url = f"{self.host}/vodlist/type/all/keyword/{quote(key)}/orderby/default/page/{page}.html"
        html = self._fetch(url)
        if not html:
            return {"list": []}
        data = self._extract_vod_data(html)
        if not data:
            return {"list": []}
        items = data.get("request_data", {}).get("list", [])
        return {"list": self._parse_list(items)}

    def playerContent(self, flag, vid, vipFlags=None):
        """播放地址解析"""
        if not vid:
            return {"parse": 0, "url": ""}

        if vid.endswith((".m3u8", ".mp4")):
            return {"parse": 0, "url": vid, "header": self.headers}

        if "aojiexi.com" in vid:
            match = re.search(r'url=([^&]+)', vid)
            if match:
                real_url = match.group(1)
                real_url = re.sub(r'%([0-9A-Fa-f]{2})', lambda m: chr(int(m.group(1), 16)), real_url)
                return {"parse": 0, "url": real_url, "header": self.headers}

        if vid.startswith("http"):
            html = self._fetch(vid)
            if html:
                match = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html)
                if match:
                    return {"parse": 0, "url": match.group(0), "header": self.headers}

        return {"parse": 1, "url": vid}

    def isVideoFormat(self, url):
        if not url:
            return False
        return url.endswith((".m3u8", ".mp4", ".m3u8?"))

    def destroy(self):
        pass