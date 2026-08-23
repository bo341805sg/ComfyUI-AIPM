---
name: aipm-qwen-image-edit
description: Rewrite Qwen Image single- and multi-image edit requests into direct Chinese instructions with explicit sources, targets, preservation, and consistency rules.
---

# Qwen Image 编辑导演

## 强制规则

1. 先写编辑动作、目标对象和目标位置，再写来源与保留项；不把编辑任务重写成全新文生图描述。
2. 单图编辑明确“修改什么”和“其余保持不变”。保留未涉及的人物身份、服装、姿势、构图、背景、光线和文字。
3. 多图编辑逐张绑定：`<Picture 1>`、`<Picture 2>`……分别说明取用的元素、放入位置和禁止继承的内容。
4. 多人物任务为每个人指定唯一身份来源，禁止融合五官；身份参考优先于服装和风格参考。
5. 指令矛盾时做最小必要修复；信息不足只补充保证空间和操作可执行所需的细节。

## 综合范式

`以 <Picture 1> 为基础图，只把画面右侧男性的身份替换为 <Picture 2> 中的男性，保持其原有站位、姿势和黑色外套；左侧女性完全不变。仅采用 <Picture 3> 的银色手提箱替换男性右手中的道具，不继承 <Picture 2> 和 <Picture 3> 的背景、构图或其他人物。`

## 质量门

每张输入图都有明确职责；来源、目标和保留项无歧义；不同人物身份没有交叉；未请求区域不会因重复描述而漂移。
