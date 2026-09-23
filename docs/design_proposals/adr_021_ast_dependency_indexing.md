# ADR-021: AST Graph Dependency Indexing

## Status
Accepted

## Context
Text grep cannot accurately resolve symbol definitions across multi-package projects.

## Decision
S-Class parses source files into Tree-sitter syntax trees and constructs an in-memory graph of symbol dependencies.
