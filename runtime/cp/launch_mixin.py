from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

from .constants import (
    LOG_DIR,
    PROMPT_DIR,
    REPO_ROOT,
)
from .network import LaunchPolicy, WorkerProcess, strip_command_args
from .utils import (
    dedupe_strings,
    format_command,
    now_iso,
    run_shell,
    slugify,
    summarize_list,
    terminate_process_tree,
)


class LaunchMixin:
    """Methods for rendering prompts, preparing worktrees, launching and stopping workers."""

    def render_prompt(self, worker: dict[str, Any], provider_name: str, model: str) -> Path:
        prompt_path = PROMPT_DIR / f"{worker['agent']}.md"
        task_id = worker.get("task_id", "unassigned")
        task_title = self.task_title(task_id)
        profile = self.task_profile_for_worker(worker)
        git_identity = self.worker_git_identity(worker)
        git_identity_text = (
            f"{git_identity['name']} <{git_identity['email']}>"
            if git_identity["name"] and git_identity["email"]
            else "environment default"
        )
        reference_workspace_root = self.reference_workspace_root() or "unassigned"
        reference_inputs = self.reference_inputs()
        prompt_context_files = dedupe_strings(
            [
                *self.prompt_context_files(),
                *profile.get("prompt_context_files", []),
                "governance/operating_model.md",
                "state/backlog.yaml",
                "state/gates.yaml",
                "state/agent_runtime.yaml",
            ]
        )
        reference_input_text = "\n".join(f"- {item}" for item in reference_inputs) or "- none configured"
        context_file_text = "\n".join(f"- {item}" for item in prompt_context_files)
        text = f"""# {worker['agent']} Worker Prompt

Repository name: {self.project.get('repository_name', 'target-repo')}
Local workspace root: {self.project.get('local_repo_root', str(REPO_ROOT))}
Reference workspace: {reference_workspace_root}
Agent: {worker['agent']}
Task: {task_id} - {task_title}
Task type: {profile.get('task_type', 'default')}
Provider: {provider_name}
Model: {model}
Worktree: {worker['worktree_path']}
Branch: {worker['branch']}
Commit identity: {git_identity_text}
Manager merge target: {self.integration_branch()}

Reference inputs:

{reference_input_text}

Mandatory rules:

1. Work only inside the assigned worktree.
2. Do not start nested control-plane sessions or launch additional agent CLI processes such as `control_plane.py up`, `control_plane.py serve`, `claude-code`, `ducc`, `copilot`, or `opencode` from inside this worker session.
3. Update your status file in `status/agents/` and your checkpoint in `checkpoints/agents/`.
4. Treat configured reference inputs as guidance, not as the final host implementation.
5. Report blockers before widening scope.
6. Do not edit shared control-plane files unless the manager explicitly asks and the lock is held.
7. Commit only on your assigned branch; A0 owns final merge or cherry-pick into `{self.integration_branch()}`.

First files to read:

{context_file_text}

Primary test command:

{worker.get('test_command', 'unassigned')}
"""
        prompt_path.write_text(text, encoding="utf-8")
        return prompt_path

    def provider_runtime(
        self,
        pool_name: str,
        worker: dict[str, Any],
        provider_override: str | None = None,
        model_override: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any], str, str]:
        pool = self.resource_pools[pool_name]
        provider_name = provider_override or worker.get("provider") or pool["provider"]
        provider = self.providers[provider_name]
        model = model_override or worker.get("model") or pool["model"]
        return provider, pool, provider_name, model

    def provider_prompt_transport(self, provider_name: str, provider: dict[str, Any]) -> str:
        configured = str(provider.get("prompt_transport") or "").strip().lower()
        if configured in {"stdin", "prompt-file"}:
            return configured
        if provider_name == "ducc":
            return "stdin"
        return "prompt-file"

    def sanitize_provider_command(self, provider_name: str, command: list[str], prompt_transport: str) -> list[str]:
        flags_to_strip: set[str] = set()
        if prompt_transport == "stdin":
            flags_to_strip.add("--prompt-file")
        if provider_name == "ducc":
            flags_to_strip.add("--cwd")
        if not flags_to_strip:
            return command
        return strip_command_args(command, flags_to_strip)

    def branch_exists(self, branch: str) -> bool:
        repo_root = self.target_repo_root()
        result = subprocess.run(
            ["git", "show-ref", "--verify", f"refs/heads/{branch}"],
            cwd=repo_root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0

    def ensure_worktree(self, worker: dict[str, Any]) -> None:
        repo_root = self.target_repo_root()
        worktree_path = Path(worker["worktree_path"])
        if worktree_path.exists():
            git_marker = worktree_path / ".git"
            if git_marker.exists():
                return
            if worktree_path.is_dir() and not any(worktree_path.iterdir()):
                pass
            else:
                raise RuntimeError(f"worktree path exists but is not an initialized git worktree: {worktree_path}")
        else:
            worktree_path.parent.mkdir(parents=True, exist_ok=True)
        branch = worker["branch"]
        base_branch = self.project.get("base_branch", "main")
        if self.branch_exists(branch):
            command = ["git", "worktree", "add", str(worktree_path), branch]
        else:
            command = ["git", "worktree", "add", str(worktree_path), "-b", branch, base_branch]
        subprocess.run(command, cwd=repo_root, check=True)

    def ensure_environment(self, worker: dict[str, Any]) -> None:
        sync_command = worker.get("sync_command")
        if not sync_command or sync_command == "none":
            return
        result = run_shell(sync_command, Path(worker["worktree_path"]))
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "sync failed")

    def configure_git_identity(self, worker: dict[str, Any]) -> None:
        identity = self.worker_git_identity(worker)
        worktree_path = Path(worker["worktree_path"])
        if identity["name"]:
            result = subprocess.run(
                ["git", "config", "user.name", identity["name"]],
                cwd=worktree_path,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "failed to set git user.name")
        if identity["email"]:
            result = subprocess.run(
                ["git", "config", "user.email", identity["email"]],
                cwd=worktree_path,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "failed to set git user.email")

    def launch_worker(self, worker: dict[str, Any], policy: LaunchPolicy | None = None) -> dict[str, Any]:
        resolved_policy = policy or self.default_launch_policy()
        pool_name, evaluation = self.resolve_pool_for_launch(worker, resolved_policy)
        provider, pool, provider_name, model = self.provider_runtime(
            pool_name,
            worker,
            provider_override=resolved_policy.provider,
            model_override=resolved_policy.model,
        )
        prompt_path = self.render_prompt(worker, provider_name, model)
        self.ensure_worktree(worker)
        self.configure_git_identity(worker)
        self.ensure_environment(worker)
        template = worker.get("command_template") or provider.get("command_template")
        if not template:
            raise RuntimeError(f"no command template configured for provider {provider_name}")

        if not evaluation["binary_found"]:
            raise RuntimeError(f"provider binary missing for pool {pool_name}: {evaluation['binary']}")
        if not evaluation["auth_ready"]:
            raise RuntimeError(str(evaluation.get("auth_detail") or f"provider auth unavailable for pool {pool_name}"))

        values = {
            "agent": worker["agent"],
            "model": model,
            "prompt_file": str(prompt_path),
            "worktree_path": worker["worktree_path"],
            "branch": worker["branch"],
            "repository_name": self.project.get("repository_name", "target-repo"),
            "reference_workspace_root": self.reference_workspace_root() or "unassigned",
        }
        command = format_command(template, values)
        prompt_transport = self.provider_prompt_transport(provider_name, provider)
        command = self.sanitize_provider_command(provider_name, command, prompt_transport)
        env = os.environ.copy()
        recursion_guard = self.provider_recursion_guard_mode(provider_name, provider)
        launch_wrapper = ""
        api_value = pool.get("api_key", "")
        api_env_name = provider.get("api_key_env_name")
        if (
            self.provider_auth_mode(provider) == "api_key"
            and api_env_name
            and api_value
            and api_value != "replace_me_or_use_api_key_env"
        ):
            env[api_env_name] = api_value
        extra_env = pool.get("extra_env", {})
        if isinstance(extra_env, dict):
            env.update({str(key): str(value) for key, value in extra_env.items()})
        env.update(self.guarded_worker_env(worker, provider_name, provider))
        if self.provider_uses_exec_wrapper(provider_name, provider):
            wrapper_path = self.ensure_provider_exec_wrapper(provider_name)
            launch_wrapper = str(wrapper_path)
            command = [launch_wrapper, *command]

        log_path = LOG_DIR / f"{worker['agent']}.log"
        log_handle = log_path.open("w", encoding="utf-8")
        prompt_handle = prompt_path.open("r", encoding="utf-8") if prompt_transport == "stdin" else None
        process = subprocess.Popen(
            command,
            cwd=worker["worktree_path"],
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            stdin=prompt_handle if prompt_handle is not None else subprocess.DEVNULL,
            text=True,
            env=env,
            start_new_session=True,
        )
        if prompt_handle is not None:
            prompt_handle.close()
        previous = self.processes.get(worker["agent"])
        if previous and previous.process.poll() is None:
            previous.process.terminate()
        self.provider_stats[pool_name]["launch_successes"] += 1
        self.provider_stats[pool_name]["last_failure"] = ""
        self.persist_provider_stats()
        self.processes[worker["agent"]] = WorkerProcess(
            agent=worker["agent"],
            resource_pool=pool_name,
            provider=provider_name,
            model=model,
            command=command,
            wrapper_path=launch_wrapper,
            recursion_guard=recursion_guard,
            worktree_path=Path(worker["worktree_path"]),
            log_path=log_path,
            log_handle=log_handle,
            process=process,
            started_at=time.time(),
        )
        self.update_runtime_entry(
            worker,
            pool_name,
            provider_name,
            model,
            "launching",
            recursion_guard=recursion_guard,
            launch_wrapper=launch_wrapper,
        )
        self.update_heartbeat(worker["agent"], "launching", "process_spawned", "waiting for first monitor check")
        return {
            "agent": worker["agent"],
            "resource_pool": pool_name,
            "provider": provider_name,
            "model": model,
            "pid": process.pid,
            "recursion_guard": recursion_guard,
            "launch_wrapper": launch_wrapper,
            "command": command,
            "launch_strategy": resolved_policy.strategy,
        }

    def launch_all(self, restart: bool = False, policy: LaunchPolicy | None = None) -> dict[str, Any]:
        with self.lock:
            errors = self.launch_blockers()
            if errors:
                return {
                    "ok": False,
                    "errors": errors,
                    "error": f"launch blocked by {len(errors)} issue(s): {summarize_list(errors)}",
                }
            resolved_policy = policy or self.default_launch_policy()
            if restart:
                self.stop_workers()
            launched: list[dict[str, Any]] = []
            failures: list[dict[str, str]] = []
            for worker in self.workers:
                if worker["agent"] in self.processes and self.processes[worker["agent"]].process.poll() is None:
                    continue
                try:
                    launched.append(self.launch_worker(worker, policy=resolved_policy))
                except Exception as exc:
                    try:
                        candidate_pools = [self.resolve_pool_for_launch(worker, resolved_policy)[0]]
                    except Exception:
                        candidate_pools = self.candidate_pools_for_worker(worker)
                    pool_name = candidate_pools[0] if candidate_pools else "unassigned"
                    if pool_name in self.provider_stats:
                        self.provider_stats[pool_name]["launch_failures"] += 1
                        self.provider_stats[pool_name]["last_failure"] = str(exc)
                        self.persist_provider_stats()
                    provider_name = resolved_policy.provider or worker.get("provider", "unassigned") or "unassigned"
                    model = resolved_policy.model or worker.get("model", "unassigned") or "unassigned"
                    provider_config = self.providers.get(provider_name, {}) if provider_name in self.providers else {}
                    launch_wrapper = (
                        str(self.provider_wrapper_path(provider_name))
                        if provider_name in self.providers
                        and self.provider_uses_exec_wrapper(provider_name, provider_config)
                        else ""
                    )
                    self.update_runtime_entry(
                        worker,
                        pool_name,
                        provider_name,
                        model,
                        f"launch_failed: {exc}",
                        recursion_guard=(
                            self.provider_recursion_guard_mode(provider_name, provider_config)
                            if provider_name in self.providers
                            else "env-only"
                        ),
                        launch_wrapper=launch_wrapper,
                    )
                    self.update_heartbeat(worker["agent"], "stale", "launch_failed", str(exc))
                    failures.append({"agent": worker["agent"], "error": str(exc)})
            self.last_event = f"launch:{resolved_policy.strategy}:{len(launched)} workers"
            self.write_session_state()
            error_summary = ""
            if failures:
                failure_messages = [f"{item['agent']}: {item['error']}" for item in failures]
                error_summary = f"launch failed for {len(failures)} worker(s): {summarize_list(failure_messages)}"
            return {
                "ok": len(failures) == 0,
                "launched": launched,
                "failures": failures,
                "error": error_summary,
                "launch_policy": {
                    "strategy": resolved_policy.strategy,
                    "provider": resolved_policy.provider,
                    "model": resolved_policy.model,
                },
            }

    def stop_workers(self) -> dict[str, Any]:
        with self.lock:
            stopped: list[str] = []
            for agent in list(self.processes.keys()):
                result = self.stop_worker_locked(agent)
                if result.get("stopped") or result.get("already_stopped"):
                    stopped.append(agent)
            self.last_event = f"stop:{len(stopped)} workers"
            self.write_session_state()
            return {"ok": True, "stopped": stopped, "cleanup": self.cleanup_status()}

    def stop_worker(self, agent: str, note: str = "") -> dict[str, Any]:
        with self.lock:
            result = self.stop_worker_locked(agent, note)
            self.last_event = f"stop:{agent}"
            self.write_session_state()
            result["cleanup"] = self.cleanup_status()
            return result

    def stop_worker_locked(self, agent: str, note: str = "") -> dict[str, Any]:
        worker_config = next((item for item in self.workers if str(item.get("agent") or "").strip() == agent), None)
        if worker_config is None:
            raise ValueError(f"unknown worker {agent}")
        if agent == "A0":
            raise ValueError("A0 cannot be shut down through the worker shutdown path")

        process_entry = self.processes.get(agent)
        runtime_entry = next(
            (
                item
                for item in self.dashboard_runtime_state().get("workers", [])
                if isinstance(item, dict) and str(item.get("agent") or "").strip() == agent
            ),
            {},
        )
        stopped = False
        already_stopped = True
        pool_name = str(runtime_entry.get("resource_pool") or worker_config.get("resource_pool") or "unassigned")
        provider_name = str(runtime_entry.get("provider") or worker_config.get("provider") or "unassigned")
        model = str(runtime_entry.get("model") or worker_config.get("model") or "unassigned")
        if process_entry is not None:
            already_stopped = process_entry.process.poll() is not None
            if process_entry.process.poll() is None:
                terminate_process_tree(process_entry.process.pid, signal.SIGTERM)
                try:
                    process_entry.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    terminate_process_tree(process_entry.process.pid, signal.SIGKILL)
                    process_entry.process.wait(timeout=5)
                stopped = True
            process_entry.log_handle.close()
            pool_name = process_entry.resource_pool
            provider_name = process_entry.provider
            model = process_entry.model
            del self.processes[agent]

        self.update_heartbeat(agent, "offline", "manager_stop", note or "none")
        self.update_runtime_entry(worker_config, pool_name, provider_name, model, "stopped")
        self.append_team_mailbox_message(
            "A0",
            agent,
            "status_note",
            note or "A0 requested a clean worker shutdown.",
            [str(worker_config.get("task_id") or "").strip()] if str(worker_config.get("task_id") or "").strip() else [],
            "direct",
        )
        return {"ok": True, "agent": agent, "stopped": stopped, "already_stopped": already_stopped and not stopped}
