# pylint: disable=logging-fstring-interpolation

"""
HD2 CMP Sync Tool

This script is designed to synchronize the files of the Hidden & Dangerous 2 game with a specific
GitHub repository.
It checks for version updates, synchronizes necessary files, and provides a user interface for
manual file checking and installation.

The script supports two modes of operation:
1. Automatic mode: Triggered when the game is launched via an .asi file.
2. Manual mode: Provides a console menu for checking files and installing updates.

Requirements:
- Python 3.12+


Author: Matro
"""

import asyncio
import ctypes
import logging
import os
import sys
import time
import webbrowser
from pathlib import Path

import aiofiles
import aiohttp

from tqdm import tqdm

from src.check import check_internet_connection, check_game_executable
from src.local_version import get_local_version, save_local_version, check_latest_version
from src.actual_versions import fetch_cmp_version
from src.git_functions import calculate_sha1

# Constants
FOLDERS_TO_CHECK = ['Maps', 'Models', 'Sounds', 'Missions', 'Scripts', 'Text', 'cmp_optional']
RAW_BASE_URL = 'https://raw.githubusercontent.com/ehylla93/had2-cmp/main'


async def fetch_file(session: aiohttp.ClientSession, url: str, dest_path: str, pbar):
    """
    Asynchronously download a file from the given URL.

    Parameters
    ----------
    session : aiohttp.ClientSession
        The active client session for making HTTP requests.
    url : str
        The URL of the file to download.
    dest_path : str
        The destination path to save the file.
    pbar : tqdm
        The progress bar to update for overall progress.
    """
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            chunk_size = 1024  # Размер куска данных для загрузки
            async with aiofiles.open(dest_path, 'wb') as file:
                async for chunk in response.content.iter_chunked(chunk_size):
                    await file.write(chunk)
                    pbar.update(len(chunk))  # Обновляем общий прогресс-бар

    except Exception as e:
        logging.error(f"Error downloading file from {url} to {dest_path}: {e}")
        raise


async def fetch_with_retry(session, url, retries=3, backoff_factor=2) -> dict | list:
    """
    Fetch data from GitHub with retry logic on rate limit errors.

    Parameters
    ----------
    session : aiohttp.ClientSession
        The active client session for making HTTP requests.
    url : str
        The URL of the file to download.
    retries : int, optional
        The number of retries (default is 3).
    backoff_factor : int, optional
        The backoff factor for retries (default is 2).

    Returns
    -------
    list or dict
        The JSON content of the response.
    """
    for _ in range(retries):
        async with session.get(url) as response:
            if response.status == 403 and 'rate limit' in await response.text():
                retry_after = int(response.headers.get('Retry-After', backoff_factor))
                print(f"Requests Rate limit exceeded. Retrying in {retry_after} seconds...")
                time.sleep(retry_after)
            elif response.status == 404:
                logging.error(f"Error 404: Not Found. URL: {url}")
                return []
            elif response.status == 401:
                print("Error 401: Unauthorized")
                logging.error("Error 401: Unauthorized")
                return []
            else:
                response.raise_for_status()
                return await response.json()

    logging.error(f"Failed to fetch data after {retries} attempts.")
    return []


async def download_files(session: aiohttp.ClientSession, files_to_download: list) -> None:
    """
    Download files concurrently and display a global progress bar.

    Parameters
    ----------
    session : aiohttp.ClientSession
        The active client session for making HTTP requests.
    files_to_download : list
        of dictionaries containing the download URL and local path.
    """
    total_size = sum(
        int(file_info['size']) for file_info in files_to_download)  # Общий размер всех файлов
    download_tasks = []

    # Создание общего прогресс-бара
    with tqdm(total=total_size, unit='B', unit_scale=True, desc="Downloading files",
              dynamic_ncols=True) as pbar:
        for file_info in files_to_download:
            download_tasks.append(
                fetch_file(session, file_info['download_url'], file_info['local_path'], pbar))
        await asyncio.gather(*download_tasks)


