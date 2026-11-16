"""POLARIS X mission-planner chat over the solver: SKELETON, never called tonight.

- Model: Gemini through Vertex AI (google-genai SDK, GOOGLE_GENAI_USE_VERTEXAI=True).
  Project and region come from GOOGLE_CLOUD_PROJECT / GOOGLE_CLOUD_LOCATION. No keys in code.
- Tools: the solver's own spec, `python -m polaris_solver --tool-spec`.
- Numbers come only from the solver. `grounding_check` rejects any number in the reply that is
  not present in that turn's tool results. Every reply is labelled AI-GENERATED.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

TOOLS_DIR = Path(__file__).resolve().parents[1]
LABEL = "AI-GENERATED (numbers quoted from POLARIS solver tool results only)"

_NUM = re.compile(r"(?<![\w.])[-+]?\d+(?:[.,]\d+)*(?:\.\d+)?(?:[eE][-+]?\d+)?")


def _numbers(text: str) -> set[str]:
    out = set()
    for m in _NUM.finditer(text):
        s = m.group(0).replace(",", "").lstrip("+")
        try:
            out.add(_canon(float(s)))
        except ValueError:
            continue
    return out


def _canon(x: float) -> str:
    return repr(float(x)).rstrip("0").rstrip(".") if "e" not in repr(float(x)) else repr(float(x))


def _walk_numbers(obj: Any, acc: set[str]) -> None:
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        acc.add(_canon(obj))
    elif isinstance(obj, str):
        acc |= _numbers(obj)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _walk_numbers(k, acc)
            _walk_numbers(v, acc)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _walk_numbers(v, acc)


def grounding_check(reply: str, tool_results: list[Any]) -> tuple[bool, list[str]]:
    """Return (ok, ungrounded). ok is False if any number in `reply` is absent from `tool_results`.

    Comparison is on canonical float value, so "72.1" matches 72.1 and "1,000" matches 1000.
    Rounding is NOT accepted: a reply that says 72 when the tool said 72.107 is rejected.
    """
    allowed: set[str] = set()
    _walk_numbers(tool_results, allowed)
    bad = sorted(n for n in _numbers(reply) if n not in allowed)
    return (not bad, bad)


def load_tool_spec(python: str | None = None) -> Any:
    py = python or os.environ.get("POLARIS_PYTHON", sys.executable)
    out = subprocess.run([py, "-m", "polaris_solver", "--tool-spec"], cwd=TOOLS_DIR, check=True,
                         capture_output=True, text=True)
    return json.loads(out.stdout)


def make_client():  # pragma: no cover - needs Vertex AI credentials
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")
    from google import genai  # type: ignore

    return genai.Client(vertexai=True, project=os.environ["GOOGLE_CLOUD_PROJECT"],
                        location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"))


def ask(question: str, model: str | None = None) -> dict:  # pragma: no cover - not called tonight
    """Sketch of one turn: model proposes solver calls, we run them, model answers, we gate the answer."""
    raise NotImplementedError(
        "Skeleton only. Wire: make_client(); tools=load_tool_spec() -> genai types.Tool(function_declarations=...); "
        "run each function_call through polaris_solver.solve(); pass results back; then "
        "ok, bad = grounding_check(reply, results); block the reply if not ok; prefix LABEL."
    )


if __name__ == "__main__":
    print("planner skeleton: see README.md. Not calling any API.")
