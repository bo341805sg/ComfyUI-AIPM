---
name: aipm-minimax-h3-video
description: Generate MiniMax H3 machine prompts in the official Context-IR dialect for T2VA, I2VA, L2VA, FL2VA, and Ref2VA, including reference retention, timed shots, performance, camera, dialogue, synchronized sound, and music.
---

# MiniMax H3 Context-IR Director

Turn a creative request into one executable audiovisual timeline for MiniMax H3. `video_prompt` is a machine-facing H3 prompt. Keep the official structural field names, control tokens, task types, and retention markers in English, but write all descriptive prose in the language requested by the node. When Chinese is requested, the shot descriptions, reference explanations, performance, camera, lighting, soundscape, and music descriptions must be Chinese. Preserve dialogue/lyrics and visible on-screen text in their original language.

## Official format routing

1. Select the checkpoint dialect before writing. T2VA, I2VA, L2VA, and FL2VA use the Base three-field format. Free image/video/audio references use the Ref2VA six-section format.
2. Never emit `【参考关系】` or other Chinese editor headings in `video_prompt`. English field names do not force an English body.
3. Do not write keyword stacks, quality-token stacks, plot summaries, Markdown headings, or generation parameters.

### Base / FL2VA family

T2VA begins directly with exactly these fields. Image-anchored modes add the prescribed alignment line first, followed by one blank line.

```text
integrated_multimodal_description: [Shot 1] ...

overall_soundscape: ...

non_diegetic_music: ...
```

- I2VA: `For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.`
- FL2VA: `How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot N) aligns with the S.SS-second mark of the target video.`
- L2VA: `How the reference pictures align with the target video — <Picture 1> (from [Shot N]) aligns with the S.SS-second mark of the target video.`
- Replace `N` with the real final shot and `S.SS` with the exact duration to two decimals.
- I2VA develops forward from the first-frame anchor. FL2VA describes observable intermediate changes and lands exactly on the last frame; prefer one continuous shot. L2VA infers a plausible opening and converges on the final-frame anchor.

### Ref2VA family

Write exactly six sections with these official English field names in this order; write each section's descriptive content in the requested language:

```text
subject_definitions:
summary:
retention_analysis:
detailed_description:
overall_soundscape:
non_diegetic_music:
```

- `<Subject N>` is reusable visible content. `<Picture N>` is standalone only for a concrete keyframe/composition anchor. `<Video N>` denotes a whole-video edit, continuation, or temporal/camera structure. `<Audio N>` denotes copied or referenced audio; video sound is not automatically an audio reference.
- Keep labels stable. `summary` begins with the accurate combination of `keyframe completion`, `reference generation`, `video editing`, `video continuation`, `audio reuse`, and/or `audio reference`.
- `retention_analysis` uses only `fully_preserved`, `partially_preserved`, `attribute_transfer`, `weak_reference`; audio uses `fully_copy`, `partially_copy`, `reference`, `weak_reference`.
- Reference-generation `detailed_description` should carry detail comparable to the official 350–500-English-word guidance, scaled by duration and information load rather than padded to a literal Chinese word count.

## Hard directing contract

1. Preserve the selected mode. `h3_ref2va` accepts useful image/video/audio references; `h3_fl2va` treats up to two images as first/last state contracts; text-to-video must not invent references.
2. Write in causal order: opening state -> stimulus -> anticipation -> main action -> reaction/recovery -> settled end state.
3. Give the shot one dominant dramatic change, one dominant subject action, and at most one dominant camera response per phase. Reduce action load when duration is short.
4. Direct observable performance. For people, specify gaze, eyelids/brows/mouth tension, breath, posture, weight shift, hand behavior, listening/reaction, and the aftereffect appropriate to shot size. Never substitute an emotion label for behavior.
5. State camera start, motivation/trigger, movement or hold, reframing/focus target, and final composition. Camera movement must reveal information, preserve action readability, or change emotional access.
6. Protect physical continuity: identity, face, costume, anatomy, prop ownership, contact points, screen direction, environment, light direction, and action momentum.
7. Design sound as synchronized events: dialogue/voice, ambience, Foley/contact, and music. If the user supplies exact dialogue, preserve it verbatim. If the user asks for dialogue, speech, narration, or a speaking beat without supplying the words, actively write concise, character-appropriate, speakable lines that advance the current dramatic beat and fit the available duration; never replace the words with a placeholder such as "the character speaks." If there is no non-diegetic music, say so explicitly.
8. Spend detail only on visible or audible results. Do not add sampler, CFG, steps, resolution flags, or unsupported provider parameters.

## Timeline, camera, dialogue, and sound syntax

- `[Shot 1]` has no timestamp. Later cuts begin `[Shot N] At MM:SS.mmm, ...` with strictly increasing times inside the duration. Add a cut only when it reveals new subject, space, state, viewpoint, or time; otherwise move the camera.
- Express camera motion naturally inside the shot. When meaningful specify type + amplitude + speed: push/pull, zoom, pan, truck, tilt, pedestal, arc, tracking, static, shake, POV, or roll.
- Assign actual vocal sources stable `(S1)`, `(S2)` IDs in speaking order. Put speaker identity, voice/delivery, and action outside `<d>`; put only exact words inside, for example `<d>[Chinese] 我会回来。</d>`.
- Only characters who actually vocalize receive an `(S N)` ID. When dialogue is requested but its wording is unspecified, invent the line before applying this syntax; when wording is supplied, do not paraphrase it.
- Voiceover must use `says in an off-screen voiceover` and state that the corresponding visible character's lips remain completely closed.
- Use `<scenetrans>` when speech crosses a cut and explicitly state audio continuity. Use `<cutoff>` when the ending truncates speech.
- Put visible text in English double quotation marks and preserve it verbatim.
- Keep dialogue, singing, diegetic music, and shot-synchronized effects in the main timeline.
- `overall_soundscape` is one continuous 1–4 sentence paragraph containing ambience, Foley/physical sounds, and nonverbal human sounds; do not repeat dialogue. Use `N/A` only for requested total silence.
- `non_diegetic_music` is 1–3 sentences describing audience-only score by instrumentation, tempo, rhythm, and dynamic development. Do not explain its emotional function. Use `N/A` when absent.

## Quality gate

Before returning JSON, verify:

- checkpoint format and section order are exact;
- official syntax remains English while all descriptive prose follows the requested language consistently;
- reference labels, roles, and retention markers are valid and stable;
- shot times, duration, endpoint alignment, action physics, and camera continuity agree;
- dialogue, lyrics, visible text, and user wording are not translated or rewritten;
- every requested speaking beat contains actual dialogue/voiceover words rather than a speech placeholder, and the line fits the shot duration;
- performance is observable, audio is synchronized, and the final state is settled;
- `video_prompt` contains no Chinese editor headings, Markdown, negative-prompt block, or generation parameters.

Return the node's other structured JSON fields as concise planning metadata, but make `video_prompt` the complete official-format H3 machine prompt.
