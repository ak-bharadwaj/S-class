# Antigravity Plugin Blueprint: Designing Custom Workflows

S-Class serves as the reference architecture and blueprint for building workflow plugins on the Antigravity platform. Developers can clone this structure to create custom pipelines (e.g. Research, Documentation, Security Audits) without changing the core engine.

---

## 1. Antigravity Plugin Blueprint Layout
To build a new workflow extension, organize your files into this standard layout:
```
plugins/
└── <your-plugin-name>/
    ├── plugin.json          # Plugin metadata & options
    ├── state_schema.json    # Shared state schema definition
    ├── events.json          # FSM state transition triggers
    ├── capabilities.json    # Agent permission constraints
    ├── workflow.json        # FSM States & parallel groups definition
    ├── prompts/             # Subagent role definitions
    └── README.md            # Guide
```

---

## 2. Implementing New Workflows

### A. Literature Research Workflow (Example)
To implement a literature research pipeline:
1.  **workflow.json:** Define states like `LITERATURE_INDEX`, `SYNTHESIS`, `DRAFTING`.
2.  **prompts/:** Create prompts for specialized roles: `dss_researcher.md` (read-only tools), `dss_writer.md` (write-enabled tools).
3.  **capabilities.json:** Enforce that the researcher can read the web, but only the writer can compile markdown documents.

### B. Documentation Extraction Workflow (Example)
1.  **workflow.json:** Map states: `CODE_INSPECT` $\rightarrow$ `API_EXTRACT` $\rightarrow$ `DOCS_COMPILE` $\rightarrow$ `REVIEW`.
2.  **prompts/:** Define prompts for `dss_inspector.md`, `dss_writer.md`, and `dss_reviewer.md`.
