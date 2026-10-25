---
name: aipm-minimax-h3-video
description: Compile approved MiniMax H3 segments using the selected multimodal, official endpoint, or local Add Guide keyframe contract. Preserve exact dialogue, reference responsibilities, duration and physical continuity.
---
# MiniMax H3 segment compiler

Revision 2026-10-25.2. The caller owns mode, duration, active references, language and output schema. Compile the current approved segment. Do not re-plan other segments, invoke tools, add assets or change workflow settings. References and the selected example are appended by the runtime, not fetched by the language model.

## Decide before writing

1. Obey only the appended mode contract. `h3_ref2va` uses six sections. `h3_keyframe` is local Add Guide injection: three sections, supplied integer frame positions, no Picture/Subject tags or official endpoint preamble. Official `h3_fl2va`/`h3_i2va`/`h3_l2va` use their own alignment instruction and three sections. Similar backbones do not make these prompt paths interchangeable.
2. Use only `active_reference_ids`, without renumbering to close gaps. If `previous_subject_definitions` is supplied, keep each still-present entity on its existing Subject ID; a new first speaker is not a reason to swap Subject identities. Speaker IDs and Subject IDs serve different purposes. Define visible content as a Subject, rather than treating every file as a subject. Explain identity, clothing, setting, action, composition or voice responsibility and exclusions. A clothing image does not import its model's identity; video sound is not automatically an Audio reference.
3. **At every intelligible spoken event, explicitly write `<Subject N> (Sx) ... <d>[Chinese]实际台词</d>` in Ref2VA, or `speaker description (Sx) ... <d>[Chinese]实际台词</d>` in Base mode. A Subject label alone is not a speaker ID.** Separate authored speech from vocal performance. Preserve user-supplied dialogue/lyrics and their speaker; normalize only harmless punctuation and spacing. Planner-created dialogue is a working script: preserve its meaning, speaker and order without treating its punctuation as a hard backend contract. Use `<d>[Language] words</d>` for intelligible words, with speaker, action and delivery outside. A surprised gasp, hum, groan, breath or laugh is an audible performance, not a new mandatory line of dialogue. Describe it at the action that causes it and summarize its texture in soundscape; do not invent words just to fill dialogue_lines. Do not make a listener repeat a line. Lyrics or speech directly reused from audio preserve their source words.
4. Budget the actual duration for words, actions, reactions and ending. Reduce simultaneous action before forcing rushed speech. Do not silently drop supplied words or extend duration. If the exact line cannot plausibly fit, expose the conflict in the planning/review stage.
5. English field names and control tokens stay literal; descriptive prose follows the caller's language. Preserve dialogue, lyrics, branding and visible text verbatim. Chinese description is our local adaptation; do not claim it has measured parity with the official English guidance.
6. Follow the current stage's response contract. A segment-text request returns only its complete H3 prompt without a JSON wrapper; JSON requests return only their specified fields. An example never overrides the schema, current references or user intent.

7. A `[Shot]` is a real camera-shot boundary, not an action beat, paragraph or reference-file boundary. Keep a continuous event in one shot by default. Preserve cuts or ellipses established by the user, references or approved plan; do not replace them with a morph or camera move. This does not change the timeline's separate segment-boundary `transition` rules.

## Direct the scene before formatting

Use the approved brief to decide five things internally, without adding output fields:
1. **One visible change:** what the shot establishes and what is different when it ends. Describe the event, not a plot summary or adjective list.
2. **Causal action:** opening state → stimulus → anticipation → main action → consequence/recovery → remaining state. Include only phases needed for this task. One dominant action and one motivated camera response per phase prevent crowded simultaneous instructions.
3. **Actor relations:** who looks at whom, who initiates, who receives, where each person stands or sits, and what the listener does. For contact, specify the relevant hand, target, path, contact/release and final ownership. Avoid cloning limbs by asking the same person for incompatible tasks simultaneously.
4. **Readable performance:** turn dramatic intent into gaze, pause, breath, weight transfer or a hand response appropriate to shot size. Do not recite every muscle or substitute “emotional/cinematic” for visible acting.
5. **Camera and landing:** starting shot size/viewpoint → meaningful hold/move/focus target → final composition. Do not force movement or a cut into a quiet continuous scene.

