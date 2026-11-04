import re
import threading
import time

import cv2
import mss
import numpy as np
import pygetwindow as gw
from colorama import Fore, Style
from PIL import Image
from strsimpy.levenshtein import Levenshtein
from tesserocr import PSM, PyTessBaseAPI

from prydwen_parser import get_all_artifacts

# tesseract_path = os.path.abspath('Tesseract-OCR/tesseract.exe')
# pytesseract.pytesseract.tesseract_cmd = tesseract_path
LEVENSHTEIN_LOCK = threading.Lock()
LEVENSHTEIN = Levenshtein()

ARTIFACT_LIST = get_all_artifacts()
ARTIFACT_SLOTS = {'flower of life':'Flower', 'plume of death':'Plume', 'sands of eon':'Sands', 'goblet of eonothem':'Goblet', 'circlet of logos':'Circlet'}
ARTIFACT_MAIN_AFFIX = ['HP','ATK','DEF','Elemental Mastery','Energy Recharge','Physical DMG Bonus','Anemo DMG Bonus','Geo DMG Bonus','Electro DMG Bonus','Dendro DMG Bonus','Hydro DMG Bonus','Pyro DMG Bonus','Cyro DMG Bonus','CRIT Rate','CRIT DMG','Healing Bonus']
ARTIFACT_MINOR_AFFIX = ['HP','ATK','DEF','Elemental Mastery','Energy Recharge','CRIT Rate','CRIT DMG']

TESSEROCR_LOCK = threading.Lock()
TESSEROCR_API = PyTessBaseAPI(path="tessdata", lang="genshin_eng")
TESSEROCR_DEFAULTS = {"tessedit_char_whitelist": ""}

SCT = mss.MSS()
GENSHIN_WINDOW = None

class StatLine:
    def __init__(self, name, value, activated=True):
        self.name = name
        self.value = value
        self.activated = activated

    def __str__(self):
        return f'{Fore.CYAN if self.activated else Fore.RED}{self.name}: {self.value}{Style.RESET_ALL}'
    
    def __eq__(self, other):
        return self.name == other.name and self.value == other.value and self.activated == other.activated
    
    def __hash__(self):
        return hash((self.name, self.value, self.activated))

class Artifact:
    def __init__(self, name, slot, level, main_affix, minor_affixes):
        self.name = name
        self.slot = slot
        self.level = level
        self.main_affix = StatLine(main_affix['name'], main_affix['value'])
        self.minor_affixes = []
        for minor_affix in minor_affixes:
            self.minor_affixes.append(StatLine(minor_affix['name'], minor_affix['value'], minor_affix['activated']))
        self.minor_affixes = tuple(self.minor_affixes)

    def __str__(self):
        s1 = f'Name: {self.name}\nSlot: {self.slot}\nLevel: {self.level}\n'
        s2 = f'Main Affix:\n\t{self.main_affix!s}\n'
        s3 = 'Minor Affixes:\n'
        for minor_affix in self.minor_affixes:
            s3 +=  f'\t{minor_affix!s}\n'
        return s1+s2+s3
    
    def __eq__(self, other):
        if not isinstance(other, Artifact):
            return NotImplemented
        if not (self.name == other.name and self.slot == other.slot and self.level == other.level): return False
        if self.main_affix != other.main_affix: return False
        for i in range(4):
            if self.minor_affixes[i] != other.minor_affixes[i]: return False
        return True
    
    def __hash__(self):
        return hash((self.name, self.slot, self.level, hash(self.main_affix), hash(self.minor_affixes)))

def is_window_valid(window):
    if not window:
        return False

    try:
        return window._hWnd in [w._hWnd for w in gw.getAllWindows()]
    except Exception:  # noqa: BLE001
        return False

