from flask import Flask, request, jsonify
import os
import subprocess
import sys
import re
import logging
from logging.handlers import RotatingFileHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler('aeneas.log', maxBytes=10485760, backupCount=5),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route("/health", methods=["GET"])
def health_check():
    """
    Health check endpoint to verify service is running.
    """
    try:
        # Check if required tools are available
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        subprocess.run(["python3", "-m", "aeneas.diagnostics"], capture_output=True, check=True)
        return jsonify({"status": "healthy"}), 200
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 500

def clean_srt(subtitle_path):
    """
    Cleans SRT file by removing redundant subtitle entries and keeping only complete ones.
    Uses the second timestamp occurrence for each subtitle block.
    """
    try:
        with open(subtitle_path, 'r', encoding='utf-8') as file:
            content = file.read().strip()
        # Split into subtitle blocks
        blocks = content.split('\n\n')
        cleaned_blocks = []
        subtitle_count = 1
        # Regular expressions for matching
        timestamp_pattern = re.compile(r'^\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}$')
        number_pattern = re.compile(r'^\d+$')

        for block in blocks:
            lines = block.split('\n')
            cleaned_lines = []
            text_lines = []
            timestamps = []
            
            for line in lines:
                line = line.strip()
                if timestamp_pattern.match(line):
                    timestamps.append(line)
                elif number_pattern.match(line):
                    if not cleaned_lines:  # Only add number if it's the first line
                        cleaned_lines.append(str(subtitle_count))
                else:
                    text_lines.append(line)

            # Use the second timestamp if available
            if len(timestamps) >= 2:
                cleaned_lines.append(timestamps[1])
            elif timestamps:  # Fallback to first timestamp if only one exists
                cleaned_lines.append(timestamps[0])

            if timestamps and text_lines:  # Only keep blocks with both timestamp and text
                cleaned_lines.extend(text_lines)
                cleaned_blocks.append('\n'.join(cleaned_lines))
                subtitle_count += 1

        # Write the cleaned content
        with open(subtitle_path, 'w', encoding='utf-8') as file:
            file.write('\n\n'.join(cleaned_blocks))
            file.write('\n')  # Add final newline
        
        logger.info(f"Cleaned subtitle saved to {subtitle_path}")
        return True
    except Exception as e:
        logger.error(f"Error during subtitle cleaning: {e}")
        return False

@app.route("/sync", methods=["POST"])
def sync_subtitles():
    """
    Synchronize subtitles using Aeneas.
    """
    data = request.json

    # Input validation
    if "video_path" not in data or "srt_path" not in data or "language" not in data:
        return jsonify({"error": "Missing video_path, srt_path, or language in request"}), 400

    video_path = data["video_path"]
    srt_path = data["srt_path"]
    source_language = data["language"]

    if not os.path.exists(video_path) or not os.path.exists(srt_path):
        return jsonify({"error": "File does not exist"}), 400

    # Step 1: Extract audio from the video file
    audio_file_path = f"{video_path.rsplit('.', 1)[0]}.mp3"
    logger.info(f"Extracting audio from {video_path} to {audio_file_path}")

    try:
        subprocess.run([
            "ffmpeg", "-i", video_path, "-vn", "-acodec", "libmp3lame",
            "-ab", "192k", "-ar", "44100", "-y", audio_file_path
        ], check=True)
        logger.info(f"Audio file created at: {audio_file_path}")
    except subprocess.CalledProcessError as e:
        return jsonify({"error": f"Error during audio extraction: {e}"}), 500

    # Step 2: Sync the subtitles using Aeneas
    output_subtitle_path = srt_path.replace(".srt", "_aligned.srt")
    try:
        command = [
            "python3", "-m", "aeneas.tools.execute_task",
            audio_file_path, srt_path,
            f"task_language={source_language}|os_task_file_format=srt|is_text_type=subtitles",
            output_subtitle_path
        ]
        subprocess.run(command, check=True)
        logger.info(f"Subtitle timings corrected and saved: {output_subtitle_path}")

        # Step 3: Clean the synced subtitles
        if clean_srt(output_subtitle_path):
            logger.info("Successfully cleaned the synchronized subtitles")
        else:
            logger.warning("Subtitle cleaning process encountered issues")

        # Step 4: Replace original subtitle file with the aligned version
        os.rename(output_subtitle_path, srt_path)
        logger.info(f"Original subtitle file replaced with aligned version: {srt_path}")
    except subprocess.CalledProcessError as e:
        return jsonify({"error": f"Error during subtitle processing: {e}"}), 500
    finally:
        if os.path.exists(audio_file_path):
            os.remove(audio_file_path)
            logger.info(f"Temporary audio file removed: {audio_file_path}")

    logger.info("Processing completed successfully.")
    return jsonify({"synced_srt": srt_path}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)