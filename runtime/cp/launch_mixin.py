from __future__ import annotations

import os
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
    format_command,
    now_iso,
    run_shell,
    slugify,
    summarize_list,
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
        prompt_context_files = self.scoped_context_files(worker, profile)
        inline_state_context = self.render_inline_state_context(worker, profile)
        reference_input_text = "\n".join(f"- {item}" for item in reference_inputs) or "- none configured"
        context_file_text = "\n".join(f"- {item}" for item in prompt_context_files) if prompt_context_files else "- none"
        text = f"""# {worker['agent']} Worker 提示词

仓库名称: {self.project.get('repository_name', 'target-repo')}
本地工作区根目录: {self.project.get('local_repo_root', str(REPO_ROOT))}
参考工作区: {reference_workspace_root}
Agent: {worker['agent']}
任务: {task_id} - {task_title}
任务类型: {profile.get('task_type', 'default')}
Provider: {provider_name}
模型: {model}
Worktree: {worker['worktree_path']}
分支: {worker['branch']}
提交身份: {git_identity_text}
管理者合并目标: {self.integration_branch()}

参考输入:

{reference_input_text}

强制规则:

1. 只在分配给你的 worktree 内工作。
2. 不得在当前 worker 会话中启动嵌套 control-plane 会话，也不得额外启动 `control_plane.py up`、`control_plane.py serve`、`claude-code`、`ducc`、`copilot`、`opencode` 等 agent CLI 进程。
3. 你在 `status/agents/` 中的状态汇报、在 `checkpoints/agents/` 中的检查点、以及任何面对管理者或人类的汇报，必须全部使用中文。
4. 配置的 reference inputs 只是参考，不是最终宿主实现。
5. 发现阻塞时，先用中文汇报阻塞，再决定是否扩展范围。
6. 除非管理者明确要求且已经持锁，否则不要编辑共享 control-plane 文件。
7. 只能在分配给你的分支上提交；最终合并或 cherry-pick 到 `{self.integration_branch()}` 由 A0 负责。

{inline_state_context}

优先阅读的文件:

{context_file_text}

主测试命令:

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
        env.pop("CLAUDECODE", None)
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
            skipped: list[str] = []
            failures: list[dict[str, str]] = []
            for worker in self.workers:
                agent = worker["agent"]
                if agent in self.processes and self.processes[agent].process.poll() is None:
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
                "skipped_blocked": skipped,
                "failures": failures,
                "error": error_summary,
                "launch_policy": {
                    "strategy": resolved_policy.strategy,
                    "provider": resolved_policy.provider,
                    "model": resolved_policy.model,
                },
            }

    def render_checkpoint_prompt(self, worker: dict[str, Any]) -> Path:
        """Render a short checkpoint prompt that asks the agent to save its progress."""
        prompt_path = PROMPT_DIR / f"{worker['agent']}_checkpoint.md"
        task_id = worker.get("task_id", "unassigned")
        task_title = self.task_title(task_id)
        text = f"""# {worker['agent']} 检查点会话

仓库名称: {self.project.get('repository_name', 'target-repo')}
Agent: {worker['agent']}
任务: {task_id} - {task_title}
Worktree: {worker['worktree_path']}
分支: {worker['branch']}

当前会话结束前，请先保存检查点。

要求:

1. 在 `checkpoints/agents/{worker['agent']}.md` 写入检查点，内容请用中文概括：
   - 当前任务已经完成了什么
   - 你创建或修改过哪些关键文件
   - 还剩下哪些工作
   - 目前的阻塞点或重要发现
   - 当前测试状态
2. 只聚焦于工作本身，不要展开 control-plane 或会话机制。
3. 内容保持简洁但信息完整，方便下一个会话低成本续接。
4. 在你的分支上提交该检查点文件，提交信息使用 "checkpoint: {task_id} session pause"。
"""
        prompt_path.write_text(text, encoding="utf-8")
        return prompt_path

    def soft_stop_all(self, timeout: int = 120) -> dict[str, Any]:
        """Gracefully stop all agents after launching checkpoint sessions to save progress."""
        with self.lock:
            # Identify active agents
            active_agents: list[str] = []
            for agent, wp in self.processes.items():
                if wp.process.poll() is None:
                    active_agents.append(agent)

            if not active_agents:
                return {"ok": True, "stopped": [], "checkpointed": [], "skipped": [], "cleanup": self.cleanup_status()}

            # Stop current processes first
            stopped: list[str] = []
            for agent in active_agents:
                result = self.stop_worker_locked(agent)
                if result.get("stopped") or result.get("already_stopped"):
                    stopped.append(agent)

            # Launch checkpoint sessions for each previously-active agent
            checkpoint_procs: list[tuple[str, subprocess.Popen]] = []
            checkpointed: list[str] = []
            skipped: list[str] = []
            for agent_name in active_agents:
                worker = next((w for w in self.workers if w["agent"] == agent_name), None)
                if not worker:
                    skipped.append(agent_name)
                    continue
                try:
                    pool_name = worker.get("resource_pool") or "ducc_pool"
                    pool = self.resource_pools.get(pool_name, {})
                    provider_name = worker.get("provider") or pool.get("provider") or "ducc"
                    provider = self.providers.get(provider_name, {})
                    model = worker.get("model") or pool.get("model") or "unknown"
                    template = worker.get("command_template") or provider.get("command_template")
                    if not template:
                        skipped.append(agent_name)
                        continue

                    prompt_path = self.render_checkpoint_prompt(worker)
                    prompt_transport = self.provider_prompt_transport(provider_name, provider)
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
                    command = self.sanitize_provider_command(provider_name, command, prompt_transport)
                    env = os.environ.copy()
                    env.pop("CLAUDECODE", None)
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
                        env.update({str(k): str(v) for k, v in extra_env.items()})
                    env.update(self.guarded_worker_env(worker, provider_name, provider))
                    if self.provider_uses_exec_wrapper(provider_name, provider):
                        wrapper_path = self.ensure_provider_exec_wrapper(provider_name)
                        command = [str(wrapper_path), *command]

                    log_path = LOG_DIR / f"{agent_name}_checkpoint.log"
                    log_handle = log_path.open("w", encoding="utf-8")
                    prompt_handle = prompt_path.open("r", encoding="utf-8") if prompt_transport == "stdin" else None
                    proc = subprocess.Popen(
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
                    checkpoint_procs.append((agent_name, proc))
                    self.peek_append(agent_name, [f"[checkpoint] saving progress for {agent_name}..."])
                except Exception:
                    skipped.append(agent_name)

        # Wait for checkpoint processes outside the lock
        for agent_name, proc in checkpoint_procs:
            try:
                proc.wait(timeout=timeout)
                checkpointed.append(agent_name)
                self.peek_append(agent_name, [f"[checkpoint] {agent_name} progress saved"])
            except subprocess.TimeoutExpired:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                skipped.append(agent_name)
                self.peek_append(agent_name, [f"[checkpoint] {agent_name} timed out, killed"])

        with self.lock:
            self.last_event = f"soft_stop:{len(checkpointed)} checkpointed, {len(stopped)} stopped"
            self.write_session_state()
            return {
                "ok": True,
                "stopped": stopped,
                "checkpointed": checkpointed,
                "skipped": skipped,
                "cleanup": self.cleanup_status(),
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
