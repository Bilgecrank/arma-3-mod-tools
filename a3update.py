#!/usr/bin/python3
import os
import os.path
import shutil
import time

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
print("Updating A3 server ({})".format(a3_server_id));
print("=========")

os.system("{} {}".format(steam_cmd, steam_cmd_params))

# Update mods
for key, value in mods.items():
    path = "{}/steamapps/workshop/content/{}/{}".format(a3_server_dir, a3_workshop_id, value)

    # Delete existing folder so that we can verify whether the download succeeded
    if os.path.isdir(path):
        shutil.rmtree(path)

    # Keep trying until the download actually succeeded
    while os.path.isdir(path) == False:
        print("");
        print("=========")
        print("Updating {}".format(key));
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
        time.sleep(0.5)

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
