# -*- coding: utf-8 -*-
import requests
import random
import re


class Spider:
    def init(self, extend=""):
        self.host = "https://5721004.xyz"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.pandalive.co.kr/',
            'Origin': 'https://www.pandalive.co.kr'
        }
        self.proxies = [
            "https://hubu.515355.xyz/proxy/?",
            "https://pol.515355.xyz/proxy/",
            "https://f00.515355.xyz/proxy/",
            "https://ce2.515355.xyz/proxy/?",
        ]
        self._cache = {}

    def getName(self):
        return "PandaLive"

    def getDependence(self):
        return []

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    def localProxy(self, param):
        return None

    def _load_m3u(self):
        """解析 M3U 返回 {userId: {stream_url, annotations, tags}}"""
        if '_m3u' in self._cache:
            return self._cache['_m3u']
        m = {}
        try:
            r = requests.get(f"{self.host}/player/list.m3u", headers=self.headers, timeout=10)
            if r.status_code == 200:
                lines = r.text.split('\n')
                header_info = {}
                for line in lines[:10]:
                    if line.startswith('#主播数量'):
                        header_info['total'] = line.split('：')[-1].strip()
                    elif line.startswith('#列表说明'):
                        header_info['desc'] = line
                for i, line in enumerate(lines):
                    if line.startswith('#EXTINF') and i + 1 < len(lines):
                        parts = line.split(',')
                        if len(parts) >= 2:
                            uid = parts[1].strip()
                            nick_meta = parts[2].strip() if len(parts) > 2 else ''
                            # 提取注解: [录] [粉] [🎥] 等
                            tags = re.findall(r'\[([^\]]+)\]', nick_meta)
                            # 去掉注解后的纯昵称
                            clean_nick = re.sub(r'\[[^\]]*\]', '', nick_meta).strip()
                            m[uid] = {
                                'url': lines[i + 1].strip(),
                                'tags': tags,
                                'nick': clean_nick or uid,
                                'is_recorded': '录' in tags,
                                'is_fan': '粉' in tags,
                                'header_info': header_info,
                            }
        except Exception:
            pass
        self._cache['_m3u'] = m
        return m

    def _load_list(self):
        """加载 list.json + 合并 M3U 元数据，只返回有流的频道"""
        if '_list' in self._cache:
            return self._cache['_list']
        m3u = self._load_m3u()
        processed = []
        if not m3u:
            self._cache['_list'] = []
            return []
        try:
            r = requests.get(f"{self.host}/player/list.json", headers=self.headers, timeout=10)
            if r.status_code == 200:
                raw = r.json().get('list', [])
                # 按 m3u 顺序排列（m3u 顺序即主播列表手动更新顺序）
                seen = set()
                for uid in m3u:
                    if uid in seen:
                        continue
                    seen.add(uid)
                    # 查找 json 中对应条目
                    match = None
                    for item in raw:
                        if item.get('userId') == uid:
                            match = item
                            break
                    if not match:
                        continue
                    m3u_meta = m3u[uid]
                    nick = match.get('userNick', m3u_meta['nick'] or uid)
                    title = match.get('title', '無標題')
                    is_adult = match.get('isAdult', False)
                    is_pw = match.get('isPw', False)
                    v_type = match.get('type', '')
                    user_count = match.get('user', 0)
                    thumb = match.get('thumbUrl', '')
                    tags = list(m3u_meta['tags'])
                    if is_adult:
                        tags.append('19+')
                    tag_str = ' '.join(f'[{t}]' for t in tags)
                    processed.append({
                        'vod_id': f"live_{uid}",
                        'vod_name': f"📺 {nick}",
                        'vod_pic': thumb,
                        'vod_remarks': f"👤 {user_count} {tag_str}",
                        'vod_content': title or f'{nick} 的直播',
                        'vod_actor': uid,
                        'vod_tag': '录播' if m3u_meta['is_recorded'] else '直播',
                        '_isAdult': is_adult,
                        '_isPw': is_pw,
                        '_type': v_type,
                        '_isRecorded': m3u_meta['is_recorded'],
                        '_isFan': m3u_meta['is_fan'],
                        '_user_count': user_count,
                        '_score': match.get('totalScoreCnt', 0),
                        '_bookmark': match.get('bookmarkCnt', 0),
                    })
        except Exception:
            pass
        self._cache['_list'] = processed
        return processed

    def homeContent(self, filter):
        try:
            all_data = self._load_list()
            classes = [{'type_id': 'pandalive', 'type_name': f'🐼 PandaTV ({len(all_data)})'}]
            filters = {
                "pandalive": [
                    {
                        "key": "type",
                        "name": "類型",
                        "value": [
                            {"n": "全部", "v": "all"},
                            {"n": "🔞 19+", "v": "adult"},
                            {"n": "🔐 密碼房", "v": "pw"},
                            {"n": "💎 粉絲房", "v": "fan"},
                            {"n": "📼 錄播", "v": "recorded"},
                        ]
                    },
                    {
                        "key": "sort",
                        "name": "排序",
                        "value": [
                            {"n": "觀眾量 ↓", "v": "user-desc"},
                            {"n": "實時熱度 ↓", "v": "totalScoreCnt-desc"},
                            {"n": "關注量 ↓", "v": "bookmarkCnt-desc"},
                            {"n": "默認排序", "v": "default"},
                        ]
                    }
                ]
            }
            return {'class': classes, 'list': all_data[:30], 'filters': filters}
        except Exception as e:
            print(f"homeContent錯誤: {e}")
            return {'class': [], 'list': []}

    def homeVideoContent(self):
        try:
            return {'list': self._load_list()[:20]}
        except:
            return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            all_list = self._load_list()
            filtered = all_list

            f_type = extend.get('type', 'all')
            if f_type == 'adult':
                filtered = [v for v in filtered if v.get('_isAdult')]
            elif f_type == 'pw':
                filtered = [v for v in filtered if v.get('_isPw')]
            elif f_type == 'fan':
                filtered = [v for v in filtered if v.get('_type') == 'fan' or v.get('_isFan')]
            elif f_type == 'recorded':
                filtered = [v for v in filtered if v.get('_isRecorded')]

            sort_type = extend.get('sort', 'default')
            if sort_type == 'user-desc':
                filtered.sort(key=lambda x: x.get('_user_count', 0), reverse=True)
            elif sort_type == 'totalScoreCnt-desc':
                filtered.sort(key=lambda x: x.get('_score', 0), reverse=True)
            elif sort_type == 'bookmarkCnt-desc':
                filtered.sort(key=lambda x: x.get('_bookmark', 0), reverse=True)

            pg = int(pg)
            limit = 30
            start = (pg - 1) * limit
            end = start + limit
            page_list = filtered[start:end] if start < len(filtered) else []

            return {
                'list': page_list,
                'page': pg,
                'pagecount': (len(filtered) + limit - 1) // limit if filtered else 1,
                'limit': limit,
                'total': len(filtered)
            }
        except Exception as e:
            print(f"categoryContent錯誤: {e}")
            return {'list': [], 'page': int(pg)}

    def detailContent(self, ids):
        try:
            first_id = ids[0] if isinstance(ids, list) else ids
            user_id = first_id.replace("live_", "")

            # 从缓存列表中找对应主播信息
            all_list = self._load_list()
            vod_info = None
            for v in all_list:
                if v['vod_id'] == first_id:
                    vod_info = v
                    break

            m3u = self._load_m3u()
            meta = m3u.get(user_id)
            if not meta:
                return {'list': []}

            stream_url = meta['url']

            # 随机打乱代理顺序，避免单线路过载
            shuffled = list(self.proxies)
            random.shuffle(shuffled)
            play_links = [f"代理{i}${p}{stream_url}" for i, p in enumerate(shuffled, 1)]

            vod = {
                'vod_id': first_id,
                'vod_name': vod_info['vod_name'] if vod_info else f"PandaTV - {user_id}",
                'vod_pic': vod_info.get('vod_pic', '') if vod_info else '',
                'vod_content': vod_info.get('vod_content', f'主播: {user_id}') if vod_info else f'主播: {user_id}',
                'vod_play_from': 'PandaLive',
                'vod_play_url': '#'.join(play_links)
            }
            return {'list': [vod]}
        except Exception as e:
            print(f"detailContent錯誤: {e}")
            return {'list': []}

    def searchContent(self, key, quick, pg="1"):
        try:
            all_v = self._load_list()
            key_l = key.lower()
            res = [v for v in all_v if key_l in v['vod_name'].lower() or key_l in v['vod_actor'].lower()]
            return {'list': res[:50], 'page': int(pg)}
        except:
            return {'list': [], 'page': int(pg)}

    def playerContent(self, flag, id, vipFlags):
        return {
            'parse': 0,
            'url': id,
            'header': self.headers
        }
