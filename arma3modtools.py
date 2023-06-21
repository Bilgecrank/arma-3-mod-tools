#!/usr/bin/python3

# MIT License
#
# Copyright (c) 2017 Marcel de Vries
# Modified by EggyPapa - https://github.com/EggyPapa
# Copyright (c) 2023 Bilgecrank
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import re  # for sanitizing mod_names
from pathlib import Path, PurePath  # for file-handling operations
from datetime import datetime  # for comparing timestamps for mod updates
import urllib.request  # for reaching Steam Workshop webpages
import urllib.error  # for catching issues with urllib returning
import threading  # to speed up requests for getting mod data
import subprocess
import argparse
from getpass import getpass

# Non-core modules
import networkx as nx  # for sorting mod dependencies
from bs4 import BeautifulSoup  # to scrape Steam Workshop webpages of information

STEAM_CMD = 'steamcmd'  # SteamCMD reference, either the environment variable, or the path to the shell
SERVER_ID = '233780'  # Steam ID for Arma 3's Server Software'
WORKSHOP_ID = '107410'  # Workshop ID for Arma 3
SERVER_DIR = PurePath('/home/steam/servers/arma3')
WORKSHOP_DIR = SERVER_DIR / 'steamapps/workshop/content' / WORKSHOP_ID  # Directory where workshop items are placed
MODS_DIR = SERVER_DIR / 'mods'  # Directory mods will be referenced from to the game
KEYS_DIR = SERVER_DIR / 'keys'  # Key directory for mods.
STARTUP_SCRIPT = SERVER_DIR / 'start-server.sh' # The script for starting the server.

parser = argparse.ArgumentParser(
    prog='arma3modtools',
    description='Mod tools to install, update and maintain mods for Arma 3 on Linux.'
)
parser.add_argument('-f', '--html-file', action='store', dest='html_file',
                    help='Update and install mods with an Arma 3 Launcher-made html mod list.')
parser.add_argument('-v', '--validate', action='store_true', dest='validate_mods',
                    help='Validate existing mods in the workshop directory.')
parser.add_argument('-k', '--key-symlinks', action='store_true', dest='validate_key_links',
                    help='Clean up and create new keys based on mods in the workshop directory.')
arguments = parser.parse_args()


def call_steamcmd(launch_params: str):
    """
    Call the steamcmd client and run parameters against the client call

    :param launch_params: String list of parameters
    :raises subprocess.CalledProcessError: If steamcmd ends unexpectedly.
    :return: **bool** Whether or not steamcmd successfully runs
    """
    try:
        with subprocess.Popen([f'{STEAM_CMD}', f'{launch_params}']) as steamcmd:
            steamcmd.wait()
        return True
    except subprocess.CalledProcessError as error:
        print(error)
        return False


def mod_list_from_html(import_file: str):
    """
    Defines a mod list of urls from a html import file generated from Arma 3's launcher

    :param import_file: An html import file.
    :return: **list** A list of all links in the mod-list. False, if operation fails.
    """
    try:
        mod_link_list = []
        with open(import_file, 'r') as html_file:
            # Parse html file with beautiful soup and pull out all hrefs under a tags.
            soup = BeautifulSoup(html_file, 'html.parser')
            for link in soup.find_all('a'):
                mod_link_list.append(link.get('href'))
        return mod_link_list
    except IOError as error:
        print(error)
        return False


def mod_data_getter(mod_url: str, mod_dict: dict):
    """
    Thread function for ```mod_dictionary_builder```, runs concurrently to grab up-to-date information for mods.
    :param mod_url: The Steam Workshop url for the mod.
    :param mod_dict: The dictionary being built from ```mod_dictionary_builder```, not a completed dictionary
    """
    try:
        if mod_url is not None:
            dependencies = []
            # Refresh dependencies dictionary with each mod

            with urllib.request.urlopen(mod_url) as response:
                # Gather information about the mod from the steam workshop web page
                html = response.read()
                mod_soup = BeautifulSoup(html, 'html.parser')
                mod_name = mod_soup.find("div", {"class": "workshopItemTitle"}).string
                required_items = mod_soup.find(id="RequiredItems")
                if required_items is not None:
                    # Check to see if there are any dependencies for the mod.
                    dependency_links = required_items.find_all('a')
                    for link in dependency_links:
                        depend_url = link.get('href')
                        with urllib.request.urlopen(depend_url) as dependency:
                            dependency_soup = BeautifulSoup(dependency, 'html.parser')
                            depend_name = dependency_soup.find("div", {"class": "workshopItemTitle"}).string
                            dependency = {
                                'name': depend_name,
                                'param_name': '@' + re.sub('[^0-9a-zA-Z]+', '', depend_name).lower(),
                                'key': depend_url.replace(
                                    'https://steamcommunity.com/workshop/filedetails/?id=', ''),
                                'url': depend_url
                            }
                            dependencies.append(dependency)
            mod_details = {
                'name': mod_name,
                'param_name': '@' + re.sub('[^0-9a-zA-Z]+', '', mod_name).lower(),
                'key': mod_url.replace('https://steamcommunity.com/sharedfiles/filedetails/?id=', ''),
                'url': mod_url,
                'dependencies': dependencies
            }
            mod_dict[mod_url.replace('https://steamcommunity.com/sharedfiles/filedetails/?id=', '')] = mod_details
    except (TimeoutError, urllib.error.URLError) as error:
        print(error)


