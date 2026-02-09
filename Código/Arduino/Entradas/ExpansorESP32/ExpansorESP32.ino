#include <Wire.h>
#include <Adafruit_MCP23X17.h>

// Instancias de los 4 MCP23017
Adafruit_MCP23X17 mcp1;  // Dirección 0x20
Adafruit_MCP23X17 mcp2;  // Dirección 0x21
Adafruit_MCP23X17 mcp3;  // Dirección 0x22
Adafruit_MCP23X17 mcp4;  // Dirección 0x23

void setup() {
  Serial.begin(9600);
  delay(100);
  Wire.begin();

  // Inicializa cada MCP
  if (!mcp1.begin_I2C(0x20)) {
    Serial.println("Error: MCP1 no detectado en 0x20");
    while (1);
  } else {
    Serial.println("MCP1 detectado en 0x20");
  }

  if (!mcp2.begin_I2C(0x21)) {
    Serial.println("Error: MCP2 no detectado en 0x21");
    while (1);
  } else {
    Serial.println("MCP2 detectado en 0x21");
  }

  if (!mcp3.begin_I2C(0x22)) {
    Serial.println("Error: MCP3 no detectado en 0x22");
    while (1);
  } else {
    Serial.println("MCP3 detectado en 0x22");
  }

  // if (!mcp4.begin_I2C(0x23)) {
  //   Serial.println("Error: MCP4 no detectado en 0x23");
  //   while (1);
  // } else {
  //   Serial.println("MCP4 detectado en 0x23");
  // }

  // Configura los pines GPA0 y GPB0 como entradas en todos los MCP
  for (int i = 0; i < 4; i++) {
    getMCP(i).pinMode(0, INPUT);  // GPA0
    getMCP(i).pinMode(8, INPUT);  // GPB0
  }
}

void loop() {
  // Lee y muestra GPA0 y GPB0 de cada MCP
  for (int i = 0; i < 4; i++) {
    Adafruit_MCP23X17 &mcp = getMCP(i);
    bool gpa0 = mcp.digitalRead(0);
    bool gpb0 = mcp.digitalRead(8);

    Serial.print("MCP");
    Serial.print(i + 1);
    Serial.print(" - GPA0: ");
    Serial.print(gpa0);
    Serial.print(" | GPB0: ");
    Serial.println(gpb0);
  }

  Serial.println("-----------------------------");
  delay(500);
}

// Función auxiliar para acceder a cada MCP por índice
Adafruit_MCP23X17 &getMCP(int index) {
  switch (index) {
    case 0: return mcp1;
    case 1: return mcp2;
    case 2: return mcp3;
    // case 3: return mcp4;
    default: return mcp1;  // Evita errores si se pasa un índice inválido
  }
}
