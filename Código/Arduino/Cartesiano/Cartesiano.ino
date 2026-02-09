// Librerias
#include <Wire.h>
#include <Arduino.h>
#include <Adafruit_MCP23X17.h>

// Dirección esclavo
#define SLAVE_ADDR 0x30
#define NUM_MUESTRAS 20

// Estancias MCP
Adafruit_MCP23X17 mcp1;   // 0x20
Adafruit_MCP23X17 mcp2;   // 0x21
Adafruit_MCP23X17 mcp3;   // 0x22
Adafruit_MCP23X17 mcp4;   // 0x23

// Pines Nema 1
#define Step 2    
#define Dir 5     

// Pines Nema 2
#define Step2 3    
#define Dir2 6    

// Pines Nema 3
#define Step3 4    
#define Dir3 7   

#define Enable 8 

// Pines para los finales de carrera (configuración Pull-Up)
const int FCX = 9;  //  X
const int FCY = 10;  // Y
const int FCZ = 11;  // Z

// Variables de nema
int retardo = 800;   // Menor numero = más rápido
unsigned int pasos = 1000;     // 100 pasos ≈ 1 mm
int op = 0;

// Variables de TCS3200
#define NUM_MUESTRAS 15
struct ColorSensor { // Estructura de los sensores
  int s0, s1, s2, s3, out;
};
ColorSensor sensores[3] = { // Pines de las estaciones
  {43, 41, 37, 39, 35}, // Estación 1
  {31, 29, 25, 27, 23}, // Estación 2
  {52, 50, 46, 48, 44}  // Estación 3
};

byte color = 0;
byte comando = 42;
byte recibido = 0;
byte presencia[50];

void setup() {
  Wire.begin();
  Serial.begin(115200);

  pinMode(Step, OUTPUT); pinMode(Dir, OUTPUT); 
  pinMode(Step2, OUTPUT); pinMode(Dir2, OUTPUT);
  pinMode(Step3, OUTPUT); pinMode(Dir3, OUTPUT); 

  pinMode(Enable, OUTPUT);

  pinMode(FCY, INPUT_PULLUP);
  pinMode(FCX, INPUT_PULLUP);
  pinMode(FCZ, INPUT_PULLUP);

  for(int i=0;i<3;i++)
    initSensor(sensores[i]);
  
  initMCPs();
  home();
}

void loop() {
  if (Serial.available() > 0) {
    String datos = Serial.readStringUntil('\n');  // Lee hasta salto de línea
    datos.trim();  // Elimina espacios o \r

    // Opción 1: Parseo con separadores "q0:valor,q1:valor"
    int i0 = datos.indexOf("op:");
    int i1 = datos.indexOf("pasos:");

    if (i0 != -1 && i1 != -1 ) {
      op = datos.substring(i0 + 3, datos.indexOf(',', i0)).toInt();
      pasos = datos.substring(i1 + 6).toInt();

      switch (op) {
        case 0: home();       break;  //seteo home
        case 1: mov_garra(1); break;  //subir
        case 2: mov_garra(2); break;  //bajar
        case 3: mov_garra(3); break;  //izquierda
        case 4: mov_garra(4); break;  //derecha
        case 5: garra(0);     break;  //dentro
        case 6: garra(1);     break;  //fuera
        case 7: //carga estacion 1
          comando = 4;  enviari2c();  esperarACK();
          comando = 10; enviari2c();  esperarACK();
          comando = 1;  enviari2c();  esperarACK(); break;          
        case 8: //carga estacion 2
          comando = 5;  enviari2c();  esperarACK();
          comando = 11; enviari2c();  esperarACK();
          comando = 2;  enviari2c();  esperarACK(); break;         
        case 9: //carga estacion 3
          comando = 6;  enviari2c();  esperarACK();
          comando = 12; enviari2c();  esperarACK();
          comando = 3;  enviari2c();  esperarACK(); break;          
        case 10: //caja estacion 1 -> cartesiano
          garra(1);
          comando = 7;  enviari2c();  esperarACK(); delay(1500);
          garra(0);   break;
        case 11: //caja estacion 2 -> cartesiano
          garra(1);
          comando = 8;  enviari2c();  esperarACK(); delay(1500);
          garra(0);   break;
        case 12: //caja estacion 3 -> cartesiano
          garra(1);
          comando = 9;  enviari2c();  esperarACK(); delay(1500);
          garra(0);   break;
        case 13: //caja cartesiano -> estacion 1 
          garra(1);
          comando = 10;  enviari2c();  esperarACK();
          pasos=100; mov_garra(2);
          garra(0);   break;
        case 14: //caja cartesiano -> estacion 2
          garra(1);
          comando = 11;  enviari2c();  esperarACK();
          pasos=100; mov_garra(2);
          garra(0);   break;
        case 15: //caja cartesiano -> estacion 3
          garra(1);
          comando = 12;  enviari2c();  esperarACK();
          pasos=100; mov_garra(2);
          garra(0);   break;
        case 16: //descarga estacion 1
          comando = 4;  enviari2c();  esperarACK();
          comando = 7;  enviari2c();  esperarACK();
          comando = 1;  enviari2c();  esperarACK();  break;
        case 17: //descarga estacion 2
          comando = 5;  enviari2c();  esperarACK();
          comando = 8;  enviari2c();  esperarACK();
          comando = 2;  enviari2c();  esperarACK();  break;
        case 18: //descarga estacion 2           
          comando = 6;  enviari2c();  esperarACK();
          comando = 9;  enviari2c();  esperarACK();
          comando = 3;  enviari2c();  esperarACK();   break;
        case 19: //lee color estacion 1
          color = leerColorEstacion(0);
          enviarColorSerial(color);   break;
        case 20: //lee color estacion 2
          color = leerColorEstacion(1);
          enviarColorSerial(color);   break;
        case 21: //lee color estacion 3
          color = leerColorEstacion(2);
          enviarColorSerial(color);   break;         
        case 22: //enviar arreglo de sensores
          leerSensoresPresencia(); 
          enviarPresenciaSerial();  break;
      }
      pasos = 0;
      Serial.println("ACK:1");
    }
  }
}

