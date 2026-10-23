#!/usr/bin/env python3
"""make_layout_config.py -- 现成图模式：用户自带成品插画（无英文），直接生成排版配置并排版。

跳过「转录」和「重制插画」两个最耗时环节：英文原文由用户给出并已写进 course.json，
页图直接用用户的图，只补「英文精确排版」这一步（生图不写字、脚本排字的系列原则不变）。

用法（图片顺序 = 参数顺序，第一张必须是封面）：
    python make_layout_config.py <course_dir> <封面图> <页1图> <页2图> ...
    python make_layout_config.py <course_dir> ... --run          # 生成配置后直接排版
可选：
    --font-size 44        内页字号（封面固定 96 / min 60）
    --text-pos tl         内页文字位置 tl|tr|bl|br（默认 tl）
    --no-panel            内页文字不加底板（默认加）
    --out <dir>           排版输出目录（默认 <course_dir>/pages-5x4）

前置：course.json 已写好（title / sentences pageIndex 0 起 / words sentenceIndex）。
产出：
    _raw/src/00.<ext>…              图片副本（排版脚本从这里读，不碰原图）
    _raw/layout-config-cover.json   封面配置（标题大字，词色 orange/red 轮换）
    _raw/layout-config.json         内页配置（句子 + 生词高亮 red/green/blue 轮换）
然后（或加 --run 自动执行）：
    python <cards>/scripts/layout_pages.py -c <course>/_raw/layout-config-cover.json
    python <cards>/scripts/layout_pages.py -c <course>/_raw/layout-config.json

词图与此脚本无关；不带词图整本也能出课（build_course.py 全有或全无逻辑支持零词图）。
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

CARDS_LAYOUT_CANDIDATES = [
    os.environ.get("ECP_CARDS_LAYOUT", ""),
    os.path.expanduser("~/.workbuddy/skills/english-picturebook-cards/scripts/layout_pages.py"),
]

HL_COLORS = ["red", "green", "blue"]
TITLE_COLORS = ["orange", "red"]

COVER_CFG = {
    "font_size": 96, "min_font_size": 60, "line_spacing": 1.2,
    "margin": 48, "max_text_width": 1100,
    "panel": {"enabled": True, "fill": [255, 253, 248, 235],
              "outline": [240, 214, 170, 235], "radius": 28,
              "pad_x": 34, "pad_y": 26},
    "colors": {"default": [58, 58, 82, 255], "red": [226, 82, 62, 255],
               "orange": [232, 125, 44, 255]},
}
INNER_CFG = {
    "font_size": 44, "min_font_size": 30, "line_spacing": 1.32,
    "margin": 48, "max_text_width": 760,
    "panel": {"enabled": True, "fill": [255, 253, 248, 215],
              "outline": [240, 214, 170, 235], "radius": 28,
              "pad_x": 34, "pad_y": 26},
    "colors": {"default": [58, 58, 82, 255], "red": [226, 82, 62, 255],
               "green": [106, 148, 74, 255], "blue": [64, 120, 200, 255]},
}


def phrase_pattern(words, stem=False):
    """生词（含多词短语）的正则，忽略大小写、带词边界。

    stem=True 时每个 token 允许词形变化（sleep→sleeping、give up→gives up），
    仅在精确匹配失败后兜底使用。
    """
    alts = []
    for w in words:
        toks = [re.escape(t) for t in w.split()]
        if stem:
            toks = [t + r"\w*" for t in toks]
        alts.append(r"\s+".join(toks))
    alts.sort(key=len, reverse=True)
    return re.compile(r"\b(?:" + "|".join(alts) + r")\b", re.I)


def word_variants(text, highlights):
    """逐词决定用精确还是词干匹配（sleep→sleeping、give up→gives up）。

    返回 (精确命中的词, 仅词干命中的词, 精确和词干都找不到的词)。
    """
    exact, stems, missing = [], [], []
    for w in highlights:
        if phrase_pattern([w]).search(text):
            exact.append(w)
        elif phrase_pattern([w], stem=True).search(text):
            stems.append(w)
        else:
            missing.append(w)
    return exact, stems, missing


def combined_pattern(exact, stems):
    """精确词与词干词合并成一个交替正则，长词优先避免子串抢匹配。"""
    alts = [re.escape(w) for w in exact]
    for w in stems:
        toks = [re.escape(t) + r"\w*" for t in w.split()]
        alts.append(r"\s+".join(toks))
    alts.sort(key=len, reverse=True)
    return re.compile(r"\b(?:" + "|".join(alts) + r")\b", re.I)


def build_segments(text, highlights):
    """把句子拆成 [文本, 颜色] 段，生词按 HL_COLORS 轮换高亮。"""
    text = text.strip()
    if not highlights:
        return [[text, None]]
    exact, stems, _ = word_variants(text, highlights)
    if not exact and not stems:
        return [[text, None]]
    pat = combined_pattern(exact, stems)
    segs, pos, ci = [], 0, 0
    for m in pat.finditer(text):
        if m.start() > pos:
            segs.append([text[pos:m.start()], None])
        segs.append([m.group(), HL_COLORS[ci % len(HL_COLORS)]])
        ci += 1
        pos = m.end()
    if pos < len(text):
        segs.append([text[pos:], None])
    return segs or [[text, None]]


def title_segments(title):
    """标题词色轮换 orange/red（与已上线课程封面同款）。"""
    words = title.split()
    return [[w + (" " if i < len(words) - 1 else ""), TITLE_COLORS[i % 2]]
            for i, w in enumerate(words)] or [[title, "red"]]


def find_layout_script():
    for p in CARDS_LAYOUT_CANDIDATES:
        if p and os.path.isfile(p):
            return p
    sys.exit("ERROR: 找不到 layout_pages.py（english-picturebook-cards 未安装？"
             "可用环境变量 ECP_CARDS_LAYOUT 指定路径）")


def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("course_dir")
    ap.add_argument("images", nargs="+")
    ap.add_argument("--title")
    ap.add_argument("--font-size", type=int, default=44)
    ap.add_argument("--text-pos", default="tl", choices=["tl", "tr", "bl", "br"])
    ap.add_argument("--no-panel", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--run", action="store_true")
    a = ap.parse_args()

    course_file = os.path.join(a.course_dir, "course.json")
    if not os.path.isfile(course_file):
        sys.exit(f"ERROR: 没有 {course_file}，先写好 course.json 再跑本脚本")
    course = json.load(open(course_file, encoding="utf-8"))
    if len(a.images) < 2:
        sys.exit("ERROR: 至少给 2 张图（封面 + 1 内页）；顺序 = 参数顺序，第一张是封面")

    # 图片拷进 _raw/src/，顺序编号 00..
    src_dir = os.path.join(a.course_dir, "_raw", "src")
    os.makedirs(src_dir, exist_ok=True)
    copied = []
    for i, img in enumerate(a.images):
        if not os.path.isfile(img):
            sys.exit(f"ERROR: 图片不存在：{img}")
        dst = os.path.join(src_dir, "%02d%s" % (i, os.path.splitext(img)[1].lower()))
        shutil.copyfile(img, dst)
        copied.append("src/" + os.path.basename(dst))

    # 句子按页归组（pageIndex 0 = pages[0] = 第 2 张图）
    by_page = {}
    for idx, s in enumerate(course["sentences"]):
        by_page.setdefault(int(s.get("pageIndex", 0)), []).append((idx, s["en"]))
    # 生词按句子归组
    words_by_sent = {}
    for w in course.get("words", []):
        words_by_sent.setdefault(int(w.get("sentenceIndex", 0)), []).append(w["word"])

    out_dir = a.out or os.path.join(a.course_dir, "pages-5x4")
    raw_dir = os.path.join(a.course_dir, "_raw")
    cover_title = a.title or course.get("title", "")
    if not cover_title:
        sys.exit("ERROR: course.json 没有 title，也没给 --title，封面没字可排")

    # 封面配置（第 1 张图 = id 00）
    cover = dict(COVER_CFG, raw_dir=raw_dir, out_dir=out_dir,
                 target_size=[1280, 1024],
                 pages=[{"id": "00", "file": copied[0], "text_pos": "tl",
                         "segments": title_segments(cover_title)}])

    # 内页配置（第 2 张起 = id 01..，句子 pageIndex k-1）
    pages = []
    for k in range(1, len(copied)):
        sents = by_page.get(k - 1, [])
        if not sents:
            print(f"警告：pageIndex={k-1} 没有句子，页 {k} 不排文字")
            continue
        text = " ".join(en for _, en in sents)
        hl = [w for idx in (i for i, _ in sents) for w in words_by_sent.get(idx, [])]
        _, _, missing = word_variants(text, hl)
        for w in missing:
            print(f"提示：生词 “{w}” 不在 pageIndex={k-1} 的句子里（含词形变化也找不到），未高亮")
        pages.append({"id": "%02d" % k, "file": copied[k],
                      "text_pos": a.text_pos, "segments": build_segments(text, hl)})
    inner = dict(INNER_CFG, raw_dir=raw_dir, out_dir=out_dir,
                 target_size=[1280, 1024], pages=pages)
    if a.font_size != 44:
        inner["font_size"] = a.font_size
    if a.no_panel:
        inner["panel"] = dict(inner["panel"], enabled=False)

    cover_path = os.path.join(raw_dir, "layout-config-cover.json")
    inner_path = os.path.join(raw_dir, "layout-config.json")
    json.dump(cover, open(cover_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    json.dump(inner, open(inner_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"已生成：{cover_path}（封面标题）")
    print(f"        {inner_path}（{len(pages)} 内页，生词高亮）")

    cmds = [[sys.executable, find_layout_script(), "-c", cover_path],
            [sys.executable, find_layout_script(), "-c", inner_path]]
    if a.run:
        for cmd in cmds:
            r = subprocess.run(cmd)
            if r.returncode:
                sys.exit(r.returncode)
        made = sorted(f for f in os.listdir(out_dir) if f.endswith(".jpg")) if os.path.isdir(out_dir) else []
        print(f"排版完成：{out_dir}（{len(made)} 张）")
    else:
        print("\n下一步（或重跑本脚本加 --run）：")
        for cmd in cmds:
            print("  " + " ".join(cmd))


if __name__ == "__main__":
    main()
