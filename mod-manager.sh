#!/usr/bin/python3

# MIT License
#
# Copyright (c) 2017 Marcel de Vries
#
# Modified by Connor Gowans
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
import shutil
import time

from datetime import datetime
from urllib import request

## Configuration information:
# The location of your steamcmd install.
STEAM_CMD = "/home/steam/steamcmd/steamcmd.sh"
# Your steam username.
STEAM_USER = "USERNAME"
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

def empty_strings2none(obj):
    for k, v in six.iteritems(obj):
        if v == '':
            obj[k] = None
    return obj

def log(msg):
    print("")
    print("{{0:=<{}}}".format(len(msg)).format(""))
    print(msg);
    print("{{0:=<{}}}".format(len(msg)).format(""))


def call_steamcmd(params):
    os.system("{} {}".format(STEAM_CMD, params))
    print("")


def update_server():
    steam_cmd_params  = " +login {}".format(STEAM_USER)
    steam_cmd_params += " +force_install_dir {}".format(A3_SERVER_DIR)
    steam_cmd_params += " +app_update {} validate".format(A3_SERVER_ID)
    steam_cmd_params += " +quit"

    call_steamcmd(steam_cmd_params)

def get_mods_from_file():
    # Pull mods from mods.json
    with open('mods.json', 'r') as handle:
        # Strip comments.
        fixed_json = ''.join(line for line in handle if not line.startswith('//'))
        modsfile = json.loads(fixed_json, object_hook=empty_strings2none)
    # Append to MODS_URL 
    MOD_URLS.update(modsfile)

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

            ## steam_cmd_params  = " +login {} {}".format(STEAM_USER, STEAM_PASS)
            steam_cmd_params  = " +login {}".format(STEAM_USER)
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

def get_starting_params():
    starter = "./arma3server \"-name=" + server_name + "\" \"-config=" + server_cfg + "\" \"-mods="
    modstring = ""
    for mod_name, mod_id in MODS.items():
        modstring = modstring + mod_name + ";"
    modstring = modstring[:-1]
    starter = starter + modstring + "\""
    print (starter)


log("Updating A3 server ({})".format(A3_SERVER_ID))
update_server()

log("Getting mod URL's from mods.json")
get_mods_from_file()

log("Trying to get mod info from URLs")
get_mod_url_info()

log("Updating mods")
update_mods()

log("Converting uppercase files/folders to lowercase...")
lowercase_workshop_dir()

log("Creating symlinks...")
create_mod_symlinks()

log("Here is a server starting command: ")
get_starting_params()
log("Note, the mods may not be in the correct order. Mods load left to right.")