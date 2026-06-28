import cv2
import numpy as np

def crop_inner_keep_bg():
    img = cv2.imread('frontend/acme_logo_old.png')
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    edges = cv2.Canny(gray, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    h, w = gray.shape
    valid_contours = []
    
    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        if cw > w * 0.8 or ch > h * 0.8:
            continue
        valid_contours.append(c)
        
    if valid_contours:
        x, y, cw, ch = cv2.boundingRect(np.vstack(valid_contours))
        print(f"Inner logo bounding box: x={x}, y={y}, w={cw}, h={ch}")
        
        # Add some padding to keep a little border
        pad = 20
        x = max(0, x - pad)
        y = max(0, y - pad)
        cw = min(w - x, cw + pad*2)
        ch = min(h - y, ch + pad*2)
        
        # Crop the image directly from the BGR image (keeping the background)
        cropped = img[y:y+ch, x:x+cw]
        
        cv2.imwrite('frontend/acme_logo.png', cropped)
        print("Cropped inner logo and kept the background.")
    else:
        print("Could not find inner logo.")

if __name__ == "__main__":
    crop_inner_keep_bg()
