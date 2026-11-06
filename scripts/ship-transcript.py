#!/usr/bin/env python3
"""Ship a Claude Code session transcript to EvaliQA.

Runs as the ``Stop`` and ``SessionEnd`` hooks of the ``evaliqa`` plugin.
Claude Code's OTel spans carry structure, timings, tokens and cost, but
not the agent's own answer and not the result of ``Agent``,
``AskUserQuestion`` or MCP calls. That text is on disk in the session
transcript; this posts it so the trace can be stored complete. The two
halves join on ids both sides already have (``session_id``,
``tool_use_id``, ``agent_id``), so there is nothing to correlate by hand.

Installed with the plugin, so nothing is copied into a repository. The
operator supplies their own credentials through the plugin's config
dialog (``/plugin configure evaliqa``). Claude Code keeps the API key in
the platform's secure credential storage and passes both values to this
hook as environment variables:

    CLAUDE_PLUGIN_OPTION_EVALIQA_API_KEY   (evx_...)
    CLAUDE_PLUGIN_OPTION_EVALIQA_URL       (https://your-evaliqa-host)

Without both, the hook does nothing and says nothing: the same repository
is worked in by people who have not connected it to EvaliQA.

Stdlib only, so it runs wherever Claude Code does. It never fails the
turn: any error goes to stderr and the exit code stays 0.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

TIMEOUT_SEC = 20
PATH = "/api/traces/claude-code/session"


def subagent_files(transcript_path: Path) -> dict[str, Path]:
    """``{agent_id: file}`` for the session's subagents.

    Claude Code writes them beside the transcript, in a directory named
    after the session, as ``agent-<agent_id>.jsonl``. That id is the one
    the spans carry as ``agent_id``, which is what lets a hand-back be
    attached to the right ``Agent`` call.
    """
    folder = transcript_path.with_suffix("") / "subagents"
    if not folder.is_dir():
        return {}
    found: dict[str, Path] = {}
    for file in folder.glob("agent-*.jsonl"):
        agent_id = file.stem[len("agent-") :]
        if agent_id:
            found[agent_id] = file
    return found


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"evaliqa: cannot read {path}: {exc}", file=sys.stderr)
        return ""


def build_payload(session_id: str, transcript_path: Path) -> dict:
    """The request body: the session file plus every subagent file."""
    return {
        "session_id": session_id,
        "transcript": _read(transcript_path),
        "subagents": {
            agent_id: _read(file) for agent_id, file in subagent_files(transcript_path).items()
        },
    }


def ship(payload: dict, base_url: str, api_key: str) -> str:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + PATH,
        data=body,
        headers={"content-type": "application/json", "x-api-key": api_key},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SEC) as response:
        return response.read().decode("utf-8", errors="replace")


def main() -> int:
    api_key = os.environ.get("CLAUDE_PLUGIN_OPTION_EVALIQA_API_KEY", "").strip()
    base_url = os.environ.get("CLAUDE_PLUGIN_OPTION_EVALIQA_URL", "").strip()
    if not api_key or not base_url:
        # Not configured is not an error: the same repository is worked in
        # by people who have not connected it to EvaliQA.
        return 0

    try:
        event = json.load(sys.stdin)
    except ValueError:
        print("evaliqa: hook payload was not JSON", file=sys.stderr)
        return 0

    session_id = str(event.get("session_id") or "").strip()
    raw_path = str(event.get("transcript_path") or "").strip()
    if not session_id or not raw_path:
        print("evaliqa: hook payload had no session_id or transcript_path", file=sys.stderr)
        return 0

    transcript_path = Path(raw_path)
    if not transcript_path.is_file():
        print(f"evaliqa: transcript missing at {transcript_path}", file=sys.stderr)
        return 0

    try:
        result = ship(build_payload(session_id, transcript_path), base_url, api_key)
        print(f"evaliqa: {result}", file=sys.stderr)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        # Losing a transcript costs some text in the feed. Failing the
        # hook would cost the operator their turn, which is worse.
        print(f"evaliqa: ship failed: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
