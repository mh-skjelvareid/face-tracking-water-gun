import cv2


def find_working_cameras(max_index=10):
    available = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            print(f"Camera found at index {i}")
            available.append(i)
            cap.release()
    return available


print("Available cameras:", find_working_cameras())
