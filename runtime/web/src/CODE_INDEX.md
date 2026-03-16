# CODE_INDEX — runtime/web/src/

React dashboard frontend for the WARP control plane. UI copy is Chinese-first; backend-generated durable prompts and reports are also localized to Chinese.

## Library modules (`lib/`)

| Module | Responsibility | Key exports |
|---|---|---|
| `local-types.ts` | Frontend-only types, constants, drafts, view enums | `AgentRow`, `ProgressModel`, `MailboxDraft`, `WorkflowDraft`, `AUTO_REFRESH_MS`, ... |
| `utils.ts` | Text translation, config normalization, display-state helpers, clipboard/path utilities | `translateUiText`, `translateColumnLabel`, `translateOptionLabel`, `tabLabel`, `displayState`, `normalizeConfig`, `parseQueue`, `writeClipboard`, ... |
| `config.ts` | Config hydration, reset-to-A0 behavior, derived worker paths/queues, validation helpers | `hydrateConfigForA0`, `buildPlannedWorkers`, `workerPlanView`, `configForProjectSave`, ... |
| `workflow.ts` | Workflow draft hydration, brief generation, mailbox/task peeks | `workflowDraftFromTask`, `workflowDraftFromRequest`, `workflowBriefLines`, `workflowPeekTasks`, `mailboxPeekMessages` |
| `data.ts` | Dashboard-state to view-model shaping, validation summaries, localized launch error formatting | `buildAgentRows`, `buildProgressModel`, `buildIssueMap`, `formatLaunchErrorMessage`, `renderValidation` |

## Component modules (`components/`)

| Module | Responsibility | Key exports |
|---|---|---|
| `shared.tsx` | Reusable stateless UI primitives for tables, fields, issue lists, metrics | `DataTable`, `Field`, `SelectField`, `SectionIssueList`, `Metric`, `HelperCard` |
| `cards.tsx` | Overview/operations cards for merge, mailbox, workflow, cleanup, automation summary | `MergeCard`, `AgentCard`, `A0RequestCard`, `MailboxCard`, `CleanupWorkerCard`, `WorkflowPatchCard`, ... |
| `OverviewTab.tsx` | Task DAG, progress, merge board, live agent peek | `OverviewTab` |
| `OperationsTab.tsx` | Workflow, mailbox, cleanup, manager-facing operations | `OperationsTab` |
| `SettingsTab.tsx` | Project paths, pools, defaults, per-worker overrides | `SettingsTab` |
| `A0ConsoleView.tsx` | A0 console pop-out for approvals, unblock guidance, workflow editing | `A0ConsoleView` |
| `AgentPeekPanel.tsx` | Sliding window live output per agent | `AgentPeekPanel` |
| `TaskDAG.tsx` | DAG visualization for backlog dependencies | `TaskDAG` |

## Top-level files

| File | Responsibility |
|---|---|
| `App.tsx` | Application shell, polling, tab routing, dashboard actions, A0 console integration |
| `api.ts` | Fetch wrappers for dashboard APIs |
| `types.ts` | Shared API-facing type definitions |
| `main.tsx` | React entry point |
| `styles.css` | Global stylesheet |

## Build

```bash
source ~/.bashrc && cd runtime/web && npm run build
```
