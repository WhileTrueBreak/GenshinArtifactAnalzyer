import time

import keyboard
import pyautogui

print("Press SPACE to print mouse position. Press ESC to quit.")

try:
    while True:
        if keyboard.is_pressed('space'):
            x, y = pyautogui.position()
            print(f"Space pressed! Mouse at ({x}, {y})")
            # Wait to avoid multiple prints for a single press
            while keyboard.is_pressed('space'):
                time.sleep(0.1)
        if keyboard.is_pressed('esc'):
            print("Exiting...")
            break
        time.sleep(0.05)
except KeyboardInterrupt:
    print("Stopped by user.")
