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

- Multiple pictures of identity, costume or one continuous event do not imply separate shots. For genuine frame/composition anchors, explain their temporal relationship and the feasible change between them; preserve an approved cut when present.
- Retention grades the defined referenced attributes, not every pixel or evolving state. `fully_preserved` identity/clothing can coexist with natural walking, sitting, pose or framing changes. Change to a protected attribute requires the appropriate different marker; a pose, direction or endpoint explicitly locked by an anchor remains a constraint. State the actual inherited/excluded attributes, not a blanket downgrade because the actor moves.
