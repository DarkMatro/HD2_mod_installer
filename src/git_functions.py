import hashlib
import logging
import os
import pygit2


def calculate_sha1(file_path):
    """
    Calculate the SHA1 hash of a file using pygit2.

    Parameters
    ----------
    file_path : str
        The path to the file.

    Returns
    -------
    str
        The SHA1 hash of the file in hexadecimal format.

    >>> calculate_sha1('../Maps/!dkola02.bmp')
    '4f0f4027dfb9d06142a6c6852d8197fbb0b22a46'
    """
    # Ensure the file exists before trying to read
    if not os.path.isfile(file_path):
        return None

    try:
        # Use pygit2 to compute the SHA1
        with open(file_path, 'rb') as f:
            # Read the file content
            data = f.read()
            # Compute SHA1 hash
            sha1 = pygit2.hash(data)
    except Exception as e:
        logging.error(f"Error reading file {file_path}: {e}")
        return None  # Return None if there was an error

    return str(sha1)
