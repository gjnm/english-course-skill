---
name: english-course-producer
version: "1.4.0"
display_name: "英文绘本精品课生产线"
display_name_en: "English picture-book course producer"
description: "End-to-end production line for the AI English course: from photos of an English picture book, transcribe the English, regenerate watercolor illustration pages, write sentences/words/quizzes, synthesize child-voice TTS audio (Volcano/火山), build a self-contained showcase page (线上绘本展示.html, styled after the App learn screen), and — in the owner's local mode only — upload the course to the local import API (127.0.0.1:3100) with full md5 verification. Uploaded courses land as review_status=pending and stay pending; the owner approves in the admin backend, this skill NEVER changes review status. External users (no project .env) stop at the showcase HTML and do NOT upload. Use when the user asks to 做一本精品课/做成课程/做课/生产课程/把绘本做成课程/上传精品课, provides picture-book photos for course production, asks to 重新生成音频/换音色重做/改课程内容后重传, or wants a 线上绘本展示/展示页. Triggers (plain speech included): 精品课、做课、绘本做课程、课程音频、线上绘本展示、导入课程、做成能听能读的英文课、绘本做成课后练习、给孩子做英文绘本课、绘本配音频、绘本跟读、把绘本做成课. NOT for single image cards alone (use english-picturebook-cards) or for the user-facing photo-to-course feature. Risk level L2 for the owner (paid TTS, image-generation credits, local upload as pending); L1 for external users (no upload at all)."
description_zh: "「AI 助学英语」精品课端到端生产线：从英文绘本照片开始——转录英文 → 重制水彩插画页 → 编写句子/生词/问答 → 火山童声 TTS 合成音频 → 生成单文件「线上绘本展示.html」（对齐 App 学习页风格：左侧学习选择栏 + 右侧内容区，含课程音频/重点词汇九宫格/跟读练习/语音问答四个板块）。分两种模式：**作者本机模式**（找得到项目 server/.env）在展示页后直接上传到 http://127.0.0.1:3100，落为「待审核」，由作者到后台点通过；**外部使用者模式**（没有项目 .env，只填自己的火山 key）到展示页为止，不上传、不碰服务端。本 skill 绝不修改审核状态。风险等级：作者 L2（调付费 TTS、耗生图积分、上传本机库为待审核），外部 L1（不上传）。触发说法：精品课、做课、绘本做课程、线上绘本展示、导入课程、做成能听能读的英文课、绘本做成课后练习、给孩子做英文绘本课、把绘本做成课。"
agent_created: true
---

# 英文绘本精品课生产线

把一摞英文绘本照片，做成一本可直接在 App「精品课程」里播放的完整课程：重制插画 + 中英句子 + 生词卡（图+音）+ 问答（题音+答音）+ 慢速跟读，全部音频本地合成后随课上传，服务端零合成。

本 skill 的定位是**跑数据**：一条命令链跑到底，跑完把「线上绘本展示」页（作者模式还带课号）交出来。首例：`产出/精品课-DontOpenTheDoor/`（2026-10-17 上线），同目录下还有 `精品课-LittleRabbitsCarrot/`、`精品课-EatUpAllTheFood/`。

> 风险等级：**作者 L2**（调火山付费 TTS、耗生图积分、上传本机库）、**外部 L1**（到展示页为止，不碰服务端）。**审核状态一律不碰。**

## 两种模式（先判定，再开跑）

| | 作者本机模式 | 外部使用者模式 |
|---|---|---|
| 判定 | 找得到项目 `server/.env`（含 `TTS_VOLC_*` + `COURSE_IMPORT_TOKEN`） | 找不到；只有 `~/.english-course-producer/credentials.env` |
| 凭证 | 项目 server/.env | 自己的火山 APP ID / Access Token |
| 终点 | 展示页 → **`--upload` 到 `http://127.0.0.1:3100`** → 6 组 md5 + 回读 | **展示页为止**，不上传、不要 token、不连服务端 |
| 交付 | 展示页 + 课号，等作者后台过审 | 展示页 + 课程目录，交回作者 |

