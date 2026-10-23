# 精品课导入接口契约（POST /api/official-courses）

> 依据 2026-10-17 验收 + 2026-10-18 改造实测（24/24 通过）。实现：`server/src/routes/officialCourses.ts` + `lib/officialCourse.ts`。

## 基本约定

- `POST {serverBase}/api/official-courses`，multipart/form-data，头 `X-Import-Token: <COURSE_IMPORT_TOKEN>`。
- 口令错误/缺失返回 **404**（伪装成地址不存在），不是 401。不需要设备号（lib/device.ts 白名单）。
- 成功返回：`{ok, data: {id, replaced, audioDigests, slowDigests, wordAudioDigests, quizQuestionAudioDigests, quizAnswerAudioDigests, pictureDigests, ...}}`。

## 文件字段（顺序即语义！）

图片 jpg/png/webp ≤4MB（按字节头嗅探）；音频 mp3 ≤8MB（ID3 或 0xFFEx 头）；整次 ≤64MB。

| 字段 | 重复次数 | 对齐对象 |
|---|---|---|
| `cover` | 1 | 封面 |
| `page` | 页数 | pages[] 顺序 |
| `audio` | 句数 | sentences[] 顺序 |
| `slow` | 句数 | sentences[] 顺序 |
| `wordAudio` | 词数 | words[] 顺序 |
| `picture` | 词数（可整组省略） | words[] 顺序 |
| `quizQuestionAudio` | 问答数 | quizzes[] 顺序 |
| `quizAnswerAudio` | 问答数 | quizzes[] 顺序 |

**服务端不做任何内容校验，audio[i] ?? null 按到达顺序配对**——漏一个或字段重排，从那句起全部音画错配且返回成功。所以字段只能由 build_course.py 按 manifest 顺序 append，禁止手拼 curl。

## JSON 文本字段

- `title` / `titleZh` / `externalId`
- `sentences`：JSON 数组，每条 `{en, zh, leadIn, pageIndex}`（leadIn 脚本自动生成 `Listen. {en}`）
- `words`：course.json 的 words 原样
- `quizzes`：course.json 的 quizzes 原样

## externalId 语义（幂等覆盖）

- 格式 `{slug}-v1-{hash8}`；**ASCII only**，≤64 字符（中文会 400）。hash8 = 文本签名（句子/词/问答文本）的 sha256 前 8 位。
- 同 externalId 再传 = **覆盖**该课（`replaced: true`）：文件清理后重写，句子级学习进度清零（events JOIN sentences），打开次数保留。
- 文本变了 → hash8 变 → **新课**。旧课下架：**DELETE 接口已停用**（`DELETE /api/official-courses/{externalId}` 现在返回 400「这本课要下架的话，请到审核页点退回」），只能在后台对旧课点「退回」，状态变 rejected 后不再进列表。

## 缺音频的后果（必须每句都传）

`audio_status` 落为 pending 的句子，会在用户打开课程音频时用**服务端 TTS（BV001 中文音色）**兜底合成——精品课里音色瞬间断层。词/问答同理：不传 wordAudio/quizAudio 就走服务端合成音色。

## 四道防线（脚本已内置，了解即可）

1. **上传前预检**：数量/长度上限/pageIndex 越界/mp3 魔数/图片魔数/体积（build_course.py preflight）
2. **顺序由脚本 append**：FormData 重复同名 key 保持插入顺序；禁用"对象转表单"库（会合并同名字段）
3. **上传后 md5 回执核对**：6 组 digest 与本地逐一比对——唯一能抓出顺序错位的手段
4. **回读校验**：GET /api/materials/{id} 查每句 audioFile，抽样下载比对 md5，词/问答实际播放返回的音频也要对上

## 其他注意

- 页面图按原字节存储不压缩（savePageThumb 只改名），1280×1024 JPEG q82 约 300KB/张，单图目标 ≤2MB。
- 上限（>80 句 / >21 页等）目前返回 500 而非 400（服务端待修）；invalid() 的报错文案是家长拍照线的（"这张图有点大"），导入方忽略文案看 status 即可。
- word 播放优先读 card_json.audioPath；有词卡图的服务端不再现场生成。

## 审核状态（2026-10-20 起）

- 导入落库时 `review_status='pending'`：列表（`scope=official`）与 `GET /api/materials/:id` 都只认 `approved`，pending 的课等于「库里有了但不可见、不可学」。
- **本 skill 的边界：只负责把数据传进去并保持 pending。禁止调用 approve/reject，禁止改库改状态。** 审核是作者在后台的人工动作。
- 审核接口（仅供了解，`X-Admin-Token` 由 `POST /api/admin/login` 用 `.env` 的 `ADMIN_USER`/`ADMIN_PASSWORD` 换）：
  - `GET /api/admin/courses?review=pending`（审核列表）
  - `POST /api/admin/courses/{id}/approve` / `.../reject`（作者操作）
- approved 的课不能再被同 externalId 覆盖（`CourseOnShelfError`）；要改内容：用新文本生成新课，旧课在后台退回。
- 覆盖导入会重置 `review_status='pending'`，每次重传都要重新过审。
- 判断"上传成功"只看库里 `status='ready'` + `review_status='pending'`（`select ... where external_id=...`），别用列表有没有出现来判断。
