# coding=utf-8
# 文件名: test.py
# 描述: 萝莉AV爬虫 - 修正版

from base.spider import Spider
import re
import json
import urllib.parse

class Spider(Spider):
    def getName(self):
        return "萝莉AV"
    
    def init(self, extend=""):
        self.host = "https://212602.luoliav.cc"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': self.host,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        # 分类列表 - 根据页面导航栏
        self.classes = [
            {"type_name": "国产精选", "type_id": "1"},
            {"type_name": "日韩AV", "type_id": "2"},
            {"type_name": "蓝光超清", "type_id": "3"},
            {"type_name": "欧美精品", "type_id": "4"},
            {"type_name": "异族风情", "type_id": "5"},
            {"type_name": "动漫专区", "type_id": "6"},
        ]
    
    def homeContent(self, filter):
        """返回分类列表"""
        result = {}
        result["class"] = self.classes
        return result
    
    def homeVideoContent(self):
        """首页推荐视频"""
        try:
            url = f"{self.host}/index.html"
            rsp = self.fetch(url, headers=self.headers)
            html = rsp.text
            
            videos = self._parse_video_list(html)
            print(f"首页解析到 {len(videos)} 个视频")
            
            return {"list": videos}
        except Exception as e:
            print(f"首页视频解析错误: {e}")
            return {"list": []}
    
    def categoryContent(self, tid, pg, filter, extend):
        """分类页面内容"""
        try:
            # 构建分类URL
            url = f"{self.host}/list.php?cid={tid}&page={pg}"
            print(f"分类页面URL: {url}")
            
            rsp = self.fetch(url, headers=self.headers)
            html = rsp.text
            
            # 解析视频列表
            videos = self._parse_video_list(html)
            
            # 解析分页信息
            pagecount = int(pg)
            # 查找分页链接
            pagination_pattern = r'<a href="list\.php\?cid=' + tid + r'&amp;page=(\d+)">(\d+)</a>'
            page_matches = re.findall(pagination_pattern, html)
            if page_matches:
                pages = [int(p[1]) for p in page_matches]
                if pages:
                    pagecount = max(pages)
            else:
                # 如果找不到分页，假设有3页
                pagecount = int(pg) + 2
            
            print(f"分类解析完成: 第 {pg} 页，共 {pagecount} 页，找到 {len(videos)} 个视频")
            
            return {
                "list": videos,
                "page": int(pg),
                "pagecount": pagecount,
                "limit": 30,
                "total": len(videos) * pagecount
            }
        except Exception as e:
            print(f"分类页面解析错误: {e}")
            return {
                "list": [],
                "page": int(pg),
                "pagecount": 1,
                "limit": 30,
                "total": 0
            }
    
    def _parse_video_list(self, html):
        """解析视频列表的通用方法"""
        videos = []
        
        # 找到所有视频项
        # 模式：<div class="group ... item"> ... </div>
        pattern = r'<div[^>]*class="[^"]*group[^"]*item[^"]*"[^>]*>(.*?)</div>\s*</div>\s*</div>'
        items = re.findall(pattern, html, re.DOTALL)
        
        if not items:
            # 备选模式：更简单的匹配
            pattern = r'<div class="group[^"]*item[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>.*?<img[^>]*data-original="([^"]+)"[^>]*>.*?<a[^>]*class="[^"]*font-bold[^"]*"[^>]*>([^<]+)</a>'
            matches = re.findall(pattern, html, re.DOTALL)
            for match in matches:
                vod_id = match[0]
                if not vod_id.startswith('http'):
                    if vod_id.startswith('/'):
                        vod_id = self.host + vod_id
                    else:
                        vod_id = self.host + '/' + vod_id
                
                # 去掉URL中的时间戳参数
                vod_id = re.sub(r'\?.*$', '', vod_id)
                
                vod_pic = match[1]
                if vod_pic and not vod_pic.startswith('http'):
                    if vod_pic.startswith('//'):
                        vod_pic = 'https:' + vod_pic
                    elif vod_pic.startswith('/'):
                        vod_pic = self.host + vod_pic
                
                vod_name = match[2].strip()
                
                videos.append({
                    "vod_id": vod_id,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": ""
                })
            return videos
        
        # 逐个解析每个视频项
        for item in items:
            try:
                # 提取视频链接
                href_match = re.search(r'<a[^>]*href="([^"]+)"[^>]*>', item)
                if not href_match:
                    continue
                vod_id = href_match.group(1)
                if not vod_id.startswith('http'):
                    if vod_id.startswith('/'):
                        vod_id = self.host + vod_id
                    else:
                        vod_id = self.host + '/' + vod_id
                
                # 去掉URL中的时间戳参数
                vod_id = re.sub(r'\?.*$', '', vod_id)
                
                # 提取封面图
                img_match = re.search(r'<img[^>]*data-original="([^"]+)"[^>]*>', item)
                if not img_match:
                    img_match = re.search(r'<img[^>]*src="([^"]+)"[^>]*>', item)
                if not img_match:
                    continue
                vod_pic = img_match.group(1)
                if vod_pic and not vod_pic.startswith('http'):
                    if vod_pic.startswith('//'):
                        vod_pic = 'https:' + vod_pic
                    elif vod_pic.startswith('/'):
                        vod_pic = self.host + vod_pic
                
                # 提取标题
                title_match = re.search(r'<a[^>]*class="[^"]*font-bold[^"]*"[^>]*>([^<]+)</a>', item)
                if not title_match:
                    title_match = re.search(r'<a[^>]*>([^<]+)</a>\s*</div>\s*$', item)
                if not title_match:
                    continue
                vod_name = title_match.group(1).strip()
                
                videos.append({
                    "vod_id": vod_id,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": ""
                })
            except Exception as e:
                print(f"解析单个视频时出错: {e}")
                continue
        
        return videos
    
    def detailContent(self, ids):
        """视频详情页"""
        try:
            vod_id = ids[0]
            # 确保URL完整
            if not vod_id.startswith('http'):
                if vod_id.startswith('/'):
                    url = self.host + vod_id
                else:
                    url = self.host + '/' + vod_id
            else:
                url = vod_id
            
            print(f"详情页URL: {url}")
            rsp = self.fetch(url, headers=self.headers)
            html = rsp.text
            
            # 提取标题
            vod_name = "未知标题"
            title_match = re.search(r'<title>([^<]+)</title>', html)
            if title_match:
                vod_name = title_match.group(1)
                # 清理标题
                vod_name = re.sub(r'\s*-\s*少女AV.*', '', vod_name)
            
            # 提取封面图
            vod_pic = ""
            pic_match = re.search(r'<img[^>]+src="([^"]+)"[^>]*class="[^"]*thumb[^"]*"', html)
            if not pic_match:
                pic_match = re.search(r'<meta property="og:image" content="([^"]+)"', html)
            if not pic_match:
                pic_match = re.search(r'<img[^>]+data-original="([^"]+)"', html)
            
            if pic_match:
                vod_pic = pic_match.group(1)
                if vod_pic.startswith('//'):
                    vod_pic = 'https:' + vod_pic
                elif vod_pic.startswith('/'):
                    vod_pic = self.host + vod_pic
            
            # 提取播放地址 - 这个需要您提供详情页HTML才能准确解析
            play_url = ""
            
            # 尝试找m3u8
            m3u8_match = re.search(r'(https?://[^"\']+\.m3u8[^"\']*)', html)
            if m3u8_match:
                play_url = m3u8_match.group(1)
            else:
                # 找mp4
                mp4_match = re.search(r'(https?://[^"\']+\.mp4[^"\']*)', html)
                if mp4_match:
                    play_url = mp4_match.group(1)
            
            # 如果没找到，可能需要从JavaScript变量中提取
            if not play_url:
                # 查找类似 var video_url = '...' 的代码
                js_match = re.search(r'var[^;]*video[^=]*=[^"\']*["\']([^"\']+\.m3u8[^"\']*)["\']', html, re.IGNORECASE)
                if js_match:
                    play_url = js_match.group(1)
            
            if not play_url:
                play_url = url  # 如果没找到，让TVBox去解析
            
            video = {
                "vod_id": ids[0],
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_content": "",
                "vod_year": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_area": "",
                "vod_play_from": "萝莉AV",
                "vod_play_url": f"播放${play_url}"
            }
            
            return {"list": [video]}
            
        except Exception as e:
            print(f"详情页解析错误: {e}")
            import traceback
            traceback.print_exc()
            video = {
                "vod_id": ids[0],
                "vod_name": "加载失败",
                "vod_pic": "",
                "vod_content": "",
                "vod_play_from": "默认",
                "vod_play_url": f"播放${ids[0]}"
            }
            return {"list": [video]}
    
    def searchContent(self, key, quick, pg=1):
        """搜索功能"""
        try:
            # 构建搜索URL
            encoded_key = urllib.parse.quote(key)
            url = f"{self.host}/search.php?keyword={encoded_key}&page={pg}"
            print(f"搜索URL: {url}")
            
            rsp = self.fetch(url, headers=self.headers)
            html = rsp.text
            
            # 搜索结果页可能和分类页结构相同
            videos = self._parse_video_list(html)
            
            print(f"搜索到 {len(videos)} 个结果")
            
            return {
                "list": videos,
                "page": int(pg),
                "pagecount": 1,
                "limit": 30,
                "total": len(videos)
            }
            
        except Exception as e:
            print(f"搜索解析错误: {e}")
            return {"list": []}
    
    def playerContent(self, flag, id, vipFlags):
        """解析播放地址"""
        result = {}
        
        try:
            # 如果已经是视频链接，直接返回
            if id.endswith(('.m3u8', '.mp4', '.flv', '.ts')):
                result["parse"] = 0
                result["url"] = id
                result["header"] = self.headers
            else:
                # 否则需要二次解析
                if not id.startswith('http'):
                    if id.startswith('/'):
                        play_url = self.host + id
                    else:
                        play_url = self.host + '/' + id
                else:
                    play_url = id
                
                # 去掉时间戳参数
                play_url = re.sub(r'\?.*$', '', play_url)
                
                result["parse"] = 1
                result["url"] = play_url
                result["header"] = self.headers
            
        except Exception as e:
            print(f"播放地址解析错误: {e}")
            result["parse"] = 1
            result["url"] = id
            result["header"] = self.headers
        
        return result
    
    def isVideoFormat(self, url):
        """判断是否为视频格式"""
        return url.endswith(('.m3u8', '.mp4', '.avi', '.mkv', '.flv', '.ts'))
    
    def localProxy(self, params):
        """本地代理"""
        return [200, "video/MP2T", ""]
