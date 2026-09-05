# -*- coding: utf-8 -*-
import datetime, html, json, re, struct, time, zlib, requests
from base.spider import Spider as BaseSpider
from bs4 import BeautifulSoup

SITES, TAG, UA = ['https://www.cd-zj.com', 'https://maihaolian.com', "https://zzztool.com"], "枫叶4K", "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 Chrome/150.0.0.0 Mobile"
SITE = SITES[0]
HDRS = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "zh-CN,zh;q=0.9", "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Site": "none", "Upgrade-Insecure-Requests": "1", "Referer": SITE + "/"}

try:
    BeautifulSoup("<p></p>", 'lxml'); BS_PARSER = 'lxml'
except Exception: BS_PARSER = 'html.parser'

RE_PLAYER_AAAA, RE_URL_VAR = re.compile(r'var\s+player_aaaa[\s\S]*?"url"\s*:\s*"([^"]+)"'), re.compile(r'url\s*[:=]\s*["\'](http[^"\']+)["\']')
RE_TOKEN, RE_PAGE_NEXT = re.compile(r'data-te="([^"]+)"'), re.compile(r'\d+')
RE_PAGE_TIP, RE_LINE_KEY, RE_WHITESPACE = re.compile(r'\d+/(\d+)页'), re.compile(r'[-_]'), re.compile(r'\s+')

TPL = {0: ["...##.....####...##..##.##....####....####....####....##.##..##...####.....##..."], 1: ["...###....####..######.....###.....###.....###.....###.....###.....###..########"], 2: ["..####...##..##.##....##......##.....##.....##.....##.....##.....##.....##.....########"], 3: ["..####...##..##.##....##....###......###.......##...##..##.##...####...##..##..."], 4: [".....##.....###....####...##.##..##..##.##...##.########.....##......##......##."], 5: ["..####...##..##.##----####....##.##..###..###.##......##.#....##.##..##...####.."], 6: [".#####..##...##.......##.....##....###.......##.......##......####...##..#####.."], 7: ["########......##......##.....##.....##.....##.....##.....##.....##......##......"], 8: ["..####...##..##.##....##.##..##...####...##..##.##....####....##.##..##...####.."], 9: ["#######.##......##......##.###..###..##.......##......####....##.##..##...####.."]}
PARSE_MAP = {'JD': "https://fgsrg.hzqingshan.com", 'co': "https://zzrs.mfdyvip.com", 'knmb': "https://zzrs.mfdyvip.com", 'YYNB': "https://zzrs.mfdyvip.com"}

def _decode_png(data):
    if data[:8] != b'\x89PNG\r\n\x1a\n': raise ValueError('not png')
    pos, width, height, idat = 8, None, None, b''
    while pos < len(data):
        ln, typ, chunk = struct.unpack('>I', data[pos:pos+4])[0], data[pos+4:pos+8], data[pos+8:pos+8+struct.unpack('>I', data[pos:pos+4])[0]]
        pos += 12 + ln
        if typ == b'IHDR': width, height, bit_depth, color_type = struct.unpack('>IIBB', chunk[:10])
        elif typ == b'IDAT': idat += chunk
        elif typ == b'IEND': break
    if color_type not in (0, 2, 3, 4, 6): raise ValueError('color type')
    channels, stride, raw = {0:1, 2:3, 3:1, 4:2, 6:4}[color_type], width * {0:1, 2:3, 3:1, 4:2, 6:4}[color_type], zlib.decompress(idat)
    prev, gray, p = bytearray(stride), [], 0
    for y in range(height):
        ft, line, p = raw[p], bytearray(raw[p+1:p+1+stride]), p + 1 + stride
        if ft == 1:
            for i in range(channels, stride): line[i] = (line[i] + line[i-channels]) & 0xff
        elif ft == 2:
            for i in range(stride): line[i] = (line[i] + prev[i]) & 0xff
        elif ft == 3:
            for i in range(stride): line[i] = (line[i] + (((line[i-channels] if i >= channels else 0) + prev[i]) >> 1)) & 0xff
        elif ft == 4:
            for i in range(stride):
                a, b, c = line[i-channels] if i >= channels else 0, prev[i], prev[i-channels] if i >= channels else 0
                pp = a + b - c; pa, pb, pc = abs(pp-a), abs(pp-b), abs(pp-c)
                line[i] = (line[i] + (a if (pa <= pb and pa <= pc) else (b if pb <= pc else c))) & 0xff
        if color_type in (2, 6): step = 3 if color_type == 2 else 4; rows = [int(line[x*step]*0.299 + line[x*step+1]*0.587 + line[x*step+2]*0.114) for x in range(width)]
        elif color_type == 4: rows = [line[x*2] for x in range(width)]
        else: rows = list(line[:width])
        gray.append(rows); prev = line
    return width, height, gray

