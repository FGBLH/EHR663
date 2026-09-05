#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import json
import logging
import urllib.parse
import os
import sys
import requests
from bs4 import BeautifulSoup

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    BaseSpider = object

logger = logging.getLogger(__name__)


class Spider(BaseSpider):
    """映像星球爬虫 - 适配 MxPro CMS"""

    BASE_URL = "https://www.yxxq41.cc"
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    CATEGORY_MAP = {
        "1": "电影",
        "2": "电视剧",
        "3": "综艺",
        "4": "动漫",
        "7": "纪录片",
        "39": "短剧",
        "53": "体育",
    }

    def __init__(self):
        try:
            super().__init__()
        except Exception:
            pass
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def init(self, extend):
        pass

    def getName(self):
        return "映像星球"

    def homeContent(self, filter=False):
        """首页内容"""
        try:
            url = f"{self.BASE_URL}/"
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            resp.encoding = 'utf-8'
            html = resp.text
            
            classes = []
            for cate_id, cate_name in self.CATEGORY_MAP.items():
                classes.append({
                    "type_id": cate_id,
                    "type_name": cate_name,
                })
            
            soup = BeautifulSoup(html, 'html.parser')
            videos = []
            seen_ids = set()
            
            for item in soup.select('a.module-poster-item'):
                if item.get('data-ad-slot') or 'mac-ad-card' in item.get('class', []):
                    continue
                href = item.get('href', '')
                m = re.search(r'/html/(\d+)\.html', href)
                if not m:
                    continue
                vid = m.group(1)
                if vid in seen_ids:
                    continue
                seen_ids.add(vid)
                
                title_el = item.select_one('.module-poster-item-title')
                title = title_el.get_text(strip=True) if title_el else ''
                
                pic_el = item.select_one('.module-item-pic img')
                pic = ''
                if pic_el:
                    pic = pic_el.get('data-original', '') or pic_el.get('src', '')
                
                note_el = item.select_one('.module-item-note')
                remark = note_el.get_text(strip=True) if note_el else ''
                
                videos.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remark,
                })
                if len(videos) >= 36:
                    break
            
            return {
                "class": classes,
                "list": videos,
            }
        except Exception as e:
            logger.error(f"获取首页失败: {e}")
            return {}

    def homeVideoContent(self):
        home = self.homeContent()
        return {"list": home.get("list", [])}

    def categoryContent(self, tid, pg, filter, ext):
        """分类内容"""
        try:
            page = int(pg) if pg else 1
            if page == 1:
                url = f"{self.BASE_URL}/list/{tid}.html"
            else:
                url = f"{self.BASE_URL}/list/{tid}-{page}.html"
            
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            resp.encoding = 'utf-8'
            html = resp.text
            soup = BeautifulSoup(html, 'html.parser')
            
            total = 0
            total_page = 1
            
            vod_list = []
            for item in soup.select('a.module-poster-item'):
                if item.get('data-ad-slot') or 'mac-ad-card' in item.get('class', []):
                    continue
                href = item.get('href', '')
                m = re.search(r'/html/(\d+)\.html', href)
                if not m:
                    continue
                vid = m.group(1)
                
                title_el = item.select_one('.module-poster-item-title')
                title = title_el.get_text(strip=True) if title_el else ''
                
                pic_el = item.select_one('.module-item-pic img')
                pic = ''
                if pic_el:
                    pic = pic_el.get('data-original', '') or pic_el.get('src', '')
                
                note_el = item.select_one('.module-item-note')
                remark = note_el.get_text(strip=True) if note_el else ''
                
                vod_list.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remark,
                })
            
            m_total = re.search(r'共(\d+)条', html)
            if m_total:
                total = int(m_total.group(1))
            
            for a in soup.select('.module-page a'):
                txt = a.get_text(strip=True)
                if txt.isdigit():
                    num = int(txt)
                    if num > total_page:
                        total_page = num
            
            return {
                "list": vod_list,
                "page": page,
                "pagecount": total_page,
                "limit": 20,
                "total": total,
            }
        except Exception as e:
            logger.error(f"获取分类内容失败: {e}")
            return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        """详情内容 - 精确提取播放列表"""
        try:
            vod_id = ids[0] if isinstance(ids, list) else str(ids)
            url = f"{self.BASE_URL}/html/{vod_id}.html"
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            resp.encoding = 'utf-8'
            html = resp.text
            soup = BeautifulSoup(html, 'html.parser')
            
            # 基本信息
            name = ''
            name_el = soup.select_one('.module-info-heading h1')
            if name_el:
                name = name_el.get_text(strip=True)
            
            pic = ''
            pic_el = soup.select_one('.module-info-poster .module-item-pic img')
            if pic_el:
                pic = pic_el.get('data-original', '') or pic_el.get('src', '')
            
            year = ''
            area = ''
            type_name = ''
            for tl in soup.select('.module-info-tag-link a'):
                txt = tl.get_text(strip=True)
                if re.search(r'20\d{2}', txt) and not year:
                    year = txt
                if re.search(r'(大陆|香港|台湾|韩国|日本|美国|欧美|海外|国产|泰国|印度)', txt) and not area:
                    area = txt
                if not type_name:
                    type_name = txt
            
            remark = ''
            content = ''
            for item in soup.select('.module-info-item'):
                title_el = item.select_one('.module-info-item-title')
                if title_el:
                    t = title_el.get_text(strip=True)
                    content_el = item.select_one('.module-info-item-content')
                    if content_el and '备注' in t:
                        remark = content_el.get_text(strip=True)
            
            desc_div = soup.select_one('.module-info-introduction-content')
            if desc_div:
                content = desc_div.get_text(strip=True)
            
            # ===== 精确提取播放列表 =====
            play_sources = []
            
            # 获取播放源名称
            source_names = []
            for tab in soup.select('#y-playList .tab-item'):
                name_tmp = tab.get_text(strip=True)
                if name_tmp:
                    source_names.append(name_tmp)
            
            # 获取 play-list 分组 (class="tab-list his-tab-list")
            play_panels = soup.select('.tab-list.his-tab-list')
            
            if source_names and play_panels:
                for i, src_name in enumerate(source_names):
                    episodes = []
                    if i < len(play_panels):
                        for link in play_panels[i].select('a.module-play-list-link'):
                            href = link.get('href', '')
                            ep_name_el = link.select_one('span')
                            ep_name = ep_name_el.get_text(strip=True) if ep_name_el else ''
                            if href and ep_name:
                                episodes.append((ep_name, href))
                    if episodes:
                        play_sources.append((src_name, episodes))
            
            # 备用：正则提取
            if not play_sources:
                all_links = re.findall(
                    r'<a class="module-play-list-link"[^>]*href="(/play/\d+-\d+-\d+\.html)"[^>]*>.*?<span>(.*?)</span>',
                    html, re.DOTALL
                )
                if all_links:
                    src_names = source_names or ['线路①']
                    for sn in src_names:
                        episodes = [(n.strip(), h) for h, n in all_links]
                        if episodes:
                            play_sources.append((sn, episodes))
                        break
            
            play_from_list = []
            play_url_list = []
            
            for src_name, episodes in play_sources:
                play_from_list.append(src_name)
                ep_list = []
                for ep_name, href in episodes:
                    full_url = href if href.startswith('http') else f"{self.BASE_URL}{href}"
                    ep_list.append(f"{ep_name}${full_url}")
                play_url_list.append('#'.join(ep_list))
            
            vod_item = {
                "vod_id": vod_id,
                "vod_name": name,
                "vod_pic": pic,
                "type_name": type_name,
                "vod_year": year,
                "vod_area": area,
                "vod_remarks": remark,
                "vod_content": content,
                "vod_play_from": '$$$'.join(play_from_list),
                "vod_play_url": '$$$'.join(play_url_list),
            }
            
            return {"list": [vod_item]}
        except Exception as e:
            logger.error(f"获取详情失败: {e}")
            return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        """播放内容 - 解析真实m3u8地址"""
        try:
            play_url = urllib.parse.unquote(id) if id else ''
            if not play_url:
                return {"parse": 0, "url": ""}
            
            if not play_url.startswith('http'):
                play_url = f"{self.BASE_URL}{play_url}" if play_url.startswith('/') else f"{self.BASE_URL}/{play_url}"
            
            resp = self.session.get(play_url, timeout=30)
            resp.raise_for_status()
            resp.encoding = 'utf-8'
            html = resp.text
            
            m = re.search(r'player_aaaa\s*=\s*({.*?});', html, re.DOTALL)
            if m:
                try:
                    data = json.loads(m.group(1))
                    real_url = data.get('url', '')
                    if real_url:
                        return {
                            "parse": 0,
                            "url": real_url,
                            "header": json.dumps(self.HEADERS),
                        }
                except Exception:
                    pass
            
            return {
                "parse": 1,
                "url": play_url,
            }
        except Exception as e:
            logger.error(f"解析播放失败: {e}")
            return {"parse": 0, "url": ""}

    def searchContent(self, key, quick, pg):
        """搜索内容"""
        try:
            page = int(pg) if pg else 1
            encoded_key = urllib.parse.quote(key)
            url = f"{self.BASE_URL}/search/{encoded_key}-------------{page}.html"
            
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            resp.encoding = 'utf-8'
            html = resp.text
            soup = BeautifulSoup(html, 'html.parser')
            
            vod_list = []
            seen_ids = set()
            
            for item in soup.select('.module-item'):
                detail_link = item.select_one('a[href*="/html/"]')
                if not detail_link:
                    continue
                href = detail_link.get('href', '')
                m = re.search(r'/html/(\d+)\.html', href)
                if not m:
                    continue
                vid = m.group(1)
                if vid in seen_ids:
                    continue
                seen_ids.add(vid)
                
                title = detail_link.get('title', '') or detail_link.get_text(strip=True)
                
                pic = ''
                img = item.select_one('img')
                if img:
                    pic = img.get('data-original', '') or img.get('src', '')
                
                remark = ''
                remark_el = item.select_one('.module-item-note, .video-note, .note')
                if remark_el:
                    remark = remark_el.get_text(strip=True)
                
                vod_list.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remark,
                })
            
            if not vod_list:
                for link in soup.select('a[href*="/html/"]'):
                    href = link.get('href', '')
                    m = re.search(r'/html/(\d+)\.html', href)
                    if not m:
                        continue
                    vid = m.group(1)
                    if vid in seen_ids:
                        continue
                    seen_ids.add(vid)
                    title = link.get_text(strip=True)
                    if not title:
                        continue
                    vod_list.append({
                        "vod_id": vid,
                        "vod_name": title,
                        "vod_pic": '',
                        "vod_remarks": '',
                    })
            
            total = 0
            m_total = re.search(r'找到(\d+)部影片', html)
            if m_total:
                total = int(m_total.group(1))
            else:
                total = len(vod_list)
            
            return {
                "list": vod_list,
                "page": page,
                "pagecount": 1,
                "limit": 20,
                "total": total,
            }
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}

    def localProxy(self, param):
        return []


