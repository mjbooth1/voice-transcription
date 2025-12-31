"""
Entry point for running transcription service as a module.
Usage: python -m voice-transcription
"""

if __name__ == "__main__":
    import sys
    import os
    import signal
    
    # Add the voice-transcription directory to the Python path
    current_dir = os.path.dirname(__file__)
    sys.path.insert(0, current_dir)
    
    from transcription_service import TranscriptionService

    def signal_handler(signum, frame):
        """Handle shutdown signals."""
        print("🔴 Received shutdown signal")
        service.stop()
        sys.exit(0)

    # Set up signal handling for clean shutdown
    service = TranscriptionService()
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        service.start_server()
    except KeyboardInterrupt:
        service.stop()
    except Exception as e:
        print(f"❌ Service crashed: {e}")
        service.show_toast(f"❌ Service crashed: {e}")