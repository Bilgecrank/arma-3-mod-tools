#!/usr/bin/python3

# MIT License
#
# Copyright (c) 2017 Marcel de Vries
#
# Modified by EggyPapa
# https://github.com/EggyPapa
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

import os
import os.path
import re
import json
import six
import sys
import shutil
import time
import datetime as dt
import argparse
import tempfile

from datetime import datetime
from urllib import request
from getpass import getpass

# Parse parameters.
parser = argparse.ArgumentParser(description='Downloads Mods from the Arma3 Steam Workshop. \n NOTE: The account you use, MUST own a copy of Arma3.')
parser.add_argument('-p','--password', action='store', dest='password_param',help='Provide password.')
parser.add_argument('-u','--username', action='store', dest='username_param',help='Provide username.')
parser.add_argument('-f','--modlist', action='store', dest='modfile_name',help='Provide the name of a json modfile, or a list of modfiles with their names seperated by commas.')
parser.add_argument('-w','--weblocation', action='store', dest='web_file_name',help='Provide the URL for a json modfile.')
parser.add_argument('-d','--defer', action='store_true', dest='defer_upgrade_true',help='Defer server upgrade.')
parser.add_argument('-q','--quick', action='store_true', dest='quick_install_true',help='Quickly install a single mod.')
results = parser.parse_args()

## Configuration information:
# The location of your steamcmd install.
STEAM_CMD = "/home/steam/steamcmd/steamcmd.sh"
# Your steam username, for if you want to hardcode it.
STEAM_USER = ""
# Your steam account password, for if you want to hardcode it.
STEAM_PASS = ""
# The appid of Arma 3's Dedicated server. You shouldn't need to change this.
A3_SERVER_ID = "233780"
# The location that arma3 dedicated server is installed.
A3_SERVER_DIR = "/home/steam/arma3"
# The appid of Arma 3, this is used to get workshop content. You shouldn't need to change this.
A3_WORKSHOP_ID = "107410"
# The location for which workshop content will be installed, you shouldn't need to change this.
A3_WORKSHOP_DIR = "{}/steamapps/workshop/content/{}".format(A3_SERVER_DIR, A3_WORKSHOP_ID)
# The location the symlinked folders for the mods will be placed, this should be in or below the folder Arma 3 is installed.
A3_MODS_DIR = "/home/steam/arma3"
# The location for mod keys to be placed.
A3_KEYS_DIR = "{}/keys".format(A3_SERVER_DIR)

###
### Mods are stored in mods.json
###

## These ones only matter if you want to have a starting command pregenerated
# The name you want the server to have
server_name = "Arma 3 Server"
# The name of your server.cfg file, I recommend leaving it as server.cfg but i'm not your Dad.
server_cfg = "server.cfg"

#
###
####
#### Users don't need to look at anything below this.
####
###
#

# These are the dictionaries that will be populated by the script.
MOD_URLS = {}
MODS = {}

PATTERN = re.compile(r"workshopAnnouncement.*?<p id=\"(\d+)\">", re.DOTALL)
WORKSHOP_CHANGELOG_URL = "https://steamcommunity.com/sharedfiles/filedetails/changelog"
mod_name_pattern = re.compile(r"(?:<title>Steam Workshop :: )(.+)(?:<.+>)")
mod_id_pattern = re.compile(r"(?:\?id=)(.+)")

class colour:
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    BOLD='\033[31m'
    REG='\033[0;0m'

def empty_strings2none(obj):
    for k, v in six.iteritems(obj):
        if v == '':
            obj[k] = None
    return obj

def log(msg, type = 0):
    if type == 1:
        style = colour.BOLD + "{{0:!<{}}}" + colour.REG
    else:
        style = "{{0:=<{}}}"
    print("\n" + style.format(len(msg)).format(""))
    print(msg)
    print(style.format(len(msg)).format(""))

def call_steamcmd(params):
    os.system("{} {}".format(STEAM_CMD, params))
    print("")

# Handle the password parameter.
def handle_password():
    global STEAM_PASS
    if STEAM_PASS:
        log("{GREEN}Using hardcoded password variable.{REG}")
    elif results.password_param:
        log("{GREEN}Using password from parameter.{REG}")
        STEAM_PASS = results.password_param
    else:
        STEAM_PASS = getpass("Enter your account password: ")
        if not STEAM_PASS:
            catch_account_fail("You must either provide a password with the -p parameter, enter it during runtime or hardcode it.")   

