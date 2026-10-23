# course.json 内容稿 schema

服务端字段长度上限（超了 400）：title/titleZh ≤80，en ≤400，zh ≤200，word ≤40，question ≤200，answer ≤80。

```jsonc
{
  "title": "Don't Open the Door",      // 英文书名，≤80
  "titleZh": "别开门",                  // 中文书名
  "cover": "03.jpg",                   // 封面文件名（必须在 pagesDir 里；可与 pages 重复）
  "pages": ["02.jpg", "03.jpg"],       // 内页图，按顺序；1..20 张；pageIndex 从 0 起对应这里
  "sentences": [
    {
      "en": "A wolf comes and knocks at the door.",   // 一条 = 一条音频，太长不好跟读
      "zh": "一只狼走过来，敲了敲门。",
      "pageIndex": 1                                   // 0 起，< 页数
    }
  ],
  "words": [
    {
      "word": "wolf",
      "zh": "狼",
      "phonetic": "/wʊlf/",          // 英式 IPA
      "sentenceIndex": 1             // 该词出自第几句（0 起）
    }
  ],
  "quizzes": [
    {
      "sentenceIndex": 1,            // 考哪一句；不必每句都配，但尽量每句一道
      "question": "Who comes to the door?",
      "questionZh": "谁来到门口？",
      "answer": "A wolf",            // 1–5 个词，考理解不考复述
      "accept": ["wolf", "a wolf", "the wolf"],  // 同义答案列表，全小写
      "keyWord": "wolf"              // 关联生词
    }
  ]
}
```

## 写稿原则（首例验证过）

- **角色台词从叙述里拆成独立句**（"…," he says. 单独成句），口播节奏好、跟读友好。
- 生词 10–12 个：Sight word + 核心名词/动词；抽象短语（at once / back）也保留，词图可画场景。
- 问答逐句出题，`accept` 要把孩子的常见说法都列上（带不带冠词、缩写与否），全小写。
- 译文按绘本原意，不直译也不扩写。

## 完整首例

`AI助学英语/产出/精品课-DontOpenTheDoor/course.json`（11 句 / 12 词 / 11 问答 / 7 页），新绘本照抄此结构。
