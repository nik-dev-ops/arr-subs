import uuid
import logging
from typing import Optional, Dict, Any

def process_sonarr_webhook(data: Dict[str, Any], request_id: str) -> Optional[Dict[str, Any]]:
    """
    Process webhook data from Sonarr.
    
    Args:
        data: The webhook payload from Sonarr
        request_id: Unique identifier for the request
        
    Returns:
        Optional[Dict[str, Any]]: Processed job data if successful, None if failed
    """
    try:
        # Validate required fields
        if "episodeFile" not in data:
            logging.error(f"[{request_id}] Missing episodeFile in Sonarr webhook data")
            return None
            
        episode_file = data["episodeFile"]
        if "path" not in episode_file:
            logging.error(f"[{request_id}] Missing path in episodeFile data")
            return None
            
        episode_path = episode_file["path"]
        audio_languages = episode_file.get("audioLanguages", [])
        
        # Get source and target languages
        source_language = audio_languages[0] if audio_languages else "eng"
        target_language = data.get("target_language", "eng")
        
        # Create job
        job = {
            "type": "sonarr",
            "job_id": str(uuid.uuid4()),
            "file_path": episode_path,
            "source_language": source_language,
            "target_language": target_language,
            "request_id": request_id,
            "series_name": data.get("series", {}).get("title", "Unknown Series"),
            "episode_info": {
                "season": data.get("episodes", [{}])[0].get("seasonNumber"),
                "episode": data.get("episodes", [{}])[0].get("episodeNumber")
            }
        }
        
        logging.info(f"[{request_id}] Successfully processed Sonarr webhook for {job['series_name']}")
        return job
        
    except Exception as e:
        logging.error(f"[{request_id}] Error processing Sonarr webhook: {str(e)}")
        logging.error(f"[{request_id}] Traceback: {traceback.format_exc()}")
        return None