def _recognize_captcha(data):
    try: W, H, gray = _decode_png(data)
    except Exception: return None
    avg_gray = sum(sum(r) for r in gray) / (W * H) if W * H else 128
    threshold = min(max(avg_gray * 0.8, 80), 170)
    bw = [[1 if gray[y][x] < threshold else 0 for x in range(W)] for y in range(H)]
    col_sums = [sum(bw[y][x] for y in range(H)) for x in range(W)]
    segs, inseg, start = [], False, 0
    for x in range(W):
        if col_sums[x] > 0 and not inseg: start, inseg = x, True
        elif col_sums[x] == 0 and inseg:
            if x - start >= 3: segs.append((start, x-1))
            inseg = False
    if inseg and (W - start >= 3): segs.append((start, W-1))
    if len(segs) != 4:
        valid_cols = [i for i, cs in enumerate(col_sums) if cs > 0]
        if valid_cols:
            step = (valid_cols[-1] - valid_cols[0] + 1) / 4.0
            segs = [(int(valid_cols[0] + i * step), int(valid_cols[0] + (i + 1) * step)) for i in range(4)]
        else: return None
    result = ''
    for s, e in segs:
        char_cols = range(max(0, s), min(W, e+1))
        rows = [y for y in range(H) if any(bw[y][x] for x in char_cols)]
        if not rows: return None
        ch = [bw[y][max(0, s):min(W, e+1)] for y in range(rows[0], rows[-1]+1)]
        h, w = len(ch), len(ch[0])
        if h == 0 or w == 0: return None
        flat = ''.join('#' if ch[min(h-1, int(ty*h/10))][min(w-1, int(tx*w/8))] else '.' for ty in range(10) for tx in range(8))
        best_d, best_score = None, 10**9
        for d, variants in TPL.items():
            for v in variants:
                score = sum(1 for i in range(80) if flat[i] != v[i])
                if score < best_score: best_score, best_d = score, d
        if best_score > 28: return None
        result += str(best_d)
    return result

def _make_options(arr): return [{"n": "全部", "v": ""}] + [{"n": str(x), "v": str(x)} for x in arr]
def _get_year_filter(): return {"key": "year", "name": "年份", "value": _make_options(list(range(datetime.datetime.now().year, datetime.datetime.now().year - 23, -1)))}
def _get_letter_filter(): return {"key": "letter", "name": "字母", "value": _make_options([chr(65 + i) for i in range(26)] + ["0-9"])}
def _get_order_by_filter(): return {"key": "orderby", "name": "默认排序", "value": [{"n": "默认排序", "v": ""}, {"n": "人气", "v": "hits"}, {"n": "时间", "v": "time"}, {"n": "评分", "v": "score"}]}

