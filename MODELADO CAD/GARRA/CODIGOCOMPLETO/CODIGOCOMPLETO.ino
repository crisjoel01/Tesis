// Pines Nema 17 eje Z
#define Step 40    // Define el Pin de STEP para Motor de eje z
#define Dir 41   // Define el Pin de DIR  para Motor de eje z
#define Enable 42    // Define el Pin de ENABLE  para Motor de eje z

#include <Servo.h>

Servo servoMotor;
const int pinServo = 6;  // Pin de señal del servo

const int usMin = 1000;   // Pulso mínimo (ajusta según tu servo)
const int usMax = 2400;  // Pulso máximo

int retardo = 600;   // Menor numero el giro es mas rapido
int pasos = 10000;   // 100pasos==1mm

void setup() {
  Serial.begin(9600);
  servoMotor.attach(pinServo, usMin, usMax);

  // Posición inicial (apertura)
  servoMotor.write(80);
  Serial.println("Servo en apertura inicial (80°)");

//Inicializaciòn de motores Nema
pinMode(Step, OUTPUT); pinMode(Dir, OUTPUT); pinMode(Enable, OUTPUT);
 }


void loop() {
    Serial.println("Abriendo poco a poco...");
  for (int pos = 10; pos <= 80; pos++) {
    servoMotor.write(pos);
    delay(10);  // 10 ms por grado
  }

  Serial.println("Abierto completamente (80°)");
  delay(1000);  // Mantener abierto 2 segundos

  giro(Step,Dir,Enable,0);
  delay(1000);

   Serial.println("Cerrando poco a poco...");
  for (int pos = 80; pos >= 10; pos--) {
    servoMotor.write(pos);
    delay(10);  // 10 ms por grado
  }

  Serial.println("Cerrado completamente (12°)");
  delay(1000);  // Mantener cerrado 2 segundos

  giro(Step,Dir,Enable,1);
  delay(1000);
 }


void giro(int paso_,int dire_,int habi_,int dir) {
  digitalWrite(habi_, LOW);  // Habilita el Driver
  if( dir==0){ // Bajar eje
   digitalWrite(dire_, LOW);   // direccion de giro 0
   for(int i=0;i<pasos;i++){  // da  pasos por un pasos  
    digitalWrite(paso_, HIGH);      
    delayMicroseconds(retardo);          
    digitalWrite(paso_, LOW);       
    delayMicroseconds(retardo); 
   }
  }
  if( dir==1){ // Subir eje
  digitalWrite(dire_, HIGH);   // direccion de giro 1
  for(int i=0;i<pasos;i++){   // da  pasos por un pasos  
    digitalWrite(paso_, HIGH);      
    delayMicroseconds(retardo);          
    digitalWrite(paso_, LOW);       
    delayMicroseconds(retardo);  
   }
  }
  digitalWrite(habi_, HIGH);   // quita la habilitacion del Driver

}