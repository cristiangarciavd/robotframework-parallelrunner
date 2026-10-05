# ParallelRunner

[![PyPI](https://img.shields.io/pypi/v/robotframework-parallelrunner)](https://pypi.org/project/robotframework-parallelrunner/)
[![Python versions](https://img.shields.io/pypi/pyversions/robotframework-parallelrunner)](https://pypi.org/project/robotframework-parallelrunner/)
[![Tests](https://github.com/cristiangarciavd/robotframework-parallelrunner/actions/workflows/tests.yml/badge.svg)](https://github.com/cristiangarciavd/robotframework-parallelrunner/actions/workflows/tests.yml)

**Run a loop inside a single Robot Framework test case in parallel — with one clean `log.html`, not a merge of many.**

ParallelRunner is a small Robot Framework library that lets you fan a
keyword out across a thread pool from *within* a test case — e.g. hit 100
API endpoints, or repeat one check N times — and get back a single,
correctly ordered `log.html` plus a structured list of per-item results.

**Keyword documentation:** <https://cristiangarciavd.github.io/robotframework-parallelrunner/ParallelRunner.html>

## Installation

```bash
pip install robotframework-parallelrunner
```

Requires Python 3.9+ and Robot Framework 5.0+ (installed automatically).
See [docs/INSTALLATION.md](https://github.com/cristiangarciavd/robotframework-parallelrunner/blob/main/docs/INSTALLATION.md) for development installs
and upgrading from the pre-release import path.

## Quickstart

The keyword you want to parallelize is a method of a Python library. It
receives the current item first, and an injected `_logger` it should log
through (so logs from different threads never interleave):

```python
# my_library.py
class MyLibrary:
    def verify_agent_data(self, agent_id, _logger=None, **kwargs):
        _logger(f"Checking agent {agent_id}")
        ...
        return result
```

```robot
*** Settings ***
Library    ParallelRunner
Library    my_library.MyLibrary

*** Test Cases ***
Verify Agents In Parallel
    ${agents}=    Create List    1    2    3    4    5
    ${results}=    Run Parallel Scenarios
    ...    keyword=Verify Agent Data
    ...    library=my_library.MyLibrary
    ...    for_loop_iterable=${agents}
```

```bash
robot --pythonpath . my_suite.robot
```

See [docs/QUICKSTART.md](https://github.com/cristiangarciavd/robotframework-parallelrunner/blob/main/docs/QUICKSTART.md) for a full walkthrough and
[docs/API_REFERENCE.md](https://github.com/cristiangarciavd/robotframework-parallelrunner/blob/main/docs/API_REFERENCE.md) for every parameter of
`Run Parallel Scenarios`. For the internal design (log buffering, thread
safety), see [ARCHITECTURE.md](https://github.com/cristiangarciavd/robotframework-parallelrunner/blob/main/ARCHITECTURE.md).

## Why This Works

**Thread safety.** We avoid `BuiltIn().run_keyword()` inside threads, which is
the main cause of crashes in multi-threaded Robot Framework. We call the
underlying Python methods directly instead.

**No log interleaving.** Each worker thread buffers its own log messages in
memory. Once every task finishes, the main thread replays all buffered logs
sequentially into Robot Framework's real logger (`_replay_logs`). The result:
`log.html` shows logs grouped cleanly by item, even though the work happened
concurrently.

**Encapsulation.** Callers only ever see `Run Parallel Scenarios` — the
threading, buffering, and replay logic stay out of your `.robot` files.

## Summary of Benefits

- **Speed.** Validating 100 APIs that take 1s each takes roughly 10s (with 10
  workers) instead of 100s.
- **Integrity.** Your `log.html` remains the single source of truth — no
  broken XML tags from concurrent writes.
- **Flexibility.** Pass `repeat=10` to stress-test a single endpoint, or
  `for_loop_iterable=${items}` for batch validation of a whole list.
- **Ergonomics.** Results come back in call order (not completion order), so
  `${results}[0]` is always the first call. Add `return_values_only=True` to
  skip the status/logs envelope entirely and unpack each call's return value
  straight into its own variable — e.g. `${id1}    ${id2}    ${id3}=    Run Parallel Scenarios    ...    repeat=3    return_values_only=True`
  when seeding N independent fixture rows.

## How Is This Different From pabot?

[pabot](https://github.com/mkorpela/pabot) is the standard tool for parallel
execution in the Robot Framework ecosystem, and this project is not a
replacement for it — the two solve different problems and compose well
together.

| | **pabot** | **ParallelRunner** |
|---|---|---|
| Parallelizes at the level of | Suites / test cases | A loop (or repeated call) **inside one test case** |
| Execution model | Separate **processes** | **Threads** in the same process |
| Result merging | Runs each suite separately, then merges multiple `output.xml` files with `rebot` | Nothing to merge — logs are buffered per item and replayed into the *same* `log.html` in order |
| Best suited for | Running many independent suites/tests concurrently, across cores or machines | Fanning out inside a single test case (e.g. one test that validates 100 endpoints) |
| Workload type | Any (process isolation means CPU-bound work scales too) | I/O-bound work (HTTP calls, DB/network waits) — Python's GIL limits benefit for CPU-bound work |

Concretely:

- **pabot** takes your existing suites/tests, runs several of them at once as
  separate OS processes (so they don't share memory or a GIL), and then stitches
  the independent `output.xml` results back into one report. It answers: "I
  have many independent tests, how do I run them all faster?"
- **ParallelRunner** answers a different question: "I have *one* test case
  that needs to do the same kind of work many times (loop over a list of IDs,
  or repeat something N times) — how do I parallelize the body of that loop
  without corrupting the log or needing to merge anything?" It uses a
  `ThreadPoolExecutor` inside a single process, and produces one
  already-merged, already-ordered log for that test case.
- Because ParallelRunner uses **threads**, not processes, it shares memory and
  is subject to the GIL — it is a good fit for **I/O-bound** work (network
  calls, waiting on APIs/databases) where threads spend most of their time
  blocked on I/O, not a good fit for CPU-bound number crunching.
- The two are **complementary**: you can use pabot to run many suites in
  parallel across processes, where individual test cases *within* those suites
  use ParallelRunner to parallelize their own inner loops across threads.

If you need to speed up "run these 50 independent test files faster," reach
for pabot. If you need to speed up "this one test case loops over 100 items
and I want a single readable log instead of 100 sequential HTTP round trips
(or 100 merged `output.xml` files)," that's what ParallelRunner is for.

## When Not To Use This

- **CPU-bound work.** Threads share Python's GIL — number crunching won't
  get faster this way. Use `multiprocessing`, or pabot (separate processes),
  instead.
- **Your keyword mutates shared state without synchronization.** Logging is
  made thread-safe for you; your own keyword's side effects are not. If it
  writes to a shared variable, file, or object without a lock, running it
  concurrently can race the same way any multi-threaded code can.
- **You need per-item retries or a timeout.** Not implemented yet (see
  [ROADMAP.md](https://github.com/cristiangarciavd/robotframework-parallelrunner/blob/main/ROADMAP.md)) — one hung call currently blocks the whole batch
  from returning.
- **You need process-level isolation** (a crash in one call shouldn't be
  able to affect another) or cross-machine parallelism — that's pabot's
  domain, not this library's.

## Project Structure

```
ParallelRunner/
├── src/ParallelRunner/     # The installable library (core, do not depend on internals prefixed with `_`)
├── examples/               # Example "business logic" libraries used by the test suites
├── atest/            # Robot Framework acceptance suites
├── docs/                   # INSTALLATION, QUICKSTART, API_REFERENCE
└── ARCHITECTURE.md         # Technical deep dive
```

See [ARCHITECTURE.md](https://github.com/cristiangarciavd/robotframework-parallelrunner/blob/main/ARCHITECTURE.md) for the full breakdown and design
principles.

### Optional: UI automation with Playwright

The same thread-pool approach applies to browser automation, not just HTTP
calls — see [examples/playwright_ui/](https://github.com/cristiangarciavd/robotframework-parallelrunner/tree/main/examples/playwright_ui/) for a
worked example using Playwright's official `sync_api`. It's kept out of
the default install and CI (heavy dependency, real browser download), so
it's opt-in: read that folder's README before installing anything.

## Contributing

See [CONTRIBUTING.md](https://github.com/cristiangarciavd/robotframework-parallelrunner/blob/main/CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](https://github.com/cristiangarciavd/robotframework-parallelrunner/blob/main/CODE_OF_CONDUCT.md).
For what's done and what's planned, see [ROADMAP.md](https://github.com/cristiangarciavd/robotframework-parallelrunner/blob/main/ROADMAP.md) and
[CHANGELOG.md](https://github.com/cristiangarciavd/robotframework-parallelrunner/blob/main/CHANGELOG.md).

## License

MIT — see [LICENSE](https://github.com/cristiangarciavd/robotframework-parallelrunner/blob/main/LICENSE).
