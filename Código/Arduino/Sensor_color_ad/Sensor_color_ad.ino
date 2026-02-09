/* =====================================================
   TCS3200 x3 con calibración independiente por estación
   0 vacío | 1 rojo | 2 verde | 3 azul
   ===================================================== */

#include <Arduino.h>

int NUM_MUESTRAS =10;

// =====================================================
struct ColorSensor {
  int s0, s1, s2, s3, out;
};

// =====================================================
// PINES
// =====================================================
ColorSensor sensores[3] = {
  {43, 41, 37, 39, 35}, // Est1
  {31, 29, 25, 27, 23}, // Est2
  {52, 50, 46, 48, 44}  // Est3
};


// =====================================================
// ⭐ PROTOTIPOS POR ESTACIÓN
// [estacion][color][RGB]
// color: 0 rojo, 1 verde, 2 azul
// =====================================================
const int ref[3][3][3] = {

  // ===== ESTACION 1 =====
  {
    {23,39,27}, // rojo
    {42,26,23}, // verde
    {49,31,16}  // azul
  },

  // ===== ESTACION 2 =====
  {
    {23,46,23},
    {62,36,62},
    {71,41,71}
  },

  // ===== ESTACION 3 =====
  {
    {16,35,29},
    {40,27,29},
    {42,28,17}
  }
};


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
// LECTURAS
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
int distancia(int r1,int v1,int a1,int r2,int v2,int a2)
{
  int dr=r1-r2;
  int dv=v1-v2;
  int da=a1-a2;
  return dr*dr + dv*dv + da*da;
}


// =====================================================
// ⭐ CLASIFICAR SEGÚN SU PROPIA ESTACIÓN
// =====================================================
int clasificar(int estacion, int R, int V, int A)
{
  int dRojo  = distancia(R,V,A, ref[estacion][0][0], ref[estacion][0][1], ref[estacion][0][2]);
  int dVerde = distancia(R,V,A, ref[estacion][1][0], ref[estacion][1][1], ref[estacion][1][2]);
  int dAzul  = distancia(R,V,A, ref[estacion][2][0], ref[estacion][2][1], ref[estacion][2][2]);

  int dMin = min(dRojo, min(dVerde, dAzul));

  if(dMin == dRojo)  return 1;
  if(dMin == dVerde) return 2;
  if(dMin == dAzul)  return 3;

  return 0;
}


// =====================================================
// ⭐ LECTURA PRINCIPAL
// =====================================================
int leerColor(int idx)
{
  ColorSensor &s = sensores[idx];

  long sumaR=0, sumaV=0, sumaA=0;

  for(int i=0;i<NUM_MUESTRAS;i++)
  {
    sumaR += leerRojo(s);
    delay(12);

    sumaV += leerVerde(s);
    delay(12);

    sumaA += leerAzul(s);
    delay(12);
  }

  int R = sumaR / NUM_MUESTRAS;
  int V = sumaV / NUM_MUESTRAS;
  int A = sumaA / NUM_MUESTRAS;

  Serial.print("E"); Serial.print(idx+1);
  Serial.print(" -> R:");
  Serial.print(R);
  Serial.print(" V:");
  Serial.print(V);
  Serial.print(" A:");
  Serial.println(A);

  return clasificar(idx, R, V, A);
}


// =====================================================
void setup()
{
  Serial.begin(115200);

  for(int i=0;i<3;i++)
    initSensor(sensores[i]);

  Serial.println("Sistema listo");
}


// =====================================================
void loop()
{
  for(int i=0;i<3;i++)
  {
    int color = leerColor(i);

    Serial.print("Color detectado: ");
    Serial.println(color);
  }

  Serial.println("------");
  delay(1200);
}
