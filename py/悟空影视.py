# -*- coding: utf-8 -*-
"""
悟空影视爬虫
站点: https://www.yikucun.com
基于 MacCMS (苹果CMS) 程序，HTML 解析方式
OK影视 / 海阔视界 兼容版
"""

import re
import time
import json
import urllib.parse

import requests

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        pass


class Spider(BaseSpider):
    BASE_URL = "https://www.yikucun.com"
    
    # 分类映射
    TYPE_MAP = {
        "1": "电影",
        "2": "电视剧",
        "3": "综艺",
        "4": "动漫",
        "5": "短剧",
    }
    
    # 筛选条件 - 各分类的类型和地区
    FILTERS = {
        "1": {  # 电影
            "类型": ["全部", "动作", "喜剧", "爱情", "科幻", "恐怖", "剧情", "战争", "犯罪", "奇幻", "悬疑", "动画", "恐怖", "纪录片", "其他"],
            "地区": ["全部", "大陆", "香港", "台湾", "日本", "韩国", "美国", "法国", "英国", "德国", "泰国", "印度", "其他"],
            "年份": ["全部", "2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019", "2018", "2017", "2016", "2015", "2014", "2013", "2012", "2011", "2010"],
        },
        "2": {  # 电视剧
            "类型": ["全部", "古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作", "奇幻", "剧情", "历史", "经典", "乡村", "情景", "商战", "网剧", "其他"],
            "地区": ["全部", "内地", "韩国", "香港", "台湾", "日本", "美国", "泰国", "英国", "新加坡", "其他"],
            "年份": ["全部", "2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019", "2018", "2017", "2016", "2015", "2014", "2013", "2012", "2011", "2010"],
        },
        "3": {  # 综艺
            "类型": ["全部", "真人秀", "脱口秀", "访谈", "美食", "旅游", "选秀", "情感", "音乐", "舞蹈", "其他"],
            "地区": ["全部", "大陆", "香港", "台湾", "日本", "韩国", "欧美", "其他"],
            "年份": ["全部", "2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019", "2018", "2017", "2016", "2015"],
        },
        "4": {  # 动漫
            "类型": ["全部", "日本动漫", "国产动漫", "欧美动漫", "其他"],
            "地区": ["全部", "日本", "大陆", "美国", "其他"],
            "年份": ["全部", "2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019", "2018", "2017", "2016", "2015"],
        },
        "5": {  # 短剧
            "类型": ["全部", "其他"],
            "地区": ["全部", "其他"],
            "年份": ["全部", "2026", "2025", "2024", "2023"],
        },
    }
    
    def __init__(self):
        super().__init__()
        self.name = ""
        self.error_play_url = "https://kjjsaas-sh.oss-cn-shanghai.aliyuncs.com/u/3401405881/20240818-936952-fc31b16575e80a7562cdb1f81a39c6b0.mp4"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.yikucun.com/",
            "Connection": "keep-alive",
        })
        self._init_cookies()
    
    def getName(self):
        return self.name
    
    def init(self, extend="{}"):
        try:
            self.extend = json.loads(extend)
            self.name = self.extend.get("name", "")
        except Exception as e:
            print(e)
            self.extend = {}
    
    def _init_cookies(self):
        """初始化 cookies（处理 508 反爬）"""
        try:
            r = self.session.get(self.BASE_URL, timeout=10, verify=False)
            if r.status_code == 508:
                time.sleep(1)
                self.session.get(self.BASE_URL, timeout=10, verify=False)
        except Exception:
            pass
    
    def _get(self, url, **kwargs):
        """GET 请求，自动处理 508"""
        try:
            r = self.session.get(url, timeout=15, verify=False, **kwargs)
            if r.status_code == 508:
                time.sleep(0.5)
                r = self.session.get(url, timeout=15, verify=False, **kwargs)
            r.encoding = "utf-8"
            return r
        except Exception as e:
            class FakeResp:
                status_code = 500
                text = str(e)
            return FakeResp()
    
    def homeContent(self, filter):
        """首页 - 返回分类和推荐"""
        result = {
            "class": [],
            "filters": {},
            "list": [],
            "parse": 0,
            "jx": 0,
        }
        
        # 分类列表
        for tid, name in self.TYPE_MAP.items():
            result["class"].append({
                "type_id": tid,
                "type_name": name,
            })
        
        # 筛选条件
        for tid, flist in self.FILTERS.items():
            result["filters"][tid] = []
            for fname, fvalues in flist.items():
                result["filters"][tid].append({
                    "key": fname,
                    "name": fname,
                    "value": [{"n": v, "v": v} for v in fvalues],
                })
        
        # 首页推荐
        try:
            r = self._get(f"{self.BASE_URL}/")
            if r.status_code == 200:
                result["list"] = self._parse_list(r.text)
        except Exception:
            pass
        
        return result
    
    def categoryContent(self, tid, pg, filter, extend):
        """分类页"""
        result = {
            "list": [],
            "parse": 0,
            "jx": 0,
        }
        
        # URL 格式: 12个位置，用 - 分隔
        # 位置: 1=tid, 2=地区, 3=空, 4=类型, 5=空, 6=空, 7=空, 8=空, 9=页码, 10=空, 11=空, 12=年份
        area = extend.get("地区", "") if isinstance(extend, dict) else ""
        type_val = extend.get("类型", "") if isinstance(extend, dict) else ""
        year = extend.get("年份", "") if isinstance(extend, dict) else ""
        
        if area == "全部":
            area = ""
        if type_val == "全部":
            type_val = ""
        if year == "全部":
            year = ""
        
        area_enc = urllib.parse.quote(area) if area else ""
        type_enc = urllib.parse.quote(type_val) if type_val else ""
        
        # 12个位置
        parts = [
            tid,            # 1
            area_enc,       # 2
            "",             # 3
            type_enc,       # 4
            "",             # 5
            "",             # 6
            "",             # 7
            "",             # 8
            str(pg),        # 9 页码
            "",             # 10
            "",             # 11
            year,           # 12 年份
        ]
        
        url = f"{self.BASE_URL}/ucusw/{'-'.join(parts)}.html"
        
        try:
            r = self._get(url)
            if r.status_code == 200:
                result["list"] = self._parse_list(r.text)
        except Exception:
            pass
        
        return result
    
    def detailContent(self, ids):
        """详情页"""
        result = {
            "list": [],
            "parse": 0,
            "jx": 0,
        }
        
        vid = ids[0]
        url = f"{self.BASE_URL}/ucudt/{vid}.html"
        
        try:
            r = self._get(url)
            if r.status_code == 200:
                detail = self._parse_detail(r.text, vid)
                if detail:
                    result["list"].append(detail)
        except Exception:
            pass
        
        return result
    
    def searchContent(self, key, quick, pg="1"):
        """搜索"""
        result = {
            "list": [],
            "parse": 0,
            "jx": 0,
        }
        
        try:
            # 搜索 URL: /ucusc/-------------.html?wd=关键词
            # 分页: /ucusc/-------------(页码).html?wd=关键词
            if int(pg) > 1:
                search_url = f"{self.BASE_URL}/ucusc/-------------{pg}.html?wd={urllib.parse.quote(key)}"
            else:
                search_url = f"{self.BASE_URL}/ucusc/-------------.html?wd={urllib.parse.quote(key)}"
            r = self._get(search_url)
            if r.status_code == 200:
                result["list"] = self._parse_list(r.text)
        except Exception:
            pass
        
        return result
    
    def playerContent(self, flag, id, vipFlags):
        """播放页 - 获取播放地址"""
        result = {
            "url": self.error_play_url,
            "parse": 0,
            "jx": 0,
            "header": {},
        }
        
        try:
            # id 格式: 视频ID-线路ID-集数ID
            parts = id.split("-")
            if len(parts) >= 3:
                vid, sid, nid = parts[0], parts[1], parts[2]
                play_url = f"{self.BASE_URL}/ucupy/{vid}-{sid}-{nid}.html"
                r = self._get(play_url)
                if r.status_code == 200:
                    url = self._parse_play_url(r.text)
                    if url:
                        result["url"] = url
                        result["parse"] = 0
        except Exception:
            pass
        
        return result
    
    def localProxy(self, params):
        return 0
    
    def _parse_list(self, html):
        """解析列表页"""
        items = []
        
        # 找到所有 class="name" 的标题，然后往前找最近的图片
        name_pattern = r'class="name"[^>]*>\s*<a[^>]*href="/ucudt/(\d+)\.html"[^>]*>([^<]+)</a>'
        
        # 先找出所有 name 的位置
        name_matches = list(re.finditer(name_pattern, html))
        
        seen = set()
        for i, m in enumerate(name_matches):
            vid = m.group(1)
            name = m.group(2).strip()
            
            if vid in seen:
                continue
            seen.add(vid)
            
            # 往前找最近的图片（在这个 name 之前）
            pos = m.start()
            start = max(0, pos - 2000)
            segment = html[start:pos]
            
            # 找所有图片
            img_matches = re.findall(r'<img[^>]*src="([^"]+)"', segment)
            pic = img_matches[-1] if img_matches else ""
            
            if pic and not pic.startswith("http"):
                pic = "https:" + pic if pic.startswith("//") else pic
            
            # 找备注
            remarks = ""
            rgba_match = re.search(r'class="rgba[^"]*"[^>]*>([^<]+)</span>', segment)
            if rgba_match:
                remarks = rgba_match.group(1).strip()
            
            items.append({
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": remarks,
            })
        
        return items[:30]
    
    def _parse_detail(self, html, vid):
        """解析详情页"""
        detail = {
            "vod_id": vid,
            "vod_name": "",
            "vod_pic": "",
            "type_name": "",
            "vod_year": "",
            "vod_area": "",
            "vod_remarks": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": "",
            "vod_play_from": "",
            "vod_play_url": "",
        }
        
        # 标题
        title_match = re.search(r'<title>《([^》]+)》', html)
        if title_match:
            detail["vod_name"] = title_match.group(1).strip()
        
        # 图片
        pic_match = re.search(r'og:image"[^>]*content="([^"]+)"', html)
        if pic_match:
            pic = pic_match.group(1)
            if not pic.startswith("http"):
                pic = "https:" + pic if pic.startswith("//") else pic
            detail["vod_pic"] = pic
        
        # 主演
        actor_match = re.search(r'<dt>主演[：:]</dt>\s*<dd>(.*?)</dd>', html, re.DOTALL)
        if actor_match:
            actors = re.sub(r'<[^>]+>', '', actor_match.group(1)).strip()
            actors = actors.replace('&nbsp;', ' ').replace('\xa0', ' ')
            detail["vod_actor"] = actors
        
        # 导演
        dir_match = re.search(r'<dt>导演[：:]</dt>\s*<dd>(.*?)</dd>', html, re.DOTALL)
        if dir_match:
            directors = re.sub(r'<[^>]+>', '', dir_match.group(1)).strip()
            directors = directors.replace('&nbsp;', ' ').replace('\xa0', ' ').strip()
            # 隐晦水印
            import base64
            wm = base64.b64decode(b'5pif5rKz').decode('utf-8')
            if directors:
                directors = directors + ' ' + wm
            else:
                directors = wm
            detail["vod_director"] = directors
        
        # 类型
        type_match = re.search(r'<dt>类型[：:]</dt>\s*<dd>(.*?)</dd>', html, re.DOTALL)
        if type_match:
            type_name = re.sub(r'<[^>]+>', '', type_match.group(1)).strip()
            type_name = type_name.replace('&nbsp;', ' ').replace('\xa0', ' ').strip()
            detail["type_name"] = type_name
        
        # 地区
        area_match = re.search(r'<dt>地区[：:]</dt>\s*<dd>(.*?)</dd>', html, re.DOTALL)
        if area_match:
            area = re.sub(r'<[^>]+>', '', area_match.group(1)).strip()
            area = area.replace('&nbsp;', ' ').replace('\xa0', ' ').strip()
            detail["vod_area"] = area
        
        # 年代
        year_match = re.search(r'<dt>年代[：:]</dt>\s*<dd>(.*?)</dd>', html, re.DOTALL)
        if year_match:
            year = re.sub(r'<[^>]+>', '', year_match.group(1)).strip()
            year = year.replace('&nbsp;', ' ').replace('\xa0', ' ').strip()
            detail["vod_year"] = year
        
        # 备注/状态
        remark_match = re.search(r'<dt>备注[：:]</dt>\s*<dd>(.*?)</dd>', html, re.DOTALL)
        if remark_match:
            detail["vod_remarks"] = re.sub(r'<[^>]+>', '', remark_match.group(1)).strip()
        
        # 简介
        desc_match = re.search(r'<dt>剧情[：:]</dt>\s*<dd>(.*?)</dd>', html, re.DOTALL)
        if desc_match:
            content = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip()
            content = content.replace("详细", "").strip()
            detail["vod_content"] = content
        
        # 播放源和播放地址
        # 1. 从 tab2 提取线路 id -> 名称 映射 (按顺序)
        source_order = []
        tab_match = re.search(r'class="tab2">(.*?)</dt>', html, re.DOTALL)
        if tab_match:
            tab_html = tab_match.group(1)
            source_pattern = r'<span[^>]*id="([^"]+)"[^>]*>([^<]+)</span>'
            source_matches = re.findall(source_pattern, tab_html)
            for sid, sname in source_matches:
                source_order.append((sid, sname.strip()))
        
        # 2. 定位到 content 区域
        source_eps = {}
        content_match = re.search(r'<div[^>]*id="content"[^>]*>(.*?)</div>\s*</div>', html, re.DOTALL)
        if content_match:
            content = content_match.group(1)
            
            # 用 <dd 分割，逐个处理
            dd_parts = re.split(r'<dd\s+', content)
            for part in dd_parts[1:]:
                class_match = re.search(r'class="([^"]+)"', part)
                if not class_match:
                    continue
                dd_class = class_match.group(1)
                
                if 'mod' not in dd_class:
                    continue
                
                source_key = dd_class.replace('mod', '').strip()
                if not source_key:
                    continue
                
                # 找这个 dd 里的所有集数
                ep_pattern = r'href="/ucupy/(\d+)-(\d+)-(\d+)\.html"[^>]*>([^<]+)<'
                ep_matches = re.findall(ep_pattern, part)
                
                if ep_matches:
                    eps = []
                    for evid, esid, enid, ename in ep_matches:
                        eps.append(f"{ename.strip()}${evid}-{esid}-{enid}")
                    source_eps[source_key] = "#".join(eps)
        
        # 3. 按 source_order 的顺序组装结果
        play_from_list = []
        play_url_list = []
        for source_key, source_name in source_order:
            if source_key in source_eps:
                play_from_list.append(source_name)
                play_url_list.append(source_eps[source_key])
        
        if play_from_list:
            detail["vod_play_from"] = "$$$".join(play_from_list)
            detail["vod_play_url"] = "$$$".join(play_url_list)
        
        # 如果没找到播放列表，用默认线路名
        if not detail["vod_play_from"]:
            detail["vod_play_from"] = "速播大屏"
            detail["vod_play_url"] = f"第01集${vid}-1-1"
        
        return detail
    
    def _parse_play_url(self, html):
        """解析播放地址"""
        # 从 player_aaaa 变量中提取
        idx = html.find('player_aaaa=')
        if idx >= 0:
            eq_idx = html.find('=', idx)
            if eq_idx >= 0:
                end_idx = html.find('</script>', eq_idx)
                if end_idx > 0:
                    json_str = html[eq_idx+1:end_idx].strip()
                    if json_str.endswith(';'):
                        json_str = json_str[:-1].strip()
                    try:
                        data = json.loads(json_str)
                        url = data.get("url", "")
                        if url:
                            return url
                    except Exception:
                        pass
        
        # 备用：直接找 m3u8
        url_match = re.search(r'"url"\s*:\s*"(https?://[^"]+\.m3u8[^"]*)"', html)
        if url_match:
            url = url_match.group(1).replace("\\/", "/").replace("\\", "")
            return url
        
        return ""


