import requests
import logging

logger = logging.getLogger(__name__)

AENEAS_URL = "http://aeneas:5001/sync"

def sync_subtitles(video_path, srt_path, language):
    try:
        logger.info(f"Starting Aeneas sync...")
        aeneas_response = requests.post(
            AENEAS_URL,
            json={
                "video_path": video_path,
                "srt_path": srt_path,
                "language": language
            }
        )
        aeneas_response.raise_for_status()

        synced_srt_path = aeneas_response.json().get("synced_srt", "")
        if not synced_srt_path:
            raise ValueError("Aeneas did not return a valid synced SRT.")
        
        logger.info(f"Sync completed. Synced SRT at {synced_srt_path}")
        return {"synced_srt_path": synced_srt_path}

    except Exception as e:
        logger.error(f"Subtitle sync error: {str(e)}")
        return None