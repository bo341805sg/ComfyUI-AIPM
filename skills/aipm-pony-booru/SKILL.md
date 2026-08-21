---
name: aipm-pony-booru
description: Generate professional Pony-family prompts using score tags and disciplined booru vocabulary, with character priority, composition, anatomy safeguards, and concise negatives. Use for Pony Diffusion and Pony-derived checkpoints.
---

# Pony 专业标签导演

## 模型卡优先

Pony 衍生 checkpoint 的质量与 rating 约定可能变化。若模型卡提供前缀、负面 score 或 source/rating 标签，严格采用该卡；下列 V6 score 前缀只用于明确的 Pony V6 兼容模型。

## 标签顺序

1. 模型质量前缀：Pony V6 必须原样以 `score_9, score_8_up, score_7_up, score_6_up, score_5_up, score_4_up` 开头；不要同时堆叠 `masterpiece, best quality, 8k`。
2. 内容级别与人数：如适用，写 rating 与 `1girl/1boy/2girls`。
3. 主体身份：角色、物种、年龄段和最稳定识别特征。
4. 外观与服装：发型、眼睛、体型、服装部件、材质、道具。
5. 表演：动作、姿态、手势、视线、表情与主体关系。
6. 镜头与构图：景别、视角、动态透视、主体位置、景深。
7. 场景、光线、色彩、气氛和媒介风格。

## 专业化规则

- 使用规范、可识别的英文 booru 标签；避免把长篇中文直译成破碎伪标签。
- 把核心人物、动作、构图放在前半段；装饰性细节靠后。
- 质量不只依赖 score 标签，还要明确 clean linework, precise eye highlights, controlled shading, coherent anatomy, plausible hands, readable fabric folds, clean silhouette separation, atmospheric depth 等视觉结果。
- 只在前置顺序不足时对极少数关键标签使用温和权重；不堆叠括号。
- 多人画面必须分别绑定外观、动作、服装和位置，避免属性串人。

## 负面提示

以 `score_4, score_3, score_2, score_1` 等低质量项为基础时须符合目标 checkpoint 习惯，再补充任务相关错误：bad anatomy, malformed hands, extra digits, fused limbs, duplicate subject, identity drift, unreadable text, accidental crop。不要把 Pony score 标签套到 Illustrious。

## 质量门

标签必须能映射到常见 booru 概念；删掉自造伪标签。多人时按角色分块绑定发色、服装、动作、视线和画面位置；若无法可靠绑定，降低同时出现的人物和动作复杂度。
