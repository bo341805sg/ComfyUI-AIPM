---
name: aipm-flux2-natural
description: Generate faithful FLUX.2 text-to-image prompts with explicit subject relations, typography, optics, lighting, materials, and optional prompt-upsample awareness.
---

# FLUX.2 Text-to-Image Director

## Non-negotiables

1. Write one cohesive English natural-language prompt. Do not use SD weights or quality-tag stacks.
2. Preserve every explicit subject, action, count, color, spatial relation, medium, and quoted text. Do not invent a new key subject or prop.
3. Put exact visible text in double quotes and define its carrier, placement, hierarchy, type treatment, color, and legibility.
4. Keep prompt content separate from workflow controls. Never emit steps, CFG, seed, resolution flags, or `prompt_upsampling` as prompt prose.

## Construction

Lead with the decisive subject and event. Then establish foreground/midground/background, framing and viewpoint, motivated light, material response, palette, medium, and a small number of visible finish criteria. Give the main subject more descriptive weight than the background. If upstream prompt upsampling is enabled, keep the prompt precise and avoid redundant embellishment; if it is disabled, add only details that improve visual determinacy without changing intent.

## Quality gate

The subject count and spatial relationships must be uniquely interpretable; quoted text must be exact; optics and lighting must not contradict; negative prompt is empty unless the active workflow consumes it.
