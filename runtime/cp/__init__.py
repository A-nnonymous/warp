"""Control-plane sub-package — assembled ControlPlaneService and CLI entry point."""
from __future__ import annotations

import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .constants import LOG_DIR, PROMPT_DIR
from .network import WorkerProcess
from .config_mixin import ConfigMixin
from .backlog_mixin import BacklogMixin
from .mailbox_mixin import MailboxMixin
from .routing_mixin import RoutingMixin
from .provider_mixin import ProviderMixin
from .launch_mixin import LaunchMixin
from .state_mixin import StateMixin
from .dashboard_mixin import DashboardMixin
from .api_mixin import ApiMixin
from .cli import main


class ControlPlaneService(
    ConfigMixin,
    BacklogMixin,
    MailboxMixin,
    RoutingMixin,
    ProviderMixin,
    LaunchMixin,
    StateMixin,
    DashboardMixin,
    ApiMixin,
):
    """Assembled control-plane service combining all domain mixins.

    The ``__init__`` method is the only piece that lives here — every other
    method is inherited from the mixin classes above.
    """

    def __init__(
        self,
        config_path: Path,
        host_override: str | None = None,
        port_override: int | None = None,
        persist_config_path: Path | None = None,
        bootstrap_requested: bool = False,
    ):
        self.config_path = config_path
        self.persist_config_path = persist_config_path or config_path
        self.host_override = host_override
        self.port_override = port_override
        self.bootstrap_requested = bootstrap_requested
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.monitor_thread: threading.Thread | None = None
        self.server_threads: list[threading.Thread] = []
        self.http_servers: list[ThreadingHTTPServer] = []
        self.processes: dict[str, WorkerProcess] = {}
        self.last_event = "initialized"
        PROMPT_DIR.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.config: dict[str, Any] = {}
        self.project: dict[str, Any] = {}
        self.providers: dict[str, Any] = {}
        self.resource_pools: dict[str, Any] = {}
        self.workers: list[dict[str, Any]] = []
        self.provider_stats: dict[str, dict[str, Any]] = {}
        self.bootstrap_mode = False
        self.bootstrap_reason = ""
        self.listen_host = ""
        self.listen_port = 0
        self.listen_endpoints: list[str] = []
        self.listener_active = False
        self.reload_config()


__all__ = ["ControlPlaneService", "main"]
