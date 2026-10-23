#!/usr/bin/env python3
"""精品课构建与上传（english-course-producer skill 主脚本）。

用法：
    python build_course.py <course_dir>            # 预检 + 合成 + manifest（外部模式到此为止）
    python build_course.py <course_dir> --upload   # 上述 + 上传 + md5 回执 + 回读校验（仅作者本机）
    python build_course.py <course_dir> --verify   # 只对已上传的课做回读校验（审核通过后用）
可选：--base URL 覆盖服务端地址；--voice ID / --speed-normal X / --speed-slow X 临时覆盖音色语速；
      --allow-remote-upload 允许传给非本机服务端（默认只允许 127.0.0.1/localhost）。

两种模式：
- 作者模式（本机）：凭证在项目 server/.env，上传到 http://127.0.0.1:3100，落 pending 由作者后台过审。
- 外部模式（别人）：只在 ~/.english-course-producer/credentials.env 填自己的火山 key，**不加 --upload**，
  产出音频 + manifest + 线上绘本展示页即可；不需要服务端、不需要 COURSE_IMPORT_TOKEN。

注意：新版服务端导入的精品课默认 review_status=pending，要管理员审核通过才会进列表；
未通过审核时回读接口返回 404，脚本会打印 SKIP 而不是报错。

course_dir 里必须有两份文件：
    course.json   内容稿（schema 见 skill references/course-json.md）
    config.json   {slug, pagesDir, voice, speedNormal, speedSlow, serverBase, envFile}

设计要点：
- 音频目录按音色分（audio-bv506/ …），换音色绝不误用旧缓存；
- synth 幂等：目标文件已存在即复用，改文案重传不必重合成（删对应 mp3 可强制重合成）；
- externalId = {slug}-v1-{文本哈希8}，哈希只含文本 → 改文本=新课，改音色/语速=覆盖同一课；
- multipart 字段严格按 manifest 顺序 append（接口按到达顺序对齐，顺序错位不报错）。
"""
import base64
import hashlib
import json
import os
import sys
import time

import requests
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))

DEFAULT_SERVER = "http://127.0.0.1:3100"
USER_ENV = os.path.expanduser("~/.english-course-producer/credentials.env")
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
LIMITS = {  # 服务端字段长度上限（超了会 400）
    "title": 80, "titleZh": 80, "en": 400, "zh": 200,
    "word": 40, "question": 200, "answer": 80,
}


def md5(data):
    return hashlib.md5(data).hexdigest()


