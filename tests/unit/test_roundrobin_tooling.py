"""
Unit tests for the round-robin collaborator commit utility (tools/roundrobin_commit.py).
Verifies that author assignment alternates deterministically between collaborators:
  - ak-bharadwaj <dornipaduakshith@gmail.com>
  - tHarini1105 <harini0112005@gmail.com>
  - Katyaeni17 <katyaeni87@gmail.com>
"""

import sys
import os
import pytest

# Ensure root tools directory is importable
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from tools.roundrobin_commit import (
    ACCOUNT_AK,
    ACCOUNT_HARINI,
    ACCOUNT_KATYAENI,
    get_next_author,
    get_last_commit_author,
)


def test_roundrobin_toggles_from_ak_to_harini():
    """When the last author is ak-bharadwaj, next author must be tHarini1105."""
    next_name, next_email = get_next_author("ak-bharadwaj <dornipaduakshith@gmail.com>")
    assert (next_name, next_email) == ACCOUNT_HARINI
    assert next_name == "tHarini1105"
    assert next_email == "harini0112005@gmail.com"


def test_roundrobin_toggles_from_harini_to_katyaeni():
    """When the last author is tHarini1105, next author must be Katyaeni17."""
    next_name, next_email = get_next_author("tHarini1105 <harini0112005@gmail.com>")
    assert (next_name, next_email) == ACCOUNT_KATYAENI
    assert next_name == "Katyaeni17"
    assert next_email == "katyaeni87@gmail.com"


def test_roundrobin_toggles_from_katyaeni_to_ak():
    """When the last author is Katyaeni17, next author must be ak-bharadwaj."""
    next_name, next_email = get_next_author("Katyaeni17 <katyaeni87@gmail.com>")
    assert (next_name, next_email) == ACCOUNT_AK
    assert next_name == "ak-bharadwaj"
    assert next_email == "dornipaduakshith@gmail.com"


def test_roundrobin_defaults_to_ak_when_author_unknown():
    """When the last author is empty or unrecognized, defaults safely to ak-bharadwaj."""
    assert get_next_author("") == ACCOUNT_AK
    assert get_next_author("   ") == ACCOUNT_AK
    assert get_next_author(None) == ACCOUNT_AK
    assert get_next_author(12345) == ACCOUNT_AK
    assert get_next_author("Unknown Author <unknown@corp.com>") == ACCOUNT_AK


def test_roundrobin_case_insensitivity_and_whitespace():
    """Author strings with whitespace or mixed-case should resolve accurately."""
    assert get_next_author("  AK-BHARADWAJ <dornipaduakshith@gmail.com> ") == ACCOUNT_HARINI
    assert get_next_author("  THARINI1105 <HARINI0112005@GMAIL.COM> ") == ACCOUNT_KATYAENI
    assert get_next_author("  KATYAENI17 <KATYAENI87@GMAIL.COM> ") == ACCOUNT_AK


def test_roundrobin_full_three_way_cycle():
    """Successive calls simulate a complete 3-person commit cycle."""
    # Start from ak
    author_1 = f"{ACCOUNT_AK[0]} <{ACCOUNT_AK[1]}>"
    next_1 = get_next_author(author_1)
    assert next_1 == ACCOUNT_HARINI

    # From harini
    author_2 = f"{next_1[0]} <{next_1[1]}>"
    next_2 = get_next_author(author_2)
    assert next_2 == ACCOUNT_KATYAENI

    # From katyaeni
    author_3 = f"{next_2[0]} <{next_2[1]}>"
    next_3 = get_next_author(author_3)
    assert next_3 == ACCOUNT_AK

    # Back to harini
    author_4 = f"{next_3[0]} <{next_3[1]}>"
    next_4 = get_next_author(author_4)
    assert next_4 == ACCOUNT_HARINI


def test_get_last_commit_author_returns_non_empty_in_repo():
    """In a valid git repository with commits, get_last_commit_author returns a non-empty string."""
    author = get_last_commit_author()
    assert isinstance(author, str)
    assert len(author) > 0
    assert "@" in author
