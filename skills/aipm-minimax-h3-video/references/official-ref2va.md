# Official Ref2VA contract (distilled)

Apply only when free image, video, or audio references are used. Output exactly these six sections in this order. Never use the Base three-field format.

```text
subject_definitions:
summary:
retention_analysis:
detailed_description:
overall_soundscape:
non_diegetic_music:
```

- `<Subject N>` is reusable visible content: a person, animal, object, scene, clothing, prop, style, action, expression, or pose.
- `<Picture N>` is standalone only when the whole image supplies a concrete keyframe or composition anchor. When an image merely defines a subject, cite it inside that subject definition instead of duplicating it as a Picture anchor.
- `<Video N>` supplies whole-video editing, continuation, temporal, action, or camera structure. Its embedded sound does not automatically create `<Audio N>`.
- `<Audio N>` supplies copied or referenced audio. Video and Audio numbering are independent.
- One subject may be defined by several assets and one asset may define several subjects. Use only references active for this segment.
- `summary` begins with the accurate combination of: `keyframe completion`, `reference generation`, `video editing`, `video continuation`, `audio reuse`, `audio reference`. Merely receiving a video or audio asset does not prove that task type.
- `retention_analysis` uses only `fully_preserved`, `partially_preserved`, `attribute_transfer`, `weak_reference`; audio uses `fully_copy`, `partially_copy`, `reference`, `weak_reference`. State inherited attributes and excluded background, pose, framing, or unrelated content.
- `detailed_description` uses `[Shot 1]`, timed later shots, stable `(SN)` speakers, `<d>[Language] ...</d>`, `<scenetrans>`, and `<cutoff>` under the same timeline rules as Base mode.
- Preserve reference identity, costume, prop ownership, contact points, spatial direction, light direction, and motion phase where requested. Do not falsely promise pixel-perfect identity.

Multi-reference transfer check: distinguish the source of each attribute before writing. Two views of one person remain one subject; a clothing-only source must not replace that person's face. A group image does not imply one subject. Preserve the planner's global/local reference responsibilities; do not promote every active source to a universal anchor.

Two-speaker example fragment (syntax only; never reuse its names or dialogue): `<Subject 1>` is defined by `<Picture 1>` and `<Subject 2>` by `<Picture 2>`. If the approved plan says the woman speaks first and the man replies, write `女子 (S1) 问道：<d>[Chinese] 准备好了吗？</d> 男子先安静听完，再 (S2) 回答：<d>[Chinese] 可以出发了。</d>` inside detailed_description. Keep one ID per vocal clause; do not add narration or make the listener echo. A third clothing-detail image for Subject 1 supplies only the approved clothing attributes, not a third speaker or a new face. Keep the full six-section output; this fragment is not a replacement schema.

Integrated example (structure, not reusable content):

```text
subject_definitions:
<Subject 1> 是由 <Picture 1> 定义的成年女侦探，继承短黑发、窄脸、灰色风衣和右眉上方的小疤痕。

summary:
reference generation. 使用 <Picture 1> 定义主体身份与服装，生成雨夜站台上的短暂警觉反应。

retention_analysis:
<Picture 1> 对 <Subject 1> 的脸型、发型、眉上疤痕和灰色风衣采用 fully_preserved；原图背景、站姿和构图采用 weak_reference。

detailed_description:
[Shot 1] <Subject 1> 站在雨棚边缘，听见身后金属落地声后肩膀收紧，先用眼角向右后方确认，再缓慢转身半步。镜头以小幅慢速推近跟随她的视线，最终停在胸像构图；她确认无人后背靠立柱站稳。(S1) 她压低声音说道：<d>[Chinese] 谁在那里？</d>

overall_soundscape:
密集雨声敲击铁皮雨棚，远处雷声低沉滚过，金属零件落地后弹跳两次，衣料摩擦与短促吸气清楚同步。

non_diegetic_music:
N/A
```
