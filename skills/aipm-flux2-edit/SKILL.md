---
name: aipm-flux2-edit
description: Generate FLUX.2 single- and multi-reference edit prompts with per-image duties, explicit edits, protected content, and identity-safe compositing.
---

# FLUX.2 Multi-Reference Edit Director

## Non-negotiables

1. Start with the edit operation and target: add, remove, replace, restyle, relight, reposition, composite, inpaint, or outpaint.
2. Account for every connected `<Picture N>` with its assigned role or roles; one image may supply several compatible attributes. State what transfers, its destination and exclusions; explicitly leave an irrelevant image unused rather than forcing it into the edit.
3. For people, keep identities separate. Never average faces. Name the target position and bind face, hair, body, clothing, and accessories to the intended reference.
4. Write explicit protection in the final prompt: preserve the base image's poses, positions, framing, background and lighting unless those are requested edits. For each donor, explicitly exclude its unassigned pose, background and other content. "Use only its face and coat" does not replace these exclusions. Do not protect an attribute the user asked to change.
5. Use English natural language; no SD weights, LoRA syntax, sampler settings, or unsupported parameters.

## Integrated pattern

`Edit image1 as the base composition. Keep its camera position, background, lighting direction, and the woman on the left unchanged. Use image2 only for the man on the right's facial identity and hairstyle; do not inherit image2's clothing or background. Use image3 only for his dark wool coat. Preserve two distinct faces and place both subjects at the original scale and positions.`

## Quality gate

Every input is accounted for; source and destination are unambiguous; no two identities share a face definition; edited and protected regions do not conflict.
