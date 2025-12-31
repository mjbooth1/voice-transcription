# Quick test of optimized settings
import time
import numpy as np
from faster_whisper import WhisperModel
from scipy.io.wavfile import write
import tempfile
import os

def create_test_audio(duration_seconds=30, sample_rate=16000):
    """Create test audio data."""
    samples = int(duration_seconds * sample_rate)
    t = np.linspace(0, duration_seconds, samples, False)
    
    # Create a simple sine wave with some noise
    audio = np.sin(2 * np.pi * 440 * t) * 0.3
    audio += np.random.normal(0, 0.05, samples)
    
    return audio.astype(np.float32)

def test_optimized_model():
    print("=== Testing Optimized Settings ===")
    
    # Load model with optimized settings
    print("Loading optimized model...")
    try:
        model = WhisperModel(
            "turbo",
            device="cuda",
            compute_type="float16",  # New optimization
            num_workers=4,           # New optimization  
            cpu_threads=12           # New optimization for 24-core CPU
        )
        print("✅ Model loaded successfully")
    except Exception as e:
        print(f"❌ Model loading failed: {e}")
        return
    
    # Test 30-second audio
    print("\nTesting 30-second audio transcription...")
    audio_data = create_test_audio(30)
    
    # Save to temp file
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
        audio_int16 = np.int16(audio_data * 32767)
        write(tmp_file.name, 16000, audio_int16)
        temp_filename = tmp_file.name
    
    try:
        # Transcribe with optimizations
        start_time = time.perf_counter()
        segments, info = model.transcribe(
            temp_filename,
            beam_size=1,
            vad_filter=False,
            without_timestamps=True  # New optimization
        )
        # Consume the generator
        text_parts = [segment.text for segment in segments]
        elapsed = time.perf_counter() - start_time
        
        # Results
        real_time_factor = 30 / elapsed
        
        print(f"✅ Transcription complete:")
        print(f"   Processing time: {elapsed:.2f}s")
        print(f"   Real-time factor: {real_time_factor:.1f}x")
        
        # Compare to previous baseline (0.53s for 30s audio)
        previous_time = 0.53
        improvement = (previous_time / elapsed - 1) * 100
        
        print(f"\nComparison to previous performance:")
        print(f"   Previous: {previous_time}s (56.4x real-time)")
        print(f"   Current: {elapsed:.2f}s ({real_time_factor:.1f}x real-time)")
        print(f"   Improvement: {improvement:.1f}% faster")
        
        if improvement > 20:
            print("🚀 EXCELLENT improvement!")
        elif improvement > 10:
            print("✅ Good improvement!")
        elif improvement > 0:
            print("📈 Slight improvement")
        else:
            print("⚠️ Performance similar to before")
            
    finally:
        # Clean up
        try:
            os.remove(temp_filename)
        except:
            pass

if __name__ == "__main__":
    test_optimized_model()