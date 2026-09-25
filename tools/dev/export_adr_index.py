"""Generates markdown index of all accepted Architectural Decision Records."""
import os

def generate_index(adr_dir: str) -> str:
    files = sorted([f for f in os.listdir(adr_dir) if f.startswith("adr_")])
    lines = ["# Architectural Decision Records Index\n"]
    for f in files:
        lines.append(f"- [{f}](./{f})")
    return "\n".join(lines)

if __name__ == "__main__":
    print("ADR Index Generator Ready.")
