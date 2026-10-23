# 火山 TTS 调用细节与音色笔记

## 接口（v1，项目同款）

`POST https://openspeech.bytedance.com/api/v1/tts`，头 `Authorization: Bearer;<ACCESS_TOKEN>`，body：

```json
{
  "app":  {"appid": "<TTS_VOLC_APP_ID>", "token": "access_token", "cluster": "volcano_tts"},
  "user": {"uid": "course-build"},
  "audio": {"voice_type": "BV506_streaming", "encoding": "mp3", "speed_ratio": 0.95},
  "request": {"reqid": "<唯一串>", "text": "...", "text_type": "plain", "operation": "query"}
}
```

- 成功：`code=3000`，`data` 为 base64 mp3。失败重试 3 次、间隔 1.5s。
- 密钥从 `.env` 读：`TTS_VOLC_APP_ID` / `TTS_VOLC_ACCESS_TOKEN` / `TTS_VOLC_CLUSTER`。
- **文本先过 speak_text()**：去掉弯引号 “”‘’（保留句读），否则合成会念出标点或停顿异常。
- 合成后校验 mp3 魔数（ID3 或 0xFFEx），防止把错误页存成音频。

## 当前音色与语速基准

| 音色 | 说明 | 语速基准 | 推荐参数 |
|---|---|---|---|
| `BV506_streaming` | 天真萌娃 Lily（美式女童）**当前选用** | 2.43 词/秒 @1.0（偏慢） | 正句 0.95 / 慢速 0.65 |
| `BV421_streaming` | 天才少女（美式童声，8 国语言） | 2.92 词/秒 @1.0 | 正句 0.8 / 慢速 0.65 |
| `BV001_streaming` | 中文音色——**读英文难听，这就是要做精品课音频的根因** | — | 禁用 |

对照样本：`AI助学英语/产出/TTS音色试听-火山-绘本句/`。切换音色时用同句（Mother rabbit goes to the market…）对齐节奏后再定 speed。

## 收费风险（换音色前必查）

官方口径：**试用阶段可调用全部音色；服务正式开通后，音色需在控制台单独下单购买**。所以"能调通 ≠ 免费"。付费精品音库 1000 元/音色/月（旧版口径 10,000 元/年/音色）。确认路径（最硬的先查）：

1. 费用中心 → 账单详情（后付费约 3 小时出账，看有没有音色相关扣费）
2. 旧版控制台 → API 服务中心 → 语音合成 → 服务详情
3. 控制台 → 音色库 → 探索（官方指定的归类查询处）
4. 提工单

风险只压在 publish/计费环节：服务端只收 mp3 不调 TTS，运行时无授权问题。

## 幂等缓存（最大的坑）

synth 的幂等逻辑是"目标文件存在即复用"。历史事故：旧版不分目录，换音色后旧音色音频被静默复用且不报错。现行方案：**音频目录按音色分（audio-bv506/、audio-bv421/）**，换音色天然隔离。另外注意服务端 `db.ts` 的音频缓存只按文本查不带音色维度——**覆盖上传（同 externalId）时旧音频文件名不变即可正确覆盖；若怀疑服务端缓存，可查 DB 再验**。

## 其他

- 火山 2.0（v3 接口 seed-tts-2.0）已实测打通但**英文音色全成人**，童声只在 1.0——精品课不需要升 2.0。
- 服务端慢速朗读（audio_slow_path）目前"只存不播"，慢速音频照传不误。