def mod_dictionary_builder(mod_list: list):
    """
    Builds the mod dictionary from a list of url strings linking to steam workshop pages. Calls ```mod_data_getter``` in
    separate strings to speed up the process.

    :param mod_list: A list of url strings, point to steam workshop pages.
    :return: **dict** All mods in the mod-list as dictionaries.
    """
    threads = []
    mod_dict = {}
    i = 1
    print('REQUEST: Sending out requests for mod information.')
    for mod_url in mod_list:
        thread = threading.Thread(target=mod_data_getter, args=(mod_url, mod_dict))
        thread.start()
        threads.append(thread)

    for result in threads:
        print(f'\rREQUEST: Returned {i}/{len(mod_list)} mods', end='', flush=True)
        result.join()
        i += 1
    print('')
    return mod_dict


def needs_update(mod_key: str):
    """
    Checks a mod's changelist page on the Steam Workshop and pulls the last update time and compares it when the
    mod's directory was created in the local workshop directory.

    :param mod_key: **str** The key of the mod to be checked.
    :return: **bool** Whether or not the mod needs an update.
    :raises TimeoutError: If the request for the changelist page times out.
    :raises FileNotFoundError: If the directory does not exist.
    :raises urllib.error.URLError: If a separate error through urllib happens as a result of the request.
    """
    mod_home_dir = Path(PurePath.joinpath(WORKSHOP_DIR, mod_key))
    if mod_home_dir.is_dir():  # Check if mod is installed in the workshop directory.
        try:
            with urllib.request.urlopen(
                    'https://steamcommunity.com/sharedfiles/filedetails/changelog/' + mod_key) as response:
                html = response.read()
                soup = BeautifulSoup(html, 'html.parser')
                updated = datetime.fromtimestamp(int(
                    soup.find("div", {"class": "detailBox workshopAnnouncement noFooter"}).p['id']))
                downloaded = datetime.fromtimestamp(mod_home_dir.stat().st_ctime)
                return updated >= downloaded
        except (TimeoutError,
                urllib.error.URLError,
                FileNotFoundError) as error:
            print(error)
    return True


def get_login():
    """
    Get login information from user. Will only accept 'LOGIN PASSWORD' or 'LOGIN PASSWORD STEAM_GUARD' combinations.

    :return: **str** login string for SteamCMD login variable, false if the operation does not succeed.
    """
    print('LOGIN: Account should have a valid copy of the game to download mods.')
    username = input('Username: ')
    if not username:
        print('LOGIN FAILURE: No username entry.')
        return False
    password = getpass('Password: ')
    if not password:
        print('LOGIN FAILURE: No password entry.')
        return False
    steam_guard = input('Steam Guard Code (Optional): ')
    credentials = f'{username} {password}'
    if steam_guard:
        credentials += f' {steam_guard}'
    return credentials


def check_installed_dirs(mod_list: list):
    """
    Checks the ```WORKSHOP_DIR``` to see if all mods successfully installed.

    :param mod_list: The full mod dictionary
    :return: A list of yet-to-be-installed mods, or an empty one if all mods installed.
    """
    print('UPDATE: Checking if all mods installed.')
    to_install = mod_list
    for installed_mod in Path(WORKSHOP_DIR).iterdir():
        if installed_mod.name in to_install:
            index = to_install.index(installed_mod.name)
            to_install.pop(index)
    return to_install


