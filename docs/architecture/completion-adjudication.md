# Architecture: Independent Completion Adjudication

## 1. Principle

Neither an agent declaring "DONE" nor Step-Code emitting "GOAL COMPLETE" can close a task or declare project completion.

## 2. Adjudication Pipeline

When completion is proposed:

```text
PROPOSED COMPLETION
       |
       v
CompletionEvaluator.adjudicate()
       |
       +-- 1. All mandatory TechnicalObligations SATISFIED?
       +-- 2. All required technical claims VERIFIED (not just unit tests)?
       +-- 3. All required evidence fresh (timestamp > mutation boundary)?
       +-- 4. Open verification frontier clean (0 unresolved items)?
       +-- 5. All regression checks clean?
       +-- 6. Workspace identity consistent with authoritative root?
       |
       +---> All passed -> ACCEPT
       +---> Failed/broken items -> RECOVER
       +---> Incomplete/unresolved -> BLOCK
```
