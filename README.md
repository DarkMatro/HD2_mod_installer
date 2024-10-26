# HD2 Mod Installer
![image](https://github.com/user-attachments/assets/5bf12936-2dc3-4d18-b868-b44ec841141c)

This repository contains the **HD2 Mod Installer**, a Python script designed to synchronize the files of the Hidden & Dangerous 2 (HD2) game with a specific GitHub repository. The tool is particularly useful for ensuring that the game files are up to date with the latest versions available in the repository.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Mods](#mods)


## Features

- **Manual Update**: Provides a console menu for manually checking and updating files.
- **Efficient File Management**: Downloads or deletes only the files that have changed based on their SHA-1 hashes.
  
## Installation

- Download [latest release](https://github.com/DarkMatro/HD2_mod_installer/releases/download/v0.0.3/mod_installer.exe). 
- Copy file mod_installer.exe to game folder.
  
## Usage
- Open mod_installer.exe.
- Choose mod to install/uninstall.

## Mods
- [Coop Map Package (CMP)](https://github.com/ehylla93/had2-cmp)
- [Texture and Sounds mods by Max](https://github.com/DarkMatro/Texture-and-Sounds-mods-by-Max)

## Code compilation to .exe (for developers only)
```bash
pyinstaller  --name="mod_installer"  main.py --onefile --hiddenimport pygit2 --hiddenimport _cffi_backend --icon 'icons/icon.ico'
```
