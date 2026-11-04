import json
import statistics
from functools import lru_cache

import numpy as np

from artifact_scanner import (
    capture_genshin_screen,
    crop_artifact_desc_inv,
    parse_desc_img,
)
from debug import DEBUG_LOGGER
from rich_console import LogLevel, RichConsole

MAIN_AFFIX_VALUES = {
    'HP': [
        717, 920, 1123, 1326, 1530, 1733, 1936, 2139, 2342, 2545,
        2749, 2952, 3155, 3358, 3561, 3764, 3967, 4171, 4374, 4577, 4780
    ],
    'ATK': [
        47, 60, 73, 86, 100, 113, 126, 139, 152, 166,
        179, 192, 205, 219, 232, 245, 258, 272, 285, 298, 311
    ],
    'HP%': [
        7.0, 9.0, 11.0, 12.9, 14.9, 16.9, 18.9, 20.9, 22.8, 24.8,
        26.8, 28.8, 30.8, 32.8, 34.7, 36.7, 38.7, 40.7, 42.7, 44.6, 46.6
    ],
    'ATK%': [
        7.0, 9.0, 11.0, 12.9, 14.9, 16.9, 18.9, 20.9, 22.8, 24.8,
        26.8, 28.8, 30.8, 32.8, 34.7, 36.7, 38.7, 40.7, 42.7, 44.6, 46.6
    ],
    'DEF%': [
        8.7, 11.2, 13.7, 16.2, 18.6, 21.1, 23.6, 26.1, 28.6, 31.0,
        33.5, 36.0, 38.5, 40.9, 43.4, 45.9, 48.4, 50.8, 53.3, 55.8, 58.3
    ],
    'Energy Recharge%': [
        7.8, 10.0, 12.2, 14.4, 16.6, 18.8, 21.0, 23.2, 25.4, 27.6,
        29.8, 32.0, 34.2, 36.4, 38.6, 40.8, 43.0, 45.2, 47.4, 49.6, 51.8
    ],
    'Elemental Mastery': [
        28.0, 35.9, 43.8, 51.8, 59.7, 67.6, 75.5, 83.5, 91.4, 99.3,
        107.2, 115.2, 123.1, 131.0, 138.9, 146.9, 154.8, 162.7, 170.6, 178.6, 186.5
    ],
    'Pyro DMG Bonus%': [
        7.0, 9.0, 11.0, 12.9, 14.9, 16.9, 18.9, 20.9, 22.8, 24.8,
        26.8, 28.8, 30.8, 32.8, 34.7, 36.7, 38.7, 40.7, 42.7, 44.6, 46.6
    ],
    'Electro DMG Bonus%': [
        7.0, 9.0, 11.0, 12.9, 14.9, 16.9, 18.9, 20.9, 22.8, 24.8,
        26.8, 28.8, 30.8, 32.8, 34.7, 36.7, 38.7, 40.7, 42.7, 44.6, 46.6
    ],
    'Cryo DMG Bonus%': [
        7.0, 9.0, 11.0, 12.9, 14.9, 16.9, 18.9, 20.9, 22.8, 24.8,
        26.8, 28.8, 30.8, 32.8, 34.7, 36.7, 38.7, 40.7, 42.7, 44.6, 46.6
    ],
    'Hydro DMG Bonus%': [
        7.0, 9.0, 11.0, 12.9, 14.9, 16.9, 18.9, 20.9, 22.8, 24.8,
        26.8, 28.8, 30.8, 32.8, 34.7, 36.7, 38.7, 40.7, 42.7, 44.6, 46.6
    ],
    'Dendro DMG Bonus%': [
        7.0, 9.0, 11.0, 12.9, 14.9, 16.9, 18.9, 20.9, 22.8, 24.8,
        26.8, 28.8, 30.8, 32.8, 34.7, 36.7, 38.7, 40.7, 42.7, 44.6, 46.6
    ],
    'Anemo DMG Bonus%': [
        7.0, 9.0, 11.0, 12.9, 14.9, 16.9, 18.9, 20.9, 22.8, 24.8,
        26.8, 28.8, 30.8, 32.8, 34.7, 36.7, 38.7, 40.7, 42.7, 44.6, 46.6
    ],
    'Geo DMG Bonus%': [
        7.0, 9.0, 11.0, 12.9, 14.9, 16.9, 18.9, 20.9, 22.8, 24.8,
        26.8, 28.8, 30.8, 32.8, 34.7, 36.7, 38.7, 40.7, 42.7, 44.6, 46.6
    ],
    'Physical DMG Bonus%': [
        8.7, 11.2, 13.7, 16.2, 18.6, 21.1, 23.6, 26.1, 28.6, 31.0,
        33.5, 36.0, 38.5, 40.9, 43.4, 45.9, 48.4, 50.8, 53.3, 55.8, 58.3
    ],
    'CRIT Rate%': [
        4.7, 6.0, 7.3, 8.6, 9.9, 11.3, 12.6, 13.9, 15.2, 16.6,
        17.9, 19.2, 20.5, 21.8, 23.2, 24.5, 25.8, 27.1, 28.4, 29.8, 31.1
    ],
    'CRIT DMG%': [
        9.3, 12.0, 14.6, 17.3, 19.9, 22.5, 25.2, 27.8, 30.5, 33.1,
        35.7, 38.4, 41.0, 43.7, 46.3, 49.0, 51.6, 54.2, 56.9, 59.5, 62.2
    ],
    'Healing Bonus%': [
        5.4, 6.9, 8.4, 10.0, 11.5, 13.0, 14.5, 16.1, 17.6, 19.1,
        20.6, 22.1, 23.7, 25.2, 26.7, 28.2, 29.8, 31.3, 32.8, 34.3, 35.9
    ],
}

