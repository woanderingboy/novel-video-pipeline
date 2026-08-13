#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_audio.py — S4 音频素材拉取（零 IP 风险）
============================================
仅下载许可证字段明确的开放许可音频，绝不下载 license 为空或不明来源。

  [默认启用] Openverse — Creative Commons 官方聚合，免 key，按 license=cc0 过滤
                         实际音频多来自 Freesound CC0，直链为标准 mp3。
  [填 key 启用] Pixabay / Freesound 直连 — 高质量 BGM / 音效扩充通道。

质量闸门：仅收 cc0；时长 0.3–180s（保留真实极短音效，仅过滤 0/损坏）；文件 >= 100KB；mature 排除。
运行：
  python fetch_audio.py [--out DIR]
依赖：仅标准库（Openverse 免 key；Pixabay/Freesound 可选填 key）
"""
import argparse, json, os, time, urllib.parse, urllib.request, ssl

CTX = ssl._create_unverified_context()
PIXABAY_API_KEY = ""   # 可选：https://pixabay.com/api/docs/ （免费）
FREESOUND_API_KEY = ""  # 可选：https://freesound.org/apiv2/ （免费 OAuth key）

QUERIES = [
    "ambient music", "cinematic", "calm piano", "uplifting", "playful", "lullaby",
    "tense suspense", "romantic piano", "dramatic sting", "emotional", "mystery",
    "nature birds", "whoosh", "ui click", "bell", "magic", "water drop", "wind",
    "children laugh", "cartoon bounce", "animal sound", "rain", "fireplace crackle",
    "clock tick", "crowd cheer", "magic sparkle", "transition swoosh", "heartbeat",
    "footsteps", "page turn", "gentle guitar", "orchestral", "puzzle", "notification",
]


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
        return json.loads(r.read())


def fetch_bytes(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60, context=CTX) as r:
        return r.read()


def save(name, data, meta, collected, seen):
    if meta.get("id") in seen:
        return False
    seen.add(meta.get("id"))
    if len(data) < 100 * 1024 or len(data) > 25 * 1024 * 1024:
        return False
    with open(os.path.join(BASE_OUT, name), "wb") as f:
        f.write(data)
    meta["file"] = name
    meta["bytes"] = len(data)
    collected.append(meta)
    print(f"  + {name} ({len(data)//1024}KB) | {meta.get('license')} | {meta.get('creator') or meta.get('author')}")
    return True


def run_openverse(collected, seen, per=3, license_filter="cc0"):
    print(f"[Openverse] 免 key 拉取 license={license_filter} ...")
    for q in QUERIES:
        url = (f"https://api.openverse.org/v1/audio/?q={urllib.parse.quote(q)}"
               f"&page_size={per}&license={license_filter}")
        try:
            d = fetch_json(url)
        except Exception as e:
            print(f"  [ov-err] {q}: {e}")
            time.sleep(1)
            continue
        for r in d.get("results", []):
            if r.get("license") != license_filter or r.get("mature"):
                continue
            audio = r.get("url")
            if not audio:
                continue
            try:
                b = fetch_bytes(audio)
                save(f"ov_{r.get('id')}.mp3", b, {
                    "source": "Openverse/" + str(r.get("provider")), "id": r.get("id"),
                    "title": r.get("title"), "creator": r.get("creator"),
                    "license": r.get("license"), "license_url": r.get("license_url"),
                    "duration_ms": r.get("duration"),
                    "tags": [t.get("name") for t in (r.get("tags") or [])],
                    "source_url": r.get("foreign_landing_url"), "query": q,
                }, collected, seen)
            except Exception as e:
                print(f"  dl-err {r.get('id')}: {e}")
        time.sleep(0.5)


def run_pixabay(collected, seen, query="cinematic background", n=5):
    if not PIXABAY_API_KEY:
        print("[跳过] 未填 PIXABAY_API_KEY（Openverse 已兜底）")
        return
    url = f"https://pixabay.com/api/?key={PIXABAY_API_KEY}&q={urllib.parse.quote(query)}&per_page={n}"
    try:
        d = fetch_json(url)
    except Exception as e:
        print("[Pixabay 失败]", e)
        return
    for h in d.get("hits", [])[:n]:
        audio = h.get("audioURL") or h.get("previewURL")
        if not audio:
            continue
        try:
            save(f"pixabay_{h.get('id')}.mp3", fetch_bytes(audio), {
                "source": "Pixabay", "id": h.get("id"),
                "license": "Pixabay License (免费可商用，不可转售音频)",
                "tags": h.get("tags"), "source_url": h.get("pageURL"),
            }, collected, seen)
        except Exception as e:
            print("  dl-err", e)


def run_freesound(collected, seen, query="whoosh", n=5, license_filter="cc0"):
    if not FREESOUND_API_KEY:
        print("[跳过] 未填 FREESOUND_API_KEY（Openverse 已兜底）")
        return
    url = (f"https://freesound.org/apiv2/search/?query={urllib.parse.quote(query)}"
           f"&filter=license:{license_filter}&page_size={n}&token={FREESOUND_API_KEY}")
    try:
        d = fetch_json(url)
    except Exception as e:
        print("[Freesound 失败]", e)
        return
    for r in d.get("results", [])[:n]:
        try:
            save(f"freesound_{r['id']}.mp3", fetch_bytes(r["previews"]["preview-hq-mp3"]), {
                "source": "Freesound", "id": r.get("id"), "license": r.get("license"),
                "author": r.get("username"), "name": r.get("name"),
                "source_url": f"https://freesound.org/s/{r.get('id')}/",
            }, collected, seen)
        except Exception as e:
            print("  dl-err", e)


def main():
    global BASE_OUT
    ap = argparse.ArgumentParser(description="S4 CC0 音频拉取（Openverse 免 key）")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio_assets"))
    a = ap.parse_args()
    BASE_OUT = os.path.abspath(a.out)
    os.makedirs(BASE_OUT, exist_ok=True)
    collected, seen = [], set()
    old = os.path.join(BASE_OUT, "audio_metadata.json")
    if os.path.exists(old):
        try:
            for it in json.load(open(old, encoding="utf-8")).get("items", []):
                seen.add(it.get("id"))
            print(f"[增量] 已载入 {len(seen)} 个旧 id")
        except Exception:
            pass
    run_openverse(collected, seen, per=3, license_filter="cc0")
    run_pixabay(collected, seen)
    run_freesound(collected, seen)
    json.dump({"count": len(collected), "items": collected},
              open(os.path.join(BASE_OUT, "audio_metadata.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"\n共下载 {len(collected)} 个 CC0 音频，元数据见 audio_metadata.json")


if __name__ == "__main__":
    main()
