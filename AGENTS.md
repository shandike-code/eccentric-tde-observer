# School compute handoff

Read `handoff/AGENT_TASKS_ZH.md` and `hpc/README.md` before substantial work.
The user wants to finish the H/He continuum replacement on the USTC Slurm platform.
This is a research continuation, not a claim that a complete atmosphere exists.

- Configure repository-local Git author identity before edits/commits. Use the user's
  verified identity; do not invent an email, copy another author's identity, or set
  machine-wide Git defaults. Never commit credentials or tokens.
- MANDATORY PRE-RUN CHECK (user requirement, 2026-09-18). This is a physics project:
  the chain physics model -> mathematical formula -> code -> numerical result must be
  correct, closed and explainable, so "the code runs" is never sufficient. Before
  running any code, perform and report three checks:
  (1) **Code**: syntax, variables/functions/array shapes, types, indices, NaN/Inf and
      division-by-zero, explicit units and definitions, and whether the code really
      implements the intended formula rather than merely running;
  (2) **Logic**: walk input -> model assumptions -> formula -> computation -> output;
      every key variable has a stated source, every formula maps to code, and there is
      no logical gap, hidden assumption or ad-hoc correction;
  (3) **Physics**: dimensional consistency, order of magnitude, limiting cases against
      physical intuition, conservation laws, trends under parameter changes, and
      whether the result matches a defensible physical picture.
  Emit exactly this block before running, naming what was actually checked (never just
  "checked, no problems"):

  ```text
  [PRE-RUN CHECK]

  Code: PASS / WARNING / BLOCK
  Logic: PASS / WARNING / BLOCK
  Physics: PASS / WARNING / BLOCK

  Key Issues:
  1. ...
  2. ...
  3. ...

  Decision: RUN / DO NOT RUN
  ```

  If a formula, unit, model assumption or physical interpretation is uncertain, say so
  explicitly instead of guessing. If a result looks wrong, never adjust the result,
  add an unexplained correction factor or retune parameters to make a figure look
  plausible: diagnose units -> formula -> code -> initial conditions -> numerical method.
  After a successful run, perform a POST-RUN CHECK covering warnings, NaN/Inf or
  divergence, order of magnitude, whether trends match theory, numerical artefacts in
  figures, and whether the result is explainable by the physical model.
  Priority is always: physics correct > logic closed > numerically reliable > code runs.
  The earlier three review passes (interface read-through, unit/negative-path tests,
  real-artifact end-to-end) remain required as the *how*; this block is the *evidence*
  that must accompany every platform submission.
- Keep the Mac historical `src/`, phase scripts, protocols and result bytes immutable
  until a separately named, documented migration or science branch is needed.
  Existing protocols hash their dependencies. A hash failure is evidence, not a
  reason to disable validation or silently regenerate the old protocol.
- A candidate run IS its `trial_material.npz`: the encoded vector in that file
  defines the experiment. `hpc/pipeline.py::run_pipeline` calls `migrate_trial()`
  whenever a new run has no trial on disk, which **silently substitutes the fixed
  MATERIAL candidate (the 0.0625 step)**. On 2026-09-18 that replaced two small-step
  candidates, produced a verdict about the wrong step, and forced a retraction
  (`handoff/linux-runs/2026-09-18-RETRACTION-trial-identity-error.md`). Therefore:
  any script that creates a run must write or copy the intended trial **before** the
  run is initialized, and must assert `encoded_state`, `base_encoded_state`,
  `finite_direction`, `base_residual` and `relaxation` bitwise against the source
  trial. Config-, seed- or hash-only checks do not satisfy the triple check; if the
  trial identity is not asserted, the check is incomplete and the run must not start.
- Run significant computation only inside a Slurm allocation. WebShell hardware and
  `free -h` are not the job's CPU/memory allocation. Do not assume 48 CPUs/125 GiB
  are available to this user. The existing runner uses exactly two workers.
- First establish clean-checkout smoke tests, artifact integrity, cross-platform
  numerical parity, and one complete 76-block mapping with measured resource use.
- The discussion permits investigating a modestly relaxed inner radiation criterion.
  Use a NEW protocol for a candidate threshold of 2.5e-4 and compare against 2e-4
  and the original 1e-4. The threshold has NOT been changed in the old runner.
  Do not relax positivity, conservation, frequency ownership, matter-domain checks,
  feedback stability, or the outer material-residual acceptance criteria.
- Never use arbitrary clipping, floors, nan_to_num, omitted failed cells, or post-hoc
  normalization to pass a science gate. Report numerical and physical failures.
- Preserve the distinction between an inner radiation solution, one accepted matter
  step, a converged coupled column, a full-domain atmosphere table, and an observer
  spectrum. Phase 6 is only a conditional kinematic line kernel.
- Checkpoint files are external data. Do not add `.dat`, simulation products,
  environments, binaries, personal notes outside this project, or papers to Git.
  Do not delete historical checkpoints without explicit user authorization.
- Save every new run under its own name with Git commit, configuration hash,
  environment, scheduler job ID, residuals, energy/feedback metrics, and timings.
- Follow `docs/code_conventions.md` for physical notation and new code. The legacy
  Markdown normalizer has known over-broad transformations; inspect its proposed
  diff and do not blindly run `--write` over the lecture archive.

Scope authorization already includes ordinary implementation, tests and batch runs
needed for this handoff's research milestones within granted school resources.
Do not repeatedly ask permission for each reversible implementation step. Ask only
for missing access, new resource charges, destructive changes, or changed science scope.
