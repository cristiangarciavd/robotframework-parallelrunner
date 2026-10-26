# pabot + ParallelRunner timing demo

A small, offline demo that shows how much wall-clock time each tool saves,
and what happens when you combine them.

- 4 suites (`suites/`), one test each.
- Every test validates 8 items. Each validation is simulated I/O: it just
  waits 1 second (`DemoClient.validate_item`), so there is no network and the
  timings are reproducible.
- The `MODE` variable switches the loop between a plain sequential `FOR` loop
  and `Run Parallel Scenarios` (see `demo.resource`).

It lives here, not under `atest/`, so it does not slow down the regular test
run or CI.

## Run it

From the repository root, after `poetry install`:

```bash
poetry run invoke demo-pabot                         # 8 workers, 4 pabot processes
poetry run invoke demo-pabot --workers 4 --processes 2
```

The task runs the four combinations below and prints a table. It passes the
current Python interpreter to pabot (`--command ... --end-command`), so pabot
always uses the `robot` from the same environment.

To run a single combination by hand:

```bash
# sequential loop, plain robot
poetry run robot --pythonpath . --variable MODE:sequential examples/pabot_demo/suites
# ParallelRunner + pabot
ROBOT_THREAD_WORKERS=8 poetry run pabot --processes 4 --pythonpath . --variable MODE:parallel examples/pabot_demo/suites
```

On Windows PowerShell, set the variable first: `$env:ROBOT_THREAD_WORKERS = "8"`.

## Results

Measured on 2026-10-25 (ParallelRunner 0.4.0, Windows 11, Python 3.11,
pabot 5.2.2; median of 3 runs, which varied by up to ±0.3 s without pabot and
±1.2 s with it):

| Run | Wall-clock time | Speedup |
|---|---|---|
| robot, sequential loop | 32.9 s | ×1.0 |
| robot + ParallelRunner (8 workers) | 5.1 s | ×6.5 |
| pabot (4 processes), sequential loop | 12.4 s | ×2.7 |
| pabot (4 processes) + ParallelRunner (8 workers) | 4.6 s | ×7.2 |

How to read it:

- **32 s of pure waiting** (4 suites × 8 items × 1 s) is the baseline.
- **ParallelRunner** removes the wait *inside* each test: each suite's 8
  items run at once, so each test takes about 1 s instead of 8 s.
- **pabot** removes the wait *between* suites: the 4 suites run at once, so
  the total is about one suite's time (8 s) plus process start-up.
- **Both together**: about 1 s of real work, plus pabot's start-up cost
  (roughly 3.5 s here). With such short suites that fixed cost dominates,
  which is why combining them gains less over ParallelRunner alone than you
  might expect. With longer suites the start-up cost matters less and the
  combination pays off more.

Your numbers will depend on the machine, the worker and process counts, and
above all on how much of your real tests is spent waiting on I/O.
