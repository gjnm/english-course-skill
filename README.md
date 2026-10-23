# 英文绘本精品课 · WorkBuddy 技能

把一本英文绘本的照片，做成一套**能听、能跟读、能答题**的课程页：重制插画、中英对照句子、生词图卡、语音问答，最后生成一个单文件网页，双击就打开。

跑在你自己的电脑上，用的是你自己的生图和语音额度，课程内容不上传任何服务器。

---

## 一、装之前

| 需要 | 说明 |
|---|---|
| WorkBuddy | 技能跑在 WorkBuddy 里（生图、对话触发都靠它）：<https://www.workbuddy.cn> |
| Python 3.8+ | 脚本用；macOS 自带，Windows 去 python.org 装（勾 Add to PATH） |
| 火山引擎语音账号 | 取 `APP ID` / `Access Token`，用于合成英文音频 |
| 一本英文绘本的照片 | 手机拍清楚，8 张左右，按页序 |

Pillow、requests 这两个 Python 包安装脚本会自动补，不用手动装。

---

## 二、安装

### macOS / Linux

到 [Releases](https://github.com/gjnm/english-course-skill/releases/latest) 下载 `english-course-skills.zip` 解压，在解压目录里执行：

```bash
bash install.sh
```

或者一条命令（走 GitHub Release）：

```bash
curl -fsSL https://raw.githubusercontent.com/gjnm/english-course-skill/main/install.sh | bash
```

### Windows

解压 zip，在解压目录按住 Shift 右键 →「在此处打开 PowerShell 窗口」：

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

安装脚本会做四件事：把两个技能放进 `~/.workbuddy/skills/`（旧版自动备份成 `.bak-时间戳`，不删任何东西）→ 生成凭证模板 `~/.english-course-producer/credentials.env` → 补 Python 依赖 → 跑一遍环境自检。

自检里出现 `FAIL` 就先按提示处理，再往下走。

---

## 三、怎么用

1. 打开 WorkBuddy（已经开着的话重开一次，让它加载新技能）
2. 打开 `~/.english-course-producer/credentials.env`，填两行：
   ```
   TTS_VOLC_APP_ID=你的appid
   TTS_VOLC_ACCESS_TOKEN=你的token
   ```
3. 在对话里把绘本照片发出去，说一句：

> 这几张绘本照片，做成能听能读的英文课

也可以说「把绘本做成课后练习」「给孩子做本英文绘本课」「做一套绘本跟读」。技能会自动接住，先转录英文，再重制插画，然后合成音频、排词汇和问答。

### 你会拿到什么

课程目录里会有：

- `pages-5x4/` — 重制的 8 张插画页（英文句子已排好版）
- `words/` — 生词图卡（6:5）
- `audio-bv506/` — 全部音频（正句 / 慢速 / 单词 / 问答）
- **`线上绘本展示.html`** — 单文件成品，图片和音频全内嵌，发给别人双击就能用

展示页的样子：左边是学习类型（课程音频 / 重点词汇 / 跟读练习 / 语音问答），右边是内容区；手机上学习选择自动移到底部。课程音频支持「连续播放」，播到哪句滚到哪句。

---

## 四、要花多少钱（重要）

这条流水线会调用付费能力，**费用从你自己的账号出**，作者不代付、也不抽成。

| 环节 | 量 | 计费 |
|---|---|---|
| 插画重制 | 约 21 张/本（8 页图 + 12 词图 + 1 角色锚点） | WorkBuddy 生图积分，每张 5–10 积分 |
| 语音合成 | 约 44–56 条短音频 | 火山语音按账号套餐计费 |

关于火山音色，**务必先确认再批量跑**：默认用的是 `BV506_streaming`（天真萌娃童声）。火山官方的说法是「服务开通后，音色需在控制台下单购买」，付费精品音库是 1000 元/音色/月那一档。所以：

- 先在火山控制台「音色库」确认这个音色对你是免费、已购、还是需要下单；
- 拿不准就先跑一本、看账单，再决定要不要换音色；
- 换音色改 `config.json` 里的 `voice` 字段即可，脚本会按音色分目录存音频，不会混用旧缓存。

时间上，绝大部分花在生图：一本 8 页约 4–5 小时（生图必须串行，同时发多张会互相覆盖）。转录、排版、TTS、展示页加起来不到半小时。

---

## 五、它不做什么

- **不上传任何课程**。全部在本机跑完。没有服务端、不需要 token，脚本里也拒绝用你的自备凭证往远端传东西。
- **不收集数据**。不联网回传，除了火山语音接口和 WorkBuddy 自己的生图。
- **不碰任何审核状态**。这是纯生产工具，没有后台、没有权限。
- 不替你判断版权：绘本照片请自备，商用前确认授权。

---

## 六、常见问题

**Q：跑到合成音频就停了，说找不到凭证？**
凭证文件没填或键名写错。打开 `~/.english-course-producer/credentials.env` 对照模板检查，改完重跑即可（已合成的音频会复用，不会重复花钱）。

**Q：排版报 `no usable font found`？**
系统里没找到可用字体。Windows 一般有 `C:\Windows\Fonts\comicbd.ttf`，macOS 有 `ChalkboardSE.ttc`；实在没有，在 layout 配置里指定 `font_path` 指向任意英文 `.ttf`。

**Q：中途断了要重来吗？**
不用。每一步都幂等：页图落位就跳过、音频文件存在就复用、展示页随时可重生成。

**Q：能改已经做好的课吗？**
改文字 = 新课（课号会变）；只改音色或语速 = 覆盖同一课。

**Q：手机上能用吗？**
生成的 HTML 是单文件，手机上用浏览器打开也能看，学习选择在底部。

---

## 七、目录里都有什么

```
skills/english-course-producer/     主技能：转录 → 生图 → 排版 → TTS → 展示页
skills/english-picturebook-cards/   子技能：插画重制与精确文字排版（主技能会调用它）
install.sh / install.ps1            安装脚本
```

版本：v1.4.0
