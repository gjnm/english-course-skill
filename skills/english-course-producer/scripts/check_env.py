#!/usr/bin/env python3
"""装完 / 开跑前先做环境自检：缺什么、怎么补，一次说清。

用法：
    python check_env.py                 # 只查依赖
    python check_env.py --course <dir>  # 顺带查课程目录是否齐（course.json / config.json / 页图）

退出码：0 全部可用；1 有必须处理的项。
"""
import importlib.util
import json
import os
import sys

CARDS_SCRIPT = os.path.expanduser(
    "~/.workbuddy/skills/english-picturebook-cards/scripts/layout_pages.py")
USER_ENV = os.path.expanduser("~/.english-course-producer/credentials.env")

OK, WARN, FAIL = "OK", "WARN", "FAIL"
rows = []


def add(level, what, hint=""):
    rows.append((level, what, hint))


def read_env(path):
    env = {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def check_python():
    v = sys.version_info
    ver = f"{v.major}.{v.minor}.{v.micro}"
    if (v.major, v.minor) >= (3, 8):
        add(OK, f"Python {ver}")
    else:
        add(FAIL, f"Python {ver} 太旧", "需要 3.8+，建议装 3.11 或更新版本")


def check_pkg(mod_name, pip_name, needed_by):
    try:
        mod = __import__(mod_name)
        ver = getattr(mod, "__version__", "")
        add(OK, f"{pip_name}{' ' + ver if ver else ''}")
        return True
    except ImportError:
        add(FAIL, f"缺 {pip_name}（{needed_by} 要用）", f"pip3 install --user {pip_name}")
        return False


def load_cards_module():
    """读 cards skill 的字体候选清单，保证两边的字体判断一致。"""
    if not os.path.isfile(CARDS_SCRIPT):
        return None
    spec = importlib.util.spec_from_file_location("cards_layout", CARDS_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except SystemExit:
        return None
    return mod


def check_cards(pillow_ok):
    if not os.path.isfile(CARDS_SCRIPT):
        add(FAIL, "没找到 english-picturebook-cards skill",
            "它在发布包里是必装项，重跑 install.sh 或手动复制到 ~/.workbuddy/skills/")
        return
    add(OK, "english-picturebook-cards skill 在位")
    if not pillow_ok:
        return
    mod = load_cards_module()
    if mod is None:
        add(WARN, "读不到排版脚本的字体清单", f"手动确认 {CARDS_SCRIPT} 可 import")
        return
    found = next((p for p in mod.FONT_CANDIDATES if os.path.exists(p)), None)
    if found:
        add(OK, f"排版字体：{os.path.basename(found)}")
    else:
        add(FAIL, "系统里没有可用的排版字体", "在 layout 配置里显式指定 font_path 指向任意英文 .ttf/.ttc")


def is_placeholder(value):
    """模板里的「你的appid」「your_token」「<xxx>」都算没填。"""
    v = (value or "").strip().lower()
    if not v:
        return True
    return any(h in v for h in ("你的", "your", "xxx", "<", ">", "填", "示例", "example", "todo"))


def check_credentials():
    if not os.path.isfile(USER_ENV):
        add(WARN, "还没填火山语音凭证（转录/生图能跑，TTS 会停在合音频）",
            f"cp <skill>/references/credentials.example.env {USER_ENV} 再填两个值")
        return
    env = read_env(USER_ENV)
    keys = ("TTS_VOLC_APP_ID", "TTS_VOLC_ACCESS_TOKEN")
    empty = [k for k in keys if is_placeholder(env.get(k))]
    if empty:
        if all(is_placeholder(env.get(k)) for k in keys):
            add(WARN, "凭证文件是模板，两个值还没填（转录/生图能跑，TTS 会停）",
                f"打开 {USER_ENV} 把「你的appid / 你的access_token」换成真值")
        else:
            add(FAIL, f"凭证没填全：{' / '.join(empty)}", f"打开 {USER_ENV} 补齐")
    else:
        add(OK, "火山语音凭证已填写")
    token = env.get("COURSE_IMPORT_TOKEN")
    if token:
        add(WARN, "凭证文件里写了 COURSE_IMPORT_TOKEN",
            "外部模式用不上它；本 skill 不会拿自备凭证往服务端上传")


def check_course(course_dir):
    for name in ("course.json", "config.json"):
        p = os.path.join(course_dir, name)
        if os.path.isfile(p):
            add(OK, name)
        else:
            add(FAIL, f"课程目录缺 {name}", "见 skill 的「0. 建课目录」")
    cfg_path = os.path.join(course_dir, "config.json")
    if not os.path.isfile(cfg_path):
        return
    try:
        cfg = json.load(open(cfg_path, encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        add(FAIL, f"config.json 解析失败：{exc}")
        return
    pages_dir = cfg.get("pagesDir") or ""
    if not os.path.isdir(pages_dir):
        add(FAIL, f"pagesDir 不存在：{pages_dir}", "改成页图实际所在目录（绝对路径）")
        return
    pics = [f for f in os.listdir(pages_dir) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
    add(OK if pics else FAIL, f"页图 {len(pics)} 张 → {pages_dir}")
    if cfg.get("serverBase"):
        host = cfg["serverBase"].split("//")[-1].split("/")[0].split(":")[0]
        if host not in ("127.0.0.1", "localhost"):
            add(WARN, f"config.json 里有 serverBase={cfg['serverBase']}",
                "外部模式不需要它，脚本也不会据此上传")


def main():
    argv = sys.argv[1:]
    course_dir = None
    if "--course" in argv:
        i = argv.index("--course")
        if i + 1 < len(argv):
            course_dir = os.path.abspath(argv[i + 1])
        else:
            raise SystemExit("--course 后面要跟课程目录")

    print("=" * 46)
    print("  英文绘本精品课 · 环境自检")
    print("=" * 46)
    check_python()
    check_pkg("requests", "requests", "上传/TTS 请求")
    ok_pil = check_pkg("PIL", "Pillow", "页图排版/裁图")
    check_cards(ok_pil)
    check_credentials()
    if course_dir:
        check_course(course_dir)

    print()
    for level, what, hint in rows:
        print(f"  {level:<4} {what}")
        if hint:
            print(f"       → {hint}")
    n_fail = sum(1 for r in rows if r[0] == FAIL)
    n_warn = sum(1 for r in rows if r[0] == WARN)
    print()
    if n_fail:
        print(f"结果：{n_fail} 项必须处理{'，另有 ' + str(n_warn) + ' 项提示' if n_warn else ''}。")
        sys.exit(1)
    print(f"结果：可以直接开工{'（' + str(n_warn) + ' 项提示可忽略）' if n_warn else ''}。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