`build_course.py` 会按 `config.envFile` → `ECP_ENV_FILE` → 项目 `server/.env` → `~/.english-course-producer/credentials.env` 顺序找凭证，找到哪个用哪个，并打印 `凭证：<路径>`，据此就能知道当前是哪一档。

## 核心原则

1. **上传只属于作者本机模式**：外部使用者跑到展示页就结束，**不加 `--upload`**、不配 `serverBase`、不要 token。脚本自带两道闸，加了 `--upload` 也会被拒（退出码 3）：① 凭证来自 `~/.english-course-producer/credentials.env`（自备凭证=外部模式）；② `serverBase` 不是 `127.0.0.1`/`localhost`（确需传远端要显式加 `--allow-remote-upload`）。上传落库固定 `review_status=pending`；**禁止**调用 `POST /api/admin/courses/:id/approve|reject`，**禁止**直接改库改成 approved。作者在后台点通过，用户才看得到。
2. **展示页不是卡点，但也别越过模式**：作者模式合成完 → 出 `线上绘本展示.html` → **立即 `--upload`**；外部模式出完展示页就交付，不尝试上传（连不上服务端，也没 token）。
3. **音频永远本地合成、随课上传**。缺哪句的音频，服务端就用 BV001（中文音色）兜底，音色瞬间断层——**每句必传，一句不落**。
4. **内容改动会换 externalId**：哈希只含文本（句子/词/问答），改一个词就是新课；改音色/语速才覆盖同一课。改文本后旧课要在后台**退回**（reject）下架——服务端 DELETE 接口已停用（返回"请到审核页点退回"）。
5. **音频缓存按音色分目录**（`audio-bv506/`、`audio-bv421/`），换音色永不误用旧缓存。
6. **中断不重跑**：所有步骤幂等（图落位即跳过、TTS 文件存在即复用、上传按 externalId 覆盖）。网断了先看目录现状，缺口补缺口。

## 前置条件

**作者本机模式**
- 服务端已启动（默认 `http://127.0.0.1:3100`）。`.env` 已配 `COURSE_IMPORT_TOKEN` 与 `TTS_VOLC_APP_ID`/`TTS_VOLC_ACCESS_TOKEN`。
- 服务端挂了（`/api/health` 不通）先起：`cd <项目>/ai-english/server && npm start`（后台跑，日志 `/tmp/ai-english-server.log`）。上传脚本会自检，挂了直接报错不会白跑。

**外部使用者模式**
- 只需要自己的火山语音凭证：复制 `references/credentials.example.env` 到 `~/.english-course-producer/credentials.env`，填 `TTS_VOLC_APP_ID` / `TTS_VOLC_ACCESS_TOKEN`（开通与取值见文件内注释）。
- **不需要**服务端、**不需要** `COURSE_IMPORT_TOKEN`、`config.json` 里**不要**写 `serverBase`。
- 缺凭证时脚本会直接给出上面这段做法并退出码 2，不会甩 traceback。

**通用**
- **开跑前先自检**（外部用户必做，作者本机也建议）：`python3 <skill>/scripts/check_env.py`。它一次查完 Python 版本、requests、Pillow、cards 技能是否在位、可用排版字体、火山凭证是否填好，缺什么直接给补的命令。带 `--course <课程目录>` 还会顺带查 course.json / config.json / pagesDir。
- Python：优先 WorkBuddy 托管解释器 `~/.workbuddy/binaries/python/envs/default/bin/python`（通常已带 requests/Pillow），没有就用系统 `python3` + `pip install --user requests pillow`。
- 插画重制能力委托 skill **english-picturebook-cards**（5:4 = 1280×1024，无字生图 + 脚本排版）。**这两个 skill 必须一起装**：分发包里是一起带的，单独只装本 skill 会在排版这步报找不到 `layout_pages.py`。
- 排版字体按平台自动找（macOS Chalkboard / Windows Comic Sans / Linux DejaVu），全都没有时在 layout 配置里显式给 `font_path`。

