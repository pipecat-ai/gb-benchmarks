#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import mimetypes
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from replay_support import (
    DEFAULT_RUNS_DIR,
    build_replay_bundle_for_completed_run,
    build_replay_bundle_for_stream,
    list_available_runs,
    resolve_artifact_path,
)


class ReplayServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        request_handler_class: type[BaseHTTPRequestHandler],
        *,
        runs_dir: Path,
        ui_dist: Path | None,
    ) -> None:
        super().__init__(server_address, request_handler_class)
        self.runs_dir = runs_dir
        self.ui_dist = ui_dist


class ReplayRequestHandler(BaseHTTPRequestHandler):
    server: ReplayServer

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self._send_json({"ok": True})
            return
        if parsed.path == "/api/runs":
            self._handle_runs()
            return
        if parsed.path == "/api/replay":
            self._handle_replay(parsed.query)
            return
        if parsed.path == "/api/live":
            self._handle_live(parsed.query)
            return
        if self.server.ui_dist is not None:
            self._serve_ui_asset(parsed.path)
            return
        self._send_json(
            {
                "message": "Replay helper is running.",
                "endpoints": ["/api/health", "/api/runs", "/api/replay", "/api/live"],
            }
        )

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")

    def _send_json(self, payload: Any, *, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, status: int, message: str) -> None:
        self._send_json({"error": message}, status=status)

    def _query_value(self, query: str, key: str) -> str | None:
        values = parse_qs(query).get(key) or []
        if not values:
            return None
        text = str(values[0]).strip()
        return text or None

    def _handle_runs(self) -> None:
        self._send_json({"runs": list_available_runs(runs_dir=self.server.runs_dir)})

    def _handle_replay(self, query: str) -> None:
        run_path_text = self._query_value(query, "run_path")
        if run_path_text is None:
            self._send_error_json(HTTPStatus.BAD_REQUEST, "Missing run_path query parameter.")
            return
        judge_path_text = self._query_value(query, "judge_path")

        try:
            run_path = resolve_artifact_path(run_path_text, default_dir=self.server.runs_dir)
            judge_path = (
                resolve_artifact_path(judge_path_text, default_dir=run_path.parent)
                if judge_path_text is not None
                else None
            )
            bundle = build_replay_bundle_for_completed_run(run_path, judge_path=judge_path)
        except FileNotFoundError as exc:
            self._send_error_json(HTTPStatus.NOT_FOUND, str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            self._send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
            return

        self._send_json(bundle)

    def _handle_live(self, query: str) -> None:
        stream_path_text = self._query_value(query, "stream_path")
        if stream_path_text is None:
            self._send_error_json(HTTPStatus.BAD_REQUEST, "Missing stream_path query parameter.")
            return

        try:
            stream_path = resolve_artifact_path(stream_path_text, default_dir=self.server.runs_dir)
        except Exception as exc:  # noqa: BLE001
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))
            return

        if not stream_path.exists():
            self._send_error_json(HTTPStatus.NOT_FOUND, f"Stream file not found: {stream_path}")
            return

        self.send_response(HTTPStatus.OK)
        self._send_cors_headers()
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        last_payload = None
        heartbeat_deadline = time.monotonic() + 15.0
        try:
            while True:
                bundle = build_replay_bundle_for_stream(stream_path)
                serialized = json.dumps(bundle, ensure_ascii=False, separators=(",", ":"))
                if serialized != last_payload:
                    self._write_sse("replay", serialized)
                    last_payload = serialized
                    heartbeat_deadline = time.monotonic() + 15.0
                elif time.monotonic() >= heartbeat_deadline:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                    heartbeat_deadline = time.monotonic() + 15.0
                time.sleep(0.5)
        except (BrokenPipeError, ConnectionResetError):
            return

    def _write_sse(self, event_name: str, serialized_json: str) -> None:
        self.wfile.write(f"event: {event_name}\n".encode("utf-8"))
        for line in serialized_json.splitlines() or [""]:
            self.wfile.write(f"data: {line}\n".encode("utf-8"))
        self.wfile.write(b"\n")
        self.wfile.flush()

    def _serve_ui_asset(self, request_path: str) -> None:
        assert self.server.ui_dist is not None
        dist_root = self.server.ui_dist
        path = request_path.lstrip("/") or "index.html"
        candidate = (dist_root / path).resolve()
        if not str(candidate).startswith(str(dist_root.resolve())) or not candidate.exists():
            candidate = dist_root / "index.html"
        if not candidate.exists():
            self._send_error_json(HTTPStatus.NOT_FOUND, f"UI asset not found: {candidate}")
            return

        body = candidate.read_bytes()
        mime_type, _ = mimetypes.guess_type(candidate.name)
        self.send_response(HTTPStatus.OK)
        self._send_cors_headers()
        self.send_header("Content-Type", mime_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Replay helper server for port-to-port runs.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=8777, help="Bind port")
    parser.add_argument(
        "--runs-dir",
        default=str(DEFAULT_RUNS_DIR),
        help="Directory used for recent-run discovery and relative artifact resolution.",
    )
    parser.add_argument(
        "--serve-ui-dist",
        default=None,
        help="Optional built frontend directory to serve alongside the API.",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    runs_dir = resolve_artifact_path(args.runs_dir)
    ui_dist = resolve_artifact_path(args.serve_ui_dist) if args.serve_ui_dist else None
    server = ReplayServer(
        (args.host, args.port),
        ReplayRequestHandler,
        runs_dir=runs_dir,
        ui_dist=ui_dist,
    )
    print(f"Replay helper listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