async def fetch_tree_contents(session: aiohttp.ClientSession, folder: str, local_path: str,
                              files_to_download: list) -> None:
    """
    Fetch contents of the specified tree SHA.

    Parameters
    ----------
    session : aiohttp.ClientSession
        The active client session for making HTTP requests.
    folder : str
        folder name.
    local_path : str
        The local path where the folder contents should be saved.
    files_to_download : list
        The list to store the details of files that need to be downloaded.
    """
    url = f'https://api.github.com/repos/ehylla93/had2-cmp/git/trees/main:{folder}?recursive=1'
    tree_contents = await fetch_with_retry(session, url)

    # Инициализация прогресс-бара
    for item in tqdm(tree_contents['tree'], desc=f"Scanning {folder}", unit=' files',
                     dynamic_ncols=True):
        if item['type'] == 'tree':
            sub_folder_local_path = os.path.join(local_path, item['path'])
            if not os.path.exists(sub_folder_local_path):
                os.makedirs(sub_folder_local_path)
        elif item['type'] == 'blob':
            local_file_path = os.path.join(local_path, item['path'])
            if not Path(local_file_path).exists() or item['sha'] != calculate_sha1(local_file_path):
                files_to_download.append({
                    'download_url': f"{RAW_BASE_URL}/{folder}/{item['path']}",
                    'local_path': local_file_path,
                    'size': item['size']
                })


async def install_cmp(cmp_version: str) -> None:
    """
    Install CMP files from the repository.

    This function checks and downloads all necessary files from the repository.
    """
    print('Installing Coop Map Package (CMP)')
    async with aiohttp.ClientSession() as session:
        files_to_download = []
        for folder in FOLDERS_TO_CHECK:
            folder_local_path = os.path.join(os.getcwd(), folder)
            if not os.path.exists(folder_local_path):
                print(folder_local_path)
                os.makedirs(folder_local_path)
            await fetch_tree_contents(session, folder, folder_local_path, files_to_download)

        if files_to_download:
            logging.info(f"Downloading {len(files_to_download)} files...")
            await download_files(session, files_to_download)
        else:
            print("No new or updated files to download.")
            logging.info("No new or updated files to download.")

        save_local_version(cmp_version)
        print(f"Synchronization complete. CMP is now at version {cmp_version}.")
        logging.info(f"Synchronization complete. CMP is now at version {cmp_version}.")

    await menu()


async def main():
    """
    Main entry point for the script.

    This function checks the version, displays the menu in manual mode,
    and handles automatic updates if triggered via .asi.
    """
    # Setup logging
    logging.basicConfig(filename='hd2_sync.log', level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info("Starting HD2 CMP Sync Tool.")
    await check_latest_version()
    check_internet_connection()
    check_game_executable()

    try:
        local_version = get_local_version()
        repo_version = await fetch_cmp_version()
        print(f"Actual version for CMP is {repo_version}, local version is"
              f" {'None' if local_version is None else local_version}")
        if local_version:
            if local_version == repo_version:
                print("Versions are equal.")
                logging.info("Local version matches the repository version.")
            else:
                print("Versions do not match.")
                logging.warning(f"Local version {local_version} does not match repository version"
                                f" {repo_version}.")
        else:
            print("No local version found.")
            logging.warning("No local version found.")

        await menu()

    except Exception as e:
        logging.error(f"An error occurred: {e}")
    finally:
        print("Program has ended.")
        logging.info("Program has ended.")


async def menu():
    """
    Console application menu
    """
    repo_version = await fetch_cmp_version()
    while True:
        print("1. Install CMP")
        print("2. Go to GitHub page")
        print("3. Exit")
        choice = input("Choose an option: ")

        if choice == '1':
            await install_cmp(repo_version)
            break
        if choice == '2':
            print("Opening GitHub page...")
            webbrowser.open("https://github.com/DarkMatro/HD2_mod_installer")
        if choice == '3':
            print("Exiting the program.")
            logging.info("User chose to exit the program.")
            break
        print("Invalid choice. Please try again.")

def is_admin():
    """
    Checks if the script is running as administrator.
    """
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    """
    Restarts the script with administrator rights.
    """
    if is_admin():
        return
    try:
        # Запускает этот скрипт с правами администратора
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, ' '.join(sys.argv), None, 1)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_as_admin()
    asyncio.run(main())
