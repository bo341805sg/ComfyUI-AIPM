---
name: aipm-sd3-modern
description: Generate professional English natural-language prompts for Stable Diffusion 3/3.5 and modern T5-based image models, covering multiple subjects, typography, composition, optics, lighting, materials, restrained emphasis, and precise negatives.
---

# SD3 / 现代 T5 生图导演

## 模型适配原则

SD3/3.5 使用多文本编码器，优先完整、无歧义的英文自然语言和清楚的对象关系。不要沿用 SD1.x 的碎片标签墙；先让每个主体、动作、位置和文字唯一可解，再增加风格与画质。

## 正向提示结构

使用准确英文自然语言与少量视觉关键词：

1. 用完整主句声明主体、数量、动作、关系和场景。
2. 分别绑定每个主体的外观、服装、表情、手势和位置。
3. 描述前中后景、遮挡、比例、透视和视觉层级。
4. 指定 shot size, camera height, viewing angle, lens character, depth of field, focal plane 和 negative space。
5. 指定 motivated lighting：来源、方向、软硬、色温、明暗比、轮廓光和反射。
6. 指定皮肤、织物、金属、玻璃、木材和环境介质的真实响应。
7. 用具体完成度收尾：precise facial structure and eye focus, anatomically plausible hands and contact, nuanced skin microtexture, readable fabric weave, material-specific reflections, controlled highlights, clean shadow gradients, restrained sharpening。

## 强调与文字

- 依靠句法、前置顺序和描述精度突出重点。
- 只有目标实现明确支持时才使用少量温和 `(concept:weight)`；不要沿用 SD1 的标签墙。
- 图中文字必须逐字引用，同时规定语言、字体类别、位置、层级、颜色和版式。
- 复杂文字拆成少量短文本块，分别绑定载体和位置；不要用“some text”或“a slogan”代替实际内容。

## 负面提示

使用短而针对性的英文：anatomy failure, extra subjects, identity drift, incorrect costume, unreadable typography, unintended crop, flat lighting, plastic skin, muddy detail。不要用超长负面列表抵消含糊正向提示。

不要输出 API 参数、模型名、LoRA、steps、CFG 或分辨率设置。

## 质量门

检查多人属性是否串位、手与道具接触是否有动作逻辑、焦点与景深是否匹配、主辅光是否互相矛盾。`8K/masterpiece`不得替代以上检查。
