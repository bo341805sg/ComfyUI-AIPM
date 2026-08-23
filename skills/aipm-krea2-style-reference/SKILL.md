---
name: aipm-krea2-style-reference
description: Generate Krea 2 prompts for style-reference or moodboard workflows while preventing subject and layout leakage from style images.
---

# Krea 2 Style-Reference Director

## Non-negotiables

1. Write the content prompt in faithful English natural language. Do not add key subjects, props, or actions.
2. Text controls what is in the frame; style references control palette, medium, texture, line quality, grain, contrast, and aesthetic rhythm.
3. For each `<Picture N>`, state the style traits to inherit and explicitly reject its people, objects, text, background, and layout unless requested.
4. Do not claim prompt text can replace a missing style-reference input. Keep adapter strength and workflow parameters out of the prompt.

Describe subject and action first, then composition, then the selected style traits, motivated light, and material finish. Turbo may be concise, but must retain all content constraints.

## Quality gate

The generated content remains owned by the user brief; reference subjects cannot leak into it; one primary style and at most one compatible secondary texture direction remain.
