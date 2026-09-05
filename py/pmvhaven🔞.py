# -*- coding: utf-8 -*-

import json, re, requests
from urllib.parse import quote
from datetime import datetime, timezone, timedelta

API = 'https://pmvhaven.com/api'
H = {
    'Accept': 'application/json, text/plain, */*',
    'Origin': 'https://pmvhaven.com',
    'Referer': 'https://pmvhaven.com/',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
}
PHEADERS = {
    'User-Agent': 'Mozilla/5.0',
    'Referer': 'https://pmvhaven.com/',
    'Origin': 'https://pmvhaven.com',
}


class Spider:

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(H)

    # ---------- 工具 ----------
    def _get(self, url):
        r = self.session.get(url, timeout=25)
        r.raise_for_status()
        return r.json()

    def _video_item(self, v):
        """列表里一个视频 -> vod 条目"""
        return {
            'vod_id': v.get('_id') or v.get('id') or '',
            'vod_name': v.get('title') or 'Untitled',
            'vod_pic': v.get('thumbnailUrl') or '',
            'vod_remarks': '%s·%s' % (v.get('duration') or '', v.get('views') or ''),
        }

    def _play_url(self, d):
        """从视频详情取播放地址列表 [ '标题$url', ... ]"""
        plays = []
        if d.get('hlsMasterPlaylistUrl'):
            plays.append('自动$' + d.get('hlsMasterPlaylistUrl'))
        for v in (d.get('hlsVariants') or []):
            if v.get('playlistUrl'):
                plays.append('%s$%s' % (v.get('resolution') or '源', v.get('playlistUrl')))
        if not plays and d.get('videoUrl'):
            plays.append('源$' + (d.get('videoUrl') or ''))
        return plays

    # ---------- 首页 ----------
    def homeContent(self, filter):
        
        classes = [
            {'type_id': 'latest',   'type_name': '最新更新'},
            {'type_id': 'trending',  'type_name': '热点趋势'},
            {'type_id': 'popular',   'type_name': '人气流行'},
            {'type_id': 'playlists', 'type_name': '播放列表'},
            {'type_id': 'browse',    'type_name': '分类标签'},            
        ]
        filters = {
            'popular': [
                {'key': 'period', 'name': '时间', 'value': [
                    {'n': '全部', 'v': ''},
                    {'n': '今日', 'v': '1'},
                    {'n': '本周', 'v': '7'},
                    {'n': '本月', 'v': '30'},
                ]},
            ],
            'trending': [
                {'key': 'period', 'name': '时间', 'value': [                        
                    {'n': '1小时', 'v': '1h&tab=hot'},
                    {'n': '6小时', 'v': '6h&tab=hot'},
                    {'n': '今日', 'v': ''},
                                      
                ]},
            ],
        }
        return {'class': classes, 'filters': filters}

    def homeVideoContent(self):
        j = self._get('%s/videos?page=1&limit=24&sort=random' % API)
        items = [self._video_item(v) for v in (j.get('videos') or [])]
        return {'list': items}
    # ---------- 分类 ----------
    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = int(str(pg).strip())
        except Exception:
            pg = 1
        tid = str(tid)
        # 文件夹下钻: vod_id 以 @ 标记
        if '@' in tid:
            return self._category_folder(tid, pg)
        if tid == 'popular':
            # v 为空=ALLTIME；否则为天数(N)，换算为 uploadDateFrom=now-N天
            period = (extend or {}).get('period') or ''
            url = '%s/videos?page=%d&limit=24&sort=-views' % (API, pg)
            if period:
                try:
                    days = int(str(period).strip())
                    dt = (datetime.now(timezone.utc) - timedelta(days=days)).strftime('%Y-%m-%dT00:00:00.000Z')
                    url += '&uploadDateFrom=%s' % dt
                except Exception:
                    pass
            j = self._get(url)
            items = [self._video_item(v) for v in (j.get('videos') or [])]
            pgmeta = j.get('pagination') or {}
            total = int(pgmeta.get('total') or 0)
            limit = 24

        elif tid == 'trending':
            # period 由筛选器传入（已自带 &tab=hot），如 '24h&tab=hot'
            period = (extend or {}).get('period') or '24h&tab=hot'
            url = '%s/videos/trending?page=%d&limit=24&period=%s' % (API, pg, period)
            j = self._get(url)
            items = [self._video_item(v) for v in (j.get('videos') or [])]
            total = int(j.get('count') or 0)
            limit = 24

        elif tid == 'random':
            url = '%s/videos?page=%d&limit=24&sort=random' % (API, pg)
            j = self._get(url)
            items = [self._video_item(v) for v in (j.get('videos') or [])]
            pgmeta = j.get('pagination') or {}
            total = int(pgmeta.get('total') or 0)
            limit = 24

        elif tid == 'browse':
            # 标签云 -> 文件夹(无封面), 点开下钻视频
            url = '%s/tags/popular?page=%d&limit=30' % (API, pg)
            j = self._get(url)
            tags = j.get('data') or []
            items = []
            for t in tags:
                name = t.get('name') or ''
                if not name:
                    continue
                items.append({
                    'vod_id': 'tag@' + name,
                    'vod_name': name,
                    'vod_pic': '',
                    'vod_tag': 'folder',
                    'vod_remarks': '▶ %s' % (t.get('usageCount') or ''),
                })
            pgmeta = j.get('pagination') or {}
            total = int(pgmeta.get('total') or 0)
            limit = 30

        elif tid == 'playlists':
            # 合集 -> 文件夹(带封面), 点开下钻各集; 私密合集(isPublic=false)标注
            url = '%s/playlists?page=%d&limit=24' % (API, pg)
            j = self._get(url)
            pls = j.get('data') or []
            items = []
            for p in pls:
                pid = p.get('_id') or p.get('id') or ''
                if not pid:
                    continue
                cnt = len(p.get('videos') or [])
                private = not p.get('isPublic')
                items.append({
                    'vod_id': 'pl@' + pid,
                    'vod_name': p.get('name') or 'Playlist',
                    'vod_pic': p.get('thumbnailUrl') or '',
                    'vod_tag': 'folder',
                    'vod_remarks': ('🔒私密 ' if private else '') + '%s 视频' % cnt,
                })
            meta = j.get('meta') or {}
            total = int(meta.get('total') or meta.get('count')
                        or (meta.get('pagination') or {}).get('total') or 0)
            limit = 24

        elif tid == 'latest':
            # 最新
            url = '%s/videos?page=%d&limit=24&sort=-releaseDate' % (API, pg)
            j = self._get(url)
            items = [self._video_item(v) for v in (j.get('videos') or [])]
            pgmeta = j.get('pagination') or {}
            total = int(pgmeta.get('total') or 0)
            limit = 24

        else:
            # 未知 tid 兜底，避免变量未定义
            items, total, limit = [], 0, 24

        pagecount = max(1, (total + limit - 1) // limit) if total else 1
        return {'list': items, 'total': total, 'page': pg, 'pagecount': pagecount, 'limit': limit}

    # ---------- 文件夹下钻 (标签/合集) ----------
    def _category_folder(self, tid, pg):
        key = str(tid).rstrip('@')
        if key.startswith('tag@'):
            name = key[4:]
            url = '%s/videos?page=%d&limit=24&tag=%s&sort=-views' % (API, pg, quote(name, safe=''))
            j = self._get(url)
            items = [self._video_item(v) for v in (j.get('videos') or [])]
            pgmeta = j.get('pagination') or {}
            total = int(pgmeta.get('total') or 0)
            limit = 24
        elif key.startswith('pl@'):
            pid = key[3:]
            try:
                dd = self._get('%s/playlists/%s' % (API, pid)).get('data') or {}
            except Exception:
                # 私有/无权限合集: 返回空，避免崩溃
                return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 24, 'total': 0}
            vids = dd.get('videoDetails') or []
            items = [self._video_item(v) for v in vids]
            total = len(vids)
            limit = 24
        else:
            items, total, limit = [], 0, 24
        pagecount = max(1, (total + limit - 1) // limit) if total else 1
        return {'list': items, 'page': pg, 'pagecount': pagecount, 'limit': limit, 'total': total}

    # ---------- 详情 ----------
    def detailContent(self, ids):
        tid = ids[0]
        if tid.startswith('pl:'):
            return self._detail_playlist(tid[3:])
        if tid.startswith('tag:'):
            return self._detail_tag(tid[4:])
        return self._detail_video(tid)

    def _detail_video(self, vid):
        url = '%s/videos/%s' % (API, vid)
        d = self._get(url).get('data') or {}
        plays = self._play_url(d)
        vod = {
            'vod_id': vid,
            'vod_name': d.get('title') or 'Untitled',
            'vod_pic': d.get('thumbnailUrl') or '',
            'vod_remarks': d.get('duration') or '',
            'vod_content': ' '.join([str(x) for x in (d.get('music') or [])]) or d.get('description') or '',
            'vod_play_from': 'PMVHaven',
            'vod_play_url': '#'.join(plays),
        }
        return {'list': [vod]}

    def _detail_playlist(self, pid):
        url = '%s/playlists/%s' % (API, pid)
        dd = self._get(url).get('data') or {}
        items = dd.get('videoDetails') or []
        plays = []
        for v in items:
            u = v.get('hlsMasterPlaylistUrl') or v.get('videoUrl')
            if u:
                plays.append('%s$%s' % (v.get('title') or 'video', u))
        vod = {
            'vod_id': 'pl:' + pid,
            'vod_name': dd.get('name') or 'Playlist',
            'vod_pic': dd.get('thumbnailUrl') or '',
            'vod_remarks': '%d 视频' % len(items),
            'vod_play_from': 'PMVHaven',
            'vod_play_url': '#'.join(plays),
        }
        return {'list': [vod]}

    def _detail_tag(self, tag):
        url = '%s/videos?page=1&limit=60&tag=%s&sort=-views' % (API, quote(tag, safe=''))
        j = self._get(url)
        items = j.get('videos') or []
        plays = []
        for v in items:
            u = v.get('hlsMasterPlaylistUrl') or v.get('videoUrl')
            if u:
                plays.append('%s$%s' % (v.get('title') or 'video', u))
        vod = {
            'vod_id': 'tag:' + tag,
            'vod_name': '#' + tag,
            'vod_pic': '',
            'vod_remarks': '%d 视频' % len(items),
            'vod_play_from': 'PMVHaven',
            'vod_play_url': '#'.join(plays),
        }
        return {'list': [vod]}

    # ---------- 搜索 ----------
    def searchContent(self, key, quick):
        url = '%s/videos?page=1&limit=24&q=%s&sort=-views' % (API, quote(key, safe=''))
        j = self._get(url)
        items = [self._video_item(v) for v in (j.get('videos') or [])]
        return {'list': items}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        if 'm3u8' in id:
            return {'parse': 0, 'url': id, 'header': json.dumps(PHEADERS), 'format': 'application/x-mpegURL'}
        return {'parse': 0, 'url': id, 'header': json.dumps(PHEADERS), 'format': 'video/mp4'}

    # ---------- 自测 ----------
    def _test(self):
        print('HOME classes:', [c['type_name'] for c in self.homeContent(0)['class']])
        for tid in ['popular', 'trending', 'random', 'browse', 'playlists']:
            r = self.categoryContent(tid, 1, False, {} if tid != 'trending' else {'period': '24h'})
            print('[%s] total=%s n=%d' % (tid, r['total'], len(r['list'])))
        # 点开第一个标签 / 合集 验证文件夹下钻
        b = self.categoryContent('browse', 1, False, {})['list']
        if b:
            r = self.categoryContent(b[0]['vod_id'], 1, False, {})
            print('TAG open:', r['list'][0]['vod_name'], 'n=', len(r['list']))
        p = self.categoryContent('playlists', 1, False, {})['list']
        if p:
            r = self.categoryContent(p[0]['vod_id'], 1, False, {})
            print('PL open:', r['list'][0]['vod_name'], 'n=', len(r['list']))


if __name__ == '__main__':
    Spider()._test()
