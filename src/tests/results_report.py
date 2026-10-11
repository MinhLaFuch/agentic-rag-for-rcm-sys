"""Pytest plugin: write the input and output of EVERY test into ONE results file.

Why: a plain pass/fail log says nothing about *what* a test fed into the code and *what* came back.
This plugin records, per test, so a failure can be diagnosed from the file alone:

  * source        the test's own source (the assertions are the "expected" side)
  * inputs        fixture values / parametrize values the test received
  * calls         every call the test body makes into ``package/`` (or ``scripts/``):
                  arguments in -> return value (or exception) out
  * locals        variables the test body created (``result``, ``candidates``, ...) at the end
                  (or at the moment of failure)
  * error         assertion message + short traceback for failed tests
  * captured      stdout / stderr / log output of the test

No test needs to be edited: calls are captured with ``sys.monitoring`` (Python 3.12+) while the test body
runs, so there is no effect on fixtures/teardown and almost no overhead on stdlib/pandas calls.

Usage (wired up from tests/conftest.py)::

    pytest tests/                                   # -> tests/logs/test_results_<timestamp>.md
    pytest tests/ --results-file=out/results.json   # extension picks the format: .md or .json (use '=')
    pytest tests/ --no-results                      # disable
    TEST_RESULTS_FILE=out/r.md pytest tests/        # env var alternative to --results-file
"""

from __future__ import annotations

import dataclasses
import inspect
import json
import os
import platform
import sys
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

TESTS_DIR = Path(__file__).resolve().parent
PROJECT_DIR = TESTS_DIR.parent
DEFAULT_RESULTS_DIR = TESTS_DIR / "logs"

# Code under test: calls from test code into these directories are recorded as "input -> output".
TRACED_DIRS = tuple(str(PROJECT_DIR / name) + os.sep for name in ("package", "scripts"))
TESTS_PREFIX = str(TESTS_DIR) + os.sep

MAX_CALLS_PER_TEST = 60  # beyond this the rest is only counted
MAX_ITEMS = 8  # list / dict / set entries shown
MAX_DEPTH = 3  # nesting depth shown
MAX_STR = 400  # characters of a single string value
MAX_VALUE = 1200  # characters of one rendered value
MAX_CAPTURED = 4000  # characters of captured stdout / stderr / log kept per section

# Fixtures that are plumbing, not test input.
SKIP_FIXTURES = {"request", "monkeypatch", "capsys", "capfd", "caplog", "capsysbinary", "capfdbinary",
                 "pytestconfig", "tmp_path_factory", "tmpdir_factory", "record_property", "cache", "doctest_namespace"}

_NO_TRACE_FLAGS = inspect.CO_GENERATOR | inspect.CO_COROUTINE | inspect.CO_ASYNC_GENERATOR


# ----------------------------------------------------------------------------------------------
# Value rendering: turn arbitrary objects into short, readable, never-failing strings
# ----------------------------------------------------------------------------------------------
def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else f"{text[:limit]}... <+{len(text) - limit} chars>"


def _is_default_repr(obj: Any) -> bool:
    return type(obj).__repr__ is object.__repr__


def fmt(obj: Any, depth: int = 0, _seen: frozenset[int] = frozenset()) -> str:
    """Short human-readable rendering of ``obj``. Never raises."""
    try:
        return _clip(_fmt(obj, depth, _seen), MAX_VALUE if depth == 0 else MAX_STR)
    except Exception as exc:  # a broken __repr__ must not break the report
        return f"<unrenderable {type(obj).__name__}: {type(exc).__name__}>"


