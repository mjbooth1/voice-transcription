#!/usr/bin/env python3
"""
Test script specifically for programming pattern corrections.
Tests underscore notation and dum variable naming.
"""

import os
import sys

# Add the current directory to path so we can import transcription_service
sys.path.insert(0, os.path.dirname(__file__))

from transcription_service import TranscriptionService

def test_programming_corrections():
    """Test the programming-specific correction functionality."""

    print("=" * 70)
    print("PROGRAMMING CORRECTIONS TEST")
    print("=" * 70)

    # Create a transcription service instance
    service = TranscriptionService()

    # Test cases for programming patterns
    test_cases = [
        # === UNDERSCORE NOTATION TESTS ===
        # Known prefixes from @underscore_prefixes
        ("QD underscore delete sheet", "QD_Delete sheet"),
        ("qd underscore prior", "QD_Prior"),  # Should uppercase prefix
        ("API underscore response data", "API_Response data"),
        ("DB underscore connection string", "DB_Connection string"),

        # General underscore patterns (not in prefix list)
        ("variable underscore name", "variable_Name"),
        ("user underscore input", "user_Input"),
        ("test underscore data", "test_Data"),

        # Multiple underscores in one sentence
        ("QD underscore delete and API underscore response", "QD_Delete and API_Response"),

        # === DUM VARIABLE NAMING TESTS ===
        # Should convert these
        ("dumb A1", "duma1"),
        ("dumb country", "dumcountry"),
        ("dumb version", "dumversion"),
        ("dumb data", "dumdata"),
        ("dumb test", "dumtest"),

        # Should NOT convert these (normal usage)
        ("that idea is dumb", "that idea is dumb"),
        ("the answer was dumb", "the answer was dumb"),
        ("it sounds dumb", "it sounds dumb"),

        # === MIXED PATTERNS ===
        ("QD underscore prior then dumb version", "QD_Prior then dumversion"),
        ("at Mike use dumb data from API underscore response", "@Mike use dumdata from API_Response"),

        # === EDGE CASES ===
        # Should not change
        ("underscore by itself", "underscore by itself"),
        ("just dumb", "just dumb"),
        ("QD without underscore", "QD without underscore"),

        # Complex sentences
        ("I need to update the QD underscore delete sheet with dumb country data",
         "I need to update the QD_Delete sheet with dumcountry data"),
    ]

    print(f"Testing {len(test_cases)} programming correction scenarios...\n")

    passed = 0
    failed = 0

    for i, (input_text, expected) in enumerate(test_cases, 1):
        print(f"Test {i}:")
        print(f"  Input:    '{input_text}'")
        print(f"  Expected: '{expected}'")

        try:
            result = service.apply_smart_corrections(input_text)
            print(f"  Output:   '{result}'")

            if result == expected:
                print(f"  [PASS] Correction matches expected output")
                passed += 1
            else:
                print(f"  [FAIL] Output doesn't match expected")
                failed += 1

        except Exception as e:
            print(f"  [ERROR] {e}")
            failed += 1

        print()

    print("=" * 70)
    print(f"TEST RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)

    # Summary of what should work
    print("\nProgramming Corrections Summary:")
    print("✓ Underscore notation: '[word] underscore [word]' → '[word]_[Word]'")
    print("✓ Known prefixes: 'QD underscore delete' → 'QD_Delete' (uppercase prefix)")
    print("✓ Dum variables: 'dumb [variable]' → 'dum[variable]'")
    print("✓ Context-aware: Won't change 'dumb' in normal sentences")
    print("✓ Multi-word: 'delete sheet' → 'DeleteSheet' (PascalCase)")

    print("\nTo add more patterns:")
    print("1. Edit corrections.txt")
    print("2. Add to @underscore_prefixes: for new prefixes")
    print("3. Add 'dumb [term]:dum[term]' for new variables")

if __name__ == "__main__":
    test_programming_corrections()