# -*- coding: utf-8 -*-
import sys, re, json, html as hmod, base64
from urllib.parse import quote, unquote, urljoin, urlparse
sys.path.append('..')
try:
    from base.spider import Spider as _B
except ImportError:
    class _B: pass
try:
    import requests
except ImportError:
    requests = None

U = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
IMG_HOST = "https://4sbase64.dt188.site"

# ==========================================
# 域名自适应配置
# ==========================================
_DOMAIN_CANDIDATES = [
    "https://www.r3e2o.top",
    "https://r3e2o.top",
]
_ENTER_PATH = "/enter.html"

def _discover_domain(candidates=None, timeout=10):
    candidates = candidates or _DOMAIN_CANDIDATES
    session = requests.Session()
    session.headers.update({"User-Agent": U, "Referer": ""})
    for domain in candidates:
        try:
            r = session.get(domain + _ENTER_PATH, timeout=timeout, allow_redirects=True)
            if r.status_code in (200, 301, 302):
                text = r.text
                m = re.search(r'href="(https?://[^"]+)/index/home\.html"', text)
                if m:
                    return m.group(1)
                m = re.search(r'document\.domain\s*[=:]\s*["\']?([^"\';\s]+)', text)
                if m:
                    host = m.group(1)
                    if host.startswith('http'):
                        return host
                    return "https://" + host
                final_url = r.url
                parsed = urlparse(final_url)
                return f"{parsed.scheme}://{parsed.netloc}"
        except Exception as e:
            print(f"[R3]domain check failed {domain}: {e}")
            continue
    return candidates[0] if candidates else "https://www.r3e2o.top"


# ==========================================
# AES-256-CBC 解密核心（key 已修正为 32 字节）
# ==========================================
# 正确的 32 字节 key（参考脚本通过 base64 解码得到）
_AES_KEY = 'IdTJq0HklpuI6mu8iB%OO@!vd^4K&uXW'
_AES_IV  = '$0v@krH7V2883346'

def _py_aes_decrypt(ciphertext):
    """
    先尝试 AES-256-CBC 解密，失败则尝试纯 base64 解码。
    与参考脚本 N2D4ZCrypto.decrypt 逻辑保持一致。
    """
    if not ciphertext or not isinstance(ciphertext, str):
        return ciphertext
    # 已经是 URL 的直接返回
    if ciphertext.startswith('http://') or ciphertext.startswith('https://'):
        return ciphertext

    key = _AES_KEY.encode('utf-8')
    iv = _AES_IV.encode('utf-8')

    # 尝试 AES-256-CBC
    try:
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import unpad
        cipher = AES.new(key, AES.MODE_CBC, iv)
        ct = base64.b64decode(ciphertext)
        pt = unpad(cipher.decrypt(ct), AES.block_size)
        result = pt.decode('utf-8')
        return result.strip().strip('"').strip("'")
    except ImportError:
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.primitives import padding
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
            decryptor = cipher.decryptor()
            ct = base64.b64decode(ciphertext)
            pt = decryptor.update(ct) + decryptor.finalize()
            unpadder = padding.PKCS7(128).unpadder()
            pt = unpadder.update(pt) + unpadder.finalize()
            result = pt.decode('utf-8')
            return result.strip().strip('"').strip("'")
        except ImportError:
            print("[R3]缺少加密库，请安装: pip install pycryptodome")
    except Exception:
        pass

    # AES 失败，尝试纯 base64 解码（参考脚本的兜底逻辑）
    try:
        plain = base64.b64decode(ciphertext).decode('utf-8')
        return plain.strip().strip('"').strip("'")
    except Exception:
        pass

    # 都失败，原样返回
    return ciphertext


def _batch_decrypt(enc_list):
    """批量解密"""
    if not enc_list:
        return {}
    return {enc: _py_aes_decrypt(enc) for enc in enc_list}


