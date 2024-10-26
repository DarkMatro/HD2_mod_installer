# pylint: disable=logging-fstring-interpolation

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import aiohttp
import psutil
import pygit2
from tqdm import tqdm


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


async def fetch_tree_contents(url: str, session: aiohttp.ClientSession,
                              folder: str, local_path: str, files: list,
                              is_delete: bool = False, raw_base_url: str = '') -> None:
    """
    Fetch contents of the specified tree SHA with parallel SHA1 calculations.

    Parameters
    ----------
    url : str
        of main or master branch like
         'https://api.github.com/repos/ehylla93/had2-cmp/git/trees/main'
    session : aiohttp.ClientSession
        The active client session for making HTTP requests.
    folder : str
        Folder name.
    local_path : str
        The local path where the folder contents should be saved.
    files : list
        The list to store the details of files that need to be downloaded.
    is_delete : bool
        True for uninstall, False for install
    raw_base_url : str
        strongly required for is_delete = False
        of main or master branch like
         'https://raw.githubusercontent.com/DarkMatro/Texture-and-Sounds-mods-by-Max/master'
    """
    url = f'{url}:{folder}?recursive=1'
    tree_contents = await fetch_with_retry(session, url)
    if not tree_contents:
        return

    total_files = len([item for item in tree_contents['tree'] if item['type'] == 'blob'])

    # Используем прогресс-бар с общим количеством файлов
    with tqdm(total=total_files, desc=f"Scanning {folder}", unit=' files',
              dynamic_ncols=True) as pbar:
        with ThreadPoolExecutor(max_workers=psutil.cpu_count(logical=False)) as executor:
            futures = []

            for item in tree_contents['tree']:
                if item['type'] == 'tree':
                    sub_folder_local_path = os.path.join(local_path, item['path'])
                    if not os.path.exists(sub_folder_local_path):
                        os.makedirs(sub_folder_local_path)
                elif item['type'] == 'blob':
                    # Добавляем задачу в пул потоков
                    if is_delete:
                        future = executor.submit(check_and_prepare_file_to_delete, item, local_path,
                                                 files)
                    else:
                        future = executor.submit(check_and_prepare_file, item, folder, local_path,
                                                 files, raw_base_url)
                    futures.append(future)

            # Обновляем прогресс-бар по завершению каждой задачи
            for future in as_completed(futures):
                future.result()  # Получаем результат (если есть исключение - поднимаем его)
                pbar.update()  # Обновляем прогресс-бар


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
    msg = f"Failed to fetch data after {retries} attempts. Try again later."
    logging.error(msg)
    print(msg)
    raise ConnectionError(msg)


def check_and_prepare_file(item, folder, local_path, files_to_download, raw_base_url):
    """
    Check if the file exists and its SHA1 matches the expected value. If not, add it to the download
    list.

    Parameters
    ----------
    item : dict
        File metadata from the GitHub API tree.
    folder : str
        The folder being scanned.
    local_path : str
        The local path where files are stored.
    files_to_download : list
        of files to download if they are missing or have mismatched hashes.
    raw_base_url : str
        of main or master branch like
         'https://raw.githubusercontent.com/DarkMatro/Texture-and-Sounds-mods-by-Max/master'
    """
    local_file_path = os.path.join(local_path, item['path'])
    # Проверяем, если файл не существует или его SHA1 хэш не совпадает с указанным
    if not Path(local_file_path).exists() or item['sha'] != calculate_sha1(local_file_path):
        # Если файл не совпадает, добавляем его в список для скачивания
        files_to_download.append({
            'download_url': f"{raw_base_url}/{folder}/{item['path'].replace('#', '%23')}",
            'local_path': local_file_path,
            'size': item['size']
        })


def check_and_prepare_file_to_delete(item, local_path, files_to_delete):
    """
    Check if the file exists and its SHA1 matches the expected value. If yes, add it to the delete
    list.

    Parameters
    ----------
    item : dict
        File metadata from the GitHub API tree.
    local_path : str
        The local path where files are stored.
    files_to_delete : list
        of files to download if they are missing or have mismatched hashes.
    """
    local_file_path = os.path.join(local_path, item['path'])
    # Проверяем, если файл не существует или его SHA1 хэш не совпадает с указанным
    if Path(local_file_path).exists() and item['sha'] == calculate_sha1(local_file_path):
        # Если файл совпадает, добавляем его в список для удаления
        files_to_delete.append({'local_path': local_file_path, 'size': item['size']})