MINOR_AFFIX_INCREASE = {
    'HP':[209.13, 239.00, 268.88, 298.75],
    'ATK':[13.62, 15.56, 17.51, 19.45],
    'DEF':[16.20, 18.52, 20.83, 23.15],
    'HP%':[4.08, 4.66, 5.25, 5.83],
    'ATK%':[4.08, 4.66, 5.25, 5.83],
    'DEF%':[5.10, 5.83, 6.56, 7.29],
    'Elemental Mastery':[16.32, 18.65, 20.98, 23.31],
    'Energy Recharge%':[4.53, 5.18, 5.83, 6.48],
    'CRIT Rate%':[2.72, 3.11, 3.50, 3.89],
    'CRIT DMG%':[5.44, 6.22, 6.99, 7.77],
}

MINOR_AFFIX_AVG_INCREASE = {k: statistics.fmean(v) for k,v in MINOR_AFFIX_INCREASE.items()}

OFF_PIECE_PENALTY = 0.8
WEIGHT_DECAY = 0.5

def calc_max_permutations(artifact):
    upgrades_left = 5-(artifact.level//4)
    minor_affixes = artifact.minor_affixes
    minor_affix_values = []
    minor_affix_keys = []
    for affix in minor_affixes:
        if not affix.activated: 
            upgrades_left -= 1
        minor_affix_values.append(affix.value)
        minor_affix_keys.append(affix.name)

    values = np.array([MINOR_AFFIX_INCREASE[k] for k in minor_affix_keys])
    upgrade_matrix = np.zeros((16, 4))
    upgrade_matrix[np.arange(16), np.repeat(np.arange(4), 4)] = values.flatten()

    if upgrades_left == 0:
        upgrade_permutations = np.zeros((1,4))
    else:
        upgrade_permutations = upgrade_matrix
        for _ in range(upgrades_left - 1):
            upgrade_permutations = (upgrade_permutations[:, None, :] + upgrade_matrix[None, :, :]).reshape(-1, upgrade_matrix.shape[1])
    
    minor_affix_permutations = upgrade_permutations + np.array(minor_affix_values)

    for i, key in enumerate(minor_affix_keys):
        minor_affix_permutations[:,i] /= MINOR_AFFIX_AVG_INCREASE[key]
    return minor_affix_keys, minor_affix_permutations

@lru_cache(maxsize=10)
def get_max_score(minor_affix_prios):
    if len(minor_affix_prios) == 0:
        return 0
    prios = sorted(minor_affix_prios)[:4]
    score = WEIGHT_DECAY**(prios[0]-1)*4
    for prio in prios:
        score += WEIGHT_DECAY**(prio-1)
    return score

def score_minor_affixes(minor_affixes, minor_affix_prio, off_piece=False):
    normalised_minor_affix_values = {k:v/MINOR_AFFIX_AVG_INCREASE[k] for k,v in minor_affixes.items()}
    max_score = get_max_score(tuple(minor_affix_prio.values()))
    if max_score == 0: 
        return 1
    score = 0
    for affix, value in normalised_minor_affix_values.items():
        if affix not in minor_affix_prio: continue
        weight = WEIGHT_DECAY ** (minor_affix_prio[affix] - 1)
        if off_piece:
            score += weight*value*OFF_PIECE_PENALTY
        else:
            score += weight*value
    normalised_score = score/max_score
    return normalised_score

def get_top_percentile_score(minor_affix_keys, minor_affix_permutations, minor_affix_prio, off_piece=False, percentile=0.85):
    max_score = get_max_score(tuple(minor_affix_prio.values()))
    if max_score == 0: 
        if off_piece: return 0
        else: return 1

    weights = np.array([WEIGHT_DECAY ** (minor_affix_prio[key] - 1) if key in minor_affix_prio else 0 for key in minor_affix_keys], dtype=np.float64)
    if off_piece: weights *= OFF_PIECE_PENALTY

    scores = minor_affix_permutations @ weights
    scores /= max_score

    top_percentile_score = np.percentile(scores, 100*(percentile))
    return top_percentile_score

def cut_main_stat_from_prios(artifact, minor_affix_prios):
    minor_affix_prios = dict(minor_affix_prios)
    main_stat_name = artifact.main_affix.name
    if main_stat_name in minor_affix_prios:
        del minor_affix_prios[main_stat_name]
    return minor_affix_prios

@lru_cache(maxsize=10)
def calc_artifact_potential(artifact, artifact_builds, percentile=0.85):
    RichConsole.log('Calculating Potential', level=LogLevel.INFO, logger=DEBUG_LOGGER)
    keys, permutations = calc_max_permutations(artifact)
    
    character_potentials = {}
    for artifact_key, builds in artifact_builds.items():
        off_piece = artifact_key != artifact.name
        for build in builds:
            if artifact.slot in build['affixes']['main_affix']:
                main_affixes = build['affixes']['main_affix'][artifact.slot]
                if artifact.main_affix.name not in main_affixes: continue

            minor_affix_prios = build['affixes']['minor_affix'].copy()
            minor_affix_prios = cut_main_stat_from_prios(artifact, minor_affix_prios)

            score = get_top_percentile_score(keys, permutations, minor_affix_prios, off_piece=off_piece, percentile=percentile)

            for char in build['characters']:
                if char not in character_potentials: character_potentials[char] = {'score':score,'off_piece':off_piece}
                if score > character_potentials[char]['score']:
                    character_potentials[char] = {'score': score,'off_piece':off_piece}
    return character_potentials

def filter_potentials(potentials, threshold):
    filtered_potentials = [{'character':k,'score':v['score'],'offpiece':v['off_piece']} for k,v in potentials.items() if v['score'] >= threshold]
    filtered_potentials.sort(key=lambda e:e['score'], reverse=True)
    return filtered_potentials

if __name__ == '__main__':
    screen = capture_genshin_screen()
    desc_img = crop_artifact_desc_inv(screen)
    artifact = parse_desc_img(desc_img)
    with open('artifact_builds.json') as f:
        artifact_builds = json.load(f)
    character_potentials = calc_artifact_potential(artifact, artifact_builds)
    character_potentials = filter_potentials(character_potentials, 0.6)
    print(character_potentials)