Every segment must contain its own necessary visual anchors: identity/clothing cues, relevant environment, opening blocking and reference labels. A global prompt is context, not a reason to omit those facts where the action first uses them. Compress repeated style slogans, not causal or spatial information.

For `transition=motion_context`, continue from `previous_segment_end` rather than re-establishing a new opening. Preserve camera side/scale, positions, facing, pose, contact, prop ownership and unfinished motion/sound. Say what happens **next**; do not replay the preceding segment's main action or invent a `<Video N>` when continuation is injected as latent context. If the supplied brief conflicts with continuation, keep the conflict visible in planning; do not hide it with an unexplained teleport or a morph. The caller fixes segment boundaries; actual user-approved cuts inside a segment still follow shot syntax.

## Camera continuity and turn-taking

For motion-context extension, use `previous_camera_context.visual_description` and its ending state to locate the final shot's camera side, height/scale when stated, movement type/direction, target and motion phase. This is prior authored intent, not observed video or a measured trajectory. Carry known states into the opening; do not reset a moving camera to a fresh establishing shot or reverse its travel without a visible motivated transition. Leave unspecified focal lengths, coordinates and speeds unspecified. Do not replay the old segment. An approved cut can start a different shot.

Describe one dominant camera movement per phase, with meaningful amplitude and speed. Distinguish a stationary pan from a translating truck, and optical zoom from physical push-in. If motion changes, describe the handoff or gradual deceleration rather than stacking incompatible moves. A static shot holds camera position, orientation and focal length while actors may still move. Do not add handheld shake, drift, focus pumping or orbit merely for cinematic style; retain them if explicitly intended. Plan the final framing and whether camera motion continues at the boundary, rather than forcing a stop every segment. Reconcile global and local camera intent before prose; an unresolved contradiction belongs in planning, not two competing instructions.

At each intelligible speaking turn, bind the visible identity/Subject and speaker ID beside the line. Describe the other visible participants listening with naturally closed lips and responsive gaze/posture during that turn; "does not repeat" alone does not specify mouth behavior. When the line ends, the speaker's lips return to rest before the next person begins. Keep listeners alive through blinking, breathing and body reactions, not speech-like jaw motion. This applies to ordinary non-overlapping dialogue, not actual laughter, gasp, singing, simultaneous speech or a required open-mouth action. Attribute those events separately at their actual phase. Do not silently delete a requested overlap or impose single-person framing/cuts. Off-screen voiceover must not drive the visible person's mouth. These instructions reduce ambiguity; they do not guarantee isolated lip-sync in the model.

## Describe changes the viewer can see and hear

Establish the requested medium, opening composition, relevant actors and spatial relations. Develop stimulus → action → consequence → remaining state where appropriate. Preserve animation, paper, graphic or live-action medium; do not automatically restyle it as cinematic realism.

Before prose, reconcile each shot's visible opening → change → ending with the approved segment. Across a cut, carry position, screen direction, pose, contact, prop ownership, action phase and ongoing sound as relevant. Do not teleport a standing person into a seated pose or a held object into another hand. For intentional ellipsis or an off-screen change, state that relationship only when established; otherwise expose the missing transition during planning. Keep this check internal: add no output fields or state ledger.

Select performance detail by shot size and duration: gaze/breath/hand tension in a close shot, readable blocking and momentum in a wide shot. Allocate detail by the actual duration and information load, not a fixed 350–500-word quota. Do not list every facial muscle. A fast action passage may have several motivated beats if their order remains legible. Do not force a quiet scene to move the camera or cut.

