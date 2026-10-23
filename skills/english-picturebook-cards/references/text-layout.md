# 文字排版规则与配置示例

## 位置选择（text_pos: tl / tr / bl / br）

按每张图的构图挑**留白最多的角**，逐图判断，没有全局默认：

| 画面情况 | 推荐 |
|---|---|
| 上部是天空/素墙 | `tl` 或 `tr` |
| 上部有屋顶/树枝，下部是草地/地板 | `bl` / `br`（注意别压脚） |
| 左右都有主体、只有上部中间空 | 仍选 `tl`/`tr`，面板宽度受 `max_text_width` 限制，不会太宽 |

面板样式（默认值已调好，一般不动）：半透明白 `rgba(255,253,248,215)` + 米色描边 `rgba(240,214,170,235)`、圆角 28。半透明是为了让底图纹理微微透出，不生硬。

## 字体

优先级见 `layout_pages.py` 的 `FONT_CANDIDATES`：Chalkboard SE（macOS 自带圆体，儿童感强）→ Arial Rounded → Comic Sans → DejaVuSans（Linux 兜底）。

## 字号与自动缩字

默认 44px（1280 宽画布）；单词太长放不进 `max_text_width` 时自动逐级缩到 `min_font_size`（默认 30），不会溢出面板。改字号只动 `font_size`，别去改脚本。

## 生词高亮配色（colors）

```json
{
  "default": [58, 58, 82, 255],
  "red":   [226, 82, 62, 255],
  "green": [106, 148, 74, 255],
  "blue":  [64, 120, 200, 255]
}
```

## 完整 config 示例（首例实测可用）

```json
{
  "raw_dir":  "<绘本目录>/_raw",
  "out_dir":  "<绘本目录>/重制版-5x4",
  "target_size": [1280, 1024],
  "font_size": 44,
  "line_spacing": 1.32,
  "margin": 48,
  "max_text_width": 760,
  "panel": {
    "enabled": true,
    "fill": [255, 253, 248, 215],
    "outline": [240, 214, 170, 235],
    "radius": 28, "pad_x": 34, "pad_y": 26
  },
  "colors": {
    "default": [58, 58, 82, 255],
    "red": [226, 82, 62, 255],
    "green": [106, 148, 74, 255],
    "blue": [64, 120, 200, 255]
  },
  "pages": [
    {
      "id": "02",
      "file": "Soft_watercolor_children_s_pic_2026-10-15T07-07-10.png",
      "trim_left": 0,
      "text_pos": "tl",
      "segments": [
        ["Mother rabbit goes to the ", null],
        ["market", "red"],
        [" and leaves three little rabbits at home.", null]
      ]
    },
    {
      "id": "03",
      "file": "Soft_watercolor_children_s_pic_2026-10-15T07-07-11.png",
      "trim_left": 200,
      "text_pos": "tl",
      "segments": [
        ["A wolf comes and ", null],
        ["knocks", "red"],
        [" at the door. \u201cOpen the door, babies! I have some candies,\u201d he says.", null]
      ]
    }
  ]
}
```

## 裁切参数语义（踩过坑，重点）

- `trim_left: N` = 从**左边**裁掉 N 像素（剩余窗口右移）；省略 = 居中裁
- `trim_top: N` 同理（只有原图比目标"更高"时才生效）
- 生图统一出 1536x1024、目标 1280x1024 时，宽向共裁 256：`trim_left` 取值 0–256
- **值怎么定**：看构图——主体偏右就从左边多裁（trim_left 调大），主体偏左就取 0。定不准就先跑一版 Read 看效果

## 验证方法

1. `--dry-run` 打印每页换行，检查断词（高亮词不能被拆行）和行数
2. 正式跑后逐张 Read：文字完整、面板位置、比例
3. 与预期不符：只改 config 重跑，脚本秒级、零积分