# ==========================================
# 分类总表（只保留剧情区、视频区、精选区）
# ==========================================
SUB = [
    # ===== 第1组：剧情区 (juqing) =====
    ("最新剧情", "juqing", "/cYcL2p1cWluZy9saXN0cy5odG1s.html"),
    ("  麻豆传媒", "juqing", "/cYcL2p1cWluZy9saXN0Lem6u%2BixhuS8oOWqki5odG1s.html"),
    ("  天美传媒", "juqing", "/cYcL2p1cWluZy9saXN0LeWkqee%2BjuS8oOWqki5odG1s.html"),
    ("  星空果冻", "juqing", "/cYcL2p1cWluZy9saXN0LeaYn%2BepuuaenOWGuy5odG1s.html"),
    ("  蜜桃精东", "juqing", "/cYcL2p1cWluZy9saXN0LeicnOahg%2BeyvuS4nC5odG1s.html"),
    ("  韩国伦理", "juqing", "/cYcL2p1cWluZy9saXN0LemfqeWbveS8pueQhi5odG1s.html"),
    ("  COSPLAY", "juqing", "/cYcL2p1cWluZy9saXN0LUNPU1BMQVkuaHRtbA%3D%3D.html"),
    ("  经典三级", "juqing", "/cYcL2p1cWluZy9saXN0Lee7j%2BWFuOS4iee6py5odG1s.html"),
    ("  中文字幕", "juqing", "/cYcL2p1cWluZy9saXN0LeS4reaWh%2BWtl%2BW5lS5odG1s.html"),

    # ===== 第2组：视频/电影区 (shipin) =====
    ("最新电影", "shipin", "/cYcL3NoaXBpbi9saXN0cy5odG1s.html"),
    ("  日本av", "shipin", "/cYcL3NoaXBpbi9saXN0LeaXpeacrGF2Lmh0bWw%3D.html"),
    ("  韩国热舞", "shipin", "/cYcL3NoaXBpbi9saXN0LemfqeWbveeDreiIni5odG1s.html"),
    ("  欧美精品", "shipin", "/cYcL3NoaXBpbi9saXN0Leasp%2Be%2BjueyvuWTgS5odG1s.html"),
    ("  动漫电影", "shipin", "/cYcL3NoaXBpbi9saXN0LeWKqOa8q%2BeUteW9sS5odG1s.html"),
    ("  国产自拍", "shipin", "/cYcL3NoaXBpbi9saXN0LeWbveS6p%2BiHquaLjS5odG1s.html"),
    ("  岛国无码", "shipin", "/cYcL3NoaXBpbi9saXN0LeWym%2BWbveaXoOeggS5odG1s.html"),
    ("  JVID", "shipin", "/cYcL3NoaXBpbi9saXN0LUpWSUQuaHRtbA%3D%3D.html"),
    ("  SM调教", "shipin", "/cYcL3NoaXBpbi9saXN0LVNN6LCD5pWZLmh0bWw%3D.html"),

    # ===== 第3组：精选区 (jingpin) =====
    ("最新精选", "jingpin", "/cYcL2ppbmdwaW4vbGlzdHMuaHRtbA%3D%3D.html"),
    ("  软萌福利姬", "jingpin", "/cYcL2ppbmdwaW4vbGlzdC3ova%2FokIznpo%2FliKnlp6wuaHRtbA%3D%3D.html"),
    ("  黑料头条", "jingpin", "/cYcL2ppbmdwaW4vbGlzdC3pu5HmlpnlpLTmnaEuaHRtbA%3D%3D.html"),
    ("  明星AI", "jingpin", "/cYcL2ppbmdwaW4vbGlzdC3mmI7mmJ9BSS5odG1s.html"),
    ("  人妖伪娘", "jingpin", "/cYcL2ppbmdwaW4vbGlzdC3kurrlppbkvKrlqJguaHRtbA%3D%3D.html"),
    ("  onlyfans", "jingpin", "/cYcL2ppbmdwaW4vbGlzdC1vbmx5ZmFucy5odG1s.html"),
    ("  探花系列", "jingpin", "/cYcL2ppbmdwaW4vbGlzdC3mjqLoirHns7vliJcuaHRtbA%3D%3D.html"),
    ("  主播大秀", "jingpin", "/cYcL2ppbmdwaW4vbGlzdC3kuLvmkq3lpKfnp4AuaHRtbA%3D%3D.html"),
    ("  韩国主播", "jingpin", "/cYcL2ppbmdwaW4vbGlzdC3pn6nlm73kuLvmkq0uaHRtbA%3D%3D.html"),
]


