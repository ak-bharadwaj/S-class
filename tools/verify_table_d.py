import hashlib
import os
import subprocess
import sys

def main():
    hashes_file = "FROZEN-HASHES-388c0b54.txt"
    if not os.path.exists(hashes_file):
        print(f"Error: {hashes_file} not found")
        sys.exit(1)

    print("| File Path | Expected Hash | Actual Hash | Match |")
    print("|---|---|---|---|")

    all_matched = True
    with open(hashes_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                continue
            expected_hash, rel_path = parts
            rel_path = rel_path.strip()

            if not os.path.exists(rel_path):
                print(f"| {rel_path} | {expected_hash[:12]}... | MISSING | NO |")
                all_matched = False
                continue

            with open(rel_path, "rb") as content_file:
                actual_hash = hashlib.sha256(content_file.read()).hexdigest()

            matches = (actual_hash == expected_hash)
            if not matches:
                all_matched = False
            status = "YES" if matches else "NO"
            print(f"| {rel_path} | `{expected_hash}` | `{actual_hash}` | {status} |")

    print("\nProtected Paths Diff Stat vs 388c0b54:")
    res = subprocess.run(
        ["git", "diff", "--stat", "388c0b54..HEAD", "--", "00-SPEC", "10-CONFORMANCE", "20-RUNTIME", ".github", "tools/gates", "tests/guards", "docs", "governance"],
        capture_output=True,
        text=True,
    )
    diff_out = res.stdout.strip()
    if diff_out:
        print(diff_out)
        all_matched = False
    else:
        print("0 bytes (diff is completely empty)")

    if not all_matched:
        sys.exit(1)

if __name__ == "__main__":
    main()
