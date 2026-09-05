import json
from base.spider import Spider

class Spider(Spider):
    def getName(self):
        return "PigAV_Stable"

    def init(self, extend=""):
        self.base_url = "https://pigav.ws"
        self.api_url = "https://pigav.ws/api/v1"
        # 基础浏览器特征
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://pigav.ws",
            "Referer": "https://pigav.ws/"
        }
        self.page_size = 24

    def homeContent(self, filter):
        result = {"class": []}
        result["class"] = [
            {"type_id": "publishedAt", "type_name": "最近更新"},
            {"type_id": "hot", "type_name": "热门视频"},
            {"type_id": "views", "type_name": "最多观看"}
        ]
        result["list"] = self.get_videos(f"{self.api_url}/videos?sort=-publishedAt&count={self.page_size}&start=0")
        return result

    def categoryContent(self, tid, pg, filter, extend):
        sort_map = {"publishedAt": "-publishedAt", "hot": "-hot", "views": "-views"}
        sort = sort_map.get(tid, "-publishedAt")
        p = int(pg)
        start = (max(1, p) - 1) * self.page_size
        url = f"{self.api_url}/videos?sort={sort}&count={self.page_size}&start={start}"
        return {"list": self.get_videos(url)}

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) else ids
        url = f"{self.api_url}/videos/{vid}"
        try:
            res = self.fetch(url, headers=self.headers, timeout=10)
            data = json.loads(res.text if hasattr(res, 'text') else res)
            vod = {
                "vod_id": vid,
                "vod_name": data.get("name", ""),
                "vod_pic": self.fix_url(data.get("thumbnailPath", "")),
                "vod_remarks": self.format_time(data.get("duration", 0)),
                "vod_actor": data.get("channel", {}).get("displayName", ""),
                "vod_content": data.get("description", ""),
                "vod_play_from": "PigAV",
                "vod_play_url": f"播放正片${vid}"
            }
            return {"list": [vod]}
        except:
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        p = int(pg)
        start = (max(1, p) - 1) * self.page_size
        url = f"{self.api_url}/search/videos?search={key}&count={self.page_size}&start={start}"
        return {"list": self.get_videos(url)}

    def playerContent(self, flag, id, vipFlags):
        url = f"{self.api_url}/videos/{id}"
        
        # 终极伪装 Header：模拟 Chrome 播放内核请求行为，防止 CDN 断流
        play_headers = {
            "User-Agent": self.headers["User-Agent"],
            "Referer": f"https://pigav.ws/videos/{id}",
            "Origin": "https://pigav.ws",
            "Accept": "*/*",
            "Range": "bytes=0-", # 核心：开启断点续传支持
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "video",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site"
        }

        try:
            res = self.fetch(url, headers=self.headers, timeout=12)
            data = json.loads(res.text if hasattr(res, 'text') else res)
            
            play_url = ""
            
            # 优先方案：HLS (m3u8) 分片加载，最不容易超时
            streaming = data.get("streamingPlaylists", [])
            if streaming:
                # 策略：如果网络差，选列表中间的画质（通常 0 是低，最后是高）
                # 这里我们尝试选倒数第二个，通常是 720P，兼顾清晰度与速度
                idx = max(0, len(streaming) - 2)
                play_url = streaming[idx].get("playlistUrl")
            
            # 备选方案：MP4 直链
            if not play_url:
                files = data.get("files", [])
                if files:
                    # 优先寻找高度 <= 720 的文件
                    suitable_files = [f for f in files if f.get("resolution", {}).get("height", 0) <= 720]
                    best_file = suitable_files[-1] if suitable_files else files[0]
                    play_url = best_file.get("fileUrl") or best_file.get("fileDownloadUrl")

            if play_url:
                return {
                    "parse": 0,
                    "url": self.fix_url(play_url),
                    "header": play_headers,
                    "timeout": 60 # 延长内核超时建议值
                }
        except:
            pass
        return {"parse": 0, "url": ""}

    def get_videos(self, url):
        videos = []
        try:
            res = self.fetch(url, headers=self.headers, timeout=10)
            content = res.text if hasattr(res, 'text') else res
            data = json.loads(content)
            items = data.get("data", []) if isinstance(data, dict) else data
            for item in items:
                videos.append({
                    "vod_id": item.get("shortUUID") or item.get("uuid"),
                    "vod_name": item.get("name", ""),
                    "vod_pic": self.fix_url(item.get("thumbnailPath", "")),
                    "vod_remarks": self.format_time(item.get("duration", 0))
                })
        except:
            pass
        return videos

    def fix_url(self, path):
        if not path: return ""
        if path.startswith("http"): return path
        return self.base_url + path

    def format_time(self, seconds):
        try:
            sec = int(seconds)
            m, s = divmod(sec, 60)
            h, m = divmod(m, 60)
            return f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"
        except: return ""