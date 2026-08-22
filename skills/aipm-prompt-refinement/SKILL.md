---
name: aipm-prompt-refinement
description: Diagnose and minimally refine an existing image or video generation prompt when an observed result has defects or misses the intended outcome.
---

# Prompt Diagnosis and Refinement

Treat the original prompt as an artifact to repair, not an invitation to recreate it.

## Diagnose before editing

Separate the symptom from its likely cause: prompt ambiguity or contradiction; anatomy, contact, occlusion, spatial, temporal, camera, continuity, dialogue or sound direction; reference-binding failure; or a model, sampler, denoise, resolution, duration, conditioning or workflow limitation.

Do not pretend a prompt rewrite can reliably fix a workflow or model limitation. Provide the safest prompt-side mitigation and put non-prompt fixes in `workflow_recommendations`.

## Make the smallest sufficient repair

- Preserve every subject, action, setting, style, camera decision, timing beat, reference relation and literal line the user did not ask to change.
- Treat `must_preserve` as immutable. Report a direct conflict instead of silently discarding it.
- Replace vague goals with visible, physically plausible states and transitions.
- For penetration or contact defects, define body-part ownership, contact surface, depth ordering, occlusion, grip points, collision boundaries and beginning/end states. Do not merely add “no clipping”.
- For motion defects, clarify causal phases, weight transfer, momentum, interaction timing, camera response and the final state without scripting every frame.
- For identity drift, restate only the affected subject's discriminating identity anchors and reference bindings.
- Preserve exact dialogue unless asked to rewrite it; clarify speaker binding, delivery, timing, environmental sound and mix priority.

## Honor the target dialect

Apply `base_prompt_skill` after diagnosis. Preserve required model tokens, reference names, subject/speaker bindings, weights, tags and dialogue syntax. Do not inject SD quality tags into natural-language models or invent unsupported parameters.

## Output contract

`refined_prompt` is a complete executable replacement, not commentary. Retain useful negatives only when the target dialect benefits from them. Keep diagnosis causal and concise, list concrete edits, record protected elements, and reserve `workflow_recommendations` for non-prompt fixes.

Never include analysis, Markdown fences or alternative versions inside `refined_prompt`.
