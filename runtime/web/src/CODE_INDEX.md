# CODE_INDEX — runtime/web/src/

Frontend React dashboard for the WARP control plane. Built with React 18,
TypeScript, and bundled via esbuild.

## Library Modules (lib/)

| Module | Lines | Responsibility | Key Exports |
|---|---|---|---|
| `local-types.ts` | 127 | Frontend-only type definitions and constants | Types: `AgentRow`, `ProgressModel`, `IssueMap`, `SectionStatusMap`, `PlannedWorker`, `WorkerPlanView`, `WorkerResetScope`, `MailboxDraft`, `WorkflowDraft`, `WorkflowPresetAction`. Constants: `AUTO_REFRESH_MS`, `A0_CONSOLE_VIEW`, `DEFAULT_MAILBOX_DRAFT`, `DEFAULT_WORKFLOW_DRAFT` |
| `utils.ts` | 135 | Pure utility functions (text, state, config normalization) | `normalizedText`, `isAutoManagedBlank`, `isAutoManagedCommandBlank`, `isPlaceholderPath`, `firstMeaningfulValue`, `firstMeaningfulCommand`, `firstMeaningfulPath`, `classNames`, `displayState`, `stateClass`, `renderCell`, `formatTokenCount`, `cloneConfig`, `normalizeConfig`, `parseQueue`, `stringifyQueue`, `launchStrategyLabel`, `slugify`, `preferredLaunchProvider`, `writeClipboard`, `projectReferenceWorkspace` |
| `config.ts` | 433 | Config transformation, hydration, derivation, validation | `mergeWorkerWithDefaults`, `resetWorkerDefaultsToA0`, `resetWorkerOverridesToA0`, `deriveWorktreePath`, `deriveBranchName`, `deriveDefaultEnvironmentPath`, `normalizeDerivedPaths`, `mergeSavedSection`, `buildSectionValue`, `configForProjectSave`, `buildRuntimeWorkerMap`, `buildResolvedWorkerMap`, `deriveDefaultPoolQueue`, `inferRuntimeWorkerValue`, `buildPlannedWorkers`, `workerPlanView`, `hydrateConfigForA0`, `sectionMatchesField`, `collectSectionIssues`, `sectionRouteUnavailable` |
| `workflow.ts` | 128 | Workflow draft manipulation and brief generation | `workflowDraftFromTask`, `workflowDraftFromRequest`, `pickWorkflowTask`, `workflowBriefLines`, `workflowPeekTasks`, `mailboxPeekMessages` |
| `data.ts` | 269 | Derived view-model builders from DashboardState | `buildAgentRows`, `buildProgressModel`, `getLocalValidationIssues`, `buildIssueMap`, `summarizeValidationMessages`, `formatLaunchErrorMessage`, `renderValidation` |

## Component Modules (components/)

| Module | Lines | Responsibility | Key Exports |
|---|---|---|---|
| `shared.tsx` | 142 | Reusable stateless presentational components | `DataTable`, `Field`, `SelectField`, `SectionIssueList`, `SectionHeader`, `Metric`, `ProgressRow`, `HelperCard` |
| `cards.tsx` | 402 | Feature-specific card components used across tabs | `MergeCard`, `AgentCard`, `A0RequestCard`, `MailboxCard`, `CleanupWorkerCard`, `MailboxComposerCard`, `WorkflowBriefCard`, `MailboxPeekCard`, `WorkflowPatchCard`, `AutomationSummary` |
| `OverviewTab.tsx` | 89 | Overview dashboard tab (progress, agents, merge board) | `OverviewTab` |
| `OperationsTab.tsx` | 100 | Operations dashboard tab (workflow, mailbox, cleanup) | `OperationsTab` |
| `SettingsTab.tsx` | 225 | Settings dashboard tab (pools, project, workers) | `SettingsTab` |
| `A0ConsoleView.tsx` | 105 | A0 console view (requests, conversation, workflow) | `A0ConsoleView` |

## Top-Level Files

| Module | Lines | Responsibility | Key Exports |
|---|---|---|---|
| `App.tsx` | 898 | Application shell — state, effects, event handlers, tab routing | `App` |
| `types.ts` | — | Shared API type definitions (DashboardState, ConfigShape, etc.) | All API-facing types |
| `api.ts` | — | API fetch helpers | `fetchState`, `postAction`, etc. |
| `main.tsx` | — | React entry point (renders `<App />`) | — |
| `styles.css` | — | Global stylesheet | — |

**Total: 12 source modules, ~3 053 lines** (from original single-file `App.tsx` at 2 959 lines, plus module overhead).

## Build

```bash
cd runtime/web
npx esbuild src/main.tsx --bundle --format=esm --target=es2020 \
  --jsx=automatic --outdir=static --entry-names=app --loader:.css=css
```
