# coding=utf-8
# !/usr/bin/python

from Crypto.Util.Padding import unpad, pad
from Crypto.Cipher import ARC4, AES
from urllib.parse import unquote, quote
from base.spider import Spider
from datetime import datetime
from bs4 import BeautifulSoup
from base64 import b64decode
import urllib.request
import urllib.parse
import binascii
import requests
import hashlib
import base64
import uuid
import hmac
import json
import time
import sys
import re
import os

sys.path.append('..')

xurl = "https://minidrama-api.contentchina.com"

headerx = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.87 Safari/537.36'
          }

headers = {
    'Accept': '*/*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'Origin': 'https://minidrama.contentchina.com',
    'Pragma': 'no-cache',
    'Referer': 'https://minidrama.contentchina.com/',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'cross-site',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0',
    'sec-ch-ua': '"Microsoft Edge";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
           }

class Spider(Spider):

    def getName(self):
        return "🌷"

    def init(self, extend):
        pass

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def homeContent(self, filter):
        result = {"class": []}
        def get_category_data():
            url = f"{xurl}/web/v1/home/categoryList?isLeft=1"
            response = requests.get(url=url, headers=headerx)
            response.encoding = "utf-8"
            return response.json()
        def process_categories(data):
            categories = []
            for vod in data['data']['categories']:
                category_info = {
                    "type_id": vod['id'],
                    "type_name": f"🌷{vod['name']}"
                                }
                categories.append(category_info)
            return categories
        def build_result(categories):
            return {"class": categories}
        data = get_category_data()
        categories = process_categories(data)
        result = build_result(categories)
        return result

    def homeVideoContent(self):
        pass

    def categoryContent(self, cid, pg, filter, ext):
        def get_page_number():
            return int(pg) if pg else 1
        def fetch_category_data(page_number):
            url = f'{xurl}/web/v1/drama/list?pageSize=24&currentPage={str(page_number)}&filterCategories[]={cid}'
            response = requests.get(url=url, headers=headerx)
            response.encoding = "utf-8"
            return response.json()
        def parse_videos(data):
            video_list = []
            for vod in data['data']['data']:
                video_info = {
                    "vod_id": f"{vod['albumId']}@{vod['total']}",
                    "vod_name": vod['title'],
                    "vod_pic": vod['coverUrl'],
                    "vod_remarks": f"🌷共{vod.get('total', '暂无备注')}集"
                             }
                video_list.append(video_info)
            return video_list
        def build_result(video_list, page_number):
            return {
                'list': video_list,
                'page': page_number,
                'pagecount': 9999,
                'limit': 90,
                'total': 999999
                   }
        current_page = get_page_number()
        response_data = fetch_category_data(current_page)
        parsed_videos = parse_videos(response_data)
        result = build_result(parsed_videos, current_page)
        return result

    def detailContent(self, ids):
        def parse_ids():
            did = ids[0]
            parts = did.split("@")
            return parts[0], int(parts[1])
        def generate_play_items(base_id, total_count):
            return [f"{i}${base_id}@{i}" for i in range(1, total_count + 1)]
        def build_play_url(items):
            return "#".join(items)
        def create_video_info(did, play_url):
            return {
                "vod_id": did,
                "vod_play_from": "喜福专线",
                "vod_play_url": play_url
                   }
        def build_result(video_info):
            return {'list': [video_info]}
        base_id, total_count = parse_ids()
        play_items = generate_play_items(base_id, total_count)
        play_url = build_play_url(play_items)
        video_info = create_video_info(ids[0], play_url)
        result = build_result(video_info)
        return result

    def playerContent(self, flag, id, vipFlags):
        def parse_video_id():
            parts = id.split("@")
            return parts[0], parts[1]
        def get_play_auth(album_id, seq):
            url = f'{xurl}/web/v1/drama/play_auth?albumId={album_id}&seq={seq}'
            response = requests.get(url=url, headers=headerx)
            response.encoding = "utf-8"
            return response.json()
        def extract_credentials(data):
            video_id = data['data']['vid']
            play_auth_b64 = data['data']['playAuth']
            play_auth_json = base64.b64decode(play_auth_b64).decode('utf-8')
            return json.loads(play_auth_json), video_id
        def build_request_params(credentials, video_id):
            params = {
                'Action': 'GetPlayInfo',
                'Version': '2017-03-21',
                'Format': 'JSON',
                'AccessKeyId': credentials['AccessKeyId'],
                'SecurityToken': credentials['SecurityToken'],
                'VideoId': video_id,
                'AuthInfo': credentials.get('AuthInfo', ''),
                'Timestamp': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
                'SignatureMethod': 'HMAC-SHA1',
                'SignatureVersion': '1.0',
                'SignatureNonce': str(uuid.uuid4()),
                     }
            if 'PlayConfig' in credentials:
                params['PlayConfig'] = json.dumps(credentials.get('PlayConfig'))
            return params
        def generate_signature(params, credentials):
            sorted_params = sorted(params.items())
            canonicalized_query_string = '&'.join(
                [f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(str(v), safe='')}" for k, v in sorted_params])
            string_to_sign = f"GET&%2F&{urllib.parse.quote(canonicalized_query_string, safe='')}"
            key = credentials['AccessKeySecret'] + "&"
            signature = hmac.new(key.encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha1).digest()
            return base64.b64encode(signature).decode('utf-8'), canonicalized_query_string
        def get_final_play_url(credentials, canonicalized_query_string, signature_b64):
            final_url = f"https://vod.{credentials.get('Region', 'cn-shanghai')}.aliyuncs.com/?{canonicalized_query_string}&Signature={urllib.parse.quote(signature_b64, safe='')}"
            response = requests.get(url=final_url, headers=headers)
            response.encoding = "utf-8"
            data = response.json()
            return data['PlayInfoList']['PlayInfo'][0]['PlayURL']
        def build_result(play_url):
            return {
                "parse": 0,
                "playUrl": '',
                "url": play_url,
                "header": headerx
                   }
        album_id, seq = parse_video_id()
        auth_data = get_play_auth(album_id, seq)
        credentials, video_id = extract_credentials(auth_data)
        request_params = build_request_params(credentials, video_id)
        signature_b64, canonicalized_query_string = generate_signature(request_params, credentials)
        play_url = get_final_play_url(credentials, canonicalized_query_string, signature_b64)
        result = build_result(play_url)
        return result

    def searchContentPage(self, key, quick, pg):
        pass

    def searchContent(self, key, quick, pg="1"):
        return self.searchContentPage(key, quick, '1')

    def localProxy(self, params):
        if params['type'] == "m3u8":
            return self.proxyM3u8(params)
        elif params['type'] == "media":
            return self.proxyMedia(params)
        elif params['type'] == "ts":
            return self.proxyTs(params)
        return None












