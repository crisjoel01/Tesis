+#include <Adafruit_MCP23X17.h>
#define LED_PIN11 0     // MCP23XXX pin LED is attached to
#define LED_PIN12 8     // MCP23XXX pin LED is attached to
#define LED_PIN21 0     // MCP23XXX pin LED is attached to
#define LED_PIN22 8     // MCP23XXX pin LED is attached to

 
Adafruit_MCP23X17 mcp1;
Adafruit_MCP23X17 mcp2;  // Segundo MCP (0x21)

 
void setup() {
 
  // Wait for connection
  if (!mcp1.begin_I2C(0x20)) {
    while (1);
  }
  
  if (!mcp2.begin_I2C(0x21)) {
    while (1);
  }
  // configure chosen pin as output
  mcp1.pinMode(LED_PIN11, OUTPUT);
  mcp1.pinMode(LED_PIN12, INPUT);
  mcp2.pinMode(LED_PIN21, INPUT);
  mcp2.pinMode(LED_PIN22, OUTPUT);
 
}
 
void loop() {

  if(mcp1.digitalRead(LED_PIN12) && mcp2.digitalRead(LED_PIN21)){
    mcp2.digitalWrite(LED_PIN22, LOW);
    mcp1.digitalWrite(LED_PIN11, LOW);
  }else if(mcp1.digitalRead(LED_PIN12)){
    mcp2.digitalWrite(LED_PIN22, HIGH);
    mcp1.digitalWrite(LED_PIN11, LOW);
  }else if(mcp2.digitalRead(LED_PIN21)){
    mcp1.digitalWrite(LED_PIN11, HIGH);
    mcp2.digitalWrite(LED_PIN22, LOW);    
  }

}