# Backend Tests

Backend tests must preserve the runtime invariants they exercise without changing production execution topology.

## Platform-specific fixtures

Native Windows cannot report POSIX execute or owner/group mode bits through
`stat`. Tests dedicated to actual POSIX permission results must declare a
Windows skip explicitly. Portable error-recovery tests still run: keep the
real chmod call, verify the requested mode and retry behavior, and assert the
filesystem's resulting mode only on POSIX. Never treat such a skip as Windows
ACL coverage.

Blocking-I/O CLI fixtures must launch a real local subprocess on both platforms.
Use an executable shell script on POSIX and a `.cmd` launcher invoking the
current Python interpreter on Windows. Keep fixture paths quoted, prepend the
fixture directory to PATH, and assert that the resolved CLI path is the fixture.
Do not require a globally installed CLI or replace subprocess execution with
a mock to make the strict gate pass.

## Executor starvation tests

`test_executor_starvation.py` covers the deterministic starvation semantics from RFC #4560:

- default-executor saturation and queueing;
- cancellation of an awaiter while an already-started synchronous worker continues;
- isolation between the asyncio default executor and OmniHarness's dedicated file-I/O executor.

Use explicit synchronization such as `threading.Event` rather than sleep-based timing thresholds for worker lifecycle assertions. Every test must release blocked workers and restore any process-global monkeypatches so teardown cannot leak threads or state into later tests.

Stress/soak testing, AnyIO worker instrumentation, Uvicorn multi-process behavior, and broad production executor redesign are separate concerns and should not be folded into these deterministic regressions.
