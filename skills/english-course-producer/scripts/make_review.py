#!/usr/bin/env python3
"""生成单文件「线上绘本展示」HTML（english-course-producer skill）。

用法：python make_review.py <course_dir>

设计对齐 App 学习页（frontend/src/pages/material/*）：
- 桌面宽屏：左侧「学习选择」栏（封面 + 课程音频/重点词汇/跟读练习/语音问答），右侧内容区独立滚动
- 竖屏 / 窄屏：学习选择沉到底部，内容区占满
- 课程音频 / 跟读练习：图文卡纵向滚动，顶部「连续播放」串起全篇
- 重点词汇：九宫格铺开，点卡片听音
- 语音问答：一题一页，上一题 / 下一题

产物：<course_dir>/线上绘本展示.html（自包含：图片与音频全部 base64 内嵌）。
"""
import base64
import html
import io
import json
import os
import re
import sys
from string import Template

from PIL import Image

MODES = [
    ("audio", "课程音频", "🎧"),
    ("words", "重点词汇", "🃏"),
    ("read", "跟读练习", "🎙️"),
    ("quiz", "语音问答", "💬"),
]


def b64_audio(path):
    with open(path, "rb") as fh:
        return "data:audio/mpeg;base64," + base64.b64encode(fh.read()).decode()


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    course_dir = os.path.abspath(sys.argv[1])
    course = json.load(open(os.path.join(course_dir, "course.json"), encoding="utf-8"))
    manifest = json.load(open(os.path.join(course_dir, "manifest.json"), encoding="utf-8"))
    cfg = json.load(open(os.path.join(course_dir, "config.json"), encoding="utf-8"))
    result_path = os.path.join(course_dir, "upload-result.json")
    result = json.load(open(result_path, encoding="utf-8")) if os.path.isfile(result_path) else None
    pages_dir = cfg["pagesDir"]
    audio_dir = os.path.join(course_dir, "audio-%s" % manifest["voice"].split("_")[0].lower())
    words_dir = os.path.join(course_dir, "words")

    def img_data(name, width, base):
        im = Image.open(os.path.join(base, name)).convert("RGB")
        im.thumbnail((width, width), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=78)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()

    page_src = {name: img_data(name, 820, pages_dir) for name in dict.fromkeys([course["cover"]] + course["pages"])}
    cover_src = page_src[course["cover"]]

    audio = {}
    for item in manifest["sentences"]:
        audio[item["audio"]] = b64_audio(os.path.join(audio_dir, item["audio"]))
        audio[item["slow"]] = b64_audio(os.path.join(audio_dir, item["slow"]))
    for item in manifest["words"]:
        audio[item["audio"]] = b64_audio(os.path.join(audio_dir, item["audio"]))
    for item in manifest["quizzes"]:
        audio[item["questionAudio"]] = b64_audio(os.path.join(audio_dir, item["questionAudio"]))
        audio[item["answerAudio"]] = b64_audio(os.path.join(audio_dir, item["answerAudio"]))

    # ---- 句子高亮：把该句对应的生词包成 <em>（只标第一处）----
    key_by_sentence = {}
    for w in manifest["words"]:
        key_by_sentence.setdefault(w["sentenceIndex"], []).append(w["word"])

    def marked(en, idx):
        out = html.escape(en)
        for word in key_by_sentence.get(idx, []):
            pattern = re.compile(r"(?<![A-Za-z])" + re.escape(html.escape(word)) + r"(?![A-Za-z])", re.I)
            m = pattern.search(out)
            if m:
                out = out[: m.start()] + '<em>%s</em>' % m.group(0) + out[m.end():]
        return out

    # ---- 课程音频 ----
    sentence_cards = []
    for i, s in enumerate(manifest["sentences"]):
        sentence_cards.append(
            """      <article class="card" data-i="%(i)d" data-src="%(src)s">
        <div class="shot"><img src="%(img)s" alt="第 %(page)d 页" loading="lazy"><span class="no">%(no)02d</span></div>
        <p class="line">%(en)s</p>
        <p class="zh">%(zh)s</p>
        <div class="cue">
          <button class="spk primary" data-play="%(src)s"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9v6h4l5 4V5L8 9H4z"/><path class="w1" d="M16.5 8.5a5 5 0 0 1 0 7"/><path class="w2" d="M19 6a8.5 8.5 0 0 1 0 12"/></svg>听这句</button>
          <button class="spk" data-play="%(slow)s"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9v6h4l5 4V5L8 9H4z"/><path class="w1" d="M16.5 8.5a5 5 0 0 1 0 7"/></svg>慢速</button>
        </div>
      </article>"""
            % {
                "i": i,
                "src": s["audio"],
                "slow": s["slow"],
                "img": page_src[course["pages"][s["pageIndex"]]],
                "page": s["pageIndex"] + 1,
                "no": i + 1,
                "en": marked(s["en"], i),
                "zh": html.escape(s["zh"]),
            }
        )

    # ---- 词卡（九宫格）----
    word_cards = []
    for i, w in enumerate(manifest["words"]):
        fp = os.path.join(words_dir, "w%02d.jpg" % i)
        pic = '<img src="%s" alt="%s" loading="lazy">' % (img_data("w%02d.jpg" % i, 420, words_dir), html.escape(w["word"])) if os.path.isfile(fp) else '<div class="nopic">🎨</div>'
        word_cards.append(
            """      <button class="wcard" data-play="%(src)s">
        %(pic)s
        <div class="w">%(word)s</div>
        <div class="ph">%(ph)s</div>
        <div class="wzh">%(zh)s</div>
        <span class="wspk"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9v6h4l5 4V5L8 9H4z"/><path class="w1" d="M16.5 8.5a5 5 0 0 1 0 7"/><path class="w2" d="M19 6a8.5 8.5 0 0 1 0 12"/></svg>点我听</span>
      </button>"""
            % {
                "src": w["audio"],
                "pic": pic,
                "word": html.escape(w["word"]),
                "ph": html.escape(w["phonetic"]),
                "zh": html.escape(w["zh"]),
            }
        )

    # ---- 跟读练习：同音频布局，换按钮文案 ----
    read_cards = []
    for i, s in enumerate(manifest["sentences"]):
        read_cards.append(
            """      <article class="card">
        <div class="shot"><img src="%(img)s" alt="第 %(page)d 页" loading="lazy"><span class="no">%(no)02d</span></div>
        <p class="line">%(en)s</p>
        <p class="zh">%(zh)s</p>
        <div class="cue">
          <button class="spk primary" data-play="%(src)s"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9v6h4l5 4V5L8 9H4z"/><path class="w1" d="M16.5 8.5a5 5 0 0 1 0 7"/><path class="w2" d="M19 6a8.5 8.5 0 0 1 0 12"/></svg>听示范</button>
          <button class="spk" data-play="%(slow)s"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9v6h4l5 4V5L8 9H4z"/><path class="w1" d="M16.5 8.5a5 5 0 0 1 0 7"/></svg>慢慢听</button>
          <span class="chip-inline">🎤 在 App 里可以录下自己的声音</span>
        </div>
      </article>"""
            % {
                "img": page_src[course["pages"][s["pageIndex"]]],
                "page": s["pageIndex"] + 1,
                "no": i + 1,
                "en": marked(s["en"], i),
                "zh": html.escape(s["zh"]),
                "src": s["audio"],
                "slow": s["slow"],
            }
        )

    # ---- 语音问答 ----
    quiz_data = []
    for i, q in enumerate(manifest["quizzes"]):
        s = manifest["sentences"][q["sentenceIndex"]]
        quiz_data.append(
            {
                "q": q["question"],
                "qzh": q["questionZh"],
                "a": q["answer"],
                "img": page_src[course["pages"][s["pageIndex"]]],
                "page": s["pageIndex"] + 1,
                "qa": q["questionAudio"],
                "aa": q["answerAudio"],
            }
        )

    total_audio = sum(len(v) for v in manifest["audio"].values())
    chips = [
        "音色 %s" % manifest["voice"],
        "语速 %s · 慢速 %s" % (manifest["speed"]["normal"], manifest["speed"]["slow"]),
        "%d 句 · %d 词 · %d 题" % (len(manifest["sentences"]), len(manifest["words"]), len(manifest["quizzes"])),
        "音频 %d 条" % total_audio,
    ]
    if result:
        chips.append("课号 " + result["id"][:8])
        chips.append("待审核")
    else:
        chips.append("未上传")

    mode_btns = "".join(
        """        <button class="mode %s" data-mode="%s"><span class="ico">%s</span><span class="mode-t">%s</span><i class="tick">✓</i></button>\n"""
        % (mid, mid, ico, label)
        for mid, label, ico in MODES
    )

    payload = json.dumps(
        {
            "audio": audio,
            "quizzes": quiz_data,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )

    tpl = Template(
        r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>$title · 线上绘本展示</title>
<style>
  :root{
    color-scheme:light;
    --blue:#4A9BFF;--blue-d:#2F6FE0;--amber:#FFB020;--amber-d:#E88A0B;
    --green:#7CD44B;--green-d:#45A81F;--ink:#2B3A55;--ink-2:#66748C;--ink-3:#9AA7BC;
    --line:#E4EEF9;--red:#FF6B5B;--r-card:26px;
  }
  *{box-sizing:border-box}
  html,body{height:100%;margin:0}
  body{
    font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Helvetica Neue",Arial,sans-serif;
    color:var(--ink);font-size:15px;line-height:1.55;-webkit-font-smoothing:antialiased;
    background:linear-gradient(180deg,#bfe4fb 0%,#e7f4fd 46%,#f7fbfe 100%) fixed;
  }
  button{font-family:inherit}
  .app{max-width:1200px;margin:0 auto;height:100dvh;display:flex;gap:22px;padding:24px 20px 28px}

  /* ---------- 左栏：学习选择 ---------- */
  .rail{width:262px;flex:none;display:flex;flex-direction:column;gap:14px;align-self:flex-start;position:sticky;top:0;max-height:calc(100dvh - 52px);overflow:auto;padding-bottom:4px}
  .rail-title{font-size:21px;font-weight:800;color:#24385c;letter-spacing:.5px;padding-left:2px}
  .cover{position:relative;height:150px;border-radius:22px;overflow:hidden;background:#d9ebf8;box-shadow:0 10px 24px rgba(80,140,190,.16)}
  .cover img{width:100%;height:100%;object-fit:cover;display:block}
  .cover-name{position:absolute;left:0;right:0;bottom:0;padding:26px 12px 10px;color:#fff;font-size:16px;font-weight:800;
    background:linear-gradient(180deg,rgba(20,40,70,0),rgba(20,40,70,.62));white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .modes{display:flex;flex-direction:column;gap:12px}
  .mode{position:relative;display:flex;align-items:center;gap:12px;min-height:70px;padding:0 46px 0 14px;
    border:3px solid transparent;border-radius:20px;background:#fff;box-shadow:0 8px 18px rgba(90,140,190,.1);
    cursor:pointer;transition:transform .16s ease,background .16s ease,border-color .16s ease;text-align:left}
  .mode:hover{transform:translateY(-1px)}
  .mode .ico{width:42px;height:42px;flex:none;border-radius:14px;display:grid;place-items:center;font-size:21px;background:#f4f8fc}
  .mode-t{font-size:16px;font-weight:800;color:#24385c}
  .mode .tick{position:absolute;right:14px;top:50%;transform:translateY(-50%) scale(.6);opacity:0;
    width:20px;height:20px;border-radius:50%;color:#fff;font-size:11px;font-style:normal;font-weight:800;display:grid;place-items:center;
    transition:opacity .16s ease,transform .16s ease}
  .mode.audio .tick{background:#3ecf8e}.mode.words .tick{background:#f0a04a}
  .mode.read .tick{background:#f0b429}.mode.quiz .tick{background:#5aa2f0}
  .mode.audio{background:#eefaf3}.mode.words{background:#fff7ee}
  .mode.read{background:#fffaee}.mode.quiz{background:#eff6ff}
  .mode.on{background:#fff}
  .mode.on .tick{opacity:1;transform:translateY(-50%) scale(1)}
  .mode.on.audio{border-color:#3ecf8e;background:#e5f8ec}
  .mode.on.words{border-color:#f0a04a;background:#fff1df}
  .mode.on.read{border-color:#f0c14a;background:#fff6dc}
  .mode.on.quiz{border-color:#7eb6f0;background:#e8f3ff}
  .meta{display:flex;flex-wrap:wrap;gap:6px;padding-top:2px}
  .chip{background:rgba(255,255,255,.78);border:1px solid #dfeaf7;border-radius:999px;padding:3px 10px;
    font-size:11.5px;font-weight:700;color:#6f86a3;line-height:1.6}

  /* ---------- 右栏：内容 ---------- */
  .stage{flex:1;min-width:0;min-height:0;display:flex;flex-direction:column}
  .head{flex:none;display:flex;align-items:center;gap:10px;padding:2px 4px 12px}
  .head-txt{min-width:0}
  .head-t{font-size:23px;font-weight:800;color:#24385c;letter-spacing:.3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .head-s{font-size:13px;font-weight:700;color:#7d92ab;margin-top:2px}
  .head-cover{width:46px;height:46px;border-radius:14px;overflow:hidden;margin-left:auto;flex:none;box-shadow:0 6px 14px rgba(80,140,190,.18)}
  .head-cover img{width:100%;height:100%;object-fit:cover;display:block}
  .stage-body{flex:1;min-height:0;overflow:auto;padding:0 6px 24px 2px;scroll-behavior:smooth;overscroll-behavior:contain;
    scrollbar-width:thin;scrollbar-color:#c9dcef transparent}
  .stage-body::-webkit-scrollbar{width:9px}
  .stage-body::-webkit-scrollbar-thumb{background:#c9dcef;border-radius:9px;border:2px solid transparent;background-clip:content-box}

  .pane{display:none}
  .pane.on{display:block;animation:fade .22s ease}
  @keyframes fade{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}

  /* 顶部工具条（贴住滚动区顶部） */
  .toolbar{position:sticky;top:0;z-index:6;display:flex;align-items:center;gap:12px;padding:8px 2px 14px;
    background:linear-gradient(180deg,rgba(231,244,253,.98) 0%,rgba(231,244,253,.9) 62%,rgba(231,244,253,0) 100%)}
  .chain{display:inline-flex;align-items:center;gap:9px;height:48px;padding:0 22px;border:none;border-radius:24px;
    background:linear-gradient(180deg,#FFE07A,#F0A020);box-shadow:0 8px 16px rgba(240,160,40,.34);
    color:#fff;font-size:16px;font-weight:800;letter-spacing:.5px;cursor:pointer;transition:transform .14s ease,box-shadow .14s ease}
  .chain:active{transform:translateY(2px)}
  .chain.on{background:linear-gradient(180deg,#8BE07A,#3EC45A);box-shadow:0 8px 16px rgba(50,180,80,.32)}
  .chain svg{width:19px;height:19px;fill:currentColor}
  .prog{font-size:13px;font-weight:800;color:#6f86a3;letter-spacing:.4px}
  .prog b{color:#24385c}

  /* 图文卡 */
  .card{position:relative;background:#fff;border-radius:28px;padding:14px 16px 20px;margin-bottom:18px;
    box-shadow:0 12px 30px rgba(74,130,200,.12);transition:box-shadow .2s ease,transform .2s ease}
  .card.active{box-shadow:0 0 0 3px rgba(74,155,255,.4),0 16px 34px rgba(74,130,200,.2)}
  .shot{position:relative;border-radius:22px;overflow:hidden;background:#eef6fd}
  .shot img{width:100%;display:block}
  .no{position:absolute;left:10px;top:10px;height:26px;min-width:34px;padding:0 9px;border-radius:13px;
    background:rgba(255,255,255,.9);color:#4d6584;font-size:12.5px;font-weight:800;display:grid;place-items:center;
    box-shadow:0 4px 10px rgba(60,110,160,.16)}
  .line{max-width:740px;margin:16px auto 0;font-size:25px;font-weight:900;line-height:1.42;text-align:center;color:#24385c;overflow-wrap:anywhere}
  .line em{font-style:normal;color:#E8891A;background:linear-gradient(180deg,transparent 66%,#FFE9C4 66%);border-radius:3px;padding:0 2px}
  .zh{max-width:700px;margin:7px auto 0;text-align:center;color:#7d92ab;font-size:15px;font-weight:700}
  .cue{display:flex;align-items:center;justify-content:center;gap:12px;flex-wrap:wrap;margin-top:16px}
  .spk{display:inline-flex;align-items:center;gap:8px;height:46px;padding:0 20px;border:none;border-radius:23px;
    background:#f4f8fc;color:#4d6584;font-size:15px;font-weight:800;cursor:pointer;transition:background .14s ease,transform .14s ease}
  .spk:active{transform:translateY(2px)}
  .spk svg{width:19px;height:19px;fill:currentColor}
  .spk svg .w1,.spk svg .w2{fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round}
  .spk.primary{background:linear-gradient(180deg,#8BC4FF,#3B7BE8);color:#fff;box-shadow:0 8px 16px rgba(59,123,232,.28)}
  .spk.on{background:linear-gradient(180deg,#7CBBFF,#2F6FE0);color:#fff;box-shadow:0 8px 16px rgba(47,111,224,.32)}
  .chip-inline{font-size:12.5px;font-weight:700;color:#9AA7BC}

  /* 九宫格词卡 */
  .wgrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
  .wcard{display:flex;flex-direction:column;background:#fff;border:none;border-radius:24px;padding:12px 12px 14px;
    box-shadow:0 10px 24px rgba(74,130,200,.1);cursor:pointer;transition:transform .16s ease,box-shadow .16s ease;text-align:center}
  .wcard:hover{transform:translateY(-3px);box-shadow:0 16px 30px rgba(74,130,200,.16)}
  .wcard.on{box-shadow:0 0 0 3px rgba(255,176,32,.55),0 16px 30px rgba(74,130,200,.16)}
  .wcard img,.wcard .nopic{width:100%;aspect-ratio:6/5;object-fit:cover;border-radius:16px;display:block;background:#f4f8fc}
  .wcard .nopic{display:grid;place-items:center;font-size:44px}
  .wcard .w{font-size:21px;font-weight:900;color:#24385c;margin-top:10px;letter-spacing:-.2px}
  .wcard .ph{font-size:12px;font-weight:700;color:#9AA7BC;margin-top:1px}
  .wcard .wzh{font-size:13.5px;font-weight:700;color:#66748C;margin-top:3px}
  .wspk{display:inline-flex;align-items:center;gap:6px;align-self:center;margin-top:10px;height:34px;padding:0 13px;
    border-radius:17px;background:#f4f8fc;color:#4d6584;font-size:12.5px;font-weight:800}
  .wspk svg{width:15px;height:15px;fill:currentColor}
  .wspk svg .w1,.wspk svg .w2{fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round}
  .wcard.on .wspk{background:#fff1d6;color:#C4882A}

  /* 语音问答 */
  .qwrap{max-width:760px;margin:0 auto}
  .count{text-align:center;color:#5e7594;font-size:14px;font-weight:800;margin:0 0 10px}
  .board-q{background:#fff;border-radius:28px;padding:14px 16px 22px;box-shadow:0 12px 30px rgba(74,130,200,.12)}
  .board-q .line{margin-top:18px}
  .ask{font-size:25px}
  .sub-note{text-align:center;color:#9AA7BC;font-size:13.5px;font-weight:700;margin-top:6px}
  .hint{display:flex;align-items:center;justify-content:center;margin:14px auto 0;height:44px;padding:0 18px;
    border:none;border-radius:22px;background:#fff6e4;color:#C4882A;font-size:14.5px;font-weight:800;cursor:pointer}
  .answer{display:none;text-align:center;margin-top:10px;color:#2F6FE0;font-size:20px;font-weight:800}
  .answer.on{display:block;animation:fade .18s ease}
  .qactions{display:flex;justify-content:center;gap:26px;margin-top:18px}
  .act{display:flex;flex-direction:column;align-items:center;gap:8px;color:#3e5678;font-size:14px;font-weight:800;
    border:none;background:none;cursor:pointer}
  .sq{width:80px;height:80px;border-radius:26px;display:grid;place-items:center;color:#fff}
  .sq svg{width:30px;height:30px;fill:currentColor}
  .sq.y{background:linear-gradient(180deg,#FFD36A,#F5A623);box-shadow:0 8px 16px rgba(240,160,30,.3)}
  .sq.g{background:linear-gradient(180deg,#7BE07A,#3EC45A);box-shadow:0 8px 16px rgba(50,180,80,.28)}
  .act.on .sq.y{background:linear-gradient(180deg,#8BC4FF,#2F6FE0);box-shadow:0 8px 16px rgba(47,111,224,.3)}
  .cloud{display:flex;justify-content:center;gap:14px;margin-top:16px;padding:14px;border-radius:32px;background:#fff;
    box-shadow:0 12px 28px rgba(80,140,200,.14)}
  .ghost{min-width:118px;height:50px;border:none;border-radius:25px;background:#f4f8fc;color:#4d6584;
    font-size:15px;font-weight:800;cursor:pointer;transition:transform .14s ease}
  .ghost:active{transform:translateY(2px)}
  .ghost:disabled{color:#C5D0DE;cursor:default;transform:none}

  footer{max-width:760px;margin:26px auto 6px;color:#93A6BE;font-size:12.5px;line-height:1.9;text-align:center}
  footer b{color:#5E7594}

  /* ---------- 竖屏 / 窄屏：学习选择沉底 ---------- */
  @media (max-width:959px){
    .app{flex-direction:column;height:100dvh;padding:0;gap:0}
    .stage{order:1;padding:12px 14px 0;min-height:0}
    .head{padding-bottom:8px}
    .head-t{font-size:19px}
    .head-cover,.cover,.rail-title,.meta{display:none}
    .rail{order:2;width:100%;position:static;max-height:none;overflow:visible;padding:10px 12px calc(10px + env(safe-area-inset-bottom));
      background:rgba(255,255,255,.92);box-shadow:0 -8px 24px rgba(80,140,190,.12);border-radius:22px 22px 0 0;display:block}
    .modes{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}
    .mode{min-width:0;min-height:74px;padding:8px 2px;flex-direction:column;justify-content:center;gap:5px;text-align:center}
    .mode .ico{width:32px;height:32px;font-size:17px;background:transparent}
    .mode-t{font-size:11.5px;line-height:1.25}
    .mode .tick{top:6px;right:6px;transform:none;width:16px;height:16px;font-size:10px}
    .mode.on .tick{transform:none}
    .line{font-size:21px}
    .wgrid{grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
    .wcard .w{font-size:18px}
    .toolbar{padding-top:2px}
    .chain{height:44px;padding:0 18px;font-size:15px}
    .sq{width:70px;height:70px;border-radius:22px}
  }
  @media (max-width:430px){
    .wgrid{grid-template-columns:repeat(2,minmax(0,1fr))}
    .line{font-size:19px}
  }
</style>
</head>
<body>
<div class="app">
  <aside class="rail">
    <div class="rail-title">学习选择</div>
    <div class="cover">
      <img src="$cover" alt="$title">
      <div class="cover-name">$titleZh</div>
    </div>
    <div class="modes">
$modes
    </div>
    <div class="meta">$chips</div>
  </aside>

  <main class="stage">
    <div class="head">
      <div class="head-txt">
        <div class="head-t">$title</div>
        <div class="head-s">$titleZh · 线上绘本展示</div>
      </div>
      <div class="head-cover"><img src="$cover" alt=""></div>
    </div>

    <div class="stage-body" id="body">
      <section class="pane on" data-pane="audio">
        <div class="toolbar">
          <button class="chain" id="chainBtn"><svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg><span id="chainTxt">连续播放</span></button>
          <span class="prog" id="prog">第 <b>1</b> / $scount 句</span>
        </div>
$sentences
      </section>

      <section class="pane" data-pane="words">
        <div class="toolbar"><span class="prog">本课 <b>$wcount</b> 个重点词 · 点卡片听发音</span></div>
        <div class="wgrid">
$words
        </div>
      </section>

      <section class="pane" data-pane="read">
        <div class="toolbar"><span class="prog">听一遍示范，再跟着读 · 共 <b>$scount</b> 句</span></div>
$reads
      </section>

      <section class="pane" data-pane="quiz">
        <div class="qwrap">
          <div class="count" id="qcount"></div>
          <div class="board-q">
            <div class="shot"><img id="qimg" alt=""><span class="no" id="qno"></span></div>
            <p class="line ask" id="qtext"></p>
            <p class="sub-note" id="qzh"></p>
            <button class="hint" id="qHint">不会答？点我听答案</button>
            <div class="answer" id="qans"></div>
          </div>
          <div class="qactions">
            <button class="act" id="qPlay"><span class="sq y"><svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg></span>播放问题</button>
          </div>
          <div class="cloud">
            <button class="ghost" id="qPrev">‹ 上一题</button>
            <button class="ghost" id="qNext">下一题 ›</button>
          </div>
        </div>
      </section>

      <footer>
        本页为 <b>$title</b> 的线上展示，图片与音频已全部内嵌，双击即可离线浏览。<br>
        $footnote
      </footer>
    </div>
  </main>
</div>

<script>
const DATA = $payload;
const player = new Audio();
player.preload = "none";
let curBtn = null, chainOn = false, chainAt = 0, chainList = [];

function resetBtn() {
  if (!curBtn) return;
  curBtn.classList.remove("on");
  const t = curBtn.querySelector(".txt");
  curBtn = null;
}
function stopAll() {
  player.pause();
  player.currentTime = 0;
  resetBtn();
}
function playFile(src, btn) {
  if (!src || !DATA.audio[src]) return;
  if (curBtn === btn && !player.paused) { stopAll(); return; }
  stopAll();
  chainOn = false; setChain(false);
  player.src = DATA.audio[src];
  player.play().catch(function () {});
  if (btn) { btn.classList.add("on"); curBtn = btn; }
}

/* 一键播放：所有 .spk / .wcard 按钮 */
document.addEventListener("click", function (e) {
  const b = e.target.closest("[data-play]");
  if (!b) return;
  const isCard = b.classList.contains("wcard");
  const card = b.closest(".card");
  if (card) { clearActive(); card.classList.add("active"); }
  playFile(b.getAttribute("data-play"), b);
  if (isCard) { document.querySelectorAll(".wcard.on").forEach(function (n) { if (n !== b) n.classList.remove("on"); }); }
});

/* ---------- 连续播放 ---------- */
const chainBtn = document.getElementById("chainBtn");
const chainTxt = document.getElementById("chainTxt");
const prog = document.getElementById("prog");
const cards = Array.prototype.slice.call(document.querySelectorAll('[data-pane="audio"] .card'));

function clearActive() { cards.forEach(function (c) { c.classList.remove("active"); }); }
function setChain(on) {
  chainOn = on;
  chainBtn.classList.toggle("on", on);
  chainTxt.textContent = on ? "暂停连续播放" : "连续播放";
  chainBtn.querySelector("svg").innerHTML = on ? '<path d="M7 5h4v14H7zM13 5h4v14h-4z"/>' : '<path d="M8 5v14l11-7z"/>';
}
function focusCard(n) {
  clearActive();
  const c = cards[n];
  if (!c) return;
  c.classList.add("active");
  c.scrollIntoView({ behavior: "smooth", block: "center" });
  prog.innerHTML = "第 <b>" + (n + 1) + "</b> / " + cards.length + " 句";
}
function playChainAt(n) {
  if (n >= chainList.length) { setChain(false); stopAll(); return; }
  chainAt = n;
  focusCard(n);
  player.src = chainList[n];
  player.play().catch(function () {});
}
player.addEventListener("ended", function () {
  if (!chainOn) { resetBtn(); return; }
  playChainAt(chainAt + 1);
});
chainBtn.addEventListener("click", function () {
  if (chainOn) { setChain(false); stopAll(); return; }
  chainList = cards.map(function (c) { return DATA.audio[c.getAttribute("data-src")]; });
  const from = cards.findIndex(function (c) { return c.classList.contains("active"); });
  setChain(true);
  playChainAt(from < 0 ? 0 : from);
});

/* ---------- 模式切换 ---------- */
const modeBtns = Array.prototype.slice.call(document.querySelectorAll(".mode"));
modeBtns.forEach(function (btn) {
  btn.addEventListener("click", function () {
    const id = btn.getAttribute("data-mode");
    modeBtns.forEach(function (b) { b.classList.toggle("on", b === btn); });
    document.querySelectorAll(".pane").forEach(function (p) { p.classList.toggle("on", p.getAttribute("data-pane") === id); });
    stopAll(); setChain(false);
    document.getElementById("body").scrollTop = 0;
  });
});

/* ---------- 语音问答 ---------- */
const Q = DATA.quizzes;
let qi = 0;
const qimg = document.getElementById("qimg"), qno = document.getElementById("qno"),
      qtext = document.getElementById("qtext"), qzh = document.getElementById("qzh"),
      qans = document.getElementById("qans"), qcount = document.getElementById("qcount"),
      qPrev = document.getElementById("qPrev"), qNext = document.getElementById("qNext"),
      qHint = document.getElementById("qHint"), qPlay = document.getElementById("qPlay");

function renderQ() {
  const q = Q[qi];
  if (!q) return;
  qimg.src = q.img;
  qno.textContent = "#" + (qi + 1);
  qtext.textContent = q.q;
  qzh.textContent = "引导：" + q.qzh;
  qans.textContent = "答：" + q.a;
  qans.classList.remove("on");
  qHint.textContent = "不会答？点我听答案";
  qcount.textContent = "第 " + (qi + 1) + " 题，共 " + Q.length + " 题";
  qPrev.disabled = qi === 0;
  qNext.disabled = qi === Q.length - 1;
}
qPrev.addEventListener("click", function () { if (qi > 0) { stopAll(); qi--; renderQ(); } });
qNext.addEventListener("click", function () { if (qi < Q.length - 1) { stopAll(); qi++; renderQ(); } });
qHint.addEventListener("click", function () {
  qans.classList.add("on");
  qHint.textContent = "答案已显示，再听一遍";
  playFile(Q[qi].aa, null);
});
qPlay.addEventListener("click", function () {
  playFile(Q[qi].qa, null);
  qPlay.classList.toggle("on", !!curBtn);
});
renderQ();
document.querySelector('.mode[data-mode="audio"]').classList.add("on");
setChain(false);
</script>
</body>
</html>
"""
    )

    html_out = tpl.substitute(
        title=html.escape(course["title"]),
        titleZh=html.escape(course.get("titleZh", "")),
        cover=cover_src,
        modes=mode_btns,
        chips="".join('<span class="chip">%s</span>' % html.escape(c) for c in chips),
        sentences="\n".join(sentence_cards),
        words="\n".join(word_cards),
        reads="\n".join(read_cards),
        scount=len(manifest["sentences"]),
        wcount=len(manifest["words"]),
        payload=payload,
        footnote=(
            "已入库：课号 %s（待作者审核，通过后学习者可见）。" % result["id"]
            if result
            else "本稿尚未上传：外部使用者到此为止；作者本机执行 build_course.py --upload 才入库。"
        )
        + "<br>音频由火山 %s 本地合成，音色与 App 内一致。" % manifest["voice"],
    )

    out = os.path.join(course_dir, "线上绘本展示.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html_out)
    print("已生成 %s  %.2f MB" % (out, os.path.getsize(out) / 1024 / 1024))


if __name__ == "__main__":
    main()
