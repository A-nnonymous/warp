from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

from .constants import (
    CONFIG_TEMPLATE_PATH,
    CONTROL_PLANE_ALLOW_NESTED_ENV,
    CONTROL_PLANE_RECURSION_POLICY_ENV,
    CONTROL_PLANE_WORKER_AGENT_ENV,
    CONTROL_PLANE_WORKER_CONTEXT_ENV,
    DEFAULT_DASHBOARD_HOST,
    DEFAULT_DASHBOARD_PORT,
    REPO_ROOT,
    RUNTIME_DIR,
    SESSION_STATE,
)
from .network import (
    control_plane_base_url,
    load_preferred_session_state,
    pid_is_running,
    post_control_plane,
    tcp_port_in_use,
    terminate_pid,
    terminate_process_tree,
    wait_for_port_listen,
    wait_for_port_release,
    wait_for_process_exit,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="warp control plane runtime")
    parser.add_argument(
        "command",
        choices=["up", "serve", "silent", "stop-agents", "stop-listener", "stop-all"],
        help="launch the control plane, or stop agents/listener from a running session",
    )
    parser.add_argument("--config", type=Path, default=RUNTIME_DIR / "local_config.yaml", help="runtime config path")
    parser.add_argument("--host", default=None, help="override dashboard host")
    parser.add_argument("--port", type=int, default=None, help="override dashboard port")
    parser.add_argument("--open-browser", action="store_true", help="open the dashboard in a browser")
    parser.add_argument("--detach", action="store_true", help="start the control plane in the background and return")
    parser.add_argument(
        "--foreground", action="store_true", help="keep the control plane attached to the current shell"
    )
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="force template-backed cold-start bootstrap even before local_config.yaml exists",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=RUNTIME_DIR / "control_plane.log",
        help="log file used when --detach is enabled",
    )
    return parser.parse_args()


def apply_runtime_defaults(args: argparse.Namespace, cold_start: bool) -> None:
    if args.command in {"serve", "up"}:
        if args.host is None:
            args.host = DEFAULT_DASHBOARD_HOST
        if args.port is None:
            args.port = DEFAULT_DASHBOARD_PORT
    if args.command == "serve" and not args.foreground:
        args.detach = True
    elif args.command == "serve" and cold_start:
        if not args.foreground:
            args.detach = True


def resolve_runtime_config(args: argparse.Namespace) -> tuple[Path, Path, bool, str]:
    requested_path = args.config
    persist_path = requested_path
    bootstrap_requested = bool(args.bootstrap)
    reasons: list[str] = []
    default_local_config = (RUNTIME_DIR / "local_config.yaml").resolve()

    if not requested_path.exists():
        if requested_path.resolve() == default_local_config or bootstrap_requested:
            if not CONFIG_TEMPLATE_PATH.exists():
                raise FileNotFoundError(f"missing template config: {CONFIG_TEMPLATE_PATH}")
            requested_path = CONFIG_TEMPLATE_PATH
            reasons.append(f"cold-start bootstrapped from template because {persist_path} does not exist")
        else:
            raise FileNotFoundError(f"missing config: {persist_path}")

    if requested_path.resolve() == CONFIG_TEMPLATE_PATH.resolve():
        if persist_path == requested_path:
            persist_path = RUNTIME_DIR / "local_config.yaml"
        reasons.append(
            "template-backed control plane will accept settings edits immediately and launch when blockers are cleared"
        )

    return (
        requested_path,
        persist_path,
        requested_path.resolve() == CONFIG_TEMPLATE_PATH.resolve(),
        "; ".join(dict.fromkeys(reasons)),
    )


def stop_agents_command(args: argparse.Namespace) -> int:
    session_state = load_preferred_session_state(args.port or DEFAULT_DASHBOARD_PORT)
    if not session_state:
        print(f"no active session state found at {SESSION_STATE}", file=sys.stderr)
        return 1
    worker_pids = {
        agent: int(worker.get("pid") or 0)
        for agent, worker in session_state.get("workers", {}).items()
        if int(worker.get("pid") or 0)
    }
    try:
        result = post_control_plane(control_plane_base_url(args, session_state), "/api/stop", {})
        print(json.dumps(result, indent=2))
        return 0
    except RuntimeError:
        stopped_workers: list[str] = []
        for agent, pid in worker_pids.items():
            if pid and pid_is_running(pid):
                terminate_process_tree(pid, signal.SIGTERM)
                if not wait_for_process_exit(pid, timeout=3):
                    terminate_process_tree(pid, signal.SIGKILL)
                    wait_for_process_exit(pid, timeout=2)
            if not pid or not pid_is_running(pid):
                stopped_workers.append(agent)
        print(json.dumps({"ok": True, "stopped": sorted(stopped_workers)}, indent=2))
        return 0