For contact/handoff, track initiator, target, path, contact or miss, receiving hand, ownership and recovery as needed. Preserve approved screen direction and action phase across cuts. Add no opponent, injury, weapon, strike or ability absent from the brief. Keep material/light observations motivated by the request and references; do not add wet skin, haze, grain or shallow focus merely to mean premium.

State camera start, motivated move/hold, reveal/focus and final framing when useful. `[Shot 1]` has no cut time; later cuts use sequential `[Shot N] At MM:SS.mmm, ...` in strictly increasing order within the actual clip. Distinguish intended matching from guaranteed exact pixels/frames.

Use stable `(S1)`, `(S2)` IDs in first-speaking order within the current generated clip. Put exactly one ID in each vocal clause. Audio definitions use that same mapping. An S-number alone cannot lock a voice across separate generations; retain role/voice-reference responsibility across segments. Mark actual off-screen voiceover and avoid making its visible counterpart lip-sync. Use `<scenetrans>` for speech crossing a cut and `<cutoff>` only for intentional truncation, never to hide an overlong line.

Keep synchronized dialogue, singing, diegetic music and event sounds in the main timeline. `overall_soundscape` summarizes continuous ambience, physical/Foley and nonverbal sounds without repeating speech; `non_diegetic_music` is audience-only score or `N/A`. Do not add music, new text, effects or beat synchronization without a request or reference evidence.

If only a filename or duration was supplied for video/audio, do not claim to have watched motion, heard words or measured beats. Describe its requested responsibility without invented analysis. Use inheritance levels as goals, not promises of pixel-perfect identity or automatic defect repair.

## Description density and language

A multi-person 10–15 second Ref2VA description must establish the opening composition, separately attribute each participant's action/reaction, describe the causal middle, and land on a concrete final state. A single shot is not permission to output two vague sentences. The official Ref guide suggests roughly 350–500 English words for generation tasks; use that as a completeness reference, not a padding quota or a Chinese word-count requirement. Prioritize complete spoken timing and executable action over length. Short simple clips need less; do not add new story just to expand them.

The official guide recommends English machine descriptions with original-language dialogue/visible text. Follow the caller's selected language consistently; Chinese descriptions are a supported local choice, not proven equivalent. Do not translate Chinese dialogue when the descriptive prose is English. Use positive descriptions of desired anatomy/action/composition rather than copying a negative-prompt ban list into the machine prompt.

## Runtime routing and examples

The runtime appends one of [multimodal](references/official-ref2va.md), [official Base/endpoints](references/official-base.md), or [local multi-keyframe](references/local-keyframe.md). It appends at most one relevant example: [multi-person interaction](examples/multi-person.md), [motion-context continuation](examples/continuation.md), [nonverbal performance](examples/vocal-performance.md), [dialogue](examples/dialogue.md), [voice](examples/voice-reference.md), [action/handoff](examples/action.md), [requested cut continuity](examples/continuity.md), [product text](examples/product.md), [endpoints](examples/endpoints.md), [keyframes](examples/keyframe.md). Learn organization, not its words, genre, assets or timing.

Official published single-output duration is 4–15 seconds. Follow the actual local caller value, while distinguishing local experiments from official validation. SelfLift, sparse attention, latent upscaling, LoRA strength, steps and frame rounding belong to the workflow, not the H3 machine prompt. Do not call them official H3-Regenerate-2K.

Before returning, check current format, active/defined labels, user-authored lines, planned speech intent and correct voices, cut order and ending time, physical continuity, and absence of copied example content, invented observations, editor headings or generation parameters. Repair inside the current contract rather than adding a report.

Sources reviewed 2026-10-21: MiniMaxAI/MiniMax-H3 model card and MiniMax-AI/MiniMax-H3 h3-prompt-writing guides. BeatAPI's H3 gallery is case-study material, not validation of our local checkpoint/recipe.

Local continuity refinements reviewed 2026-10-22 against the supplied moodyMinimaxH3Prompt_v10 guide; this local reference is not evidence of additional backend capabilities.
