# -*- coding: utf-8 -*-
import sys
import re
import json
import urllib.request
import urllib.parse
import gzip
import io

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    """污漫天堂漫画爬虫 - 皮卡丘标准格式"""

    def getName(self):
        return "污漫天堂"

    def init(self, extend=""):
        pass

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def getHeader(self):
        return {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36",
            "Referer": "https://wmtt5.com/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",  # 关键：移除br，只接受gzip
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cookie": "age_verify=1; popup_agreement=1"
        }

    def fetch(self, url, method='GET', data=None, headers=None):
        """统一请求方法 - 仅使用标准库"""
        try:
            h = headers if headers else self.getHeader()
            
            # 处理URL编码
            parsed = urllib.parse.urlparse(url)
            encoded_path = urllib.parse.quote(parsed.path, safe='/')
            url = urllib.parse.urlunparse((
                parsed.scheme,
                parsed.netloc,
                encoded_path,
                parsed.params,
                parsed.query,
                parsed.fragment
            ))
            
            # 构建请求
            req = urllib.request.Request(url, method=method.upper())
            
            # 添加headers
            for key, value in h.items():
                req.add_header(key, value)
            
            # POST数据
            if method.upper() == 'POST' and data:
                if isinstance(data, dict):
                    data = urllib.parse.urlencode(data).encode('utf-8')
                req.data = data
            
            # 发送请求
            with urllib.request.urlopen(req, timeout=15) as response:
                content = response.read()
                content_encoding = response.info().get('Content-Encoding', '').lower()
                
                # 处理gzip压缩
                if 'gzip' in content_encoding:
                    try:
                        content = gzip.decompress(content)
                    except Exception as e:
                        try:
                            buf = io.BytesIO(content)
                            with gzip.GzipFile(fileobj=buf) as f:
                                content = f.read()
                        except Exception as e2:
                            pass
                
                # 解码
                result = content.decode('utf-8', errors='ignore')
                return result
        except Exception as e:
            print(f"[ERROR] 请求失败: {url}, 错误: {e}")
            return None

    def homeContent(self, filter):
        """首页分类"""
        result = {
            "class": [
                {"type_id": "newmanga", "type_name": "最近更新"},
                {"type_id": "mangacata/all/ob/hit/st/all", "type_name": "全部漫画"},
                {"type_id": "mangacata/%E9%9F%A9%E6%BC%AB/ob/time/st/all", "type_name": "韩漫"},
                {"type_id": "mangacata/%E6%97%A5%E6%BC%AB/ob/time/st/all", "type_name": "日漫"},
                {"type_id": "mangacata/%E7%9C%9F%E4%BA%BA%E6%BC%AB%E7%94%BB/ob/time/st/all", "type_name": "真人漫画"},
                {"type_id": "mangacata/%E7%9F%AD%E7%AF%87/ob/time/st/all", "type_name": "短篇"},
                {"type_id": "mangarank/daily", "type_name": "日榜"},
                {"type_id": "mangarank", "type_name": "周榜"},
                {"type_id": "mangarank/monthly", "type_name": "月榜"},
                {"type_id": "mangarank/all", "type_name": "总榜"}
            ]
        }
        return result

    def homeVideoContent(self):
        """首页推荐内容"""
        return self.categoryContent("newmanga", "1", False, None)

    def categoryContent(self, tid, pg, filter, extend):
        """分类内容"""
        try:
            # 构建URL
            if tid == "newmanga":
                url = f"https://wmtt5.com/newmanga"
                if int(pg) > 1:
                    url += f"?page={pg}"
            elif "mangarank" in tid:
                url = f"https://wmtt5.com/{tid}"
                if int(pg) > 1:
                    url += f"?page={pg}"
            else:
                url = f"https://wmtt5.com/{tid}/page/{pg}"
            
            html = self.fetch(url)
            if not html:
                return {"list": []}
            
            vlist = self.parseList(html)
            
            return {
                "list": vlist,
                "page": pg,
                "pagecount": 9999,
                "limit": 20,
                "total": 999999
            }
        except Exception as e:
            print(f"[ERROR] categoryContent error: {e}")
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        """搜索内容"""
        try:
            search_key = urllib.parse.quote(key)
            url = f"https://wmtt5.com/cata.php?key={search_key}"
            if int(pg) > 1:
                url += f"&page={pg}"
            
            html = self.fetch(url)
            if not html:
                return {"list": []}
            
            vlist = self.parseList(html)
            
            return {
                "list": vlist,
                "page": pg,
                "pagecount": 9999,
                "limit": 20,
                "total": 999999
            }
        except Exception as e:
            print(f"[ERROR] searchContent error: {e}")
            return {"list": []}

    def detailContent(self, ids):
        """详情内容"""
        try:
            vid = ids[0]
            html = self.fetch(vid)
            if not html:
                return {"list": []}
            
            # 提取标题
            name = "未知漫画"
            name_match = re.search(r'<h1[^>]*class=["\'][^"\']*module-info-title[^"\']*["\'][^>]*>(.*?)</h1>', html, re.S)
            if name_match:
                name = self.cleanHtml(name_match.group(1))
            
            if name == "未知漫画":
                name_match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
                if name_match:
                    name = self.cleanHtml(name_match.group(1))
            
            # 提取作者
            author = ""
            author_match = re.search(r'<div[^>]*class=["\'][^"\']*module-info-item-content[^"\']*["\'][^>]*>(.*?)</div>', html, re.S)
            if author_match:
                author = self.cleanHtml(author_match.group(1))
            
            # 提取标签
            tags = re.findall(r'<div[^>]*class=["\'][^"\']*module-info-tag-link[^"\']*["\'][^>]*>(.*?)</div>', html, re.S)
            tag = " ".join([self.cleanHtml(t) for t in tags])
            
            # 提取简介
            desc = ""
            desc_match = re.search(r'<div[^>]*class=["\'][^"\']*module-info-introduction-content[^"\']*show-desc[^"\']*["\'][^>]*>(.*?)</div>', html, re.S)
            if not desc_match:
                desc_match = re.search(r'<div[^>]*class=["\'][^"\']*module-info-introduction-content[^"\']*["\'][^>]*>(.*?)</div>', html, re.S)
            if desc_match:
                desc = self.cleanHtml(desc_match.group(1))
            
            # 提取封面
            pic = ""
            pic_match = re.search(r'<div[^>]*class=["\'][^"\']*module-item-cover[^"\']*["\'][^>]*data-original=["\']([^"\']+)["\']', html)
            if not pic_match:
                pic_match = re.search(r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']', html)
            if pic_match:
                pic = self.fixUrl(pic_match.group(1))
            
            # 提取章节列表
            chapters = []
            chapter_items = re.findall(r'<a[^>]*class=["\'][^"\']*module-play-list-link[^"\']*["\'][^>]*href=["\']([^"\']+)["\'][^>]*title=["\']([^"\']+)["\']', html, re.S)
            if not chapter_items:
                chapter_items = re.findall(r'<a[^>]*href=["\'](/mangaread/\d+\.html)["\'][^>]*title=["\']([^"\']+)["\']', html)
            
            for ch_url, ch_name in chapter_items:
                ch_url = self.fixUrl(ch_url)
                chapters.append(f"{ch_name}${ch_url}")
            
            chapters.reverse()
            play_url = "#".join(chapters) if chapters else ""
            
            return {
                "list": [{
                    "vod_id": vid,
                    "vod_name": name,
                    "vod_pic": pic,
                    "type_name": tag,
                    "vod_actor": author,
                    "vod_content": desc,
                    "vod_play_from": "污漫天堂",
                    "vod_play_url": play_url
                }]
            }
        except Exception as e:
            print(f"[ERROR] detailContent error: {e}")
            import traceback
            traceback.print_exc()
            return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        """播放内容 - 提取图片"""
        try:
            url = id if id.startswith("http") else f"https://wmtt5.com{id}"
            
            html = self.fetch(url)
            if not html:
                return {"parse": 1, "url": url, "header": self.getHeader()}
            
            img_list = []
            
            # 匹配data-original
            imgs = re.findall(r'<img[^>]*data-original=["\']([^"\']+)["\']', html)
            if imgs:
                for src in imgs:
                    if any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']):
                        img_list.append(self.fixUrl(src))
            
            # 备用：匹配src
            if not img_list:
                imgs = re.findall(r'<img[^>]*src=["\']([^"\']+)["\']', html)
                for src in imgs:
                    if any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']):
                        if 'error.png' not in src and 'logo' not in src:
                            img_list.append(self.fixUrl(src))
            
            # 去重
            seen = set()
            unique_imgs = []
            for img in img_list:
                if img not in seen:
                    seen.add(img)
                    unique_imgs.append(img)
            
            if unique_imgs:
                return {
                    "parse": 0,
                    "playUrl": "",
                    "url": f"pics://{'&&'.join(unique_imgs)}",
                    "header": ""
                }
            else:
                return {"parse": 1, "url": url, "header": self.getHeader()}
        except Exception as e:
            print(f"[ERROR] playerContent error: {e}")
            return {"parse": 1, "url": id, "header": self.getHeader()}

    def localProxy(self, param):
        pass

    # ============ 工具方法 ============

    def parseList(self, html):
        """解析列表页"""
        vlist = []
        try:
            if not html or len(html) < 100:
                return vlist
            
            # 根据实际HTML结构，漫画项格式为：
            # <a class="module-poster-item module-item" href="..." title="...">
            #   <div class="module-item-cover">
            #     <div class="module-item-note">章节</div>
            #     <div class="module-item-pic">
            #       <img class="lazy lazyload" data-original="图片URL" src="...">
            #     </div>
            #   </div>
            #   <div class="module-poster-item-info">
            #     <div class="module-poster-item-title">标题</div>
            #   </div>
            # </a>
            
            # 使用更宽松的正则，匹配整个<a>标签块
            # 关键：使用非贪婪匹配，并且正确处理多行
            pattern = r'<a[^>]*class=["\'][^"\']*module-poster-item[^"\']*["\'][^>]*href=["\']([^"\']+)["\'][^>]*title=["\']([^"\']+)["\'][^>]*>(.*?)</a>'
            items = re.findall(pattern, html, re.S | re.I)  # re.I 忽略大小写
            
            if not items:
                # 尝试更简单的模式
                pattern = r'<a[^>]*href=["\']([^"\']+)["\'][^>]*title=["\']([^"\']+)["\'][^>]*class=["\'][^"\']*module-item[^"\']*["\'][^>]*>(.*?)</a>'
                items = re.findall(pattern, html, re.S | re.I)
            
            print(f"[DEBUG] 匹配到 {len(items)} 个漫画项")
            
            for item in items:
                try:
                    if len(item) == 3:
                        href, title, content = item
                    else:
                        continue
                    
                    link = self.fixUrl(href)
                    
                    # 提取封面 - 从data-original获取
                    pic = ""
                    pic_match = re.search(r'data-original=["\']([^"\']+)["\']', content)
                    if pic_match:
                        pic = self.fixUrl(pic_match.group(1))
                    
                    # 提取章节信息
                    note = ""
                    note_match = re.search(r'<div[^>]*class=["\'][^"\']*module-item-note[^"\']*["\'][^>]*>(.*?)</div>', content, re.S)
                    if note_match:
                        note = self.cleanHtml(note_match.group(1))
                    
                    vlist.append({
                        "vod_id": link,
                        "vod_name": title.strip(),
                        "vod_pic": pic,
                        "vod_remarks": note
                    })
                except Exception as e:
                    continue
            
            # 如果上面的模式没匹配到，使用备用模式（直接匹配所有mangaread链接）
            if not vlist:
                print("[DEBUG] 使用备用模式匹配")
                # 匹配所有漫画链接，并尝试获取附近的图片和章节信息
                links = re.findall(r'<a[^>]*href=["\'](/mangaread/\d+\.html)["\'][^>]*title=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.S)
                print(f"[DEBUG] 备用模式找到 {len(links)} 个链接")
                
                for href, title, content in links:
                    try:
                        link = self.fixUrl(href)
                        
                        # 尝试在附近查找图片（向前查找）
                        # 获取当前<a>标签前的HTML片段
                        pos = html.find(f'href="{href}"')
                        if pos == -1:
                            pos = html.find(f"href='{href}'")
                        
                        pic = ""
                        if pos > 0:
                            # 向前查找500字符内的data-original
                            prev_html = html[max(0, pos-500):pos]
                            pic_match = re.search(r'data-original=["\']([^"\']+)["\']', prev_html)
                            if pic_match:
                                pic = self.fixUrl(pic_match.group(1))
                        
                        # 尝试在内容中查找章节信息
                        note = ""
                        note_match = re.search(r'<div[^>]*class=["\'][^"\']*module-item-note[^"\']*["\'][^>]*>(.*?)</div>', content, re.S)
                        if note_match:
                            note = self.cleanHtml(note_match.group(1))
                        
                        vlist.append({
                            "vod_id": link,
                            "vod_name": title.strip(),
                            "vod_pic": pic,
                            "vod_remarks": note
                        })
                    except:
                        continue
            
        except Exception as e:
            print(f"[ERROR] parseList error: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"[DEBUG] parseList返回: {len(vlist)}个结果")
        return vlist

    def cleanHtml(self, text):
        """清除HTML标签"""
        if not text:
            return ""
        text = re.sub(r'<[^>]+>', '', text)
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        text = text.replace('&quot;', '"').replace('&#39;', "'")
        return text.strip()

    def fixUrl(self, url):
        """补全URL"""
        if not url:
            return ""
        if url.startswith("http"):
            return url
        if url.startswith("//"):
            return "https:" + url
        return "https://wmtt5.com" + url


# ==================== 测试代码 ====================
if __name__ == '__main__':
    spider = Spider()
    
    print("=== 测试首页分类 ===")
    home = spider.homeContent(filter=True)
    print(f"分类数量: {len(home['class'])}")
    
    print("\n=== 测试首页内容 ===")
    home_video = spider.homeVideoContent()
    print(f"获取到 {len(home_video['list'])} 条数据")
    if home_video['list']:
        print("第一条:", home_video['list'][0])
        print("最后一条:", home_video['list'][-1])
    
    print("\n=== 测试分类内容 ===")
    cat = spider.categoryContent("mangacata/%E9%9F%A9%E6%BC%AB/ob/time/st/all", "1", False, None)
    print(f"获取到 {len(cat['list'])} 条数据")
    
    print("\n=== 测试搜索 ===")
    search = spider.searchContent("测试", False, "1")
    print(f"搜索结果: {len(search['list'])} 条")
