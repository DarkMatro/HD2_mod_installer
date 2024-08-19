from urllib import request
import logging
import sys
from pathlib import Path

EXE_FILE_NAME = 'HD2_SabreSquadron.exe'

def check_internet_connection() -> None:
    """Check if there is an active internet connection."""
    try:
        request.urlopen('http://google.com', timeout=1)
    except request.URLError:
        msg = "No internet connection."
        print(msg)
        logging.error(msg)
        sys.exit(1)

def check_game_executable():
    """
    Check if the game executable exists in the current directory.

    Raises
    ------
    FileNotFoundError
        If the game executable is not found.
    """
    if not Path(EXE_FILE_NAME).exists():
        print(f"Error: {EXE_FILE_NAME} not found in the current directory.")
        print("Please move this program to the game folder containing the executable.")
        logging.error(f"{EXE_FILE_NAME} not found in the current directory.")
        input("Press any key to exit...")
        sys.exit(1)
