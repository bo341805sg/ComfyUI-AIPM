---
name: aipm-sd-weighted
description: Generate professional English prompts for Stable Diffusion 1.x and base SDXL, including restrained emphasis weights, composition, image-quality detail, and task-specific negative prompts. Use for SD1 and SDXL prompt profiles.
---

# Stable Diffusion 专业加权提示词

## 基础模型与微调模型分离

- SD1.x/基础 SDXL 没有统一官方 `masterpiece` 质量口令；仅当目标 checkpoint 的模型卡明确要求时才使用其前缀。
- A1111/kohya 风格实现支持 `(term:1.2)` 等权重，但这属于推理前端语法，不保证每条管线都支持。当前节点仅在已确认的 SD 工作流中输出，并保持克制。
- 高质量主要来自具体主体、合理构图、匹配训练分布的风格词、清楚光线与材质，而不是无限追加分辨率词。

## 先判断分支

- SD1.x：使用紧凑英文逗号标签，语义短、顺序强、避免复杂长句。
- SDXL：使用英文短语与自然语言片段混合，允许更完整的空间、摄影和材质描述。

## 正向提示结构

若已知 checkpoint 模型卡给出质量前缀，则原样置于开头；未知基础模型不自动添加。随后按顺序生成：

1. 主体锚点：人数、身份、年龄段、关键外观。
2. 核心行为与关系：动作、手部接触、视线和主体间空间关系。
3. 造型：五官、发型、服装剪裁、材质、道具。
4. 构图：景别、视角、机位高度、焦段感、主体位置、景深。
5. 场景：前景、中景、背景与时间天气。
6. 光色：主光、轮廓光、色温、对比、曝光和调色。
7. 完成度：precise eye focus, plausible hands and contact, coherent anatomy, fine fabric weave, material-specific reflections, controlled highlights, clean tonal separation, restrained sharpening 等可见结果。

## 加权规则

- 只对 1–3 个真正关键概念使用 `(term:1.1–1.3)`。
- 身份、关键道具或核心动作可加权；不要给每个标签加权。
- 权重不能代替清晰描述，不使用极端值，不嵌套多层括号。
- SDXL 优先靠清楚句法和前置顺序控制；只有重点仍易丢失时才加权。

## 负面提示

按任务选择：解剖/手部错误、主体重复、身份漂移、服装错位、焦点失败、材质塑料感、文字乱码、构图裁切。不要机械复制超长通用负面词；不要用负面词反向描述用户想要的内容。

## 禁止

不要添加模型、LoRA、采样器、CFG、步数或分辨率参数。不要用互相冲突的镜头、光线或风格标签。不要仅以 masterpiece, best quality, 8k 代替具体画质设计。

## 长度控制

SD1.x 保留高信息密度短标签，把主体和核心动作放在截断风险最低的前部；SDXL 可用较完整短语，但删除同义重复。负面提示只处理最可能的失败，不承担补写正向构图的职责。
