# Engineering Experience Templates

Use these templates for `.devexp/` records. Keep entries concise. Prefer stable project facts over full debug transcripts.

## Project Overview

```markdown
---
record_type: Project Overview
project_id:
project_name:
status: idea | prototype | mvp | active | paused | archived
last_updated: YYYY-MM-DD
tech_stack: []
repository:
---

# Project Overview: <Project Name>

## 1. Project Purpose

What problem does this project solve, and who is it for?

## 2. Current Stage

What stage is the project in now? What is already working?

## 3. Core Architecture

Describe the current architecture in plain language.

## 4. Key Modules

| Module | Responsibility | Notes |
|---|---|---|
| `<path>` |  |  |

## 5. Data / State Flow

```text
Input
-> Processing
-> Storage
-> Output
```

## 6. Important Engineering Principles

- 

## 7. Key Decisions

- ADR: 

## 8. Major Issues Resolved

- Major Issue: 

## 9. Current Known Risks

- 

## 10. Next Actions

- 

## 11. How to Resume This Project

```bash
# Install dependencies

# Run tests

# Start the app or workflow

# Read key docs
```

## 12. Notes for Coding Agent

- Read this overview before major changes.
- Read relevant records under `.devexp/records/`.
```

## ADR

```markdown
---
record_type: ADR
title:
date: YYYY-MM-DD
project_id:
status: Draft | Accepted | Superseded
area: Architecture | Backend | Frontend | Data | Agent Workflow | DevOps | Testing
importance: Low | Medium | High
tags: []
---

# ADR: <Decision Title>

## Context

What design problem or constraint required a decision?

## Decision

What was decided?

## Alternatives Considered

1. Option A:
   - Pros:
   - Cons:

2. Option B:
   - Pros:
   - Cons:

## Rationale

Why is the chosen option best for this project now?

## Consequences

### Positive

- 

### Negative / Trade-offs

- 

## Follow-up

- 

## Agent Instruction Candidate

```text
Optional short future rule. Leave empty if no stable rule exists.
```
```

## Major Issue

```markdown
---
record_type: Major Issue
title:
date: YYYY-MM-DD
project_id:
status: Open | Partially Resolved | Resolved
area: Backend | Frontend | Data | DevOps | Agent Workflow | Testing
severity: Medium | High
importance: Medium | High
tags: []
---

# Major Issue: <Issue Title>

## Problem

What major blocker happened?

## Impact

What did it block or risk?

## Diagnosis

Record only the evidence that changed the diagnosis.

## Root Cause

What was the underlying cause?

## Resolution

What fixed or mitigated it?

## Verification

How was the resolution checked?

## Lessons Learned

What should future work remember?

## Prevention

How can similar issues be avoided?

## Agent Instruction Candidate

```text
Optional short future rule. Leave empty if no stable rule exists.
```
```

## Review

```markdown
---
record_type: Review
title:
date: YYYY-MM-DD
project_id:
period:
status: Draft | Final
importance: Low | Medium | High
tags: []
---

# Review: <Review Title>

## What Changed

What changed in this period or milestone?

## Key Decisions

- ADR: 

## Major Issues

- Major Issue: 

## What Worked

- 

## What Did Not Work

- 

## Updated Engineering Principles

- 

## Recommended AGENTS.md Updates

```text
Optional patch-style candidate rules. Leave empty if none.
```
```