def main():
    spider = Spider()
    
    print("=" * 60)
    print("【1】测试首页")
    home = spider.homeContent()
    print(f"分类: {len(home.get('class', []))}, 推荐: {len(home.get('list', []))}")
    for v in home.get('list', [])[:5]:
        print(f"  - {v['vod_name']} [{v['vod_remarks']}]")
    
    print("\n" + "=" * 60)
    print("【2】测试分类 (电影)")
    cat = spider.categoryContent("1", "1", False, {})
    print(f"总数: {cat.get('total')}, 本页: {len(cat.get('list', []))}")
    for v in cat.get('list', [])[:5]:
        print(f"  - {v['vod_name']} [{v['vod_remarks']}]")
    
    print("\n" + "=" * 60)
    print("【3】测试详情 (23026 给阿嬷的情书)")
    detail = spider.detailContent(["23026"])
    if detail.get('list'):
        d = detail['list'][0]
        print(f"标题: {d['vod_name']}")
        play_from = d.get('vod_play_from', '')
        play_url = d.get('vod_play_url', '')
        sources = play_from.split('$$$')
        urls = play_url.split('$$$') if play_url else []
        print(f"播放源: {len(sources)}个")
        for i, src in enumerate(sources):
            ep_count = len(urls[i].split('#')) if i < len(urls) else 0
            print(f"  - {src}: {ep_count}集")
    
    print("\n" + "=" * 60)
    print("【4】测试播放解析")
    if detail.get('list') and detail['list'][0].get('vod_play_url'):
        first = detail['list'][0]['vod_play_url'].split('$$$')[0].split('#')[0]
        if '$' in first:
            ep_url = first.split('$')[1]
            play = spider.playerContent('', ep_url, [])
            print(f"解析结果: {play.get('url', '')[:80]}...")
    
    print("\n" + "=" * 60)
    print("【5】测试搜索")
    search = spider.searchContent("战狼", False, "1")
    print(f"结果: {search.get('total')}部")
    for v in search.get('list', [])[:5]:
        print(f"  - {v['vod_name']}")
    
    print("\n完成!")


if __name__ == "__main__":
    main()