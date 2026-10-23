# 生图 Prompt 模板与规则

## 风格串（每张图 prompt 开头复用）

```
Soft watercolor children's picture book illustration, warm pastel colors,
rounded cute characters, gentle and friendly, for kids aged 3-6.
```

## 结尾串（每张图 prompt 末尾必带）

```
Absolutely no text, no letters, no words anywhere in the image.
Main subjects centered, generous margins.
```

## 留白提示（按排版意图加在结尾前）

- 文字要放左上：`Keep the upper-left area as simple open sky.`
- 文字要放右上：`Keep the upper-right wall area simple and empty.`
- 内页素墙同理，指明哪一角。

## 角色描述串示例（《Don't open the door》首例）

写死复用，所有页一字不改：

- 兔妈妈：`a gentle white mother rabbit with tall ears, wearing a coral-pink dress and a small white apron, carrying a woven yellow basket`
- 小白兔（主角）：`a white rabbit boy with long ears, in a blue t-shirt and purple shorts`
- 小灰兔：`a grey rabbit boy in a green shirt with a red neckerchief`
- 小灰兔妹：`a grey rabbit girl in a white blouse with a pink bow`
- 狼（反派→滑稽化）：`a chubby goofy grey wolf with big round eyes and a silly toothy grin (funny, NOT scary), bushy tail, white tank top and brown shorts`

## 生成参数

| 项 | 值 | 原因 |
|---|---|---|
| size | `1536x1024` | 生图工具支持的最大横幅，裁 5:4 后仍有 1280 宽 |
| quality | `high` | 成品交付，不省这笔 |
| input_fidelity | `medium`（仅参考图页） | 保角色设计、放构图；`high` 连构图一起抄 |

## 生成顺序（角色一致性关键路径）

1. 盘点跨页复现的角色，每个角色选定一张"锚点页"（该角色最清晰的一页）先单独生成
2. 锚点图 Read 检查通过后，其余页 `image1` 传锚点图 + `input_fidelity: "medium"` 生成
3. **串行生成**：并发调用会返回同一个文件路径、互相覆盖（实测踩坑）
4. 每张立即 Read 检查四项：角色同款？无文字？留白可用？不吓人？

## 防侵权设计原则

- 换体色搭配（原书灰狼 → 重制胖灰狼+白背心，造型语言完全不同）
- 换服饰（颜色、款式组合避开原书）
- 换比例风格（原书瘦长水彩 → 圆胖低龄化）
- 不复刻原书特定构图/标志性元素
