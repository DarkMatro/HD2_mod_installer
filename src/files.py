import asyncio
import logging
from pathlib import Path

import aiofiles
import aiohttp
from tqdm import tqdm


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


async def delete_files(files: list) -> None:
    """
    Delete files concurrently and display a global progress bar.

    Parameters
    ----------
    files : list
        of dictionaries containing the local path and size.
    """
    total_size = sum(int(file_info['size']) for file_info in files)  # Общий размер всех файлов

    with tqdm(total=total_size, unit='B', unit_scale=True, desc="Deleting files",
              dynamic_ncols=True) as pbar:
        for file_info in files:
            try:
                Path(file_info['local_path']).unlink(missing_ok=True)
                pbar.update()
            except FileNotFoundError as e:
                msg = f"File {file_info['local_path']} missing: {e}"
                logging.error(msg)
