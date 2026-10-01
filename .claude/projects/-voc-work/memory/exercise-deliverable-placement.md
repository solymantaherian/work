---
name: exercise-deliverable-placement
description: In the lesson-5 exercise repo, concept starter deliverables go flat at starter/, not inside the expense_tracker/ package
metadata:
  type: project
---

In `/voc/work/exercises/lesson-5-collaborate-with-ai-throughout-development`,
each concept's `starter/` holds root-level exercise tests that import flat
modules (`from transaction_loader import ...`, `from report_modes import ...`).
Those flat modules at `starter/` are the deliverable location. The
`starter/expense_tracker/` package is pre-supplied reference material with an
incompatible contract (`Decimal` + `Transaction` objects + custom exceptions,
vs. the prompts' `dict` + `float` + `ValueError`), and its own passing tests
under `starter/tests/`.

Decided 2026-09-30: keep deliverables flat; do not restructure them into the
package or overwrite package modules.

**Why:** The exercise prompts' specs only satisfy the flat root tests, and the
package slots are already filled with working, tested code.

**How to apply:** Write concept deliverables to `starter/<module>.py`. Don't
"fix" the placement against the concept1 architecture plan — the plan describes
the package, which is already built.
