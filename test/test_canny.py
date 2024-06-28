import cv2

image = cv2.imread(
    '..\\assets\\images\\3b991d47-10_18_37_465122_WindowsGraphicsCaptureMethod_3840x2160_title_None_Clie_3Hw8AdB.png',
    cv2.IMREAD_GRAYSCALE)  # Load in grayscale

# Apply Canny edge detection
# image = cv2.Canny(image, 1, 80)

# Save the result
cv2.imwrite('edges.jpg', image)