# Handle the username parameter.
def handle_username():
    global STEAM_USER
    if STEAM_USER:
        log("Using hardcoded username variable.")
    elif results.username_param:
        log("Will login as " + results.username_param)
        STEAM_USER = results.username_param
    else:
        STEAM_USER = input("Enter your account username: ")
        if not STEAM_USER:
            catch_account_fail("You must either provide a username with the -u parameter, enter it during runtime or hardcode it.")

def catch_account_fail(reason):
    log(colour.RED + reason + "\nTo download mods from the Arma3 workshop, you MUST use an account that owns Arma3." + colour.REG, 1)
    sys.exit()

# Use this to catch bad variables to make crashes more readable.
def catch_empty():
    print('do this later')

def handle_upgrade():
    if results.defer_upgrade_true:
        log("Defering server upgrade.")
    else:
        ("Updating A3 server ({})".format(A3_SERVER_ID))
        update_server()

def update_server():
    steam_cmd_params  = " +login {}".format(STEAM_USER, STEAM_PASS)
    steam_cmd_params += " +force_install_dir {}".format(A3_SERVER_DIR)
    steam_cmd_params += " +app_update {} validate".format(A3_SERVER_ID)
    steam_cmd_params += " +quit"

    call_steamcmd(steam_cmd_params)

def handle_modlist():
    modlist = ""
    if results.web_file_name:
        # Opens the url provided and saves it as a temporary file, then appends the name of the temporary file to the mod string.
        with request.urlopen(results.web_file_name) as response:
            with tempfile.NamedTemporaryFile(delete=False) as modlist:
                shutil.copyfileobj(response, modlist)
                modlist = modlist.name + ","
    if results.modfile_name:
        modlist = modlist + results.modfile_name
        print(modlist)
        # Converts the modlist string to a list.
        modlist = modlist.split(",")
        # Strips leading or trailing spaces or returns, but leaves all others. 
        # "  test " will become "test", " test file" will become "test file" etc.
        modlist = list(map(lambda x : x.strip(), modlist))
        print(modlist)
        get_mods_from_file(modlist)
    else:
        modlist = "mods.json"
        print(modlist)
        get_mods_from_file(modlist)

def get_mods_from_file(modlist):
    for x in modlist:
        try:
            with open(x, 'r') as handle:
            # Strip comments.
                fixed_json = ''.join(line for line in handle if not line.startswith('//'))
                modsfile = json.loads(fixed_json, object_hook=empty_strings2none)
                print(x)
            # Append to MODS_URL 
            MOD_URLS.update(modsfile)
        except:
            log('The file "{}" does not exist!'.format(x))

# Check if a mod needs an update.
def mod_needs_update(mod_id, path):
    if os.path.isdir(path):
        response = request.urlopen("{}/{}".format(WORKSHOP_CHANGELOG_URL, mod_id)).read()
        response = response.decode("utf-8")
        match = PATTERN.search(response)

        if match:
            updated_at = datetime.fromtimestamp(int(match.group(1)))
            created_at = datetime.fromtimestamp(os.path.getctime(path))

            return (updated_at >= created_at)

    return False

def get_mod_url_info():
    for mod_url, mod_name_override in MOD_URLS.items():
        # Set mod_id to the mod_id pulled from the mod_url
        mod_id = mod_id_pattern.search(mod_url)
        mod_id = mod_id.group(1)
        # If there is no mod_name_override get mod name from mod_url
        if mod_name_override is None:
            response = request.urlopen(mod_url).read()
            response = response.decode("utf-8")
            mod_name = mod_name_pattern.search(response)
            mod_name = mod_name.group(1)
        # Otherwise, apply the mod name override
        else:
            mod_name = mod_name_override
        # Clean mod names.
        mod_name = mod_name.lower()
        mod_name = re.sub('[^A-Za-z0-9]+', '_', mod_name)
        mod_name = "@" + mod_name
        print(mod_name)
        # Append mods to list.
        MODS.update({mod_name:mod_id})
        print(MODS)

def update_mods():
    for mod_name, mod_id in MODS.items():
        path = "{}/{}".format(A3_WORKSHOP_DIR, mod_id)

        # Check if mod needs to be updated
        if os.path.isdir(path):

            if mod_needs_update(mod_id, path):
                # Delete existing folder so that we can verify whether the
                # download succeeded
                shutil.rmtree(path)
            else:
                print("No update required for \"{}\" ({})... SKIPPING".format(mod_name, mod_id))
                continue

        # Keep trying until the download actually succeeded
        tries = 0
        while os.path.isdir(path) == False and tries < 10:
            log("Updating \"{}\" ({}) | {}".format(mod_name, mod_id, tries + 1))

            steam_cmd_params  = " +login {} {}".format(STEAM_USER, STEAM_PASS)
            ## steam_cmd_params  = " +login {}".format(STEAM_USER)
            steam_cmd_params += " +force_install_dir {}".format(A3_SERVER_DIR)
            steam_cmd_params += " +workshop_download_item {} {} validate".format(
                A3_WORKSHOP_ID,
                mod_id
            )
            steam_cmd_params += " +quit"

            call_steamcmd(steam_cmd_params)

            # Sleep for a bit so that we can kill the script if needed
            time.sleep(5)

            tries = tries + 1

        if tries >= 10:
            log("!! Updating {} failed after {} tries !!".format(mod_name, tries))