def stop_listener_command(args: argparse.Namespace) -> int:
    session_state = load_preferred_session_state(args.port or DEFAULT_DASHBOARD_PORT)
    if not session_state:
        print(f"no active session state found at {SESSION_STATE}", file=sys.stderr)
        return 1
    server_pid = int(session_state.get("server", {}).get("pid") or 0)
    listener_port = int(session_state.get("server", {}).get("port") or DEFAULT_DASHBOARD_PORT)
    if not session_state.get("server", {}).get("listener_active", True):
        print(
            json.dumps(
                {
                    "ok": True,
                    "listener_port": listener_port,
                    "listener_released": True,
                    "stop_agents": False,
                },
                indent=2,
            )
        )
        return 0
    try:
        result = post_control_plane(control_plane_base_url(args, session_state), "/api/silent", {})
        listener_released = wait_for_port_release(listener_port)
        result["listener_port"] = listener_port
        result["listener_released"] = listener_released
        print(json.dumps(result, indent=2))
        return 0
    except RuntimeError:
        print("listener control plane is unreachable; cannot enter silent mode safely", file=sys.stderr)
        return 1


def stop_all_command(args: argparse.Namespace) -> int:
    session_state = load_preferred_session_state(args.port or DEFAULT_DASHBOARD_PORT)
    if not session_state:
        print(f"no active session state found at {SESSION_STATE}", file=sys.stderr)
        return 1
    server_pid = int(session_state.get("server", {}).get("pid") or 0)
    listener_port = int(session_state.get("server", {}).get("port") or DEFAULT_DASHBOARD_PORT)
    worker_pids = {
        agent: int(worker.get("pid") or 0)
        for agent, worker in session_state.get("workers", {}).items()
        if int(worker.get("pid") or 0)
    }
    try:
        result = post_control_plane(control_plane_base_url(args, session_state), "/api/stop-all", {})
        stopped_worker_names = []
        for agent, pid in worker_pids.items():
            if not pid:
                continue
            if wait_for_process_exit(pid, timeout=5):
                stopped_worker_names.append(agent)
            else:
                terminate_process_tree(pid, signal.SIGTERM)
                if wait_for_process_exit(pid, timeout=3):
                    stopped_worker_names.append(agent)
                else:
                    terminate_process_tree(pid, signal.SIGKILL)
                    if wait_for_process_exit(pid, timeout=2):
                        stopped_worker_names.append(agent)
        listener_released = wait_for_port_release(listener_port)
        if not listener_released and server_pid and pid_is_running(server_pid):
            terminate_pid(server_pid, signal.SIGTERM)
            listener_released = wait_for_port_release(listener_port)
        if not listener_released and server_pid and pid_is_running(server_pid):
            terminate_pid(server_pid, signal.SIGKILL)
            listener_released = wait_for_port_release(listener_port)
        result["listener_port"] = listener_port
        result["listener_released"] = listener_released
        result["stopped_workers"] = sorted(stopped_worker_names)
        result["warning"] = "listener port is still busy" if not listener_released else ""
        print(json.dumps(result, indent=2))
        return 0
    except RuntimeError:
        stopped_workers: list[str] = []
        for agent, pid in worker_pids.items():
            if pid and pid_is_running(pid):
                terminate_process_tree(pid, signal.SIGTERM)
                if not wait_for_process_exit(pid, timeout=3):
                    terminate_process_tree(pid, signal.SIGKILL)
                    wait_for_process_exit(pid, timeout=2)
            if not pid or not pid_is_running(pid):
                stopped_workers.append(agent)
        if server_pid and pid_is_running(server_pid):
            terminate_pid(server_pid, signal.SIGTERM)
            if not wait_for_port_release(listener_port):
                terminate_pid(server_pid, signal.SIGKILL)
        listener_released = wait_for_port_release(listener_port)
        print(
            json.dumps(
                {
                    "ok": listener_released,
                    "listener_pid": server_pid,
                    "listener_port": listener_port,
                    "listener_released": listener_released,
                    "stopped_workers": sorted(stopped_workers),
                    "stop_agents": True,
                },
                indent=2,
            )
        )
        return 0


