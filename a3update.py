#!/usr/bin/python3
import os
import os.path
import re
import shutil
import time

from datetime import datetime
from urllib import request

#region Configuration
STEAM_CMD = "/home/steam/arma3/steam/steamcmd.sh"
STEAM_USER = ""
STEAM_PASS = ""

A3_SERVER_ID = "233780"
A3_SERVER_DIR = "/home/steam/arma3/install"
A3_WORKSHOP_ID = "107410"

A3_WORKSHOP_DIR = "{}/steamapps/workshop/content/{}".format(A3_SERVER_DIR, A3_WORKSHOP_ID)
A3_MODS_DIR = "/home/steam/arma3/mods"

MODS = {
    "@cba_a3":             "450814997",
    "@ace3":               "463939057",
    "@alive":              "620260972",
    "@cup_terrains_core":  "583496184",
    "@cup_terrains_maps":  "583544987",
    "@cup_weapons":        "497660133",
    "@cup_units":          "497661914",
    "@cup_vehicles":       "541888371"
}

PATTERN = re.compile(r"workshopAnnouncement.*?<p id=\"(\d+)\">", re.DOTALL)
WORKSHOP_CHANGELOG_URL = "https://steamcommunity.com/sharedfiles/filedetails/changelog"
#endregion

#region Functions
def log(msg):
    print("=========")
    print(msg);
    print("=========")


def call_steamcmd(params):
    os.system("{} {}".format(STEAM_CMD, params))
    print("")


def update_server():
    steam_cmd_params  = " +login {} {}".format(STEAM_USER, STEAM_PASS)
    steam_cmd_params += " +force_install_dir {}".format(A3_SERVER_DIR)
    steam_cmd_params += " +app_update {} validate".format(A3_SERVER_ID)
    steam_cmd_params += " +quit"

    call_steamcmd(steam_cmd_params)


def mod_needs_update(item_id, path):
    if os.path.isdir(path):
        response = request.urlopen("{}/{}".format(WORKSHOP_CHANGELOG_URL, item_id)).read()
        response = response.decode("utf-8")
        match = PATTERN.search(response)

        if match:
            updated_at = datetime.fromtimestamp(int(match.group(1)))
            created_at = datetime.fromtimestamp(os.path.getctime(path))

            return (updated_at >= created_at)

    return False


def update_mods():
    for key, value in MODS.items():
        path = "{}/{}".format(A3_WORKSHOP_DIR, value)

        # Check if mod needs to be updated
        if os.path.isdir(path):

            if mod_needs_update(value, path):
                # Delete existing folder so that we can verify whether the
                # download succeeded
                shutil.rmtree(path)
            else:
                print("No update required for \"{}\" ({})... SKIPPING".format(key, value))
                continue

        # Keep trying until the download actually succeeded
        tries = 0
        while os.path.isdir(path) == False and tries < 10:
            log("Updating {} ({})".format(key, tries + 1))

            steam_cmd_params  = " +login {} {}".format(STEAM_USER, STEAM_PASS)
            steam_cmd_params += " +force_install_dir {}".format(A3_SERVER_DIR)
            steam_cmd_params += " +workshop_download_item {} {} validate".format(
                A3_WORKSHOP_ID,
                value
            )
            steam_cmd_params += " +quit"

            call_steamcmd(steam_cmd_params)

            # Sleep for a bit so that we can kill the script if needed
            time.sleep(5)

            tries = tries + 1

        if tries >= 10:
            log("!! Updating {} failed after {} tries !!".format(key, tries))


def lowercase_workshop_dir():
    os.system("(cd {} && find . -depth -exec rename -v 's/(.*)\/([^\/]*)/$1\/\L$2/' {{}} \;)".format(A3_WORKSHOP_DIR))


def create_mod_symlinks():
    for key, value in MODS.items():
        link_path = "{}/{}".format(A3_MODS_DIR, key)
        real_path = "{}/{}".format(A3_WORKSHOP_DIR, value)

        if os.path.isdir(real_path):
            if not os.path.islink(link_path):
                os.symlink(real_path, link_path)
                print("Creating symlink '{}'...".format(link_path))
        else:
            print("Mod '{}' does not exist! ({})".format(key, real_path))
#endregion

log("Updating A3 server ({})".format(A3_SERVER_ID))
update_server()

log("Updating mods")
update_mods()

log("Converting uppercase files/folders to lowercase...")
lowercase_workshop_dir()

log("Creating symlinks...")
create_mod_symlinks()