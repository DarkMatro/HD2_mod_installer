# pylint: disable=logging-fstring-interpolation

import ctypes
import json
import logging
import os
import re
import sys
from pathlib import Path
import aiohttp
from tqdm import tqdm
from aiohttp import ClientTimeout

LOCAL_VERSION_FILE = 'local_version.json'
LATEST_VERSION = 'v0.0.3'
REPO_API_URL = "https://api.github.com/repos/DarkMatro/HD2_mod_installer"
RAW_BASE_URL_CMP = 'https://raw.githubusercontent.com/ehylla93/had2-cmp/main'
REPO_API_URL_MAX = "https://api.github.com/repos/DarkMatro/Texture-and-Sounds-mods-by-Max"
VERSION_FILE_URL_CMP = f'{RAW_BASE_URL_CMP}/README.md'


def get_local_version(v_type: str = 'CMP') -> str:
    """
    Load the local version of CMP from a file.

    Parameters
    -------
    v_type: str
        'self' or 'CMP'

    Returns
    -------
    str or None
        The local version string if the file exists, otherwise None.
    """
    _check_version_file()
    with open(LOCAL_VERSION_FILE, encoding="utf-8") as f:
        settings = json.load(f)
    return settings[v_type] if v_type in settings else None


def save_local_version(version: str | None, v_type: str = 'CMP'):
    """
    Save the local version of CMP to a file.

    Parameters
    ----------
    version : str | None
        The version string to save.

    v_type: str
        'self' or 'CMP'
    """
    with open(LOCAL_VERSION_FILE, 'r+', encoding="utf-8") as f:
        data = json.load(f)
        data[v_type] = version
        f.seek(0)
        json.dump(data, f)
        f.truncate()


def _check_version_file() -> None:
    """
    Check that version file exists. If it is not - create new.
    """
    if Path(LOCAL_VERSION_FILE).exists():
        return
    with open(LOCAL_VERSION_FILE, 'w', encoding="utf-8") as f:
        json.dump(_standard_version(), f)


def _standard_version() -> dict:
    """
    Setting to create new versions file if it's missing.
    """
    return {'self': LATEST_VERSION, 'CMP': None, 'Mods by Max': None}


async def check_latest_version():
    """
    Check actual version and if it's not equal - update.
    """
    latest_version, download_url = await fetch_self_actual_version()
    if latest_version is None or download_url is None:
        return
    local_version = get_local_version('self')
    if local_version is None or local_version != latest_version:
        await self_update(latest_version, download_url)
    else:
        print(f"Program version is actual {latest_version}...")
        logging.info(f"Program version is actual {latest_version}...")


async def fetch_self_actual_version() -> tuple:
    """
    Fetch the latest version tag and download URL for mod_installer.exe from GitHub.

    Returns:
    --------
    tuple: (latest_version, download_url)
    """
    async with aiohttp.ClientSession() as session:
        url = f"{REPO_API_URL}/releases/latest"
        async with session.get(url) as response:
            if response.status == 200:
                release_data = await response.json()
                latest_version = release_data['tag_name']
                assets = release_data.get('assets', [])

                download_url = None
                for asset in assets:
                    if asset['name'] == 'mod_installer.exe':
                        download_url = asset['browser_download_url']
                        break
                if not download_url:
                    logging.error("mod_installer.exe not found in the latest release assets.")
                    return None, None
                return latest_version, download_url
            logging.error(f"Failed to fetch the latest version. Status code: {response.status}")
            return None, None


async def self_update(latest_version: str, download_url: str) -> None:
    """
    Download latest version from program repository and install instead current

    Parameters
    -------
    latest_version: str
        like v0.0.1

    download_url: str
        download URL for mod_installer.exe from GitHub.
    """
    print(f"Updating to version {latest_version}...")
    logging.info(f"Updating to version {latest_version}...")

    temp_exe_path = os.path.join(os.getcwd(), "mod_installer_new.exe")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(download_url) as response:
                response.raise_for_status()
                total_size = int(response.headers.get('content-length', 0))
                with tqdm(total=total_size, unit='B', unit_scale=True, desc=temp_exe_path,
                          dynamic_ncols=True) as pbar:
                    with open(temp_exe_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(1024):
                            f.write(chunk)
                            pbar.update(len(chunk))

        save_local_version(latest_version, 'self')

        # Запускаем скрипт замены и обновления
        bat_script = f"""
        @echo off
        timeout /t 2 /nobreak > nul
        move /y "{temp_exe_path}" "{sys.argv[0]}"
        timeout /t 2 /nobreak > nul
        start "" "{sys.argv[0]}"
        timeout /t 2 /nobreak > nul
        del "%~f0" & exit
        """
        bat_path = os.path.join(os.getcwd(), "update.bat")
        with open(bat_path, "w", encoding='utf-8') as bat_file:
            bat_file.write(bat_script)

        # Запуск update.bat с правами администратора
        shell32 = ctypes.windll.shell32
        ret = shell32.ShellExecuteW(None, "runas", bat_path, None, None, 1)
        if int(ret) <= 32:
            print("Failed to run update.bat with elevated privileges.")
            logging.error("Failed to run update.bat with elevated privileges.")
        else:
            sys.exit()

    except Exception as e:
        print(f"Error during self-update: {e}")
        logging.error(f"Error during self-update: {e}")


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
            async with session.get(VERSION_FILE_URL_CMP) as response:
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


async def fetch_max_version() -> str | None:
    """
    Asynchronously fetch the version from the GitHub repository.


    Returns
    -------
    str
        The version string from the repository.
    """
    async with aiohttp.ClientSession() as session:
        url = f"{REPO_API_URL_MAX}/releases/latest"
        async with session.get(url) as response:
            if response.status == 200:
                release_data = await response.json()
                latest_version = release_data['tag_name']
                return latest_version
            if response.status == 403:
                logging.error(f"Failed to fetch the latest max mod version. "
                              f"Status code: {response.status}")
                return 'unknown due to connection error: 403'
            logging.error(f"Failed to fetch the latest version. Status code: {response.status}")


async def print_versions(package_key: str, package_name) -> None:
    """
    Get online version and compare with local.

    Parameters
    -------
    package_key : str
        Type of mod ('CMP' or 'Mods by Max')
    package_name : str
        full name of mod
    """
    local_version = get_local_version(package_key)
    repo_version = await fetch_cmp_version() if package_key == 'CMP' \
        else await fetch_max_version()
    msg = (f"Actual version for {package_name} is {repo_version}, local version is"
           f" {'None' if local_version is None else local_version}") + '. '
    if local_version:
        if local_version == repo_version:
            msg += "Versions are equal."
            logging.info("Local version matches the repository version.")
        else:
            msg += "Versions do not match."
            logging.warning(f"Local version {local_version} does not match repository version"
                            f" {repo_version}.")
    else:
        msg += "No local version found."
        logging.warning("No local version found.")
    print(msg)
