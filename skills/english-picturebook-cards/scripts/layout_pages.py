#!/usr/bin/env python3
"""layout_pages.py -- Crop raw illustrations to a fixed ratio and overlay
English story text with rounded-panel typography.

Part of the `english-picturebook-cards` skill.

Two-stage design: image generation NEVER renders text (models misspell),
text is always composited here so spelling is guaranteed correct and the
wording can be revised without regenerating images.

Usage:
    python layout_pages.py -c config.json
    python layout_pages.py -c config.json --dry-run     # layout math only

Config schema (JSON, UTF-8):
{
  "raw_dir":  "/abs/path/to/raw/images",
  "out_dir":  "/abs/path/to/output",
  "target_size": [1280, 1024],          // final size, e.g. 5:4
  "font_path": "/System/Library/Fonts/ChalkboardSE.ttc",   // optional
  "font_size": 44,
  "min_font_size": 30,                  // auto-shrink floor
  "line_spacing": 1.32,
  "margin": 48,                         // distance from canvas edge
  "max_text_width": 760,                // max width of the text column
  "panel": {
    "enabled": true,
    "fill":    [255, 253, 248, 215],
    "outline": [240, 214, 170, 235],
    "radius": 28,
    "pad_x": 34,
    "pad_y": 26
  },
  "colors": {                            // rgba; "default" is required
    "default": [58, 58, 82, 255],
    "red":   [226, 82, 62, 255],
    "green": [106, 148, 74, 255],
    "blue":  [64, 120, 200, 255]
  },
  "pages": [
    {
      "id": "02",                        // output file name stem -> 02.jpg
      "file": "raw-page.png",            // file inside raw_dir
      "text_pos": "tl",                  // tl | tr | bl | br
      "trim_left": 0,                    // px trimmed from left (width-crop);
                                         //   omit -> centered
      "trim_top": 0,                     // px trimmed from top  (height-crop)
      "no_panel": false,                 // optional: text without panel
      "segments": [                      // ordered text runs
        ["Mother rabbit goes to the ", null],
        ["market", "red"],               // null -> colors.default
        [" and leaves three little rabbits at home.", null]
      ]
    }
  ]
}

Exit codes: 0 ok, 1 config/runtime error, 2 missing dependency.
"""

import argparse
import json
import os
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("ERROR: Pillow is required. Install it into the managed venv:\n"
          "  <managed-python> -m venv ~/.workbuddy/binaries/python/envs/default\n"
          "  ~/.workbuddy/binaries/python/envs/default/bin/pip install Pillow",
          file=sys.stderr)
    sys.exit(2)

