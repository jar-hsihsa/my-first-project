import cv2
import numpy as np

def crop_inner():
    img = cv2.imread('frontend/acme_logo_old.png')
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # We want to ignore the big rectangular box. 
    # Usually it's either the outermost contour or a large block.
    # Let's find edges.
    edges = cv2.Canny(gray, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    h, w = gray.shape
    valid_contours = []
    
    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        # ignore the outer box which is likely > 80% of the image
        if cw > w * 0.8 or ch > h * 0.8:
            continue
        valid_contours.append(c)
        
    if valid_contours:
        x, y, cw, ch = cv2.boundingRect(np.vstack(valid_contours))
        print(f"Inner logo bounding box: x={x}, y={y}, w={cw}, h={ch}")
        
        # Add some padding
        pad = 20
        x = max(0, x - pad)
        y = max(0, y - pad)
        cw = min(w - x, cw + pad*2)
        ch = min(h - y, ch + pad*2)
        
        # Convert to RGBA
        img_rgba = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
        cropped = img_rgba[y:y+ch, x:x+cw]
        
        # Remove black background of cropped region
        cropped_bgr = cropped[:, :, :3].copy()
        h_c, w_c = cropped_bgr.shape[:2]
        mask_flood = np.zeros((h_c+2, w_c+2), np.uint8)
        
        corners = [(0,0), (w_c-1,0), (0,h_c-1), (w_c-1,h_c-1)]
        for pt in corners:
            cv2.floodFill(cropped_bgr, mask_flood, pt, (255,255,255), (40,40,40), (40,40,40), flags=cv2.FLOODFILL_MASK_ONLY | (255 << 8))
            
        bg_mask = mask_flood[1:h_c+1, 1:w_c+1]
        bg_mask = cv2.GaussianBlur(bg_mask, (3, 3), 0)
        
        alpha = 255 - bg_mask
        cropped[:, :, 3] = np.minimum(cropped[:, :, 3], alpha)
        
        cv2.imwrite('frontend/acme_logo.png', cropped)
        print("Cropped inner logo and removed bg.")
    else:
        print("Could not find inner logo.")

if __name__ == "__main__":
    crop_inner()
