# S-Class SDK: Designing Custom Pipelines

The S-Class SDK is a framework for defining custom workflow plugins. By configuring FSM states, capabilities, and events, you can implement pipelines for any domain.

---

## 1. Pipeline Creation Guide

To design a new pipeline (e.g. `Research`, `GameDev`, `Startup`):

1.  **Define Metadata:** Create a `plugin.json` describing your pipeline.
2.  **Declare FSM States:** Write a `workflow.json` mapping your states, parallel groups, and transitions.
3.  **Define State Properties:** Declare what variables your states record using `state_schema.json`.
4.  **Register Transition Events:** List your first-class events in `events.json`.
5.  **Configure Subagent Prompts:** Write prompt files under a `prompts/` directory for each role.

---

## 2. Example: Research Pipeline Spec

```json
{
  "states": {
    "LITERATURE_SEARCH": {
      "transitions": {
        "literature_indexed": "PAPER_REVIEW"
      }
    },
    "PAPER_REVIEW": {
      "transitions": {
        "review_complete": "HYPOTHESIS"
      }
    },
    "HYPOTHESIS": {
      "transitions": {
        "hypothesis_framed": "EXPERIMENT"
      }
    },
    "EXPERIMENT": {
      "transitions": {
        "data_collected": "PAPER_DRAFT"
      }
    },
    "PAPER_DRAFT": {}
  }
}
```

---

## 3. Registering the Custom Pipeline
Place your new plugin folder inside the global plugins path:
`C:\Users\<username>\.gemini\config\plugins\<new-plugin-name>/`

Reference it in your local workspace `CLAUDE.md`:
```markdown
pipeline: <new-plugin-name>
```
The S-Class runtime will automatically bootstrap it.
