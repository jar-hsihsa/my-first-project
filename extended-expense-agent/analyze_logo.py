import cv2
import numpy as np

def analyze():
    img = cv2.imread('frontend/acme_logo_old.png', cv2.IMREAD_UNCHANGED)
    if img is None:
        print("Could not read image")
        return
        
    print("Shape:", img.shape)
    
    # Check if there is an alpha channel
    if img.shape[2] == 4:
        alpha = img[:, :, 3]
        # find bounding box of non-zero alpha
        coords = cv2.findNonZero(alpha)
        if coords is not None:
            x, y, w, h = cv2.boundingRect(coords)
            print(f"Alpha bounding box: x={x}, y={y}, w={w}, h={h}")
        else:
            print("Alpha channel is entirely 0")
    else:
        # no alpha channel, let's find bounding box of non-black or non-white
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Check if background is mostly white or black
        if gray[0,0] > 128:
            # white background
            _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
        else:
            # black background
            _, thresh = cv2.threshold(gray, 10, 255, cv2.THRESH_BINARY)
            
        coords = cv2.findNonZero(thresh)
        if coords is not None:
            x, y, w, h = cv2.boundingRect(coords)
            print(f"Content bounding box: x={x}, y={y}, w={w}, h={h}")

if __name__ == "__main__":
    analyze()
