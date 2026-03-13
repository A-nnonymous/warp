from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, TextIO
from urllib.parse import unquote, urlparse

from .constants import DEFAULT_DASHBOARD_HOST, DEFAULT_DASHBOARD_PORT, RUNTIME_DIR, SESSION_STATE
from .utils import terminate_process_tree


def strip_command_args(command: list[str], flags: set[str]) -> list[str]:
    cleaned: list[str] = []
    skip_next = False
    for part in command:
        if skip_next:
            skip_next = False
            continue
        if part in flags:
            skip_next = True
            continue
        cleaned.append(part)
    return cleaned


@dataclass
class WorkerProcess:
    agent: str
    resource_pool: str
    provider: str
    model: str
    command: list[str]
    wrapper_path: str
    recursion_guard: str
    worktree_path: Path
    log_path: Path
    log_handle: TextIO
    process: subprocess.Popen[str]
    started_at: float


@dataclass(frozen=True)
class LaunchPolicy:
    strategy: str
    provider: str | None = None
    model: str | None = None


class DualStackThreadingHTTPServer(ThreadingHTTPServer):
    address_family = socket.AF_INET6

    def server_bind(self) -> None:
        if hasattr(socket, "IPPROTO_IPV6") and hasattr(socket, "IPV6_V6ONLY"):
            try:
                self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            except OSError:
                pass
        super().server_bind()


class IPv6OnlyThreadingHTTPServer(ThreadingHTTPServer):
    address_family = socket.AF_INET6

    def server_bind(self) -> None:
        if hasattr(socket, "IPPROTO_IPV6") and hasattr(socket, "IPV6_V6ONLY"):
            try:
                self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
            except OSError:
                pass
        super().server_bind()


def bind_server(
    server_cls: type[ThreadingHTTPServer], address: Any, handler: type[BaseHTTPRequestHandler]
) -> ThreadingHTTPServer:
    server = server_cls(address, handler, bind_and_activate=False)
    server.server_bind()
    server.server_activate()
    return server


def create_http_servers(host: str, port: int, handler: type[BaseHTTPRequestHandler]) -> list[ThreadingHTTPServer]:
    attempts: list[str] = []
    servers: list[ThreadingHTTPServer] = []

    if host == "0.0.0.0":
        try:
            servers.append(bind_server(ThreadingHTTPServer, (host, port), handler))
        except OSError as exc:
            attempts.append(f"{host}:{port} ({exc})")
        try:
            servers.append(bind_server(IPv6OnlyThreadingHTTPServer, ("::", port, 0, 0), handler))
        except OSError as exc:
            attempts.append(f"[::]:{port} ({exc})")
        if servers:
            return servers
        detail = "; ".join(attempts) if attempts else "no compatible address families"
        raise OSError(f"failed to bind control plane on {host}:{port}: {detail}")

    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM, flags=socket.AI_PASSIVE)
    except socket.gaierror as exc:
        raise OSError(f"failed to resolve control plane host {host}:{port}: {exc}") from exc

    for family, _, _, _, sockaddr in infos:
        try:
            if family == socket.AF_INET6:
                return [bind_server(IPv6OnlyThreadingHTTPServer, sockaddr, handler)]
            if family == socket.AF_INET:
                return [bind_server(ThreadingHTTPServer, sockaddr, handler)]
        except OSError as exc:
            attempts.append(f"{sockaddr} ({exc})")

    detail = "; ".join(attempts) if attempts else "no compatible address families"
    raise OSError(f"failed to bind control plane on {host}:{port}: {detail}")


def browser_open_host(host: str) -> str:
    if host in {"0.0.0.0", "::"}:
        return "127.0.0.1"
    return host


def format_endpoint(host: str, port: int) -> str:
    if ":" in host and not host.startswith("["):
        return f"[{host}]:{port}"
    return f"{host}:{port}"


def load_session_state_file() -> dict[str, Any]:
    if not SESSION_STATE.exists():
        return {}
    return json.loads(SESSION_STATE.read_text(encoding="utf-8"))


def session_state_path_for_port(port: int) -> Path:
    return RUNTIME_DIR / f"session_state_{port}.json"


def load_preferred_session_state(preferred_port: int | None = None) -> dict[str, Any]:
    if preferred_port is not None:
        port_path = session_state_path_for_port(preferred_port)
        if port_path.exists():
            return json.loads(port_path.read_text(encoding="utf-8"))
    return load_session_state_file()


def pid_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def terminate_pid(pid: int, sig: int = signal.SIGTERM) -> None:
    os.kill(pid, sig)


def wait_for_process_exit(pid: int, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not pid_is_running(pid):
            return True
        time.sleep(0.1)
    return not pid_is_running(pid)


def tcp_port_in_use(port: int, hosts: tuple[str, ...] = ("127.0.0.1", "::1")) -> bool:
    for host in hosts:
        family = socket.AF_INET6 if ":" in host else socket.AF_INET
        try:
            with socket.socket(family, socket.SOCK_STREAM) as probe:
                probe.settimeout(0.2)
                if probe.connect_ex((host, port)) == 0:
                    return True
        except OSError:
            continue
    return False


def wait_for_port_release(port: int, timeout: float = 5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not tcp_port_in_use(port):
            return True
        time.sleep(0.1)
    return not tcp_port_in_use(port)


def wait_for_port_listen(port: int, timeout: float = 5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if tcp_port_in_use(port):
            return True
        time.sleep(0.1)
    return tcp_port_in_use(port)


def safe_relative_web_path(request_path: str) -> Path | None:
    parsed = urlparse(request_path)
    raw_path = unquote(parsed.path)
    if raw_path in {"", "/"}:
        return Path("index.html")
    relative = Path(raw_path.lstrip("/"))
    if any(part in {"..", ""} for part in relative.parts):
        return None
    return relative


def control_plane_base_url(args: argparse.Namespace, session_state: dict[str, Any]) -> str:
    server = session_state.get("server", {})
    host = args.host or server.get("host") or DEFAULT_DASHBOARD_HOST
    port = args.port or int(server.get("port") or DEFAULT_DASHBOARD_PORT)
    return f"http://{browser_open_host(str(host))}:{port}"


def post_control_plane(url: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{url}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            raise RuntimeError(body or str(exc)) from exc
        raise RuntimeError(data.get("error") or "\n".join(data.get("errors", [])) or str(exc)) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(str(exc.reason)) from exc
