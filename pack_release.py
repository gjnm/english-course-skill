#!/usr/bin/env python3
"""把 ~/.workbuddy/skills 里的两个技能同步到本仓库并打成发布 zip。

用法：
    python3 pack_release.py

做三件事：
    1. 把两个技能（脱敏后）写到 ./skills/ —— 这是仓库里的发布快照，可直接提交
    2. 按仓库内容打 zip 到 ../english-course-skills-v<版本>.zip
    3. 自检：无作者路径残留、无真实凭证文件、关键文件齐全

版本号从 english-course-producer/SKILL.md 的 version 字段读，不在这里手写。
"""
import os
import re
import shutil
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.dirname(HERE)
SRC_SKILLS = os.path.expanduser("~/.workbuddy/skills")
SKILLS = ["english-course-producer", "english-picturebook-cards"]
PRODUCER = "english-course-producer"

AUTHOR_ROOT = "/Users/a1/Desktop/高健个人空间/育儿自媒体项目/AI助学英语"
AUTHOR_PY = "/Users/a1/.workbuddy/binaries/python/envs/default/bin/python"
AUTHOR_HOME = "/Users/a1/"

TEXT_EXT = (".md", ".py", ".json", ".sh", ".ps1", ".env", ".txt")
SKIP_DIRS = {"__pycache__", ".git", ".idea", "_stage"}
SKIP_NAMES = {".DS_Store", "pack_release.py", ".gitignore"}

# 发布前自检：出现这些就说明脱敏没做干净
LEAK_MARKERS = ["/Users/a1", AUTHOR_ROOT]
FORBIDDEN_NAMES = {"credentials.env", ".env"}
REQUIRED = [
    "README.md",
    "install.sh",
    "install.ps1",
    f"skills/{PRODUCER}/SKILL.md",
    f"skills/{PRODUCER}/scripts/build_course.py",
    f"skills/{PRODUCER}/scripts/check_env.py",
    f"skills/{PRODUCER}/scripts/make_review.py",
    "skills/english-picturebook-cards/scripts/layout_pages.py",
]


def read_version():
    p = os.path.join(SRC_SKILLS, PRODUCER, "SKILL.md")
    body = open(p, encoding="utf-8").read()
    m = re.search(r'^version:\s*"([^"]+)"', body, re.M)
    if not m:
        raise SystemExit("读不到 SKILL.md 的 version 字段")
    return m.group(1)


def scrub(text):
    """去掉作者本机痕迹：项目路径、托管 python 绝对路径、家目录。"""
    text = text.replace(AUTHOR_ROOT, "<项目根>")
    text = text.replace(AUTHOR_PY, "python3")
    text = text.replace(AUTHOR_HOME, "~/")
    return text


def copy_tree(src, dst):
    """复制并顺带脱敏文本文件；返回写出的文件数。"""
    n = 0
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        rel = os.path.relpath(root, src)
        target_dir = dst if rel == "." else os.path.join(dst, rel)
        os.makedirs(target_dir, exist_ok=True)
        for name in files:
            if name in SKIP_NAMES:
                continue
            sp = os.path.join(root, name)
            tp = os.path.join(target_dir, name)
            if name.lower().endswith(TEXT_EXT):
                with open(sp, encoding="utf-8") as f:
                    data = scrub(f.read())
                with open(tp, "w", encoding="utf-8") as f:
                    f.write(data)
            else:
                shutil.copy2(sp, tp)
            n += 1
    return n


def main():
    for s in SKILLS:
        if not os.path.isdir(os.path.join(SRC_SKILLS, s)):
            raise SystemExit(f"源目录不存在：{os.path.join(SRC_SKILLS, s)}")

    version = read_version()
    stage_name = f"english-course-skills-v{version}"

    # 1. 同步到仓库根
    skills_dst = os.path.join(HERE, "skills")
    if os.path.isdir(skills_dst):
        shutil.rmtree(skills_dst)
    total = 0
    for s in SKILLS:
        total += copy_tree(os.path.join(SRC_SKILLS, s), os.path.join(skills_dst, s))

    # 2. 从仓库内容打 zip（顶层套一个版本目录，解压后不会散一地）
    out_zip = os.path.join(OUT_DIR, f"{stage_name}.zip")
    packed = []
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(HERE):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for name in sorted(files):
                if name in SKIP_NAMES or name.endswith(".zip"):
                    continue
                p = os.path.join(root, name)
                arc = os.path.join(stage_name, os.path.relpath(p, HERE))
                z.write(p, arc)
                packed.append(arc.replace(os.sep, "/"))

    # 3. 自检
    problems = []
    with zipfile.ZipFile(out_zip) as z:
        names = z.namelist()
        for n in names:
            if os.path.basename(n) in FORBIDDEN_NAMES:
                problems.append(f"包含真实凭证文件：{n}")
            if n.lower().endswith(TEXT_EXT):
                body = z.read(n).decode("utf-8", "ignore")
                for marker in LEAK_MARKERS:
                    if marker in body:
                        problems.append(f"未脱敏（{marker}）：{n}")
                        break
        for must in REQUIRED:
            if not any(n.endswith("/" + must) for n in names):
                problems.append(f"缺文件：{must}")

    size = os.path.getsize(out_zip) / 1024
    print(f"同步 {total} 个技能文件 → {skills_dst}")
    print(f"打包 {len(names)} 项 / {size:.0f} KB → {out_zip}")
    print(f"版本 {version}（来自 SKILL.md）")
    if problems:
        print("\n自检发现问题：")
        for p in problems:
            print("  -", p)
        raise SystemExit(1)
    print("自检通过：无作者路径残留、无真实凭证文件、关键文件齐全。")


if __name__ == "__main__":
    main()
