/* =====================================================
   SISTEMA 3 SENSORES TCS3200 CON VOTACIÓN (5 muestras)

   Devuelve:
   0 = vacío
   1 = rojo
   2 = verde
   3 = azul
   ===================================================== */

#include <Arduino.h>

// =====================================================
// ESTRUCTURA SENSOR
// =====================================================
struct ColorSensor {
  int s0, s1, s2, s3, out;
};

// =====================================================
// PINES DE LAS 3 ESTACIONES
// =====================================================
ColorSensor sensores[3] = {
  {43, 41, 37, 39, 35}, // Estación 1
  {31, 29, 25, 27, 23}, // Estación 2
  {52, 50, 46, 48, 44}  // Estación 3
};

// =====================================================
// ARREGLO DE STORAGE (50 posiciones)
// 0 vacío | 1 rojo | 2 verde | 3 azul
// =====================================================
byte almacen[50];

int R;
int V;
int A;

// =====================================================
// INIT SENSOR
// =====================================================
void initSensor(ColorSensor &s)
{
  pinMode(s.s0, OUTPUT);
  pinMode(s.s1, OUTPUT);
  pinMode(s.s2, OUTPUT);
  pinMode(s.s3, OUTPUT);
  pinMode(s.out, INPUT);

  digitalWrite(s.s0, HIGH);
  digitalWrite(s.s1, HIGH);
}


// =====================================================
// LECTURAS RGB
// =====================================================
int leerRojo(ColorSensor &s){
  digitalWrite(s.s2, LOW);
  digitalWrite(s.s3, LOW);
  return pulseIn(s.out, LOW);
}

int leerVerde(ColorSensor &s){
  digitalWrite(s.s2, HIGH);
  digitalWrite(s.s3, HIGH);
  return pulseIn(s.out, LOW);
}

int leerAzul(ColorSensor &s){
  digitalWrite(s.s2, LOW);
  digitalWrite(s.s3, HIGH);
  return pulseIn(s.out, LOW);
}


// =====================================================
// CLASIFICADOR DE UNA MUESTRA
// Ajusta umbrales si cambias iluminación
// =====================================================
int clasificar(int R, int V, int A)
{
  if (A < V && A < R)
    return 3; // azul

  else if (R < V && R < A)
    return 1; // rojo

  else if (V < R && V < A)
    return 2; // verde

  else
    return 0; // desconocido
}

// =====================================================
// ⭐ FUNCIÓN PRINCIPAL
// 5 muestras + voto mayoritario
// =====================================================
// =====================================================
// ⭐ FUNCIÓN PRINCIPAL
// 5 muestras + promedio + voto mayoritario
// =====================================================
int leerColor(ColorSensor &s){
  int conteo[4] = {0,0,0,0};

  long sumaR = 0;
  long sumaV = 0;
  long sumaA = 0;

  int R, V, A;

  for(int i=0; i<5; i++)
  {
    R = leerRojo(s);
    delay(40);

    V = leerVerde(s);
    delay(40);

    A = leerAzul(s);

    sumaR += R;
    sumaV += V;
    sumaA += A;

    int color = clasificar(R,V,A);
    conteo[color]++;

    delay(30);
  }

  // promedio final (más estable)
  R = sumaR / 5;
  V = sumaV / 5;
  A = sumaA / 5;

  Serial.print("R: ");
  Serial.print(R);
  Serial.print("  V: ");
  Serial.print(V);
  Serial.print("  A: ");
  Serial.println(A);

  // mayoría
  int ganador = 0;
  for(int i=1;i<4;i++)
    if(conteo[i] > conteo[ganador])
      ganador = i;

  return ganador;
}



// =====================================================
// SETUP
// =====================================================
void setup()
{
  Serial.begin(115200);

  for(int i=0;i<3;i++)
    initSensor(sensores[i]);

  Serial.println("Sensores listos");
}


// =====================================================
// EJEMPLO DE USO
// (prueba leer todos)
// =====================================================
void loop()
{
  for(int i=0;i<3;i++)
  {
    int color = leerColor(sensores[i]);

    Serial.print("Estacion ");
    Serial.print(i+1);
    Serial.print(" -> ");
    Serial.println(color);

    delay(500);
  }

  Serial.println("------");
  delay(1500);
}
