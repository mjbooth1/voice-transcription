#!/usr/bin/env python3
"""
Test script for the smart corrections system.
Tests various correction scenarios without needing actual audio.
"""

import os
import sys

# Add the current directory to path so we can import transcription_service
sys.path.insert(0, os.path.dirname(__file__))

from transcription_service import TranscriptionService

def test_corrections():
    """Test the smart corrections functionality with sample text."""

    print("=" * 60)
    print("SMART CORRECTIONS TEST")
    print("=" * 60)

    # Create a transcription service instance
    service = TranscriptionService()

    # Test cases that should trigger corrections
    test_cases = [
        # Name corrections
        "Julian presented the results to the team",
        "Kieran reviewed the analysis yesterday",

        # Technical term corrections
        "The engine showed good performance metrics",
        "We used the bays model for analysis",
        "The ngene application processed the data",

        # @mention conversions
        "at Diane reviewed the quarterly results",
        "Please send this to at Mike and at Sarah",
        "at Marnel will lead the next phase",
        "The feedback from at Ernest was positive",

        # Mixed corrections
        "at Julian used the engine to run bays analysis with Kieran",

        # Capitalization preservation
        "We ran conjoint analysis using maxdiff methodology",
        "The hierarchical bayes model needs ngene updates",

        # Edge cases
        "The car engine needs repair",  # Should NOT change to NGENE
        "At the beginning of the meeting",  # Should NOT become @the

        # No corrections needed
        "This is normal text with no corrections needed",
    ]

    print(f"Testing {len(test_cases)} correction scenarios...\n")

    for i, test_text in enumerate(test_cases, 1):
        print(f"Test {i}:")
        print(f"  Input:  '{test_text}'")

        try:
            corrected = service.apply_smart_corrections(test_text)
            print(f"  Output: '{corrected}'")

            if corrected != test_text:
                print(f"  [CORRECTED] Applied changes")
            else:
                print(f"  [NO CHANGE] As expected or no matches found")

        except Exception as e:
            print(f"  [ERROR] {e}")

        print()

    print("=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
    print("\nTo modify corrections:")
    print("1. Edit voice-transcription/corrections.txt")
    print("2. Add new 'wrong:right' pairs")
    print("3. Update @names and @terms lists")
    print("4. Changes apply immediately (no restart needed)")
    print("\nTo disable corrections:")
    print("1. Set ENABLE_CORRECTIONS = False in transcription_service.py")
    print("2. Or comment out the corrections block")
    print("3. Or rename/delete corrections.txt")

if __name__ == "__main__":
    test_corrections()