# School compute handoff

Read `handoff/AGENT_TASKS_ZH.md` and `hpc/README.md` before substantial work.
The user wants to finish the H/He continuum replacement on the USTC Slurm platform.
This is a research continuation, not a claim that a complete atmosphere exists.

- Configure repository-local Git author identity before edits/commits. Use the user's
  verified identity; do not invent an email, copy another author's identity, or set
  machine-wide Git defaults. Never commit credentials or tokens.
- Code written by any agent other than the one that verified it must pass three
  review passes before it is executed on the platform: (1) interface read-through
  against the code it calls, (2) unit and negative-path tests, (3) an end-to-end run
  on real artifacts or a dry run that exercises the full entry point. Record what
  each pass found, including defects that had to be fixed. This user requirement is
  standing: do not submit a first-run job on code that has not been through all
  three passes.
- Keep the Mac historical `src/`, phase scripts, protocols and result bytes immutable
  until a separately named, documented migration or science branch is needed.
  Existing protocols hash their dependencies. A hash failure is evidence, not a
  reason to disable validation or silently regenerate the old protocol.
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
