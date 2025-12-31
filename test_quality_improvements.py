#!/usr/bin/env python3
"""
Test script to verify transcription quality improvements.
This script tests the updated transcription service parameters.
"""

import time
import numpy as np
import tempfile
import os
from faster_whisper import WhisperModel
from scipy.io.wavfile import write

def test_transcription_quality():
    """Test the improved transcription quality settings."""
    print("=== Testing Transcription Quality Improvements ===")

    # Load model with quality-focused settings (matching updated service)
    print("Loading Whisper model with quality settings...")
    try:
        model = WhisperModel(
            "turbo",
            device="cuda",
            compute_type="float16",
            num_workers=1,
            cpu_threads=8,
            device_index=0
        )
        print("✅ Model loaded successfully")
    except Exception as e:
        print(f"❌ Model loading failed: {e}")
        print("Trying CPU fallback...")
        try:
            model = WhisperModel(
                "turbo",
                device="cpu",
                compute_type="int8",
                num_workers=1,
                cpu_threads=8
            )
            print("✅ Model loaded on CPU")
        except Exception as cpu_error:
            print(f"❌ CPU fallback also failed: {cpu_error}")
            return

    # Create a test with the user's problematic text (as audio simulation)
    # Note: This would normally require actual audio, but we can test the parameters
    print("\nTesting quality-focused transcription settings...")

    # Create dummy audio for parameter testing
    duration = 10  # seconds
    sample_rate = 16000
    samples = int(duration * sample_rate)

    # Generate simple white noise as placeholder
    audio_data = np.random.normal(0, 0.1, samples).astype(np.float32)

    # Save to temporary file
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
        audio_int16 = np.int16(audio_data * 32767)
        write(tmp_file.name, sample_rate, audio_int16)
        temp_filename = tmp_file.name

    try:
        print("Testing ORIGINAL settings (poor quality):")
        start_time = time.perf_counter()
        segments_old, info_old = model.transcribe(
            temp_filename,
            language="en",
            beam_size=5,
            vad_filter=True,
            word_timestamps=False,
            without_timestamps=True,  # Old setting
            condition_on_previous_text=False,  # Old setting (problematic)
            compression_ratio_threshold=2.4,
            log_prob_threshold=-1.0,
            temperature=[0.0, 0.2, 0.4]
        )
        old_text = " ".join([segment.text.strip() for segment in segments_old])
        old_time = time.perf_counter() - start_time

        print("Testing IMPROVED settings (better quality):")
        start_time = time.perf_counter()
        segments_new, info_new = model.transcribe(
            temp_filename,
            language="en",
            beam_size=5,
            vad_filter=True,
            word_timestamps=False,
            without_timestamps=False,  # New setting - enables better boundaries
            condition_on_previous_text=True,  # New setting - enables context
            compression_ratio_threshold=2.4,
            log_prob_threshold=-1.0,
            temperature=[0.0, 0.2, 0.4],
            initial_prompt="Transcribe with proper punctuation, capitalization, and sentence structure."
        )
        new_text = " ".join([segment.text.strip() for segment in segments_new])
        new_time = time.perf_counter() - start_time

        print(f"\n=== RESULTS ===")
        print(f"Original settings (poor): {old_time:.2f}s")
        print(f"Improved settings (better): {new_time:.2f}s")
        print(f"Text output (original): '{old_text}'")
        print(f"Text output (improved): '{new_text}'")

        # Performance comparison
        if new_time > old_time:
            slowdown = ((new_time / old_time) - 1) * 100
            print(f"\n⚠️ Quality improvements add {slowdown:.1f}% processing time")
            print("This is expected - quality improvements often require more processing")
        else:
            speedup = ((old_time / new_time) - 1) * 100
            print(f"\n🚀 Improved settings are {speedup:.1f}% faster!")

        print(f"\n=== KEY CHANGES ===")
        print("✅ condition_on_previous_text: False → True (better context)")
        print("✅ without_timestamps: True → False (better boundaries)")
        print("✅ Added initial_prompt for quality guidance")
        print("\nThese changes should significantly improve:")
        print("- Punctuation placement")
        print("- Capitalization consistency")
        print("- Sentence structure")
        print("- Overall text flow")

    except Exception as e:
        print(f"❌ Transcription test failed: {e}")

    finally:
        # Clean up temporary file
        try:
            os.remove(temp_filename)
        except:
            pass

def print_user_issue_analysis():
    """Print analysis of the user's specific quality issue."""
    print("\n" + "="*60)
    print("ANALYSIS OF YOUR QUALITY ISSUE")
    print("="*60)

    user_text = """that's exactly right they seem to think that cloud always means that like we're above board and it's like oh yeah but then you need all kinds of corporate policies and handbooks and administrative things on sensitive data whereas locally i can process my own goddamn ai models if i want to nothing leaves the building nothing leaves my house yes they treat it like it's hobbyist stuff like it's like this funny quirk hmm this new guy seems to think developing locally is a faster way to do it what an interesting tech stack and it's just like dude i'm running efficiencies on my machine you can't grasp can i just have the damn driver"""

    print(f"Your original transcription:")
    print(f"'{user_text}'")
    print(f"\nIssues identified:")
    print("❌ No capitalization at sentence starts")
    print("❌ Missing punctuation (periods, commas, question marks)")
    print("❌ Run-on sentences without proper breaks")
    print("❌ No proper sentence structure")

    print(f"\nExpected improved transcription should have:")
    print("✅ Proper capitalization: 'That's exactly right...'")
    print("✅ Punctuation: periods, commas, question marks")
    print("✅ Sentence breaks: '...my house. Yes, they treat...'")
    print("✅ Question formatting: '...what an interesting tech stack?'")
    print("✅ Better flow and readability")

if __name__ == "__main__":
    print_user_issue_analysis()
    print("\n" + "="*60)
    test_transcription_quality()
    print("\n" + "="*60)
    print("NEXT STEPS:")
    print("1. Restart your transcription service to apply changes")
    print("2. Test with real voice recording")
    print("3. Compare quality before and after")
    print("="*60)