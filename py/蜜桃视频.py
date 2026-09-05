# 蜜桃视频 类型爬虫
# 网站: https://www.nht966hht.vip:9527
# API: AES-128-CBC (ZeroPadding) + MD5 签名加密

# coding=utf-8
# !/usr/bin/python

import sys
sys.path.append('..')

from base.spider import BaseSpider
import requests
import json
import base64
import hashlib
import time
import re
import os
import string
import random
import threading
from urllib.parse import quote, unquote
from Crypto.Cipher import AES

TIMEOUT = 10

# ============================================================
# 站点配置（多站点备用）
# ============================================================
SITES = [
    {'name': 'nht966', 'host': 'https://www.nht966hht.vip:9527'},
    {'name': 'httre666', 'host': 'https://www.newhttestre666.cc'},
]

# ============================================================
# 加密常量（从 JS bundle 中提取）
# ============================================================
SIGN_KEY  = 'opum3_Loily$SV^6H'
BUNDLE_ID = 'com.ht9.web20.video'
BRAND_ID  = 'hongtao'
VERSION   = '1.0.0'
PROJECT_ID = '1'

PROXY_TYPE = 'mitao_img'


class Spider(BaseSpider):

    # ---- 基础信息 ----
    def getName(self):
        return "蜜桃视频"

    def isVideoFormat(self, url):
        return url and ('.mp4' in url or '.m3u8' in url or '.ts' in url)

    def manualVideoCheck(self):
        return False

    # ---- 类变量 ----
    filterable = True
    searchable = True
    host = SITES[0]['host']
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "lang": "cn",
        "deviceType": "H5-android",
    }

    # 测速缓存
    _speed_cache_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.mitao_cache.json')
    _speed_cache_ttl = 1800
    _lock = threading.Lock()
    _speed_test_done = False

    # 会话状态
    _user_id = ''
    _session_id = ''
    _device_id = ''
    _session_inited = False

    # 分类缓存 (从 initH5_1 typeTitleList)
    _categories = []

    # 视频类型列表 (从 appConfig videoTypeList，用于构建筛选)
    _video_type_list = []

    # 会话缓存（避免重复 deviceLogin 触发 429 限流）
    _session_cache_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.mitao_session.json')
    _session_cache_ttl = 1800  # 30 分钟

    # ============================================================
    # 多站点测速
    # ============================================================
    def _get_cached_site(self):
        try:
            if os.path.exists(self._speed_cache_file):
                with open(self._speed_cache_file, 'r') as f:
                    data = json.loads(f.read())
                age = time.time() - data.get('ts', 0)
                host = data.get('host', '')
                if age < self._speed_cache_ttl and host:
                    return host, True
        except Exception:
            pass
        return '', False

    def _save_cached_site(self, host):
        try:
            with open(self._speed_cache_file, 'w') as f:
                f.write(json.dumps({'host': host, 'ts': time.time()}))
        except Exception:
            pass

    def _resolve_host(self, portal):
        """
        解析入口域名，返回当前真实 API 站点。
        站点采用「随机重定向页」(Random Redirect Page) 做防封:
        入口域名返回一段含 targetSites 数组的 HTML/JS (常见 HTTP 状态码 888),
        真实站点会随时间轮换。此处解析 targetSites 取出当前真实站点。
        若入口本身即为真实站点 (返回 SPA 页且无 targetSites)，则直接返回。
        """
        try:
            r = requests.get(portal, headers=self.headers, timeout=TIMEOUT,
                             verify=False, allow_redirects=True)
            text = r.text or ''
            # 随机重定向页 → 解析 targetSites 数组
            if 'targetSites' in text:
                m = re.search(r'targetSites\s*=\s*\[(.*?)\]', text, re.S)
                if m:
                    urls = re.findall(r'https?://[^\s"\',\]]+', m.group(1))
                    if urls:
                        return urls[0].rstrip('/')
                return ''
            # 非重定向页且可访问 → 入口本身即真实站点
            if r.status_code == 200:
                return portal.rstrip('/')
        except Exception:
            pass
        return ''

    def _select_best_site(self):
        if self._speed_test_done:
            return
        cached_host, valid = self._get_cached_site()
        if valid:
            self.host = cached_host
            self._speed_test_done = True
            return

        # 依次解析各入口域名，取第一个解析出的真实站点
        # 注意: 真实站点在高负载时根 GET 可能返回 429/502，
        # 故只要能从 targetSites 解析出站点即信任，不再额外探测可用性，避免误判回退到已失效入口
        resolved = ''
        for s in SITES:
            h = self._resolve_host(s['host'])
            if h:
                resolved = h
                break

        self.host = resolved or SITES[0]['host']
        self._speed_test_done = True
        if resolved:
            self._save_cached_site(resolved)

    # ============================================================
    # 会话缓存（持久化到文件，避免重复 init 触发 429 限流）
    # ============================================================
    def _save_session_cache(self):
        """将会话状态写入缓存文件"""
        try:
            data = {
                'ts': time.time(),
                'user_id': self._user_id,
                'session_id': self._session_id,
                'device_id': self._device_id,
                'categories': self._categories,
                'video_type_list': self._video_type_list,
            }
            with open(self._session_cache_file, 'w') as f:
                f.write(json.dumps(data, ensure_ascii=False))
        except Exception:
            pass

    def _load_session_cache(self):
        """从缓存文件恢复会话状态，返回 True 表示缓存有效"""
        try:
            if not os.path.exists(self._session_cache_file):
                return False
            with open(self._session_cache_file, 'r') as f:
                data = json.loads(f.read())
            age = time.time() - data.get('ts', 0)
            if age >= self._session_cache_ttl:
                return False
            self._user_id = data.get('user_id', '')
            self._session_id = data.get('session_id', '')
            self._device_id = data.get('device_id', '')
            self._categories = data.get('categories', [])
            self._video_type_list = data.get('video_type_list', [])
            # 关键字段缺失视为缓存无效, 避免无认证请求被服务器拒绝
            if not self._user_id or not self._session_id:
                return False
            return True
        except Exception:
            return False

    # ============================================================
    # AES 加解密（匹配 CryptoJS ZeroPadding）
    # ============================================================
    @staticmethod
    def _zero_pad(data, block_size=16):
        pad_len = block_size - (len(data) % block_size)
        if pad_len == block_size:
            return data
        return data + b'\x00' * pad_len

    @staticmethod
    def _zero_unpad(data):
        return data.rstrip(b'\x00')

    def _gen_key(self, timestamp):
        """生成 AES-128 密钥: timestamp后6位 + signKey前4 + bundleId前6"""
        ts = str(timestamp)
        return ts[-6:] + SIGN_KEY[:4] + BUNDLE_ID[:6]

    def _gen_iv(self):
        """生成 AES-128 IV: bundleId后6 + signKey后4 + deviceId前6"""
        return BUNDLE_ID[-6:] + SIGN_KEY[-4:] + self._device_id[:6]

    def _aes_encrypt(self, plaintext, key_str, iv_str):
        """AES-128-CBC 加密 (ZeroPadding, 输出 Base64)"""
        key = key_str.encode('utf-8')
        iv = iv_str.encode('utf-8')
        cipher = AES.new(key, AES.MODE_CBC, iv)
        data = plaintext.encode('utf-8')
        padded = self._zero_pad(data)
        encrypted = cipher.encrypt(padded)
        return base64.b64encode(encrypted).decode('utf-8')

    def _aes_decrypt(self, ciphertext_b64, key_str, iv_str):
        """AES-128-CBC 解密 (ZeroPadding, 输入 Base64)"""
        key = key_str.encode('utf-8')
        iv = iv_str.encode('utf-8')
        cipher = AES.new(key, AES.MODE_CBC, iv)
        # 移除空白字符（匹配 JS 端 replace(/\s/g,"")）
        cleaned = re.sub(r'\s', '', ciphertext_b64)
        encrypted = base64.b64decode(cleaned)
        decrypted = cipher.decrypt(encrypted)
        unpadded = self._zero_unpad(decrypted)
        return unpadded.decode('utf-8', errors='replace')

    def _generate_sign(self, params, api_path):
        """MD5 签名: 参数值排序拼接 + signKey + API路径 → MD5 大写"""
        sorted_keys = sorted(params.keys())
        concat = ''
        for k in sorted_keys:
            concat += str(params[k])
        raw = concat + SIGN_KEY + api_path
        return hashlib.md5(raw.encode('utf-8')).hexdigest().upper()

    # ============================================================
    # 客户端 deviceId 生成（匹配 JS: "H5-" + 随机串）
    # ============================================================
    @staticmethod
    def _generate_device_id():
        """生成 H5 设备 ID，格式: H5- + 32位随机小写hex"""
        rand = ''.join(random.choices(string.ascii_lowercase + string.digits, k=32))
        return 'H5-' + rand

    # ============================================================
    # 通用请求 params (Ne)
    # ============================================================
    def _common_params(self):
        # channelId2 = window.location.host (含端口，如 www.nht950hht.vip:9527)
        hostname = self.host.replace('https://', '').replace('http://', '')
        return {
            'timezone': 'Asia/Karachi',
            'version': VERSION,
            'channelId': 67,  # 必须是整数! JS: __xyz_cid_ = 67, JSON.stringify 后为 67 而非 "67"
            'channelId2': hostname,
            'brandId': BRAND_ID,
        }

    # ============================================================
    # API 请求（支持加密/明文双模式）
    # ============================================================
    def _api_request(self, endpoint, params=None, skip_encrypt=False, _t=None):
        """
        发送 AES 加密 API 请求
        endpoint: e.g. '/ht/content/homeH5'
        params: 请求参数 dict
        skip_encrypt: True = 发送明文 JSON (调试用, 部分 init 端点不需加密)
        _t: 可选, 复用外部时间戳 (initH5_1/2 共用)
        """
        if params is None:
            params = {}

        # 毫秒时间戳 (支持外部传入, 匹配浏览器 initH5_1/2 共用 t 的行为)
        timestamp = str(_t) if _t else str(int(time.time() * 1000))
        key_str = self._gen_key(timestamp)
        iv_str = self._gen_iv()

        # 构建完整参数: Ne() + {t} + 业务参数
        full_params = self._common_params()
        full_params['t'] = timestamp
        full_params.update(params)

        # 签名: ze(params, endpoint) = MD5(sorted_values + signKey + path).upper()
        full_params['sign'] = self._generate_sign(full_params, endpoint)

        api_url = self.host + endpoint
        headers = dict(self.headers)
        headers['t'] = timestamp

        if self._user_id:
            headers['userId'] = self._user_id
        if self._session_id:
            headers['sessionId'] = self._session_id

        # 必填请求头 (JS Ve 拦截器会设置这些)
        headers['deviceId'] = self._device_id or ''
        headers['bundleId'] = BUNDLE_ID

        # 明文或加密
        if skip_encrypt:
            body = json.dumps(full_params, ensure_ascii=False, separators=(',', ':'))
            headers['Content-Type'] = 'application/json'
            headers['encrypt'] = 'false'
        else:
            plain = json.dumps(full_params, ensure_ascii=False, separators=(',', ':'))
            body = self._aes_encrypt(plain, key_str, iv_str)
            headers['Content-Type'] = 'text/plain'
            headers['encrypt'] = 'true'

        try:
            r = self.session.post(api_url, data=body,
                                  headers=headers, timeout=TIMEOUT, verify=False)

            resp = r.json()

            # code=10000 表示成功，解密响应 data（仅加密请求需解密）
            if resp.get('code') == 10000 and isinstance(resp.get('data'), str) and resp['data']:
                try:
                    decrypted = self._aes_decrypt(resp['data'], key_str, iv_str)
                    resp['data'] = json.loads(decrypted)
                except Exception:
                    pass

            return resp

        except requests.exceptions.Timeout:
            return None
        except requests.exceptions.ConnectionError:
            return None
        except json.JSONDecodeError:
            return None
        except Exception:
            return None

    # ============================================================
    # 会话初始化（匹配 JS 端流程）
    # ============================================================
    def _ensure_session(self):
        """
        初始化会话: 优先从文件缓存恢复 → 否则 appConfig → 生成 deviceId → initH5_1 → initH5_2 → deviceLogin
        真实浏览器流程: appConfig 最先调，initH5_1/2 共用同一个 t 时间戳
        缓存策略: 避免 T3 新建实例时重复 deviceLogin 触发 429 限流
        """
        if self._session_inited:
            return

        # 优先从缓存恢复（跳过整个 init 流程，避免 429）
        if self._load_session_cache():
            self._session_inited = True
            # 旧缓存可能没有 video_type_list，补一次 appConfig 请求
            if not self._video_type_list:
                appcfg = self._api_request('/ht/users/appConfig')
                if appcfg and appcfg.get('code') == 10000:
                    ac_data = appcfg.get('data', {})
                    if isinstance(ac_data, dict) and ac_data.get('appConfig'):
                        ac_cfg = ac_data['appConfig']
                        if isinstance(ac_cfg, dict) and ac_cfg.get('videoTypeList'):
                            self._video_type_list = ac_cfg['videoTypeList']
            return

        # 0. 生成 deviceId (JS 端 $.getDeviceId() 在页面加载时就执行)
        if not self._device_id:
            self._device_id = self._generate_device_id()

        # 0.5 appConfig — 真实浏览器第一个调的就是它，获取 videoTypeList 供筛选
        appcfg = self._api_request('/ht/users/appConfig')
        if appcfg and appcfg.get('code') == 10000:
            ac_data = appcfg.get('data', {})
            if isinstance(ac_data, dict) and ac_data.get('appConfig'):
                ac_cfg = ac_data['appConfig']
                if isinstance(ac_cfg, dict) and ac_cfg.get('videoTypeList'):
                    self._video_type_list = ac_cfg['videoTypeList']

        # 1. initH5_1 + initH5_2 共用一个 t (匹配浏览器行为)
        shared_t = int(time.time() * 1000)
        resp1 = self._api_request('/ht/users/initH5_1', _t=shared_t)

        if resp1 and resp1.get('code') == 10000:
            data = resp1.get('data', {})
            if data.get('deviceId'):
                self._device_id = data['deviceId']
            # 保存分类列表供 homeContent 使用
            if data.get('typeTitleList'):
                self._categories = data['typeTitleList']

        # 2. initH5_2 (复用 shared_t)
        self._api_request('/ht/users/initH5_2', _t=shared_t)

        # 3. deviceLogin → 获取 userId / sessionId
        resp = self._api_request('/ht/users/deviceLogin', {
            'bundleId': BUNDLE_ID,
            'brandId': BRAND_ID,
            'projectId': PROJECT_ID,
        })
        if resp and resp.get('code') == 10000:
            data = resp.get('data', {})
            self._user_id = data.get('userId', '')
            self._session_id = data.get('sessionId', '')

        self._session_inited = True
        self._save_session_cache()

    # ============================================================
    # 图片代理
    # ============================================================
    def get_proxy_image_url(self, img_url):
        if not img_url:
            return ''
        base_proxy = self.getProxyUrl()
        if not base_proxy:
            base_proxy = 'http://127.0.0.1:9980/proxy?do=py'
        return base_proxy + '&type=' + PROXY_TYPE + '&url=' + quote(img_url, safe='')

    def _fmt_duration(self, seconds):
        try:
            s = int(seconds or 0)
        except (TypeError, ValueError):
            return ''
        if s <= 0:
            return ''
        m, s = divmod(s, 60)
        return f"{m}:{s:02d}"

    # ============================================================
    # 初始化
    # ============================================================
    def init(self, extend=""):
        cached_host, valid = self._get_cached_site()
        if valid:
            self.host = cached_host
            self._speed_test_done = True

    # ============================================================
    # 首页
    # ============================================================
    # T3 首页统一入口: 同时返回分类列表 + 首页视频数据
    # ============================================================
    # 女优/专题/ 由下方特殊分类 (actor/topic) 单独处理，此处过滤掉 typeTitleList 中的同名项，避免重复且第一份无数据
    _CATEGORY_BLACKLIST = {'成人游戏', '漫画', '小说', '蜜穴女友', '一键脱衣', '春药商城', '同城交友', '吃瓜', '成人漫画', '女优', '专题'}

    def homeContent(self, filter):
        self._select_best_site()
        self._ensure_session()

        classes = []
        filters = {}

        # 动态加载真实分类（来自 initH5_1 typeTitleList），过滤掉不需要的
        for cat in self._categories:
            cid = str(cat.get('contentId', ''))
            title = cat.get('title', '')
            if not cid or not title or title in self._CATEGORY_BLACKLIST:
                continue
            classes.append({'type_id': cid, 'type_name': title})

            # ---- 构建该分类的筛选器 ----
            cat_filters = []

            # 1. 二级分类 (videoTypeList 中 typePid == contentId 的子项)
            sub_cats = [v for v in self._video_type_list if str(v.get('typePid', '')) == cid]
            if sub_cats:
                sub_values = [{'n': '全部', 'v': ''}]
                for sc in sub_cats:
                    sc_id = str(sc.get('typeId', ''))
                    sc_name = sc.get('typeName', '')
                    if sc_id and sc_name:
                        sub_values.append({'n': sc_name, 'v': sc_id})
                if len(sub_values) > 1:
                    cat_filters.append({'key': 'label', 'name': '分类', 'value': sub_values})

            # 2. 标签 (尝试从 videoTypeList 中匹配该 contentId 对应一级类型的 tags)
            #    一级类型 typePid==0 且 typeId 可能等于 contentId
            first_level = [v for v in self._video_type_list
                           if str(v.get('typePid', '')) == '0' and str(v.get('typeId', '')) == cid]
            if first_level:
                tags_str = first_level[0].get('tags', '')
                if tags_str:
                    tag_list = [t.strip() for t in tags_str.split(',') if t.strip()]
                    if tag_list:
                        tag_values = [{'n': '全部', 'v': ''}]
                        for t in tag_list:
                            tag_values.append({'n': t, 'v': t})
                        cat_filters.append({'key': 'tag', 'name': '标签', 'value': tag_values})

            # 3. 排序 (JS sortList: ["最近更新","最多播放","最多收藏"] → 索引 0/1/2)
            cat_filters.append({'key': 'sort', 'name': '排序', 'value': [
                {'n': '最近更新', 'v': '0'},
                {'n': '最多播放', 'v': '1'},
                {'n': '最多收藏', 'v': '2'},
            ]})

            if cat_filters:
                filters[cid] = cat_filters

        # ---- 添加特殊分类: 女优 (actor) ----
        classes.append({'type_id': 'actor', 'type_name': '女优'})

        # 动态生成筛选值 (API 只接受单值精确匹配)
        _actors_filters = []

        # 身高: 150-164cm
        _actors_filters.append({'key': 'height', 'name': '身高', 'value': [
            {'n': '身高', 'v': ''},
        ] + [{'n': f'{h}cm', 'v': str(h)} for h in range(150, 165)]})

        # 罩杯: A-G
        _actors_filters.append({'key': 'cup', 'name': '罩杯', 'value': [
            {'n': '罩杯', 'v': ''},
        ] + [{'n': f'{c}罩杯', 'v': c} for c in 'ABCDEFG']})

        # 年龄: 1976-2002 (出生年份)
        _actors_filters.append({'key': 'birthday', 'name': '年龄', 'value': [
            {'n': '年龄', 'v': ''},
        ] + [{'n': f'{y}年', 'v': str(y)} for y in range(2002, 1975, -1)]})

        # 出道: 2001-2025
        _actors_filters.append({'key': 'debut', 'name': '出道', 'value': [
            {'n': '出道', 'v': ''},
        ] + [{'n': f'{y}年', 'v': str(y)} for y in range(2025, 2000, -1)]})

        filters['actor'] = _actors_filters

        # ---- 添加特殊分类: 专题 (topic) ----
        classes.append({'type_id': 'topic', 'type_name': '专题'})

        # 同时返回首页推荐视频列表 (兼容 T3 统一返回模式)
        home_videos = self.categoryContent('home', 1, '', {})
        return {
            'class': classes,
            'filters': filters,
            'type': '影视',
            'list': home_videos.get('list', []),
            'page': home_videos.get('page', 1),
            'pagecount': home_videos.get('pagecount', 1),
            'limit': home_videos.get('limit', 0),
            'total': home_videos.get('total', 0),
        }

    def homeVideoContent(self, tid, pg, filter, extend):
        return self.categoryContent(tid or 'home', pg, filter, extend)

    # ============================================================
    # 分类列表
    # ============================================================
    def categoryContent(self, tid, pg, filter, extend):
        tid = str(tid)
        pg = int(pg)

        self._select_best_site()
        self._ensure_session()

        vod_list = []

        # ---- @ folder 模式: 点击文件夹 → 获取视频列表 ----
        if '@' in tid:
            real_tid = tid.replace('@', '')
            if real_tid.startswith('actor_'):
                actor_id = real_tid[len('actor_'):]

                # 先查演员名
                detail_resp = self._api_request('/ht/content/queryActorDetail', {
                    'actorId': actor_id,
                })
                actor_name = ''
                if detail_resp and detail_resp.get('code') == 10000:
                    detail_data = detail_resp.get('data', {})
                    actor_info = (detail_data.get('actorDetail') or detail_data or {})
                    actor_name = (actor_info.get('actorName') or actor_info.get('actor_name') or '')

                # 用演员名搜索视频
                if actor_name:
                    resp = self._api_request('/ht/content/search', {
                        'keywords': actor_name,
                        'pageNo': str(pg - 1),
                        'pageSize': '20',
                    })
                else:
                    # 降级: 用 actorId 尝试 queryTypeVideosH5
                    resp = self._api_request('/ht/content/queryTypeVideosH5', {
                        'actorId': actor_id,
                        'pageNo': str(pg - 1),
                        'pageSize': '20',
                        'type': '1',
                    })

                if not resp or resp.get('code') != 10000:
                    return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 0, 'total': 0}

                data = resp.get('data', {})
                vod_list = self._extract_videos_from_data(data)
                total_page = int(data.get('totalPage') or data.get('total_page') or 1)
                return {'list': vod_list, 'page': pg, 'pagecount': max(total_page, 1),
                        'limit': len(vod_list), 'total': max(total_page, 1) * 20}

            elif real_tid.startswith('topic_'):
                topic_id = real_tid[len('topic_'):]
                resp = self._api_request('/ht/content/queryOriTopicVideos', {
                    'topicId': topic_id,
                    'pageNo': str(pg - 1),
                    'pageSize': '20',
                })
                if not resp or resp.get('code') != 10000:
                    return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 0, 'total': 0}

                data = resp.get('data', {})
                vod_list = self._extract_videos_from_data(data)
                total_page = int(data.get('totalPage') or data.get('total_page') or 1)
                return {'list': vod_list, 'page': pg, 'pagecount': max(total_page, 1),
                        'limit': len(vod_list), 'total': max(total_page, 1) * 20}

            else:
                return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 0, 'total': 0}

        # ---- 女优列表 (folder 模式) ----
        if tid == 'actor':
            # 构建 API 参数, 映射 extend 中的筛选 key → API 参数名
            api_params = {
                'pageNo': str(pg - 1),
                'pageSize': '20',
            }
            if isinstance(extend, dict):
                _actor_filter_map = {
                    'height': 'actorHeight',
                    'cup': 'cupSize',
                    'birthday': 'actorBirthday',
                    'debut': 'actorDebut',
                }
                for ek, ak in _actor_filter_map.items():
                    val = extend.get(ek, '')
                    if val:
                        api_params[ak] = val

            resp = self._api_request('/ht/content/getActors', api_params)
            if not resp or resp.get('code') != 10000:
                return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 0, 'total': 0}

            data = resp.get('data', {})
            vod_list = self._parse_actor_list(data)
            total_page = int(data.get('totalPage') or 1)
            return {'list': vod_list, 'page': pg, 'pagecount': total_page,
                    'limit': len(vod_list), 'total': total_page * 20}

        # ---- 专题列表 (folder 模式) ----
        if tid == 'topic':
            resp = self._api_request('/ht/content/getOriTopicList', {
                'pageNo': str(pg - 1),
                'pageSize': '20',
            })
            if not resp or resp.get('code') != 10000:
                return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 0, 'total': 0}

            data = resp.get('data', {})
            vod_list = self._parse_topic_list(data)
            return {'list': vod_list, 'page': pg, 'pagecount': 50, 'limit': len(vod_list),
                    'total': len(vod_list) * 50}

        if tid in ('home', 'new', 'hot'):
            # 首页/最新/热门 → 使用 queryTypeVideosH5
            # homeH5 端点始终返回 20001，改用已验证通的 queryTypeVideosH5
            sort_map = {'home': '1', 'new': '1', 'hot': '2'}
            resp = self._api_request('/ht/content/queryTypeVideosH5', {
                'pageNo': str(pg - 1),
                'pageSize': '20',
                'sort': sort_map.get(tid, '1'),
                'type': '1',
            })
            if not resp or resp.get('code') != 10000:
                return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 0, 'total': 0}

            data = resp.get('data', {})

            items = (data.get('typeVideoList') or data.get('list') or data.get('data') or data.get('videoList') or [])

            if isinstance(items, list):
                for v in items:
                    parsed = self._parse_video(v)
                    if parsed:
                        vod_list.append(parsed)

        else:
            # 数值分类 (contentId) → queryTypeVideosH5
            # T3 通过 extend dict 传递筛选和排序参数
            #   extend: {'label': '子分类id', 'tag': '标签名', 'sort': '排序值'}
            api_params = {
                'pageNo': str(pg - 1),
                'pageSize': '20',
                'typeId': tid,          # 按分类过滤（queryTypeVideosH5 → typeId）
                'type': '1',            # 媒体类型 1=视频（home 分支也带，缺少会导致 API 返回默认列表）
            }
            if isinstance(extend, dict):
                for key in ('label', 'tag', 'sort'):
                    val = extend.get(key, '')
                    if val:
                        api_params[key] = val

            resp = self._api_request('/ht/content/queryTypeVideosH5', api_params)
            if not resp or resp.get('code') != 10000:
                return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 0, 'total': 0}

            data = resp.get('data', {})
            items = (data.get('typeVideoList') or data.get('list') or data.get('data') or data.get('videoList') or [])

            if isinstance(items, list):
                for v in items:
                    parsed = self._parse_video(v)
                    if parsed:
                        vod_list.append(parsed)

        # 使用 API 返回的真实 totalPage（pageSize 固定 20）
        total_page = int(data.get('totalPage') or 1)
        return {
            'list': vod_list,
            'page': pg,
            'pagecount': total_page,
            'limit': len(vod_list),
            'total': total_page * 20,
        }

    # ============================================================
    # 辅助: 从 data 提取视频列表
    # ============================================================
    def _extract_videos_from_data(self, data):
        """从响应 data 中提取视频列表（多种格式兼容）"""
        # data 可能是 dict 或 list
        if isinstance(data, list):
            items = data
        elif not isinstance(data, dict):
            return []
        else:
            items = (data.get('videoList') or data.get('list') or data.get('data')
                     or data.get('videos') or data.get('typeVideoList')
                     or data.get('topicVideoIdList') or data.get('searchList')
                     or data.get('contentList') or data.get('records')
                     or data.get('pageData') or [])
        if not isinstance(items, list):
            return []
        return [p for v in items if (p := self._parse_video(v))]

    # ============================================================
    # 辅助: 从 dict item 中尝试获取字段值（多种命名兼容）
    # ============================================================
    @staticmethod
    def _try_get(item, *keys):
        """依次尝试多个字段名, 返回第一个非空值"""
        for k in keys:
            v = item.get(k)
            if v is not None and v != '':
                return v
        return ''

    # ============================================================
    # 解析女优列表（getActors API 响应 → folder list, vod_id + '@'）
    # ============================================================
    def _parse_actor_list(self, data):
        """解析 getActors 返回的演员列表，生成带 @ 后缀的 folder 条目"""
        # data 可能是 dict 或 list
        if isinstance(data, list):
            items = data
        elif not isinstance(data, dict):
            return []
        else:
            items = (data.get('actorList') or data.get('actors') or data.get('list')
                     or data.get('data') or [])
        if not isinstance(items, list):
            return []

        results = []
        seen = set()
        for item in items:
            if not isinstance(item, dict):
                continue

            actor_id = str(self._try_get(item,
                'actorId', 'contentId', 'id', 'artId', 'actor_id', 'userId'))
            actor_name = str(self._try_get(item,
                'actorName', 'name', 'title', 'artName', 'actor_name', 'actor'))
            actor_img = str(self._try_get(item,
                'actorPic', 'actorImg', 'img', 'avatar', 'cover',
                'imageUrl', 'headImg', 'head', 'photo', 'image', 'pic', 'actor_img'))
            actor_count = str(self._try_get(item,
                'videoCount', 'contentCount', 'count', 'totalCount',
                'total', 'video_count'))

            if not actor_id:
                continue
            if actor_id in seen:
                continue
            seen.add(actor_id)

            # 兜底: 无图时用 favicon 保证 item 可见
            if not actor_img:
                actor_img = self.host + '/favicon.ico'
            remarks = f'{actor_count}部' if actor_count else ''
            results.append({
                'vod_id': 'actor_' + actor_id + '@',
                'vod_name': actor_name or ('演员' + actor_id),
                'vod_pic': self.get_proxy_image_url(actor_img),
                'vod_tag': 'folder',
                'vod_remarks': remarks,
            })

        return results

    # ============================================================
    # 解析专题列表（getOriTopicList API 响应 → folder list, vod_id + '@'）
    # ============================================================
    def _parse_topic_list(self, data):
        """解析 getOriTopicList 返回的专题列表，生成带 @ 后缀的 folder 条目"""
        # data 可能是 dict 或 list
        if isinstance(data, list):
            items = data
        elif not isinstance(data, dict):
            return []
        else:
            items = (data.get('topicList') or data.get('oriTopicList') or data.get('list')
                     or data.get('data') or data.get('topics') or [])
        if not isinstance(items, list):
            return []

        results = []
        seen = set()
        for item in items:
            if not isinstance(item, dict):
                continue

            topic_id = str(self._try_get(item,
                'topicId', 'id', 'contentId', 'oriTopicId', 'topic_id'))
            topic_name = str(self._try_get(item,
                'topicName', 'name', 'title', 'oriTopicName', 'topic_name', 'topic'))
            topic_img = str(self._try_get(item,
                'topicPic', 'topicImg', 'img', 'cover', 'imageUrl', 'pic',
                'thumb', 'image', 'topic_img', 'oriTopicImg'))
            topic_count = str(self._try_get(item,
                'videoCount', 'count', 'contentCount', 'totalCount',
                'total', 'video_count'))

            if not topic_id:
                continue
            if topic_id in seen:
                continue
            seen.add(topic_id)

            # 兜底: 无图时用 favicon 保证 item 可见
            if not topic_img:
                topic_img = self.host + '/favicon.ico'
            remarks = f'{topic_count}部' if topic_count else ''
            results.append({
                'vod_id': 'topic_' + topic_id + '@',
                'vod_name': topic_name or ('专题' + topic_id),
                'vod_pic': self.get_proxy_image_url(topic_img),
                'vod_tag': 'folder',
                'vod_remarks': remarks,
            })

        return results

    # ============================================================
    # 解析视频条目
    # ============================================================
    def _parse_video(self, item):
        # 仅过滤真正的广告: contentType=3 且带 jumpScheme 跳转链接
        # 注意: 部分真实影片 contentType 也会是 3, 不能一刀切过滤, 否则女优影片被吞
        if item.get('contentType') == 3 and item.get('jumpScheme'):
            return None


        vid = str(item.get('contentId') or item.get('id') or item.get('videoId') or '')
        title = item.get('title') or item.get('name') or item.get('videoTitle') or ''
        pic = item.get('img') or item.get('cover') or item.get('coverUrl') or item.get('pic') or item.get('imageUrl') or ''
        remarks = item.get('duration') or item.get('playCount') or item.get('remark') or ''

        # 时长格式化
        if remarks and str(remarks).isdigit():
            remarks = self._fmt_duration(remarks)

        return {
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': self.get_proxy_image_url(pic) if pic else '',
            'vod_remarks': str(remarks) if remarks else '',
        }

    # ============================================================
    # 详情页
    # ============================================================
    def detailContent(self, ids):
        did = ids[0] if isinstance(ids, list) else ids

        self._select_best_site()
        self._ensure_session()

        resp = self._api_request('/ht/content/detail', {'contentId': str(did)})
        if not resp or resp.get('code') != 10000:
            return {'list': []}

        detail = resp.get('data', {})

        if not detail:
            return {'list': []}

        # 真实标题/封面/简介/时长/演员 均在嵌套的 videoDetail 中, 顶层仅有播放地址
        vd = detail.get('videoDetail') or {}

        # 兼容多种字段名 (优先 videoDetail, 回退顶层)
        title = (vd.get('title') or detail.get('title') or detail.get('name') or
                 detail.get('videoTitle') or '未知标题')
        pic = (vd.get('img') or vd.get('cover') or vd.get('coverUrl') or
               detail.get('img') or detail.get('cover') or
               detail.get('coverUrl') or detail.get('imageUrl') or '')
        desc = (vd.get('description') or vd.get('desc') or
                detail.get('description') or detail.get('desc') or detail.get('intro') or '')
        duration = vd.get('duration') or detail.get('duration', 0)
        actor = (vd.get('author') or vd.get('actor') or vd.get('actors') or
                 detail.get('actor') or detail.get('actors') or '')

        # 播放地址在顶层: playUrl(m3u8) / downUrl(mp4)
        play_url = (detail.get('playUrl') or detail.get('videoUrl') or
                    detail.get('downUrl') or detail.get('url') or
                    detail.get('m3u8Url') or detail.get('sl') or '')

        vod_play_url = '播放$' + str(did)
        if play_url:
            vod_play_url = '播放$' + play_url

        return {'list': [{
            'vod_id': str(did),
            'vod_name': title,
            'vod_pic': self.get_proxy_image_url(pic) if pic else '',
            'vod_actor': str(actor) if actor else '',
            'vod_director': '',
            'vod_content': desc,
            'vod_year': '',
            'vod_area': '',
            'vod_remarks': self._fmt_duration(duration),
            'vod_play_from': '蜜桃视频',
            'vod_play_url': vod_play_url,
            'type': 'video',
        }]}

    # ============================================================
    # 搜索
    # ============================================================
    def searchContent(self, key, quick, pg=1):
        self._select_best_site()
        self._ensure_session()

        pg = int(pg)
        resp = self._api_request('/ht/content/search', {
            'keywords': key,
            'pageNo': pg - 1,
            'pageSize': 20,
        })
        if not resp or resp.get('code') != 10000:
            return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 0, 'total': 0}

        data = resp.get('data', {})

        # 兼容多种 data 形态：list / dict
        if isinstance(data, list):
            items = data
            total_n = len(data)
        elif isinstance(data, dict):
            items = (data.get('searchList')
                  or data.get('list')
                  or data.get('data')
                  or data.get('videoList')
                  or data.get('records')
                  or data.get('resultList')
                  or data.get('content')
                  or [])
            total_n = data.get('total') or data.get('totalCount') or data.get('totalNum') or 0
        else:
            return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 0, 'total': 0}

        if not isinstance(items, list):
            return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 0, 'total': 0}

        vod_list = [p for v in items if (p := self._parse_video(v))]
        total_page = int(data.get('totalPage') or 1) if isinstance(data, dict) else max(1, len(vod_list) // 20)
        return {
            'list': vod_list,
            'page': pg,
            'pagecount': total_page,
            'limit': len(vod_list),
            'total': total_page * 20,
        }

    # ============================================================
    # 播放解析
    # ============================================================
    def playerContent(self, flag, id, vipFlags=None):
        url = id.split('$')[-1]

        # 如果已经是完整 URL
        if url.startswith('http'):
            return {
                'parse': 0,
                'url': url,
                'jx': 0,
                'header': {
                    'User-Agent': self.headers['User-Agent'],
                    'Referer': self.host + '/',
                },
            }

        # 否则作为 videoId 重新获取
        self._select_best_site()
        self._ensure_session()

        resp = self._api_request('/ht/content/detail', {'contentId': url})
        if not resp or resp.get('code') != 10000:
            return {'parse': 0, 'url': '', 'jx': 0}

        detail = resp.get('data', {})
        play_url = (detail.get('playUrl') or detail.get('videoUrl') or
                    detail.get('downUrl') or detail.get('url') or
                    detail.get('m3u8Url') or detail.get('sl') or '')

        return {
            'parse': 0,
            'url': play_url,
            'jx': 0,
            'header': {
                'User-Agent': self.headers['User-Agent'],
                'Referer': self.host + '/',
            },
        }

    # ============================================================
    # 图片代理
    # ============================================================
    def localProxy(self, params):
        try:
            if params.get('type') != PROXY_TYPE:
                return [404, 'text/plain', 'not found']

            img_url = params.get('url', '')
            if not img_url:
                return [400, 'text/plain', 'missing url']

            img_url = unquote(img_url)

            r = requests.get(img_url, headers={
                'User-Agent': self.headers['User-Agent'],
                'Referer': self.host + '/',
            }, timeout=TIMEOUT, verify=False)

            if r.status_code != 200:
                return [404, 'text/plain', 'image not found']

            data = r.content

            # 尝试 XOR 0x88 解密 (蜜桃图片防盗链, _xfile.jpg 全部 XOR)
            if data[:2] != b'\xff\xd8' and data[:4] != b'\x89PNG' \
                    and not (data[:4] == b'RIFF' and data[8:12] == b'WEBP'):
                decoded = bytes(b ^ 0x88 for b in data)
                if decoded[:2] == b'\xff\xd8' or decoded[:4] == b'\x89PNG' \
                        or (decoded[:4] == b'RIFF' and decoded[8:12] == b'WEBP'):
                    data = decoded

            if data[:2] == b'\xff\xd8':
                return [200, 'image/jpeg', data, {'Content-Length': str(len(data))}]
            elif data[:4] == b'\x89PNG':
                return [200, 'image/png', data, {'Content-Length': str(len(data))}]
            elif data[:4] == b'RIFF' and data[8:12] == b'WEBP':
                return [200, 'image/webp', data, {'Content-Length': str(len(data))}]
            else:
                mime = r.headers.get('Content-Type', 'image/jpeg')
                if mime.startswith('image/'):
                    return [200, mime, data, {'Content-Length': str(len(data))}]
                return [404, 'text/plain', 'invalid image format']
        except Exception:
            return [500, 'text/plain', 'proxy error']