_OTHER_FILTERS = [{"key": "area", "name": "地区", "value": _make_options(["大陆", "香港", "台湾", "美国", "韩国", "日本", "泰国", "新加坡", "马来西亚", "印度", "英国", "法国", "加拿大", "西班牙", "俄罗斯", "其它"])}, _get_year_filter(), {"key": "lang", "name": "语言", "value": _make_options(["国语", "英语", "粤语", "闽南语", "韩语", "日语", "其它"])}, _get_letter_filter(), _get_order_by_filter()]
MY_FILTERS = {
    "1": [{"key": "type", "name": "类型", "value": [{"n": "全部", "v": "1"}, {"n": "动作片", "v": "6"}, {"n": "喜剧片", "v": "7"}, {"n": "恐怖片", "v": "8"}, {"n": "科幻片", "v": "9"}, {"n": "爱情片", "v": "10"}, {"n": "剧情片", "v": "11"}]}, {"key": "class", "name": "剧情", "value": _make_options(["喜剧", "爱情", "恐怖", "动作", "科幻", "剧情", "战争", "警匪", "犯罪", "动画", "奇幻", "武侠", "冒险", "枪战", "悬疑", "惊悚", "经典", "青春", "文艺", "微电影", "古装", "历史", "运动", "农村", "儿童", "网络电影"])}] + _OTHER_FILTERS,
    "2": [{"key": "type", "name": "类型", "value": [{"n": "全部", "v": "2"}, {"n": "国产剧", "v": "13"}, {"n": "日韩剧", "v": "15"}, {"n": "海外剧", "v": "16"}]}, {"key": "class", "name": "剧情", "value": _make_options(["古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作", "奇幻", "剧情", "历史", "经典", "乡村", "情景", "商战", "网剧", "其他"])}] + _OTHER_FILTERS,
    "3": [{"key": "type", "name": "类型", "value": [{"n": "全部", "v": "3"}, {"n": "大陆综艺", "v": "21"}, {"n": "日韩综艺", "v": "22"}]}, {"key": "class", "name": "剧情", "value": _make_options(["选秀", "情感", "访谈", "播报", "旅游", "音乐", "美食", "纪实", "曲艺", "生活", "游戏互动", "财经", "求职"])}] + _OTHER_FILTERS,
    "4": [{"key": "type", "name": "类型", "value": [{"n": "全部", "v": "4"}, {"n": "国产动漫", "v": "25"}, {"n": "日韩动漫", "v": "26"}]}, {"key": "class", "name": "剧情", "value": _make_options(["情感", "科幻", "热血", "推理", "搞笑", "冒险", "萝莉", "校园", "动作", "机战", "运动", "战争", "少年", "少女", "社会", "原创", "亲子", "益智", "励志", "其他"])}] + _OTHER_FILTERS,
    "5": [_get_year_filter(), _get_letter_filter()]
}

