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


def delete_empty_folders(folder_path):
    """
    Recursively deletes empty folders in a directory, including nested empty folders.
    If the top-level folder is empty after processing, it will also be deleted.

    Parameters
    ----------
    folder_path : str or pathlib.Path
        to the top-level directory to check and clean.

    Returns
    -------
    None

    Raises
    ------
    ValueError
        If the provided path is not a directory.
    """
    folder = Path(folder_path)
    if not folder.is_dir():
        raise ValueError(f"{folder_path} is not a valid directory.")

    # Recursively check all subdirectories
    for item in folder.iterdir():
        if item.is_dir():
            # Recursively clean subdirectory
            delete_empty_folders(item)

    # Delete folder if it's empty after cleaning subdirectories
    if not any(folder.iterdir()):  # Check if the folder is now empty
        folder.rmdir()  # Delete the empty folder
