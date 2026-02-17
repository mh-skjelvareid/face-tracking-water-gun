# face-tracking-water-gun
Arduino and Python code for a face tracking water gun, made from a webcam on a pan-tilt platform and a windshield wiper pump. Faces are detected using Haar cascades in OpenCV, and servos are controlled via an Arduino.

## Camera and nozzle pan-tilt platform
The camera and nozzle and mounted on a simple pan-tilt platform made of wood. The angle is adjusted with two RC servo motors, and the water pump is "triggered" via a relay. Both the servos and the pump are controlled by a microcontroller, which receives serial commands from a laptop.  

<img src="images/face_tracking_water_gun_side.jpg" alt="Face tracking water gun - from side" width="500"/>

## Face detection
Images from the webcam are captured and processed using the [OpenCV library](https://opencv.org/) for Python. Faces are detected using a [cascade classifier based on Haar features](https://docs.opencv.org/3.4/db/d28/tutorial_cascade_classifier.html).

<img src="images/multiple_face_detection_example.jpg" alt="Example of faces detected using Haar cascade classifier" width="600"/>

## Face tracking and pump triggering
The face tracking code takes in all detected faces, calculates their relative position in the image, and attempts to track the face closest to the center. It uses the following simple update rule for each image frame (corresponding to a ["proportional" control loop](https://en.wikipedia.org/wiki/Proportional%E2%80%93integral%E2%80%93derivative_controller)):

    pan_angle = pan_angle - pan_angle_gain * horizontal_face_offset
    tilt_angle = tilt_angle - tilt_angle_gain * vertical_face_offset

where the offset values correspond to the offset of the face relative to the center of the image, and the gain values are parameters that can be tuned to get a "sweet spot" between responsiveness and stability. 

If you are close enough to the camera (the width of the detected face is above a threshold), the relay is "triggered", which starts the water pump and sprays you in the face!  

## Electronics
The electronics are mounted on a plate below the pan-tilt platform, and can be run via a 12 V battery or power supply. The white connector is attached to the pump.

<img src="images/arduino_servo_power_wiring.jpg" alt="Arduino Uno with Adafruit motor shield and rc relay - overview of wiring" width="600"/>

The project uses a "motor shield" mounted on top of the Arduino. The image below shows the shield separated from the base board. The full motor shield is not really needed in this project -- for controlling servos, it simply exposes two of the digital PWM output pins together with +5 V and ground so that servo wires can be attached directly. An relay that can be controlled with RC signals (PWM) is also included, with wires soldered directly to the shield.

<img src="images/arduino_motor_shield_closeup.jpg" alt="Closeup of motor shield and arduino separately." width="500"/>

## Components
This project was originally built in 2019, with parts that were purchased before that. Some parts are not available any longer, or have been replaced with new versions. However, here is a list of the components used:

- **Camera**: Logitech HD 720P C525 webcam
- **Pan servo**: Tower Pro, SG-5010 
- **Tilt servo**: Turnigy TGY-210DMH
- **Relay**: [Pololu RC switch with relay](https://www.pololu.com/product/2804)
- **Microcontroller**: [Arduino Uno](https://en.wikipedia.org/wiki/Arduino_Uno) with [Adafruit Motor Shield v1](https://learn.adafruit.com/adafruit-motor-shield/overview)
- **Windscreen washer (pump, nozzle, tank)**: [Biltema 58-657](https://www.biltema.no/bil---mc/bildeler/viskerutstyr/vindusspyler/vindusspyler-15-l-2000017961)
 

