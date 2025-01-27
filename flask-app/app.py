import os
import pika
import uuid
import time
import requests
from flask import Flask, request, jsonify
import logging
import traceback
import json
from radarr import get_movie_details
from sonarr import process_sonarr_webhook
from languages import LANGUAGE_CODES
from logging.handlers import RotatingFileHandler

# Set up structured logging
def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # File handler with rotation
    file_handler = RotatingFileHandler('app.log', maxBytes=1024*1024, backupCount=5)
    file_handler.setLevel(logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

def validate_environment():
    required_vars = ['RADARR_API_KEY', 'RADARR_API_URL', 'RABBITMQ_HOST']
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

def connect_rabbitmq_with_retry(host, max_retries=5, delay=5):
    for attempt in range(max_retries):
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=host,
                    heartbeat=600,
                    blocked_connection_timeout=300
                )
            )
            channel = connection.channel()
            # Declare the queue once at startup
            channel.queue_declare(queue="media_jobs", durable=True)
            return connection, channel
        except pika.exceptions.AMQPConnectionError as e:
            if attempt == max_retries - 1:
                raise
            logging.warning(f"Failed to connect to RabbitMQ (attempt {attempt + 1}/{max_retries}). Retrying in {delay} seconds...")
            time.sleep(delay)

app = Flask(__name__)

# Environment variables
RADARR_API_KEY = os.getenv("RADARR_API_KEY")
RADARR_API_URL = os.getenv("RADARR_API_URL", "http://localhost:7878/api/v3/movie")
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")

# Global RabbitMQ connection and channel
rabbitmq_connection = None
rabbitmq_channel = None

# Initialize the application
def init_app(app):
    global rabbitmq_connection, rabbitmq_channel
    setup_logging()
    validate_environment()
    rabbitmq_connection, rabbitmq_channel = connect_rabbitmq_with_retry(RABBITMQ_HOST)

# Call initialization
init_app(app)

@app.teardown_appcontext
def shutdown(exception=None):
    global rabbitmq_connection
    if rabbitmq_connection and not rabbitmq_connection.is_closed:
        rabbitmq_connection.close()

def publish_to_queue(job):
    global rabbitmq_connection, rabbitmq_channel
    
    try:
        if not rabbitmq_connection or rabbitmq_connection.is_closed:
            rabbitmq_connection, rabbitmq_channel = connect_rabbitmq_with_retry(RABBITMQ_HOST)
        
        rabbitmq_channel.basic_publish(
            exchange="",
            routing_key="media_jobs",
            body=json.dumps(job),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Make message persistent
                correlation_id=str(uuid.uuid4())
            )
        )
        logging.info(f"Job {job['job_id']} added to the queue")
        return True
    except Exception as e:
        logging.error(f"Failed to publish job to RabbitMQ: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return False

@app.route("/webhook", methods=["POST"])
def webhook():
    request_id = str(uuid.uuid4())
    logging.info(f"Processing webhook request {request_id}")
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"message": "Invalid JSON payload"}), 400
            
        job = {}

        # Radarr webhook processing
        if "movie" in data:
            logging.info(f"[{request_id}] Radarr webhook detected")
            tmdb_id = data["movie"].get("tmdbId")
            
            if not tmdb_id or tmdb_id == 0:
                return jsonify({"message": "Invalid or missing tmdbId"}), 400
            
            movie_details = get_movie_details(tmdb_id, RADARR_API_URL, RADARR_API_KEY)
            
            if not movie_details:
                return jsonify({"message": f"Failed to fetch movie details for tmdbId {tmdb_id}"}), 500

            movie_path = movie_details[0]["movieFile"]["path"]
            audio_languages = movie_details[0]["movieFile"].get("languages", [])
            language_codes = [LANGUAGE_CODES.get(lang["name"], "eng") for lang in audio_languages]
            
            job = {
                "type": "radarr",
                "job_id": str(uuid.uuid4()),
                "file_path": movie_path,
                "source_language": language_codes[0] if language_codes else "eng",
                "target_language": data.get("target_language", "eng"),
                "languages": language_codes,
                "request_id": request_id
            }

        # Sonarr webhook processing
        elif "series" in data:
            logging.info(f"[{request_id}] Sonarr webhook detected")
            job = process_sonarr_webhook(data, request_id)
            if not job:
                return jsonify({"message": "Failed to process Sonarr webhook"}), 400

        else:
            return jsonify({"message": "Invalid webhook payload type"}), 400

        # Publish job to RabbitMQ
        if publish_to_queue(job):
            return jsonify({
                "message": f"Job {job['job_id']} added to the queue",
                "request_id": request_id
            }), 202
        else:
            return jsonify({"message": "Failed to queue job"}), 500

    except Exception as e:
        logging.error(f"[{request_id}] Error processing webhook: {str(e)}")
        logging.error(f"[{request_id}] Traceback: {traceback.format_exc()}")
        return jsonify({"message": "Internal server error", "request_id": request_id}), 500

if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=8000, debug=debug_mode)