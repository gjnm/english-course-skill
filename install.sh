#!/usr/bin/env bash
# 英文绘本精品课 · 安装脚本（macOS / Linux）
# 用法一（推荐，从 GitHub Release 一条命令）：
#   curl -fsSL https://raw.githubusercontent.com/gjnm/english-course-skill/main/install.sh | bash
# 用法二（下载 zip 解压后，在解压目录里）：
#   bash install.sh
set -euo pipefail

REPO_SLUG="${ECP_REPO_SLUG:-gjnm/english-course-skill}"
ZIP_URL="${ECP_ZIP_URL:-https://github.com/${REPO_SLUG}/releases/latest/download/english-course-skills.zip}"
FALLBACK_URL="https://codeload.github.com/${REPO_SLUG}/zip/refs/heads/main"
SKILLS_DIR="${WORKBUDDY_SKILLS_DIR:-$HOME/.workbuddy/skills}"
CRED_DIR="$HOME/.english-course-producer"
CRED_FILE="$CRED_DIR/credentials.env"
PRODUCER="english-course-producer"
CARDS="english-picturebook-cards"

say() { printf '%s\n' "$*"; }
die() { printf '出错：%s\n' "$*" >&2; exit 1; }

say "=============================="
say " 英文绘本精品课 · 安装"
say "=============================="
say ""

# 1. 找安装源：脚本旁边的 skills/ 优先（zip 解压后直接跑），否则下载
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
WORK=""
cleanup() { if [ -n "$WORK" ]; then rm -rf "$WORK"; fi; }
trap cleanup EXIT

if [ -d "$SELF_DIR/skills/$PRODUCER" ]; then
  SRC="$SELF_DIR/skills"
  say "安装源：本地目录 $SRC"
else
  command -v curl >/dev/null || die "没有 curl，装不了。请用浏览器下载 zip 解压后运行 bash install.sh"
  WORK="$(mktemp -d)"
  say "安装源：下载 $ZIP_URL"
  if ! curl -fsSL --retry 2 -o "$WORK/pkg.zip" "$ZIP_URL"; then
    say "Release 资产取不到（可能还没发布），改从仓库分支取，内容一致："
    say "  $FALLBACK_URL"
    curl -fsSL --retry 2 -o "$WORK/pkg.zip" "$FALLBACK_URL" \
      || die "下载失败。检查网络，或用浏览器打开 https://github.com/${REPO_SLUG} 手动下载"
  fi
  command -v unzip >/dev/null || die "没有 unzip，请手动解压 zip 后运行 bash install.sh"
  unzip -q "$WORK/pkg.zip" -d "$WORK/x"
  SRC="$(find "$WORK/x" -type d -name "$PRODUCER" -maxdepth 4 | head -1 | xargs -I{} dirname {})"
  [ -n "$SRC" ] && [ -d "$SRC/$PRODUCER" ] || die "压缩包里没找到 $PRODUCER"
fi

# 2. WorkBuddy 装了吗
if [ ! -d "$HOME/.workbuddy" ]; then
  say "提示：没找到 ~/.workbuddy，看起来还没装 WorkBuddy。"
  say "      这个技能跑在 WorkBuddy 里（生图、对话触发都靠它）：https://www.workbuddy.cn"
  say "      仍要继续安装技能文件？10 秒后继续，Ctrl+C 可取消。"
  sleep 10
fi

# 3. 装两个技能（旧版先备份，不删东西）
mkdir -p "$SKILLS_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
for name in "$PRODUCER" "$CARDS"; do
  if [ -d "$SKILLS_DIR/$name" ]; then
    mv "$SKILLS_DIR/$name" "$SKILLS_DIR/$name.bak-$STAMP"
    say "已备份旧版：$SKILLS_DIR/$name.bak-$STAMP"
  fi
  cp -R "$SRC/$name" "$SKILLS_DIR/$name"
  say "已安装：$SKILLS_DIR/$name"
done

# 4. 凭证模板（有就不覆盖）
mkdir -p "$CRED_DIR"
if [ ! -f "$CRED_FILE" ]; then
  cp "$SKILLS_DIR/$PRODUCER/references/credentials.example.env" "$CRED_FILE"
  say "已生成凭证模板：$CRED_FILE"
else
  say "已有凭证文件，保持不动：$CRED_FILE"
fi

# 5. Python 与依赖
PY="${ECP_PYTHON:-}"
if [ -z "$PY" ]; then
  for cand in "$HOME/.workbuddy/binaries/python/envs/default/bin/python" "$(command -v python3 || true)"; do
    if [ -n "$cand" ] && [ -x "$cand" ]; then PY="$cand"; break; fi
  done
fi
[ -n "$PY" ] || die "没找到 python3。装一个 3.8+ 的 Python 再来（macOS：brew install python）"
say "Python: ${PY} ($($PY -V 2>&1))"

if ! "$PY" -c "import PIL" 2>/dev/null; then
  say "缺 Pillow（排版、裁图要用），现在装到当前用户环境……"
  "$PY" -m pip install --user --quiet pillow || say "自动安装失败，请手动跑：$PY -m pip install --user pillow"
fi
if ! "$PY" -c "import requests" 2>/dev/null; then
  say "缺 requests（合成音频要用），现在装……"
  "$PY" -m pip install --user --quiet requests || say "自动安装失败，请手动跑：$PY -m pip install --user requests"
fi

# 6. 自检
say ""
"$PY" "$SKILLS_DIR/$PRODUCER/scripts/check_env.py" || true

say ""
say "=============================="
say " 装完了，下一步"
say "=============================="
say "1. 打开 WorkBuddy（已开着就重开一次，让它加载新技能）"
say "2. 填凭证：$CRED_FILE"
say "   TTS_VOLC_APP_ID / TTS_VOLC_ACCESS_TOKEN（火山语音控制台可取）"
say "3. 在对话里说：「这几张绘本照片，做成能听能读的英文课」并附上照片"
say ""
say "本工具不往任何服务器上传课程，全部在你本机跑完，最后给你一个 HTML 展示页。"
