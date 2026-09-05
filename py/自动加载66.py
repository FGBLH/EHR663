# -*- coding: utf-8 -*-
"""
TVBox 本地 Py/Js 爬虫聚合源
==============================
扫描 /py/ 和 /js/ 目录下的爬虫文件，聚合展示。
"""
import os
import json
import base64
from base.spider import Spider


class Spider(Spider):
    # ==========================================================================
    # 📂 【配置区】
    # ==========================================================================
    PY_DIR    = "/storage/emulated/0/海豚影视/海豚/py"
    JS_DIR    = "/storage/emulated/0/海豚影视/海豚/js"
    JAR_DIR   = "/storage/emulated/0/海豚影视/海豚/jar"
    SAVE_PATH = "/storage/emulated/0/海豚影视/海豚/海豚影视.json"
    LOGO_PATH = "/https://img.freepik.com/free-vector/cute-dolphin-swimming-cartoon-vector-icon-illustration-animal-nature-icon-isolated-flat-vector_138676-12582.jpg?semt=ais_hybrid&w=740&q=80"

    # 🔒 锁定在 sites 第 0、1 位的配置，无论扫描结果如何始终存在
    _LOCKED_SITES = [
		{
            "name": "🐬自动加载",
            "key": "自动加载",
            "type": 3,
            "api": "https://ghfast.top/https://raw.githubusercontent.com/FGBLH/HKL/refs/heads/main/py/自动加载66.py"
         },
		{
            "name": "🐬弹幕",
            "key": "弹幕豆瓣",
            "type": 3,
            "api": "csp_SecureDanmu",
            "searchable": 1,
            "jar": "https://ghfast.top/https://raw.githubusercontent.com/goodcommunication/mydm/main/danmu-spider-native.jar",
            "ext": {
            "apiUrls": [
            "https://danmu.iyo.us.ci/theft-dastardly-prognosis-hula-agenda2-dropkick|公益源",
            "https://logo.saodu.work:8888/87654321|公益源1",
            "https://dm.ljiaovm.com/luosen|公益源2"
            ],
            "titleMappingsUrl": "https://ghfast.top/https://raw.githubusercontent.com/goodcommunication/mydm/main/yins.json",
            "filter": "./lib/douban.json"
         }
	   }
    ]
    _LOCKED_KEYS = {"FishConfig", "Local"}
    # ==========================================================================

    def __init__(self):
        super().__init__()
        self.inited = False
        self.cache = {"categories": [], "file_index": {}}

    def getName(self):
        return "本地Py/Js聚合源"

    def init(self, extend):
        if self.inited:
            return
        self._scan_all()
        self._save_config_json()
        self.inited = True

    # ==========================================================================
    # 🔍 【扫描核心】手动递归，不依赖 os.walk
    # ==========================================================================
    def _scan_dir(self, base_dir, ext_list):
        """手动递归扫描目录，返回 [(full_path, file_name_no_ext, ext), ...]"""
        results = []
        if not base_dir:
            return results
        if not os.path.exists(base_dir):
            try:
                os.makedirs(base_dir, exist_ok=True)
            except Exception:
                return results
        if not os.path.isdir(base_dir):
            return results

        try:
            entries = os.listdir(base_dir)
        except Exception:
            return results

        for entry in sorted(entries):
            full_path = os.path.join(base_dir, entry)
            if entry.startswith("."):
                continue

            if os.path.isdir(full_path):
                sub_results = self._scan_dir(full_path, ext_list)
                results.extend(sub_results)
            elif os.path.isfile(full_path):
                lower_name = entry.lower()
                matched_ext = None
                for ext in ext_list:
                    if lower_name.endswith(ext):
                        matched_ext = ext
                        break
                if matched_ext:
                    name_no_ext = entry[: -len(matched_ext)]
                    results.append((full_path, name_no_ext, matched_ext))

        return results

    def _scan_all(self):
        """扫描 py 和 js 两个目录"""
        sites = []
        self_path = os.path.abspath(__file__) if hasattr(__file__, '__file__') else ""

        # ---- 扫描 .py 文件 ----
        py_files = self._scan_dir(self.PY_DIR, [".py"])
        for full_path, name, ext in py_files:
            if self_path and os.path.abspath(full_path) == self_path:
                continue
            display_name = f"【PY】{name}"
            tid = base64.b64encode(
                ("PY|" + full_path).encode("utf-8")
            ).decode("utf-8")
            sites.append({
                "type_id": tid,
                "type_name": display_name,
                "_path": full_path,
                "_ext": "py",
                "_dir": self.PY_DIR,
                "_sk": (0, name),
            })
            self.cache["file_index"][tid] = {
                "path": full_path,
                "ext": "py",
                "dir": self.PY_DIR,
            }

        # ---- 扫描 .js 文件 ----
        js_files = self._scan_dir(self.JS_DIR, [".js"])
        for full_path, name, ext in js_files:
            display_name = f"【JS】{name}"
            tid = base64.b64encode(
                ("JS|" + full_path).encode("utf-8")
            ).decode("utf-8")
            sites.append({
                "type_id": tid,
                "type_name": display_name,
                "_path": full_path,
                "_ext": "js",
                "_dir": self.JS_DIR,
                "_sk": (1, name),
            })
            self.cache["file_index"][tid] = {
                "path": full_path,
                "ext": "js",
                "dir": self.JS_DIR,
            }

        sites.sort(key=lambda x: x["_sk"])
        self.cache["categories"] = [
            {"type_id": s["type_id"], "type_name": s["type_name"]}
            for s in sites
        ]

    def _build_api(self, file_info):
        """拼接 api 相对路径"""
        f_path = file_info["path"]
        base_dir = file_info["dir"]
        try:
            rel = os.path.relpath(f_path, base_dir)
        except ValueError:
            rel = os.path.basename(f_path)
        dir_name = os.path.basename(base_dir)
        return "./" + dir_name + "/" + rel

    # ==========================================================================
    # 🆕 【jar 扫描】扫描 jar 目录下所有 .jar 文件，拼接 spider 值
    # ==========================================================================
    def _build_spider_value(self):
        """扫描 jar 目录，返回用分号拼接的所有 jar 相对路径"""
        jar_dir = self.JAR_DIR
        if not jar_dir or not os.path.isdir(jar_dir):
            return ""

        jar_files = []
        save_dir = os.path.dirname(self.SAVE_PATH)

        try:
            entries = sorted(os.listdir(jar_dir))
        except Exception:
            return ""

        for entry in entries:
            if entry.startswith("."):
                continue
            if entry.lower().endswith(".jar") and os.path.isfile(os.path.join(jar_dir, entry)):
                abs_jar = os.path.join(jar_dir, entry)
                try:
                    rel = os.path.relpath(abs_jar, save_dir)
                except ValueError:
                    rel = "jar/" + entry
                rel = "./" + rel.replace("\\", "/")
                if not rel.startswith("./"):
                    rel = "./" + rel.lstrip("./")
                jar_files.append(rel)

        return ";".join(jar_files)

    def _save_config_json(self):
        """保存 TVBox config.json"""
        config = {
            "logo": self.LOGO_PATH,
            "spider": self._build_spider_value(),
            "sites": []
        }
        for cat in self.cache["categories"]:
            file_info = self.cache["file_index"].get(cat["type_id"])
            if not file_info:
                continue
            f_path = file_info["path"]
            ext = file_info["ext"]
            f_base = os.path.basename(f_path)
            if "." in f_base:
                f_base = f_base.rsplit(".", 1)[0]
            config["sites"].append({
                "key": f_base + "_" + ext,
                "name": f_base,
                "type": 3,
                "searchable": 1,
                "quickSearch": 1,
                "filterable": 1,
                "api": self._build_api(file_info),
            })

        # ============================================================
        # 🔒 【锁定逻辑】移除冲突项 → 锁定项强制置顶
        # ============================================================
        filtered = [
            s for s in config["sites"]
            if s.get("key") not in self._LOCKED_KEYS
        ]
        config["sites"] = list(self._LOCKED_SITES) + filtered
        # ============================================================

        save_dir = os.path.dirname(self.SAVE_PATH)
        if save_dir and not os.path.exists(save_dir):
            try:
                os.makedirs(save_dir, exist_ok=True)
            except Exception:
                pass

        try:
            with open(self.SAVE_PATH, "w", encoding="utf-8") as fp:
                json.dump(config, fp, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ==========================================================================
    # 🔧 辅助
    # ==========================================================================
    def _get_file_info(self, tid):
        return self.cache["file_index"].get(tid)

    def _count_str(self):
        py_count = 0
        js_count = 0
        for info in self.cache["file_index"].values():
            if info["ext"] == "py":
                py_count += 1
            elif info["ext"] == "js":
                js_count += 1
        return f"共扫描到 {py_count} 个PY文件, {js_count} 个JS文件"

    def _count_jar_str(self):
        """统计 jar 文件数量"""
        if not os.path.isdir(self.JAR_DIR):
            return "jar 目录不存在"
        count = 0
        for f in os.listdir(self.JAR_DIR):
            if f.lower().endswith(".jar") and os.path.isfile(os.path.join(self.JAR_DIR, f)):
                count += 1
        return f"共扫描到 {count} 个JAR文件"

    # ==========================================================================
    # 📺 【TVBox 标准接口】
    # ==========================================================================
    def homeContent(self, filter):
        return {"class": self.cache["categories"]}

    def homeVod(self):
        info = self._count_str() + " | " + self._count_jar_str()
        return {"list": [{
            "vod_id": "__debug__",
            "vod_name": info,
            "vod_pic": "",
            "vod_remarks": "统计",
        }]}

    def categoryContent(self, tid, pg, filter, ext):
        if str(pg) != "1":
            return {"list": []}

        file_info = self._get_file_info(tid)
        if not file_info:
            return {"list": []}

        f_path = file_info["path"]
        if not os.path.exists(f_path):
            return {"list": []}

        f_base = os.path.basename(f_path)
        if "." in f_base:
            f_base = f_base.rsplit(".", 1)[0]
        ext_name = file_info["ext"]

        tag = "PY" if ext_name == "py" else "JS"
        v_id = base64.b64encode(
            (tag + "|" + f_path).encode("utf-8")
        ).decode("utf-8")

        return {"list": [{
            "vod_id": v_id,
            "vod_name": f_base,
            "vod_pic": "",
            "vod_remarks": "[" + ext_name.upper() + "]",
        }]}

    def detailContent(self, array):
        try:
            v_id_raw = str(array[0])

            if v_id_raw == "__debug__":
                info = self._count_str() + "\n" + self._count_jar_str()
                detail = "PY目录: " + self.PY_DIR + "\n"
                detail += "JS目录: " + self.JS_DIR + "\n"
                detail += "JAR目录: " + self.JAR_DIR + "\n"
                detail += "配置文件: " + self.SAVE_PATH + "\n\n"
                detail += info + "\n\n"
                detail += "spider 值:\n  " + self._build_spider_value() + "\n\n"
                detail += "已扫描文件列表:\n"
                for tid, finfo in self.cache["file_index"].items():
                    detail += "  [" + finfo["ext"].upper() + "] " + finfo["path"] + "\n"
                return {"list": [{
                    "vod_name": "扫描调试信息",
                    "vod_pic": "",
                    "vod_play_from": "信息",
                    "vod_play_url": "",
                    "vod_content": detail,
                }]}

            v_id_padded = v_id_raw + "=" * ((4 - len(v_id_raw) % 4) % 4)
            raw = base64.b64decode(v_id_padded).decode("utf-8", errors="ignore")

            if "|" in raw:
                tag, f_path = raw.split("|", 1)
            else:
                tag, f_path = "PY", raw

            if not os.path.exists(f_path):
                return {"list": [{"vod_name": "文件不存在", "vod_content": "路径: " + f_path}]}

            f_base = os.path.basename(f_path)
            if "." in f_base:
                f_base = f_base.rsplit(".", 1)[0]
            ext_name = f_path.rsplit(".", 1)[-1] if "." in f_path else "unknown"

            file_info = self.cache["file_index"].get(v_id_raw)
            if file_info:
                api = self._build_api(file_info)
            else:
                api = f_path

            site_info = {
                "key": f_base + "_" + ext_name,
                "name": f_base,
                "type": 3,
                "searchable": 1,
                "quickSearch": 1,
                "filterable": 1,
                "api": api,
            }
            info_text = json.dumps(site_info, ensure_ascii=False, indent=2)

            self._save_config_json()

            return {"list": [{
                "vod_name": "[" + ext_name.upper() + "] " + f_base,
                "vod_pic": "",
                "vod_play_from": "配置信息",
                "vod_play_url": "查看配置$" + f_path,
                "vod_content": (
                    "配置已自动保存到: " + self.SAVE_PATH + "\n\n"
                    "站点类型: " + ext_name.upper() + "\n\n"
                    "站点配置:\n" + info_text + "\n\n"
                    "文件路径: " + f_path
                ),
            }]}
        except Exception as e:
            return {"list": [{"vod_name": "解析错误", "vod_content": str(e)}]}

    def searchContent(self, key, quick):
        res = []
        for tid, file_info in self.cache["file_index"].items():
            f_path = file_info["path"]
            ext_name = file_info["ext"]
            f_base = os.path.basename(f_path)
            if "." in f_base:
                f_base = f_base.rsplit(".", 1)[0]
            if key.lower() in f_base.lower():
                tag = "PY" if ext_name == "py" else "JS"
                v_id = base64.b64encode(
                    (tag + "|" + f_path).encode("utf-8")
                ).decode("utf-8")
                res.append({
                    "vod_id": v_id,
                    "vod_name": "[" + ext_name.upper() + "] " + f_base,
                    "vod_pic": "",
                    "vod_remarks": self._build_api(file_info),
                })
        return {"list": res}

    def playerContent(self, flag, id, vipFlags):
        url = id.split("$")[-1] if "$" in id else id
        return {"url": url, "header": {}, "parse": 0}

    def destroy(self):
        return "destroy"
