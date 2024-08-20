# pylint: disable=logging-fstring-interpolation

import logging
import re

import aiohttp
from aiohttp import ClientTimeout

RAW_BASE_URL = 'https://raw.githubusercontent.com/ehylla93/had2-cmp/main'
VERSION_FILE_URL = f'{RAW_BASE_URL}/README.md'


async def fetch_cmp_version() -> str | None:
    """
    Asynchronously fetch the CMP version from the GitHub repository.

    Returns
    -------
    str
        The version string from the repository.
    """
    try:
        async with aiohttp.ClientSession(timeout=ClientTimeout(10)) as session:
            async with session.get(VERSION_FILE_URL) as response:
                logging.info(response)
                response.raise_for_status()
                text = await response.text()
                version_match = re.search(r'v([\d\.]+)', text)
                if version_match:
                    return version_match.group(1)
                logging.error("Version information not found in the latest commit message.")
                return None
    except Exception as e:
        logging.error(f"Error fetching version: {e}")
        raise
