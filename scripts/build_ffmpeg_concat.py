#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_ffmpeg_concat.py — S5 合成辅助：由 storyboard.json 生成 FFmpeg concat 列表 + 拼接命令

读 storyboard.json 的 shots（shot_id + duration_s），为每段 clip（<clips-dir>/<shot_id>.mp4）
生成 FFmpeg concat demuxer 列表（含 duration 指令，严格对齐分镜时长）。若项目含
audio_manifest.json，则额外给出音视频合成命令。

纯标准库，无需 pip install。

用法：
  python scripts/build_ffmpeg_concat.py --project <DIR> --clips-dir <DIR>/clips --out <DIR>/concat.txt
"""
import argparse
import json
import os
import sys

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(path):
    if not os.path.exists(path):
        return None
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception as e:  # noqa
        print(f"[warn] 解析失败 {path}: {e}", file=sys.stderr)
        return None


def main():
    ap = argparse.ArgumentParser(description="S5：由 storyboard.json 生成 FFmpeg 拼接列表 + 命令")
    ap.add_argument("--project", required=True, help="含 storyboard.json（可选 audio_manifest.json）的目录")
    ap.add_argument("--clips-dir", default=None, help="每镜 clip 目录（默认 <project>/clips），文件名 <shot_id>.mp4")
    ap.add_argument("--out", default=None, help="输出 concat 列表路径（默认 <project>/concat.txt）")
    args = ap.parse_args()

    proj = os.path.abspath(args.project)
    storyboard = _load(os.path.join(proj, "storyboard.json"))
    if not storyboard:
        print(f"[error] 找不到 {proj}/storyboard.json", file=sys.stderr)
        return 2

    clips_dir = args.clips_dir or os.path.join(proj, "clips")
    out_path = args.out or os.path.join(proj, "concat.txt")

    shots = storyboard.get("shots", [])
    if not shots:
        print("[error] storyboard.json 无 shots", file=sys.stderr)
        return 2

    ar = storyboard.get("aspect_ratio", "16:9")
    platform = storyboard.get("platform", "bilibili")

    lines = []
    total = 0
    missing = []
    for s in shots:
        sid = s.get("shot_id", "?")
        dur = s.get("duration_s", 0)
        clip = os.path.join(clips_dir, f"{sid}.mp4")
        lines.append(f"file '{clip}'")
        lines.append(f"duration {dur}")
        total += dur
        if not os.path.exists(clip):
            missing.append(sid)
    # concat demuxer 末尾需重复最后一个 file 以保尾帧（部分 ffmpeg 版本要求）
    if shots:
        last = shots[-1].get("shot_id", "?")
        lines.append(f"file '{os.path.join(clips_dir, last + '.mp4')}'")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    # 拼接命令
    fps = 30
    audio = _load(os.path.join(proj, "audio_manifest.json"))
    if audio:
        audio_clip = os.path.join(proj, "audio.m4a")
        cmd = (f"ffmpeg -f concat -safe 0 -i \"{out_path}\" -i \"{audio_clip}\" "
               f"-c:v libx264 -c:a aac -r {fps} -pix_fmt yuv420p -movflags +faststart "
               f"-shortest output_{ar.replace(':', 'x')}.mp4")
    else:
        cmd = (f"ffmpeg -f concat -safe 0 -i \"{out_path}\" "
               f"-c:v libx264 -r {fps} -pix_fmt yuv420p -movflags +faststart "
               f"output_{ar.replace(':', 'x')}.mp4")

    print(f"[ok] 生成 concat 列表 → {out_path}（{len(shots)} 镜，总时长 {total}s，比例 {ar}，平台 {platform}）")
    if missing:
        print(f"     ⚠️ 以下 clip 尚未生成（请先由 S5 §二 各生成器产出）：{', '.join(missing)}")
    print(f"\n--- 拼接命令（复制执行）---\n{cmd}\n")
    print("提示：先确保 <clips-dir> 下每段 <shot_id>.mp4 已存在；音频见 audio_manifest.json（仅 CC0）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
