#include <Wire.h>
#include "Adafruit_TCS34725.h"

// =====================================================
// CONFIGURACION
// =====================================================
#define TCA_ADDR 0x70
#define LED_PIN 7
#define MUESTRAS 10
#define NUM_ESTACIONES 3

const float ref[3][3][3] = {

  // -------- Estación 1 --------
  {
    {0.662, 0.396, 0.360}, // rojo
    {0.477, 0.512, 0.365}, // verde
    {0.514, 0.498, 0.466}  // azul
  },

  // -------- Estación 2 --------
  {
    {0.684, 0.471, 0.426},
    {0.494, 0.529, 0.407},
    {0.528, 0.526, 0.489}
  },

  // -------- Estación 3 --------
  {
    {0.697, 0.471, 0.438},
    {0.533, 0.530, 0.427},
    {0.561, 0.519, 0.501}
  }
};

// =====================================================
// OBJETO SENSOR (uno solo, se reinicia por canal)
// =====================================================
Adafruit_TCS34725 tcs(
  TCS34725_INTEGRATIONTIME_154MS,
  TCS34725_GAIN_4X
);

// =====================================================
// Seleccionar canal del TCA9548A
// =====================================================
void tcaSelect(uint8_t canal)
{
  Wire.beginTransmission(TCA_ADDR);
  Wire.write(1 << canal);
  Wire.endTransmission();
}

// =====================================================
// Reiniciar sensor en el canal actual
// CLAVE para que funcione con el multiplexor
// =====================================================
bool iniciarSensor()
{
  if (!tcs.begin())
    return false;

  delay(10);
  return true;
}

// =====================================================
// Leer color de una estación
//
// 0 = vacío
// 1 = rojo
// 2 = verde
// 3 = azul
// =====================================================
uint8_t leerColorEstacion(uint8_t estacion)
{
  uint8_t canal = estacion - 1;

  // cambiar canal
  tcaSelect(canal);
  delay(5);

  // 🔥 REINICIALIZAR SENSOR EN ESTE CANAL
  if (!iniciarSensor())
  {
    Serial.print("E");
    Serial.print(estacion);
    Serial.println(" -> SENSOR NO DETECTADO");
    return 0;
  }

  uint32_t rSum=0, gSum=0, bSum=0, cSum=0;

  for(int i=0;i<MUESTRAS;i++)
  {
    uint16_t r,g,b,c;
    tcs.getRawData(&r,&g,&b,&c);

    rSum+=r;
    gSum+=g;
    bSum+=b;
    cSum+=c;

    delay(5);
  }

  float r = rSum/(float)MUESTRAS;
  float g = gSum/(float)MUESTRAS;
  float b = bSum/(float)MUESTRAS;
  float c = cSum/(float)MUESTRAS;

  // vacío
  if(c < 40)
  {
    Serial.print("E");
    Serial.print(estacion);
    Serial.println(" -> VACIO");
    return 0;
  }

  // normalización
  float rN = r/c;
  float gN = g/c;
  float bN = b/c;

  // ==============================
  // IMPRESION PEDIDA
  // ==============================
  Serial.print("E");
  Serial.print(estacion);
  Serial.print("  rN:");
  Serial.print(rN, 3);
  Serial.print("  gN:");
  Serial.print(gN, 3);
  Serial.print("  bN:");
  Serial.println(bN, 3);

  // clasificación
  if(rN > 0.60 && rN > gN && rN > bN) return 1;  // ROJO
  if(gN > 0.50 && gN > rN && gN > bN) return 2;  // VERDE
  if(bN > 0.46 && bN > rN && bN > gN) return 3;  // AZUL

  return 0;
}

// =====================================================
// SETUP
// =====================================================
void setup()
{
  Serial.begin(115200);
  Wire.begin();

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH);

  Serial.println("Sistema listo");
}

// =====================================================
// LOOP
// =====================================================
void loop()
{
  for(int e=1; e<=NUM_ESTACIONES; e++)
  {
    uint8_t color = leerColorEstacion(e);

    Serial.print("Estacion ");
    Serial.print(e);
    Serial.print(" -> ");

    switch(color)
    {
      case 1: Serial.println("ROJO"); break;
      case 2: Serial.println("VERDE"); break;
      case 3: Serial.println("AZUL"); break;
      default: Serial.println("VACIO"); break;
    }
  }

  Serial.println("-----------------");
  delay(600);
}