def capture_genshin_screen():
    global GENSHIN_WINDOW

    if not is_window_valid(GENSHIN_WINDOW):
        windows = gw.getWindowsWithTitle("Genshin Impact")
        GENSHIN_WINDOW = windows[0] if windows else None

    if GENSHIN_WINDOW:
        region = {
            "left": GENSHIN_WINDOW.left,
            "top": GENSHIN_WINDOW.top,
            "width": GENSHIN_WINDOW.width,
            "height": GENSHIN_WINDOW.height
        }

        screenshot = SCT.grab(region)
        return np.array(screenshot)[:, :, :3][:, :, ::-1].copy()

    return None

def crop_artifact_desc_inv(img):
    x_range = (1308, 1800)
    y_range = (120, 959)
    return img[y_range[0]:y_range[1],x_range[0]:x_range[1]]

def crop_artifact_desc_detail(img):
    x_range = (1380, 1872)
    y_range = (120, 959)
    return img[y_range[0]:y_range[1],x_range[0]:x_range[1]]

def crop_artifact_desc(img):
    crop_margin = 10
    lower = 66
    upper = 230
    grad = 255/(upper-lower)
    details_button_img = img[1000:1036,1630:1771]
    grey_details_button_img = cv2.cvtColor(details_button_img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    grey_details_button_img = np.clip(grad*(grey_details_button_img-lower),0,255).astype(np.uint8)
    
    ys, xs = np.where(grey_details_button_img<200)
    if len(xs) < 10: return crop_artifact_desc_detail(img)
    min_x, max_x = max(np.min(xs)-crop_margin,0), min(np.max(xs)+crop_margin,grey_details_button_img.shape[1]-1)
    min_y, max_y = max(np.min(ys)-crop_margin,0), min(np.max(ys)+crop_margin,grey_details_button_img.shape[0]-1)
    grey_details_button_img = grey_details_button_img[min_y:max_y,min_x:max_x].squeeze().astype(np.uint8)
    # cv2.imwrite('res/inv_button.png', grey_details_button_img)
    detected_string = image_to_string(Image.fromarray(grey_details_button_img), psm=PSM.SINGLE_LINE).strip().casefold()
    if detected_string is None: return crop_artifact_desc_detail(img)
    closest_text = None
    best_distance = 3
    for text in ['details', 'enhance']:
        with LEVENSHTEIN_LOCK:
            distance = LEVENSHTEIN.distance(detected_string, text.casefold())
        if distance > best_distance: continue
        best_distance = distance
        closest_text = text
    if closest_text is None: return crop_artifact_desc_detail(img)
    return crop_artifact_desc_inv(img)

def image_to_string(pil_image, psm=PSM.SINGLE_LINE, variables=None):
    with TESSEROCR_LOCK:
        TESSEROCR_API.SetPageSegMode(psm)
        for name, value in TESSEROCR_DEFAULTS.items():
            TESSEROCR_API.SetVariable(name, value)
        if variables is not None:
            for variable in variables:
                TESSEROCR_API.SetVariable(variable[0], variable[1])
        TESSEROCR_API.SetImage(pil_image)
        text = TESSEROCR_API.GetUTF8Text().strip()
    return text

def parse_desc_img_artifact_name(desc_img, crop_margin=2, distance_threshold=4):
    lower = 127
    upper = 86
    grad = 255/(upper-lower)
    lower_desc_img = desc_img[284:768,:]
    green_ratio = ((lower_desc_img[:,:,1].astype(float) / (np.sum(lower_desc_img, axis=2) + 1e-6))*255).squeeze()
    grey_name_img = np.clip(grad*(green_ratio-lower),0,255).astype(np.uint8)
    ys, xs = np.where(grey_name_img<200)
    if len(xs) < 10: return None
    min_x, max_x = max(np.min(xs)-crop_margin,0), min(np.max(xs)+crop_margin,grey_name_img.shape[1]-1)
    min_y, max_y = max(np.min(ys)-crop_margin,0), min(np.max(ys)+crop_margin,grey_name_img.shape[0]-1)
    grey_name_img = grey_name_img[min_y:max_y,min_x:max_x].squeeze().astype(np.uint8)
    # cv2.imwrite('res/artifact_name.png', grey_name_img)
    detected_string = image_to_string(Image.fromarray(grey_name_img), psm=PSM.SINGLE_LINE).strip().casefold()[:-1]
    closest_artifact = None
    best_distance = distance_threshold
    for artifact in ARTIFACT_LIST:
        with LEVENSHTEIN_LOCK:
            distance = LEVENSHTEIN.distance(detected_string, artifact.casefold())
        if distance > best_distance: continue
        best_distance = distance
        closest_artifact = artifact
    return closest_artifact

def parse_desc_img_slot(desc_img, crop_margin=2, distance_threshold=4):
    lower = 255
    upper = 100
    grad = 255/(upper-lower)
    slot_text_img = desc_img[66:100,:250]
    grey_slot_text_img = cv2.cvtColor(slot_text_img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    grey_slot_text_img = np.clip(grad*(grey_slot_text_img-lower),0,255).astype(np.uint8)

    ys, xs = np.where(grey_slot_text_img<200)
    if len(xs) < 10: return None
    min_x, max_x = max(np.min(xs)-crop_margin,0), min(np.max(xs)+crop_margin,grey_slot_text_img.shape[1]-1)
    min_y, max_y = max(np.min(ys)-crop_margin,0), min(np.max(ys)+crop_margin,grey_slot_text_img.shape[0]-1)
    grey_slot_text_img = grey_slot_text_img[min_y:max_y,min_x:max_x].squeeze().astype(np.uint8)
    # cv2.imwrite('res/artifact_slot.png', grey_slot_text_img)
    detected_string = image_to_string(Image.fromarray(grey_slot_text_img), psm=PSM.SINGLE_LINE).strip().casefold()
    closest_slot = None
    best_distance = distance_threshold
    for slot in ARTIFACT_SLOTS:
        with LEVENSHTEIN_LOCK:
            distance = LEVENSHTEIN.distance(detected_string, slot.casefold())
        if distance > best_distance: continue
        best_distance = distance
        closest_slot = slot
    if closest_slot is None: return None
    return ARTIFACT_SLOTS[closest_slot]

def parse_desc_img_main_affix(desc_img, crop_margin=2, distance_threshold=2):
    # parse main affix value
    lower = 255
    upper = 144
    grad = 255/(upper-lower)
    main_affix_value_img = desc_img[180:230,:250]
    grey_main_affix_value_img = cv2.cvtColor(main_affix_value_img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    grey_main_affix_value_img = np.clip(grad*(grey_main_affix_value_img-lower),0,255).astype(np.uint8)
    ys, xs = np.where(grey_main_affix_value_img<200)
    if len(xs) < 10: return None
    min_x, max_x = max(np.min(xs)-crop_margin,0), min(np.max(xs)+crop_margin,grey_main_affix_value_img.shape[1]-1)
    min_y, max_y = max(np.min(ys)-crop_margin,0), min(np.max(ys)+crop_margin,grey_main_affix_value_img.shape[0]-1)
    grey_main_affix_value_img = grey_main_affix_value_img[min_y:max_y,min_x:max_x].squeeze().astype(np.uint8)
    # cv2.imwrite('res/artifact_main_affix_value.png', grey_main_affix_value_img)
    detected_affix_value = image_to_string(Image.fromarray(grey_main_affix_value_img), psm=PSM.SINGLE_LINE, variables=[('tessedit_char_whitelist', '0123456789%.,')]).strip().casefold()
    detected_affix_value = detected_affix_value.replace(',','')

    #parse main affix name
    lower = 191
    upper = 129
    grad = 255/(upper-lower)
    main_affix_name_img = desc_img[150:180,:250]
    grey_main_affix_name_img = cv2.cvtColor(main_affix_name_img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    grey_main_affix_name_img = np.clip(grad*(grey_main_affix_name_img-lower),0,255).astype(np.uint8)
    ys, xs = np.where(grey_main_affix_name_img<200)
    if len(xs) < 10: return None
    min_x, max_x = max(np.min(xs)-crop_margin,0), min(np.max(xs)+crop_margin,grey_main_affix_name_img.shape[1]-1)
    min_y, max_y = max(np.min(ys)-crop_margin,0), min(np.max(ys)+crop_margin,grey_main_affix_name_img.shape[0]-1)
    grey_slot_text_img = grey_main_affix_name_img[min_y:max_y,min_x:max_x].squeeze().astype(np.uint8)
    # cv2.imwrite('res/artifact_main_affix_name.png', grey_slot_text_img)
    detected_affix_name = image_to_string(Image.fromarray(grey_slot_text_img),psm=PSM.SINGLE_LINE).strip().casefold()
    closest_affix_name = None
    best_distance = distance_threshold
    for main_affix in ARTIFACT_MAIN_AFFIX:
        with LEVENSHTEIN_LOCK:
            distance = LEVENSHTEIN.distance(detected_affix_name, main_affix.casefold())
        if distance > best_distance: continue
        best_distance = distance
        closest_affix_name = main_affix
    if closest_affix_name is None: return None
    if detected_affix_value.endswith('%'):
        closest_affix_name += '%'
        detected_affix_value = detected_affix_value[:-1]
    return {'name':closest_affix_name,'value':detected_affix_value}

def parse_single_minor_affix(affix_img, fname, crop_margin=2, distance_threshold=2):
    # lower = 156
    lower = 146
    upper = 230
    grad = 255/(upper-lower)
    grey_minor_affix_1_img = cv2.cvtColor(affix_img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    grey_minor_affix_1_img = np.clip(grad*(grey_minor_affix_1_img-lower),0,255)

    ys, xs = np.where(grey_minor_affix_1_img<200)
    if len(xs) < 10: return None
    min_x, max_x = max(np.min(xs)-crop_margin,0), min(np.max(xs)+crop_margin,grey_minor_affix_1_img.shape[1]-1)
    min_y, max_y = max(np.min(ys)-crop_margin,0), min(np.max(ys)+crop_margin,grey_minor_affix_1_img.shape[0]-1)
    grey_minor_affix_1_img = grey_minor_affix_1_img[min_y:max_y,min_x:max_x].squeeze().astype(np.uint8)

    # cv2.imwrite(fname, grey_minor_affix_1_img)
    detected_minor_affix = image_to_string(Image.fromarray(grey_minor_affix_1_img), psm=PSM.SINGLE_BLOCK).strip().casefold()
    detected_minor_affix = detected_minor_affix.replace('\n',' ')

    minor_affix_parser = re.compile(r'^(. )?([\w ]+)\+([\d\.%]+)( \(unactivated\))?$')
    match = re.search(minor_affix_parser, detected_minor_affix)
    if match is None: return None
    
    closest_affix_name = None
    best_distance = distance_threshold
    for minor_affix in ARTIFACT_MINOR_AFFIX:
        with LEVENSHTEIN_LOCK:
            distance = LEVENSHTEIN.distance(match.group(2), minor_affix.casefold())
        if distance > best_distance: continue
        best_distance = distance
        closest_affix_name = minor_affix
    if closest_affix_name is None: return None
    affix_value = match.group(3)
    if affix_value.endswith('%'):
        closest_affix_name += '%'
        affix_value = affix_value[:-1]
    is_activated = match.group(4) is None

    minor_affix = {'name':closest_affix_name,'value':float(affix_value),'activated':is_activated}
    return minor_affix

def parse_desc_img_minor_affix(desc_img, green_threshold=0.36, crop_margin=2, distance_threshold=4):
    # find lower bound
    lower_desc_img = desc_img[284:768,:]
    green_ratio = lower_desc_img[:,:,1].astype(float) / (np.sum(lower_desc_img, axis=2) + 1e-6)
    green_mask = green_ratio > green_threshold
    ys, _ = np.where(green_mask)
    if len(ys) < 10: return None
    lower_bound = max(np.min(ys)-crop_margin,0)+284

    minor_affixes = []
    minor_affix_1_img = desc_img[345:394,:]
    minor_affix_1 = parse_single_minor_affix(minor_affix_1_img, 'res/artifact_minor_affix_1.png', distance_threshold=distance_threshold, crop_margin=crop_margin)
    if minor_affix_1 is None: return None
    minor_affixes.append(minor_affix_1)
    minor_affix_2_img = desc_img[394:432,:]
    minor_affix_2 = parse_single_minor_affix(minor_affix_2_img, 'res/artifact_minor_affix_2.png', distance_threshold=distance_threshold, crop_margin=crop_margin)
    if minor_affix_2 is None: return None
    minor_affixes.append(minor_affix_2)
    minor_affix_3_img = desc_img[432:471,:]
    minor_affix_3 = parse_single_minor_affix(minor_affix_3_img, 'res/artifact_minor_affix_3.png', distance_threshold=distance_threshold, crop_margin=crop_margin)
    if minor_affix_3 is None: return None
    minor_affixes.append(minor_affix_3)
    minor_affix_4_img = desc_img[471:lower_bound,:]
    minor_affix_4 = parse_single_minor_affix(minor_affix_4_img, 'res/artifact_minor_affix_4.png', distance_threshold=distance_threshold, crop_margin=crop_margin)
    if minor_affix_4 is None: return None
    minor_affixes.append(minor_affix_4)

    return minor_affixes

def parse_desc_img_level(desc_img):
    lower = 255
    upper = 66
    grad = 255/(upper-lower)
    level_img = desc_img[310:335,31:84]
    grey_level_img = cv2.cvtColor(level_img,cv2.COLOR_BGR2GRAY).astype(np.float32)
    grey_level_img = np.clip(grad*(grey_level_img-lower),0,255).astype(np.uint8)
    grey_level_img[[0, -1], :] = 255
    grey_level_img[:, [0, -1]] = 255
    # cv2.imwrite('res/artifact_level.png', grey_level_img)
    detected_level = image_to_string(Image.fromarray(grey_level_img), psm=PSM.SINGLE_BLOCK).strip().casefold()
    
    level_parser = re.compile(r'^\+(\d+)$')
    match = re.search(level_parser, detected_level)
    if match is None: return None
    return int(match.group(1))

def parse_desc_img(desc_img, crop_margin=10):
    name = parse_desc_img_artifact_name(desc_img, crop_margin=crop_margin)
    if name is None: return None
    slot = parse_desc_img_slot(desc_img, crop_margin=crop_margin)
    if slot is None: return None
    level = parse_desc_img_level(desc_img)
    if level is None: return None
    minor_affixes = parse_desc_img_minor_affix(desc_img, crop_margin=crop_margin)
    if minor_affixes is None: return None
    main_affix = parse_desc_img_main_affix(desc_img, crop_margin=crop_margin)
    if main_affix is None: return None

    return Artifact(name, slot, level, main_affix, minor_affixes)

if __name__ == '__main__':
    try:
        while True:
            time.sleep(1)
            screen = capture_genshin_screen()
            if screen is None: continue
            desc_img = crop_artifact_desc(screen)
            # cv2.imwrite('res/artifact_desc.png', desc_img)
            st = time.time_ns()
            parsed_artifact = parse_desc_img(desc_img)
            et = time.time_ns()
            if parsed_artifact is None: continue
            print(hash(parsed_artifact))
            print(parsed_artifact)
    except KeyboardInterrupt:
        print("Exiting...")
