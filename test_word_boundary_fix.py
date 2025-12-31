#!/usr/bin/env python3
"""
Test script to verify the word boundary fix for @mentions.
Tests the specific cases reported by the user.
"""

import os
import sys

# Add the current directory to path so we can import transcription_service
sys.path.insert(0, os.path.dirname(__file__))

from transcription_service import TranscriptionService

def test_word_boundary_fix():
    """Test that word boundaries are properly respected in @mention conversion."""

    print("=" * 80)
    print("WORD BOUNDARY FIX TEST")
    print("=" * 80)
    print()

    # Create a transcription service instance
    service = TranscriptionService()

    # Test cases - (input, expected_output, description)
    test_cases = [
        # Cases that should NOT trigger @mention (the bug we're fixing)
        ("what Rob said", "what Rob said", "Bug fix: 'what' contains 'at' but shouldn't trigger"),
        ("that will", "that will", "Bug fix: 'that' contains 'at' but shouldn't trigger"),
        ("whatever Mike wants", "whatever Mike wants", "Edge case: 'whatever' contains 'at'"),
        ("I sat with Joe", "I sat with Joe", "Edge case: 'sat' ends with 'at'"),
        ("at that time", "at that time", "Edge case: 'at that' shouldn't trigger for 'that'"),

        # Cases that SHOULD trigger @mention (correct behavior)
        ("at Rob said", "@Rob said", "Correct: 'at Rob' at start of sentence"),
        ("I'll at Rob tomorrow", "I'll @Rob tomorrow", "Correct: 'at Rob' after punctuation"),
        ("call at Mike", "call @Mike", "Correct: 'at Mike' after space"),
        ("at Will and at Rob", "@Will and @Rob", "Correct: multiple @mentions"),
        ("send to at Mike, at Joe H", "send to @Mike, @Joe H", "Correct: comma-separated"),

        # Mixed corrections and @mentions
        ("at Julian reviewed the bays model", "@Julien reviewed the Bayes model",
         "Correct: Name correction + @mention + technical term"),
        ("at Casey helped with ngene", "@K.C. helped with NGENE",
         "Correct: Complex name correction + @mention + technical term"),
    ]

    total_tests = len(test_cases)
    passed_tests = 0
    failed_tests = []

    print(f"Running {total_tests} test cases...\n")

    for i, (input_text, expected, description) in enumerate(test_cases, 1):
        result = service.apply_smart_corrections(input_text)

        if result == expected:
            passed_tests += 1
            status = "PASS"
        else:
            failed_tests.append((input_text, expected, result, description))
            status = "FAIL"

        print(f"{status} Test {i}: {description}")
        print(f"  Input:    '{input_text}'")
        print(f"  Expected: '{expected}'")
        print(f"  Got:      '{result}'")
        print()

    # Summary
    print("=" * 80)
    print("TEST RESULTS")
    print("=" * 80)
    print(f"Total tests:  {total_tests}")
    print(f"Passed:       {passed_tests}")
    print(f"Failed:       {len(failed_tests)}")
    print(f"Success rate: {passed_tests/total_tests*100:.1f}%")
    print()

    if failed_tests:
        print("FAILED TESTS:")
        print("-" * 80)
        for input_text, expected, actual, description in failed_tests:
            print(f"Description: {description}")
            print(f"  Input:    '{input_text}'")
            print(f"  Expected: '{expected}'")
            print(f"  Got:      '{actual}'")
            print()
        return False
    else:
        print("SUCCESS! ALL TESTS PASSED!")
        print("The word boundary fix is working correctly.")
        return True

if __name__ == "__main__":
    success = test_word_boundary_fix()
    sys.exit(0 if success else 1)
