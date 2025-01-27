import os
import logging
from logging.handlers import RotatingFileHandler
from rabbitmq_handler import connect_to_rabbitmq, main as rabbitmq_main

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler('worker.log', maxBytes=10485760, backupCount=5),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    rabbitmq_main()