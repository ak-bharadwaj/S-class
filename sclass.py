#!/usr/bin/env python3
"""
S-Class EOS Unified Developer CLI (sclass.py)

The sovereign developer CLI for S-Class EOS.
Commands:
  sclass learn      - Learns a new empirical regression failure case from a bad run
  sclass rules      - Projects AGENTS.md rules across platforms or checks CI drift
  sclass classify   - Deterministic task categorization and scope classification
  sclass doctor     - Runs system preflight diagnostics and health checks
  sclass grill      - Runs adversarial specification grill on requirements
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    parser = argparse.ArgumentParser(
        prog="sclass",
        description="S-Class EOS — The Deterministic AI Systems Runtime & Safety-Case Engine"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: learn
    learn_parser = subparsers.add_parser("learn", help="Capture a new failure case into regression_cases.json")
    learn_parser.add_argument("--project", default="GeneralProject", help="Target project identifier")
    learn_parser.add_argument("--stack", default="python_pytest", help="Technology stack")
    learn_parser.add_argument("--summary", help="Summary of failure mode")
    learn_parser.add_argument("--root-cause", default="unhandled_edge_case", help="Root cause classification")
    learn_parser.add_argument("--missing-contracts", help="Comma-separated missing contracts/invariants")
    learn_parser.add_argument("--skeptic-rule-id", default="SKEPTIC-STRUCTURAL-GROUNDING", help="Mapped skeptic rule ID (defaults to grounded rule)")
    learn_parser.add_argument("--from-run-log", help="Path to a test output or error log file to parse")
    learn_parser.add_argument("--path", help="Path to regression_cases.json")

    # Command: rules
    rules_parser = subparsers.add_parser("rules", help="Sync AGENTS.md cross-platform rules or check drift")
    rules_parser.add_argument("--check", action="store_true", help="Run CI drift detection; fails if target files drifted from AGENTS.md")
    rules_parser.add_argument("--sync", action="store_true", help="Project AGENTS.md to .cursorrules, CLAUDE.md, etc.")
    rules_parser.add_argument("--workspace", default=os.getcwd(), help="Target workspace root")

    # Command: classify
    classify_parser = subparsers.add_parser("classify", help="Deterministically classify a task description")
    classify_parser.add_argument("task_text", nargs="?", help="Task text or prompt to classify")

    # Command: doctor
    doctor_parser = subparsers.add_parser("doctor", help="Run S-Class doctor system preflight diagnostics")
    doctor_parser.add_argument("--workspace", default=os.getcwd(), help="Target workspace directory")

    # Command: grill
    grill_parser = subparsers.add_parser("grill", help="Run adversarial specification griller")
    grill_parser.add_argument("spec_file", nargs="?", help="Path to spec file to grill (default: PROJECT.md)")

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()

    if args.command == "learn":
        from failure_log import sclass_learn_cli
        cmd_args = []
        if args.project: cmd_args.extend(["--project", args.project])
        if args.stack: cmd_args.extend(["--stack", args.stack])
        if args.summary: cmd_args.extend(["--summary", args.summary])
        if args.root_cause: cmd_args.extend(["--root-cause", args.root_cause])
        if args.missing_contracts: cmd_args.extend(["--missing-contracts", args.missing_contracts])
        if args.skeptic_rule_id: cmd_args.extend(["--skeptic-rule-id", args.skeptic_rule_id])
        if args.from_run_log: cmd_args.extend(["--from-run-log", args.from_run_log])
        if args.path: cmd_args.extend(["--path", args.path])
        sys.exit(sclass_learn_cli(cmd_args))

    elif args.command == "rules":
        from rule_projector import RuleProjector
        projector = RuleProjector(workspace_dir=args.workspace)
        if args.check:
            drifted, details = projector.check_drift()
            if drifted:
                print("[!] Rule drift detected against canonical AGENTS.md:")
                for file_path, status in details.items():
                    if status != "IN_SYNC":
                        print(f"  - {file_path}: {status}")
                print("\nRun `sclass rules --sync` to regenerate projected rule files.")
                sys.exit(1)
            else:
                print("[OK] All cross-platform rule files are perfectly in sync with AGENTS.md.")
                sys.exit(0)
        else:
            synced = projector.sync()
            print(f"[OK] Successfully projected AGENTS.md to {len(synced)} rule files:")
            for p in synced:
                print(f"  - {p}")
            sys.exit(0)

    elif args.command == "classify":
        from task_classifier import TaskClassifier
        task_text = args.task_text or " ".join(sys.argv[2:])
        if not task_text:
            print("Error: task text required")
            sys.exit(1)
        result = TaskClassifier.classify_task(task_text)
        print("==================================================================")
        print("[*] Task Classification (Deterministic Over Adaptive):")
        print(f"  Category:        {result['category']}")
        print(f"  Scope Tier:      {result['scope_tier']}")
        print(f"  Confidence:      {result['confidence']:.2f}")
        print(f"  Matched Rules:   {', '.join(result.get('matched_rules', []))}")
        print(f"  Deterministic:   {result.get('deterministic', True)}")
        print("==================================================================")
        sys.exit(0)

    elif args.command == "doctor":
        import shutil
        import importlib.util
        from doctor import run_doctor
        from rule_projector import RuleProjector
        from failure_log import FailureLogManager

        workspace = os.path.abspath(args.workspace)
        print("==================================================================")
        print(f"[*] Running S-Class System Preflight Diagnostics on {workspace}")
        print("==================================================================")

        # 1. Standard Doctor Report
        report = run_doctor(workspace)
        print(f"Overall Workspace Health: [{report.overall_status}]")
        for chk in report.checks:
            tag = f"[{chk.status}]".ljust(8)
            print(f"  {tag} {chk.name}: {chk.message}")

        # 2. Local AST SAST Check
        print("\nSecurity SAST Binaries (Subprocess Substrate):")
        has_semgrep = shutil.which("semgrep") or (importlib.util.find_spec("semgrep") is not None)
        has_bandit = shutil.which("bandit") or (importlib.util.find_spec("bandit") is not None)
        print(f"  [{'PASS' if has_semgrep else 'WARN'}] Semgrep AST Scanner: {'Installed' if has_semgrep else 'Not found in PATH (operates in regex fallback)'}")
        print(f"  [{'PASS' if has_bandit else 'WARN'}] Bandit Python SAST:  {'Installed' if has_bandit else 'Not found in PATH (operates in regex fallback)'}")

        # 3. Empirical Failure Log
        print("\nEmpirical Skeptic Corpus:")
        cases = FailureLogManager.load_cases()
        print(f"  [PASS] regression_cases.json: {len(cases)} verified failure cases active")

        # 4. Cross-Platform Rule Drift
        projector = RuleProjector(workspace)
        drifted, _ = projector.check_drift()
        print(f"  [{'WARN' if drifted else 'PASS'}] Rule Projector (AGENTS.md): {'Drift detected (run `sclass rules --sync`)' if drifted else 'In sync'}")
        print("==================================================================")
        sys.exit(0 if report.overall_status == "HEALTHY" else 1)

    elif args.command == "grill":
        from sclass_grill import SpecGrillerEngine
        spec_target = args.spec_file or os.getcwd()
        workspace = os.path.dirname(os.path.abspath(spec_target)) if os.path.isfile(spec_target) else os.path.abspath(spec_target)

        print(f"[*] Running S-Class Spec Griller on workspace: {workspace}")
        report = SpecGrillerEngine.grill_specification(workspace_dir=workspace)
        print("==================================================================")
        print(f"[*] Spec Grill Result: {'PASSED' if report.overall_passed else 'FAILED'}")
        print(f"  Vectors Tested: {report.vectors_passed}/{report.total_vectors_tested} Passed")
        print(f"  Critical Defects: {report.critical_defects_found}")
        for r in report.vector_results:
            tag = "[PASS]" if r.passed else f"[{r.risk_level}]"
            print(f"  {tag.ljust(10)} {r.name}")
            for f in r.findings:
                print(f"     - {f}")
        print("==================================================================")
        sys.exit(0 if report.overall_passed else 1)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
