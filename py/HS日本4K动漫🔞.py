import sys, re, requests, urllib.parse
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from base.spider import Spider

requests.packages.urllib3.disable_warnings()

class Spider(Spider):
    def getName(self): return "Hstream"

    def init(self, extend=""):
        self.siteUrl = "https://hstream.moe"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': self.siteUrl + '/',
            'Origin': self.siteUrl,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
        }
        self.sess = requests.Session()
        self.sess.mount('https://', HTTPAdapter(max_retries=Retry(total=3, status_forcelist=[500, 502, 503, 504])))

    def fetch(self, url):
        try: return self.sess.get(url, headers=self.headers, timeout=10, verify=False)
        except: return None

    def homeContent(self, filter):
        cats = [
            {"type_id": "recently-uploaded", "type_name": "最近上传"},
            {"type_id": "recently-released", "type_name": "最新发布"},
            {"type_id": "view-count", "type_name": "最多观看"},
            {"type_id": "tag_uncensored", "type_name": "步兵无码"},
            {"type_id": "tag_milf", "type_name": "人妻(Milf)"},
            {"type_id": "tag_school-girl", "type_name": "学生妹"},
            {"type_id": "tag_big-boobs", "type_name": "巨乳(Boobs)"},
            {"type_id": "tag_succubus", "type_name": "魅魔"},
            {"type_id": "tag_tentacle", "type_name": "触手"},
            {"type_id": "tag_maid", "type_name": "女仆"},
            {"type_id": "tag_bdsm", "type_name": "调教(BDSM)"},
            {"type_id": "tag_elf", "type_name": "精灵(Elf)"},
            {"type_id": "tag_4k-48fps", "type_name": "4K专区"}
        ]
        return {'class': cats}

    def categoryContent(self, tid, pg, filter, extend):
        if tid.startswith("tag_"):
            tag_slug = tid.replace("tag_", "")
            url = f"{self.siteUrl}/search?order=recently-uploaded&tags%5B0%5D={tag_slug}&page={pg}"
        else:
            url = f"{self.siteUrl}/search?order={tid}&page={pg}"
        return self.postList(url, int(pg))

    def searchContent(self, key, quick, pg=1):
        url = f"{self.siteUrl}/search?search={key}&page={pg}"
        return self.postList(url, int(pg))

    def postList(self, url, pg):
        r = self.fetch(url)
        l = []
        if r and r.ok:
            blocks = re.findall(r'<a[^>]*href=["\'][^"\']*/hentai/([^"\']+)["\'][^>]*>(.*?)</a>', r.text, re.S)
            seen = set()
            for block in blocks:
                vod_id = block[0]
                if vod_id in seen: continue
                seen.add(vod_id)
                
                inner_html = block[1]
                
                pic_match = re.search(r'src=["\']([^"\']+)["\']', inner_html)
                vod_pic = pic_match.group(1) if pic_match else f"{self.siteUrl}/images/default-avatar.webp"
                if not vod_pic.startswith("http"): vod_pic = f"{self.siteUrl}{vod_pic}"
                
                t_match = re.search(r'alt=["\']([^"\']+)["\']', inner_html)
                vod_name = t_match.group(1) if t_match else re.sub(r'<[^>]+>', '', inner_html).strip()
                if not vod_name: vod_name = vod_id

                l.append({
                    'vod_id': f"{vod_id}@@@{vod_name}@@@{vod_pic}",
                    'vod_name': vod_name,
                    'vod_pic': vod_pic,
                    'vod_remarks': '4K/FHD',
                    'style': {"type": "rect", "ratio": 1.33}
                })
                
        return {'list': l, 'page': pg, 'pagecount': pg + 1 if len(l) == 24 else pg, 'limit': 24, 'total': 9999}

    def detailContent(self, ids):
        vid = ids[0]
        name, pic = vid, ""
        
        if "@@@" in vid:
            parts = vid.split("@@@")
            vid = parts[0]
            name = parts[1] if len(parts) > 1 else name
            pic = parts[2] if len(parts) > 2 else pic

        # 【极致纯净】：只有 4K，简单粗暴！
        play_list = [
            f"4K画质${vid}|2160/manifest.mpd"
        ]

        vod = {
            'vod_id': ids[0],
            'vod_name': name,
            'vod_pic': pic,
            'type_name': '动漫',
            'vod_play_from': 'HStream',
            'vod_play_url': "#".join(play_list)
        }
        return {'list': [vod]}

    def playerContent(self, flag, id, vipFlags):
        id_parts = id.split("|")
        vid = id_parts[0]
        mode = id_parts[1] if len(id_parts) > 1 else "2160/manifest.mpd"

        page_url = f"{self.siteUrl}/hentai/{vid}"
        try:
            r = self.sess.get(page_url, headers=self.headers, verify=False, timeout=10)
            
            xsrf_cookie = self.sess.cookies.get('XSRF-TOKEN', '')
            if xsrf_cookie:
                xsrf_cookie = urllib.parse.unquote(xsrf_cookie)
                
            meta_token = ""
            token_match = re.search(r'<meta name="csrf-token" content="([^"]+)">', r.text)
            if token_match:
                meta_token = token_match.group(1)

            if not xsrf_cookie and not meta_token:
                return {"parse": 0, "url": f"error://token_not_found"}

            api_headers = self.headers.copy()
            api_headers.update({
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": page_url
            })
            if xsrf_cookie: api_headers["X-XSRF-TOKEN"] = xsrf_cookie
            if meta_token: api_headers["X-CSRF-TOKEN"] = meta_token

            # 从隐藏 input 里挖出原生 episode_id
            episode_id = None
            e_id_match = re.search(r'id=["\']e_id["\'][^>]*value=["\'](\d+)["\']|value=["\'](\d+)["\'][^>]*id=["\']e_id["\']', r.text, re.I)
            if e_id_match:
                episode_id = e_id_match.group(1) or e_id_match.group(2)
            else:
                lw_match = re.search(r'"class":"App\\\\Models\\\\Episode","key":(\d+)', r.text)
                if lw_match:
                    episode_id = lw_match.group(1)

            if not episode_id:
                return {"parse": 0, "url": "error://episode_id_not_found"}

            payload = {"episode_id": episode_id} 
            api_url = f"{self.siteUrl}/player/api"
            
            res = self.sess.post(api_url, json=payload, headers=api_headers, timeout=10, verify=False)
            
            if res.ok:
                data = res.json()
                
                # 依然坚守主节点
                domains = data.get("stream_domains", [])
                if not domains:
                    domains = data.get("asia_stream_domains", [])
                    
                if domains and "stream_url" in data:
                    domain = domains[0].rstrip('/')
                    stream_url = data["stream_url"].strip('/')
                    play_url = f"{domain}/{stream_url}/{mode}"
                    
                    return {
                        "parse": 0, 
                        "url": play_url, 
                        "header": {
                            "Referer": self.siteUrl + "/",
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                        }
                    }
                else:
                    return {"parse": 0, "url": "error://json_missing_domains"}
            else:
                return {"parse": 0, "url": f"error://post_api_failed_status_{res.status_code}"}
                
        except Exception as e:
            return {"parse": 0, "url": f"error://exception_{str(e)[:20]}"}
