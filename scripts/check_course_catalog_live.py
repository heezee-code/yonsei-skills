#!/usr/bin/env python3
"""Run one read-only live course-handbook check without launching a browser."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MCP_SERVER = (
    ROOT
    / "plugins"
    / "yonsei-student-companion"
    / "runtime"
    / "yonsei_bridge"
    / "mcp_server.py"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", default="2026")
    parser.add_argument("--semester", default="2nd semester")
    parser.add_argument("--college", default="Engineering")
    parser.add_argument("--server", type=Path, default=MCP_SERVER)
    args = parser.parse_args()

    started = time.monotonic()
    try:
        requests = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-06-18"},
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "yonsei_student",
                    "arguments": {
                        "intent": "courses",
                        "action": "search",
                        "request": {
                            "year": args.year,
                            "semester": args.semester,
                            "college": args.college,
                        },
                    },
                },
            },
        ]
        with tempfile.TemporaryDirectory(prefix="yonsei-live-course-") as temporary:
            completed = subprocess.run(
                [sys.executable, "-B", str(args.server.resolve())],
                input="".join(
                    json.dumps(request, ensure_ascii=False) + "\n"
                    for request in requests
                ),
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
                timeout=45,
                env={
                    **os.environ,
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "YONSEI_BRIDGE_HOME": temporary,
                    # Any attempted browser use fails immediately. A successful
                    # result therefore proves this path stayed terminal-only.
                    "YONSEI_CDP_URL": "http://127.0.0.1:9",
                },
            )
        if completed.returncode:
            raise AssertionError(completed.stderr.strip() or "MCP server failed")
        responses = [
            json.loads(line)
            for line in completed.stdout.splitlines()
            if line.strip()
        ]
        initialized = next(response for response in responses if response.get("id") == 1)
        called = next(response for response in responses if response.get("id") == 2)
        if initialized["result"]["serverInfo"]["version"] != "0.7.0":
            raise AssertionError("the packaged MCP server version is stale")
        tool_result = called["result"]
        if tool_result.get("isError"):
            raise AssertionError(tool_result.get("content", [{}])[0].get("text", "tool failed"))
        result = tool_result["structuredContent"]
        primary = result["primary_result"]
        catalog = result["details"]["catalog"]
        rows = primary["courses"]
        if result["status"] != "ready" or not rows:
            raise AssertionError("the official handbook returned no ready course rows")
        if catalog.get("transport") != "direct_https_json":
            raise AssertionError("the course query did not use direct HTTPS JSON")
        if catalog.get("browser_used") is not False:
            raise AssertionError("the course query reported browser use")
        if catalog.get("login_required") is not False:
            raise AssertionError("the public course query requested login")
        if catalog.get("unmatched_filters"):
            raise AssertionError("one or more requested filters were not applied")
        if not all(catalog.get("requested_filters_applied", {}).values()):
            raise AssertionError("one or more requested filters were not verified")
        first_fields = rows[0].get("fields", {})
        if not first_fields.get("학정번호") or not first_fields.get("교과목명"):
            raise AssertionError("the official row mapping is incomplete")
        summary = {
            "ok": True,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "mcp_server_version": initialized["result"]["serverInfo"]["version"],
            "status": result["status"],
            "transport": catalog["transport"],
            "browser_used": catalog["browser_used"],
            "login_required": catalog["login_required"],
            "filters": catalog["filters"],
            "returned_result_count": len(rows),
            "official_result_count": primary["official_result_count"],
            "official_result_limited": primary["result_limited"],
            "first_course": {
                "course_code": first_fields["학정번호"],
                "section": first_fields.get("분반"),
                "title": first_fields["교과목명"],
                "instructor": first_fields.get("교수"),
                "time": first_fields.get("강의시간"),
            },
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except Exception as error:
        print(
            json.dumps(
                {
                    "ok": False,
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                    "error": str(error),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
