"""TTAP conformance kit. Any wholesaler can certify its gateway:

    uv run pytest conformance --server-url https://gateway.example --agent-key K1 --other-agent-key K2

Requirements are marked `must` or `should` (RFC 2119). A JSON report is written to conformance/compatibility.json.
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest


def pytest_addoption(parser):
    parser.addoption("--server-url", default="http://localhost:8811")
    parser.addoption("--agent-key", default="demo-key-hotel-a")
    parser.addoption("--other-agent-key", default="demo-key-resto-b")


def pytest_configure(config):
    config.addinivalue_line("markers", "must: mandatory requirement")
    config.addinivalue_line("markers", "should: recommended requirement")
    config._ttap_results = []


@pytest.fixture(scope="session")
def base(request) -> str:
    return request.config.getoption("--server-url").rstrip("/")


@pytest.fixture(scope="session")
def agent(request, base) -> httpx.Client:
    return httpx.Client(base_url=base, timeout=60, headers={"Authorization": f"Bearer {request.config.getoption('--agent-key')}"})


@pytest.fixture(scope="session")
def other(request, base) -> httpx.Client:
    return httpx.Client(base_url=base, timeout=60,
                        headers={"Authorization": f"Bearer {request.config.getoption('--other-agent-key')}"})


@pytest.fixture(scope="session")
def anon(base) -> httpx.Client:
    return httpx.Client(base_url=base, timeout=60)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
        level = "must" if item.get_closest_marker("must") else "should" if item.get_closest_marker("should") else "may"
        item.config._ttap_results.append({"requirement": item.name, "level": level, "outcome": report.outcome,
                                          "doc": (item.function.__doc__ or "").strip()})


def pytest_sessionfinish(session, exitstatus):
    results = getattr(session.config, "_ttap_results", [])
    if not results:
        return
    summary = {lvl: {"passed": sum(r["outcome"] == "passed" for r in results if r["level"] == lvl),
                     "total": sum(r["level"] == lvl for r in results)} for lvl in ("must", "should")}
    compliant = summary["must"]["passed"] == summary["must"]["total"]
    report = {"protocol": "TTAP", "server": session.config.getoption("--server-url"),
              "compliant": compliant, "summary": summary, "results": results}
    Path(__file__).with_name("compatibility.json").write_text(json.dumps(report, indent=1))