**可移植性**：凭证文件与 `serverBase` **刻意不随包分发**，包内只有 `references/credentials.example.env` 模板。所以外部用户开箱即可跑完转录、生图、排版、TTS、manifest、展示页（缺的只是他自己的火山 key）；上传这一步在设计上就不开放给外部。

## 真实耗时（2026-10-19 实测，8 页 / 12 词 / 11 句 / 56 条音频）

| 环节 | 实测 | 说明 |
|---|---|---|
| 转录 + 写 course.json | ~20 min | 8 张照片 |
| **页图 8 张** | **4 h 26 min** | 18:32→22:58，**唯一的大头**：串行生图 + 一次一张 Read 验收 + 3 次 EPIPE 重试 + 网络挂起等回话 |
| 排版（layout_pages.py） | 13 min | 脚本本身秒级，时间花在配置和验收 |
| 词图 12 张 | 35 min | 00:11→00:46，≈3 min/张 |
| **TTS 56 条** | **1.2 min** | 火山很快，**不要为它做任何优化** |
| manifest + 展示页 | < 1 min | |
| 上传 + 6 组 md5 + 回读 | 3–10 min | pending 时回读自动 SKIP |
| 上传后进程挂掉重传 | +20 min | 2026-10-20 实际发生：服务端半夜退出，重传一次（现已加自检） |

**结论：时间 95% 花在生图，而其中大半是"串行 + 每张一次往返 + 网络中断后干等"。** 下面第 2 步的并行与批量验收就是针对这个。

## 流水线（8 步，第 7 步按模式分流）

### 0. 建课目录

`产出/精品课-<Slug>/`（Slug 用 ASCII 连字符小写，如 `dont-open-the-door`）。写两份文件：

`config.json`（机器读，脚本用）。**作者本机版**：

```json
{
  "slug": "dont-open-the-door",
  "pagesDir": "/绝对路径/重制版-5x4",
  "voice": "BV506_streaming",
  "speedNormal": 0.95,
  "speedSlow": 0.65,
  "serverBase": "http://127.0.0.1:3100",
  "envFile": "<项目根>/ai-english/server/.env"
}
```

**外部使用者版**（不要 `serverBase`、不要 `envFile`，凭证走 `~/.english-course-producer/credentials.env`）：

```json
{
  "slug": "dont-open-the-door",
  "pagesDir": "/绝对路径/重制版-5x4",
  "voice": "BV506_streaming",
  "speedNormal": 0.95,
  "speedSlow": 0.65
}
```

`course.json`（内容稿，schema 与字段上限见 `references/course-json.md`）。

### 1. 读图转录

**一批并行读**（一次消息里发 4–6 个 Read），不要一张一张来。**从照片转录英文原文**（不是凭记忆编），看不清就问用户。整理页序表：页码 → 英文句子。

先判定是哪条路：**成品插画卡**（英文已精确排版、风格统一）→ 直接当页图，只需 `prep_images.py pages` 补 5:4；**实体书拍照**（页面弯曲、有桌面背景）→ 走第 2 步完整重制。

### 2. 重制插画（最耗时环节，按下面三条走）

走 english-picturebook-cards 的流程（角色锚点图 → 生图 → 排版），但用这里的**提速版**：

