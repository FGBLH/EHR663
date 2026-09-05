# coding=utf-8
#!/usr/bin/python
import base64
from datetime import datetime, timedelta
from functools import lru_cache
import json
import random
import re
import sys
import threading
import time
from urllib.parse import quote, urlparse

import requests
from urllib3.util.retry import Retry

from base.spider import Spider

sys.path.append("..")


class Spider(Spider):

  def init(self, extend="{}"):
    self.create_session_with_retry()

    self.dynamic_urls = [
        "https://zh.stripchat.com",
        "https://zh.stripchat.global",
        "https://zh.stripol.com",
    ]

    self.Doppiocdn = "doppiocdn.org"
    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:153.0) Gecko/20100101"
        " Firefox/153.0"
    )
    self.headers = {
        "User-Agent": user_agent,
        "Accept-Language": "zh,en;q=0.5",
    }

    self.host = self.dynamic_urls[0]
    self._update_headers_for_host(self.host)

    self.stripchat_preferredVideoCodec = "H264"  # 可选H264或AV1
    self.stripchat_key = "YzWScuyQRGAGcxx1KIJmiQ7BY9Vi35ftwLqUOVO8uoo="
    self.stripchat_pkey = "Fq6m2TO2ZeBkRPm9"
    self.stripchat_play = "0 0"
    self.danmu_active_room = ''
    self.danmu_cache = {}
    self.danmu_threads = {}
    self.danmu_lock = threading.Lock()

  def _update_headers_for_host(self, host_url):
    self.host = host_url
    self.headers["Origin"] = host_url
    self.headers["Referer"] = f"{host_url}/"
    self.json_headers = {
        **self.headers,
        "Accept": "application/json, text/plain, */*",
    }

  def _request_with_failover(self, path, timeout=(3, 5)):
    urls_to_try = list(self.dynamic_urls)
    if self.host in urls_to_try:
      urls_to_try.remove(self.host)
      urls_to_try.insert(0, self.host)

    last_error = None

    for domain in urls_to_try:
      clean_domain = domain.strip().rstrip('/')
      full_url = (
          f'{clean_domain}{path}' if path.startswith('/') else f'/{path}'
      )

      headers = {
          **self.headers,
          'Origin': clean_domain,
          'Referer': f'{clean_domain}/',
          'Accept': 'application/json, text/plain, */*',
      }

      try:
        response = self.session.get(full_url, headers=headers, timeout=timeout)
        if response.status_code == 200:
          data = response.json()
          if isinstance(data, dict):
            if self.host != clean_domain:
              self.log(f'[HOST] 切换可用域名为: {clean_domain}')
              self._update_headers_for_host(clean_domain)
            return data
        else:
          self.log(
              f'[HOST] 域名 {clean_domain} 请求失败，状态码: {response.status_code}，尝试下一个...'
          )
      except Exception as e:
        self.log(f'[HOST] 域名 {clean_domain} 访问异常: {e}，尝试下一个...')
        last_error = e
        continue

    self.log(f'[HOST] 所有域名均访问失败! 最后一次错误: {last_error}')
    return {}

  def getName(self):
    return 'StripChat'

  def isVideoFormat(self, url):
    pass

  def manualVideoCheck(self):
    pass

  def destroy(self):
    self.danmu_active_room = ''
    with self.danmu_lock:
      threads = list(self.danmu_threads.items())
      self.danmu_threads.clear()
    for rid, (t, evt) in threads:
      try:
        evt.set()
        t.join(timeout=1.0)
      except Exception:
        pass

  def homeVideoContent(self):
    pass

  def datetime_utc8(self, strTime, outFormat):
    try:
      dt = datetime.strptime(str(strTime), '%Y-%m-%dT%H:%M:%SZ')
    except Exception:
      return ''
    return (dt + timedelta(hours=8)).strftime(outFormat)

  def homeContent(self, filter):
    CLASSES = [
        {'type_name': '女主播', 'type_id': 'girls'},
        {'type_name': '情侣', 'type_id': 'couples'},
        {'type_name': '男主播', 'type_id': 'men'},
        {'type_name': '跨性别', 'type_id': 'trans'},
    ]
    VALUE = [
        {'n': '推荐', 'v': 'recommended'},
		{'n': '新主播', 'v': 'autoTagNew'},
        {'n': '亚洲人', 'v': 'ethnicityAsian'},
        {'n': '🇨🇳中国', 'v': 'tagLanguageChinese'},
        {'n': '🇯🇵日本', 'v': 'tagLanguageJapanese'},
        {'n': '🇰🇷韩国', 'v': 'tagLanguageKorean'},
        {'n': '🇻🇳越南', 'v': 'tagLanguageVietnamese'},
        {'v': 'tagLanguageUkrainian', 'n': '🇺🇦乌克兰'},
        {'v': 'tagLanguageRussianSpeaking', 'n': '🇷🇺俄罗斯'},
        {'v': 'tagLanguageUSModels', 'n': '🇺🇸美国'},
        {'v': 'tagLanguageColombian', 'n': '🇨🇴哥伦比亚'},
        {'v': 'tagLanguageGermanSpeaking', 'n': '🇩🇪德国'},
        {'v': 'tagLanguageFrench', 'n': '🇫🇷法国'},
        {'v': 'tagLanguageUKModels', 'n': '🇬🇧英国'},
        {'v': 'tagLanguageCanadian', 'n': '🇨🇦加拿大'},
        {'v': 'tagLanguageMexican', 'n': '🇲🇽墨西哥'},
        {'v': 'ethnicityIndian', 'n': '🇮🇳印度'},
        {'v': 'tagLanguageVenezuelan', 'n': '🇻🇪委内瑞拉'},
        {'v': 'tagLanguageRomanian', 'n': '🇷🇴罗马尼亚'},
        {'v': 'tagLanguageAfrican', 'n': '🌍非洲'},
        {'v': 'tagLanguageSpanishSpeaking', 'n': '🇪🇸西班牙'},
        {'v': 'ethnicityMiddleEastern', 'n': '🇸🇦🇦🇪阿拉伯'},
        {'v': 'tagLanguageKenyan', 'n': '🇰🇪肯尼亚'},
        {'v': 'tagLanguageSouthAfrican', 'n': '🇿🇦南非'},
        {'v': 'tagLanguageBrazilian', 'n': '🇧🇷巴西'},
        {'v': 'tagLanguageThai', 'n': '🇹🇭泰国'},
        {'v': 'tagLanguageItalian', 'n': '🇮🇹意大利'},
        {'n': '亚洲', 'v': 'ethnicityAsian'},
        {'n': '白人', 'v': 'ethnicityWhite'},
        {'n': '拉丁', 'v': 'ethnicityLatino'},
        {'n': '混血', 'v': 'ethnicityMultiracial'},
        {'n': '印度', 'v': 'ethnicityIndian'},
        {'n': '阿拉伯', 'v': 'ethnicityMiddleEastern'},
        {'n': '黑人', 'v': 'ethnicityEbony'},
		{'v': 'fuckMachine', 'n': '炮机'},
        {'n': '青年', 'v': 'ageTeen'},
        {'n': 'VR', 'v': 'autoTagVr'},
        {'n': '✨新主播', 'v': 'autoTagNew'},
        {'n': 'VR直播', 'v': 'autoTagVr'},
        {'n': '18+', 'v': 'ageTeen'},
        {'n': '鲜嫩青年22+', 'v': 'ageYoung'},
        {'n': '学生', 'v': 'subcultureStudent'},
        {'n': '口交', 'v': 'doBlowjob'},
        {'n': '深喉', 'v': 'doDeepThroat'},
        {'n': '恋足', 'v': 'doFootFetish'},
        {'n': '互动玩具', 'v': 'autoTagInteractiveToy'},
        {'n': '自慰', 'v': 'doMasturbation'},
        {'n': '肛交', 'v': 'doAnal'},
        {'n': '潮吹', 'v': 'doSquirt'},
        {'n': '狗式', 'v': 'doDoggyStyle'},
        {'n': 'Cosplay', 'v': 'doCosplay'},
        {'n': 'RolePlay', 'v': 'doRolePlay'},
    ]
    VALUE_MEN = [
        {'n': '情侣', 'v': 'sexGayCouples'},
        {'n': '直男', 'v': 'orientationStraight'},
    ]
    TIDS = ('girls', 'couples', 'men', 'trans')
    filters = {
        tid: [{'key': 'tag', 'value': VALUE_MEN + VALUE if tid == 'men' else VALUE}]
        for tid in TIDS
    }
    return {'class': CLASSES, 'filters': filters}

  def _parse_status_remark(self, is_live, status, viewers=0):
    if not is_live or status == 'off':
      status_text = '⚫ 已下播'
    elif status == 'public':
      status_text = '直播中'
    else:
      status_text = '收费房'

    return f'👤 {viewers}人 | {status_text}' if viewers else status_text

  def categoryContent(self, tid, pg, filter, extend):
    try:
      pg_str = str(pg)
      page_num = int(pg_str)

      # 搜索场景逻辑
      if tid.startswith('search '):
        _, tag, key = tid.split(maxsplit=2)
        path = f'/api/front/v4/models/search/group/username?query={key}&limit=900&primaryTag={tag}'
        rsp = self._request_with_failover(path)

        videos = []
        for u in rsp.get('models', []):
          if not u.get('isLive'):
            continue
          viewers = u.get('viewersCount', 0)
          is_live = u.get('isLive', False)
          status = u.get('status', 'off')

          remark = self._parse_status_remark(is_live, status, viewers)
          videos.append({
              'vod_id': str(u['id']),
              'vod_name': (
                  f"{self.country_code_to_flag(str(u.get('country', '')))}{u['username']}"
              ),
              'vod_pic': (
                  f"https://img.{self.Doppiocdn}/snapshot/{u['id']}/{u.get('snapshotTimestamp', '')}"
              ),
              'style': {'type': 'rect', 'ratio': 1.78},
              'vod_remarks': remark,
          })

        return {
            'list': videos,
            'page': pg_str,
            'pagecount': '1',
            'limit': '900',
            'total': str(len(videos)),
        }

      # 普通分类列表场景逻辑
      limit = 60
      offset = limit * (page_num - 1)
      path = f'/api/front/models?improveTs=false&removeShows=false&limit={limit}&offset={offset}&primaryTag={tid}&sortBy=stripRanking&rcmGrp=A&rbCnGr=true&prxCnGr=false&nic=false'
      if 'tag' in extend and extend['tag']:
        path += f'&filterGroupTags=[["{extend["tag"]}"]]'

      rsp = self._request_with_failover(path)

      videos = []
      for v in rsp.get('models', []):
        is_live = v.get('isLive', False)
        status = v.get('status', 'public')
        viewers = v.get('viewersCount', 0)

        remark = self._parse_status_remark(is_live, status, viewers)

        videos.append({
            'vod_id': str(v['id']),
            'vod_name': (
                f"{self.country_code_to_flag(str(v.get('country', '')))}{v['username']}"
            ),
            'vod_pic': (
                f"https://img.{self.Doppiocdn}/snapshot/{v['id']}/{v.get('snapshotTimestamp', '')}"
            ),
            'vod_remarks': remark,
        })

      total = int(rsp.get('filteredCount', 0))
      pagecount = (total + limit - 1) // limit if total > 0 else 1

      return {
          'list': videos,
          'page': pg_str,
          'pagecount': str(pagecount),
          'limit': str(limit),
          'total': str(total),
      }
    except Exception as e:
      self.log(f'获取分类内容失败: {e}')
      return {
          'list': [],
          'page': str(pg),
          'pagecount': '1',
          'limit': '60',
          'total': '0',
      }

  def detailContent(self, array):
    model_id = array[0]

    try:
      path = f'/api/front/v2/models/{model_id}/cam'
      rsp = self._request_with_failover(path)

      info = rsp.get('cam', {})
      user = rsp.get('user', {}).get('user', {})
      uid = str(user.get('id', model_id))
      username = str(user.get('username', ''))
      isLive = user.get('isLive', False)

      oldName = self.stripchat_play.rsplit(' ', 1)[-1]
      if model_id != oldName:
        timestp = int(time.time())
        self.stripchat_play = f'0 {timestp} {model_id}'
      flag = self.country_code_to_flag(str(user.get('country', '')).strip())

      remark = '直播中' if isLive else '⚫ 已下播'
      show = info.get('show') or info.get('groupShowAnnouncement')
      if show:
        startAt = show.get('createdAt') or show.get('startAt')
        if startAt:
          remark = (
              f"🎫 购票表演始于 {self.datetime_utc8(startAt, '%m月%d日 %H:%M')}"
          )

      director = f'{flag}{username if username else model_id}'
      try:
        if isLive:
          self.start_danmu(uid)
          self.fetch_chat_once(uid)
      except Exception as e:
        self.log(f'详情预取弹幕失败: {e}')
      desc = self.get_danmaku_desc(uid)

      vod_play_from = '飞鱼高清$$$标清线路二$$$标清线路三'
      vod_play_url = (
          f'主线路${uid}$$$备用线路$lemon_{uid}$$$备用线路三$sacf_{uid}'
      )

      return {
          'list': [{
              'vod_id': model_id,
              'vod_name': str(info.get('topic', ''))[:80] or username,
              'vod_pic': str(user.get('avatarUrl', '')),
              'vod_director': director,
              'vod_content': desc,
              'vod_remarks': remark,
              'vod_play_from': vod_play_from,
              'vod_play_url': vod_play_url,
          }]
      }
    except Exception as e:
      self.log(f'获取详情失败: {e}')
      return {'list': []}

  def searchContent(self, key, quick, pg='1'):
    if int(pg) > 1:
      return {}
    return {
        'list': [
            {
                'vod_id': f'search {t["type_id"]} {key}',
                'vod_name': t['type_name'],
                'vod_tag': 'folder',
            }
            for t in self.homeContent(False).get('class', [])
        ]
    }

  def playerContent(self, flag, id, vipFlags):
    urls = []
    try:
      sid = id.split('_')[-1]
      self.start_danmu(sid)

      headers = {
          'User-Agent': self.headers.get('User-Agent'),
          'Origin': self.host,
          'Referer': f'{self.host}/',
      }

      # --- 线路2: stripchat.global ---
      if id.startswith('lemon'):
        rsp = self.session_get(
            f'https://edge-hls.growcdnssedge.com/hls/{sid}/master/{sid}_auto.m3u8?playlistType=standard'
        ).text
        lines = rsp.strip().split('\n')
        for i, line in enumerate(lines):
          if '#EXT-X-STREAM-INF' in line:
            qn_start = line.find('NAME="') + 6
            qn = line[qn_start : line.find('"', qn_start)]
            url = lines[i + 1]
            urls.extend([qn, url])

      # --- 线路3: StripOl ---
      elif id.startswith('sacf'):
        rsp = self.session_get(
            f'https://edge-hls.sacfedge.com/hls/{sid}/master/{sid}_auto.m3u8?playlistType=standard'
        ).text
        lines = rsp.strip().split('\n')
        psch, pkey = 'v2', self.stripchat_pkey
        for i, line in enumerate(lines):
          if '#EXT-X-STREAM-INF' in line:
            qn_start = line.find('NAME="') + 6
            qn = line[qn_start : line.find('"', qn_start)]
            full_url = f'{lines[i+1]}&psch={psch}&pkey={pkey}&preferredVideoCodec={self.stripchat_preferredVideoCodec}'
            urls.extend([qn, f'{self.getProxyUrl()}&url={quote(full_url)}'])

      # --- 线路1: StripChat (主线路) ---
      else:
        rsp = self.session_get(
            f'https://edge-hls.{self.Doppiocdn}/hls/{sid}/master/{sid}_auto.m3u8?playlistType=standard'
        ).text
        lines = rsp.strip().split('\n')
        psch, pkey = 'v2', self.stripchat_pkey
        for i, line in enumerate(lines):
          if '#EXT-X-STREAM-INF' in line:
            qn_start = line.find('NAME="') + 6
            qn = line[qn_start : line.find('"', qn_start)]
            full_url = f'{lines[i+1]}&psch={psch}&pkey={pkey}&preferredVideoCodec={self.stripchat_preferredVideoCodec}'
            urls.extend([qn, f'{self.getProxyUrl()}&url={quote(full_url)}'])

      # 关联弹幕请求接口
      return {
          'url': urls,
          'parse': '0',
          'position': '0',
          'header': headers,
          'danmaku': f'{self.getProxyUrl()}&type=danmu&room={sid}',
      }
    except Exception as e:
      self.log(f'播放失败 {id}: {e}')
      return {'url': urls, 'parse': 0}

  def update_vod(self, username):
    try:
      content_data = self.detailContent([username]).get('list')[0]
      payload = {'json': json.dumps(content_data, ensure_ascii=False)}
      self.post('http://127.0.0.1:9978/action?do=refresh&type=vod', data=payload)
    except Exception as e:
      self.log(f'刷新详情失败: {e}')

  def xml_escape(self, text):
    return str(text or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

  def proxy_danmu(self, room_id):
    try:
      room_id = str(room_id)
      with self.danmu_lock:
        cache = self.danmu_cache.get(room_id, {})
        items = list(cache.get('msg', []))

      # 以最新一条消息的时间为 0 点，计算每条相对偏移
      times = []
      for it in items:
        ts = 0
        try:
          dt = datetime.strptime(str(it.get('time')), '%Y-%m-%dT%H:%M:%SZ')
          ts = (dt + timedelta(hours=8)).timestamp()
        except Exception:
          ts = 0
        times.append(ts)
      base_ts = max(times) if times else 0

      xml = [
          '<?xml version="1.0" encoding="UTF-8"?>',
          '<i>',
          '\t<chatserver>chat.stripchat.local</chatserver>',
          '\t<chatid>88888888</chatid>',
          '\t<mission>0</mission>',
          '\t<maxlimit>99999</maxlimit>',
          '\t<state>0</state>',
          '\t<real_name>0</real_name>',
          '\t<source>stripchat</source>',
      ]

      for i, item in enumerate(items[-100:]):
        text = self.xml_escape(
            (str(item.get('user', '')) + ': ' if item.get('user') else '')
            + str(item.get('text', ''))
        )
        pos = max(0.0, round(base_ts - times[i], 1)) if base_ts else round(i * 1.5, 1)
        color = (
            '16777215'
            if random.random() > 0.1
            else str(random.randint(0, 0xFFFFFF))
        )
        xml.append(f'\t<d p="{pos},1,25,{color},0">{text}</d>')

      xml.append('</i>')
      return [200, 'text/xml', '\n'.join(xml)]
    except Exception as e:
      self.log(f'弹幕输出失败: {e}')
      return [200, 'text/xml', '<?xml version="1.0" encoding="UTF-8"?><i></i>']

  def localProxy(self, param):
    type = param.get('type', '')

    if type == 'danmu':
      return self.proxy_danmu(str(param.get('room', '')))

    url = param['url']
    if type == 'media':
      data = self.session_get(url, timeout=(5, 15))
      return [200, 'video/mp4', data.content]

    rsp = self.session_get(url)
    oldCode, oldtmp, username = self.stripchat_play.rsplit(' ')
    timestp = int(time.time())
    is_time_up = (timestp - 10) > int(oldtmp)
    is_code_changed = int(oldCode) != 0 and rsp.status_code != int(oldCode)
    if is_time_up or is_code_changed:
      self.stripchat_play = f'{rsp.status_code} {timestp} {username}'
      self.log('计划更新')
      threading.Thread(
          target=self.update_vod, args=(username,), daemon=True
      ).start()
      if is_code_changed:
        self.log('code变更')
        try:
          rsp2 = self.session_get(url, timeout=(5, 10))
          if rsp2.status_code == 200:
            rsp = rsp2
        except Exception:
          pass
    if rsp.status_code == 403:
      rsp = self.session_get(
          re.sub(r'(_\d+p\d*)?\.m3u8', '_160p_blurred.m3u8', url)
      )
    if rsp.status_code != 200:
      return [404, 'text/plain', '']
    data = (
        self.process_m3u8(rsp.text)
        if '#EXT-X-MOUFLON:URI:' in rsp.text
        else rsp.text
    )
    return [200, 'application/vnd.apple.mpegur', data]

  URL_PATTERN = re.compile(
      r'https://media-hls\.doppiocdn\.\w+/b-hls-\d+/media\.mp4'
  )
  MAP_URI_PATTERN = re.compile(r'URI=["\']?(https?://[^\s"\'<>]+)["\']?')
  MOUFLON_TAIL_PATTERN = re.compile(r'(_part\d+)?\.mp4$')

  def process_m3u8(self, content):
    lines = content.strip().split('\n')
    for i, line in enumerate(lines):
      if line.startswith('#EXT-X-MOUFLON:URI:') and 'media.mp4' in lines[i + 1]:
        mouflon = line.split(':', 2)[2].strip()
        encrypted = self.MOUFLON_TAIL_PATTERN.sub('', mouflon).rsplit('_', 2)[1]
        new_url = mouflon.replace(
            encrypted, self._decode(encrypted[::-1], self.stripchat_key)
        )
        proxy_url = f'{self.getProxyUrl()}&type=media&url={quote(new_url)}'
        lines[i + 1] = self.URL_PATTERN.sub(proxy_url, lines[i + 1])
      elif line.startswith('#EXT-X-MAP:URI'):
        match = self.MAP_URI_PATTERN.search(line)
        if match:
          original_url = match.group(1)
          proxy_url = (
              f'{self.getProxyUrl()}&type=media&url={quote(original_url)}'
          )
          lines[i] = line.replace(original_url, proxy_url)
    return '\n'.join(lines)

  def country_code_to_flag(self, code):
    return (
        ''.join(
            chr(ord(c.upper()) - ord('A') + 0x1F1E6)
            for c in code
            if len(code) == 2 and code.isalpha()
        )
        if len(code) == 2 and code.isalpha()
        else code
    )

  @staticmethod
  @lru_cache(maxsize=20)
  def _decode(encrypted_b64: str, key_b64: str) -> str:
    encrypted_b64 += '=' * (4 - len(encrypted_b64) % 4)
    key_bytes = base64.b64decode(key_b64)
    encrypted = base64.b64decode(encrypted_b64)
    decrypted = bytearray(len(encrypted))
    for i in range(len(encrypted)):
      decrypted[i] = encrypted[i] ^ (key_bytes[i % len(key_bytes)] & 0xFF)
    return decrypted.decode('utf-8')

  def create_session_with_retry(self):
    self.session = requests.Session()
    retry = Retry(
        total=2,
        backoff_factor=0.2,
        status_forcelist=[408, 429, 500, 502, 503, 504],
        raise_on_status=False,
    )
    adapter = requests.adapters.HTTPAdapter(
        max_retries=retry, pool_connections=20, pool_maxsize=50, pool_block=False
    )
    self.session.mount('http://', adapter)
    self.session.mount('https://', adapter)

  def session_get(self, url, headers=None, stream=False, timeout=(3, 5)):
    return self.session.get(
        url,
        headers=self.headers if headers is None else headers,
        timeout=timeout,
        stream=stream,
        allow_redirects=True,
    )

  def start_danmu(self, room_id):
    try:
      room_id = str(room_id)
      self.danmu_active_room = room_id
      entry = self.danmu_threads.get(room_id)
      if entry:
        t, _ = entry
        if t.is_alive():
          self.log(f'弹幕线程已存在: {room_id}')
          return
      for rid, (ot, stop_evt) in list(self.danmu_threads.items()):
        if rid == room_id:
          continue
        if ot.is_alive():
          self.log(f'正在关闭其他房间弹幕线程: {rid}')
          stop_evt.set()
          ot.join(timeout=1.0)
        del self.danmu_threads[rid]
      stop_event = threading.Event()
      t = threading.Thread(
          target=self._danmu_poll_worker,
          args=(room_id, stop_event),
          daemon=True,
      )
      self.danmu_threads[room_id] = (t, stop_event)
      t.start()
      self.log(f'弹幕线程启动: {room_id}')
    except Exception as e:
      self.log(f'弹幕线程启动失败: {e}')

  def _danmu_poll_worker(self, room_id, stop_event):
    fail_count = 0
    while True:
      if self.danmu_active_room != room_id:
        break
      try:
        got_new = self.fetch_chat_once(room_id)
        fail_count = 0
        # 有新消息时刷新弹幕文件 + 节流追加到详情简介
        if got_new:
          self.refresh_desc_if_needed(room_id)
          if stop_event.wait(2):
            break
          continue
      except Exception as e:
        fail_count += 1
        self.log(f'弹幕轮询异常 {room_id}: {e}')
        if fail_count >= 10:
          self.log(f'连续失败过多次，弹幕线程退出: {room_id}')
          break
      if stop_event.wait(5):
        break
    self.log(f'弹幕线程结束: {room_id}')

  def fetch_chat_once(self, room_id):
    room_id = str(room_id)
    path = f'/api/front/v2/models/{room_id}/chat?source=regular&uniq={int(time.time()*1000)}'
    data = self._request_with_failover(path)

    arr = data.get('messages') if isinstance(data, dict) else []
    if not isinstance(arr, list):
      return 0
    newId, newMsg = 0, []
    oldId = 0
    isFirst = False
    with self.danmu_lock:
      cache = self.danmu_cache.get(room_id, {})
      oldId = cache.get('id', 0)
      isFirst = not bool(oldId)
      cacheMsg = cache.get('msg', [])
      seen = {int(m.get('id', 0)) for m in cacheMsg}
      for raw in reversed(arr):
        try:
          mid = int(raw.get('id', 0))
        except Exception:
          continue
        if oldId and mid <= oldId:
          break
        if not newId:
          newId = mid
        if mid in seen:
          continue
        item = self.normalize_chat_message(raw)
        if not item:
          continue
        item['_mid'] = mid
        newMsg.append(item)
      if newId:
        if newMsg:
          cacheMsg = newMsg + cacheMsg
          cacheMsg = cacheMsg[:30]
        self.danmu_cache[room_id] = {'id': newId, 'msg': cacheMsg}
    if newMsg:
      if isFirst or self._updating_desc:
        # 首次拉取是历史填充；刷新简介途中不重复推送实时弹幕
        return len(newMsg)
      # 轮询到新弹幕时刷新弹幕文件并实时推送
      self.call_local_action('do=refresh&type=danmaku', '刷新弹幕')
      for m in reversed(newMsg):
        m.pop('_mid', None)
        self.send_live_danmaku(m)
        time.sleep(0.05)
    return len(newMsg)

  _desc_refresh_ts = 0
  _updating_desc = False

  def refresh_desc_if_needed(self, room_id, force=False):
    now = int(time.time())
    if not force and (self._updating_desc or now - self._desc_refresh_ts < 15):
      return False
    self._updating_desc = True
    self._desc_refresh_ts = now
    try:
      model_id = str(self.stripchat_play.rsplit(' ', 1)[-1])
      content_data = self.detailContent([model_id]).get('list')[0]
      payload = {'json': json.dumps(content_data, ensure_ascii=False)}
      ok = False
      for base in [self.base_url] if self.base_url else ['http://127.0.0.1:9978']:
        try:
          r = self.fetch(base + '/action?do=refresh&type=vod', timeout=1)
          r2 = self.post(base + '/action?do=refresh&type=vod', data=payload)
          ok = True
        except Exception:
          continue
      self.log(f'简介弹幕刷新: {ok}')
      return ok
    except Exception as e:
      self.log(f'简介刷新失败: {e}')
      return False
    finally:
      self._updating_desc = False

  def replace_emoji(self, text: str) -> str:
    emoji_map = {
        ':heart:': '❤️',
        ':dancing:': '💃',
        ':thumbsup:': '👍',
        ':flower:': '🌹',
        ':lol:': '😄',
        ':flirt:': '😉',
        ':devil:': '😈',
        ':hideeyes:': '🙈',
        ':ask:': '❓',
        ':inlove:': '😍',
        ':tongue:': '😛',
        ':cry:': '😭',
        ':fire:': '🔥',
        ':asking:': '🤔',
        ':wink:': '😉',
        ':ok:': '👌',
        ':shy:': '😳',
        ':angry:': '😡',
        ':facepalm:': '🤦‍♂️',
        ':ass:': '🍑',
    }
    for code, emoji_char in emoji_map.items():
      text = text.replace(code, emoji_char)
    return text

  def normalize_chat_message(self, msg):
    try:
      if not isinstance(msg, dict):
        return None
      details = msg.get('details') or {}
      text = (
          msg.get('text')
          or msg.get('message')
          or msg.get('content')
          or msg.get('body')
          or ''
      )
      if not text and isinstance(details, dict):
        text = (
            details.get('body')
            or details.get('message')
            or details.get('text')
            or ''
        )
      if isinstance(text, dict):
        text = text.get('text') or text.get('body') or ''
      tp = msg.get('type') or ''
      if not text and tp == 'tip':
        amount = (
            details.get('amount') or details.get('tokens') or ''
            if isinstance(details, dict)
            else ''
        )
        text = f'打赏 {amount} tk' if amount else '打赏'
      if not text and tp == 'lovense':
        text = 'Lovense互动'
      if not text and tp == 'goal':
        text = '🎯 目标更新'
      ud = msg.get('userData') or msg.get('user') or msg.get('sender') or {}
      user = ''
      if isinstance(ud, dict):
        user = ud.get('username') or ud.get('name') or ud.get('login') or ''
      elif isinstance(ud, str):
        user = ud
      if not user:
        user = msg.get('username') or msg.get('userName') or ''
      text, user = str(text).strip(), str(user).strip()
      if not text:
        return None
      return {
          'time': msg.get('createdAt'),
          'user': user[:32],
          'text': self.replace_emoji(text)[:120],
      }
    except Exception as e:
      self.log(f'弹幕解析失败: {e}')
      return None

  def send_live_danmaku(self, item):
    try:
      text = str(item.get('text', '')).strip()
      user = str(item.get('user', '')).strip()
      show = (f'{user}: {text}' if user else text)[:80]
      ok = self.call_local_action(
          f'do=danmaku&text={quote(show)}', f'实时弹幕发送: {show}'
      )
      if not ok:
        self.log('实时弹幕 action 未确认')
    except Exception as e:
      self.log(f'实时弹幕发送失败: {e}')

  def get_danmaku_desc(self, room_id):
    cache = self.danmu_cache.get(str(room_id), {})
    cacheMsg = cache.get('msg', [])

    msg = []
    for item in cacheMsg:
      t = self.datetime_utc8(item.get('time'), '%H:%M') or '--:--'
      text = str(item.get('text', '')).strip()
      user = str(item.get('user', '')).strip()
      show = f'{t} {user}: {text}' if user else f'{t} {text}'
      msg.append(show)

    return '\n'.join(msg)

  def get_action_bases(self):
    bases = []
    try:
      p = urlparse(self.getProxyUrl())
      if p.scheme and p.netloc:
        bases.append(f'{p.scheme}://{p.netloc}')
    except Exception:
      pass
    for b in ['http://127.0.0.1:9978', 'http://127.0.0.1:9979']:
      if b not in bases:
        bases.append(b)
    return bases

  base_url = ''

  def call_local_action(self, query, log_name):
    for base in [self.base_url] if self.base_url else self.get_action_bases():
      try:
        url = f'{base}/action?{query}'
        r = self.fetch(url, timeout=1)
        if r.text.strip() == 'OK':
          self.base_url = base
          self.log(log_name)
          return True
      except:
        continue
    self.log(f'失败: {log_name}')
    return False
