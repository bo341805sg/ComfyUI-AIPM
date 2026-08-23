---
name: aipm-ltx-video
description: Generate compact LTX-Video prompts with front-loaded action, explicit camera behavior, synchronized sound, and a clear final state.
---

# LTX-Video Prompt Director

## Non-negotiables

1. Front-load the subject, action, setting, shot size, and camera behavior. Do not bury motion after long visual styling.
2. Write a compact chronological shot: initial composition -> action phases -> reaction -> final composition.
3. Use concrete motion verbs with direction, pace, and amplitude. Avoid simultaneous unrelated actions.
4. Keep identity, clothing, props, anatomy, spatial direction, lighting, and image-reference facts continuous.
5. Synchronize dialogue, ambience, Foley, and music only when the workflow supports audio; otherwise keep audible intentions in `audio_prompt`, not as visual objects.

Style and material details are secondary to motion clarity. Prefer a hold, pan, push, pull, track, or arc with a stated motivation and landing frame; do not combine several camera moves for decoration.

## Quality gate

The first sentence contains the executable visual event; every motion has a source and endpoint; the camera and subject do not issue conflicting movement cues; the ending is settled.
