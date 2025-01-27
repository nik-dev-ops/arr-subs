import os
import logging
import time
import traceback
from googletrans import Translator
from google_lang import GOOGLE_LANG_CODES

logger = logging.getLogger(__name__)
translator = Translator()

DEFAULT_TARGET_LANGUAGE = os.getenv("DEFAULT_TARGET_LANGUAGE", "eng")

def translate_srt(input_srt_path, target_language=None):
    try:
        target_language = target_language or DEFAULT_TARGET_LANGUAGE
        google_lang = GOOGLE_LANG_CODES.get(target_language.lower())
        
        if not google_lang:
            logger.error(f"No Google Translate language code found for {target_language}")
            return None
            
        logger.info(f"Starting translation to: {target_language} (Google code: {google_lang})")
        
        if not os.path.exists(input_srt_path):
            logger.error(f"Input SRT file not found: {input_srt_path}")
            return None
        
        base_path = input_srt_path.rsplit('.', 2)[0]
        output_srt_path = f"{base_path}.{target_language}.srt"
        logger.info(f"Will save translated file to: {output_srt_path}")

        try:
            with open(input_srt_path, "r", encoding="utf-8") as file:
                lines = file.readlines()
        except Exception as e:
            logger.error(f"Error reading input SRT file: {str(e)}")
            return None

        total_lines = len(lines)
        logger.info(f"Total lines to process: {total_lines}")

        translated_lines = []
        buffer = []
        current_subtitle = 1

        for line_num, line in enumerate(lines, 1):
            try:
                stripped_line = line.strip()
                if stripped_line == "":
                    if buffer:
                        original_text = " ".join(buffer)
                        logger.info(f"Translating subtitle {current_subtitle} of {total_lines//4}")
                        
                        # Add retry logic for translation
                        max_retries = 3
                        for attempt in range(max_retries):
                            try:
                                translated_text = translator.translate(
                                    original_text, 
                                    dest=google_lang,
                                    timeout=10
                                ).text
                                translated_lines.append(translated_text)
                                break
                            except Exception as e:
                                if attempt == max_retries - 1:
                                    raise
                                logger.warning(f"Translation attempt {attempt + 1} failed, retrying...")
                                time.sleep(2)
                        
                        buffer = []
                        current_subtitle += 1
                    translated_lines.append("")
                elif stripped_line.isdigit():
                    translated_lines.append(stripped_line)
                elif "-->" in stripped_line:
                    translated_lines.append(stripped_line)
                else:
                    buffer.append(stripped_line)

                # Write progress periodically
                if line_num % 100 == 0:
                    logger.info(f"Processed {line_num}/{total_lines} lines")

            except Exception as e:
                logger.error(f"Error translating line {line_num}: {str(e)}")
                logger.error(f"Line content: {stripped_line}")
                raise

        logger.info("Writing translated subtitles to file...")
        with open(output_srt_path, "w", encoding="utf-8") as file:
            file.write("\n".join(translated_lines))

        logger.info(f"Translation completed successfully: {output_srt_path}")
        return output_srt_path

    except Exception as e:
        logger.error(f"Translation failed with error: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None