def _fmt(obj: Any, depth: int, seen: frozenset[int]) -> str:
    if obj is None or isinstance(obj, (bool, int, float, complex)):
        return repr(obj)
    if isinstance(obj, str):
        return repr(_clip(obj, MAX_STR))
    if isinstance(obj, (bytes, bytearray)):
        return repr(bytes(obj[:MAX_STR])) + (f"... <+{len(obj) - MAX_STR} bytes>" if len(obj) > MAX_STR else "")
    if isinstance(obj, Path):
        return f"Path({str(obj)!r})"
    if isinstance(obj, BaseException):
        return f"{type(obj).__name__}: {_clip(str(obj), MAX_STR)}"
    if inspect.isclass(obj):
        return f"<class {obj.__name__}>"
    if inspect.ismodule(obj):
        return f"<module {obj.__name__}>"
    if inspect.isroutine(obj):
        return f"<function {getattr(obj, '__qualname__', repr(obj))}>"
    if id(obj) in seen:
        return "<recursive>"
    seen = seen | {id(obj)}

    mod, name = type(obj).__module__.split(".")[0], type(obj).__name__
    if mod == "pandas" and name == "DataFrame":
        head = obj.head(5).to_string(max_cols=12, max_colwidth=40)
        return f"DataFrame shape={obj.shape}\n{textwrap.indent(head, '    ')}"
    if mod == "pandas" and name == "Series":
        return f"Series name={obj.name!r} shape={obj.shape}\n{textwrap.indent(obj.head(8).to_string(max_colwidth=40), '    ')}"
    if mod == "numpy" and name == "ndarray":
        sample = obj.ravel()[:MAX_ITEMS].tolist()
        return f"ndarray shape={obj.shape} dtype={obj.dtype} values={sample}{' ...' if obj.size > MAX_ITEMS else ''}"
    if mod == "numpy":  # numpy scalars
        return repr(obj)
    if mod == "scipy" and hasattr(obj, "nnz"):
        return f"{name} shape={obj.shape} nnz={obj.nnz} dtype={obj.dtype}"

    if depth >= MAX_DEPTH:
        return f"<{name}>"
    sub = lambda v: fmt(v, depth + 1, seen)  # noqa: E731

    if isinstance(obj, dict):
        items = [f"{sub(k)}: {sub(v)}" for k, v in list(obj.items())[:MAX_ITEMS]]
        more = f", ... <+{len(obj) - MAX_ITEMS} more>" if len(obj) > MAX_ITEMS else ""
        return "{" + ", ".join(items) + more + "}"
    if isinstance(obj, (list, tuple, set, frozenset)):
        seq = list(obj)[:MAX_ITEMS]
        more = f", ... <+{len(obj) - MAX_ITEMS} more>" if len(obj) > MAX_ITEMS else ""
        body = ", ".join(sub(v) for v in seq) + more
        if isinstance(obj, list):
            return f"[{body}]"
        if isinstance(obj, tuple):
            return f"({body}{',' if len(seq) == 1 and not more else ''})"
        return "{" + body + "}"
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        fields = ", ".join(f"{f.name}={sub(getattr(obj, f.name, None))}" for f in dataclasses.fields(obj)[:MAX_ITEMS * 2])
        return f"{name}({fields})"
    if not _is_default_repr(obj):
        return _clip(repr(obj), MAX_STR)
    attrs = getattr(obj, "__dict__", None)
    if attrs:
        shown = ", ".join(f"{k}={sub(v)}" for k, v in list(attrs.items())[:MAX_ITEMS] if not k.startswith("__"))
        return f"{name}({shown})"
    return f"<{name}>"


# ----------------------------------------------------------------------------------------------
# Call tracer: records calls from test code into the code under test (Python 3.12+ sys.monitoring)
# ----------------------------------------------------------------------------------------------
_MON = getattr(sys, "monitoring", None)  # None on Python < 3.12: calls are then not traced
_PRIVATE_LOCAL = ("__", "@")  # dunder names and pytest's assertion-rewrite temporaries (@py_assert0, ...)


