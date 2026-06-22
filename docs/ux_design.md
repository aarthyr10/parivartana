# UX Design

This document explains the design decisions behind the PARIVARTANA Streamlit application. It is meant for a future maintainer who will inherit the code and extend it.

## Design principles

**Honesty over polish.** When Stage 2 is not wired, the UI says so. When a dataset is not present, it says so. We do not fabricate sample outputs, mock progress bars, or claim completion before the underlying capability exists. A user trusting the dashboard must be able to act on what the dashboard says.

**Progressive disclosure.** The Home dashboard surfaces the four metrics that matter most (stages live, dataset coverage, providers configured, samples available). Anything else is one click away. Tabs and expanders defer detail until the user asks for it.

**Status-first.** Every page begins with a small set of headline metrics or status badges. The user knows the state of the system before they have to scan any tables.

**One action per surface.** The Workspace page does one thing: transpile a single program. The Batch Run page does one thing: process a dataset slice. The Datasets page does one thing in three modes: browse, ingest, sample. Mixing these would invite the user to lose track of what they are doing.

**Empty states with action.** When there is no data to show, the page does not display a table of zeros. It explains what is missing and offers the next step. Empty Batch Run links directly to Datasets. Empty Metrics links to Batch Run.

## Visual system

**Light theme, single accent.** The primary colour `#4F46E5` (deep indigo) is used sparingly for headlines, primary buttons, and brand wordmarks. Neutral grays carry the rest. This keeps screens calm and lets the user's attention land on the data.

**Typography.**
- Brand wordmark in serif (Georgia / Times) — signals heritage, fitting for a project named in Sanskrit.
- Page bodies in the platform sans-serif — neutral, readable.
- Code in monospace.
- Eyebrows and labels in small caps with letter-spacing — signals navigation context without competing with content.

**Badges, not colours alone.** Status is shown both in colour and in text label (Live, In Progress, Beta, Planned). Colour-blind users get the same information.

**Whitespace.** Cards have 1.4rem padding. Dividers are 1.5rem above and below. The block container is capped at 1280px so lines never grow too wide to scan.

## Information architecture

```
Home (Dashboard)         At-a-glance health, quick links, system status
  +-- Workspace          Single-program transpile (Stage 1 live; 2 and 3 stubbed)
  +-- Batch Run          Dataset slice through Stage 1 with persisted run files
  +-- Datasets           Browse, ingest, sample (the heaviest page)
  +-- Pipeline Config    YAML inspector for the four config files
  +-- Metrics            Run history with trend lines
  +-- Settings           Environment, paths, credentials, dependencies
```

## Key interaction flows

**First-run flow.** A new user lands on Home. The dataset coverage card shows 0/9. They click "Open Datasets" → land on Ingest tab → click "Ingest all auto-fetchable" → wait for download → the same coverage card now shows 6/9 (HuggingFace and GitHub corpora). Manual datasets remain marked as such with clear instructions.

**Single-program flow.** From Workspace, the user picks a sample, optionally toggles Stage 3, clicks Run. Results stream into a five-tab section (AST, Tokens, Linearised, Stage 2, Stage 3). Stage 2 always shows an "In Progress" notice with concrete pointers to the integration file. Stage 3 either runs or explains exactly which environment variable is missing.

**Batch flow.** From Batch Run, the user picks a present dataset, sets a slice size, clicks Start. A progress bar updates as records process. On completion, summary metrics, a tier distribution chart, and a per-record table render together. With "Save run" enabled, the result lands in `artifacts/outputs/` and appears on the Metrics page.

## Error handling

Every long-running operation (ingestion, batch processing, LLM calls) is wrapped in a try-except that surfaces the underlying message in `st.error` and the trace in a collapsed `st.expander`. The application never silently swallows a failure. When an external dependency is missing (`datasets`, `git`, `cobc`), the failure points to the exact remediation.

## What we deliberately did not do

- No emojis in any UI surface.
- No dark mode toggle. The product is light-theme only by design.
- No animated transitions. They become tedious on the second visit.
- No marketing-style copy. Every sentence on the dashboard is true.
- No hand-rolled charts where Streamlit's `st.bar_chart` and `st.line_chart` work.