def main():
    """测试用"""
    spider = Spider()
    spider.init('{}')
    
    print("=== homeContent 测试 ===")
    result = spider.homeContent({})
    print(f"分类数: {len(result['class'])}")
    print(f"首页推荐: {len(result['list'])} 个")
    for item in result['list'][:3]:
        print(f"  {item['vod_id']}: {item['vod_name']}")
    
    print()
    print("=== categoryContent 测试 (电视剧) ===")
    result = spider.categoryContent("2", "1", "", {})
    print(f"结果数: {len(result['list'])} 个")
    for item in result['list'][:3]:
        print(f"  {item['vod_id']}: {item['vod_name']}")
    
    print()
    print("=== searchContent 测试 (千香) ===")
    result = spider.searchContent("千香", False, "1")
    print(f"结果数: {len(result['list'])} 个")
    for item in result['list'][:3]:
        print(f"  {item['vod_id']}: {item['vod_name']}")
    
    if result["list"]:
        vid = result["list"][0]["vod_id"]
        print(f"\n=== detailContent 测试 ({vid}) ===")
        detail_result = spider.detailContent([vid])
        if detail_result["list"]:
            d = detail_result["list"][0]
            print(f"  标题: {d['vod_name']}")
            print(f"  主演: {d['vod_actor'][:50]}...")
            print(f"  线路: {d['vod_play_from']}")
            sources = d['vod_play_from'].split('$$$')
            print(f"  线路数: {len(sources)}")
            
            # 播放测试
            urls = d['vod_play_url'].split('$$$')
            first_ep = urls[0].split('#')[0]
            ep_id = first_ep.split('$')[1] if '$' in first_ep else first_ep
            print(f"\n=== playerContent 测试 ({ep_id}) ===")
            play_result = spider.playerContent(sources[0], ep_id, [])
            print(f"  parse: {play_result['parse']}")
            print(f"  url: {play_result['url'][:80] if play_result['url'] else '无'}...")


if __name__ == "__main__":
    main()
