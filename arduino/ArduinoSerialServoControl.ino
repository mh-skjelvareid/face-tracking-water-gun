#include <Servo.h>
Servo rcRelay;
Servo panServo;
Servo tiltServo;
String inByte;
int pos;
unsigned long timeNow = 0;
int period = 1000;                   // Trigger active time
boolean relayTriggerActivated = false; 

/*
   The code receives serial data and adjusts the servo positions. 
   A command to change position comes in parts:
    - First byte: 'R','P' or 'T' (indicates relay, pan or tilt)
    - Remaining bytes: Interpreted as ASCII numbers, converted to desired angle
      (for the relay, an angle below 90 is off, above 90 is on)
*/

// Connect servos
void setup() {
  rcRelay.attach(2);      // Relay on pin 2
  panServo.attach(9);     // Pan servo on pin 9
  tiltServo.attach(10);   // Tilt servo on pin 10
  Serial.begin(115200);   // Baud rate 115200
}

// Main loop
void loop()
{
  int val =  0;           // byte value read from serial 

  if(relayTriggerActivated && millis() > timeNow + period)    // If trigger has timed out
  {
    relayTriggerActivated = false;
    rcRelay.write(0);
    Serial.println("Relay OFF");
  }
  
  if (Serial.available() >0) {
    // Read first byte (indicates which servo to adjust)
    val = Serial.read();

    // Adjust position if command 'R', 'P' or 'T'
    if (val == 'R' || val=='P' || val=='T') 
    {
      inByte = Serial.readStringUntil('\n'); // read data until newline
      pos = inByte.toInt();   // change datatype from string to integer
      
      if(val=='R'){     // RC relay
        
        if(pos==0){
          rcRelay.write(0);
          Serial.println("Relay OFF");
        }
        
        if(pos==1){
          rcRelay.write(180);    // Maximum servo angle
          Serial.println("Relay ON");
        }

        if(pos==2){              // "Trigger mode"
          timeNow = millis();
          rcRelay.write(180);    // Maximum servo angle
          relayTriggerActivated = true;
          Serial.println("Relay TRIGGERED");          
        }
                
      }
      
      if(val=='P'){       // Pan servo
        panServo.write(pos);
        Serial.print("Pan:  ");
        Serial.println(inByte);
      } 
      
      if(val=='T'){       // Tilt servo
        tiltServo.write(pos);
        Serial.print("Tilt: ");
        Serial.println(inByte);
      }
       
    }     
  }  
} // end loop
