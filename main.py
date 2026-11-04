import json
import os
import threading
import time

import cv2
from frozendict import frozendict
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text

from artifact_desc_finder import crop_desc
from artifact_scanner import capture_genshin_screen, parse_desc_img
from debug import DEBUG_LOGGER
from rich_console import LogLevel, RichConsole
from state import STATE
from upgrade_scryer import calc_artifact_potential, filter_potentials

FILTER_THRESHOLD = 0.50

def freeze(obj):
    if isinstance(obj, dict):
        return frozendict({k: freeze(v) for k, v in obj.items()})
    elif isinstance(obj, list):
        return tuple(freeze(v) for v in obj)
    return obj

def get_score_color(score):
    if score >= 1:
        return '#dd22f2'
    elif score >= 0.8:
        return '#58e61c'
    elif score >= 0.6:
        return '#e6b01c'
    else:
        return '#b31414'

def save_desc_img(img):
    folder = 'res/desc_bank'
    i = 1
    while os.path.exists(os.path.join(folder, f"{i}.png")):
        i += 1
    path = os.path.join(folder, f"{i}.png")
    cv2.imwrite(path, cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
    return path

def update():
    with open('artifact_builds.json') as f:
        artifact_builds = freeze(json.load(f))
    while True:
        try:
            RichConsole.log('Waiting...', level=LogLevel.INFO)
            RichConsole.log('Reading Screen...', level=LogLevel.INFO)
            screen = capture_genshin_screen()
            if screen is None: 
                RichConsole.log('No screen found', level=LogLevel.WARNING)
                STATE['artifact'] = None
                STATE['character_potentials'] = None
                continue
            st = time.time()
            desc_img, conf, _ = crop_desc(screen)
            RichConsole.log(f'Crop time: {(time.time()-st)*1000:.2f} ms', level=LogLevel.INFO)
            if conf < 0.9: 
                STATE['artifact'] = None
                STATE['character_potentials'] = None
                continue
            RichConsole.log('Parsing Artifact...', level=LogLevel.INFO)
            artifact = parse_desc_img(desc_img)
            if artifact == STATE['artifact']:
                continue
            STATE['artifact'] = artifact
            STATE['character_potentials'] = None
            if artifact is None: 
                STATE['potential_status'] = 'No artifact found'
                RichConsole.log('No artifact found', level=LogLevel.WARNING)
                continue
            STATE['potential_status'] = 'Calculating potentials'
            save_desc_img(desc_img)
            RichConsole.log('Calculating Potentials...', level=LogLevel.INFO)
            character_potentials = calc_artifact_potential(artifact, artifact_builds)
            character_potentials = filter_potentials(character_potentials, FILTER_THRESHOLD)
            if not character_potentials:
                STATE['potential_status'] = 'No matching characters'
            STATE['character_potentials'] = character_potentials
        except Exception as e:  # noqa: BLE001
            RichConsole.log(f'Error: {e}', level=LogLevel.EXCEPTION, logger=DEBUG_LOGGER)
            time.sleep(0.5)

def render_artifact_panel():
    artifact = STATE['artifact']

    if artifact is None:
        return Panel(
            Text('No artifact selected', justify='center', style='dim'),
            title='Current Artifact',
            border_style='#ff4d76',
            expand=True
        )

    content = Text()

    content.append(f'Name:  {artifact.name}\n')
    content.append(f'Slot:  {artifact.slot}\n')
    content.append(f'Level: +{artifact.level}\n\n')

    content.append('Main Affix:\n', style='bold')
    content.append(f'   {artifact.main_affix.name}: {artifact.main_affix.value}\n\n', style='#36ffbc')

    content.append('Minor Affixes:\n', style='bold')

    for affix in artifact.minor_affixes:
        style = '#36ffbc' if affix.activated else '#ff7236'
        content.append(f'   {affix.name}: {affix.value}',style=style)
        if not affix.activated:
            content.append(' (Unactivated)',style=style)
        content.append('\n')

    return Panel(content, title='Current Artifact', border_style='#ff4d76', expand=True)

def render_potentials_panel():
    character_potentials = STATE['character_potentials']
    table = Table(show_header=True, expand=True, box=None)
    table.add_column('Character', ratio=1, no_wrap=True, style='#ff4d76')
    table.add_column('Potential', ratio=2, no_wrap=True, style='#ff4d76')
    table.add_column("Score", justify="right")
    table.add_row('','')
    if character_potentials is None:
        character_potentials = []
    for potential in character_potentials:
        name_style = '#e0c3b6' if not potential['offpiece'] else '#91786d'
        name = Text(potential['character'].replace('-', ' ').title(), style=name_style)
        if potential['offpiece']:
            name.append(' off', style='#525252')

        score = float(potential['score'])
        color = get_score_color(score)
        bar = ProgressBar(
            total=1.1,
            completed=max(0, min(score, 1.1)),
            width=25,
            complete_style=color,
            finished_style=color,
        )
        score_text = Text(f'{score*100:.1f}%', style=color)
        table.add_row(name, bar, score_text)
    if not character_potentials:
        table.add_row(Text(''), Text(STATE['potential_status'], style='#525252'), Text(''))
    return Panel(
        table,
        title='Character Potentials',
        border_style='#ff4d76',
        expand=True
    )

def render():
    layout = Layout()
    layout.split_row(
        Layout(render_potentials_panel(), ratio=2),
        Layout(name="right")
    )
    layout["right"].split_column(
        Layout(render_artifact_panel(), ratio=4),
        Layout(RichConsole.render_console_panel(), ratio=1)
    )

    return layout

if __name__ == '__main__':
    RichConsole.set_max_messages(7)
    console = Console()

    update_thread = threading.Thread(target=update, daemon=True)
    update_thread.start()

    try:
        with Live(render(), console=console, screen=True, refresh_per_second=10, vertical_overflow="crop") as live:
            while update_thread.is_alive():
                live.update(render())
                time.sleep(0.1)
            live.update(render())
    except KeyboardInterrupt:
        console.print('Exiting...')