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
import logging
import os
import time
from pathlib import Path

import aiofiles
import aiohttp

from tqdm import tqdm

from src.check import check_internet_connection, check_game_executable
from src.local_version import get_local_version, save_local_version
from src.actual_versions import fetch_cmp_version
from src.git_functions import calculate_sha1

# Constants
GITHUB_REPO_URL = 'https://api.github.com/repos/ehylla93/had2-cmp/contents'
FOLDERS_TO_CHECK = ['Maps', 'Models', 'Sounds', 'Missions', 'Scripts', 'Text']
GITHUB_API_PER_PAGE_LIMIT = 1000
GITHUB_TOKEN = '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'
CMP_OPTIONAL_PATHS = ['cmp_optional/Civil Uniform Mod/Maps',
                      'cmp_optional/Civil Uniform Mod/Models']
RAW_BASE_URL = 'https://raw.githubusercontent.com/ehylla93/had2-cmp/main'


async def fetch_file(session, url, dest_path, pbar):
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
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}'
    }
    try:
        async with session.get(url, headers=headers) as response:
            response.raise_for_status()
            chunk_size = 1024  # Размер куска данных для загрузки
            async with aiofiles.open(dest_path, 'wb') as file:
                async for chunk in response.content.iter_chunked(chunk_size):
                    await file.write(chunk)
                    pbar.update(len(chunk))  # Обновляем общий прогресс-бар

    except Exception as e:
        logging.error(f"Error downloading file from {url} to {dest_path}: {e}")
        raise


async def fetch_with_retry(session, url, retries=3, backoff_factor=2):
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
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}'
    }

    for _ in range(retries):
        async with session.get(url, headers=headers) as response:
            if response.status == 403 and 'rate limit' in await response.text():
                retry_after = int(response.headers.get('Retry-After', backoff_factor))
                print(f"Requests Rate limit exceeded. Retrying in {retry_after} seconds...")
                time.sleep(retry_after)
            elif response.status == 404:
                logging.error(f"Error 404: Not Found. URL: {url}")
                return []
            else:
                response.raise_for_status()
                return await response.json()

    logging.error(f"Failed to fetch data after {retries} attempts.")
    return []


async def fetch_folder_contents(session, folder_url, local_path, files_to_download, page=1,
                                previous_items=None, is_top_level=True):
    """
    Fetch the contents of a folder recursively from GitHub with pagination support and retry logic.

    Parameters
    ----------
    session : aiohttp.ClientSession
        The active client session for making HTTP requests.
    folder_url : str
        The URL of the folder in the GitHub repository.
    local_path : str
        The local path where the folder contents should be saved.
    files_to_download : list
        The list to store the details of files that need to be downloaded.
    page : int, optional
        The current page number for pagination (default is 1).
    previous_items : set, optional
        The set of previously fetched items to avoid infinite loops (default is None).
    is_top_level : bool, optional
        Flag to indicate whether the folder is at the top level (default is True).
    """
    if previous_items is None:
        previous_items = set()

    # Ensure that ?ref=main is added only once
    if "?ref=main" not in folder_url:
        folder_url += "?ref=main"

    while True:
        paginated_url = f"{folder_url}&page={page}&per_page={GITHUB_API_PER_PAGE_LIMIT}"
        items = await fetch_with_retry(session, paginated_url)
        if not items or len(items) == 0:
            break

        current_items = set(item['name'] for item in items)

        # Check if we've already seen these items (avoiding infinite loop)
        if current_items.issubset(previous_items):
            break

        previous_items.update(current_items)

        if is_top_level:
            # Display progress only for top-level folders
            progress_desc = f"Scanning {os.path.basename(local_path)}"
            for item in tqdm(items, desc=progress_desc, unit=" files", dynamic_ncols=True):
                await process_item(item, session, local_path, files_to_download, is_top_level=False)
        else:
            # For nested folders, process items without showing progress
            for item in items:
                await process_item(item, session, local_path, files_to_download, is_top_level=False)
        page += 1
        # Если получено меньше элементов, чем лимит страницы, значит, мы дошли до конца
        if len(items) < GITHUB_API_PER_PAGE_LIMIT:
            break


