// Librerias
#include <Servo.h>
#include <Wire.h>

// Dirección del esclavo
#define SLAVE_ADDR 0x30

// Pines Nema 1 ESTACION 1
#define Step 2    
#define Dir 5     

// Pines Nema 2 ESTACION 2
#define Step2 3    
#define Dir2 6    

// Pines Nema 3 ESTACION 3
#define Step3 4    
#define Dir3 7   
#define Enable 8 

// Declaración de servomotores
Servo servogarra1;
Servo servogarra2;
Servo servogarra3;

// Pines para los finales de carrera (configuración Pull-Up)
const int FC1 = 9;   //  Estacion 1 arriba
const int FC2 = 10;  //  Estacion 2 arriba
const int FC3 = 11;  //  Estacion 3 arriba
const int FC4 = 35;  //  Estacion 1 abajo
const int FC5 = 37;  //  Estacion 2 abajo
const int FC6 = 39;  //  Estacion 3 abajo

// Variables de funcionamiento de motores NEMA 17
int retardo = 700;   // Menor numero = más rápido
unsigned int pasos = 0; 

// Variables I2C
volatile byte op = 0;
volatile bool datoRecibido = false;
volatile bool listoParaEnviar = false;
volatile byte respuesta = 0;

void recibirDato(int bytes);
void enviarDato();

void setup() {
  Wire.begin(SLAVE_ADDR);
  Wire.onReceive(recibirDato);
  Wire.onRequest(enviarDato);

  pinMode(Step, OUTPUT); pinMode(Dir, OUTPUT); 
  pinMode(Step2, OUTPUT); pinMode(Dir2, OUTPUT);
  pinMode(Step3, OUTPUT); pinMode(Dir3, OUTPUT); 

  pinMode(Enable, OUTPUT);

  pinMode(FC1, INPUT_PULLUP);
  pinMode(FC2, INPUT_PULLUP);
  pinMode(FC3, INPUT_PULLUP);
  pinMode(FC4, INPUT_PULLUP);
  pinMode(FC5, INPUT_PULLUP);
  pinMode(FC6, INPUT_PULLUP);

  servogarra1.attach(45);
  servogarra2.attach(44);
  servogarra3.attach(46);

  Serial.begin(115200);

  home_estaciones();
  pasos = 30000;
  digitalWrite(Enable, HIGH);  // Deshabilita el Driver
  delay(500);
}

void loop(){
  
  if (datoRecibido) {

    switch (op) {
      case 0: home_estaciones();    delay(1000);    respuesta = 1;  break;  //posicion home
      case 1: estacion(Step, Dir, FC1, FC4, 1);     respuesta = 1;  break;  //sube estacion 1
      case 2: estacion(Step2, Dir2, FC2, FC5, 1);   respuesta = 1;  break;  //sube estacion 2
      case 3: estacion(Step3, Dir3, FC3, FC6, 1);   respuesta = 1;  break;  //sube estacion 3
      case 4: estacion(Step, Dir, FC1, FC4, 0);     respuesta = 1;  break;  //baja estacion 1
      case 5: estacion(Step2, Dir2, FC2, FC5, 0);   respuesta = 1;  break;  //baja estacion 2
      case 6: estacion(Step3, Dir3, FC3, FC6, 0);   respuesta = 1;  break;  //baja estacion 3
      case 7: delay(500); servogarra1.write(90);  delay(500);  respuesta = 1;  break;  //abrir pinza 1
      case 8: delay(500); servogarra2.write(90);  delay(500);  respuesta = 1;  break;  //abrir pinza 2
      case 9: delay(500); servogarra3.write(90);  delay(500);  respuesta = 1;  break;  //abrir pinza 3
      case 10: delay(500);  servogarra1.write(10);  delay(500);  respuesta = 1;  break;  //cerrar pinza 1
      case 11: delay(500);  servogarra2.write(10);  delay(500);  respuesta = 1;  break;  //cerrar pinza 2
      case 12: delay(500);  servogarra3.write(10);  delay(500);  respuesta = 1;  break;  //cerrar pinza 3
    }
    listoParaEnviar = true;
    datoRecibido = false;
  }
}

