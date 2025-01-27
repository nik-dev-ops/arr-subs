import os
import json
import pika
import logging
import time
import requests
from whisper_transcription import process_whisper_transcription
from subtitle_translation import translate_srt

logger = logging.getLogger(__name__)

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
WHISPER_URL = "http://whisper:9000/asr?encode=true&task=transcribe&word_timestamps=false&output=srt"
AENEAS_URL = "http://aeneas:5001/sync"
DEFAULT_TARGET_LANGUAGE = os.getenv("DEFAULT_TARGET_LANGUAGE", "eng")

def process_job(channel, method, properties, body):
    try:
        job = json.loads(body.decode("utf-8"))
        job_id = job["job_id"]
        media_type = job["type"]
        file_path = job["file_path"]
        source_language = job["source_language"]

        logger.info(f"Processing job {job_id} ({media_type}): {file_path}")

        # Perform transcription and processing
        result = process_whisper_transcription(file_path, source_language)
        
        if result:
            # Always translate to DEFAULT_TARGET_LANGUAGE
            translated_srt_path = translate_srt(result['synced_srt_path'], DEFAULT_TARGET_LANGUAGE)
            
            if translated_srt_path:
                logger.info(f"Job {job_id}: Translation completed successfully")
            else:
                logger.error(f"Job {job_id}: Translation failed")
        
    except Exception as e:
        logger.error(f"Failed to process message: {str(e)}")
    finally:
        channel.basic_ack(delivery_tag=method.delivery_tag)

def connect_to_rabbitmq():
    while True:
        logger.info("Attempting to connect to RabbitMQ...")
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=RABBITMQ_HOST,
                    heartbeat=600,
                    blocked_connection_timeout=300
                )
            )
            logger.info("Connected to RabbitMQ!")
            return connection
        except pika.exceptions.AMQPConnectionError:
            logger.warning("RabbitMQ is not ready. Retrying in 5 seconds...")
            time.sleep(5)

def main():
    logger.info("Starting the worker...")
    connection = connect_to_rabbitmq()
    channel = connection.channel()
    
    channel.queue_declare(queue="media_jobs", durable=True)
    channel.basic_qos(prefetch_count=1)
    
    channel.basic_consume(queue="media_jobs", on_message_callback=process_job)
    logger.info("Worker is waiting for jobs...")

    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        logger.info("Worker interrupted, shutting down...")
        connection.close()
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        connection.close()

if __name__ == "__main__":
    main()