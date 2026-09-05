# -*- coding: utf-8 -*-
# flixflop.com Spider Plugin
import sys
import re
import json
from urllib.parse import quote
sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    def init(self, extend=""):
        pass

    def getName(self):
        return "飞流视频"

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    headers = {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
    }

    host = "https://www.flixflop.com"
    api_base = "https://www.flixflop.com/api/v1"

    def get_json(self, path):
        """调用 API 并返回解析后的 JSON 字典"""
        url = f"{self.api_base}{path}"
        try:
            resp = self.fetch(url, headers=self.headers)
            text = resp.text
            return json.loads(text)
        except Exception as e:
            print(f"Error fetching {url}: {str(e)}")
            return {}

    def homeContent(self, filter):
        """首页内容：返回分类导航 + 筛选条件 + 首页推荐列表"""
        result = {}

        # 获取分类列表
        cats_data = self.get_json('/categories')
        cats = cats_data.get('data', [])
        result['class'] = [{'type_id': c['category_id'], 'type_name': c['name']} for c in cats]

        # 获取各分类的筛选条件
        result['filters'] = {}
        for cat in cats:
            cat_id = cat['category_id']
            fdata_raw = self.get_json(f'/explore/{cat_id}/filters')
            fdata = fdata_raw.get('data', {})

            filters_list = []

            # 地区筛选
            areas = fdata.get('areas', [])
            if areas:
                filters_list.append({
                    'key': 'area',
                    'name': '地区',
                    'value': [{'n': '全部', 'v': ''}] + [{'n': a['name'], 'v': a['area_id']} for a in areas]
                })

            # 类型筛选（仅当有多个类型时才显示）
            genres = fdata.get('genres', [])
            if genres and len(genres) > 1:
                filters_list.append({
                    'key': 'genre',
                    'name': '类型',
                    'value': [{'n': '全部', 'v': ''}] + [{'n': g['name'], 'v': g['genre_id']} for g in genres]
                })

            # 年份筛选（过滤掉异常年份）
            years = fdata.get('published_years', [])
            valid_years = [y for y in years if isinstance(y, int) and 2000 <= y <= 2035]
            if valid_years:
                filters_list.append({
                    'key': 'year',
                    'name': '年份',
                    'value': [{'n': '全部', 'v': ''}] + [{'n': str(y), 'v': str(y)} for y in valid_years]
                })

            # 语言筛选
            languages = fdata.get('languages', [])
            if languages:
                filters_list.append({
                    'key': 'language',
                    'name': '语言',
                    'value': [{'n': '全部', 'v': ''}] + [{'n': l['name'], 'v': l['language_id']} for l in languages]
                })

            result['filters'][cat_id] = filters_list

        # 获取首页推荐列表
        result['list'] = []
        daily_data = self.get_json('/landing/recommendations/daily')
        daily = daily_data.get('data', [])
        for item in daily:
            result['list'].append({
                'vod_id': item.get('video_id', ''),
                'vod_name': item.get('title', ''),
                'vod_pic': item.get('cover_image', ''),
                'vod_remarks': item.get('remarks', ''),
                'vod_year': str(item.get('published_year', '')),
            })

        # 如果没有每日推荐，取第一个分类的周推荐
        if not result['list'] and cats:
            cat_id = cats[0]['category_id']
            weekly_data = self.get_json(f'/landing/{cat_id}/recommendations/weekly')
            weekly = weekly_data.get('data', {})
            for item in weekly.get('latest', []):
                result['list'].append({
                    'vod_id': item.get('video_id', ''),
                    'vod_name': item.get('title', ''),
                    'vod_pic': item.get('cover_image', ''),
                    'vod_remarks': item.get('remarks', ''),
                    'vod_year': str(item.get('published_year', '')),
                })

        return result

    def homeVideoContent(self):
        return {}

    def categoryContent(self, tid, pg, filter, extend):
        """分类列表页：支持筛选和分页"""
        result = {}
        page = int(pg)

        # 构建带筛选参数的 API URL
        params = [f'page={page}']
        if extend:
            for key in ['area', 'genre', 'year', 'language']:
                val = extend.get(key, '')
                if val:
                    params.append(f'{key}={val}')

        query_string = '&'.join(params)
        api_data = self.get_json(f'/explore/{tid}?{query_string}')

        meta = api_data.get('meta', {})
        total = int(meta.get('count', 0))
        videos_data = api_data.get('data', [])

        videos = []
        for item in videos_data:
            videos.append({
                'vod_id': item.get('video_id', ''),
                'vod_name': item.get('title', ''),
                'vod_pic': item.get('cover_image', ''),
                'vod_remarks': item.get('remarks', ''),
                'vod_year': str(item.get('published_year', '')),
            })

        result['list'] = videos
        result['page'] = page
        result['limit'] = 12
        result['total'] = total
        result['pagecount'] = (total + 11) // 12 if total > 0 else page

        return result

    def detailContent(self, ids):
        """详情页：获取视频详情和播放源"""
        video_id = ids[0]

        # 获取视频元数据
        meta_data = self.get_json(f'/videos/{video_id}/metadata')
        data = meta_data.get('data', {})

        vod = {
            'vod_id': video_id,
            'vod_name': data.get('title', ''),
            'vod_pic': data.get('cover_image', ''),
            'type_name': data.get('genre', '') or data.get('category', ''),
            'vod_year': str(data.get('published_year', '')),
            'vod_area': data.get('area', ''),
            'vod_remarks': data.get('remarks', ''),
            'vod_actor': '',
            'vod_director': '',
            'vod_content': data.get('description', ''),
            'vod_play_from': '',
            'vod_play_url': '',
        }

        # 主演
        actors = data.get('actors', [])
        if actors:
            vod['vod_actor'] = ', '.join([a.get('name', '') for a in actors])

        # 导演
        directors = data.get('directors', [])
        if directors:
            vod['vod_director'] = ', '.join([d.get('name', '') for d in directors])

        # 获取播放源
        sources_data = self.get_json(f'/videos/{video_id}/sources')
        sources = sources_data.get('data', [])

        play_from_list = []
        play_url_list = []
        for source in sources:
            source_name = source.get('name', '')
            source_url = source.get('url', '')
            if source_name and source_url:
                play_from_list.append(source_name)
                play_url_list.append(source_url)

        vod['vod_play_from'] = '$$$'.join(play_from_list)
        vod['vod_play_url'] = '$$$'.join(play_url_list)

        return {'list': [vod]}

    def searchContent(self, key, quick, pg="1"):
        """搜索"""
        encoded_key = quote(key)
        api_data = self.get_json(f'/explore/search?query={encoded_key}')
        results = api_data.get('data', [])

        videos = []
        for item in results:
            videos.append({
                'vod_id': item.get('video_id', ''),
                'vod_name': item.get('title', ''),
                'vod_pic': item.get('cover_image', ''),
                'vod_remarks': item.get('remarks', ''),
            })

        return {'list': videos}

    def playerContent(self, flag, id, vipFlags):
        """播放页：返回真实播放地址（m3u8 直链）"""
        headers = {
            'referer': self.host,
            'user-agent': self.headers['user-agent'],
        }
        # id 已经是 m3u8 直链地址，无需解析
        return {'parse': 0, 'url': id, 'header': headers}

    def localProxy(self, param):
        pass

    def liveContent(self, url):
        pass
