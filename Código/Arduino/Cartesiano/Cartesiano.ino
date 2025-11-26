// Pines Nema 1
#define Step 2    
#define Dir 5     
#define Enable 8    

// Pines Nema 2
#define Step2 3    
#define Dir2 6    
#define Enable2 8  

// Pines para los finales de carrera (configuración Pull-Up)
const int FC1 = 9;  //  Y
const int FC2 = 10;  //  X
const int FC3 = 11;  // Z

int retardo = 1000;   // Menor numero = más rápido
int pasos = 1000;     // 100 pasos ≈ 1 mm

void setup() {
  pinMode(Step, OUTPUT); pinMode(Dir, OUTPUT); pinMode(Enable, OUTPUT);
  pinMode(Step2, OUTPUT); pinMode(Dir2, OUTPUT); pinMode(Enable2, OUTPUT);

  pinMode(FC1, INPUT_PULLUP);
  pinMode(FC2, INPUT_PULLUP);
  pinMode(FC3, INPUT_PULLUP);
  home();
}

void loop() {
  


  
}

void home(){
  pasos = 10000;
  giroDual(3);
  delay(1000);
  giroDual(2);
  delay(1000);

}


// ---------------------------
//  FUNCIÓN SIMULTÁNEA
// ---------------------------
void giroDual(int direccion) {
  bool emergencia = false;

  // Habilitar drivers
  digitalWrite(Enable, LOW);
  digitalWrite(Enable2, LOW);

  // Configurar direcciones
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
    if (direccion == 2 && digitalRead(FC1) == LOW) emergencia = true;
    if (direccion == 3 && digitalRead(FC2) == LOW) emergencia = true;

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

  // Deshabilitar drivers
  digitalWrite(Enable, HIGH);
  digitalWrite(Enable2, HIGH);
}
