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
PAN_GAIN = 0.02  # Parameter for adjusting servo pan position
TILT_GAIN = 0.035  # Parameter for adjusting servo tilt position
PAN_LIMITS = (0, 170)  # Min / max pan angle
TILT_LIMITS = (65, 150)  # Min / max tilt angle
DESIRED_FACE_POS = (0.5, 0.6)  # Desired face center, relative

CASCADE_MODEL_PATH = "haarcascade_frontalface_default.xml"  # Face detection file
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


# Methods for changing camera angle
def update_servo_pos(arduino: Serial, panAngle: float, tiltAngle: float) -> None:
    """Generate bytestrings for updating servo angles"""
    panAngle = np.clip(panAngle, PAN_LIMITS[0], PAN_LIMITS[1])
    tiltAngle = np.clip(tiltAngle, TILT_LIMITS[0], TILT_LIMITS[1])

    send_servo_pos(arduino, "P" + str(int(round(panAngle))) + "\n")
    send_servo_pos(arduino, "T" + str(int(round(tiltAngle))) + "\n")


def send_servo_pos(arduino: Serial, posString: str) -> None:
    """Write bytestring to arduino and print response"""
    arduino.write(posString.encode())
    response = arduino.readline()
    print(response.decode("ascii").rstrip())


def main() -> None:
    # Initialize variables / objects
    panAngle = DEFAULT_PAN_ANGLE
    tiltAngle = DEFAULT_TILT_ANGLE
    video_capture = cv2.VideoCapture(0)
    faceCascade = cv2.CascadeClassifier(CASCADE_MODEL_PATH)
    arduino = Serial("/dev/ttyACM0", 115200)  # create serial object named arduino
    refTime = time.perf_counter()
    noFaceCounter = time.perf_counter()

    # Initial code (run once)
    time.sleep(2)  # Let serial connection be established
    update_servo_pos(arduino, panAngle, tiltAngle)  # Set original tilt

    # Create window
    window = cv2.namedWindow("Video", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Video", 900, 900)

    # Main loop
    try:
        while True:
            # Capture frame-by-frame, convert to greyscale for face detection
            ret, frame = video_capture.read()
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            (frameHeight, frameWidth, nChannels) = frame.shape

            # Detect faces
            faces = faceCascade.detectMultiScale(
                gray,
                scaleFactor=CASCADE_SCALE_FACTOR,
                minNeighbors=CASCADE_MIN_NEIGHBORS,
                minSize=CASCADE_FACE_MIN_SIZE,
                maxSize=CASCADE_FACE_MAX_SIZE,
                flags=cv2.CASCADE_SCALE_IMAGE,
            )

            # Process detected faces
            if not (len(faces) == 0):  # In any faces detected
                # Find positions of faces relative to image center
                faceCenterX = faces[:, 0] + faces[:, 2] / 2  # left edge + half width
                faceCenterY = faces[:, 1] + faces[:, 3] / 2  # lower edge + half height
                xOffset = faceCenterX - frameWidth * (1 - DESIRED_FACE_POS[0])
                yOffset = faceCenterY - frameHeight * (1 - DESIRED_FACE_POS[1])
                rOffset = np.sqrt(xOffset**2 + yOffset**2)  # Radius from image center

                # Find face closest to center, calculate position error
                index_rOffsetMin = np.argmin(rOffset)
                xError = xOffset[index_rOffsetMin]
                yError = yOffset[index_rOffsetMin]

                # Update camera angle to reduce x and y error
                panAngle -= PAN_GAIN * xError
                tiltAngle -= TILT_GAIN * yError
                update_servo_pos(panAngle, tiltAngle)

                # Trigger relay if face is close enough
                if faces[index_rOffsetMin, 2] > frameWidth * MIN_REL_FACE_WIDTH:
                    if time.perf_counter() > refTime + RETRIGGER_WAIT:
                        refTime = time.perf_counter()
                        send_servo_pos("R2\n")  # Send trigger code

                # Draw rectangle(s) around face(s)
                for x, y, w, h in faces:
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

                # Reset "no faces" counter
                noFaceCounter = time.perf_counter()

            # Reset camera angle if "no faces" timeout
            if time.perf_counter() > noFaceCounter + NO_FACE_RESET_TIME:
                update_servo_pos(DEFAULT_PAN_ANGLE, DEFAULT_TILT_ANGLE)

            # Display the resulting frame (with or without faces)
            cv2.imshow("Video", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        #  Clean up
        video_capture.release()
        cv2.destroyAllWindows()
        arduino.close()


# Run the main function
if __name__ == "__main__":
    main()
