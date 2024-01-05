# Arma 3 Mod Tools for Linux CLI

Rewrote a lot of the code to practice with different python libraries. This version of the code just focuses on pulling info from an Arma 3 Launcher HTML and using those links to install, update, and determine the load order of modpack. When running the arma3modtools.py with the argument -f <filename.html> it will do the following:
 
1. Pull a url list from an Arma 3 Launcher mod list html
2. Concurrently query each mod's Steam Workshop page
3. Check each page for **Required Items** and add these to the mod's info entry as dependencies.
4. Update all mods that need updating from the list
5. As for login credentials _once_. Steam Guard code is optionally asked for
6. Download all mods in the pack. Get some coffee if it's a big pack.
7. Create mod symlinks
8. Create key symlinks
9. Run a topological sort of mods and their dependencies and generate a string for the -mod= parameter in proper load order.
10. Generate/Update a shell script with the above -mod= parameter.
