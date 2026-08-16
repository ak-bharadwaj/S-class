#!/usr/bin/env python3
"""
Gate 1.6C — Failure Taxonomy Classifier
(benchmark/v0/engineering/failure_taxonomy.py)

Classifies failing benchmark runs into 5 mutually exclusive categories:
1. wrong_requirement: Model misinterpreted requirement spec in task prompt.
2. missing_requirement: Model omitted required class, method, or function.
3. implementation_bug: Logic error, TypeError, ValueError, AssertionError in generated code.
4. test_api_mismatch: Function signature / class structure did not match test suite expectations.
5. environment_failure: SyntaxError, ImportError, or system failure.
"""

import re
from typing import Dict, Any, List, Optional

TAXONOMY_CATEGORIES = {
    "wrong_requirement",
    "missing_requirement",
    "implementation_bug",
    "test_api_mismatch",
    "environment_failure"
}

class FailureTaxonomyClassifier:
    @staticmethod
    def classify_failure(oracle_result: Dict[str, Any], raw_prompt: str, final_code: str) -> Dict[str, Any]:
        """
        Analyzes oracle test output and failure trace to assign taxonomy classification.
        """
        if oracle_result.get("all_passed", False):
            return {
                "category": None,
                "reason": "Run passed 100% of oracle tests.",
                "details": []
            }

        stdout = oracle_result.get("stdout", "")
        stderr = oracle_result.get("stderr", "")
        combined_output = f"{stdout}\n{stderr}"

        # 1. Environment / Syntax Failure Check
        if "SyntaxError:" in combined_output or "IndentationError:" in combined_output:
            return {
                "category": "environment_failure",
                "reason": "Generated code contains invalid Python syntax or indentation.",
                "details": FailureTaxonomyClassifier._extract_error_lines(combined_output, ["SyntaxError", "IndentationError"])
            }

        # 2. Test / API Mismatch Check (Signature or import mismatches)
        api_mismatch_patterns = [
            r"TypeError: .* got an unexpected keyword argument",
            r"TypeError: .* takes \d+ positional arguments but \d+ were given",
            r"TypeError: .* missing \d+ required positional argument",
            r"AttributeError: module .* has no attribute",
            r"ImportError: cannot import name",
            r"NameError: name '.*' is not defined"
        ]
        for pattern in api_mismatch_patterns:
            matches = re.findall(pattern, combined_output)
            if matches:
                return {
                    "category": "test_api_mismatch",
                    "reason": f"API / signature mismatch detected: {matches[0]}",
                    "details": matches
                }

        # 3. Missing Requirement Check
        missing_patterns = [
            r"NotImplementedError",
            r"AttributeError: '.*' object has no attribute",
            r"AttributeError: type object '.*' has no attribute"
        ]
        for pattern in missing_patterns:
            matches = re.findall(pattern, combined_output)
            if matches:
                return {
                    "category": "missing_requirement",
                    "reason": f"Required class or method missing: {matches[0]}",
                    "details": matches
                }

        # 4. Implementation Bug vs Wrong Requirement Check
        logic_patterns = [
            r"IndexError: .*",
            r"KeyError: .*",
            r"ValueError: .*",
            r"ZeroDivisionError: .*",
            r"TypeError: unsupported operand type.*",
            r"AssertionError: .*"
        ]
        logic_matches = []
        for pattern in logic_patterns:
            found = re.findall(pattern, combined_output)
            if found:
                logic_matches.extend(found)

        if logic_matches:
            if any("assert " in m.lower() for m in logic_matches) and len(logic_matches) > 3:
                return {
                    "category": "wrong_requirement",
                    "reason": "Model generated implementation that misinterprets requirement specifications.",
                    "details": logic_matches[:5]
                }
            return {
                "category": "implementation_bug",
                "reason": f"Runtime logic error or assertion failure: {logic_matches[0]}",
                "details": logic_matches[:5]
            }

        # Fallback default
        return {
            "category": "wrong_requirement",
            "reason": "Failed oracle assertions without explicit exception traceback.",
            "details": [combined_output[:300]]
        }

    @staticmethod
    def _extract_error_lines(text: str, keywords: List[str]) -> List[str]:
        lines = text.splitlines()
        matched = []
        for line in lines:
            if any(kw in line for kw in keywords):
                matched.append(line.strip())
        return matched if matched else [text[:200]]
