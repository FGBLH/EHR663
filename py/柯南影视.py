# -*- coding: utf-8 -*-
"""
兼容 FongMi/TV (T3) 和 WebHomeTV/PeekPro (T4) 的 Python Spider
站点: https://www.knvod.com
"""
import sys
import re
import json
import time
import base64
import urllib.parse

sys.path.append('..')

# ===== 兼容导入 =====
try:
    from base.spider import Spider
except ImportError:
    import requests as rq

    class Spider:
        def fetch(self, url, headers=None, **kw):
            kw.pop('timeout', None)
            r = rq.get(url, headers=headers, timeout=15, **kw)
            r.encoding = 'utf-8'
            return r


class Spider(Spider):

    def getName(self):
        return "柯南影视"

    def init(self, extend=""):
        # T3: extend 是字符串; T4: 可能传模块列表
        if isinstance(extend, list):
            self.extend = ''
        else:
            self.extend = extend or ''
        self.host = "https://www.knvod.com"
        self.header = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36',
            'Referer': self.host + '/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        }

    # ========== 网络工具 ==========
    def _txt(self, url, referer=None, timeout=30):
        """安全请求，返回文本，失败返回空字符串"""
        headers = dict(self.header)
        if referer:
            headers['Referer'] = referer
        try:
            rsp = self.fetch(url, headers=headers, timeout=timeout)
            try:
                rsp.encoding = 'utf-8'
            except Exception:
                pass
            if hasattr(rsp, 'status_code') and rsp.status_code == 520:
                for i in range(2):
                    rsp = self.fetch(url, headers=headers, timeout=timeout)
                    if hasattr(rsp, 'status_code') and rsp.status_code == 200:
                        break
            return rsp.text
        except Exception:
            return ''

    def _fixPic(self, pic):
        if not pic:
            return pic
        if pic.startswith('//'):
            pic = 'https:' + pic
        elif pic.startswith('/'):
            pic = self.host + pic
        elif pic.startswith('http://'):
            pic = pic.replace('http://', 'https://', 1)
        return pic

    def _match(self, pattern, text, default=''):
        m = re.search(pattern, text, re.S)
        return m.group(1).strip() if m else default

    # ========== 列表解析 ==========
    def _parseList(self, text):
        """
        统一解析列表页，兼容两种卡片结构:
        1. 分类页: <div class="public-list-div public-list-bj">  + <img data-src="...">
        2. 搜索页: <div class="cover" style="...url(IMG)">       + <a class="public-list-exp" href="/vdetail/ID.html">
        策略: 找所有 public-list-exp 链接，向前找图片
        """
        videos = []
        seen = set()

        # 找所有 vdetail 链接 (在 public-list-exp 的 a 标签中)
        exp_matches = list(re.finditer(
            r'<a[^>]*class="[^"]*public-list-exp[^"]*"[^>]*href="/vdetail/(\d+)\.html"[^>]*>(.*?)</a>',
            text, re.S
        ))

        for m in exp_matches:
            vid = m.group(1)
            if vid in seen:
                continue
            seen.add(vid)

            # 从链接向前找图片
            before = text[max(0, m.start() - 600):m.start()]

            # 方式1: 分类页的 data-src
            pic = ''
            ds_m = re.search(r'data-src="([^"]+)"', before)
            if ds_m:
                pic = self._fixPic(ds_m.group(1))

            # 方式2: 搜索页的 url() 背景图
            if not pic:
                url_m = re.search(r'url\(([^)]+)\)', before)
                if url_m:
                    pic = self._fixPic(url_m.group(1))

            # 方式3: 从 a 标签内部找 data-src
            if not pic:
                inner = m.group(2)
                ds2 = re.search(r'data-src="([^"]+)"', inner)
                if ds2:
                    pic = self._fixPic(ds2.group(1))

            # 名称: 先从 a 标签的 title 属性
            name = ''
            title_m = re.search(r'title="([^"]+)"', m.group(0))
            if title_m:
                name = title_m.group(1).strip()
            # 再从 img 的 alt 属性
            if not name:
                alt_m = re.search(r'alt="([^"]+)"', m.group(2))
                if alt_m:
                    name = alt_m.group(1).strip().replace('封面图', '')

            # 备注: 从后面找 public-list-prb
            after = text[m.end():m.end() + 600]
            r_m = re.search(r'public-list-prb[^>]*>([^<]+)', after)
            remark = r_m.group(1).strip() if r_m else ''

            videos.append({
                'vod_id': vid,
                'vod_name': name,
                'vod_pic': pic,
                'vod_remarks': remark,
            })

        # 兜底: 如果上面的正则没匹配到，尝试更宽松的方式
        if not videos:
            cards = re.findall(r'href="/vdetail/(\d+)\.html"', text)
            seen2 = set()
            for vid in cards:
                if vid in seen2:
                    continue
                seen2.add(vid)
                # 找这个 vid 对应的上下文
                pos = text.find('/vdetail/{}.html'.format(vid))
                context = text[max(0, pos - 400):pos + 400]
                # url()
                pic = ''
                url_m = re.search(r'url\(([^)]+)\)', context)
                if url_m:
                    pic = self._fixPic(url_m.group(1))
                # data-src
                if not pic:
                    ds_m = re.search(r'data-src="([^"]+)"', context)
                    if ds_m:
                        pic = self._fixPic(ds_m.group(1))
                # name
                name = ''
                alt_m = re.search(r'alt="([^"]+)"', context)
                if alt_m:
                    name = alt_m.group(1).strip().replace('封面图', '')
                title_m = re.search(r'title="([^"]+)"', context)
                if title_m:
                    name = title_m.group(1).strip()
                videos.append({
                    'vod_id': vid,
                    'vod_name': name,
                    'vod_pic': pic,
                    'vod_remarks': '',
                })

        return videos

    # ========== 首页 ==========
    def homeContent(self, filter):
        result = {}
        classes = [
            {'type_id': '1', 'type_name': '电影'},
            {'type_id': '2', 'type_name': '电视剧'},
            {'type_id': '3', 'type_name': '动漫'},
            {'type_id': '4', 'type_name': '综艺'},
        ]
        result['class'] = classes

        videos = []
        seen = set()
        for tid in ['1', '2', '3', '4']:
            html = self._txt(self.host + '/vshow/{}-----------.html'.format(tid))
            if html:
                for v in self._parseList(html):
                    if v['vod_id'] not in seen:
                        seen.add(v['vod_id'])
                        videos.append(v)
            if len(videos) >= 72:
                break
        result['list'] = videos
        return result

    def homeVideoContent(self):
        return {"list": []}

    # ========== 分类列表 ==========
    def categoryContent(self, tid, pg, filter, extend):
        url = self.host + '/vshow/{}--------{}---.html'.format(tid, pg)
        html = self._txt(url)
        videos = []
        if html:
            videos = self._parseList(html)
        return {
            "list": videos,
            "page": pg,
            "pagecount": 9999,
            "limit": len(videos),
            "total": 999999,
        }

    # ========== 详情页 ==========
    def detailContent(self, ids):
        # 兼容 list 和 str
        if isinstance(ids, str):
            ids = [ids]
        vod_id = ids[0]

        url = self.host + '/vdetail/{}.html'.format(vod_id)
        html = self._txt(url)
        if not html:
            return {"list": []}

        # 剧名
        title = self._match(r'<h3[^>]*>(.*?)</h3>', html)
        if title:
            title = re.sub(r'<[^>]+>', '', title).strip()

        # 封面: 优先 detail-pic 区域的 data-src，跳过广告/logo
        pic = ''
        # 方式1: detail-pic 区域
        dp_m = re.search(r'detail-pic[^>]*>.*?data-src="([^"]+)"', html, re.S)
        if dp_m:
            pic = self._fixPic(dp_m.group(1))
        # 方式2: slide-time-img2 区域
        if not pic:
            st_m = re.search(r'slide-time-img2[^>]*>.*?data-src="([^"]+)"', html, re.S)
            if st_m:
                pic = self._fixPic(st_m.group(1))
        # 方式3: 第一个非广告的 data-src 图片
        if not pic:
            for ds_m in re.finditer(r'data-src="([^"]+)"', html):
                img_url = ds_m.group(1)
                if 'base64' in img_url or 'imgapi' in img_url or 'baidu' in img_url:
                    continue
                if re.search(r'\.(jpg|jpeg|png|webp|gif)', img_url, re.I):
                    pic = self._fixPic(img_url)
                    break

        # 简介
        desc = ''
        m = re.search(r'id="height_limit"[^>]*>(.*?)</div>', html, re.S)
        if m:
            desc = re.sub(r'<[^>]+>', '', m.group(1)).strip().replace('&nbsp;', ' ')

        # 主演
        actor = ''
        m = re.search(r'主演：</em>(.*?)</li>', html, re.S)
        if m:
            actor = ' '.join(re.findall(r'>([^<]+)</a>', m.group(1)))

        # 导演
        director = ''
        m = re.search(r'导演\s*:</strong>(.*?)</div>', html, re.S)
        if m:
            director = ' '.join(re.findall(r'>([^<]+)</a>', m.group(1)))

        # 类型
        type_name = ''
        m = re.search(r'类型：</em>(.*?)</li>', html, re.S)
        if m:
            type_name = ' '.join(re.findall(r'>([^<]+)</a>', m.group(1)))

        # 地区
        area = self._match(r'地区：</em>([^<]+)</li>', html)

        # 年份
        year = self._match(r'年份：</em>([^<]+)</li>', html)

        # ===== 播放线路 =====
        # 线路名: <a class="swiper-slide"><i ...></i>&nbsp;线路名<span class="badge">集数</span></a>
        from_names = re.findall(r'<a class="swiper-slide">.*?&nbsp;([^<]+)<span class="badge">', html)

        # 集数列表: <ul class="anthology-list-play ...">...</ul>
        uls = re.findall(
            r'(<ul[^>]*class="[^"]*anthology-list-play[^"]*"[^>]*>.*?</ul>)',
            html, re.S
        )

        play_from = []
        play_url = []
        name_counts = {}
        # 这些线路依赖外部解析器，对部分资源会出现只有声音无画面、一直转圈或嗅探失败。
        unstable_lines = set(['推荐', '推荐2', '超快③', '超快l', '超快I', '超快Ⅰ'])

        for i, ul in enumerate(uls):
            # 线路名
            name = from_names[i].strip() if i < len(from_names) else '线路{}'.format(i + 1)
            if name in unstable_lines:
                continue
            if name in name_counts:
                name_counts[name] += 1
                name = name + str(name_counts[name])
            else:
                name_counts[name] = 1
            play_from.append(name)

            # 集数链接: <a href="/vplay/ID-SID-NID.html">集名</a>
            items = re.findall(
                r'<a[^>]+href="(/vplay/\d+-\d+-\d+\.html)"[^>]*>([^<]+)</a>',
                ul
            )
            # HTML 中集数是倒序的 (最后一集在前)，需要反转
            items.reverse()

            urls = []
            for href, ep_name in items:
                ep_name = ep_name.strip()
                play_link = self.host + href
                urls.append('{}${}'.format(ep_name, play_link))

            play_url.append('#'.join(urls))

        # 稳定线路前置，避免默认优先点到快线解析器导致转圈或嗅探失败。
        if play_from and play_url:
            pairs = list(zip(play_from, play_url))
            def _line_rank(pair):
                name = pair[0]
                if name.startswith('超稳'):
                    return 0
                if name.startswith('蓝光') or name.startswith('移动'):
                    return 1
                return 2
            pairs.sort(key=_line_rank)
            play_from = [x[0] for x in pairs]
            play_url = [x[1] for x in pairs]

        vod = {
            "vod_id": vod_id,
            "vod_name": title,
            "vod_pic": pic,
            "type_name": type_name,
            "vod_year": year,
            "vod_area": area,
            "vod_remarks": "",
            "vod_actor": actor,
            "vod_director": director,
            "vod_content": desc,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }
        return {"list": [vod]}

    # ========== 搜索 ==========
    def searchContent(self, key, quick, pg="1"):
        url = self.host + '/search/{}-------------.html'.format(urllib.parse.quote(key))
        html = self._txt(url)
        videos = []
        if html:
            videos = self._parseList(html)
        return {"list": videos}

    def searchContentPage(self, key, quick, pg):
        return self.searchContent(key, quick, pg)

    # ========== 播放辅助 ==========
    def _is_direct_media(self, url):
        url = (url or "").lower()
        return ".m3u8" in url or ".mp4" in url or ".flv" in url or ".mkv" in url

    def _is_official_source(self, url):
        url = (url or "").lower()
        keys = (
            "mgtv.com", "youku.com", "iqiyi.com", "qiyi.com",
            "v.qq.com", "qq.com", "bilibili.com", "le.com",
            "sohu.com", "pptv.com", "1905.com",
        )
        return any(k in url for k in keys) and not self._is_direct_media(url)

    def _aes_cbc_decrypt_text(self, cipher_text):
        try:
            from Crypto.Cipher import AES
            key = cipher_text[-32:-16].encode("utf-8")
            iv = cipher_text[-16:].encode("utf-8")
            data = base64.b64decode(cipher_text[:-32])
            raw = AES.new(key, AES.MODE_CBC, iv).decrypt(data)
            pad = raw[-1] if raw else 0
            if 0 < pad <= 16:
                raw = raw[:-pad]
            return raw.decode("utf-8", "ignore")
        except Exception:
            return ""

    def _decode_bfq_result(self, result):
        text = self._aes_cbc_decrypt_text(result or "")
        if not text:
            return {}
        try:
            return json.loads(text)
        except Exception:
            return {}

    def _resolve_official_to_media(self, src_url):
        if not src_url or not self._is_official_source(src_url):
            return ""
        try:
            page_url = "https://bfq.txnp.cn/player?url=" + urllib.parse.quote(src_url, safe="")
            referer = "https://bfq.txnp.cn/excessive?url=" + urllib.parse.quote(src_url, safe="")
            html = self._txt(page_url, referer=referer, timeout=20)
            result = self._match(r'let\s+result\s*=\s*"([^"]+)"', html)
            data = self._decode_bfq_result(result)
            video = ((data.get("video_info") or {}).get("video") or {})
            media = (video.get("url") or "").replace("\\/", "/")
            if media and self._is_direct_media(media):
                if ".m3u8" in media:
                    media = self._resolve_m3u8_child(media, referer=page_url)
                return media
        except Exception:
            pass
        return ""

    def _resolve_m3u8_child(self, m3u8_url, referer=""):
        text = self._txt(m3u8_url, referer=referer or self.host + "/", timeout=20)
        if not text or "#EXTM3U" not in text:
            return m3u8_url
        lines = [x.strip() for x in text.splitlines() if x.strip()]
        for i, line in enumerate(lines):
            if line.startswith("#EXT-X-STREAM-INF"):
                for nxt in lines[i + 1:]:
                    if nxt and not nxt.startswith("#"):
                        return urllib.parse.urljoin(m3u8_url, nxt)
        return m3u8_url

    def _proxy_url(self, media_url, referer=""):
        if not hasattr(self, "getProxyUrl"):
            return media_url
        try:
            base = self.getProxyUrl()
            return base + "&url=" + urllib.parse.quote(media_url, safe="") + "&referer=" + urllib.parse.quote(referer or self.host + "/", safe="")
        except Exception:
            return media_url

    def _build_parse_url(self, play_url, next_link="", title=""):
        """柯南站内 parse.js 实际使用的解析器地址，减少壳子二次嗅探原播放页。"""
        if not play_url:
            return ""
        parse_url = "https://xn--ewr.211997.xyz/ppy.php?url=" + play_url
        if next_link:
            if str(next_link).startswith("//"):
                parse_url += "&next=" + next_link
            elif str(next_link).startswith("http"):
                parse_url += "&next=//" + str(next_link).replace("https://", "").replace("http://", "")
            else:
                parse_url += "&next=//www.knvod.com" + str(next_link)
        if title:
            parse_url += "&title=" + urllib.parse.quote(title)
        return parse_url

    # ========== 播放解析 ==========
    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 1, "playUrl": "", "url": ""}

        url = id if str(id).startswith("http") else self.host + id

        # 1. 官源检测与解析 (文档 8.4)
        if self._is_official_source(url):
            resolved = self._resolve_official_to_media(url)
            if resolved:
                return {
                    "parse": 0,
                    "playUrl": "",
                    "url": resolved,
                    "header": {
                        "User-Agent": self.header["User-Agent"],
                        "Referer": "https://bfq.txnp.cn/",
                    },
                    "format": "application/x-mpegURL" if ".m3u8" in resolved else "",
                    "contentType": "application/x-mpegURL" if ".m3u8" in resolved else "",
                }

        # 2. 直链直接返回
        if self._is_direct_media(url):
            return {
                "parse": 0,
                "playUrl": "",
                "url": url,
                "header": {
                    "Referer": self.host + '/',
                    "User-Agent": self.header['User-Agent'],
                },
                "format": "application/x-mpegURL" if ".m3u8" in url else "",
                "contentType": "application/x-mpegURL" if ".m3u8" in url else "",
            }

        # 3. 尝试解析播放页，看是否有 iframe 或全局 m3u8/mp4
        try:
            html = self._txt(url, referer=self.host + '/', timeout=20)
            if html:
                # iframe 中的媒体地址
                iframes = re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', html, re.S | re.I)
                for ifr in iframes:
                    if self._is_direct_media(ifr):
                        return {
                            "parse": 0,
                            "playUrl": "",
                            "url": ifr,
                            "header": {
                                "Referer": self.host + '/',
                                "User-Agent": self.header['User-Agent'],
                            },
                        }

                # player_aaaa 中的 url
                m = re.search(r'var\s+player_[a-zA-Z0-9_]+\s*=\s*(\{.*?\})\s*</script>', html, re.S)
                if m:
                    pdata = json.loads(m.group(1))
                    purl = pdata.get('url', '')
                    next_link = pdata.get('link_next', '')
                    title = ((pdata.get('vod_data') or {}).get('vod_name') or '')
                    # encrypt=1: unescape; encrypt=2: base64decode+unescape
                    enc = str(pdata.get('encrypt', '0'))
                    if enc == '1':
                        purl = urllib.parse.unquote(purl)
                    elif enc == '2':
                        try:
                            purl = urllib.parse.unquote(base64.b64decode(purl).decode('utf-8', 'ignore'))
                        except Exception:
                            pass
                    if purl and self._is_direct_media(purl):
                        if ".m3u8" in purl:
                            purl = self._resolve_m3u8_child(purl, referer=url)
                        return {
                            "parse": 0,
                            "playUrl": "",
                            "url": purl,
                            "header": {
                                "Referer": self.host + '/',
                                "User-Agent": self.header['User-Agent'],
                            },
                            "format": "application/x-mpegURL" if ".m3u8" in purl else "",
                            "contentType": "application/x-mpegURL" if ".m3u8" in purl else "",
                        }

                    if purl and self._is_official_source(purl):
                        resolved = self._resolve_official_to_media(purl)
                        if resolved:
                            return {
                                "parse": 0,
                                "playUrl": "",
                                "url": resolved,
                                "header": {
                                    "Referer": "https://bfq.txnp.cn/",
                                    "User-Agent": self.header['User-Agent'],
                                },
                                "format": "application/x-mpegURL" if ".m3u8" in resolved else "",
                                "contentType": "application/x-mpegURL" if ".m3u8" in resolved else "",
                            }

                    if purl:
                        parse_url = self._build_parse_url(purl, next_link, title)
                        return {
                            "parse": 1,
                            "playUrl": "",
                            "url": parse_url,
                            "header": {
                                "Referer": "https://xn--ewr.211997.xyz/",
                                "User-Agent": self.header['User-Agent'],
                            },
                        }

                # 全局 m3u8/mp4 匹配
                media_m = re.search(r'["\'](https?://[^"\']+\.(?:m3u8|mp4)[^"\']*)["\']', html, re.I)
                if media_m:
                    media = media_m.group(1)
                    return {
                        "parse": 0,
                        "playUrl": "",
                        "url": media,
                        "header": {
                            "Referer": self.host + '/',
                            "User-Agent": self.header['User-Agent'],
                        },
                    }
        except Exception:
            pass

        # 4. 兜底: 让壳子嗅探
        return {
            "parse": 1,
            "playUrl": "",
            "url": url,
            "header": {
                "Referer": self.host + '/',
                "User-Agent": self.header['User-Agent'],
            },
        }

    # ========== 本地代理 ==========
    def localProxy(self, param):
        try:
            import urllib.parse
            url = param.get("url", "") if isinstance(param, dict) else ""
            if not url:
                url = urllib.parse.parse_qs(param).get("url", [""])[0] if isinstance(param, str) else ""
            if url:
                rsp = self.fetch(url, headers=self.header, timeout=30)
                content = rsp.content if hasattr(rsp, "content") else b""
                ctype = rsp.headers.get("Content-Type", "video/MP2T") if hasattr(rsp, "headers") else "video/MP2T"
                return [200, ctype, content, ""]
        except Exception:
            pass
        return [200, "video/MP2T", b"", ""]

    # ========== 清理 ==========
    def destroy(self):
        pass

    def close(self):
        self.destroy()


if __name__ == '__main__':
    spider = Spider()
    spider.init()
    # print(spider.homeContent(None))
    # print(spider.categoryContent('1', '1', None, None))
    # print(spider.detailContent('168080'))
    # print(spider.playerContent('', 'https://www.knvod.com/vplay/168080-8-25.html', ''))
    # print(spider.searchContent('百花杀', False))
