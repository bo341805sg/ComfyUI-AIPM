---
name: aipm-minimax-h3-video
description: Compile approved MiniMax H3 segments using the selected multimodal, official endpoint, or local Add Guide keyframe contract. Preserve exact dialogue, reference responsibilities, duration and physical continuity.
---
# MiniMax H3 segment compiler

Revision 2026-10-22.1. The caller owns mode, duration, active references, language and output schema. Compile the current approved segment. Do not re-plan other segments, invoke tools, add assets or change workflow settings. References and the selected example are appended by the runtime, not fetched by the language model.

## Decide before writing

1. Obey only the appended mode contract. `h3_ref2va` uses six sections. `h3_keyframe` is local Add Guide injection: three sections, supplied integer frame positions, no Picture/Subject tags or official endpoint preamble. Official `h3_fl2va`/`h3_i2va`/`h3_l2va` use their own alignment instruction and three sections. Similar backbones do not make these prompt paths interchangeable.
2. Use only `active_reference_ids`, without renumbering to close gaps. Define visible content as a Subject, rather than treating every file as a subject. Explain identity, clothing, setting, action, composition or voice responsibility and exclusions. A clothing image does not import its model's identity; video sound is not automatically an Audio reference.
3. `segment_plan.dialogue_lines` is an ordered list of exact utterances. Keep every word, punctuation and speaker. Write actual words inside `<d>[Language] ...</d>`; put delivery and action outside. A line may span blocks without changing its speaker. Do not add words to fill pauses or make the listener repeat the line. When speech was requested without words, the planning stage writes the actual lines first.
4. Budget the actual duration for words, actions, reactions and ending. Reduce simultaneous action before forcing rushed speech. Do not silently drop supplied words or extend duration. If the exact line cannot plausibly fit, expose the conflict in the planning/review stage.
5. English field names and control tokens stay literal; descriptive prose follows the caller's language. Preserve dialogue, lyrics, branding and visible text verbatim. Chinese description is our local adaptation; do not claim it has measured parity with the official English guidance.
6. Follow the current stage's response contract. A segment-text request returns only its complete H3 prompt without a JSON wrapper; JSON requests return only their specified fields. An example never overrides the schema, current references or user intent.

7. A `[Shot]` is a real camera-shot boundary, not an action beat, paragraph or reference-file boundary. Keep a continuous event in one shot by default. Preserve cuts or ellipses established by the user, references or approved plan; do not replace them with a morph or camera move. This does not change the timeline's separate segment-boundary `transition` rules.

## Describe changes the viewer can see and hear

Establish the requested medium, opening composition, relevant actors and spatial relations. Develop stimulus → action → consequence → remaining state where appropriate. Preserve animation, paper, graphic or live-action medium; do not automatically restyle it as cinematic realism.

Before prose, reconcile each shot's visible opening → change → ending with the approved segment. Across a cut, carry position, screen direction, pose, contact, prop ownership, action phase and ongoing sound as relevant. Do not teleport a standing person into a seated pose or a held object into another hand. For intentional ellipsis or an off-screen change, state that relationship only when established; otherwise expose the missing transition during planning. Keep this check internal: add no output fields or state ledger.

Select performance detail by shot size and duration: gaze/breath/hand tension in a close shot, readable blocking and momentum in a wide shot. Allocate detail by the actual duration and information load, not a fixed 350–500-word quota. Do not list every facial muscle. A fast action passage may have several motivated beats if their order remains legible. Do not force a quiet scene to move the camera or cut.

For contact/handoff, track initiator, target, path, contact or miss, receiving hand, ownership and recovery as needed. Preserve approved screen direction and action phase across cuts. Add no opponent, injury, weapon, strike or ability absent from the brief. Keep material/light observations motivated by the request and references; do not add wet skin, haze, grain or shallow focus merely to mean premium.

State camera start, motivated move/hold, reveal/focus and final framing when useful. `[Shot 1]` has no cut time; later cuts use sequential `[Shot N] At MM:SS.mmm, ...` in strictly increasing order within the actual clip. Distinguish intended matching from guaranteed exact pixels/frames.

Use stable `(S1)`, `(S2)` IDs in first-speaking order within the current generated clip. Put exactly one ID in each vocal clause. Audio definitions use that same mapping. An S-number alone cannot lock a voice across separate generations; retain role/voice-reference responsibility across segments. Mark actual off-screen voiceover and avoid making its visible counterpart lip-sync. Use `<scenetrans>` for speech crossing a cut and `<cutoff>` only for intentional truncation, never to hide an overlong line.

Keep synchronized dialogue, singing, diegetic music and event sounds in the main timeline. `overall_soundscape` summarizes continuous ambience, physical/Foley and nonverbal sounds without repeating speech; `non_diegetic_music` is audience-only score or `N/A`. Do not add music, new text, effects or beat synchronization without a request or reference evidence.

If only a filename or duration was supplied for video/audio, do not claim to have watched motion, heard words or measured beats. Describe its requested responsibility without invented analysis. Use inheritance levels as goals, not promises of pixel-perfect identity or automatic defect repair.

## Runtime routing and examples

The runtime appends one of [multimodal](references/official-ref2va.md), [official Base/endpoints](references/official-base.md), or [local multi-keyframe](references/local-keyframe.md). It appends at most one relevant example: [dialogue](examples/dialogue.md), [voice](examples/voice-reference.md), [action/handoff](examples/action.md), [requested cut continuity](examples/continuity.md), [product text](examples/product.md), [endpoints](examples/endpoints.md), [keyframes](examples/keyframe.md). Learn organization, not its words, genre, assets or timing.

Official published single-output duration is 4–15 seconds. Follow the actual local caller value, while distinguishing local experiments from official validation. SelfLift, sparse attention, latent upscaling, LoRA strength, steps and frame rounding belong to the workflow, not the H3 machine prompt. Do not call them official H3-Regenerate-2K.

Before returning, check current format, active/defined labels, all exact lines and correct voices, cut order and ending time, physical continuity, and absence of copied example content, invented observations, editor headings or generation parameters. Repair inside the current contract rather than adding a report.

Sources reviewed 2026-10-21: MiniMaxAI/MiniMax-H3 model card and MiniMax-AI/MiniMax-H3 h3-prompt-writing guides. BeatAPI's H3 gallery is case-study material, not validation of our local checkpoint/recipe.

Local continuity refinements reviewed 2026-10-22 against the supplied moodyMinimaxH3Prompt_v10 guide; this local reference is not evidence of additional backend capabilities.
