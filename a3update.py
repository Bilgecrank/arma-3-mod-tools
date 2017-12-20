#!/usr/bin/python3
import os
import os.path
import re
import shutil
import time

from datetime import datetime
from urllib import request

steam_cmd = "/home/steam/arma3/steam/steamcmd.sh"
steam_user = ""
steam_pass = ""

a3_server_id = "233780"
a3_server_dir = "/home/steam/arma3/install"
a3_workshop_id = "107410"

a3_workshop_dir = "{}/steamapps/workshop/content/{}".format(a3_server_dir, a3_workshop_id)
a3_mods_dir = "/home/steam/arma3/mods"

mods = {
    "@cba_a3":             "450814997",
    "@ace3":               "463939057",
    "@alive":              "620260972",
    "@cup_terrains_core":  "583496184",
    "@cup_terrains_maps":  "583544987",
    "@cup_weapons":        "497660133",
    "@cup_units":          "497661914",
    "@cup_vehicles":       "541888371"
}

# Update A3 server
steam_cmd_params  = " +login {} {}".format(steam_user, steam_pass)
steam_cmd_params += " +force_install_dir {}".format(a3_server_dir)
steam_cmd_params += " +app_update {} validate".format(a3_server_id)
steam_cmd_params += " +quit"

print("=========")
print("Updating A3 server ({})".format(a3_server_id))
print("=========")

os.system("{} {}".format(steam_cmd, steam_cmd_params))

time.sleep(5)

# Update mods
pattern = re.compile(r"workshopAnnouncement.*?<p id=\"(\d+)\">", re.DOTALL)
workshop_changelog_url = "https://steamcommunity.com/sharedfiles/filedetails/changelog/{}"

for key, value in mods.items():
    updated_at = None

    response = request.urlopen(workshop_changelog_url.format(value)).read()
    response = response.decode("utf-8")
    match = pattern.search(response)

    if match:
        updated_at = datetime.fromtimestamp(int(match.group(1)))

    path = "{}/steamapps/workshop/content/{}/{}".format(a3_server_dir, a3_workshop_id, value)

    # Check if mod needs to be updated
    if os.path.isdir(path):
        created_at = datetime.fromtimestamp(os.path.getctime(path))

        if updated_at != None and updated_at >= created_at:
            # Delete existing folder so that we can verify whether the download succeeded
            shutil.rmtree(path)
        else:
            continue

    # Keep trying until the download actually succeeded
    tries = 0
    while os.path.isdir(path) == False and tries < 10:
        print("")
        print("=========")
        print("Updating {} ({})".format(key, tries + 1))
        print("=========")

        steam_cmd_params  = " +login {} {}".format(steam_user, steam_pass)
        steam_cmd_params += " +force_install_dir {}".format(a3_server_dir)
        steam_cmd_params += " +workshop_download_item {} {} validate".format(
            a3_workshop_id,
            value
        )
        steam_cmd_params += " +quit"

        os.system("{} {}".format(steam_cmd, steam_cmd_params))

        # Sleep for a bit so that we can kill the script if needed
        time.sleep(5)

        tries = tries + 1

    if tries >= 10:
        print("Updating {} failed!".format(key))


print("")
print("=========")
print("Converting uppercase files/folders to lowercase...")
print("=========")
os.system("find {} -depth -exec rename -v 's/(.*)\/([^\/]*)/$1\/\L$2/' {{}} \;".format(a3_workshop_dir))

print("=========")
print("Creating symlinks...")
print("=========")
for key, value in mods.items():
    link_path = "{}/{}".format(a3_mods_dir, key)
    real_path = "{}/{}".format(a3_workshop_dir, value)

    if os.path.isdir(real_path):
        if not os.path.islink(link_path):
            os.symlink(real_path, link_path)
            print("Creating symlink '{}'...".format(link_path))
    else:
        print("Mod '{}' does not exist! ({})".format(key, real_path))
