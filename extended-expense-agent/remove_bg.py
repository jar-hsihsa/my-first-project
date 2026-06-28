import cv2
import numpy as np

def remove_black_bg():
    img = cv2.imread('frontend/acme_logo.png')
    if img is None:
        print("Could not read image")
        return

    # Add alpha channel
    img_rgba = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    
    h, w = img.shape[:2]
    mask_flood = np.zeros((h+2, w+2), np.uint8)
    
    # Flood fill from all 4 corners to be safe
    corners = [(0,0), (w-1,0), (0,h-1), (w-1,h-1)]
    for pt in corners:
        cv2.floodFill(img, mask_flood, pt, (255,255,255), (40,40,40), (40,40,40), flags=cv2.FLOODFILL_MASK_ONLY | (255 << 8))
    
    # The mask_flood has 255 where the background is.
    bg_mask = mask_flood[1:h+1, 1:w+1]
    
    # Soften the mask for smoother edges
    bg_mask = cv2.GaussianBlur(bg_mask, (3, 3), 0)
    
    # Where bg_mask is high (close to 255), alpha should be low (close to 0)
    # alpha = 255 - bg_mask
    alpha = 255 - bg_mask
    
    # Combine original alpha with new alpha, just take the minimum
    img_rgba[:, :, 3] = np.minimum(img_rgba[:, :, 3], alpha)
    
    cv2.imwrite('frontend/acme_logo.png', img_rgba)
    print("Background removed successfully.")

if __name__ == "__main__":
    remove_black_bg()
