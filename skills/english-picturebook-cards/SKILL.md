---
name: english-picturebook-cards
version: "1.0.0"
display_name: "英文绘本页重制插画卡片"
display_name_en: "English picture-book page card maker"
description: "Turn photos of English picture-book pages into clean 5:4 watercolor illustration cards with precisely typeset English text, for the AI English course audio page. Use when the user provides photos of picture-book pages and asks to 重制/重做/做成插画/做成课程配图, mentions 绘本卡片, or wants kid-friendly (3-6岁) redesigned characters that avoid copyright infringement. Triggers: 绘本照片、绘本重制、插画卡片、课程音频页配图、绘本配图重做. Not for editing arbitrary photos or making non-picturebook illustrations. Risk level L1 (creates local files, consumes image-generation credits ~5-10 per image)."
description_zh: "把英文绘本的拍照页重制成干净的 5:4 水彩插画卡片（英文由脚本精确排版，生词标色），用作 AI 英语课程音频页配图。当用户提供绘本照片并要求重制/重做/做成插画/做成课程配图，或要求为 3-6 岁重新设计角色并规避侵权时使用。触发词：绘本照片、绘本重制、插画卡片、课程音频页配图、绘本配图重做。不用于编辑普通照片或非绘本插画。风险等级 L1（写本地文件，生图消耗积分约每张 5-10）。"
description_en: "Rebuild photos of English picture-book pages into clean 5:4 watercolor illustration cards with script-typeset English text (keyword highlighting), for a kids' English course audio page. Triggers: 绘本照片, 绘本重制, 插画卡片, 课程音频页配图. Risk level L1."
agent_created: true
---

# 英文绘本页重制插画卡片

## 用途

把用户拍的一摞英文绘本照片，重制成一套构图干净、角色统一、适合 3-6 岁的 5:4 插画卡片，直接用于「AI 助学英语」课程音频页的配图位。首例：`AI助学英语/绘本照片/Dont open the door/`（2026-10-15 完成）。

> 分类：图像生成 + 排版流水线
> 风险等级：**L1** — 只写本地文件；消耗生图积分（每张 5-10，开始前必须告知用户）
> 核心原则：**生图永远不生成文字，文字全部由脚本排版** —— 模型拼英文必错，脚本排版保证拼写正确，且改句子不用重新生图。

---

## 什么时候用

- 用户发来绘本拍照页（通常糊、歪、带桌面杂物），要求做成规整插画
- 用户要求重设角色避免侵权、适配 3-6 岁
- 用户要给课程音频页补配图

**不适用**：修普通照片、做非绘本类插画、需要真实摄影风格的需求。

---

## 流水线（7 步，验收不可跳过）

### 1. 读图转录

逐张 Read 照片，转录每页英文原文（**从照片读，不是凭记忆编**）。文字看不清就先问用户，不要猜。整理成页序表：页码 → 英文句子。

### 2. 文本分段（决定生词高亮）

每页拆成 `segments`：普通文字 + 高亮词。沿用原书设计：每页标 1 个关键词（Sight word / 本页核心词），配色约定：

- 动作词/核心词 → `red`
- 回归/方位词 → `green`
- 时间/强调短语 → `blue`
- 正文 → 深藏青 `default`

原书没有高亮的页也可不标，不强求。

### 3. 角色重设计（防侵权 + 适龄）

为每个角色写一段**固定描述串**（体型、配色、服饰），整本书所有页复用同一串——这是角色一致性的根基。设计要求：

- **不照抄原书造型**：改体色搭配、服饰、比例（例：原书狼瘦长 → 重制为圆胖白背心棕短裤的滑稽狼）
- 3-6 岁适龄：圆润、大头身比、暖色、表情夸张但**不吓人**（反派做成滑稽）
- 每个角色一句话即可，别写太长（太长模型顾不过来）

### 4. 生图（规则最多的一步）

- 统一参数：`size: "1536x1024"`、`quality: "high"`、水彩绘本风 prompt 串（模板见 `references/image-generation.md`）
- **生图 prompt 末尾必须带**："Absolutely no text, no letters, no words anywhere in the image"
- **先出锚点图**：每个会跨页复现的角色，先生成一张该角色的图并 Read 检查；通过后，其余页用 `image1` 传锚点图 + `input_fidelity: "medium"` 生成（medium 保角色换场景；high 会把构图也抄过来）
- **⚠️ 一次只调一张，绝不并发**：ImageGen 并发调用会返回同一个文件路径（互相覆盖），带参考图的调用尤其如此
- 每张生成后立即 Read 检查：角色和锚点是否同款、有没有画出文字、留白区是否可用、有无吓人元素。不合格当场重生成，别攒到最后

### 5. 写排版配置

把生图产物整理进 `layout-config.json`（schema 见 `scripts/layout_pages.py` 文件头注释，完整示例见 `references/text-layout.md`）。要点：

- `target_size: [1280, 1024]` = 5:4（课程音频页要求的比例）
- 每页 `trim_left`：决定裁掉左边还是右边——看构图，主体偏哪边就从另一边多裁
- 每页 `text_pos`：`tl` / `tr` / `bl` / `br`，放在画面留白最多的角（天空、素墙）；拿不准就生成后看图再定
- 原始生成文件名带时间戳很乱，没关系，`id` 决定输出文件名（`"02"` → `02.jpg`）

### 6. 排版执行（脚本已验证）

```bash
# dry-run 先看换行和断词
<python> scripts/layout_pages.py -c layout-config.json --dry-run
# 正式出图
<python> scripts/layout_pages.py -c layout-config.json
```

Python 解析顺序：优先 `python3`（已装 Pillow）；没有则建隔离 venv 装 Pillow，**不许全局 pip**。

### 7. 验收（每张都要看）

逐张 Read 输出图，检查清单：

- [ ] 文字拼写与转录一致、无截断、无意外换行
- [ ] 面板不压在角色脸上/关键元素上
- [ ] 比例 1280x1024（5:4）
- [ ] 角色跨页一致
- [ ] 整体风格统一、无吓人元素

不合格的处理路径：文字问题改 config 重跑（秒级、免费）；构图问题重生成该页生图（花积分，先告知用户）。

---

## 产出物结构

```
<绘本目录>/
├── *.jpg                  # 用户原始照片（不动）
├── 重制版-5x4/
│   └── 02.jpg ... NN.jpg  # 最终交付
└── _raw/                  # 中间产物，保留（可复用资产）
    ├── <原始生成图>.png     # 无字原图（改文案后可直接重排版）
    └── layout-config.json  # 排版配置（新绘本照抄此结构）
```

交付用 present_files 批量列出所有成品图。

---

## 已踩过的坑（血泪，别重蹈）

1. **ImageGen 并发 → 同路径覆盖**。第 4/6 页曾返回同一文件，被迫重生成。带不带参考图都可能撞，一律串行。
2. **生图带文字必错**。AI 拼写不可靠，本流水线从设计上禁止生图出字。
3. **`input_fidelity: "high"` 会连构图一起抄**。跨场景复用角色用 `medium`。
4. **裁切参数名是 `trim_left` / `trim_top`**（不是 `left`/`top`），早期版本因此全图错误地居中裁切过。
5. **角色描述串要写死复用**，凭"大概记得"描述角色必跑偏。

---

## 给别人用（分发包）

整个 skill 目录可直接复制/打包给其他 WorkBuddy 实例使用。对方机器若非 macOS，字体 fallback 链见 `scripts/layout_pages.py` 的 `FONT_CANDIDATES`，兜底 DejaVuSans，仅字体观感略异。分发打包：用 skill-creator 的 `package_skill.py` 生成 zip。