class Spider(_B):
    def init(self, ext=""):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": U})
        self.cache = {}
        
        if ext and ext.startswith("http"):
            self.H = ext.rstrip("/")
            print(f"[R3]使用外部传入域名: {self.H}")
        else:
            self.H = _discover_domain()
            print(f"[R3]自动发现域名: {self.H}")
        
        # 运行时自动解密所有分类名称
        try:
            global SUB
            all_names = list({n for n, z, u in SUB})
            if all_names:
                dec = _batch_decrypt(all_names)
                SUB = [(dec.get(n, n), z, u) for n, z, u in SUB]
        except Exception as ex:
            print("[R3]auto decrypt menu names failed:", ex)

    def getName(self): 
        return "R3E2O"
    
    def isVideoFormat(self, u): 
        return ".m3u8" in u or ".mp4" in u
    
    def manualVideoCheck(self): 
        return False

    def _get(self, u):
        if not u.startswith("http"):
            u = self.H + u
        try:
            r = self.s.get(u, timeout=20)
            r.encoding = 'utf-8'
            return r.text
        except:
            return ""

    def _proxy(self, kind, url):
        try:
            return self.getProxyUrl() + "&kind=" + kind + "&url=" + quote(url, safe="")
        except:
            return url

    def _image(self, path):
        return self._proxy("img", IMG_HOST + path) if path else ""

    def _hls(self, url):
        return self._proxy("hls", url)

    def _cards(self, h):
        v = []
        enc = {}
        for m in re.finditer(r'<a[^>]*class="video-item"[^>]*href="([^"]+)"[^>]*>', h, re.S):
            href = m.group(1)
            end = h.find('</a>', m.end())
            inner = h[m.end():end] if end > 0 else ""
            tm = re.search(r'class="video-item-title[^"]*"[^>]*title="([^"]*)"', inner)
            raw_title = tm.group(1).strip() if tm else ""
            im = re.search(r'data-base64="([^"]+)"', inner)
            img = self._image(im.group(1)) if im else ""
            dm = re.search(r'class="video-item-date"[^>]*>([^<]+)', inner)
            date = dm.group(1).strip() if dm else ""
            enc[href] = raw_title
            v.append({"vod_id": href, "vod_name": raw_title, "vod_pic": img, "vod_remarks": date})
        if enc:
            dec = _batch_decrypt(list(enc.values()))
            for item in v:
                k = enc[item["vod_id"]]
                item["vod_name"] = dec.get(k, k)
                # 同时存多种 key 形式，防止 detailContent 对不上
                self.cache[item["vod_id"]] = {"name": item["vod_name"], "pic": item["vod_pic"]}
                if not item["vod_id"].startswith('http'):
                    self.cache[self.H + item["vod_id"]] = {"name": item["vod_name"], "pic": item["vod_pic"]}
                elif item["vod_id"].startswith(self.H):
                    self.cache[item["vod_id"][len(self.H):]] = {"name": item["vod_name"], "pic": item["vod_pic"]}
        return v

    def homeContent(self, filter=False):
        return {"class": [{"type_id": str(i), "type_name": n} for i, (n, z, u) in enumerate(SUB)]}

    def homeVideoContent(self):
        h = self._get(self.H + SUB[0][2])
        return {"list": self._cards(h) if h else []}

    def categoryContent(self, tid, pg=1, filter=False, extend=None):
        # pg 可能是字符串，必须先转 int
        try:
            pg = int(str(pg))
        except:
            pg = 1
        try:
            idx = int(str(tid))
            name, zone, path = SUB[idx]
            url = self.H + path
            # 翻页支持
            if pg > 1:
                if '?' in url:
                    url += f"&page={pg}"
                else:
                    url += f"?page={pg}"
            h = self._get(url)
            if not h:
                return {"list": [], "page": pg, "pagecount": pg - 1 if pg > 1 else 1}
            cards = self._cards(h)
            has_more = len(cards) > 0
            pagecount = 999 if has_more else pg
            return {
                "list": cards, 
                "page": pg, 
                "pagecount": pagecount, 
                "limit": len(cards), 
                "total": len(cards)
            }
        except Exception as e:
            print("[R3]cat:", e)
            return {"list": [], "page": pg, "pagecount": 1}

    def detailContent(self, ids):
        play_url = str(ids[0])
        if not play_url.startswith("http"):
            play_url = self.H + play_url
        
        # 多种方式查找 cache
        cached = self.cache.get(play_url, {})
        if not cached and not play_url.startswith('http'):
            cached = self.cache.get(self.H + play_url, {})
        if not cached and play_url.startswith(self.H):
            cached = self.cache.get(play_url[len(self.H):], {})
        
        title = cached.get("name", "")
        img = cached.get("pic", "")
        
        h = self._get(play_url)
        if not h:
            return {"list": []}
        
        # cache 没命中时，从页面提取标题并解密（参考脚本的做法）
        if not title:
            for pattern in [
                r'<h1[^>]*>(.*?)</h1>',
                r'<title>([^<]+)</title>',
                r'class="[^"]*dec-ti[^"]*"[^>]*title="([^"]+)"',
                r'class="video-item-title[^"]*"[^>]*title="([^"]+)"',
            ]:
                m = re.search(pattern, h, re.S)
                if m:
                    raw = re.sub(r'<[^>]+>', '', m.group(1)).strip()
                    dec = _py_aes_decrypt(raw)
                    if dec and dec != raw:
                        title = dec
                        break
                    elif not title:
                        title = raw
                if title:
                    break
            if not title:
                title = play_url
        
        # 封面兜底提取
        if not img:
            for pattern in [
                r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"',
                r'<img[^>]*data-base64="([^"]+)"',
                r'data-original="([^"]+)"',
            ]:
                m = re.search(pattern, h)
                if m:
                    img_raw = _py_aes_decrypt(m.group(1))
                    if img_raw.startswith('http'):
                        img = img_raw
                    elif img_raw:
                        img = IMG_HOST + img_raw
                    break
        
        vm = re.search(r"var video\s*=\s*decodeString\('([^']+)'\)", h)
        hm = re.search(r"var m3u8_host\s*=\s*decodeString\('([^']+)'\)", h)
        src = ""
        if vm and hm:
            try:
                vpath = base64.b64decode(vm.group(1)).decode()
            except:
                vpath = ""
            try:
                hurl = base64.b64decode(hm.group(1)).decode()
            except:
                hurl = ""
            if hurl and vpath:
                src = self._hls(hurl.rstrip("/") + "/" + vpath.lstrip("/"))
        pf = ["线路1"]
        pu = ["线路1$" + src] if src else ["线路1$" + play_url]
        return {"list": [{"vod_id": play_url, "vod_name": title, "vod_pic": img,
            "type_name": "", "vod_year": "", "vod_area": "", "vod_remarks": "",
            "vod_actor": "", "vod_director": "", "vod_content": "",
            "vod_play_from": "$$$".join(pf), "vod_play_url": "$$$".join(pu)}]}

    def playerContent(self, flag, id, vipFlags=None):
        if id and (".m3u8" in id or ".mp4" in id):
            return {"url": id, "header": json.dumps({"User-Agent": U, "Referer": self.H + "/"})}
        d = self.detailContent([id])
        if d and d.get("list"):
            us = d["list"][0].get("vod_play_url", "").split("$$$")
            if us:
                f = us[0]
                url = f.split("$", 1)[1] if "$" in f else f
                return {"url": url, "header": json.dumps({"User-Agent": U, "Referer": self.H + "/"})}
        return {"url": ""}

    def searchContent(self, key, quick=False, pg=1):
        return {"list": []}

    def localProxy(self, param):
        try:
            raw = (param or {}).get("url", "")
            kind = (param or {}).get("kind", "")
            url = unquote(raw)
            if not url.startswith("https://"):
                return [404, "text/plain", b""]
            headers = {"User-Agent": U, "Referer": self.H + "/"}
            r = self.s.get(url, headers=headers, timeout=30)
            if r.status_code != 200:
                return [r.status_code, "text/plain", b""]
            if kind == "img":
                text = r.text.strip()
                if text.startswith("data:image/") and "," in text:
                    meta, payload = text.split(",", 1)
                    mime = meta[5:meta.index(";")]
                    return [200, mime, base64.b64decode(payload)]
                return [200, r.headers.get("Content-Type", "image/jpeg"), r.content]
            if kind == "hls":
                text = r.text
                out = []
                for line in text.splitlines():
                    if line.startswith("#EXT-X-KEY:"):
                        line = re.sub(r'URI="([^"]+)"', lambda m: 'URI="' + self._proxy("bin", urljoin(url, m.group(1))) + '"', line)
                    out.append(line)
                return [200, "application/vnd.apple.mpegurl", "\n".join(out).encode()]
            return [200, r.headers.get("Content-Type", "application/octet-stream"), r.content]
        except Exception as e:
            print("[R3]proxy:", e)
            return [500, "text/plain", b""]
