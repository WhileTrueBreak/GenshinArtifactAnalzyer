import re
from datetime import datetime
from functools import lru_cache

import requests
from bs4 import BeautifulSoup

MAIN_AFFIXES = {
    'HP%':'HP%',
    'ATK%':'ATK%',
    'DEF%':'DEF%',
    'Elemental Mastery':'Elemental Mastery',
    'Energy Recharge':'Energy Recharge%',
    'Anemo DMG':'Anemo DMG%',
    'Geo DMG':'Geo DMG%',
    'Electro DMG':'Electro DMG%',
    'Dendro DMG':'Dendro DMG%',
    'Hydro DMG':'Hydro DMG%',
    'Pyro DMG':'Pyro DMG%',
    'Cryo DMG':'Cryo DMG%',
    'Physical DMG':'Physical DMG%',
    'CRIT Rate':'CRIT Rate%',
    'CRIT DMG':'CRIT DMG%',
    'Healing%':'Healing Bonus%',
}

MINOR_AFFIXES = {
    'HP':'HP',
    'ATK':'ATK',
    'DEF':'DEF',
    'HP%':'HP%',
    'ATK%':'ATK%',
    'DEF%':'DEF%',
    'EM':'Elemental Mastery',
    'ER':'Energy Recharge%',
    'CRIT Rate':'CRIT Rate%',
    'Crit DMG':'CRIT DMG%',
}

MINOR_AFFIX_LOOKUP = {key.casefold(): value for key, value in MINOR_AFFIXES.items()}
MINOR_AFFIX_PATTERN = re.compile(rf'(?<!\w)({"|".join(re.escape(key) for key in sorted(MINOR_AFFIXES, key=len, reverse=True))})(?!\w)', re.IGNORECASE)

class ArtifactParseError(Exception):
    pass

@lru_cache(maxsize=2)
def get_url_soup(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        return soup
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None

@lru_cache
def get_all_artifacts(casefold=False):
    url = 'https://www.prydwen.gg/genshin-impact/artifacts'
    soup = get_url_soup(url)
    artifacts_soup = soup.find('div', class_='genshin-artifact-container')
    artifact_soups = artifacts_soup.find_all('span', class_='genshin-card-name')
    artifacts = []
    for artifact_soup in artifact_soups:
        if casefold:
            artifacts.append(artifact_soup.text.strip().casefold())
        else:
            artifacts.append(artifact_soup.text.strip())
    return artifacts

def get_all_character_build_page():
    url = 'https://www.prydwen.gg/genshin-impact/characters'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        character_elements = soup.find_all('a', class_='avatar-card')
        character_links = []
        for element in character_elements:
            character_links.append(element['href'])
        return character_links

    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None

def get_build_affixes(char_link):
    url = f'https://www.prydwen.gg{char_link}'
    soup = get_url_soup(url)
    if not soup: return None
    main_affix_soup = soup.find('div', class_='build-main-stat-grid')
    if not main_affix_soup: return None
    main_affix_soups = main_affix_soup.find_all('div', class_='main-stat-row')
    main_affix_dict = {}
    for artifact_soup in main_affix_soups:
        slot = artifact_soup.find('div', class_='main-stat-slot').text
        main_affixes = parse_main_affixes(artifact_soup.find('div', class_='main-stat-options').find('strong').text)
        main_affix_dict[slot] = main_affixes
    minor_affix_soup = soup.find('div', class_='stat-priority-strip')
    minor_affix_soups = minor_affix_soup.find_all('strong', class_='stat-priority-item')
    minor_affix_prio_soups = minor_affix_soup.find_all('span', class_='priority-arrow')
    minor_affix_prios = [1]
    for prio_soup in minor_affix_prio_soups:
        text = prio_soup.text
        increase = text.count('>')
        minor_affix_prios.append(minor_affix_prios[-1]+increase)
    if len(minor_affix_prios) != len(minor_affix_soups):
        raise ArtifactParseError("Mismatched number of prios and minor affixes.") 
    minor_affix_dict = {}
    for i, minor_affix_soup in enumerate(minor_affix_soups):
        parsed_minor_affix_text = parse_minor_affixes(minor_affix_soup.text)
        if len(parsed_minor_affix_text) > 1:
            print(minor_affix_soup.text)
            print(parsed_minor_affix_text)
            raise ArtifactParseError("Found more than 1 minor affixes in text") 
        if len(parsed_minor_affix_text) == 0:
            print(minor_affix_soup.text)
            print(parsed_minor_affix_text)
            raise ArtifactParseError("No minor affixes found in text") 
        minor_affix_dict[parsed_minor_affix_text[0]] = minor_affix_prios[i]   
    output = {
        'minor_affix': minor_affix_dict,
        'main_affix': main_affix_dict
    }
    return output

def get_build_artifacts(char_link):
    valid_artifacts = get_all_artifacts(casefold=True)
    url = f'https://www.prydwen.gg{char_link}'
    soup = get_url_soup(url)
    if not soup: return None
    artifact_build_soup = soup.find('div', class_='artifact-rank-table')
    if not artifact_build_soup: return None
    artifact_soups = artifact_build_soup.find_all('div', class_='build-rank-row')
    artifacts = []
    for artifact_soup in artifact_soups:
        artifact = artifact_soup.find('span', class_='build-item-name').find('strong').text.strip()
        if artifact.casefold() not in valid_artifacts: continue # skips 2 pc combos why is 2pc text so in consistent
        artifacts.append(artifact)
    return artifacts

def get_last_profile_updated(char_link):
    url = f"https://www.prydwen.gg{char_link}"
    soup = get_url_soup(url)
    if not soup: return None
    date_str = soup.find('div', class_='hero-copy').find('p', class_='freshness').find('strong').text
    return datetime.strptime(date_str, "%B %d, %Y")

def parse_main_affixes(text):
    parsed_list = []
    for main_affix_key, main_affix_value in MAIN_AFFIXES.items():
        if main_affix_key.casefold() not in text.casefold(): continue
        parsed_list.append(main_affix_value)
    return parsed_list

def parse_minor_affixes(text):
    return [MINOR_AFFIX_LOOKUP[match.casefold()] for match in MINOR_AFFIX_PATTERN.findall(text)]
