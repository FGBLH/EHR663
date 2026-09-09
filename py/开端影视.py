# -*- coding: utf-8 -*-

from Crypto.Cipher import AES
import sys, json, base64, urllib3
from base.spider import Spider
from urllib.parse import urljoin
from Crypto.Util.Padding import unpad
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
sys.path.append('..')

class Spider(Spider):
    host, site, path, timeout, targets = '','','', 5, {b'\xb1\xa1\xa6\xe2'.decode('big5'), b'\xc2\xd7\xc0\xed'.decode('gbk'), b'\xba\xd6\xa7Q'.decode('big5'), b"\xff\xfe\x0cT'`".decode('utf-16')}
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_2; rv:107) Gecko/20100101 Firefox/98',
        'Accept-Encoding': 'gzip',
        'referer': '',
        'Cookie': ''
    }

    def init(self, extend=''):
        try:
            if extend:
                ext = json.loads(extend)
            else:
                ext = {'host':'https://api.kaiduan.fun','path':{'search':'/user/movie/cms/v1/search?name={key}&page=1&count=10','detail':'/user/movie/cms/v1/play?id='}}
            self.host = ext['host'].rstrip('/')
            self.headers['referer'] =  f'{self.host}/'
            self.headers['Cookie'] = f'{self.host}/'
            self.site = ext.get('site')
            self.path = ext.get('path')
            timeout = ext.get('timeout')
            if timeout: self.timeout = timeout
        except Exception:
            self.host = ''

    def homeContent(self, filter):
        if not self.host: return None
        return {'class':[{'type_id':'电影','type_name':'电影'},{'type_id':'连续剧','type_name':'连续剧'},{'type_id':'动漫','type_name':'动漫'},{'type_id':'短剧','type_name':'短剧'},{'type_id':'综艺','type_name':'综艺'},{'type_id':'纪录片','type_name':'纪录片'}]}

    def homeVideoContent(self):
        return self.categoryContent('电影,连续剧,动漫,短剧,综艺,纪录片',1,False,{})

    def categoryContent(self, tid, pg, filter, extend):
        if not self.host: return None
        response = self.fetch(f'{self.host}/user/movie/cms/v1/category?count=20&names={tid}&page={pg}',headers=self.headers, verify=False, timeout=self.timeout).text
        data = json.loads(self.decrypt(response))['datas']
        videos = self.arr2vods(data)
        return {'list': videos}

    def searchContent(self, key, quick, pg='1'):
        if not self.host or str(pg) != '1': return None
        if self.site:
            path = f'/other/module?name={self.site}&params=search|{key}'
        else:
            if '{key}' in self.path['search']:
                path = self.path['search'].replace('{key}',key)
            else:
                path = f"{self.path['search']}{key}"
        if not path.startswith('http'):
            path = f'{self.host}{path}'
        response = self.decrypt(self.fetch(path, headers=self.headers, verify=False, timeout=self.timeout).text)
        response = json.loads(response)
        if 'datas' in response or 'data' in response:
            data = response.get('datas',response.get('data'))
        else:
            data = response
        videos = self.arr2vods(data)
        return {'list': videos, 'page': pg}

    def detailContent(self, ids):
        if not self.host: return None
        if str(ids[0]).startswith('http'):
            path = ids[0]
        else:
            if '{key}' in ids[0]:
                path = self.path['detail'].replace('{key}',ids[0])
            else:
                path = f"{self.path['detail']}{ids[0]}"
            if not path.startswith('http'): path = f'{self.host}{path}'
        data = self.decrypt(self.fetch(path,headers=self.headers, verify=False, timeout=self.timeout).text)
        raw_data = json.loads(data)
        show, play_urls = [], []
        if 'data' in raw_data:
            data = raw_data['data']
        else:
            data = raw_data
        classify = data.get('classify',data.get('category',data.get('vodClass')))
        if isinstance(classify, str) and any(i in classify for i in self.targets): return None
        urls2 = []
        for i in data.get('episodes',data.get('episodeList',[])):
            if isinstance(i,dict) and 'episode' in i:
                urls = []
                for j in i['episode']:
                    urls.append(f"{j['name']}${j['url']}")
                show.append(i.get('title', i.get('name')))
                play_urls.append('#'.join(urls))
            else:
                urls2.append(f"{i['name']}${i['url']}")
        if urls2:
            show.append('1线')
            play_urls = ['#'.join(urls2)]
        if not(show and play_urls) and 'datas' in raw_data:
            for i in raw_data['datas']:
                show.append(i['name'])
                play_urls.append(i['urls'])
        video = {
            'vod_id': ids[0],
            'vod_name': data.get('name',data.get('vodName')),
            'vod_pic': data.get('pic',data.get('vodPic')),
            'vod_remarks': data.get('remarks',data.get('vodRemarks')),
            'vod_year': data.get('year',data.get('vodYear')),
            'vod_area': data.get('area',data.get('vodArea')),
            'vod_actor': data.get('actor',data.get('vodActor')),
            'vod_director': data.get('director',data.get('vodDirector')),
            'vod_content': data.get('details',data.get('vodContent',data.get('content'))),
            'vod_play_from': '$$$'.join(show),
            'vod_play_url': '$$$'.join(play_urls),
            'type_name': classify
        }
        return {'list': [video]}

    def playerContent(self, flag, url, vip_flags):
        try:
            if '|' in url: url = self.raw_url(url)
        except Exception:
            pass
        return { 'jx': 0, 'parse': '0', 'url': url, 'header': {'User-Agent':'ijkplayer/1.0.0 (Linux;Android 11) ExoPlayerLib/2.14.1','Accept-Encoding':'gzip'}}

    def decrypt(self,data):
        prefix = "AkEdSJx"
        if not data.startswith(prefix): return data
        base64_str = data[len(prefix):]
        decode_bytes = base64.b64decode(base64_str)
        if len(decode_bytes) < 32:
            raise ValueError("加密数据长度不足")
        key = decode_bytes[:16]
        iv = decode_bytes[16:32]
        ciphertext = decode_bytes[32:]
        cipher = AES.new(key, AES.MODE_CBC, iv)
        plaintext_bytes = unpad(cipher.decrypt(ciphertext), AES.block_size)
        return plaintext_bytes.decode('utf-8')

    def arr2vods(self,arr):
        videos = []
        for i in arr:
            classify = i.get('classify',i.get('category',i.get('vodClass')))
            if not(isinstance(classify, str) and any(i in classify for i in self.targets)):
                videos.append({
                    'vod_id': i.get('url',i.get('vodId',i.get('id'))),
                    'vod_name': i.get('name',i.get('vodName')),
                    'vod_pic': i.get('pic',i.get('vodPic')),
                    'vod_remarks': i.get('remarks',i.get('vodRemarks')),
                    'vod_year': i.get('year',i.get('vodYear')),
                    'type_name': classify
                })
        return videos

    def raw_url(self,original_url):
        try:
            response = self.fetch(original_url,allow_redirects=False,stream=True,timeout=20)
            if 300 <= response.status_code < 400:
                redirect_location = response.headers.get('Location')
                if redirect_location:
                    real_url = urljoin(original_url, redirect_location)
                    return real_url
            return original_url
        except Exception:
            return original_url

    def getName(self):
        pass

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    def localProxy(self, param):
        pass