// Funciones MCP
Adafruit_MCP23X17& getMCP(int index)
{
  switch(index)
  {
    case 0: return mcp1;
    case 1: return mcp2;
    case 2: return mcp3;
    case 3: return mcp4;
    default: return mcp1;
  }
}

void initMCPs()
{
  if (!mcp1.begin_I2C(0x20)) while(1);
  if (!mcp2.begin_I2C(0x21)) while(1);
  if (!mcp3.begin_I2C(0x22)) while(1);
  //if (!mcp4.begin_I2C(0x23)) while(1);

  // Todos los pines como entrada con pullup
  // LOW = sensor activo (ocupado)
  // HIGH = vacío
  for(int m=0; m<3; m++)
  {
    for(int p=0; p<16; p++)
    {
      getMCP(m).pinMode(p, INPUT_PULLUP);
    }
  }
}

// LECTURA DE UN SOLO SENSOR
// Devuelve 0 vacío | 1 ocupado
byte leerSensorIndividual(int indice)
{
  int mcpIndex = indice / 16;
  int pin      = indice % 16;

  bool valor = getMCP(mcpIndex).digitalRead(pin);

  // invertimos porque usamos pullup
  return (valor == LOW) ? 1 : 0;
}

// Lee TODOS los 50 sensores y actualiza arreglo
void leerSensoresPresencia()
{
  for(int i=0; i<48; i++)
  {
    presencia[i] = leerSensorIndividual(i);
  }
}

// ENVÍO SERIAL PARA PYTHON
// Formato:
// SENSORS:1,0,0,1,1,0,...
void enviarPresenciaSerial()
{
  Serial.print("SENSORS:");

  for(int i=0;i<50;i++)
  {
    Serial.print(presencia[i]);
    if(i < 49) Serial.print(",");
  }

  Serial.println();
}

// Funciones TCS3200
void initSensor(ColorSensor &s)
{
  pinMode(s.s0, OUTPUT);
  pinMode(s.s1, OUTPUT);
  pinMode(s.s2, OUTPUT);
  pinMode(s.s3, OUTPUT);
  pinMode(s.out, INPUT);

  // Escala frecuencia 100% (máxima precisión)
  digitalWrite(s.s0, HIGH);
  digitalWrite(s.s1, HIGH);
}

int leerCanal(ColorSensor &s, bool s2, bool s3)
{
  digitalWrite(s.s2,s2);
  digitalWrite(s.s3,s3);
  return pulseIn(s.out,LOW);
}

int leerRojo (ColorSensor &s){ return leerCanal(s,LOW,LOW);  }
int leerVerde(ColorSensor &s){ return leerCanal(s,HIGH,HIGH);}
int leerAzul (ColorSensor &s){ return leerCanal(s,LOW,HIGH); }


void leerRGB(byte idx,int &R,int &V,int &A)
{
  long r=0,v=0,a=0;

  for(int i=0;i<NUM_MUESTRAS;i++)
  {
    r+=leerRojo(sensores[idx]);
    v+=leerVerde(sensores[idx]);
    a+=leerAzul(sensores[idx]);
  }

  R=r/NUM_MUESTRAS;
  V=v/NUM_MUESTRAS;
  A=a/NUM_MUESTRAS;

  Serial.print("E"); Serial.print(idx+1);
  Serial.print(" R:"); Serial.print(R);
  Serial.print(" V:"); Serial.print(V);
  Serial.print(" A:"); Serial.println(A);
}


// 1=rojo 2=verde 3=azul

byte clasificarE1(int R,int V,int A)
{
  if(R<25 && V>30) return 1;
  else if(V<23 && A<22) return 2;
  else if(A<16 && R>35) return 3;
  return 0;
}