void recibirDato(int bytes) {
  if (Wire.available()) {
    op = Wire.read();
    listoParaEnviar = false;
    datoRecibido = true;
  }
}

void enviarDato() {
  if (listoParaEnviar) {
    Wire.write(respuesta);
    respuesta = 0;
  } else {
    Wire.write((byte)0x00);
  }
}

void home_estaciones() {

  bool activo1 = true;
  bool activo2 = true;
  bool activo3 = true;

  servogarra1.write(90);
  servogarra2.write(90);
  servogarra3.write(90);
  delay(1000);
  
  digitalWrite(Enable, LOW);

  digitalWrite(Dir,  1);
  digitalWrite(Dir2, 1);
  digitalWrite(Dir3, 1);

  while (activo1 || activo2 || activo3) {

    // --- Leer finales ---
    if (activo1 && digitalRead(FC4) == LOW) {
      activo1 = false;
      for (int j = 0; j < 3; j++) {   // alivio
        digitalWrite(Step, HIGH);
        delayMicroseconds(100);
        digitalWrite(Step, LOW);
        delayMicroseconds(100);
      }
    }

    if (activo2 && digitalRead(FC5) == LOW) {
      activo2 = false;
      for (int j = 0; j < 3; j++) {
        digitalWrite(Step2, HIGH);
        delayMicroseconds(100);
        digitalWrite(Step2, LOW);
        delayMicroseconds(100);
      }
    }

    if (activo3 && digitalRead(FC6) == LOW) {
      activo3 = false;
      for (int j = 0; j < 3; j++) {
        digitalWrite(Step3, HIGH);
        delayMicroseconds(100);
        digitalWrite(Step3, LOW);
        delayMicroseconds(100);
      }
    }

    // --- Generar pasos SOLO a los activos ---
    if (activo1) digitalWrite(Step, HIGH);
    if (activo2) digitalWrite(Step2, HIGH);
    if (activo3) digitalWrite(Step3, HIGH);

    delayMicroseconds(retardo);

    if (activo1) digitalWrite(Step, LOW);
    if (activo2) digitalWrite(Step2, LOW);
    if (activo3) digitalWrite(Step3, LOW);

    delayMicroseconds(retardo);
  }

  digitalWrite(Enable, HIGH);
}


void estacion(int Step_, int Dir_, int FCT_, int FCB_, int Direccion) {

  if (Direccion == 1 && FCB_ == LOW) return;
  if (Direccion == 0 && FCT_ == LOW) return;

  bool emergencia = false;
  digitalWrite(Enable, LOW);  // Habilita el Driver

  // Configurar dirección
  digitalWrite(Dir_, Direccion ? HIGH : LOW);
  delayMicroseconds(50);

  for (int i = 0; i < pasos; i++) {
    // --- Comprobación de fin de carrera ---
    if (Direccion == 1 && digitalRead(FCB_) == LOW) emergencia = true;
    if (Direccion == 0 && digitalRead(FCT_) == LOW) emergencia = true;
    if (emergencia) {
      // Aliviar tensión con 3 pasos cortos
      for (int j = 0; j < 3; j++) {
        digitalWrite(Step_, HIGH);
        delayMicroseconds(100);
        digitalWrite(Step_, LOW);
        delayMicroseconds(100);
      }
      break;
    }
    // --- Paso normal simultáneo ---
  digitalWrite(Step_, HIGH);
  delayMicroseconds(retardo);
  digitalWrite(Step_, LOW);
  delayMicroseconds(retardo);
  }
  digitalWrite(Enable, HIGH);  // Deshabilita el Driver
  delay(1000);
}
