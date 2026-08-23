---
name: aipm-krea2-identity-edit
description: Generate Krea 2 identity-edit prompts that prioritize facial identity, isolate multiple people, and preserve unedited composition and content.
---

# Krea 2 Identity-Edit Director

## Non-negotiables

1. State which person in the base image is edited and which `<Picture N>` supplies that identity.
2. Bind stable facial traits separately for every person: face shape, eyes, brows, nose, lips, hairline, hairstyle, age range, and distinguishing marks. Never blend identities.
3. Preserve all unrequested content explicitly: the other person, pose, hands, clothing, framing, background, light direction, and text.
4. Use other references only for their assigned clothing, prop, pose, or style role. Reject their face and background when they are not identity sources.
5. Write English natural language without numeric weights or workflow parameters.

## Integrated pattern

`Edit only the woman on the left in image1. Use image2 exclusively for her facial identity and hairstyle. Keep the man on the right completely unchanged. Preserve image1's poses, hand contact, clothing, camera position, background, lighting, and color grade. Do not merge either face or inherit image2's background.`

## Quality gate

Each identity has one source and one destination; protected people and regions are explicit; style language cannot override identity fidelity.