- **一图一目录**：`_raw/p01/`、`_raw/p02/` …（封面 `_raw/p00/`）。ImageGen 输出名带时间戳，同目录混放既分不清顺序、也可能撞名；一图一目录后，目录名就是页序，断点也一眼看出缺哪张。
- **允许 2–3 张并发**：不同 `output_dir` 互不干扰。并发时**同一消息内发多个生图调用**；若出现失败/串味，退回串行（串行是安全底线，不是性能选项）。
- **批量验收**：一次消息并行 Read 4–6 张，别生成一张读一张（那是 20 次额外往返）。不合格的单张用原 prompt + 明确修改点重画，不要整批重来。
- 失败重试：EPIPE/超时**立刻重试一次**；连续 3 次失败再 `sleep 20` 重试（别一上来就干等）。
- prompt 末尾必须带 `Absolutely no text, no letters, no words anywhere in the image`。生图右下角有水印，居中裁切即去。

落位（顺序交给参数，不靠文件名排序）：

```bash
<python> <skill>/scripts/prep_images.py pages <课程>/../重制版-5x4 _raw/p01/*.png _raw/p02/*.png ...
# 封面（成品卡无字标题页时）：加 --crop，居中裁 5:4
<python> <skill>/scripts/prep_images.py pages <重制版-5x4> _raw/p00/*.png --crop
```

### 3. 写 course.json

- **句子**：按绘本原意转录并译中文；角色台词从叙述里拆成独立句（一句一条音频，太长不好跟读）；`pageIndex` 从 0 起。
- **生词**：10–12 个，覆盖 Sight word + 核心名词/动词，带音标和 `sentenceIndex`。
- **问答**：尽量每句配一道，`question`/`questionZh`/`answer`/`accept`（答案同义列表，全小写）/`keyWord`。**问答考理解，不考复述**，答案 1–5 个词。
- **cover**：选信息量足、适合当封面的一页（可与 pages 重复）。

### 4. 词图

每个生词一张 6:5（1229×1024）水彩词图，`_raw/w00/`…`_raw/w11/` 一图一目录，最后：

```bash
<python> <skill>/scripts/prep_images.py words <课程>/words _raw/w00/*.png _raw/w01/*.png ...
```

- 实体名词/动词直接生图；**抽象词也出场景图**，画不出就先商量换词或放弃全部词图。
- 画角色/物品时把对应页图当 ImageGen 参考图，保持同款。
- **⚠️ 要么全齐，要么一张不传**：脚本要求词图与单词一一对应，缺图整组不上传。
- 同样 2–3 张并发 + 批量验收。

### 5. 合成音频 + 生成 manifest

```bash
<python> <skill>/scripts/build_course.py <course_dir>
```

自动完成：预检（数量/长度/魔数/体积）→ 火山 v1 TTS 合成（正句/慢速/单词/问答题目+答案）→ 幂等落盘 → 生成 `manifest.json`（含全部 md5 与 externalId）。明细与音色坑见 `references/tts-notes.md`。

### 6. 线上绘本展示页（对外可发的单文件站点）

```bash
<python> <skill>/scripts/make_review.py <course_dir>
```

生成自包含 `线上绘本展示.html`（图片与音频全部 base64 内嵌，双击离线可看）。**UI 对齐 App 学习页**（`frontend/src/pages/material/*` + `styles/learn-pane.css` 的设计语言，2026-10-22 定版）：

- **布局**：宽屏（≥960px）左侧「学习选择」栏（封面卡 + 四个模式按钮 + 元信息 chips），右侧内容区**独立上下滚动**；竖屏 / 窄屏学习选择沉到底部横排。
- **课程音频**：图文卡纵向铺开（页图 + 英文高亮生词 + 中文 + 「听这句 / 慢速」喇叭按钮），顶部贴滚动区顶部的「**连续播放**」一键串播全篇并自动滚到当前句。
- **重点词汇**：**九宫格**铺开（图 + 词 + 音标 + 中文），点卡片听发音。
- **跟读练习**：与课程音频同布局，按钮为「听示范 / 慢慢听」，附"App 里可录音"提示（展示页不做录音）。
- **语音问答**：一题一页（页图 + 题目 + 引导 + 「播放问题」+ 「不会答？点我听答案」），上一题 / 下一题切换。
- **配色 / 组件**沿用 App token：蓝 #4A9BFF、琥珀 #FFB020、绿渐变按钮、白卡 28px 圆角 + 蓝色柔和投影、高亮词琥珀色。

