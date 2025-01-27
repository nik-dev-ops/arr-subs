import os
import requests
import logging
from aeneas_sync import sync_subtitles

logger = logging.getLogger(__name__)

WHISPER_URL = "http://whisper:9000/asr?encode=true&task=transcribe&word_timestamps=false&output=srt"

def process_whisper_transcription(file_path, source_language):
    try:
        logger.info(f"Starting Whisper-ASR transcription...")

        with open(file_path, 'rb') as audio_file:
            files = {'audio_file': (os.path.basename(file_path), audio_file, 'video/x-matroska')}
            response = requests.post(
                WHISPER_URL,
                files=files,
                headers={'accept': 'application/json'},
                timeout=3600
            )

        response.raise_for_status()
        srt_text = response.text

        if not srt_text:
            raise ValueError("Whisper-ASR did not return valid subtitle text.")

        # Create the initial SRT file
        srt_filename = f"{os.path.splitext(file_path)[0]}.{source_language}.srt"
        with open(srt_filename, 'w', encoding="utf-8") as srt_file:
            srt_file.write(srt_text)

        # Sync subtitles
        synced_result = sync_subtitles(file_path, srt_filename, source_language)
        
        return synced_result

    except Exception as e:
        logger.error(f"Transcription error: {str(e)}")
        return None