# Changelog

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
