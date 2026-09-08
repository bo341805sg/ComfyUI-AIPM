---
name: aipm-anima
description: Generate model-native Anima Base, Preview, and Turbo image prompts using Danbooru tags, natural language, or a deliberate hybrid, with strict framing, character binding, composition, and crop prevention. Use only for the CircleStone Labs/Comfy Org Anima image-model family, not SDXL, Illustrious, NoobAI, or Pony.
---

# Anima 图像提示词导演

Anima 是独立的动漫/插画模型家族，不是 SDXL、Illustrious、NoobAI 或 Pony checkpoint。它理解 Danbooru 风格标签、自然语言及二者混合。不要套用 SDXL 的 CLIP 截断思路，也不要默认复制 Pony 的 `score_9, score_8_up` 前缀。

## 提交前硬性检查

每次输出必须满足：

1. 忠实保留用户指定的人数、身份、年龄段、身体特征、服装、动作、场景、画幅和安全等级，不擅自改写核心意图。
2. 只使用一套互不冲突的景别。不得同时出现 `full body` 与 `portrait`、`upper body`、`cowboy shot`、`close-up` 等竞争标签。
3. 构图要求放在局部五官、胸部、手部、服饰纹理等细节之前。局部细节不能抢走用户指定的景别。
4. 标签使用小写和空格；只有模型原生 score 标签保留下划线。角色、作品与 artist 仅在用户确实指定时写入，artist 使用 `@name`。
5. 数字权重最多用于 1–3 个决定性概念。若用户指定严格景别，景别优先于局部身体特征获得强调。
6. 正向提示必须承担主体、空间和构图约束；不要依赖负向提示补写正向内容。Turbo 常用低 CFG，负向提示的作用可能较弱。
7. 删除同义堆叠、相互矛盾的姿势、镜头和画质词。不得为了“丰富”而添加用户没要求的人物、道具、文字、背景或服装。

## 选择提示形式

- 简单单人、常见动作和常见构图：以模型熟悉的英文标签为主。
- 精确空间关系、多人物互动、严格取景、复杂道具或叙事画面：使用“标签头 + 1–3 句英文自然语言”的混合形式。
- 纯自然语言：按需说明主体/动作与空间/构图，不限定句数；不要只写泛化审美形容词。

推荐标签顺序：

1. 质量、年代、meta、安全等级。
2. 人数与主体类型，如 `1girl, solo`、`1boy`、`2girls`。
3. 角色、作品、artist（只有明确指定时）。
4. 核心动作与严格构图。
5. 外观、体型、服装、表情、视线、手势和接触关系。
6. 场景、前中后景、机位、光线、色彩、材质和画质完成度。
7. 需要时追加完整英文自然语言空间契约。

## 质量与版本

- Anima 支持 `masterpiece/best quality/...` 人工质量标签，也支持 `score_9 ... score_1` 审美标签；不要把两套标签全部堆满。
- 目标版本或工作流给出推荐前缀时原样遵循。版本不明时使用保守公共前缀 `masterpiece, best quality, highres, safe`，再补足具体可见画质。
- `highres`、`absurdres`、`official art`、`anime screenshot` 属于不同 meta/风格信号，按目标画面选择，不机械全加。
- Base/Preview 通常允许更高 CFG 和更多步数；Turbo 的采样参数由工作流控制，提示词不得写入 steps、CFG、sampler 或 scheduler。

## 严格景别契约

### 全身图

用户出现“全身、全身像、完整人物、从头到脚、脚要看到、full body、head-to-toe、full-length”等意图时，正向提示必须同时具备：

- 主景别：`(full body:1.2)` 或 `full body`。
- 完整性：`head-to-toe, entire figure visible, both feet visible`。
- 镜头距离/落地关系：`long shot, standing on the ground`；坐姿或躺姿则改成符合动作的完整身体接触关系。
- 边界留白：自然语言明确头顶上方和脚底下方都有画内空间，身体任何部分不得出框。

负向提示至少包含：`cropped, accidental crop, cropped feet, feet out of frame, lower body out of frame, close-up, upper body`。若用户要求身体其他部分必须完整可见，增加对应的 `out of frame` 项。

全身要求不允许只写一个孤立的 `full body`。不得在其后加入 `portrait`、`medium shot`、`cowboy shot` 或强调局部特征的镜头语言。

### 半身、头像和特写

- 半身：明确裁切位置和需保留的手臂/手部，不使用 full-body 完整性标签。
- 头像/特写：明确脸部、肩颈或胸像边界，不意外承诺脚部可见。
- 用户没指定景别时，根据动作可读性选择最低足够景别；复杂肢体动作优先更宽构图。

## 多人物与空间关系

- 每个人分别写人数/位置、外观、服装、动作、视线和接触对象；禁止把不同人物属性混写成一串。
- 使用 left/right、foreground/background、behind/beside 等可见关系，并用自然语言消除标签无法表达的主客体歧义。
- 多人物全身图保持所有人物完整入画；允许用户要求的拥抱、接触与合理遮挡，明确肢体归属，不能为避免融合强行分开人物。负向按风险选 `fused bodies, duplicate person, cropped character`。

## 参考图

使用 `<Picture N>` 逐张分配身份、服装、姿势、道具、场景或风格职责。只继承指定属性；明确拒绝无关背景、构图、文字和其他人物。多人物参考不得融合五官或互换服装。

## 负向提示

只针对最可能失败的维度：解剖/手脚、重复主体、身份或服装串位、文字水印、构图裁切、光色或材质失败。用户要求严格景别时，裁切负向是必需项；否则不要机械附加与画面无关的超长万能列表。

## 集成示例

用户要求：“纯色背景，女性正面站立，全身图。”

正向结构：

`masterpiece, best quality, highres, safe, 1girl, solo, (full body:1.2), head-to-toe, entire figure visible, both feet visible, long shot, standing on the ground, front view, centered composition, simple background, ... . A full-length character illustration with clear space above her head and below both feet. Her complete body remains inside the frame without any crop.`

负向结构：

`cropped, accidental crop, cropped feet, feet out of frame, lower body out of frame, upper body, close-up, bad anatomy, malformed hands, malformed feet`

反例：

`1girl, detailed face, large eyes, detailed chest, full body, portrait, medium shot`

反例同时强调局部并混入竞争景别，极易把全身要求压缩成半身图，禁止输出。