byte clasificarE2(int R,int V,int A)
{
  if(R < 25 && A < 25 && V > 30) return 1;
  else if(V < 27 && R > 30 && R < 42 && A > 30 && A < 42) return 2;
  else if(R > 43 && A > 43) return 3;
  return 0;
}

byte clasificarE3(int R,int V,int A)
{
  if(R<22 && V>35) return 1;
  else if(V<26 && A>22) return 2;
  else if(A<20 && R>40) return 3;
  return 0;
}

byte clasificarPorEstacion(byte est,int R,int V,int A)
{
  if(est==0) return clasificarE1(R,V,A);
  if(est==1) return clasificarE2(R,V,A);
  if(est==2) return clasificarE3(R,V,A);
  return 0;
}

// Lee una estación específica (0,1,2)
byte leerColorEstacion(byte est)
{
  int R,V,A;
  leerRGB(est,R,V,A);
  return clasificarPorEstacion(est,R,V,A);
}

// Envía todo el arreglo a Python por serial
void enviarColorSerial(byte color)
{
  Serial.print("C:");
  Serial.println(color);
}

// Funciones I2C
void enviari2c(){
  Wire.beginTransmission(SLAVE_ADDR);
  Wire.write(comando);
  Wire.endTransmission();
}

void esperarACK() {
  byte recibido = 0;

  while (true) {
    Wire.requestFrom(SLAVE_ADDR, 1);

    if (Wire.available()) {
      recibido = Wire.read();
      if (recibido == 1) {
        return;   //aquí continúa el programa
      }
    }
    delay(10);  // no saturar el bus
  }
}

// Posición de seteo
void home(){
  garra(0);
  delay(500);
  pasos = 600;
  mov_garra(1);
  delay(1000);
  pasos = 20000;
  mov_garra(3);
  delay(1000);
  pasos = 20000;
  mov_garra(2);
  delay(1000);
}

// Movimiento cartesiano 
void mov_garra(int direccion) {
  bool emergencia = false;
  digitalWrite(Enable, LOW);  // Habilita el Driver

  // Configurar direcciones   //500pasos=100mm
  switch(direccion){
    case 1: // subir
      digitalWrite(Dir, 1);
      digitalWrite(Dir2, 1);
      break;
    case 2: // bajar
      digitalWrite(Dir, 0);
      digitalWrite(Dir2, 0);
      break;
    case 3: // izquierda
      digitalWrite(Dir, 0);
      digitalWrite(Dir2, 1);
      break;
    case 4: // derecha
      digitalWrite(Dir, 1);
      digitalWrite(Dir2, 0);
      break;
  }

  // Movimiento simultáneo
  for (int i = 0; i < pasos; i++) {

    // --- Comprobación de fin de carrera ---
    if (direccion == 2 && digitalRead(FCY) == LOW) emergencia = true;
    if (direccion == 3 && digitalRead(FCX) == LOW) emergencia = true;
    if (emergencia) {
      // Aliviar tensión con 3 pasos cortos
      for (int j = 0; j < 3; j++) {
        digitalWrite(Step, HIGH);
        digitalWrite(Step2, HIGH);
        delayMicroseconds(100);
        digitalWrite(Step, LOW);
        digitalWrite(Step2, LOW);
        delayMicroseconds(100);
      }
      break;
    }
  // --- Paso normal simultáneo ---
  digitalWrite(Step, HIGH);
  digitalWrite(Step2, HIGH);
  delayMicroseconds(retardo);
  digitalWrite(Step, LOW);
  digitalWrite(Step2, LOW);
  delayMicroseconds(retardo);
  }
  digitalWrite(Enable, HIGH);  // Deshabilita el Driver

}

void garra(int direccion){
  bool emergencia = false;
  digitalWrite(Enable, LOW);  // Habilita el Driver
  retardo = 1600;

  // Configurar direcciones
  switch(direccion){
    case 0: // dentro
      digitalWrite(Dir3, 0);
      pasos = 2400;
      break;
    case 1: // afuera
      digitalWrite(Dir3, 1);
      pasos = 240;
      break;  
  }
  for (int i = 0; i < pasos; i++) {
    // --- Comprobación de fin de carrera ---
    if (direccion == 0 && digitalRead(FCZ) == LOW) emergencia = true;
    if (emergencia) {
      // Aliviar tensión con 3 pasos cortos
      for (int j = 0; j < 3; j++) {
        digitalWrite(Step3, HIGH);
        delayMicroseconds(100);
        digitalWrite(Step3, LOW);
        delayMicroseconds(100);
      }
      break;
    }
    // --- Paso normal simultáneo ---
  digitalWrite(Step3, HIGH);
  delayMicroseconds(retardo);
  digitalWrite(Step3, LOW);
  delayMicroseconds(retardo);
  }
  digitalWrite(Enable, HIGH);  // Deshabilita el Driver
  delay(1500);
  retardo = 800;
}
