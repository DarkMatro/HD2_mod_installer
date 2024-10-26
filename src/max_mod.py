# pylint: disable=logging-fstring-interpolation

import logging
import os

import aiohttp

from src.check import delete_empty_folders
from src.files import download_files, delete_files
from src.git_functions import fetch_tree_contents
from src.local_version import save_local_version

# Constants
FOLDERS_TO_CHECK = ['Maps', 'Maps_U', 'Models', 'PlayersProfiles', 'Sounds', 'Text']
FOLDERS_TO_CHECK_RUS = ['Maps', 'Tables', 'Text']
URL = 'https://api.github.com/repos/DarkMatro/Texture-and-Sounds-mods-by-Max/git/trees/master'
URL_RU = ('https://api.github.com/repos/DarkMatro/Texture-and-Sounds-mods-by-Max_RUS/git/trees'
          '/master')
RAW_BASE_URL = ('https://raw.githubusercontent.com/DarkMatro/Texture-and-Sounds-mods-by-Max'
                '/master')
RAW_BASE_URL_RU = ('https://raw.githubusercontent.com/DarkMatro/Texture-and-Sounds-mods-by'
                   '-Max_RUS/master')


async def install_max_mod(repo_version: str, is_rus: bool) -> None:
    """
    Install MAX's mods pack files from the repository.

    This function checks and downloads all necessary files from the repository.

    Parameters
    ----------
    repo_version : str
        Actual version from GitHub repository
    is_rus : bool
        Flag to install additional files from folder 'For russian version'
    """
    print('Installing Texture and Sounds mods by Max')
    async with aiohttp.ClientSession() as session:
        files_to_download = []
        for folder in FOLDERS_TO_CHECK:
            folder_local_path = os.path.join(os.getcwd(), folder)
            if not os.path.exists(folder_local_path):
                print(f'Created new folder {folder_local_path}')
                os.makedirs(folder_local_path)
            await fetch_tree_contents(URL, session, folder, folder_local_path,
                                      files_to_download, raw_base_url=RAW_BASE_URL)
        if is_rus:
            for folder in FOLDERS_TO_CHECK_RUS:
                folder_local_path = os.path.join(os.getcwd(), folder)
                if not os.path.exists(folder_local_path):
                    print(f'Created new folder {folder_local_path}')
                    os.makedirs(folder_local_path)
                await fetch_tree_contents(URL_RU, session, folder, folder_local_path,
                                          files_to_download, raw_base_url=RAW_BASE_URL_RU)

        if files_to_download:
            logging.info(f"Downloading {len(files_to_download)} files...")
            await download_files(session, files_to_download)
        else:
            print("No new or updated files to download.")
            logging.info("No new or updated files to download.")

        save_local_version(repo_version, 'Mods by Max')
        print(f"Synchronization complete. Max Mods pack is now at version {repo_version}." + '\n')
        logging.info(f"Synchronization complete. Max Mods pack is now at version {repo_version}.")


async def uninstall_max_mod() -> None:
    """
    Uninstall Max mod pack files.

    This function checks and deletes all files from game folder equal to files from repository.
    """
    print('Uninstalling Texture and Sounds mods by Max')
    async with aiohttp.ClientSession() as session:
        files_to_delete = []
        for folder in FOLDERS_TO_CHECK:
            folder_local_path = os.path.join(os.getcwd(), folder)
            if not os.path.exists(folder_local_path):
                continue
            await fetch_tree_contents(URL, session, folder, folder_local_path, files_to_delete,
                                      is_delete=True)
        for folder in FOLDERS_TO_CHECK_RUS:
            folder_local_path = os.path.join(os.getcwd(), folder)
            if not os.path.exists(folder_local_path):
                continue
            await fetch_tree_contents(URL_RU, session, folder, folder_local_path, files_to_delete,
                                      is_delete=True)
        if files_to_delete:
            logging.info(f"Deleting {len(files_to_delete)} files...")
            await delete_files(files_to_delete)
            save_local_version(None)
            msg = "Mods pack uninstalled."
            print(msg + '\n')
            logging.info(msg)
        else:
            print("No files to delete.")
            logging.info("No files to delete.")
    for folder in FOLDERS_TO_CHECK:
        folder_local_path = os.path.join(os.getcwd(), folder)
        delete_empty_folders(folder_local_path)
