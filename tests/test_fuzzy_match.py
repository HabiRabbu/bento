"""Tests for the fuzzy matching logic in CommandPalette._fuzzy_match."""

from __future__ import annotations

from bento_app.command_palette import CommandPalette


def test_fuzzy_match_exact():
    """Exact text matches itself."""
    assert CommandPalette._fuzzy_match("system", "system") is True


def test_fuzzy_match_subsequence():
    """Subsequence characters in order match."""
    assert CommandPalette._fuzzy_match("sysmon", "system monitor") is True


def test_fuzzy_match_no_match():
    """Characters not present in text don't match."""
    assert CommandPalette._fuzzy_match("xyz", "system") is False


def test_fuzzy_match_empty_query():
    """Empty query matches everything."""
    assert CommandPalette._fuzzy_match("", "system") is True
    assert CommandPalette._fuzzy_match("", "") is True


def test_fuzzy_match_case_insensitive():
    """_fuzzy_match is called with lowered strings; verify lowercase matching."""
    # The palette lowercases both query and text before calling _fuzzy_match,
    # so we test with already-lowered inputs as the method would receive.
    assert CommandPalette._fuzzy_match("sys", "system monitor") is True
    assert CommandPalette._fuzzy_match("sm", "system monitor") is True
    # Direct uppercase won't match lowercase (method is case-sensitive itself)
    assert CommandPalette._fuzzy_match("SYS", "system") is False