- **作者模式**：不停等，直接进第 7 步（上传）。上传后可再跑一次本脚本，补上课号与"待审核"chip。
- **外部模式**：**这一步就是终点**。把 `线上绘本展示.html` + 课程目录交回作者，不再执行上传。

### 7. 上传 + 全量校验（仅作者本机模式）

**外部使用者跳过本步**（脚本不加 `--upload` 时只会打印"未上传，外部模式到此为止"）。作者本机：

```bash
<python> <skill>/scripts/build_course.py <course_dir> --upload
```

脚本先探 `/api/health`（服务端挂了直接报错并给启动命令）→ 按 manifest 顺序拼 multipart → 上传（连接中断自动退避重试 3 次）→ 核对 6 组 md5 回执（audio/slow/wordAudio/quizQuestion/quizAnswer/picture）→ 回读校验。

**回读会打印 SKIP，这是正常的**：新导入的课是 `pending`，`GET /api/materials/:id` 对未审核课返回 404（`canStudy` 只放 approved），所以回读校验在审核通过前做不了。这时脚本输出 `SKIP 课已入库，但仍待审核` 并正常退出。

课通过审核后（作者在后台点的），要补校验就跑：

```bash
<python> <skill>/scripts/build_course.py <course_dir> --verify
```

**绝不做的事**：不代作者点通过/退回；不把 review_status 改 approved；不动线上已 approved 的课（同 externalId 覆盖会被 `CourseOnShelfError` 拒——改内容要么改用新文本（新 externalId），要么请作者在后台把旧课退回）。

### 8. 交付

`present_files` 线上绘本展示页，正文给：课名、句子·词·问答·音频·词图数量、音色与语速、建议重点听哪几句。

- **作者模式**：再补 externalId / 课号 / 6 组 md5 结果 / **"已入库为待审核，去后台点通过后用户可见"**。要改内容回到第 3 步（会生成新 externalId 的新课）。
- **外部模式**：明确写"**未上传**，本稿在本机生成，音频/图/课程目录都在本目录"，并按第 3 步改内容后重跑即可。

## 中断恢复（网络挂起、进程被杀）

1. `ls` 看现状：`_raw/pNN/` 缺哪个目录、`重制版-5x4/` 有几张、`words/` 有几张、`audio-bv***/` 有几条、有没有 `manifest.json`/`upload-result.json`。
2. 生图缺的补（已存在的目录不重画）；TTS 缺的补（删对应 mp3 才重合成）；上传没成功就再 `--upload`（同 externalId 覆盖 pending 课，安全）。
3. **不要因为有 `upload-result.json` 就跳过上传校验**——它只证明当时请求发出去了，可能像 2026-10-20 那样服务端中途退出。

## 改版语义（重要）

| 改了什么 | externalId | 后果 |
|---|---|---|
| 只换音色/语速（文本不动） | 不变 | 同一课被**覆盖**；句子级学习进度清零，打开次数保留；覆盖后**重新变 pending**，要再过审 |
| 改了任何文本 | **变** | 生成**新课**；旧课在后台退回下架（DELETE 已停用），否则列表里新旧并存 |

音频幂等缓存的正确用法：改文案重传时复用已合成文件（删掉对应 mp3 可强制重合成）；换音色时新目录自动隔离，旧目录留作存档。

## 已踩过的坑（血泪）

