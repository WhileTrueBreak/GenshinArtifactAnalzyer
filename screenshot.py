
import cv2

from artifact_scanner import capture_genshin_screen

screen = capture_genshin_screen()
screen = cv2.cvtColor(screen, cv2.COLOR_RGB2BGR)
cv2.imwrite('screen1.png', screen)