async def process_item(item, session, local_path, files_to_download, is_top_level):
    """
    Process a single item (file or directory) from the GitHub repository.

    Parameters
    ----------
    item : dict
        The item (file or directory) from the GitHub API response.
    session : aiohttp.ClientSession
        The active client session for making HTTP requests.
    local_path : str
        The local path where the item should be saved.
    files_to_download : list
        The list to store the details of files that need to be downloaded.
    is_top_level : bool
        Flag to indicate whether the folder is at the top level.
    """
    item_name = item['name']
    item_type = item['type']
    item_url = item['url']

    if item_type == 'dir':
        sub_folder_local_path = os.path.join(local_path, item_name)
        if not os.path.exists(sub_folder_local_path):
            os.makedirs(sub_folder_local_path)
        await fetch_folder_contents(session, item_url, sub_folder_local_path, files_to_download,
                                    is_top_level=is_top_level)
    elif item_type == 'file':
        local_file_path = os.path.join(local_path, item_name)
        if item['sha'] != calculate_sha1(local_file_path):
            files_to_download.append({
                'download_url': item['download_url'],
                'local_path': local_file_path,
                'size': item['size']
            })


async def download_files(session, files_to_download):
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


async def get_tree_sha(session, folder):
    """
    Get the SHA of the tree for the specified folder.

    Parameters
    ----------
    session : aiohttp.ClientSession
        The active client session for making HTTP requests.
    folder : str
        The name of the folder to get the tree SHA.

    Returns
    -------
    str
        The SHA of the tree.
    """
    url = f'https://api.github.com/repos/ehylla93/had2-cmp/git/trees/main:{folder}'
    tree_info = await fetch_with_retry(session, url)
    if not tree_info:
        return None
    return tree_info['sha']


async def fetch_tree_contents(session, tree_sha, local_path, files_to_download):
    """
    Fetch contents of the specified tree SHA.

    Parameters
    ----------
    session : aiohttp.ClientSession
        The active client session for making HTTP requests.
    tree_sha : str
        The SHA of the tree.
    local_path : str
        The local path where the folder contents should be saved.
    files_to_download : list
        The list to store the details of files that need to be downloaded.
    """
    url = f'https://api.github.com/repos/ehylla93/had2-cmp/git/trees/{tree_sha}'
    tree_contents = await fetch_with_retry(session, url)

    # Инициализация прогресс-бара
    total_files = len(tree_contents['tree'])
    with (tqdm(total=total_files, desc="Scanning Maps", unit=' file',
               dynamic_ncols=True) as pbar):
        for item in tree_contents['tree']:
            item_name = item['path']
            item_type = item['type']

            if item_type == 'tree':
                sub_folder_local_path = os.path.join(local_path, item_name)
                if not os.path.exists(sub_folder_local_path):
                    os.makedirs(sub_folder_local_path)
                # Рекурсивный вызов для вложенных папок
                await fetch_tree_contents(session, item['sha'], sub_folder_local_path,
                                          files_to_download)
            elif item_type == 'blob':
                local_file_path = os.path.join(local_path, item_name)
                if not Path(local_file_path).exists() \
                        or item['sha'] != calculate_sha1(local_file_path):
                    files_to_download.append({
                        'download_url': f"{RAW_BASE_URL}/Maps/{item['path']}",
                        'local_path': local_file_path,
                        'size': item['size']
                    })
            pbar.update(1)  # Обновляем прогресс-бар


async def install_cmp(cmp_version):
    """
    Install CMP files from the repository.

    This function checks and downloads all necessary files from the repository.
    """
    print('Installing Coop Map Package (CMP)')
    async with aiohttp.ClientSession() as session:
        files_to_download = []

        for folder in FOLDERS_TO_CHECK:
            if folder == 'Maps':
                # Используем Git Trees API для папки Maps
                tree_sha = await get_tree_sha(session, folder)
                if tree_sha is None:
                    continue
                folder_local_path = os.path.join(os.getcwd(), folder)

                if not os.path.exists(folder_local_path):
                    print(folder_local_path)
                    os.makedirs(folder_local_path)

                await fetch_tree_contents(session, tree_sha, folder_local_path, files_to_download)
            else:
                # Обычная обработка других папок
                folder_url = f"{GITHUB_REPO_URL}/{folder}"
                folder_local_path = os.path.join(os.getcwd(), folder)

                if not os.path.exists(folder_local_path):
                    print(folder_local_path)
                    os.makedirs(folder_local_path)

                await fetch_folder_contents(session, folder_url, folder_local_path,
                                            files_to_download)

        for optional_path in CMP_OPTIONAL_PATHS:
            optional_url = f"{GITHUB_REPO_URL}/{optional_path}"
            optional_local_path = os.path.join(os.getcwd(), optional_path)

            if not os.path.exists(optional_local_path):
                print(optional_local_path)
                os.makedirs(optional_local_path)

            await fetch_folder_contents(session, optional_url, optional_local_path,
                                        files_to_download)

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
        print("2. Exit")
        choice = input("Choose an option: ")

        if choice == '1':
            await install_cmp(repo_version)
            break
        if choice == '2':
            print("Exiting the program.")
            logging.info("User chose to exit the program.")
            break
        print("Invalid choice. Please try again.")


if __name__ == "__main__":
    asyncio.run(main())