1. **音频顺序错位接口不报错**——按到达顺序配对，漏一个从那句起全错。只信脚本的 append 顺序 + md5 回执。
2. **幂等缓存撞音色**——旧版不分目录，换音色后旧音频被静默复用。已按 `audio-bv{音色}/` 分目录根治。
3. **externalId 不支持中文**——Slug 必须 ASCII，≤64 位。
4. **没传的词图会错位**——picture 也按顺序对齐，脚本已做"全有或全无"。
5. **火山非默认音色可能要单独购买**——能调通 ≠ 免费（试用态全量可调）。详见 `references/tts-notes.md`。
6. **生图带英文必拼错**——页图/词图一律不让模型写字。
7. **生图并发同目录会互相覆盖**——一图一目录；并发≠随便并发。
8. **服务端会半夜退出**（笔记本休眠/进程被中断）——上传前 health 自检，失败就 `npm start` 再传。
9. **pending 看不到不等于上传失败**——先查库：`select id,title,status,review_status from materials where external_id=...`，ready+pending 就是成功，只差审核。
10. 单图服务端上限 4MB，目标 ≤2MB（1280×1024 JPEG 约 300KB）。
11. **外部用户抄了作者的 `config.json`**（里面 `envFile` 是本机绝对路径）→ 现在不会直接崩，脚本按 `ECP_ENV_FILE` → 项目 `.env` → `~/.english-course-producer/credentials.env` 继续找，都找不到才提示"怎么填自己的 key"。
12. **外部用户误加 `--upload`** → 默认 `127.0.0.1:3100` 本机没服务，health 自检当场拦下并提示"去掉 --upload 跑到展示页即可"，不会产生半截数据。

## 给别人用：只给「做课 + 展示页」，不给上传（2026-10-20 定案）

**决策**：外部使用者拿这个 skill，配好自己的火山 key 后，能跑完到 `线上绘本展示.html`——能看页面、能听句子/单词/问答题音、能看题目和答案。**数据不上传**。上传只属于作者本机模式（`http://127.0.0.1:3100`）。

理由（评估过、明确放弃"外部直接上传"）：
- 服务端只有一个 `COURSE_IMPORT_TOKEN`，常量时间比较，**无法一人一令、无法单独吊销、无频率限制、无 `submitted_by`**，出事无法追溯。
- 持 token 者可往库里灌任意课程（虽都 pending）、也能覆盖别人未审的 pending 课。
- 因此收益（省去回传一步）远小于风险，不采用。

**对外部使用者要交代清楚的四件事**：
1. 凭证：`~/.english-course-producer/credentials.env`（模板 `references/credentials.example.env`，含火山开通路径）。
2. `config.json` 不写 `serverBase`/`envFile`；命令**不加 `--upload`**。
3. 流程终点是 `线上绘本展示.html`；改内容回到第 3 步重跑（音频幂等，只重合成改动的那几条）。
4. 交付物：`线上绘本展示.html` + 整个课程目录（含 `pages-5x4`/`words`/`audio-bv***`/`manifest.json`）打包回传，作者本机 `--upload` 即可入库（仍 pending，仍需作者过审）。

作者本机若要把某人做好的课入库：解包到 `产出/精品课-<Slug>/`，确认 `config.json` 指向本机 `pagesDir`，再 `--upload`。

## 参考文件

- `references/course-json.md` — course.json schema、字段上限、首例完整示例位置
- `references/api_reference.md` — 导入接口契约、md5 回执、覆盖/删除语义、审核状态（仅作者模式用）
- `references/tts-notes.md` — 火山 TTS 调用细节、可用童声、语速基准、收费确认路径
- `references/credentials.example.env` — 外部使用者自备火山凭证的模板

## 脚本清单

- `scripts/check_env.py` — 环境自检：Python 版本 / requests / Pillow / cards 技能 / 排版字体 / 火山凭证，`--course` 还查课程目录（外部用户必跑）
- `scripts/prep_images.py` — 词图裁 6:5 / 页图补 5:4 / 封面裁 5:4（顺序=参数顺序）
- `scripts/build_course.py` — 预检 + TTS + manifest（+ 作者模式上传 / md5 回执 / 回读）；`--verify` 只校验
- `scripts/make_review.py` — 单文件「线上绘本展示」HTML（纯离线，外部模式也能跑；UI 对齐 App 学习页）
