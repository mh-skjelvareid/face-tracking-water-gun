"""
Detect a face in a video stream and track it using a pan-tilt camera, keeping
the face in the center of the image.

The code relies on a Haar cascade face detector, and the pan-tilt platform
is controlled by serial communication with an Arduino.

@author: Martin H. Skjelvareid, UiT
"""

# Imports
import time

import cv2
import numpy as np
from serial import Serial

# Set fixed parameters
BAUD_RATE = 115200  # Baud rate for serial communication with arduino
DEFAULT_ARDUINO_PORT = "COM4"  # "/dev/ttyACM0"  # Port for serial comm. with arduino

PAN_GAIN = 0.02  # Parameter for adjusting servo pan position
TILT_GAIN = 0.035  # Parameter for adjusting servo tilt position
PAN_LIMITS = (0, 170)  # Min / max pan angle
TILT_LIMITS = (65, 150)  # Min / max tilt angle
DESIRED_FACE_POS = (0.5, 0.6)  # Desired face center, relative

CASCADE_MODEL_FILE = "haarcascade_frontalface_default.xml"  # Face detection file
CASCADE_SCALE_FACTOR = 1.15  # Difference between scales used for detection
CASCADE_MIN_NEIGHBORS = (
    5  # Fewer neighbors -> Higher sensitivity. More neighbors -> Fewer false positives
)
CASCADE_FACE_MIN_SIZE = (60, 60)  # Minimum face size [pixels]
CASCADE_FACE_MAX_SIZE = (350, 350)  # Maximum face size [pixels]
RETRIGGER_WAIT = 5  # How long to wait between activating relay
MIN_REL_FACE_WIDTH = 0.17  # Relative size of face vs screen considered "close"
NO_FACE_RESET_TIME = 10.0
DEFAULT_PAN_ANGLE = 90.0
DEFAULT_TILT_ANGLE = 110.0

CV_WINDOW_WIDTH = 960
CV_WINDOW_HEIGHT = 720
RECTANGLE_COLOR = (0, 255, 0)  # Color of rectangle drawn around detected faces
RECTANGLE_THICKNESS = 2  # Thickness of rectangle drawn around detected faces


def connect_arduino(
    port: str = DEFAULT_ARDUINO_PORT, baud_rate: int = BAUD_RATE
) -> Serial:
    """Create and return serial object for communication with arduino"""
    arduino = Serial(port, baud_rate)
    time.sleep(2)  # Let serial connection be established
    return arduino


def update_servo_pos(arduino: Serial, pan_angle: float, tilt_angle: float) -> None:
    """Generate bytestrings for updating servo angles"""
    pan_angle = np.clip(pan_angle, PAN_LIMITS[0], PAN_LIMITS[1])
    tilt_angle = np.clip(tilt_angle, TILT_LIMITS[0], TILT_LIMITS[1])

    send_servo_pos(arduino, "P" + str(int(round(pan_angle))) + "\n")
    send_servo_pos(arduino, "T" + str(int(round(tilt_angle))) + "\n")


def send_servo_pos(arduino: Serial, pos_string: str) -> None:
    """Write bytestring to arduino and print response"""
    arduino.write(pos_string.encode())
    response = arduino.readline()
    print(response.decode("ascii").rstrip())


def face_relative_positions(
    faces: np.ndarray, frame_width: int, frame_height: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Calculate positions of faces relative to image center"""
    face_center_x = faces[:, 0] + faces[:, 2] / 2  # left edge + half width
    face_center_y = faces[:, 1] + faces[:, 3] / 2  # lower edge + half height
    x_offset = face_center_x - frame_width * (1 - DESIRED_FACE_POS[0])
    y_offset = face_center_y - frame_height * (1 - DESIRED_FACE_POS[1])
    r_offset = np.sqrt(x_offset**2 + y_offset**2)  # Radius from image center
    return x_offset, y_offset, r_offset


def draw_face_rectangles(frame: np.ndarray, faces: np.ndarray) -> None:
    """Draw rectangles around detected faces in the frame"""
    for x, y, w, h in faces:
        cv2.rectangle(
            frame,
            (x, y),
            (x + w, y + h),
            RECTANGLE_COLOR,
            RECTANGLE_THICKNESS,
        )


def main() -> None:
    # Initialize variables / objects
    pan_angle = DEFAULT_PAN_ANGLE
    tilt_angle = DEFAULT_TILT_ANGLE
    video_capture = cv2.VideoCapture(0)  # 0 for default camera
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + CASCADE_MODEL_FILE)
    ref_time = time.perf_counter()
    no_face_counter = time.perf_counter()

    # Create window
    _ = cv2.namedWindow("Video", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Video", CV_WINDOW_WIDTH, CV_WINDOW_HEIGHT)

    # Connect to arduino and set camera to default angle
    arduino = connect_arduino()
    update_servo_pos(arduino, pan_angle, tilt_angle)

    # Main loop
    try:
        while True:
            time.sleep(0.1)  # Sleep for testing

            # Capture frame-by-frame, convert to greyscale for face detection
            _, frame = video_capture.read()
            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            (frame_height, frame_width, _) = frame.shape

            # Detect faces
            faces = face_cascade.detectMultiScale(
                gray_frame,
                scaleFactor=CASCADE_SCALE_FACTOR,
                minNeighbors=CASCADE_MIN_NEIGHBORS,
                minSize=CASCADE_FACE_MIN_SIZE,
                maxSize=CASCADE_FACE_MAX_SIZE,
                flags=cv2.CASCADE_SCALE_IMAGE,
            )
            faces = np.array(faces)  # Cast as numpy array (suppress type hint warnings)

            # Process detected faces
            if not (len(faces) == 0):  # In any faces detected
                # Calculate positions of faces relative to image center
                x_offset, y_offset, r_offset = face_relative_positions(
                    faces, frame_width, frame_height
                )

                # Find face closest to center, calculate position error
                min_r_offset_index = np.argmin(r_offset)
                x_error = x_offset[min_r_offset_index]
                y_error = y_offset[min_r_offset_index]

                # Update camera angle to reduce x and y error
                pan_angle -= PAN_GAIN * x_error
                tilt_angle -= TILT_GAIN * y_error
                update_servo_pos(arduino, pan_angle, tilt_angle)

                # Trigger relay if face is close enough
                if faces[min_r_offset_index, 2] > frame_width * MIN_REL_FACE_WIDTH:
                    if time.perf_counter() > ref_time + RETRIGGER_WAIT:
                        ref_time = time.perf_counter()
                        send_servo_pos(arduino, "R2\n")  # Send trigger code

                # Draw rectangle(s) around face(s)
                draw_face_rectangles(frame, faces)

                # Face(s) detected, reset "no faces" counter
                no_face_counter = time.perf_counter()

            # Reset camera angle if "no faces" timeout
            if time.perf_counter() > no_face_counter + NO_FACE_RESET_TIME:
                update_servo_pos(arduino, DEFAULT_PAN_ANGLE, DEFAULT_TILT_ANGLE)

            # Display the resulting frame (with or without faces)
            cv2.imshow("Video", frame)

            # Check for "q" key press to quit
            if (cv2.waitKey(1) & 0xFF) == ord(
                "q"
            ):  # 0xFF to get last 8 bits of keycode
                break

    finally:
        #  Clean up
        video_capture.release()
        cv2.destroyAllWindows()
        arduino.close()


# Run the main function
if __name__ == "__main__":
    main()