def run_update(mod_list: list, validate: bool=False):
    """
    Runs an update cycle for steamcmd, requesting credentials for each batch of update files.

    :param mod_list: **list** A list of key ids for mods on the workshop
    :param validate: **bool** Whether or not to run validation.
    """
    login_string = get_login()
    if not login_string:
        # If get_login() fails.
        print('EXIT: User/pass needed for mod downloads.')
        return False
    steamcmd_params = f' +login {login_string}' \
                      f' +force_install_dir {SERVER_DIR}'
    for mod in mod_list:
        if not validate:
            steamcmd_params += f' +workshop_download_item {WORKSHOP_ID} {mod}'
        else:
            steamcmd_params += f' +workshop_download_item {WORKSHOP_ID} {mod} validate'
    steamcmd_params += ' +quit'
    call_steamcmd(steamcmd_params)


def update_mods(mod_dict: dict):
    """
    Updates the mods in the mod list dictated by the mod dictionary. The mod list is checked for up to date mods
    and then appends workshop_download_item commands to the end of the steamcmd string for each mod that needs
    to be installed

    :param mod_dict: The full mod dictionary.
    :return: **bool** If procedure succeeds.
    """
    mods_to_update = []
    mods_up_to_date = []
    mods_to_validate = []
    for key, value in mod_dict.items():
        if needs_update(key):
            mods_to_update.append(key)
        else:
            mods_up_to_date.append(key)
    for mod in mod_dict.keys():
        mods_to_validate.append(mod)
    if len(mods_up_to_date) == len(mod_dict):
        print('UPDATE: All mods are up-to-date.')
        return True
    elif mods_up_to_date:
        print('UPDATE: The following mod(s) are up-to-date:')
        for installed_mod in mods_up_to_date:
            print(f'\t{mod_dict[installed_mod]["name"]}')
    if mods_to_update:
        print('UPDATE: Installing mods through SteamCMD.')
        run_update(mods_to_update)
    while True:
        not_installed_mods = check_installed_dirs(mods_to_update)
        if not_installed_mods:
            print('UPDATE: Not all mods installed, trying again.')
            run_update(mods_to_update)
        else:
            break
    print('UPDATE: Validating mods')
    run_update(mods_to_validate, validate=True)
    print('UPDATE: Mod updates finished.')
    print('UPDATE: Converting file and directory names to lowercase.')
    if not lowercase_mods():
        print('UPDATE: Could not successfully lowercase all/any mods.')
        return False
    return True


def create_mod_symlinks(mod_dict: dict):
    """
    Create symlinks from the ```WORKSHOP_DIR``` to the ```MODS_DIR```, also cleans any broken links in the folder.

    :param mod_dict: **dict** The current mod list's dictionary
    :return: **bool** Whether or not the function succeeds
    """
    print('MOD SYMLINKS: Checking if current mod links are valid.')
    for mod in Path(MODS_DIR).iterdir():
        if not mod.is_dir():
            print(f'KEY SYMLINKS: Unlinking broken link: {mod}')
            mod.unlink()
    for key, value in mod_dict.items():
        link_path = Path(MODS_DIR / value["param_name"])
        real_path = Path(WORKSHOP_DIR / key)
        if not link_path.is_dir():
            if real_path.is_dir():
                link_path.symlink_to(real_path)
                print(f'MOD SYMLINKS: Creating symlink at: {link_path}')
            else:
                print(f'SYMLINK ERROR: {value["name"]} not found: {real_path}')
    return True


def key_symlinks():
    """
    Creates symlinks from the key files in the workshop directory to the key files in the ```KEYS_DIR```

    :return: **bool** Whether or not the operation finishes successfully.
    """
    print('KEY SYMLINKS: Checking if current keys are valid.')
    for key in Path(KEYS_DIR).iterdir():
        if not key.is_file():
            print(f'KEY SYMLINKS: Unlinking broken key: {key}')
            key.unlink()
    # Glob all bikey files in the ```WORKSHOP DIR```
    bikey_files = Path(WORKSHOP_DIR).glob('*/*/*.bikey')
    for key in bikey_files:
        symlink_key = Path(KEYS_DIR / key.name)
        if not symlink_key.is_file():
            print(f'KEY SYMLINKS: Creating symlink at: {symlink_key}')
            symlink_key.symlink_to(key)
    return True


def lowercase_mods():
    """
    Recursively set all directories and files in the ```WORKSHOP_DIR``` to lowercase

    :return: True function successfully finishes.
    """
    if Path(WORKSHOP_DIR).is_dir():
        for directory in Path(WORKSHOP_DIR).iterdir():
            for item in directory.rglob('*'):
                lowered_item = item.name.lower()
                parent_path = item.parent
                item.replace(parent_path / lowered_item)
        return True
    else:
        print('UPDATE: No workshop folder detected.')
        return False


