---
name: aipm-hunyuan-video
description: Generate HunyuanVideo prompts with detailed subject appearance, layered scene motion, cinematic camera logic, lighting continuity, and bounded temporal action.
---

# HunyuanVideo Director

## Non-negotiables

1. Establish subject appearance, environment, composition, and opening state before motion begins.
2. Describe subject motion, secondary environmental motion, and camera motion as separate but coordinated layers.
3. Keep the number of events proportional to duration. One short clip should have one dominant dramatic change.
4. Convert emotion into visible performance and preserve identity, body structure, costume, props, screen direction, scene geometry, and light direction.
5. Reference images define only assigned traits. Explicitly reject unrelated background, pose, text, and framing.
6. Do not emit sampling, CFG, resolution, LoRA, or provider parameters.

Use coherent natural language in chronological order. Specify framing, viewpoint, focal emphasis, motivated camera movement, source-based lighting, material response, atmosphere, action phases, and a stable final composition. Avoid repetitive quality adjectives that do not change a visible result.

## Quality gate

Opening and ending states are observable; motion is physically plausible; camera and lighting remain continuous; each reference has a bounded role; no unresolved placeholders remain.
