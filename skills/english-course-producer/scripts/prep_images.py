#!/usr/bin/env python3
"""图片预处理：词图裁 6:5、页图补 5:4、封面裁 5:4。一次一批，不再手写 heredoc。

用法：
    prep_images.py words  <out_dir> <img1> <img2> ...   # 居中裁 6:5 → 1229x1024，输出 w00.jpg…
    prep_images.py pages  <out_dir> <img1> <img2> ...   # 白边补 5:4 → 1280x1024，输出 01.jpg…
    prep_images.py pages  <out_dir> <img> --crop        # 居中裁 5:4（封面用，1280x1024）

约定：
- **图片顺序 = 参数顺序**，绝不靠文件名排序（生图文件名带时间戳，顺序=生成顺序，不是页序）。
- 词图数量必须与 course.json 的 words 数量一致，否则 build_course.py 预检会拦。
- 质量：词图 q86、页图 q88；单图目标 ≤2MB（服务端上限 4MB）。
"""
import os
import sys

from PIL import Image

WORD_SIZE = (1229, 1024)   # 6:5
PAGE_SIZE = (1280, 1024)   # 5:4


def crop_to(im, target_w, target_h):
    """居中裁到目标比例（不缩放），用于 6:5 词图 / 封面。"""
    w, h = im.size
    target_ratio = target_w / target_h
    if w / h > target_ratio:            # 太宽 → 裁左右
        cw = round(h * target_ratio)
        x = (w - cw) // 2
        im = im.crop((x, 0, x + cw, h))
    elif w / h < target_ratio:          # 太高 → 裁上下
        ch = round(w / target_ratio)
        y = (h - ch) // 2
        im = im.crop((0, y, w, y + ch))
    return im.resize((target_w, target_h), Image.LANCZOS)


def pad_to(im, target_w, target_h, bg=(255, 255, 255)):
    """等比缩放到目标框内，白边居中补满（不裁画面）。"""
    im = im.copy()
    im.thumbnail((target_w, target_h), Image.LANCZOS)
    canvas = Image.new("RGB", (target_w, target_h), bg)
    canvas.paste(im, ((target_w - im.width) // 2, (target_h - im.height) // 2))
    return canvas


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    if len(args) < 3 or args[0] not in ("words", "pages"):
        print(__doc__)
        sys.exit(2)
    mode, out_dir, inputs = args[0], args[1], args[2:]
    crop = "--crop" in flags
    os.makedirs(out_dir, exist_ok=True)

    for i, src in enumerate(inputs):
        im = Image.open(src).convert("RGB")
        if mode == "words":
            im = crop_to(im, *WORD_SIZE)
            name, quality = f"w{i:02d}.jpg", 86
        else:
            if crop:
                im = crop_to(im, *PAGE_SIZE)
            else:
                im = pad_to(im, *PAGE_SIZE)
            name, quality = f"{i + 1:02d}.jpg", 88
        out = os.path.join(out_dir, name)
        im.save(out, "JPEG", quality=quality)
        kb = os.path.getsize(out) // 1024
        flag = "  ⚠️ >2MB" if kb > 2048 else ""
        print(f"{name}  {im.size[0]}x{im.size[1]}  {kb}KB{flag}  <- {os.path.basename(src)}")

    print(f"\n共 {len(inputs)} 张 → {out_dir}")


if __name__ == "__main__":
    main()
