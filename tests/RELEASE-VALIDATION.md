# v1.3.0 validation scope

Release-tree verification completed: `python -m unittest discover -s tests -p test_nodes.py` passed all 75 tests; `node tests/test_aipm_result_lifecycle.cjs` and `node tests/test_aipm_height.cjs` passed. `git diff --check` passed. The published default URL was changed to localhost before these checks.

Development regression: 75 Python tests, zero failures/errors. Cache-context test failed before the fix and passed afterward; identical requests still hit, changed roles/endpoints/models/slots do not.

Frontend behavior: duplicate/idle result replay is ignored; explicit cache import remains available; graph isolation and append preservation pass; queued-event and rebuilt-panel ownership pass. 5000 repeated layout passes plus grow/shrink and geometry changes remain stable.

Remote checks: one Qwen endpoint; two approved synthetic adult references. FLUX.2, Krea2 and Anima full prompt-node requests returned ordered bindings and consistent UI/result JSON. No images, raw request logs, credentials or private endpoint addresses are packaged here. No rendered media was evaluated in these checks.

Release gate is scoped to these fixes, not to universal skill quality. Follow-up items: multi-model skill-on/off evaluation, complex-negation cases, ambiguous visual-detail restraint, and downstream rendered-media tests.
