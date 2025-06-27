import os
import logging
from typing import List

def cleanup_temp_files(directory: str = "temp_uploads") -> List[str]:
    """
    Remove all files in the specified temporary directory.
    Returns a list of cleaned up file paths.
    """
    cleaned_files = []
    try:
        if not os.path.exists(directory):
            os.makedirs(directory)
            return cleaned_files

        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
                    cleaned_files.append(file_path)
                    logging.info(f"Cleaned up temporary file: {filename}")
            except Exception as e:
                logging.error(f"Error cleaning up {filename}: {str(e)}")
                
        return cleaned_files
    except Exception as e:
        logging.error(f"Error during cleanup of directory {directory}: {str(e)}")
        return cleaned_files