_WINFONTS = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
FONT_CANDIDATES = [
    "/System/Library/Fonts/ChalkboardSE.ttc",
    "/System/Library/Fonts/Supplemental/Chalkboard.ttc",
    "/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf",
    "/System/Library/Fonts/Supplemental/Comic Sans MS.ttf",
    os.path.join(_WINFONTS, "comicbd.ttf"),
    os.path.join(_WINFONTS, "seguibl.ttf"),
    os.path.join(_WINFONTS, "arialbd.ttf"),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def pick_font(cfg, explicit):
    if explicit:
        return explicit
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    raise SystemExit("ERROR: no usable font found; set font_path in the config "
                     "(Windows: C:\\Windows\\Fonts\\comicbd.ttf, macOS: ChalkboardSE.ttc).")


def load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception as exc:  # noqa: BLE001 - surface font problems clearly
        raise SystemExit(f"ERROR: cannot load font {path}: {exc}") from exc


def tokenize(segments):
    """Split coloured text runs into word tokens, keeping trailing spaces.

    Tokenising first means a highlighted word can never be broken across
    a line, and the trailing space keeps the visual gap correct.
    """
    tokens = []
    for text, color in segments:
        parts = text.split(" ")
        for i, part in enumerate(parts):
            if part == "" and 0 < i < len(parts) - 1:
                continue
            tok = part + (" " if i < len(parts) - 1 else "")
            if tok:
                tokens.append((tok, color))
    return tokens


def wrap(tokens, font, max_w, draw):
    lines, line, width = [], [], 0.0
    for tok, color in tokens:
        w = draw.textlength(tok, font=font)
        if line and width + w > max_w:
            lines.append(line)
            line, width = [], 0.0
        line.append((tok, color))
        width += w
    if line:
        lines.append(line)
    return lines


def fit_font(tokens, path, cfg, draw):
    """Auto-shrink so the longest single word fits the text column."""
    size = int(cfg.get("font_size", 44))
    floor = int(cfg.get("min_font_size", 30))
    max_w = cfg["max_text_width"]
    while size > floor:
        font = load_font(path, size)
        longest = max(draw.textlength(t, font=font) for t, _ in tokens)
        if longest <= max_w:
            return font, size
        size -= 2
    return load_font(path, floor), floor


def crop_to_ratio(img, target, page):
    """Trim the raw image to the target ratio.

    `trim_left` / `trim_top` give the pixels removed from that edge; both
    keys also accept the short forms `left` / `top`. Omit for centred trim.
    """
    tw, th = target
    want = tw / th
    got = img.width / img.height
    if got > want:  # too wide -> trim width
        cut = img.width - round(img.height * want)
        left = page.get("trim_left", page.get("left", cut // 2))
        top = 0
    elif got < want:  # too tall -> trim height
        cut = img.height - round(img.width / want)
        top = page.get("trim_top", page.get("top", cut // 2))
        left = 0
    else:
        return img
    return img.crop((left, top, left + tw, top + th))


def draw_page(page, cfg, font_path):
    raw = Image.open(os.path.join(cfg["raw_dir"], page["file"])).convert("RGB")
    img = crop_to_ratio(raw, tuple(cfg["target_size"]), page)
    if img.size != tuple(cfg["target_size"]):
        img = img.resize(tuple(cfg["target_size"]), Image.LANCZOS)

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    tokens = tokenize([tuple(s) for s in page["segments"]])
    font, size = fit_font(tokens, font_path, cfg, od)
    line_h = int(size * cfg.get("line_spacing", 1.32))
    lines = wrap(tokens, font, cfg["max_text_width"], od)

    panel = cfg.get("panel", {})
    pad_x = int(panel.get("pad_x", 34))
    pad_y = int(panel.get("pad_y", 26))
    text_w = max(sum(od.textlength(t, font=font) for t, _ in ln) for ln in lines)
    text_h = line_h * len(lines)

    margin = int(cfg.get("margin", 48))
    use_panel = panel.get("enabled", True) and not page.get("no_panel", False)
    box_w = int(text_w + (pad_x * 2 if use_panel else 0))
    box_h = int(text_h + (pad_y * 2 if use_panel else 0))

    horiz = page.get("text_pos", "tl")[1]
    vert = page.get("text_pos", "tl")[0]
    bx = margin if horiz == "l" else img.width - margin - box_w
    by = margin if vert == "t" else img.height - margin - box_h

    if use_panel:
        od.rounded_rectangle(
            [bx, by, bx + box_w, by + box_h],
            radius=int(panel.get("radius", 28)),
            fill=tuple(panel.get("fill", [255, 253, 248, 215])),
            outline=tuple(panel.get("outline", [240, 214, 170, 235])),
            width=3,
        )

    colors = {k: tuple(v) for k, v in cfg["colors"].items()}
    x0, y0 = bx + pad_x, by + pad_y + 2
    for ln in lines:
        cx = x0
        for tok, color in ln:
            od.text((cx, y0), tok, font=font, fill=colors[color or "default"])
            cx += od.textlength(tok, font=font)
        y0 += line_h

    out = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    os.makedirs(cfg["out_dir"], exist_ok=True)
    dest = os.path.join(cfg["out_dir"], f"{page['id']}.jpg")
    out.save(dest, quality=92)
    print(f"page {page['id']}: {raw.size} -> {out.size} | font {size}px | "
          f"{len(lines)} lines | pos {page.get('text_pos', 'tl')} | {dest}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-c", "--config", required=True, help="path to the JSON config")
    ap.add_argument("--dry-run", action="store_true",
                    help="compute layout only, write nothing")
    args = ap.parse_args()

    with open(args.config, encoding="utf-8") as fh:
        cfg = json.load(fh)

    for key in ("raw_dir", "out_dir", "target_size", "max_text_width", "colors", "pages"):
        if key not in cfg:
            raise SystemExit(f"ERROR: config is missing required key '{key}'")

    font_path = pick_font(cfg, cfg.get("font_path"))
    if args.dry_run:
        draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        for page in cfg["pages"]:
            tokens = tokenize([tuple(s) for s in page["segments"]])
            font, size = fit_font(tokens, font_path, cfg, draw)
            lines = wrap(tokens, font, cfg["max_text_width"], draw)
            print(f"page {page['id']}: font {size}px, {len(lines)} lines, "
                  f"pos {page.get('text_pos', 'tl')}")
            for ln in lines:
                print("   | " + "".join(t for t, _ in ln).rstrip())
        return

    for page in cfg["pages"]:
        draw_page(page, cfg, font_path)
    print(f"done -> {cfg['out_dir']}")


if __name__ == "__main__":
    main()
