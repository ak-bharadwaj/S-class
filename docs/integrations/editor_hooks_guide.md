# Editor Hooks Integration Guide

S-Class transparently intercepts and validates agent actions via native editor hook endpoints.

## 1. OpenAI Codex CLI
Add to `.codex/hooks.json`:
```json
{
  "pre_tool_call": "sclass hook --provider codex --event pre_call",
  "post_tool_call": "sclass hook --provider codex --event post_call"
}
```

## 2. Anthropic Claude Code
Configure in `.claude/settings.local.json`:
```json
{
  "commandInterceptors": ["sclass hook --provider claude"]
}
```

## 3. Google Antigravity
Configure in `.agents/hooks.json`:
```json
{
  "lifecycle": "sclass hook --provider antigravity"
}
```
