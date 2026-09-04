from PIL import ImageGrab
import sys
import time

try:
    img = ImageGrab.grab()
    img.save(sys.argv[1])
    print(f"Screenshot saved to {sys.argv[1]}")
except Exception as e:
    print(f"Error: {e}")
