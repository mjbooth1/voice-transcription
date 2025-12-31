"""
Entry point for running transcription client.
Usage: python -m voice-transcription.client
"""

if __name__ == "__main__":
    import sys
    import os
    
    # Add the voice-transcription directory to the Python path
    current_dir = os.path.dirname(__file__)
    sys.path.insert(0, current_dir)
    
    from transcription_client import main
    main()