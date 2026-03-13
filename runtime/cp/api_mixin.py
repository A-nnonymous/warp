from __future__ import annotations

import json
import mimetypes
import sys
import threading
import time
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - import guard
    raise SystemExit("PyYAML is required. Run `uv sync` or install PyYAML>=6.0.2.") from exc

from .constants import (
    CONFIG_SECTIONS,
    DEFAULT_DASHBOARD_HOST,
    DEFAULT_DASHBOARD_PORT,
    STATE_DIR,
    WEB_STATIC_DIR,
)
from .network import (
    browser_open_host,
    create_http_servers,
    format_endpoint,
    safe_relative_web_path,
    wait_for_port_release,
)
from .utils import dedupe_strings, load_yaml, now_iso, slugify, summarize_list


class ApiMixin:
    """Methods for the HTTP API layer, dashboard serving, lifecycle control, and shutdown."""

    def handle_api_get(self, handler: BaseHTTPRequestHandler) -> bool:
        if handler.path == "/api/state":
            payload = json.dumps(self.build_dashboard_state(), default=str).encode("utf-8")
            handler.send_response(HTTPStatus.OK)
            handler.send_header("Content-Type", "application/json; charset=utf-8")
            handler.send_header("Content-Length", str(len(payload)))
            handler.end_headers()
            try:
                handler.wfile.write(payload)
            except BrokenPipeError:
                return True
            return True
        if handler.path == "/api/config":
            payload = json.dumps(
                {"config": self.config, "config_text": self.config_path.read_text(encoding="utf-8")}, default=str
            ).encode("utf-8")
            handler.send_response(HTTPStatus.OK)
            handler.send_header("Content-Type", "application/json; charset=utf-8")
            handler.send_header("Content-Length", str(len(payload)))
            handler.end_headers()
            try:
                handler.wfile.write(payload)
            except BrokenPipeError:
                return True
            return True
        if handler.path == "/api/peek":
            peek_data = self.peek_read_all()
            payload = json.dumps({"ok": True, "peek": peek_data}, default=str).encode("utf-8")
            handler.send_response(HTTPStatus.OK)
            handler.send_header("Content-Type", "application/json; charset=utf-8")
            handler.send_header("Content-Length", str(len(payload)))
            handler.end_headers()
            try:
                handler.wfile.write(payload)
            except BrokenPipeError:
                return True
            return True
        return False

    def handle_api_post(self, handler: BaseHTTPRequestHandler) -> bool:
        try:
            payload = self.parse_request_json(handler)
        except json.JSONDecodeError as exc:
            self.write_json(handler, {"ok": False, "error": f"invalid json: {exc}"}, status=400)
            return True

        if handler.path == "/api/peek":
            agent = str(payload.get("agent", "")).strip()
            lines = payload.get("lines", [])
            if not agent:
                self.write_json(handler, {"ok": False, "error": "agent is required"}, status=400)
                return True
            if not isinstance(lines, list) or not lines:
                self.write_json(handler, {"ok": False, "error": "lines list is required"}, status=400)
                return True
            self.peek_append(agent, [str(line) for line in lines])
            self.write_json(handler, {"ok": True, "agent": agent, "buffered": len(lines)})
            return True

        if handler.path == "/api/config":
            raw_config = payload.get("config")
            try:
                if isinstance(raw_config, dict):
                    validation = self.validate_config_payload(raw_config)
                    if validation["validation_issues"]:
                        self.write_json(handler, validation, status=400)
                        return True
                    errors = self.save_config_data(raw_config)
                else:
                    raw_text = payload.get("config_text")
                    if not isinstance(raw_text, str):
                        self.write_json(
                            handler, {"ok": False, "error": "config or config_text is required"}, status=400
                        )
                        return True
                    parsed = yaml.safe_load(raw_text) or {}
                    if not isinstance(parsed, dict):
                        self.write_json(
                            handler, {"ok": False, "error": "top-level config must be a YAML mapping"}, status=400
                        )
                        return True
                    validation = self.validate_config_payload(parsed)
                    if validation["validation_issues"]:
                        self.write_json(handler, validation, status=400)
                        return True
                    errors = self.save_config_data(parsed)
            except Exception as exc:
                self.write_json(handler, {"ok": False, "error": str(exc)}, status=400)
                return True
            self.write_json(
                handler,
                {
                    "ok": True,
                    "validation_issues": [],
                    "validation_errors": errors,
                    "launch_blockers": self.launch_blockers(),
                    "cold_start": self.bootstrap_mode,
                },
            )
            return True

        if handler.path == "/api/config/validate":
            raw_config = payload.get("config")
            if not isinstance(raw_config, dict):
                self.write_json(handler, {"ok": False, "error": "config is required"}, status=400)
                return True
            self.write_json(handler, self.validate_config_payload(raw_config))
            return True

        if handler.path == "/api/config/validate-section":
            section = str(payload.get("section", "")).strip()
            value = payload.get("value")
            if section not in CONFIG_SECTIONS:
                self.write_json(handler, {"ok": False, "error": "valid section is required"}, status=400)
                return True
            self.write_json(handler, self.validate_config_section(section, value))
            return True

        if handler.path == "/api/config/section":
            section = str(payload.get("section", "")).strip()
            value = payload.get("value")
            if section not in CONFIG_SECTIONS:
                self.write_json(handler, {"ok": False, "error": "valid section is required"}, status=400)
                return True
            try:
                validation = self.validate_config_section(section, value)
                if validation["validation_issues"]:
                    self.write_json(handler, validation, status=400)
                    return True
                errors = self.save_config_section(section, value)
            except Exception as exc:
                self.write_json(handler, {"ok": False, "error": str(exc)}, status=400)
                return True
            self.write_json(
                handler,
                {
                    "ok": True,
                    "validation_issues": [],
                    "validation_errors": self.filter_section_issue_text(errors, section),
                    "launch_blockers": self.filter_section_issue_text(self.launch_blockers(), section),
                    "cold_start": self.bootstrap_mode,
                },
            )
            return True

        if handler.path == "/api/launch":
            restart = bool(payload.get("restart", False))
            try:
                launch_policy = self.parse_launch_policy(payload)
            except ValueError as exc:
                self.write_json(handler, {"ok": False, "error": str(exc)}, status=400)
                return True
            result = self.launch_all(restart=restart, policy=launch_policy)
            self.write_json(handler, result, status=200 if result.get("ok") else 400)
            return True

        if handler.path == "/api/a0/respond":
            request_id = str(payload.get("request_id", "")).strip()
            action = str(payload.get("action", "resume")).strip() or "resume"
            message = str(payload.get("message", "")).strip()
            if not request_id:
                self.write_json(handler, {"ok": False, "error": "request_id is required"}, status=400)
                return True
            if not message:
                self.write_json(handler, {"ok": False, "error": "message is required"}, status=400)
                return True
            console = self.record_a0_user_message(message, request_id=request_id, action=action)
            self.write_json(handler, {"ok": True, "a0_console": console})
            return True

        if handler.path == "/api/a0/message":
            message = str(payload.get("message", "")).strip()
            if not message:
                self.write_json(handler, {"ok": False, "error": "message is required"}, status=400)
                return True
            console = self.record_a0_user_message(message, action="note")
            self.write_json(handler, {"ok": True, "a0_console": console})
            return True

        if handler.path == "/api/tasks/action":
            task_id = str(payload.get("task_id", "")).strip()
            action = str(payload.get("action", "")).strip()
            agent = str(payload.get("agent", "A0")).strip() or "A0"
            note = str(payload.get("note", "")).strip()
            if not task_id:
                self.write_json(handler, {"ok": False, "error": "task_id is required"}, status=400)
                return True
            if not action:
                self.write_json(handler, {"ok": False, "error": "action is required"}, status=400)
                return True
            try:
                task = self.perform_task_action(task_id, action, agent=agent, note=note)
            except Exception as exc:
                self.write_json(handler, {"ok": False, "error": str(exc)}, status=400)
                return True
            self.write_json(
                handler,
                {
                    "ok": True,
                    "task": task,
                    "backlog": self.load_backlog_state(),
                    "a0_console": self.a0_request_catalog(self.merge_queue(), self.dashboard_heartbeats_state()),
                },
            )
            return True

        if handler.path == "/api/workflow/update":
            task_id = str(payload.get("task_id", "")).strip()
            agent = str(payload.get("agent", "A0")).strip() or "A0"
            note = str(payload.get("note", "")).strip()
            updates = payload.get("updates")
            if not task_id:
                self.write_json(handler, {"ok": False, "error": "task_id is required"}, status=400)
                return True
            if not isinstance(updates, dict) or not updates:
                self.write_json(handler, {"ok": False, "error": "updates are required"}, status=400)
                return True
            try:
                task = self.patch_workflow_item(task_id, updates, actor=agent, note=note)
            except Exception as exc:
                self.write_json(handler, {"ok": False, "error": str(exc)}, status=400)
                return True
            self.write_json(
                handler,
                {
                    "ok": True,
                    "task": task,
                    "backlog": self.load_backlog_state(),
                    "a0_console": self.a0_request_catalog(self.merge_queue(), self.dashboard_heartbeats_state()),
                    "cleanup": self.cleanup_status(),
                },
            )
            return True

        if handler.path == "/api/team-mail/send":
            sender = str(payload.get("from", "")).strip()
            recipient = str(payload.get("to", "")).strip()
            topic = str(payload.get("topic", "status_note")).strip() or "status_note"
            body = str(payload.get("body", "")).strip()
            scope = str(payload.get("scope", "direct")).strip() or "direct"
            related_task_ids = payload.get("related_task_ids") or []
            if not sender:
                self.write_json(handler, {"ok": False, "error": "from is required"}, status=400)
                return True
            if not recipient:
                self.write_json(handler, {"ok": False, "error": "to is required"}, status=400)
                return True
            if not body:
                self.write_json(handler, {"ok": False, "error": "body is required"}, status=400)
                return True
            message = self.append_team_mailbox_message(
                sender,
                recipient,
                topic,
                body,
                dedupe_strings(related_task_ids if isinstance(related_task_ids, list) else []),
                scope,
            )
            self.last_event = f"mail:send:{message['id']}"
            self.write_json(handler, {"ok": True, "message": message, "team_mailbox": self.team_mailbox_catalog()})
            return True

        if handler.path == "/api/team-mail/ack":
            message_id = str(payload.get("message_id", "")).strip()
            ack_state = str(payload.get("ack_state", "")).strip()
            resolution_note = str(payload.get("resolution_note", "")).strip()
            if not message_id:
                self.write_json(handler, {"ok": False, "error": "message_id is required"}, status=400)
                return True
            if not ack_state:
                self.write_json(handler, {"ok": False, "error": "ack_state is required"}, status=400)
                return True
            try:
                message = self.acknowledge_team_mailbox_message(message_id, ack_state, resolution_note)
            except Exception as exc:
                self.write_json(handler, {"ok": False, "error": str(exc)}, status=400)
                return True
            self.last_event = f"mail:ack:{message_id}:{ack_state}"
            self.write_json(handler, {"ok": True, "message": message, "team_mailbox": self.team_mailbox_catalog()})
            return True

        if handler.path == "/api/workers/stop":
            agent = str(payload.get("agent", "")).strip()
            note = str(payload.get("note", "")).strip()
            if not agent:
                self.write_json(handler, {"ok": False, "error": "agent is required"}, status=400)
                return True
            try:
                result = self.stop_worker(agent, note)
            except Exception as exc:
                self.write_json(handler, {"ok": False, "error": str(exc)}, status=400)
                return True
            self.write_json(handler, result)
            return True

        if handler.path == "/api/team-cleanup":
            note = str(payload.get("note", "")).strip()
            release_listener = bool(payload.get("release_listener", False))
            try:
                result = self.confirm_team_cleanup(note, release_listener=release_listener)
            except Exception as exc:
                self.write_json(handler, {"ok": False, "error": str(exc), "cleanup": self.cleanup_status()}, status=400)
                return True
            self.write_json(handler, {"ok": True, **result})
            if result.get("listener_release_requested"):
                threading.Thread(target=self.release_listener_after_cleanup, daemon=True).start()
            return True

        if handler.path == "/api/stop":
            result = self.stop_workers()
            self.write_json(handler, result)
            return True

        if handler.path == "/api/soft-stop":
            timeout = int(payload.get("timeout", 120))
            # Run in a thread since checkpoint sessions may take time
            self.write_json(handler, {"ok": True, "status": "soft_stop_started"})
            threading.Thread(target=self._run_soft_stop, args=(timeout,), daemon=True).start()
            return True

        if handler.path == "/api/stop-all":
            stopped_workers = sorted(self.processes.keys())
            listener_port = self.listen_port
            self.write_json(
                handler,
                {
                    "ok": True,
                    "stop_agents": True,
                    "stopped_workers": stopped_workers,
                    "listener_port": listener_port,
                    "listener_released": False,
                },
            )
            threading.Thread(target=self.shutdown, kwargs={"stop_agents": True}, daemon=True).start()
            return True

        if handler.path == "/api/silent":
            self.write_json(
                handler,
                {
                    "ok": True,
                    "listener_port": self.listen_port,
                    "listener_active": False,
                    "stop_agents": False,
                },
            )
            threading.Thread(target=self.enter_silent_mode, daemon=True).start()
            return True

        if handler.path == "/api/shutdown":
            stop_agents = bool(payload.get("stop_agents", True))
            result = {"ok": True, "stop_agents": stop_agents}
            self.write_json(handler, result)
            threading.Thread(target=self.shutdown, kwargs={"stop_agents": stop_agents}, daemon=True).start()
            return True

        return False

    def parse_request_json(self, handler: BaseHTTPRequestHandler) -> dict[str, Any]:
        length = int(handler.headers.get("Content-Length", "0"))
        raw = handler.rfile.read(length) if length else b"{}"
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def write_json(self, handler: BaseHTTPRequestHandler, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        try:
            handler.wfile.write(body)
        except BrokenPipeError:
            return

    def serve_static_asset(self, request_path: str) -> tuple[bytes, str] | None:
        relative_path = safe_relative_web_path(request_path)
        if relative_path is None:
            return None
        asset_path = (WEB_STATIC_DIR / relative_path).resolve()
        web_root = WEB_STATIC_DIR.resolve()
        try:
            asset_path.relative_to(web_root)
        except ValueError:
            return None
        if asset_path.is_dir():
            asset_path = asset_path / "index.html"
        if not asset_path.exists() or not asset_path.is_file():
            return None
        content_type, _ = mimetypes.guess_type(asset_path.name)
        return asset_path.read_bytes(), content_type or "application/octet-stream"

    def start_dashboard(self, open_browser: bool = False) -> None:
        host = self.host_override or self.project.get("dashboard", {}).get("host", "127.0.0.1")
        port = self.port_override or int(self.project.get("dashboard", {}).get("port", 8233))
        service = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                if service.handle_api_get(self):
                    return
                if self.path.startswith("/api/"):
                    service.write_json(
                        self,
                        {"ok": False, "error": f"unknown api route: {self.path}"},
                        status=404,
                    )
                    return
                asset = service.serve_static_asset(self.path)
                if asset is None:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                body, content_type = asset
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", f"{content_type}; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                try:
                    self.wfile.write(body)
                except BrokenPipeError:
                    return

            def do_POST(self) -> None:  # noqa: N802
                if service.handle_api_post(self):
                    return
                if self.path.startswith("/api/"):
                    service.write_json(
                        self,
                        {"ok": False, "error": f"unknown api route: {self.path}"},
                        status=404,
                    )
                    return
                self.send_error(HTTPStatus.NOT_FOUND)

            def log_message(self, format: str, *args: object) -> None:  # noqa: A003
                return

        self.http_servers = create_http_servers(host, port, Handler)
        self.server_threads = []
        for server in self.http_servers:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.server_threads.append(thread)

        listen_endpoints = []
        for server in self.http_servers:
            listen_host, listen_port = server.server_address[:2]
            endpoint = format_endpoint(listen_host, listen_port)
            listen_endpoints.append(endpoint)
            print(f"control plane listening on {endpoint}", file=sys.stderr, flush=True)
        self.listen_host = host
        self.listen_port = listen_port
        self.listen_endpoints = listen_endpoints
        self.listener_active = True
        self.last_event = f"dashboard:{', '.join(listen_endpoints)}"
        self.write_session_state()
        if host in {"0.0.0.0", "::"}:
            print(
                f"remote access URL: http://<server-hostname-or-ip>:{listen_port}",
                file=sys.stderr,
                flush=True,
            )
        if open_browser:
            webbrowser.open(f"http://{browser_open_host(host)}:{listen_port}")

    def wait_forever(self) -> None:
        while not self.stop_event.is_set():
            time.sleep(1)

    def start_monitoring(self) -> None:
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()

    def run_up(self, open_browser: bool = False) -> None:
        self.start_monitoring()
        self.start_dashboard(open_browser=open_browser)
        result = self.launch_all()
        if not result.get("ok"):
            launch_blockers = result.get("errors") or []
            if launch_blockers:
                self.last_event = f"cold_start: launch blocked by {len(launch_blockers)} issue(s)"
        self.wait_forever()

    def run_serve(self, open_browser: bool = False) -> None:
        self.start_monitoring()
        self.start_dashboard(open_browser=open_browser)
        self.wait_forever()

    def close_http_servers(self) -> bool:
        released = True
        for server in self.http_servers:
            server.shutdown()
            server.server_close()
        if self.listen_port:
            released = wait_for_port_release(self.listen_port)
        self.http_servers = []
        self.server_threads = []
        self.listen_endpoints = []
        self.listener_active = False
        return released

    def enter_silent_mode(self) -> None:
        with self.lock:
            if not self.listener_active:
                return
            released = self.close_http_servers()
            self.last_event = f"silent_mode:listener released={released}"
            self.write_session_state()

    def _run_soft_stop(self, timeout: int = 120) -> None:
        """Background thread target for soft stop."""
        try:
            self.soft_stop_all(timeout=timeout)
        except Exception:
            pass

    def shutdown(self, stop_agents: bool = True) -> None:
        self.stop_event.set()
        if stop_agents:
            self.stop_workers()
        listener_released = self.close_http_servers()
        self.last_event = (
            f"shutdown:all released={listener_released}"
            if stop_agents
            else f"shutdown:listener released={listener_released}"
        )
        self.write_session_state()
