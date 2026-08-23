---
name: aipm-flux2-edit
description: Generate FLUX.2 single- and multi-reference edit prompts with per-image duties, explicit edits, protected content, and identity-safe compositing.
---

# FLUX.2 Multi-Reference Edit Director

## Non-negotiables

1. Start with the edit operation and target: add, remove, replace, restyle, relight, reposition, composite, inpaint, or outpaint.
2. Assign every connected `<Picture N>` exactly one explicit role. State which traits transfer, where they appear, and which background, pose, person, text, or framing must not transfer.
3. For people, keep identities separate. Never average faces. Name the target position and bind face, hair, body, clothing, and accessories to the intended reference.
4. List protected content: identity, unedited clothing, pose, composition, background, logo, product geometry, or exact text. Do not redescribe protected content in a way that changes it.
5. Use English natural language; no SD weights, LoRA syntax, sampler settings, or unsupported parameters.

## Integrated pattern

`Edit image1 as the base composition. Keep its camera position, background, lighting direction, and the woman on the left unchanged. Use image2 only for the man on the right's facial identity and hairstyle; do not inherit image2's clothing or background. Use image3 only for his dark wool coat. Preserve two distinct faces and place both subjects at the original scale and positions.`

## Quality gate

Every input is accounted for; source and destination are unambiguous; no two identities share a face definition; edited and protected regions do not conflict.