def detach_process(args: argparse.Namespace) -> int:
    log_path = args.log_file
    log_path.parent.mkdir(parents=True, exist_ok=True)
    requested_port = int(args.port or DEFAULT_DASHBOARD_PORT)
    if tcp_port_in_use(requested_port):
        session_state = load_preferred_session_state(requested_port)
        server = session_state.get("server", {}) if isinstance(session_state, dict) else {}
        config_hint = str(server.get("config_path") or "").strip()
        pid_hint = int(server.get("pid") or 0)
        detail = f"port {requested_port} is already in use"
        if pid_hint:
            detail += f" by pid {pid_hint}"
        if config_hint:
            detail += f" using config {config_hint}"
        print(detail, file=sys.stderr)
        print(
            "stop the existing listener or choose a different --port before starting a new detached session",
            file=sys.stderr,
        )
        return 1
    script_path = str(Path(__file__).resolve().parents[1] / "control_plane.py")
    yaml_importable = False
    try:
        import yaml as _yaml_check  # noqa: F401
        yaml_importable = True
    except ImportError:
        pass
    if yaml_importable:
        command = [sys.executable, script_path, args.command]
    elif shutil.which("uv"):
        command = ["uv", "run", "--no-project", "--with", "PyYAML>=6.0.2", "python", script_path, args.command]
    else:
        command = [sys.executable, script_path, args.command]
    command.extend(["--config", str(args.config)])
    if args.host is not None:
        command.extend(["--host", args.host])
    if args.port is not None:
        command.extend(["--port", str(args.port)])
    if args.open_browser:
        command.append("--open-browser")
    if args.bootstrap:
        command.append("--bootstrap")

    env = os.environ.copy()
    env["CONTROL_PLANE_DETACHED"] = "1"
    with log_path.open("a", encoding="utf-8") as handle:
        process = subprocess.Popen(
            command,
            cwd=REPO_ROOT,
            stdin=subprocess.DEVNULL,
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=env,
        )
    if wait_for_port_listen(requested_port, timeout=5):
        print(f"control plane started in background: pid={process.pid} log={log_path}")
        return 0
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
    tail = ""
    try:
        tail = "\n".join(log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-10:])
    except OSError:
        tail = ""
    print(f"control plane failed to start on port {requested_port}; see log {log_path}", file=sys.stderr)
    if tail:
        print(tail, file=sys.stderr)
    return 1


def main() -> int:
    args = parse_args()
    if (
        args.command in {"up", "serve"}
        and os.environ.get(CONTROL_PLANE_WORKER_CONTEXT_ENV) == "1"
        and os.environ.get(CONTROL_PLANE_ALLOW_NESTED_ENV) != "1"
    ):
        agent = os.environ.get(CONTROL_PLANE_WORKER_AGENT_ENV, "worker")
        policy = os.environ.get(CONTROL_PLANE_RECURSION_POLICY_ENV, "forbid-nested-control-plane")
        print(
            f"refusing to start nested control plane from worker context {agent} ({policy}); unset {CONTROL_PLANE_WORKER_CONTEXT_ENV} or set {CONTROL_PLANE_ALLOW_NESTED_ENV}=1 only for explicit debugging",
            file=sys.stderr,
        )
        return 2
    if args.command == "silent":
        return stop_listener_command(args)
    if args.command == "stop-agents":
        return stop_agents_command(args)
    if args.command == "stop-listener":
        return stop_listener_command(args)
    if args.command == "stop-all":
        return stop_all_command(args)

    try:
        config_path, persist_config_path, cold_start, bootstrap_reason = resolve_runtime_config(args)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        print(
            f"create {RUNTIME_DIR / 'local_config.yaml'} or point --config at {CONFIG_TEMPLATE_PATH} to bootstrap from the template",
            file=sys.stderr,
        )
        return 2

    apply_runtime_defaults(args, cold_start)

    if args.detach and os.environ.get("CONTROL_PLANE_DETACHED") != "1":
        args.config = config_path
        args.bootstrap = cold_start
        return detach_process(args)

    # Lazy import to avoid circular imports when only CLI helpers are needed.
    from . import ControlPlaneService

    service = ControlPlaneService(
        config_path,
        host_override=args.host,
        port_override=args.port,
        persist_config_path=persist_config_path,
        bootstrap_requested=args.bootstrap,
    )
    if service.bootstrap_mode and bootstrap_reason:
        service.bootstrap_reason = bootstrap_reason
        service.last_event = f"cold_start:{bootstrap_reason}"

    def handle_signal(signum: int, frame: Any) -> None:  # pragma: no cover - signal path
        del signum, frame
        service.shutdown()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        if args.command == "up":
            service.run_up(open_browser=args.open_browser)
        else:
            service.run_serve(open_browser=args.open_browser)
    except OSError as exc:
        print(f"control plane startup failed: {exc}", file=sys.stderr)
        return 1
    return 0
