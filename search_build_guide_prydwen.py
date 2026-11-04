
from colorama import Fore, Style, just_fix_windows_console

just_fix_windows_console()
import json
from datetime import datetime
from pathlib import Path

from prydwen_parser import *
from transpose_char_builds import transpose_to_artifact

if __name__ == "__main__":
    char_links = get_all_character_build_page()

    path = Path("char_builds.json")
    if path.exists():
        with open('char_builds.json') as f:
            builds = json.load(f)
    else:
        builds = {}

    for char_link in char_links:
        char = char_link.split('/')[-1]
        
        last_updated = get_last_profile_updated(char_link)
        if char in builds and datetime.fromisoformat(builds[char]['last_updated']) >= last_updated:
            print(f'{Fore.GREEN}{char}{Style.RESET_ALL} has not changed.')
            continue

        char_affixes = get_build_affixes(char_link)
        char_artifacts = get_build_artifacts(char_link)
        if char_artifacts is None: 
            char_artifacts = []
        char_builds = [{'affixes':char_affixes, 'artifacts':char_artifacts}]
        char_builds = [char_build for char_build in char_builds if char_build['affixes'] is not None]
        char_entry = {'builds': char_builds, 'last_updated':last_updated.isoformat()}
        if char in builds and char_builds == builds[char]['builds']:
            print(f'{Fore.BLUE}{char}{Style.RESET_ALL} has not changed.')
        elif char_affixes is None and char_artifacts == []:
            print(f'{Fore.RED}{char}{Style.RESET_ALL} has no build.')
        else:
            print(f'Updated {Fore.YELLOW}{char}{Style.RESET_ALL} build.')
        builds[char] = char_entry

    with open('char_builds.json', 'w') as f:
        json.dump(builds, f, indent=2)
    transpose_to_artifact('char_builds.json', 'artifact_builds.json')