class Spider(BaseSpider):
    def getName(self): return "枫叶4K影院"

    def init(self, extend=""):
        global SITE, SITES, HDRS
        self.log("[init] 初始化开始"); self.sess = requests.Session(); self.sess.headers.update(HDRS)
        if isinstance(extend, str) and extend:
            try:
                ext_dict = json.loads(extend)
                if isinstance(ext_dict, dict) and ext_dict.get('sites'):
                    SITES, idx = ext_dict['sites'], int(ext_dict.get('sitesIndex', 0))
                    SITE = SITES[idx if 0 <= idx < len(SITES) else 0]; HDRS["Referer"] = SITE + "/"
            except Exception: pass
        cached_cookie = self.getCache("cd_zj_cookie")
        if cached_cookie:
            for item in str(cached_cookie).split(";"):
                if "=" in item:
                    k, v = item.strip().split("=", 1)
                    if k.strip() and v.strip(): self.sess.cookies.set(k.strip(), v.strip())
        try:
            r = self.sess.get(SITE + "/", headers=HDRS, timeout=20); r.encoding = 'utf-8'
            if "系统安全验证" in r.text: self._auto_verify()
        except Exception as e: self.log(f"[init] 初始化请求异常: {e}")

    def _check_and_refresh(self, resp_text): return self._auto_verify() if "系统安全验证" in resp_text else False

    def _verify_once(self):
        try:
            cap = self.sess.get(SITE + "/captcha.php?type=code&r=0.12345", headers={"User-Agent": UA, "Referer": SITE + "/"}, timeout=20).content
            code = _recognize_captcha(cap)
            if not code: return False
            resp = self.sess.post(SITE + "/captcha.php?type=verify", data={"check": code}, headers={"User-Agent": UA, "Referer": SITE + "/", "Content-Type": "application/x-www-form-urlencoded"}, timeout=20)
            resp.encoding = 'utf-8'
            try: return resp.json().get("code") == 1
            except Exception: return '"code":1' in resp.text
        except Exception: return False

    def _auto_verify(self):
        for _ in range(3):
            if self._verify_once():
                time.sleep(1)
                try:
                    r2 = self.sess.get(SITE + "/", headers=HDRS, timeout=20); r2.encoding = 'utf-8'
                    if "系统安全验证" not in r2.text:
                        mac_v, ver_s = self.sess.cookies.get("mac_verify", ""), self.sess.cookies.get("verify_success", "1")
                        if mac_v: self.setCache("cd_zj_cookie", f"mac_verify={mac_v};verify_success={ver_s};")
                        return True
                except Exception: return True
            time.sleep(1.5)
        return False

    def homeContent(self, filter):
        return {"class": [{"type_id": "4", "type_name": "动漫"}, {"type_id": "/label/qq", "type_name": "腾讯精选"}, {"type_id": "/label/bli", "type_name": "B站精选"}, {"type_id": "/label/youku", "type_name": "优酷精选"}, {"type_id": "2", "type_name": "电视剧"}, {"type_id": "1", "type_name": "电影"}, {"type_id": "3", "type_name": "综艺"}, {"type_id": "5", "type_name": "热门短剧"}], "filters": MY_FILTERS}

    def homeVideoContent(self): return self.categoryContent("", 1, False, {})

    def categoryContent(self, tid, pg, filter, extend):
        self.log(f"[categoryContent] tid: {tid}, pg: {pg}, extend: {extend}")
        page = int(pg) if str(pg).isdigit() else 1
        if not isinstance(extend, dict): extend = {}
        is_label = tid.startswith("/label")
        target_type = extend.get("type") if extend.get("type") is not None else tid
        type_prefix = "cupfox-list" if ("www.cd-zj.com" in SITE or "maihaolian.com" in SITE) else "list"
        area, orderby, clazz, lang, letter, year = extend.get("area", ""), extend.get("orderby", "hits"), extend.get("class", ""), extend.get("lang", ""), extend.get("letter", ""), extend.get("year", "")
        url = f"{SITE}{tid}/page/{page}.html" if is_label else (SITE if target_type == "" else f"{SITE}/{type_prefix}/{target_type}-{area}-{orderby}-{clazz}-{lang}-{letter}---{page}---{year}.html")

        try:
            r = self.sess.get(url, headers=HDRS, timeout=20); r.encoding = 'utf-8'
            if self._check_and_refresh(r.text): r = self.sess.get(url, headers=HDRS, timeout=20); r.encoding = 'utf-8'
            if "系统安全验证" not in r.text:
                vods, totalpg = self._parseListHtml(r.text, 'zzz' in SITE, is_label, False)
                return {"list": vods, "page": page, "pagecount": totalpg, "limit": 30, "total": totalpg * 30}
        except Exception as e: self.log(f"[categoryContent] 异常: {e}")
        return {"list": [], "page": page, "pagecount": 1}

    def _parseListHtml(self, html_content, is_zzz, is_label=False, is_search=False):
        if "系统安全验证" in html_content: self.log("需要验证，请重新获取ck"); raise Exception('需要验证，请重新获取ck')
        soup, vods = BeautifulSoup(html_content, BS_PARSER), []
        for el in soup.select(".module-item" if is_zzz else ".public-list-bj"):
            if is_zzz:
                poster = el.select_one('.module-card-item-poster') if (is_label or is_search) else None
                vod_id = poster.get("href") if poster else el.get("href", "")
                title_tag = el.select_one('.module-card-item-title strong') if is_label else None
                vod_name = title_tag.get_text(strip=True) if title_tag else el.get("title", "")
                pic_tag, note_tag = el.select_one(".module-item-pic img"), el.select_one(".module-item-note")
                vod_pic = pic_tag.get("data-src") or pic_tag.get("src") if pic_tag else ""
                vod_remarks = note_tag.get_text(strip=True) if note_tag else ""
                v_left, v_right = el.select_one('.module-item-version-left'), el.select_one('.module-item-version-right')
                text4k, update_time = v_left.get_text(strip=True) if v_left else "", v_right.get_text(strip=True) if v_right else ""
            else:
                exp_tag = el.select_one("a.public-list-exp")
                vod_id, vod_name = exp_tag.get("href") if exp_tag else "", exp_tag.get("title") if exp_tag else ""
                if not vod_name:
                    thumb = soup.select_one(".thumb-content a"); vod_name = thumb.get_text(strip=True) if thumb else ""
                pic_tag, ft2_tag = el.select_one(".public-list-exp img"), el.select_one(".ft2")
                vod_pic = pic_tag.get("data-src") or pic_tag.get("src") if pic_tag else ""
                vod_remarks = ft2_tag.get_text(strip=True) if ft2_tag else ""
                prt_g, prt_all = el.select_one('.public-list-exp .public-prt-g'), el.select('.public-list-exp .public-prt')
                text4k, update_time = prt_g.get_text(strip=True) if prt_g else "", prt_all[1].get_text(strip=True) if len(prt_all) > 1 else ""

            if vod_id: vods.append({"vod_id": vod_id, "vod_name": (vod_name or "").strip(), "vod_pic": html.unescape(vod_pic) if vod_pic else "", "vod_remarks": vod_remarks, "vod_year": f"{f'「{text4k}」' if text4k else ''} {update_time}".strip()})

        pagecount = 1
        if is_zzz:
            page_next = soup.select('.module-footer .page-next')
            if page_next and (m := RE_PAGE_NEXT.search(page_next[-1].get('href', ''))): pagecount = int(m.group(0))
        else:
            page_tip = soup.select_one('.page-tip')
            if page_tip and (m := RE_PAGE_TIP.search(page_tip.get_text())): pagecount = int(m.group(1))
        return vods, pagecount

    def _buildVodPlayData(self, lines, playlists, should_reverse=True):
        return {
            "vod_play_from": "$$$".join(filter(None, [f"{line}({len(eps)})" for line, eps in zip(lines, playlists)])),
            "vod_play_url": "$$$".join(["#".join(reversed(eps) if should_reverse else eps) for eps in playlists])
        }

    def _extractPlayInfo(self, soup, tab_sel, label_sel, panel_sel, item_sel):
        lines, playlists, name_counts = [], [], {}
        for tab in soup.select(tab_sel):
            lbl = tab.select_one(label_sel); raw_name = lbl.get_text(strip=True) if lbl else "线路"
            if raw_name:
                name_counts[raw_name] = name_counts.get(raw_name, 0) + 1
                lines.append(f"{raw_name}-{name_counts[raw_name]}" if name_counts[raw_name] > 1 else raw_name)
        for panel in soup.select(panel_sel):
            playlists.append([f"{a_el.get_text(strip=True)}${a_el.get('href', '')}" for a_el in panel.select(item_sel) if a_el.get_text(strip=True) and a_el.get('href')])
        return self._buildVodPlayData(lines, playlists, True)

    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, (list, tuple)) else ids)
        url = vid if vid.startswith("http") else SITE + (vid if vid.startswith("/") else "/" + vid)
        try:
            r = self.sess.get(url, headers=HDRS, timeout=20); r.encoding = 'utf-8'
            if self._check_and_refresh(r.text): r = self.sess.get(url, headers=HDRS, timeout=20); r.encoding = 'utf-8'
            soup = BeautifulSoup(r.text, BS_PARSER)
            if 'zzztool' in url or 'zzz' in SITE:
                director, actor, remarks = '', '', ''
                for item in soup.select('.module-info-item'):
                    title, content = (item.select_one('.module-info-item-title').get_text(strip=True) if item.select_one('.module-info-item-title') else ""), (item.select_one('.module-info-item-content').get_text(strip=True) if item.select_one('.module-info-item-content') else "")
                    if '导演' in title: director = content
                    elif '主演' in title: actor = content
                    elif ('集数' in title or '更新' in title or '状态' in title) and not remarks: remarks = content
                name, pic_tag, ver_right, intro = soup.select_one('.module-info-heading h1'), soup.select_one(".module-item-pic img"), soup.select_one('.module-item-version-right'), soup.select_one('.module-info-introduction-content p')
                play_info = self._extractPlayInfo(soup, '.mx-anthology-tab', '.mx-anthology-tab-label', '.mx-anthology-panel', '.mx-anthology-item a')
                return {"list": [{"vod_id": vid, "vod_name": name.get_text(strip=True) if name else "未知标题", "vod_pic": html.unescape(pic_tag.get("data-src") or pic_tag.get("src")) if pic_tag else "", "vod_remarks": remarks, "vod_play_from": play_info["vod_play_from"], "vod_play_url": play_info["vod_play_url"], "vod_year": (ver_right.get_text(strip=True) if ver_right else "") or remarks, "vod_director": director, "vod_actor": actor, "vod_content": intro.get_text(strip=True) if intro else ""}]}
            else:
                title_el, pic_el, content_el = soup.select_one('.slide-info-title'), soup.select_one('.detail-pic img'), soup.select_one('#height_limit')
                vod_actor, vod_remarks = "", ""
                for info in soup.select('.detail-info .slide-info'):
                    info_text = info.get_text()
                    if '演员' in info_text or '连载' in info_text:
                        for s in info.find_all('strong'): s.decompose()
                        clean_text = RE_WHITESPACE.sub('', info.get_text()).strip()
                        if '演员' in info_text: vod_actor = clean_text
                        else: vod_remarks = clean_text
                lines, playlists, name_counts = [], [], {}
                for slide in soup.select('.swiper-slide'):
                    for tag in slide.find_all(['i', 'span']): tag.decompose()
                    raw_name = slide.get_text(strip=True)
                    if raw_name:
                        name_counts[raw_name] = name_counts.get(raw_name, 0) + 1
                        lines.append(f"{raw_name}-{name_counts[raw_name]}" if name_counts[raw_name] > 1 else raw_name)
                for pool in soup.select('.anthology-list-box'):
                    playlists.append([f"{ep.get_text(strip=True)}${ep.get('href', '')}" for ep in pool.find_all('a') if ep.get_text(strip=True) and ep.get('href')])
                play_info = self._buildVodPlayData(lines, playlists, True)
                return {"list": [{"vod_id": vid, "vod_name": title_el.get_text(strip=True) if title_el else "未知标题", "vod_pic": html.unescape(pic_el.get("data-src") or pic_el.get("src")) if pic_el else "", "vod_actor": vod_actor, "vod_remarks": vod_remarks, "vod_content": content_el.get_text(strip=True) if content_el else "", "vod_play_from": play_info["vod_play_from"], "vod_play_url": play_info["vod_play_url"]}]}
        except Exception as e: self.log(f"[detailContent] 异常: {e}"); return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        if int(pg) >= 2: return {"list": [], "pagecount": 1}
        try:
            r = self.sess.get(f"{SITE}/{'search' if 'zzz' in SITE else 'cupfox-search'}/-------------.html?wd={requests.utils.quote(key)}", headers=HDRS, timeout=20); r.encoding = 'utf-8'
            if self._check_and_refresh(r.text): r = self.sess.get(f"{SITE}/{'search' if 'zzz' in SITE else 'cupfox-search'}/-------------.html?wd={requests.utils.quote(key)}", headers=HDRS, timeout=20); r.encoding = 'utf-8'
            vods, pagecount = self._parseListHtml(r.text, 'zzz' in SITE, False, True)
            return {"list": vods, "pagecount": pagecount}
        except Exception as e: self.log(f"[searchContent] 异常: {e}"); return {"list": [], "pagecount": 1}

    def _parsePlayUrl(self, url):
        try:
            line_key = RE_LINE_KEY.split(url)[0] if url else ""
            parse_api_url = PARSE_MAP.get(line_key)
            if not parse_api_url: return ""
            target_url = f"{parse_api_url}/player/?url={url}"
            res = self.sess.get(target_url, headers=HDRS, timeout=20); res.encoding = 'utf-8'
            if not res.text: return ""
            soup = BeautifulSoup(res.text, BS_PARSER)
            player_data = soup.select_one('#player-data')
            token = player_data.get('data-te') if player_data else None
            if not token and (token_m := RE_TOKEN.search(res.text)): token = token_m.group(1)
            if not token: return ""
            post_resp = self.sess.post(f"{parse_api_url}/player/mplayer.php", data={"url": url, "token": token}, headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "User-Agent": UA, "Referer": target_url}, timeout=20)
            post_resp.encoding = 'utf-8'
            if not post_resp.text: return ""
            parse_play_url = post_resp.json().get("url", "")
            return (parse_api_url + parse_play_url) if parse_play_url.startswith('/playproxy.php') else parse_play_url
        except Exception as e: self.log(f"[_parsePlayUrl] 错误: {e}"); return ""

    def playerContent(self, flag, id, vipFlags):
        play_url = id if id.startswith("http") else SITE + (id if id.startswith("/") else "/" + id)
        try:
            r = self.sess.get(play_url, headers=HDRS, timeout=20); r.encoding = 'utf-8'
            if self._check_and_refresh(r.text): r = self.sess.get(play_url, headers=HDRS, timeout=20); r.encoding = 'utf-8'
            t = r.text
            match = RE_PLAYER_AAAA.search(t)
            url = match.group(1).replace('\\/', '/') if match else ""
            if not url and (var_m := RE_URL_VAR.search(t)): url = var_m.group(1)
            if not url: url = play_url
            if url.startswith('http') and ("m3u" in url or ".mp4" in url): return {"parse": 0, "url": url, "header": f"User-Agent: {UA}\r\nReferer: {SITE}/"}
            real_url = self._parsePlayUrl(url) or url
            return {"parse": 0 if ("m3u" in real_url or ".mp4" in real_url) else 1, "url": real_url, "header": f"User-Agent: {UA}\r\nReferer: {SITE}/"}
        except Exception as e: self.log(f"[playerContent] 异常: {e}"); return {"parse": 0, "msg": str(e)}