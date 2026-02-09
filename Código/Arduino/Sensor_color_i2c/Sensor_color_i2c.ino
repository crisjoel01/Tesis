#include <Wire.h>
#include "Adafruit_TCS34725.h"

// =====================================================
// CONFIG
// =====================================================
#define TCA_ADDR 0x70
#define MUESTRAS 10

// =====================================================
// Sensor (uno solo reutilizado para todos los canales)
// =====================================================
Adafruit_TCS34725 tcs(
  TCS34725_INTEGRATIONTIME_154MS,
  TCS34725_GAIN_4X
);

// =====================================================
// Selecciona canal del TCA
// =====================================================
void tcaSelect(uint8_t canal)
{
  Wire.beginTransmission(TCA_ADDR);
  Wire.write(1 << canal);
  Wire.endTransmission();
}

// =====================================================
// Lee estación
//
// retorna:
// 0 = vacío
// 1 = rojo
// 2 = verde
// 3 = azul
// =====================================================
uint8_t leerColorEstacion(uint8_t estacion)
{
  uint8_t canal = estacion - 1;

  tcaSelect(canal);

  uint32_t rSum=0, gSum=0, bSum=0, cSum=0;

  for(int i=0;i<MUESTRAS;i++)
  {
    uint16_t r,g,b,c;
    tcs.getRawData(&r,&g,&b,&c);

    rSum+=r;
    gSum+=g;
    bSum+=b;
    cSum+=c;
  }

  float r = rSum/(float)MUESTRAS;
  float g = gSum/(float)MUESTRAS;
  float b = bSum/(float)MUESTRAS;
  float c = cSum/(float)MUESTRAS;

  // sin objeto
  if(c < 40) return 0;

  // normalización
  float rN = r/c;
  float gN = g/c;
  float bN = b/c;

  // clasificación
  if(rN > 0.45 && rN > gN && rN > bN) return 1;
  if(gN > 0.45 && gN > rN && gN > bN) return 2;
  if(bN > 0.40 && bN > rN && bN > gN) return 3;

  return 0;
}

// =====================================================
// SETUP
// =====================================================
void setup()
{
  Serial.begin(115200);
  Wire.begin();

  // iniciar sensor una sola vez
  tcaSelect(0);

  if(!tcs.begin())
  {
    Serial.println("No se detecto TCS34725");
    while(1);
  }
}

// =====================================================
// LOOP DEMO
// =====================================================
void loop()
{
  for(int e=1; e<=3; e++)
  {
    uint8_t color = leerColorEstacion(e);

    Serial.print("Estacion ");
    Serial.print(e);
    Serial.print(": ");
    Serial.println(color);
  }

  Serial.println("-----");
  delay(500);
}
