---
name: aipm-illustrious-booru
description: Generate professional Danbooru-style prompts for Illustrious, NoobAI, and compatible anime-tag models, with precise character binding, mandatory visual emphasis, composition, rendering quality, and model-appropriate negatives.
---

# Illustrious / NoobAI / Anima 标签导演

## 模型卡优先规则

- NoobAI XL 1.1 官方模型卡推荐 `masterpiece, best quality, newest, absurdres, highres, safe`，并规定人数/角色/系列/artist/special/general/other 的 caption 顺序。
- Illustrious 与 Anima 派生模型可能采用不同质量标签。只有目标为 NoobAI 兼容 checkpoint 时强制上述前缀；其他模型先遵循其模型卡，禁止把单一前缀冒充全系列官方规则。

## 不可省略的提交清单

每次正向提示词必须同时做到：

1. **质量口令**：NoobAI 兼容模型原样使用其推荐前缀；Illustrious/Anima 使用目标模型卡的质量标签。模型不明时使用保守的 `masterpiece, best quality, highres`，并仍补足具体画质。
2. **主体锚定**：人数、身份、稳定五官/发型/体型、服装和关键道具。
3. **表演可见**：动作、重心、手势、视线、表情或微表情至少覆盖三项。
4. **画面设计**：景别、机位/视角、主体位置或视觉动线、景深/透视。
5. **光色设计**：真实主光来源、光质、色温/主辅色、明暗或冷暖对比。
6. **材质设计**：至少写两种与画面相关的具体材质表现。
7. **画质落实**：至少四个具体可见标签，例如 detailed eyes, precise eye highlights, coherent anatomy, plausible hands, clean lineart, controlled shading, readable fabric folds, material-specific highlights, atmospheric perspective, crisp focal subject。只选与画面相关者。
8. **重点加权**：对 1–3 个真正关键的主体、动作或道具使用温和 `(concept:1.1–1.3)`；不得全词加权。

缺少任何一项都继续完善，不得提前输出。

## 标签编排

使用规范英文 Danbooru/booru 标签，顺序为：

1. 人数与主体类型。
2. 角色/作品标签（用户确实指定时）。
3. 加权后的核心身份、动作或道具。
4. 五官、发型、体型、服装分件、材质与配饰。
5. 表情、视线、口型、手势、动作、重心和人物互动。
6. portrait/full body, close-up/medium shot, from above/below, low angle, dutch angle, depth of field 等构图标签。
7. 场景、时间、天气、主光、轮廓光、色彩和气氛。
8. 材质与画质完成度标签。

不得使用 Pony 的 `score_9` 系列，除非目标 checkpoint 模型卡明确要求。不得用 masterpiece, best quality, 8k 代替具体画质设计。

## 多人物与参考图

- 分别绑定每个角色的位置、外观、动作、服装和视线，防止属性串人。
- 使用 `<Picture N>` 说明身份、服装、道具或构图职责；禁止融合不同人物五官。
- 修改任务只改变指定维度，未涉及的身份、服装、道具、构图和参考关系保持稳定。

## 负面提示

针对任务选择 bad anatomy, malformed hands, extra/missing digits, fused bodies, duplicate, wrong costume, identity drift, cross-eyed, flat lighting, muddy colors, plastic skin, unreadable text, accidental crop。保持精炼，不复制无关万能列表。

## 集成示例

输入：“雨夜未来都市，一名穿白色风衣的女侦探撑透明雨伞。”

合格结构示意（NoobAI）：`masterpiece, best quality, newest, absurdres, highres, safe, 1girl, solo, (young female detective:1.2), (white trench coat:1.15), (transparent umbrella:1.15), ... detailed eyes, precise eye highlights, coherent anatomy, plausible hands, readable fabric folds, wet translucent umbrella surface, low angle, medium shot, subject slightly off-center, depth of field, blue neon key light, warm storefront rim light, cool-warm contrast, wet pavement reflections, controlled highlights, atmospheric perspective, crisp focal subject`

示例只展示规则组合，不得照抄未被用户指定的五官或场景事实。
