# Log levels and timeouts

`ShipmentCheckClient` (in `shipment_check_client.py`) checks a batch of
shipments in parallel and logs at every Robot Framework level, so you can see
how the messages from the threads end up in `log.html`. Offline and
deterministic: the shipment id decides what happens.

| Shipment id contains | What the call does |
|---|---|
| (anything else) | Logs `INFO`, `TRACE`, `DEBUG` and `HTML`, then passes. |
| `late` | Same, plus a `WARN`. |
| `lost` | Same, plus an `ERROR`, then fails. |
| `stuck` | Hangs for `stuck_seconds` (default 60) before answering. |

## Run it

From the repository root:

```bash
# Every level visible in log.html:
robot --pythonpath . --loglevel TRACE examples/log_levels/log_levels.robot

# Robot's default --loglevel (INFO): the TRACE and DEBUG lines disappear.
robot --pythonpath . examples/log_levels/log_levels.robot

# Leave out the test that fails on purpose (the [Timeout] demo):
robot --pythonpath . --exclude fails-on-purpose examples/log_levels/log_levels.robot
```

## What to look at in log.html

- **Every Level Ends Up In The Log**: each item's block has its messages in
  the order the call logged them. `TRACE` (`GET /shipments/...`) and `DEBUG`
  (`Response: ...`) only appear with a low enough `--loglevel`. The `HTML`
  message is rendered (bold id, italic state).
- **Only Warnings And Errors From The Threads**: `thread_log_level=WARN`
  replays only the "is late" warnings, whatever `--loglevel` says.
- **Debug Without Trace**: `thread_log_level=DEBUG` leaves out the `TRACE`
  request lines even with `--loglevel TRACE`.
- **Only The Logs Of Failed Calls**: `remove_passing_logs=True` keeps only the
  lost shipment, with everything it logged before failing.
- **A Timeout Stops Waiting For A Hanging Call** (fails on purpose): the test
  fails after its 2-second `[Timeout]`, not after the 60 seconds
  `S-3-stuck` hangs for. The log shows a summary line ("1 call(s) finished,
  ..."), the finished calls as usual, and `S-3-stuck` with its partial logs
  and an `ERROR` saying it did not finish. The hanging call keeps running in
  the background, but it doesn't keep Robot from exiting.

## Levels in your own keyword

```python
def check_something(self, item, _logger=None, **kwargs):
    log = _logger or (lambda msg, level="INFO": logger.write(msg, level))
    log("starting")                       # INFO (the default)
    log(f"request: {payload}", "TRACE")
    log(f"response: {body}", "DEBUG")
    log("<b>bold</b> in log.html", "HTML")
    log("shown on the console too", "CONSOLE")
    log("something is off", "WARN")
    log("something failed", "ERROR")
    log("dropped", "IGNORE")
```

Levels are case-insensitive, and Python `logging` names work too (`WARNING`,
`CRITICAL`). A message with any other level is still logged, at `INFO` with
the level as a prefix, plus a warning that names the unknown level.
