import json
from pathlib import Path

LOCAL_VERSION_FILE = 'local_version.json'

def get_local_version():
    """
    Load the local version of CMP from a file.

    Returns
    -------
    str or None
        The local version string if the file exists, otherwise None.
    """
    _check_version_file()
    with open(LOCAL_VERSION_FILE, encoding="utf-8") as f:
        settings = json.load(f)
    return settings['CMP']


def save_local_version(version):
    """
    Save the local version of CMP to a file.

    Parameters
    ----------
    version : str
        The version string to save.
    """
    with open(LOCAL_VERSION_FILE, 'r+', encoding="utf-8") as f:
        data = json.load(f)
        data['CMP'] = version
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
    return {'CMP': ''}