def lowercase_workshop_dir():
    os.system("(cd {} && find . -depth -exec rename -v 's/(.*)\/([^\/]*)/$1\/\L$2/' {{}} \;)".format(A3_WORKSHOP_DIR))

def create_mod_symlinks():
    for mod_name, mod_id in MODS.items():
        link_path = "{}/{}".format(A3_MODS_DIR, mod_name)
        real_path = "{}/{}".format(A3_WORKSHOP_DIR, mod_id)

        if os.path.isdir(real_path):
            if not os.path.islink(link_path):
                os.symlink(real_path, link_path)
                print("Creating symlink '{}'...".format(link_path))
        else:
            print("Mod '{}' does not exist! ({})".format(mod_name, real_path))

## Creates symlinks to keys, heavily based off:
## https://gist.github.com/Freddo3000/a5cd0494f649db75e43611122c9c3f15 by https://gist.github.com/Freddo3000
def symlink_mod_keys():
    mods_folders = os.listdir(A3_MODS_DIR)
    print("\n Checking if current keys are valid.")
    for key in os.listdir(A3_KEYS_DIR):
        key_dir = "{}/{}".format(A3_KEYS_DIR, key)
        if os.path.islink(key_dir) and not os.path.exists(key_dir):
            print("Unlinking old key, {}".format(key))
            os.unlink(key_dir)
        else:
            print("The key {} is valid.".format(key))
    print("\n Creating key symlinks.")
    for folder in mods_folders:
        modname = folder
        if "@" not in folder:
            mods_folders.remove(folder)
        else:
            folder = "{}/{}/keys/".format(A3_MODS_DIR, folder)
            if os.path.exists(folder):
                key_folder_list = os.listdir(folder)
                for item in key_folder_list:
                    if ".bikey" not in item[-6:]:
                        key_folder_list.remove
                    else:
                        folder = folder + item
                        key_path = "{}/{}".format(A3_KEYS_DIR, item)
                        if not os.path.exists(key_path):
                            print("Trying to create Key Symlink for {}, key file is called {}".format(modname, item))
                            os.symlink(folder, key_path)
                        else:
                            print("The key for {} already exists.".format(modname))
            else:
                print("\n ! The keys folder for {} doesn't exist. \n".format(modname))

# Saves a file, syntax is savefile("The name of the file", "What you want to save into the file", "true = append to the file with a datetime, false = overwrite file.")
def savefile(filename, filestring, log_true):
    if log_true:
        f = open( filename, 'a' )
        f.write( "\n" + str(dt.datetime.now())[:-7] + " " + str(filestring))
        f.close()
    else:
        f = open( filename, 'w' )
        f.write(str(filestring))
        f.close()

# Saves server starting param into launchparam.cfg, and logs server starting param into to launchparam.log.
def save_starting_params():
    starter = "./arma3server \"-name=" + server_name + "\" \"-config=" + server_cfg + "\" \"-mod="
    modstring = ""
    for mod_name, mod_id in MODS.items():
        modstring = modstring + mod_name + ";"
    modstring = modstring[:-1]
    starter = starter + modstring + "\""
    # Write the launch param to a file to be read by arma3server service. The file is called #launchparam.cfg
    savefile("launchparam.cfg", starter, False)
    # Write the launch param to a log to be stored for error checking.
    savefile("launchparam.log", starter, True)

def main():
    log("Starting Mod-Manager")
    handle_username()
    handle_password()
    if results.quick_install_true:
        quickInstall()
    handle_upgrade()

    log("Getting mod URL's from mods.json")
    handle_modlist()

    log("Trying to get mod info from URLs")
    get_mod_url_info()

    log("Updating mods")
    update_mods()

    log("Converting uppercase files/folders to lowercase...")
    lowercase_workshop_dir()

    log("Creating symlinks...")
    create_mod_symlinks()

    log("Symlinking Keys...")
    symlink_mod_keys()

    log("Saving server starting param into launchparam.cfg, and logging to launchparam.log.")
    save_starting_params()
    log("Note, the mods may not be in the correct order. Mods load left to right.")

main()