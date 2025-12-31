#!/usr/bin/env python3
"""
Test script for all company names and misspellings with @mention conversion.
Tests every name from the company list with various capitalizations.
"""

import os
import sys

# Add the current directory to path so we can import transcription_service
sys.path.insert(0, os.path.dirname(__file__))

from transcription_service import TranscriptionService

def test_company_names():
    """Test @mention conversion for all company names and misspellings."""

    print("=" * 80)
    print("COMPANY NAMES @MENTION TEST")
    print("=" * 80)

    # Create a transcription service instance
    service = TranscriptionService()

    # All company names from the @names list
    company_names = [
        'Diane', 'Meg', 'Liz', 'Marnel', 'Ernest', 'Rob', 'Athena', 'Meredith',
        'Amy', 'Julien', 'Kieron', 'Will', 'Jin', 'K.C.', 'Andrew', 'Joe H',
        'Mary', 'Jackie', 'Andi', 'Chelsea', 'Hannah', 'Annelise', 'James',
        'Isaac', 'Carly', 'Sofia', 'Mariah', 'Larissa', 'Meaghan', 'Olivia',
        'Joe C', 'Alhera', 'Elaine', 'Stephanie', 'Pamela', 'Mike'
    ]

    # Common misspellings that should be corrected
    misspellings = [
        ('Casey', 'K.C.'),      # Casey -> K.C.
        ('KC', 'K.C.'),         # KC -> K.C.
        ('Marry', 'Mary'),      # Marry -> Mary
        ('Andy', 'Andi'),       # Andy -> Andi
        ('Annalise', 'Annelise'), # Annalise -> Annelise
        ('Sophia', 'Sofia'),    # Sophia -> Sofia
        ('Megan', 'Meaghan'),   # Megan -> Meaghan
        ('Al-Har', 'Alhera'),   # Al-Har -> Alhera
        ('Al-Hira', 'Alhera'),  # Al-Hira -> Alhera
        ('Alhara', 'Alhera'),   # Alhara -> Alhera
        ('Julian', 'Julien'),   # Julian -> Julien
        ('Kieran', 'Kieron'),   # Kieran -> Kieron
    ]

    total_tests = 0
    passed_tests = 0
    failed_tests = []

    print(f"Testing {len(company_names)} company names with 4 variations each...")
    print(f"Testing {len(misspellings)} misspellings...")
    print()

    # Test all company names with various capitalizations
    for name in company_names:
        print(f"Testing: {name}")

        test_cases = [
            (f'at {name}', f'@{name}'),
            (f'At {name}', f'@{name}'),
            (f'at {name.lower()}', f'@{name}'),
            (f'AT {name.upper()}', f'@{name}'),
        ]

        for input_text, expected in test_cases:
            total_tests += 1
            result = service.apply_smart_corrections(input_text)

            if result == expected:
                passed_tests += 1
                print(f"  PASS {input_text:25} -> {result}")
            else:
                failed_tests.append((input_text, expected, result))
                print(f"  FAIL {input_text:25} -> {result:25} (expected: {expected})")
        print()

    # Test misspellings with @mention conversion
    print("=" * 80)
    print("TESTING MISSPELLINGS")
    print("=" * 80)

    for wrong_name, correct_name in misspellings:
        print(f"Testing misspelling: {wrong_name} -> {correct_name}")

        test_cases = [
            (f'at {wrong_name}', f'@{correct_name}'),
            (f'At {wrong_name}', f'@{correct_name}'),
            (f'at {wrong_name.lower()}', f'@{correct_name}'),
        ]

        for input_text, expected in test_cases:
            total_tests += 1
            result = service.apply_smart_corrections(input_text)

            if result == expected:
                passed_tests += 1
                print(f"  PASS {input_text:25} -> {result}")
            else:
                failed_tests.append((input_text, expected, result))
                print(f"  FAIL {input_text:25} -> {result:25} (expected: {expected})")
        print()

    # Test some complex sentences
    print("=" * 80)
    print("TESTING COMPLEX SENTENCES")
    print("=" * 80)

    complex_tests = [
        ('at Mike and at Joe H reviewed the data', '@Mike and @Joe H reviewed the data'),
        ('At Casey will work with at Andi on this', '@K.C. will work with @Andi on this'),
        ('Please send this at K.C. and at Joe C', 'Please send this @K.C. and @Joe C'),
        ('at Marry reviewed the bays model for Julien', '@Mary reviewed the Bayes model for Julien'),
        ('At Sophia from ngene team helped at Andy', '@Sofia from NGENE team helped @Andi'),
    ]

    for input_text, expected in complex_tests:
        total_tests += 1
        result = service.apply_smart_corrections(input_text)

        if result == expected:
            passed_tests += 1
            print(f"PASS {input_text}")
            print(f"  -> {result}")
        else:
            failed_tests.append((input_text, expected, result))
            print(f"FAIL {input_text}")
            print(f"  -> {result}")
            print(f"  Expected: {expected}")
        print()

    # Final results
    print("=" * 80)
    print("TEST RESULTS")
    print("=" * 80)
    print(f"Total tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {len(failed_tests)}")
    print(f"Success rate: {passed_tests/total_tests*100:.1f}%")

    if failed_tests:
        print("\nFAILED TESTS:")
        print("-" * 80)
        for input_text, expected, actual in failed_tests:
            print(f"Input:    {input_text}")
            print(f"Expected: {expected}")
            print(f"Actual:   {actual}")
            print()
    else:
        print("\nALL TESTS PASSED!")
        print("Company @mention system is working perfectly!")

    print("\nTo add new names:")
    print("1. Add to @names list in corrections.txt")
    print("2. Add any misspellings as 'wrong:right' corrections")
    print("3. Run this test again to verify")

if __name__ == "__main__":
    test_company_names()