class CallTracer:
    """Collects the outermost calls made from test code into ``package/`` while ONE test body runs."""

    def __init__(self, test_code, fixture_names: set[str]) -> None:
        self.test_code = test_code
        self.fixture_names = fixture_names
        self.calls: list[dict] = []
        self.skipped_calls = 0
        self.locals: dict[str, str] = {}
        self._test_frame = None
        self._pending: dict[Any, dict] = {}

    def on_start(self, code, frame) -> None:
        if code is self.test_code and self._test_frame is None:
            self._test_frame = frame
            return
        if kind_of(code) != "code" or code.co_flags & _NO_TRACE_FLAGS:
            return
        caller = frame.f_back
        # Only the outermost call: test code -> code under test (not internal calls deeper down).
        if caller is None or not (caller is self._test_frame or kind_of(caller.f_code) == "test"):
            return
        if len(self.calls) >= MAX_CALLS_PER_TEST:
            self.skipped_calls += 1
            return
        argc = code.co_argcount + code.co_kwonlyargcount
        names = list(code.co_varnames[:argc])
        if code.co_flags & inspect.CO_VARARGS:
            names.append(code.co_varnames[argc])
            argc += 1
        if code.co_flags & inspect.CO_VARKEYWORDS:
            names.append(code.co_varnames[argc])
        values = frame.f_locals
        owner = None
        if names and names[0] in ("self", "cls"):
            first = values.get(names[0])
            owner = first.__name__ if inspect.isclass(first) else type(first).__name__
            names = names[1:]
        record = {
            "call": f"{owner}.{code.co_name}" if owner else code.co_name,
            "module": frame.f_globals.get("__name__", ""),
            "input": {n: fmt(values[n]) for n in names if n in values},
            "output": None,
            "raised": None,
        }
        self._pending[frame] = record
        self.calls.append(record)

    def on_return(self, code, frame, retval, exc) -> None:
        record = self._pending.pop(frame, None)
        if record is not None:
            if exc is not None:
                record["raised"] = fmt(exc)
            elif code.co_name == "__init__":
                record["output"] = fmt(frame.f_locals.get("self"))
            else:
                record["output"] = fmt(retval)
        elif frame is self._test_frame:
            self.locals = {
                k: fmt(v) for k, v in frame.f_locals.items()
                if not k.startswith(_PRIVATE_LOCAL) and k not in self.fixture_names
            }


_KIND_CACHE: dict[Any, str] = {}


def kind_of(code) -> str:
    """'code' = code under test, 'test' = anything under tests/, 'other' = stdlib / pandas / pytest / ..."""
    kind = _KIND_CACHE.get(code)
    if kind is None:
        path = code.co_filename
        kind = "code" if path.startswith(TRACED_DIRS) else "test" if path.startswith(TESTS_PREFIX) else "other"
        _KIND_CACHE[code] = kind
    return kind


class Monitor:
    """Owns the sys.monitoring tool slot for the whole session; routes events to the active CallTracer."""

    def __init__(self) -> None:
        self.tool = None
        self.active: CallTracer | None = None
        if _MON is None:
            return
        for tool_id in (3, 4, 2):  # slots not claimed by debugger(0), coverage(1) or optimizer(5)
            try:
                _MON.use_tool_id(tool_id, "test-results")
            except ValueError:
                continue
            self.tool = tool_id
            ev = _MON.events
            _MON.register_callback(tool_id, ev.PY_START, self._start)
            _MON.register_callback(tool_id, ev.PY_RETURN, self._return)
            _MON.register_callback(tool_id, ev.PY_UNWIND, self._unwind)
            break

    @property
    def available(self) -> bool:
        return self.tool is not None

    def _start(self, code, offset):
        tracer = self.active
        kind = kind_of(code)
        if kind == "other":
            return _MON.DISABLE  # never interesting: stop receiving events for this code object
        if tracer is None:
            return None
        try:
            tracer.on_start(code, sys._getframe(1))
        except Exception:  # tracing must never break a test
            pass
        return None

    def _return(self, code, offset, retval):
        if kind_of(code) == "other":
            return _MON.DISABLE
        if self.active is not None:
            try:
                self.active.on_return(code, sys._getframe(1), retval, None)
            except Exception:
                pass
        return None

    def _unwind(self, code, offset, exc):
        if self.active is not None and kind_of(code) != "other":
            try:
                self.active.on_return(code, sys._getframe(1), None, exc)
            except Exception:
                pass

    def start(self, tracer: CallTracer) -> None:
        if self.tool is None:
            return
        self.active = tracer
        ev = _MON.events
        _MON.set_events(self.tool, ev.PY_START | ev.PY_RETURN | ev.PY_UNWIND)

    def stop(self) -> None:
        self.active = None
        if self.tool is not None:
            _MON.set_events(self.tool, 0)

    def close(self) -> None:
        if self.tool is not None:
            self.stop()
            _MON.free_tool_id(self.tool)
            self.tool = None


