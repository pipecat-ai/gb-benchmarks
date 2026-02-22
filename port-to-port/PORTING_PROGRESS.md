# Port-to-Port Standalone Repo Progress

Date started: 2026-02-22

## Goal

Create a clean, standalone repository at `~/src/gb-benchmarks` that contains the
`mini-rl-harness` benchmark as `port-to-port`, runnable without depending on the
Gradient Bang monorepo.

## Checklist

- [x] Read benchmark source code and related planning/docs in the monorepo.
- [x] Create target root directory: `~/src/gb-benchmarks`.
- [x] Initialize local git repository in `~/src/gb-benchmarks`.
- [x] Copy harness source into `~/src/gb-benchmarks/port-to-port` (excluding large run artifacts/caches).
- [x] Create this progress-tracking document.
- [x] Remove monorepo import dependencies from benchmark runner.
- [x] Verify benchmark can run from `~/src/gb-benchmarks` with `claude-sonnet-4-6`.
- [x] Write standalone `README.md` with setup/run instructions.
- [ ] Commit changes.

## Notes

- `gh` CLI is not available on this machine, so remote GitHub repo creation was
  not automated here.
- Existing harness history data under `runs/` was intentionally excluded to keep
  the standalone repo clean and lightweight.
- Smoke verification run:
  - Command executed from `~/src/gb-benchmarks` with `uv run --project port-to-port ...`
  - Output files:
    - `port-to-port/runs/smoke-claude-sonnet-4-6.log`
    - `port-to-port/runs/smoke-claude-sonnet-4-6.json`
  - Result: harness executed successfully; benchmark status was non-success due to
    deliberate `--max-turns 4` smoke cap.