def dependency_sort(mod_dict: dict):
    """
    Creates a mod= string by sorting the mods by dependency through a topological sort.

    :param mod_dict: The full mod dictionary.
    :return: A string to be used for the mod= parameter
    """
    load_order = ''
    dictionary = mod_dict
    graph = nx.DiGraph()
    for key, value in dictionary.items():
        # Add mods to a directed graph. NetworkX will ignore nodes that are already made.
        graph.add_node(value['param_name'])
        for dependent in value['dependencies']:
            # Add the mods dependencies and create directed edges.
            graph.add_node(dependent['param_name'])
            graph.add_edge(dependent['param_name'], value['param_name'])
    load_order_list = list(nx.topological_sort(graph))
    relative_mod_path = MODS_DIR.relative_to(SERVER_DIR)
    # Capture relative path of ```MODS_DIR``` to ```SERVER_DIR``
    for mod in load_order_list:
        if mod is not load_order_list[0]:
            load_order += ';'
        load_order += str(relative_mod_path / mod)
    return load_order


def write_start_up_script(load_order: str):
    """
    Updates or writes the start-up script for the server with the new mod parameter.

    :param load_order: **str** The mod= string value.
    :return: **bool** Whether the process succeeds or fails.
    """
    load_order = '-mod=\"' + load_order + '\"'
    if Path(STARTUP_SCRIPT).is_file():
        with open(STARTUP_SCRIPT, 'r') as read_script:
            startup_parameters = read_script.read().split(' ')
        if any(param.startswith('-mod=') for param in startup_parameters):
            for index, param in enumerate(startup_parameters):
                if param.startswith('-mod='):
                    startup_parameters[index] = load_order
        else:
            if startup_parameters[-1].endswith('\n'):
                startup_parameters[-1] = startup_parameters[-1][:-2]
            startup_parameters.append(load_order)
        with open(STARTUP_SCRIPT, 'w') as write_script:
            for param in startup_parameters:
                if param == startup_parameters[0]:
                    write_script.write(param)
                else:
                    write_script.write(' ' + param)
    else:
        # Create new script and make it executable
        with open(STARTUP_SCRIPT, 'w') as script:
            script.write('#!/bin/sh\n\necho \"Starting server PRESS CTRL+C to exit\"\n./arma3server ' + load_order +
                         '\n')
        Path(STARTUP_SCRIPT).chmod(0o744)
    return True


def run_html_mod_update():
    """
    Carries out a mod-update process using an Arma 3 Mod List html as a source

    :return: **bool** Whether or not the function succeeds
    """
    print('CHECKING HTML: Scanning mod list for urls.')
    launcher_html = mod_list_from_html(arguments.html_file)
    if not launcher_html:
        print('CHECKING HTML: There was an issue scanning the html, shutting down.')
        return False
    print('REQUEST: Assembling dictionary.')
    mod_dictionary = mod_dictionary_builder(launcher_html)
    if not mod_dictionary:
        print('REQUEST ERROR: There was an issue assembling the dictionary, shutting down.')
        return False
    if not update_mods(mod_dictionary):
        print('UPDATE ERROR: An issue arose trying to updating the mods, shutting down.')
        return False
    if not create_mod_symlinks(mod_dictionary):
        print('MOD SYMLINKS ERROR: Something happened when creating mod symlinks, shutting down.')
        return False
    if not key_symlinks():
        print('KEY SYMLINKS ERROR: Key symlinks could not properly be established, shutting down.')
        return False
    print('SORTING DEPENDENCIES: Sorting mods by dependency.')
    mod_param = dependency_sort(mod_dictionary)
    if not mod_param:
        print('SORTING DEPENDENCIES ERROR: Either no mods were in the dictionary or dependencies could not be sorted')
    else:
        print(f'SORTING DEPENDENCIES: Printing out file in {Path.cwd()}')
    print(f'START-UP SCRIPT: Updating/Creating start-up script at {STARTUP_SCRIPT}')
    write_start_up_script(mod_param)


def validate_mods():
    """
    Validates mods in the ```WORKSHOP_DIR``` by calling workshop_download_mod validate on each mod installed.
    :return:
    """
    workshop_mods = []
    for installed_mod in Path(WORKSHOP_DIR).iterdir():
        workshop_mods.append(installed_mod.name)
    print(f'VALIDATE: Validating {len(workshop_mods)} workshop mods.')
    run_update(workshop_mods, True)
    print('VALIDATE: Validation concluded.')


if __name__ == '__main__':
    if arguments.html_file:
        run_html_mod_update()
    elif arguments.validate_mods:
        validate_mods()
    elif arguments.validate_key_links:
        key_symlinks()
    else:
        print('NO ARGUMENTS: No valid arguments passed.')
