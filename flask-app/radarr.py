import requests
import logging
import traceback
from typing import Optional, Dict, List, Any
from requests.exceptions import RequestException, HTTPError, Timeout

def get_movie_details(tmdb_id: int, radarr_api_url: str, radarr_api_key: str) -> Optional[List[Dict[str, Any]]]:
    """
    Fetch movie details from Radarr API using TMDb ID.
    
    Args:
        tmdb_id: The TMDb ID of the movie
        radarr_api_url: Base URL for the Radarr API
        radarr_api_key: API key for authentication
        
    Returns:
        Optional[List[Dict[str, Any]]]: Movie details if successful, None if failed
    """
    url = f"{radarr_api_url}?tmdbId={tmdb_id}&excludeLocalCovers=true"
    url = url.strip('"').strip()
    
    logging.debug(f"Requesting movie details from Radarr: {url}")
    
    try:
        response = requests.get(
            url,
            headers={"X-Api-Key": radarr_api_key},
            timeout=30  # Add timeout
        )
        response.raise_for_status()
        
        movie_data = response.json()
        if not movie_data:
            logging.warning(f"No movie data found for TMDb ID: {tmdb_id}")
            return None
            
        return movie_data
        
    except Timeout:
        logging.error(f"Timeout while fetching movie details for TMDb ID: {tmdb_id}")
        return None
    except HTTPError as e:
        logging.error(f"HTTP error occurred while fetching movie details: {e}")
        return None
    except RequestException as e:
        logging.error(f"Request failed: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error while fetching movie details: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return None