# ----------------------------------------------------------------------------------------------
# The plugin
# ----------------------------------------------------------------------------------------------
def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("results", "per-test input/output results file")
    group.addoption("--results-file", default=None, metavar="PATH",
                    help="write input/output of every test to this ONE file (.md or .json); "
                         "write it as --results-file=PATH (with '=') so pytest does not mistake PATH for a test path. "
                         f"Default: {DEFAULT_RESULTS_DIR.name}/test_results_<timestamp>.md")
    group.addoption("--no-results", action="store_true", default=False, help="do not write the results file")


def pytest_configure(config: pytest.Config) -> None:
    if config.getoption("no_results", default=False) or hasattr(config, "workerinput"):  # skip xdist workers
        return
    target = config.getoption("results_file", default=None) or os.environ.get("TEST_RESULTS_FILE")
    if not target:
        target = DEFAULT_RESULTS_DIR / f"test_results_{datetime.now():%Y%m%d_%H%M%S}.md"
    config.pluginmanager.register(ResultsRecorder(Path(target)), "results_recorder")


class ResultsRecorder:
    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.started = datetime.now()
        self.records: dict[str, dict] = {}  # nodeid -> record, insertion order == execution order
        self.written = False
        self.monitor = Monitor()

    # -- per-test data ---------------------------------------------------------------------
    def _record(self, nodeid: str) -> dict:
        return self.records.setdefault(nodeid, {
            "nodeid": nodeid, "outcome": None, "duration_s": 0.0, "when_failed": None,
            "description": "", "source": "", "inputs": {}, "calls": [], "calls_omitted": 0,
            "locals": {}, "error": "", "traceback": "", "captured": {},
        })

    @pytest.hookimpl(hookwrapper=True)
    def pytest_pyfunc_call(self, pyfuncitem: pytest.Function):
        """Wraps ONLY the test body (not fixture setup/teardown) to trace its calls."""
        rec = self._record(pyfuncitem.nodeid)
        func = pyfuncitem.obj
        try:
            rec["source"] = textwrap.dedent(inspect.getsource(func)).rstrip()
            doc = inspect.getdoc(func)
            rec["description"] = doc.strip().splitlines()[0] if doc else ""
        except (OSError, TypeError):
            pass
        arg_names = [n for n in pyfuncitem._fixtureinfo.argnames]
        rec["inputs"] = {n: fmt(pyfuncitem.funcargs[n]) for n in arg_names
                         if n in pyfuncitem.funcargs and n not in SKIP_FIXTURES}
        code = getattr(inspect.unwrap(func), "__code__", None)
        tracer = CallTracer(code, set(arg_names))
        self.monitor.start(tracer)
        try:
            yield
        finally:
            self.monitor.stop()
            rec["calls"] = tracer.calls
            rec["calls_omitted"] = tracer.skipped_calls
            rec["locals"] = tracer.locals

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item: pytest.Item, call: pytest.CallInfo):
        outcome = yield
        report: pytest.TestReport = outcome.get_result()
        rec = self._record(item.nodeid)
        rec["duration_s"] = round(rec["duration_s"] + report.duration, 4)
        if report.when == "call":
            if hasattr(report, "wasxfail"):
                rec["outcome"] = "xfailed" if report.skipped else "xpassed"
            else:
                rec["outcome"] = report.outcome
        elif report.failed:
            rec["outcome"], rec["when_failed"] = "error", report.when
        elif report.skipped and rec["outcome"] is None:
            rec["outcome"] = "skipped"
        if report.failed or report.skipped:
            if call.excinfo is not None:
                rec["error"] = _clip(call.excinfo.exconly(tryshort=True), MAX_CAPTURED)
            rec["traceback"] = _clip(report.longreprtext, MAX_CAPTURED * 2)
        for title, content in report.sections:  # e.g. "Captured stdout call"; later phases repeat earlier ones
            key = title.removeprefix("Captured ").strip()
            if content.strip() and key not in rec["captured"]:
                rec["captured"][key] = _clip(content.rstrip(), MAX_CAPTURED)

    # -- output ----------------------------------------------------------------------------
    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        for rec in self.records.values():  # tests that never produced a report (e.g. interrupted)
            rec["outcome"] = rec["outcome"] or "not run"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        meta = {
            "started": self.started.isoformat(timespec="seconds"),
            "duration_s": round((datetime.now() - self.started).total_seconds(), 2),
            "command": " ".join(["pytest", *map(str, session.config.invocation_params.args)]),
            "python": platform.python_version(), "platform": platform.platform(), "pytest": pytest.__version__,
            "exit_status": int(exitstatus),
        }
        tests = list(self.records.values())
        counts: dict[str, int] = {}
        for t in tests:
            counts[t["outcome"]] = counts.get(t["outcome"], 0) + 1
        if self.path.suffix.lower() == ".json":
            text = json.dumps({"meta": meta, "summary": counts, "tests": tests}, indent=2, ensure_ascii=False)
        else:
            text = render_markdown(meta, counts, tests)
        self.path.write_text(text, encoding="utf-8")
        self.written = True
        self.monitor.close()

    def pytest_terminal_summary(self, terminalreporter) -> None:
        if self.written:
            terminalreporter.write_sep("-", "per-test input/output results")
            terminalreporter.write_line(f"saved to: {self.path}")


