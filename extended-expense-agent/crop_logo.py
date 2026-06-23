import cv2
import numpy as np
from PIL import Image

def crop_coin():
    img = cv2.imread('frontend/acme_logo.jpg')
    if img is None:
        print("Error reading image")
        return

    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Let's apply a threshold to isolate the coin
    # If the background is bright and uniform, adaptive threshold or simple thresholding works.
    # The coin seems to have some bright spots but a definite edge.
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Using Otsu's thresholding to find the coin vs background
    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # We can also use Canny edge detection
    edges = cv2.Canny(blurred, 50, 150)
    
    # Find contours from edges which usually gives the boundary of the coin nicely
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        print("No contours found.")
        return
        
    # Get the contour with maximum area
    largest_contour = max(contours, key=cv2.contourArea)
    
    # Find the minimum enclosing circle
    (x, y), radius = cv2.minEnclosingCircle(largest_contour)
    center_x, center_y, radius = int(x), int(y), int(radius)
    print(f"Detected circle at ({center_x}, {center_y}) with radius {radius}")
    
    # To be safe, we will slightly shrink the radius by 1 or 2 pixels to avoid any background halo
    radius = int(radius * 0.99)
    
    pil_img = Image.open('frontend/acme_logo.jpg').convert("RGBA")
    
    # Crop to the bounding box of the circle
    min_x = center_x - radius
    max_x = center_x + radius
    min_y = center_y - radius
    max_y = center_y + radius
    
    cropped = pil_img.crop((min_x, min_y, max_x, max_y))
    
    # Create circular mask
    mask = Image.new('L', (radius * 2, radius * 2), 0)
    from PIL import ImageDraw
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, radius * 2, radius * 2), fill=255)
    
    # Apply the mask to make the outside transparent
    cropped.putalpha(mask)
    
    # Save the properly cropped image
    cropped.save('frontend/acme_logo.png', "PNG")
    print("Properly centered and cropped logo saved to frontend/acme_logo.png")

if __name__ == "__main__":
    crop_coin()
