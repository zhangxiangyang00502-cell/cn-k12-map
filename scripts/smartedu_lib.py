"""smartedu 平台抓取公共工具：带缓存的 GET、限流、重试。"""
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

RAW = os.path.join(os.path.dirname(__file__), "..", "data", "raw_smartedu")
os.makedirs(RAW, exist_ok=True)

HOSTS = ["https://s-file-1.ykt.cbern.com.cn", "https://s-file-2.ykt.cbern.com.cn",
         "https://bdcs-file-1.ykt.cbern.com.cn"]

_lock = threading.Lock()
_last = [0.0]


def _throttle():
    with _lock:
        dt = time.time() - _last[0]
        if dt < 0.2:
            time.sleep(0.2 - dt)
        _last[0] = time.time()


def fetch_json(url, cache_name=None, retries=3):
    """GET json，带磁盘缓存、限流、重试。失败返回 None。"""
    if cache_name:
        path = os.path.join(RAW, cache_name)
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    last_err = None
    for attempt in range(retries):
        _throttle()
        try:
            r = requests.get(url, timeout=30,
                             headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                data = r.json()
                if cache_name:
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False)
                return data
            last_err = f"HTTP {r.status_code}"
        except Exception as e:  # noqa
            last_err = str(e)
        time.sleep(0.5 * (attempt + 1))
    print(f"  [fail] {url} -> {last_err}")
    return None


def fetch_multi(jobs, workers=6):
    """jobs: list of (url, cache_name)；返回 {cache_name: data}。并发<=6。"""
    out = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for name, data in zip([j[1] for j in jobs],
                              ex.map(lambda j: fetch_json(j[0], j[1]), jobs)):
            out[name] = data
    return out


_punct = re.compile(r"[\s　，。、；：:；;!！?？·…—\-—–《》〈〉\"'“”‘’（）()\[\]【】.,]+")


def norm(s):
    """标题归一化：去空白和标点，用于匹配。"""
    return _punct.sub("", s or "")


def strip_html(s):
    if not s:
        return ""
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"</p>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    import html as _h
    s = _h.unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{2,}", "\n", s)
    return s.strip()
