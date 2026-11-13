"""Integration-test hooks. The synthetic report prints only after that module runs."""

from __future__ import annotations

import sys
from typing import Any


def pytest_terminal_summary(terminalreporter: Any) -> None:
    module = next(
        (
            candidate
            for candidate in sys.modules.values()
            if str(getattr(candidate, "__file__", "")).endswith("test_synthetic_e2e.py")
        ),
        None,
    )
    rows = getattr(module, "SCENARIO_ROWS", None) if module is not None else None
    if not rows:
        return
    terminalreporter.write_sep("=", "synthetic e2e (in-process latency, not a Cloud Run SLA)")
    terminalreporter.write_line(f"{'scenario':<42} {'result':<6} {'sent':>4} {'ms':>8}  sources")
    for row in rows:
        terminalreporter.write_line(
            f"{row.name:<42} {row.result:<6} {row.sent:>4} {row.synthetic_ms:>8.1f}  {row.sources}"
        )
        terminalreporter.write_line(f"    expected: {row.expected}")
        terminalreporter.write_line(f"    actual:   {row.actual}")
        if row.error:
            terminalreporter.write_line(f"    error:    {row.error}")
