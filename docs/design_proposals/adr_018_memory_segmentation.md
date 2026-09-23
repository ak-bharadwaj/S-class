# ADR-018: Agent Memory Segmentation and Quarantine Rules

## Status
Accepted

## Context
Multi-agent swarms must prevent hallucination contamination between subagents.

## Decision
Each agent operates in an isolated memory compartment. Knowledge sharing occurs exclusively via verified project claims.
