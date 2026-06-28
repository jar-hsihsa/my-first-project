import cv2
import numpy as np

def crop_ey_logo():
    src_path = '/Users/ashishraj/.gemini/antigravity-ide/brain/470f2d4c-6e55-4c5d-9e30-45bf3359ffc5/acme_corp_ey_style_logo_1782200542484.png'
    dest_path = 'frontend/acme_logo.png'
    
    img = cv2.imread(src_path)
    if img is None:
        print("Error: Could not open source logo image.")
        return

    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Get the background color from top-left corner
    bg_color = gray[0, 0]
    
    # Find all pixels that are significantly different from the background
    # Since the background is very dark (around 15-30), we threshold anything above it
    _, thresh = cv2.threshold(gray, int(bg_color) + 15, 255, cv2.THRESH_BINARY)
    
    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        print("Error: No logo content detected.")
        return
        
    # Get the combined bounding box of all contours
    x, y, w, h = cv2.boundingRect(np.vstack(contours))
    print(f"Detected content box: x={x}, y={y}, w={w}, h={h}")
    
    # Add padding to make the logo look natural
    pad_x = 40
    pad_y = 30
    
    img_h, img_w = img.shape[:2]
    x_start = max(0, x - pad_x)
    y_start = max(0, y - pad_y)
    x_end = min(img_w, x + w + pad_x)
    y_end = min(img_h, y + h + pad_y)
    
    cropped = img[y_start:y_end, x_start:x_end]
    
    # Save the cropped logo to frontend/acme_logo.png
    cv2.imwrite(dest_path, cropped)
    print(f"Successfully cropped logo and saved to {dest_path}")

if __name__ == '__main__':
    crop_ey_logo()
