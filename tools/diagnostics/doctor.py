#!/usr/bin/env python3
"""S-Class Diagnostics Doctor tool facade."""
from sclass.diagnostics.doctor import CheckResult, SClassDoctor, main

__all__ = ["CheckResult", "SClassDoctor", "main"]

if __name__ == "__main__":
    main()