def load_env(path):
    env = {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def find_project_env():
    """作者本机模式探测：环境变量 ECP_PROJECT_ENV，或从当前目录向上找 ai-english/server/.env。

    刻意不写死绝对路径——发布出去的包里带上作者本机路径既暴露隐私，也会让别人误判模式。
    外部用户机器上没有这个文件，自然返回 None。
    """
    explicit = os.environ.get("ECP_PROJECT_ENV")
    if explicit and os.path.isfile(explicit):
        return explicit
    cur = os.path.abspath(os.getcwd())
    for _ in range(6):
        cand = os.path.join(cur, "ai-english", "server", ".env")
        if os.path.isfile(cand):
            return cand
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return None


def resolve_env_path(cfg):
    """凭证文件查找顺序：config.envFile → 环境变量 ECP_ENV_FILE → 作者机器项目 .env → 用户自备。

    config.json 里的 envFile 不存在时不再直接失败（外部用户常直接抄作者的 config），
    继续往后找，找到就用；一个都没有才报错并给出自备凭证的步骤。
    """
    cands = [cfg.get("envFile"), os.environ.get("ECP_ENV_FILE"), find_project_env(), USER_ENV]
    for p in cands:
        if p and os.path.isfile(p):
            return p
    return None


def upload_blockers(env_path, base, args):
    """上传只属于作者本机模式。返回拒绝原因列表；空列表才放行。

    两道闸：
    1. 凭证来自 ~/.english-course-producer/credentials.env（用户自备）→ 外部模式，不上传；
    2. 服务端不是本机 → 默认不上传（公网部署确有需要时显式加 --allow-remote-upload）。
    """
    why = []
    if env_path and os.path.abspath(env_path) == os.path.abspath(USER_ENV):
        why.append("凭证来自用户自备文件（外部使用者模式），本 skill 不提供上传")
    host = (urlparse(base).hostname or "").lower()
    if host not in LOCAL_HOSTS and "--allow-remote-upload" not in args:
        why.append(f"服务端不是本机（{base}）；确需传远端请显式加 --allow-remote-upload")
    return why


def speak_text(text):
    """给 TTS 的纯文本：去掉排版用的引号，保留句读。"""
    out = text.replace("\u201c", "").replace("\u201d", "").replace("\u2019", "'").replace("\u2018", "'")
    return " ".join(out.split())


def preflight(course):
    """防线 1：上传前本地预检，任何一项不过就拒绝继续。"""
    errs = []
    n_pages = len(course["pages"])
    for key, cap in LIMITS.items():
        if key in ("title", "titleZh") and len(course.get(key, "")) > cap:
            errs.append(f"{key} 超长（>{cap}）")
    if not (1 <= n_pages <= 20):
        errs.append(f"页数 {n_pages} 超出 1..20")
    for i, s in enumerate(course["sentences"]):
        if not s["en"].strip():
            errs.append(f"句 {i} en 为空")
        if len(s["en"]) > LIMITS["en"]:
            errs.append(f"句 {i} en 超长")
        if len(s.get("zh", "")) > LIMITS["zh"]:
            errs.append(f"句 {i} zh 超长")
        if not (0 <= s["pageIndex"] < n_pages):
            errs.append(f"句 {i} pageIndex 越界")
        if i < len(course["quizzes"]) and course["quizzes"][i].get("sentenceIndex") != i:
            pass  # 问答不必逐句都有，sentenceIndex 合法性在下面查
    for i, q in enumerate(course["quizzes"]):
        if not (0 <= q["sentenceIndex"] < len(course["sentences"])):
            errs.append(f"问答 {i} sentenceIndex 越界")
        if len(q["question"]) > LIMITS["question"] or len(q["answer"]) > LIMITS["answer"]:
            errs.append(f"问答 {i} question/answer 超长")
    for i, w in enumerate(course["words"]):
        if not (0 <= w["sentenceIndex"] < len(course["sentences"])):
            errs.append(f"词 {i} sentenceIndex 越界")
        if len(w["word"]) > LIMITS["word"]:
            errs.append(f"词 {i} word 超长")
    if errs:
        raise SystemExit("预检失败：\n  " + "\n  ".join(errs))


def is_mp3(data):
    return data[:3] == b"ID3" or (len(data) > 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0)


def synth(cfg, text, speed, tag, path=None):
    """合成并落盘；path 已存在则直接复用（幂等缓存）。"""
    if path and os.path.isfile(path):
        return open(path, "rb").read()
    body = json.dumps({
        "app": {"appid": cfg["_app"], "token": "access_token", "cluster": cfg["_cluster"]},
        "user": {"uid": "course-build"},
        "audio": {"voice_type": cfg["voice"], "encoding": "mp3", "speed_ratio": speed},
        "request": {"reqid": f"{tag}-{int(time.time() * 1000)}", "text": speak_text(text),
                    "text_type": "plain", "operation": "query"},
    }).encode()
    last = None
    for _ in range(3):
        try:
            r = requests.post(
                "https://openspeech.bytedance.com/api/v1/tts",
                data=body,
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer;{cfg['_atok']}"},
                timeout=45,
            )
            raw = r.json()
            if raw.get("code") == 3000 and raw.get("data"):
                data = base64.b64decode(raw["data"])
                if not is_mp3(data):
                    raise RuntimeError("返回内容不是 mp3")
                if path:
                    open(path, "wb").write(data)
                return data
            last = f"code={raw.get('code')} msg={raw.get('message')}"
        except Exception as exc:
            last = str(exc)
        time.sleep(1.5)
    raise RuntimeError(f"合成失败 {tag}: {last}")


def info(audio_dir, names):
    out = []
    for n in names:
        b = open(os.path.join(audio_dir, n), "rb").read()
        out.append({"file": n, "bytes": len(b), "md5": md5(b)})
    return out


def run():
    args = sys.argv[1:]
    do_upload = "--upload" in args
    do_verify = "--verify" in args
    args = [a for a in args if not a.startswith("--")]
    if not args:
        raise SystemExit(__doc__)
    course_dir = os.path.abspath(args[0])
    course = json.load(open(os.path.join(course_dir, "course.json"), encoding="utf-8"))
    cfg = json.load(open(os.path.join(course_dir, "config.json"), encoding="utf-8"))

    # CLI 覆盖
    for flag, key, cast in [("--base", "serverBase", str), ("--voice", "voice", str),
                            ("--speed-normal", "speedNormal", float), ("--speed-slow", "speedSlow", float)]:
        if flag in sys.argv:
            cfg[key] = cast(sys.argv[sys.argv.index(flag) + 1])

    env_path = resolve_env_path(cfg)
    if not env_path:
        print("找不到火山语音凭证，合不出音频。")
        print("  作者机器：config.json 里的 envFile 指向项目 server/.env（或直接留空，脚本会自动找）。")
        print("  外部使用者：走「只出音频和展示页」模式，只需要自己的火山 key——")
        print(f"    1) 建文件 {USER_ENV}")
        print("    2) 内容（去 console.volcengine.com/speech → 语音合成 取 APP ID / Access Token）：")
        print("         TTS_VOLC_APP_ID=你的appid")
        print("         TTS_VOLC_ACCESS_TOKEN=你的token")
        print("         TTS_VOLC_CLUSTER=volcano_tts")
        print("    3) 重跑本脚本（不加 --upload）→ 得到 manifest.json，再跑 make_review.py 出线上绘本展示页。")
        print("  外部模式不上传，也不需要 COURSE_IMPORT_TOKEN。")
        sys.exit(2)
    env = load_env(env_path)

    # 上传闸门前移：别等跑完一小时 TTS 才发现没权限上传
    if do_upload:
        early = upload_blockers(env_path, cfg.get("serverBase") or DEFAULT_SERVER, sys.argv)
        if early:
            print("\n=== 拒绝上传 ===")
            for b in early:
                print(f"  - {b}")
            print("  去掉 --upload 重跑即可，音频/展示页照样能生成。")
            sys.exit(3)
    print(f"凭证：{env_path}")
    missing = [k for k in ("TTS_VOLC_APP_ID", "TTS_VOLC_ACCESS_TOKEN") if not env.get(k)]
    if missing:
        print(f"凭证不全（{env_path} 缺 {', '.join(missing)}），合不出音频。")
        sys.exit(2)
    cfg["_app"] = env["TTS_VOLC_APP_ID"]
    cfg["_atok"] = env["TTS_VOLC_ACCESS_TOKEN"]
    cfg["_cluster"] = env.get("TTS_VOLC_CLUSTER", "volcano_tts")
    cfg.setdefault("serverBase", DEFAULT_SERVER)
    base = cfg["serverBase"]
    speed_n, speed_s = cfg["speedNormal"], cfg["speedSlow"]

    preflight(course)
    print(f"预检通过：{len(course['sentences'])} 句 / {len(course['words'])} 词 / "
          f"{len(course['quizzes'])} 问答 / {len(course['pages'])} 页")

    # 音频目录按音色分，切音色不会误用旧缓存
    audio_dir = os.path.join(course_dir, f"audio-{cfg['voice'].split('_')[0].lower()}")
    os.makedirs(audio_dir, exist_ok=True)

    sentences, words, quizzes = course["sentences"], course["words"], course["quizzes"]

    print(f"\n=== 1. 合成语音（{cfg['voice']}，正句 {speed_n} / 慢速 {speed_s}）===")
    sent_files, slow_files = [], []
    for i, s in enumerate(sentences):
        name = f"s{i:02d}.mp3"
        data = synth(cfg, s["en"], speed_n, f"s{i:02d}", path=os.path.join(audio_dir, name))
        sent_files.append(name)
        cached = "(缓存)" if os.path.isfile(os.path.join(audio_dir, name)) and len(data) == os.path.getsize(os.path.join(audio_dir, name)) else ""
        print(f"  句 {i:>2} 正句 {len(data):>7d}B {cached}  {s['en'][:52]}")
        slow_name = f"s{i:02d}-slow.mp3"
        slow = synth(cfg, s["en"], speed_s, f"s{i:02d}s", path=os.path.join(audio_dir, slow_name))
        slow_files.append(slow_name)
        print(f"  句 {i:>2} 慢速 {len(slow):>7d}B")

    word_files = []
    for i, w in enumerate(words):
        name = f"w{i:02d}.mp3"
        data = synth(cfg, w["word"], speed_n, f"w{i:02d}", path=os.path.join(audio_dir, name))
        word_files.append(name)
        print(f"  词 {i:>2} {w['word']:<12} {len(data):>7d}B")

    quiz_q, quiz_a = [], []
    for i, q in enumerate(quizzes):
        qn, an = f"q{i:02d}-question.mp3", f"q{i:02d}-answer.mp3"
        qd = synth(cfg, q["question"], speed_n, f"q{i:02d}q", path=os.path.join(audio_dir, qn))
        ad = synth(cfg, q["answer"], speed_n, f"q{i:02d}a", path=os.path.join(audio_dir, an))
        quiz_q.append(qn)
        quiz_a.append(an)
        print(f"  问答 {i:>2} Q {len(qd):>6d}B  A {len(ad):>6d}B  {q['question'][:40]}")

    # 音频魔数复查（防线 1）
    for n in sent_files + slow_files + word_files + quiz_q + quiz_a:
        if not is_mp3(open(os.path.join(audio_dir, n), "rb").read(3)):
            raise SystemExit(f"预检失败：{n} 不是 mp3")

    print("\n=== 2. 生成 manifest ===")
    content_sig = json.dumps(
        {
            "sentences": [s["en"] for s in sentences],
            "words": [w["word"] for w in words],
            "quizzes": [[q["question"], q["answer"]] for q in quizzes],
        },
        ensure_ascii=False, sort_keys=True,
    )
    h8 = hashlib.sha256(content_sig.encode()).hexdigest()[:8]
    external_id = f"{cfg['slug']}-v1-{h8}"

    # 词图：words/ 下 w00.jpg… 与 words 顺序一一对应；全齐才带上（全有或全无）
    words_dir = os.path.join(course_dir, "words")
    picture_files = [os.path.join(words_dir, f"w{i:02d}.jpg") for i in range(len(words))]
    have_pictures = len(words) > 0 and all(os.path.isfile(p) for p in picture_files)
    if not have_pictures and any(os.path.isfile(p) for p in picture_files):
        print("  ⚠️ 词图不全（要么全齐要么全不传），本次不带词图")

    manifest = {
        "title": course["title"],
        "titleZh": course["titleZh"],
        "externalId": external_id,
        "voice": cfg["voice"],
        "speed": {"normal": speed_n, "slow": speed_s},
        "pages": course["pages"],
        "cover": course["cover"],
        "sentences": [
            {**{k: s[k] for k in ("en", "zh", "pageIndex")}, "audio": sent_files[i], "slow": slow_files[i]}
            for i, s in enumerate(sentences)
        ],
        "words": [
            {**{k: w[k] for k in ("word", "zh", "phonetic", "sentenceIndex")}, "audio": word_files[i]}
            for i, w in enumerate(words)
        ],
        "quizzes": [
            {**q, "questionAudio": quiz_q[i], "answerAudio": quiz_a[i]}
            for i, q in enumerate(quizzes)
        ],
        "audio": {
            "sentences": info(audio_dir, sent_files),
            "slow": info(audio_dir, slow_files),
            "words": info(audio_dir, word_files),
            "quizQuestion": info(audio_dir, quiz_q),
            "quizAnswer": info(audio_dir, quiz_a),
        },
        "wordPictures": [
            {"file": f"w{i:02d}.jpg", "bytes": os.path.getsize(p), "md5": md5(open(p, "rb").read())}
            for i, p in enumerate(picture_files)
        ] if have_pictures else [],
    }
    json.dump(manifest, open(os.path.join(course_dir, "manifest.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    total = sum(x["bytes"] for v in manifest["audio"].values() for x in v)
    print(f"  externalId = {external_id}")
    print(f"  音频 {sum(len(v) for v in manifest['audio'].values())} 条，共 {total / 1024 / 1024:.2f} MB")

    if do_verify:
        res_path = os.path.join(course_dir, "upload-result.json")
        if not os.path.exists(res_path):
            print("\n还没上传过（没有 upload-result.json），没法回读校验。")
            sys.exit(1)
        up = json.load(open(res_path, encoding="utf-8"))
        print("\n=== 回读校验（--verify）===")
        print(f"  课号 {up['id']}")
        n = verify_course(base, up["id"], manifest, quizzes, have_pictures)
        print(f"\n=== 汇总：{'全部通过' if n == 0 else f'{n} 项未通过'} ===")
        sys.exit(1 if n else 0)

    if not do_upload:
        print("\n（未上传）外部模式到此为止：把课程目录 + 线上绘本展示.html 交回作者即可。")
        print("（作者本机要入库，再跑一次加 --upload）")
        return

    print(f"\n=== 3. 上传 → {base} ===")
    # 服务端自检：进程半夜退出过（笔记本休眠/被中断），直接 POST 只会拿到 ECONNRESET 白跑一轮
    try:
        h = requests.get(f"{base}/api/health", timeout=8).json()
        if not h.get("ok"):
            raise ValueError("health 返回非 ok")
    except Exception:
        srv = os.path.dirname(env_path or "")
        print(f"  FAIL  服务端没起来（{base}/api/health 不通），先启动再上传：")
        print(f"        cd {srv} && npm start  （作者机器：项目内 ai-english/server）")
        print("        常见原因：机器休眠、上次进程被中断、端口被占")
        print("        外部使用者：本 skill 不提供上传，去掉 --upload 跑到展示页即可")
        sys.exit(1)
    token = env.get("COURSE_IMPORT_TOKEN")
    if not token:
        print("  .env 里没有 COURSE_IMPORT_TOKEN，传不了。先在服务端配好再跑 --upload。")
        print("  （只想出音频和展示页的话，不加 --upload 即可，不需要 token）")
        sys.exit(2)
    pages_dir = cfg["pagesDir"]
    files = [("cover", (course["cover"], open(os.path.join(pages_dir, course["cover"]), "rb").read(), "image/jpeg"))]
    for i, n in enumerate(course["pages"]):
        files.append(("page", (f"page{i}.jpg", open(os.path.join(pages_dir, n), "rb").read(), "image/jpeg")))
    for n in sent_files:
        files.append(("audio", (n, open(os.path.join(audio_dir, n), "rb").read(), "audio/mpeg")))
    for n in slow_files:
        files.append(("slow", (n, open(os.path.join(audio_dir, n), "rb").read(), "audio/mpeg")))
    for n in word_files:
        files.append(("wordAudio", (n, open(os.path.join(audio_dir, n), "rb").read(), "audio/mpeg")))
    if have_pictures:
        for i, p in enumerate(picture_files):
            files.append(("picture", (f"w{i:02d}.jpg", open(p, "rb").read(), "image/jpeg")))
    for n in quiz_q:
        files.append(("quizQuestionAudio", (n, open(os.path.join(audio_dir, n), "rb").read(), "audio/mpeg")))
    for n in quiz_a:
        files.append(("quizAnswerAudio", (n, open(os.path.join(audio_dir, n), "rb").read(), "audio/mpeg")))

    data = {
        "title": course["title"],
        "titleZh": course["titleZh"],
        "externalId": external_id,
        "sentences": json.dumps(
            [
                {"en": s["en"], "zh": s["zh"], "leadIn": f"Listen. {s['en']}", "pageIndex": s["pageIndex"]}
                for s in sentences
            ],
            ensure_ascii=False,
        ),
        "words": json.dumps(words, ensure_ascii=False),
        "quizzes": json.dumps(quizzes, ensure_ascii=False),
    }
    r = None
    for attempt in range(3):
        try:
            r = requests.post(f"{base}/api/official-courses", headers={"X-Import-Token": token},
                              data=data, files=files, timeout=180)
            break
        except requests.exceptions.RequestException as e:
            left = 3 - attempt - 1
            print(f"  第 {attempt + 1} 次上传中断（{type(e).__name__}）" + (f"，{3 * 2 ** attempt}s 后重试" if left else ""))
            if not left:
                print("  连续 3 次失败：检查服务端进程（npm start）与磁盘空间后重跑 --upload")
                sys.exit(1)
            time.sleep(3 * 2 ** attempt)
    print(f"  HTTP {r.status_code}")
    body = r.json()
    if not body.get("ok"):
        print(f"  失败：{r.text[:500]}")
        sys.exit(1)
    payload = body["data"]
    print(f"  课号 {payload['id']}  replaced={payload.get('replaced')}")
    json.dump(payload, open(os.path.join(course_dir, "upload-result.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    print("\n=== 4. md5 回执核对 ===")
    pairs = [
        ("audioDigests", "sentences"), ("slowDigests", "slow"),
        ("wordAudioDigests", "words"),
        ("quizQuestionAudioDigests", "quizQuestion"), ("quizAnswerAudioDigests", "quizAnswer"),
    ]
    bad = 0
    for key, sig_key in pairs:
        want = [x["md5"] for x in manifest["audio"][sig_key]]
        got = payload.get(key)
        ok = got == want
        bad += 0 if ok else 1
        print(f"  {'PASS' if ok else 'FAIL'}  {key}  {len(want)} 条")
        if not ok:
            for i, (a, b) in enumerate(zip(want, got or [])):
                if a != b:
                    print(f"        第 {i} 条不一致")
    if have_pictures:
        want = [x["md5"] for x in manifest["wordPictures"]]
        got = payload.get("pictureDigests")
        ok = got == want
        bad += 0 if ok else 1
        print(f"  {'PASS' if ok else 'FAIL'}  pictureDigests  {len(want)} 张")
        if not ok:
            for i, (a, b) in enumerate(zip(want, got or [])):
                if a != b:
                    print(f"        第 {i} 张不一致: 本地 {a} 服务端 {b}")

    print("\n=== 5. 回读校验 ===")
    bad += verify_course(base, payload["id"], manifest, quizzes, have_pictures)

    print(f"\n=== 汇总：{'全部通过' if bad == 0 else f'{bad} 项未通过'} ===")
    print(f"课号 {payload['id']}，externalId {external_id}")


def verify_course(base, mid, manifest, quizzes, have_pictures):
    """回读校验：句子/音频/单词/问答是否都按上传的落库。返回失败项数。

    课还没过审核时服务端返回 404（canStudy 只放 approved），这种情况打印 SKIP 并返回 0，
    让它成为「等审核」而不是「校验失败」。
    """
    dev = {"X-Device-Id": "build-device-check"}
    bad = 0
    r_det = requests.get(f"{base}/api/materials/{mid}", headers=dev, timeout=20)
    body = r_det.json()
    if not body.get("ok"):
        if r_det.status_code == 404:
            print("  SKIP  课已入库，但仍待审核（review_status=pending）")
            print(f"        审核通过后再跑：python build_course.py <course_dir> --verify")
            print(f"        审核接口：POST {base}/api/admin/courses/{mid}/approve（需 X-Admin-Token）")
            return 0
        print(f"  FAIL  回读失败：{r_det.text[:300]}")
        return 1
    det = body["data"]
    print(f"  句子 {len(det['sentences'])} 条 / 单词 {len(det['words'])} 个 / 页图 {len(det['pageImages'])} 张")
    miss = [s["idx"] for s in det["sentences"] if not s.get("audioFile")]
    print(f"  {'PASS' if not miss else 'FAIL'}  每句都有 audioFile" + (f"（缺 {miss}）" if miss else ""))
    miss_slow = [s["idx"] for s in det["sentences"] if not s.get("plainAudio")]
    print(f"  {'PASS' if not miss_slow else 'FAIL'}  每句都有跟读音频" + (f"（缺 {miss_slow}）" if miss_slow else ""))
    bad += len(miss) + len(miss_slow)

    for idx in range(0, len(det["sentences"]), max(1, len(det["sentences"]) // 3)):
        s = det["sentences"][idx]
        if not s.get("audioFile"):
            continue
        got = requests.get(f"{base}/api/audio/{s['audioFile']}", headers=dev, timeout=30).content
        ok = md5(got) == manifest["audio"]["sentences"][idx]["md5"]
        bad += 0 if ok else 1
        print(f"  {'PASS' if ok else 'FAIL'}  第 {idx} 句音频与本地一致（{len(got)}B）")

    for widx in range(0, len(det["words"]), max(1, len(det["words"]) // 2)):
        if widx >= len(det["words"]):
            continue
        w = det["words"][widx]
        rw = requests.post(f"{base}/api/words/{w['id']}/audio", headers=dev, timeout=40).json()
        af = rw.get("data", {}).get("audioFile")
        if not af:
            print(f"  FAIL  单词 {w['word']} 没有返回音频")
            bad += 1
            continue
        got = requests.get(f"{base}/api/audio/{af}", headers=dev, timeout=30).content
        ok = md5(got) == manifest["audio"]["words"][widx]["md5"]
        bad += 0 if ok else 1
        print(f"  {'PASS' if ok else 'FAIL'}  单词 {w['word']} 播的是上传音频")

    qz = requests.post(f"{base}/api/quizzes/ensure", json={"materialId": mid},
                       headers=dev, timeout=40).json().get("data", {}).get("quizzes", [])
    ok = len(qz) == len(quizzes)
    print(f"  {'PASS' if ok else 'FAIL'}  问答 {len(qz)} 道（期望 {len(quizzes)}）")
    bad += 0 if ok else 1
    if qz:
        q0 = qz[0]
        same = q0.get("question") == quizzes[0]["question"]
        print(f"  {'PASS' if same else 'FAIL'}  问答未被服务器改写")
        bad += 0 if same else 1
        for part, sig_key, label in [("question", "quizQuestion", "题目"), ("answer", "quizAnswer", "答案")]:
            rp = requests.post(f"{base}/api/quizzes/{q0['id']}/audio", json={"part": part},
                               headers=dev, timeout=40).json()
            af = rp.get("data", {}).get("audioFile")
            if not af:
                print(f"  FAIL  {label}语音没返回")
                bad += 1
                continue
            got = requests.get(f"{base}/api/audio/{af}", headers=dev, timeout=30).content
            ok = md5(got) == manifest["audio"][sig_key][0]["md5"]
            bad += 0 if ok else 1
            print(f"  {'PASS' if ok else 'FAIL'}  第 1 道问答{label}播的是上传音频")

    return bad


if __name__ == "__main__":
    run()
