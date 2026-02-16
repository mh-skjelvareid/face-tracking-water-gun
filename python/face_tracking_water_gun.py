"""
Detect a face in a video stream and track it using a pan-tilt camera, keeping
the face in the center of the image.

The code relies on a Haar cascade face detector, and the pan-tilt platform
is controlled by serial communication with an Arduino.

@author: Martin H. Skjelvareid, UiT
"""

# Imports
import argparse
import time

import cv2
import numpy as np
from serial import Serial

# Set fixed parameters
BAUD_RATE = 115200  # Baud rate for serial communication with arduino
DEFAULT_ARDUINO_PORT = "COM4"  # "/dev/ttyACM0"  # Port for serial comm. with arduino
DEFAULT_CAMERA_INDEX = 1  # Indexing starts at 0, 1 is second camera
FRAME_RATE = 30  # Desired frame rate for video capture (not guaranteed, depends on processing speed)

PAN_GAIN = 0.02  # Parameter for adjusting servo pan position
TILT_GAIN = 0.035  # Parameter for adjusting servo tilt position
PAN_LIMITS = (0, 170)  # Min / max pan angle
TILT_LIMITS = (65, 150)  # Min / max tilt angle
DEFAULT_PAN_ANGLE = 90.0
DEFAULT_TILT_ANGLE = 110.0

CASCADE_MODEL_FILE = "haarcascade_frontalface_default.xml"  # Face detection file
CASCADE_SCALE_FACTOR = 1.15  # Difference between scales used for detection
CASCADE_MIN_NEIGHBORS = (
    5  # Fewer neighbors -> Higher sensitivity. More neighbors -> Fewer false positives
)
CASCADE_FACE_MIN_SIZE = (60, 60)  # Minimum face size [pixels]
CASCADE_FACE_MAX_SIZE = (350, 350)  # Maximum face size [pixels]
DESIRED_FACE_POS = (0.5, 0.6)  # Desired face center, relative
MIN_REL_FACE_WIDTH = 0.15  # Relative size of face vs screen considered "close"

CV_WINDOW_WIDTH = 960
CV_WINDOW_HEIGHT = 720
RECTANGLE_COLOR = (0, 255, 0)  # Color of rectangle drawn around detected faces
RECTANGLE_THICKNESS = 2  # Thickness of rectangle drawn around detected faces

RETRIGGER_RELAY_WAIT = 3.0  # How long to wait between activating relay
NO_FACE_RESET_TIME = 4.0


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


def main(
    camera_index: int = DEFAULT_CAMERA_INDEX, serial_port: str = DEFAULT_ARDUINO_PORT
) -> None:
    """
    Main function for face detection.

    Args:
        camera_index: Index of the camera to use (default: 0)
        serial_port: Serial port for Arduino communication (default: "COM4")
    """

    # Initialize OpenCV video capture and face cascade classifier
    video_capture = cv2.VideoCapture(camera_index)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + CASCADE_MODEL_FILE)  # type: ignore

    # Create window
    _ = cv2.namedWindow("Video", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Video", CV_WINDOW_WIDTH, CV_WINDOW_HEIGHT)

    # Initialize pan/tilt angles
    pan_angle = DEFAULT_PAN_ANGLE
    tilt_angle = DEFAULT_TILT_ANGLE

    # Connect to arduino and set camera to default angle
    arduino = connect_arduino(serial_port)
    update_servo_pos(arduino, pan_angle, tilt_angle)

    # Initialize timers
    last_trigger_time = time.perf_counter()
    face_last_seen_time = time.perf_counter()

    # Calculate target frame duration for frame rate limiting
    target_frame_duration = 1.0 / FRAME_RATE

    # Main loop
    try:
        while True:
            # Record loop start time for frame rate control
            loop_start_time = time.perf_counter()

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
                    if time.perf_counter() > last_trigger_time + RETRIGGER_RELAY_WAIT:
                        last_trigger_time = time.perf_counter()
                        send_servo_pos(arduino, "R2\n")  # Send trigger code

                # Draw rectangle(s) around face(s)
                draw_face_rectangles(frame, faces)

                # Face(s) detected, reset "no faces" counter
                face_last_seen_time = time.perf_counter()

            # Reset camera angle if "no faces" timeout
            if time.perf_counter() > face_last_seen_time + NO_FACE_RESET_TIME:
                update_servo_pos(arduino, DEFAULT_PAN_ANGLE, DEFAULT_TILT_ANGLE)

            # Display the resulting frame (with or without faces)
            cv2.imshow("Video", frame)

            # Check for "q" key press to quit
            if (cv2.waitKey(1) & 0xFF) == ord(
                "q"
            ):  # 0xFF to get last 8 bits of keycode
                break

            # Sleep to maintain target frame rate (best-effort)
            elapsed_time = time.perf_counter() - loop_start_time
            sleep_time = target_frame_duration - elapsed_time
            if sleep_time > 0:
                time.sleep(sleep_time)

    finally:
        #  Clean up
        video_capture.release()
        cv2.destroyAllWindows()
        arduino.close()


def parse_arguments():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description="Detect and display faces in a video stream"
    )
    parser.add_argument(
        "-c",
        "--camera",
        type=int,
        default=DEFAULT_CAMERA_INDEX,
        help=f"Camera index (default: {DEFAULT_CAMERA_INDEX})",
    )
    parser.add_argument(
        "-p",
        "--port",
        type=str,
        default=DEFAULT_ARDUINO_PORT,
        help=f"Arduino serial port (default: {DEFAULT_ARDUINO_PORT})",
    )

    return parser.parse_args()


# Run the main function
if __name__ == "__main__":
    args = parse_arguments()
    main(camera_index=args.camera, serial_port=args.port)