# ----------------------------------------------------------------------------------------------
# Markdown rendering
# ----------------------------------------------------------------------------------------------
_ORDER = {"failed": 0, "error": 1, "xpassed": 2, "not run": 3, "skipped": 4, "xfailed": 5, "passed": 6}


def _block(text: str) -> str:
    return "```text\n" + text.rstrip() + "\n```"


def _render_call(i: int, call: dict) -> str:
    lines = [f"[{i}] {call['call']}"]
    pad = "\n" + " " * 11
    for k, v in (call["input"] or {"": "(no arguments)"}).items():
        lines.append("    in : " + (f"{k} = {v}" if k else v).replace("\n", pad))
    if call["raised"] is not None:
        lines.append(f"    RAISED: {call['raised']}")
    else:
        lines.append("    out: " + (call["output"] or "None").replace("\n", pad))
    return "\n".join(lines)


def _render_test(t: dict) -> str:
    out = [f"### [{t['outcome'].upper()}] `{t['nodeid']}`  ({t['duration_s']}s)"]
    if t["description"]:
        out.append(f"_{t['description']}_")
    if t["when_failed"]:
        out.append(f"**Failed during:** {t['when_failed']}")
    if t["error"]:
        out += ["**Error**", _block(t["error"])]
    if t["traceback"] and t["outcome"] in ("failed", "error"):
        out += ["**Traceback**", _block(t["traceback"])]
    if t["source"]:
        out += ["**Test source** (assertions = expected values)", "```python\n" + t["source"] + "\n```"]
    if t["inputs"]:
        out += ["**Inputs** (fixtures / parameters)", _block("\n".join(f"{k} = {v}" for k, v in t["inputs"].items()))]
    if t["calls"]:
        body = "\n".join(_render_call(i, c) for i, c in enumerate(t["calls"], 1))
        if t["calls_omitted"]:
            body += f"\n... {t['calls_omitted']} more calls not shown"
        out += ["**Calls into the code under test** (input -> output)", _block(body)]
    if t["locals"]:
        out += ["**Variables in the test body** (final values)", _block("\n".join(f"{k} = {v}" for k, v in t["locals"].items()))]
    for title, content in t["captured"].items():
        out += [f"**Captured {title}**", _block(content)]
    return "\n\n".join(out)


def render_markdown(meta: dict, counts: dict, tests: list[dict]) -> str:
    head = [
        f"# Test results - {meta['started']}",
        "",
        f"- command: `{meta['command']}`",
        f"- python {meta['python']} / pytest {meta['pytest']} / {meta['platform']}",
        f"- duration: {meta['duration_s']}s, exit status: {meta['exit_status']}",
        *([] if _MON is not None else ["- NOTE: Python < 3.12 -> calls into the code under test are not traced (no sys.monitoring)"]),
        "- summary: " + (", ".join(f"{v} {k}" for k, v in sorted(counts.items(), key=lambda kv: _ORDER.get(kv[0], 9))) or "no tests"),
        "",
        "## Index",
        "",
        "| status | test | seconds |",
        "|---|---|---|",
    ]
    ordered = sorted(tests, key=lambda t: _ORDER.get(t["outcome"], 9))  # stable: failures first, run order kept
    head += [f"| {t['outcome']} | `{t['nodeid']}` | {t['duration_s']} |" for t in ordered]
    body = ["", "## Details (failures first)", ""]
    body += [_render_test(t) + "\n" for t in ordered]
    return "\n".join(head + body) + "\n"
