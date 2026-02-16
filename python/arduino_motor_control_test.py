from time import sleep

from face_tracking_water_gun import connect_arduino, send_servo_pos, update_servo_pos
from serial.tools.list_ports import comports

print("Available serial ports:")
for port in comports():
    print(f"{port.device}: {port.description}")

arduino = connect_arduino()
try:
    for _ in range(3):
        update_servo_pos(arduino, 90, 90)
        send_servo_pos(arduino, "R0")  # Relay off
        sleep(1)
        update_servo_pos(arduino, 110, 110)
        send_servo_pos(arduino, "R1")  # Relay on
        sleep(1)

finally:
    arduino.close()
