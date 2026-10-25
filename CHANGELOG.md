# 2026-10-25

- Carry the previous shot description and boundary state into extension prompts, explicitly as authored intent rather than observed video.
- Clarify camera movement phases and speaker/listener mouth states; align the continuation example with the preceding truck movement.
- Restore concrete multi-person action, contact, camera and continuation instructions with three complete examples.
- Preserve prior subject definitions and ending state when appending; retain necessary global visual anchors in local prompts.
- Distinguish user-authored dialogue, planner-created speech and nonverbal vocalizations.
- Stop injecting negative-prompt ban lists into H3 positive descriptions.
- Increase planning output allowance and expose the underlying dialogue-planning error.

# 2026-10-23

- Treat dialogue content differences as review warnings while retaining structural and reference checks; allow punctuation changes and nonverbal vocalizations.
- Default all subsequent and appended video segments to motion-context extension, keeping the first segment as a cut.
- Simplify video controls and unify the three prompt nodes with ComfyUI standard buttons and multiline status widgets.
- Expand status details with task IDs, completed segments, content warnings and interruption reasons.

# 2026-10-22

- Global service URL, model ID and API key settings; migrate legacy node widgets.
- H3 contract validation and task-specific skill examples.
- Continuity, explicit cuts, dialogue and reference-retention rules.

# Changelog

## Unreleased — 2026-09-10

- Keep generation/revision request JSON in the API payload, never in the visible modification widget. Preserve edits made while a request is pending.
- For a directly connected CineTimeline append, use the editor's current shot order, surviving shots, titles and prompts. Standalone AIPM continues using its own cache.
- Allocate new segment IDs after the largest surviving ordinal, so deletion and reordering cannot collide with appended segments.
- Reuse matching global image identities during multimodal append; preserve separate local and keyframe roles.
- Pass segment titles into the CineTimeline adapter.
- Retain the 1.3.0 planning, skill and reference-analysis cache safeguards. Local server addresses and personal workflows are not included.

## 1.3.0 — 2026-09-08

- Refine image and video skill instructions: preserve explicit intent and reference roles, avoid irrelevant detail quotas, and separate stage-specific output contracts.
- Improve H3 planning: distinguish requests for silence from dialogue, allow explicitly requested repetition, and keep multimodal references separate from timed keyframes.
- Fix visual-analysis cache reuse when reference purpose, input order, service endpoint or model changes.
- Improve frontend request ownership, duplicate-result protection and adaptive node sizing without accumulating height.
- Preserve existing result JSON fields while removing mandatory quality/emphasis item counts.
- Default new-node service URL is localhost; configure your own OpenAI-compatible service. Existing workflow settings are not migrated.

### Verification and limits

75 Python tests plus JavaScript lifecycle and 5000-pass layout checks passed before packaging; release-tree checks are recorded in tests/RELEASE-VALIDATION.md. Real two-reference prompt-node checks covered FLUX.2 editing, Krea2 identity-preserving editing and Anima full-body composition on one Qwen service. These were prompt/JSON checks, not rendered-image quality tests or a complete multi-model benchmark.

Known limits: dialogue/repetition detection remains heuristic for complex negation; image analysis may overdescribe ambiguous garment details. Reference conditioning depends on the downstream workflow. No universal quality gain or automatic remote-model upgrade is claimed.
