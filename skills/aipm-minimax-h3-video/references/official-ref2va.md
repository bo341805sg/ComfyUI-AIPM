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
- `summary` begins with a square-bracketed task prefix such as `[reference generation]` or `[video continuation + reference generation]`, using the accurate combination of: `keyframe completion`, `reference generation`, `video editing`, `video continuation`, `audio reuse`, `audio reference`. Merely receiving a video or audio asset does not prove that task type.
- `retention_analysis` uses only `fully_preserved`, `partially_preserved`, `attribute_transfer`, `weak_reference`; audio uses `fully_copy`, `partially_copy`, `reference`, `weak_reference`. State inherited attributes and excluded background, pose, framing, or unrelated content.
- `detailed_description` uses `[Shot 1]`, timed later shots, stable `(SN)` speakers, `<d>[Language] ...</d>`, `<scenetrans>`, and `<cutoff>` under the same timeline rules as Base mode.
- Preserve reference identity, costume, prop ownership, contact points, spatial direction, light direction, and motion phase where requested. Do not falsely promise pixel-perfect identity.

- Multiple pictures of identity, costume or one continuous event do not imply separate shots. For genuine frame/composition anchors, explain their temporal relationship and the feasible change between them; preserve an approved cut when present.
- Retention grades the defined referenced attributes, not every pixel or evolving state. `fully_preserved` identity/clothing can coexist with natural walking, sitting, pose or framing changes. Change to a protected attribute requires the appropriate different marker; a pose, direction or endpoint explicitly locked by an anchor remains a constraint. State the actual inherited/excluded attributes, not a blanket downgrade because the actor moves.

- Use Subject-only character references in machine prose. Definitions give the Subject, active source and visible attributes without role-name fields or parenthesized names. Keep script names only in internal planning/bindings; preserve names spoken in dialogue or displayed literally. Subject, Picture and speaker numbering are independent.
- On-screen or off-screen speech by a defined subject uses both Subject and speaker ID. A narrator with no visual subject uses a stable voice description plus speaker ID. Requested group speech uses `(S1,S2)`; verbal cues only inside reused audio remain Audio cues without a new speaker. Do not put speaker IDs in retention_analysis.
