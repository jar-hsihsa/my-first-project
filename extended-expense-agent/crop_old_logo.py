import cv2
import numpy as np

def auto_crop():
    img = cv2.imread('frontend/acme_logo_old.png')
    if img is None:
        print("Could not read image")
        return

    # Convert to RGBA
    img_rgba = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    
    # We know it has a black background (or very dark)
    # Let's find the bounding box of all non-black pixels
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Threshold to find non-black pixels
    _, thresh = cv2.threshold(gray, 15, 255, cv2.THRESH_BINARY)
    
    # Find contours to get the bounding box of the actual logo
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        print("No contours found.")
        return
        
    # Get the bounding box of the largest contour, or all contours
    x, y, w, h = cv2.boundingRect(np.vstack(contours))
    print(f"Cropping to x={x}, y={y}, w={w}, h={h}")
    
    # Crop the image to this bounding box
    cropped = img_rgba[y:y+h, x:x+w]
    
    # Also remove the black background within the cropped area by making it transparent
    # Flood fill from corners of the cropped image
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
    
    # Save the cropped and transparent image
    cv2.imwrite('frontend/acme_logo.png', cropped)
    print("Cropped and background removed successfully.")

if __name__ == "__main__":
    auto_crop()
