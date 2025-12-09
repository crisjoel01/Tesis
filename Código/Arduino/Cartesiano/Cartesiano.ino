// Pines Nema 1
#define Step 2    
#define Dir 5     
#define Enable 8    

// Pines Nema 2
#define Step2 3    
#define Dir2 6    
#define Enable2 8 

// Pines Nema 3
#define Step3 4    
#define Dir3 7    
#define Enable3 8 

// Pines para los finales de carrera (configuración Pull-Up)
const int FC1 = 9;  //  Y
const int FC2 = 10;  //  X
const int FC3 = 11;  // Z

int retardo = 800;   // Menor numero = más rápido
int pasos = 1000;     // 100 pasos ≈ 1 mm

void setup() {
  pinMode(Step, OUTPUT); pinMode(Dir, OUTPUT); pinMode(Enable, OUTPUT);
  pinMode(Step2, OUTPUT); pinMode(Dir2, OUTPUT); pinMode(Enable2, OUTPUT);

  pinMode(FC1, INPUT_PULLUP);
  pinMode(FC2, INPUT_PULLUP);
  pinMode(FC3, INPUT_PULLUP);
  home();
  //pasos=1000; //1000pasos=100mm
  pasos=1000;
  mover(1);
  delay(1000);
  mover(4);
  delay(1000);
}

void loop() {
  pasos=3000; ///500 pasos son 50mm
  mover(1);
  delay(2500);

  mover(4);
  delay(2500);

  mover(2);
  delay(2500);

  mover(3);
  delay(2500);

  
}

void home(){
  pasos = 500;
  mover(5);
  delay(1000);
  mover(1);
  delay(1000);
  pasos = 20000;
  mover(3);
  delay(1000);
  mover(2);
  delay(1000);
  

}


// ---------------------------
//  FUNCIÓN SIMULTÁNEA
// ---------------------------
void mover(int direccion) {
  bool emergencia = false;

  // Habilitar drivers
  digitalWrite(Enable, LOW);
  digitalWrite(Enable2, LOW);
  digitalWrite(Enable3, LOW);

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
    case 5: // dentro
      digitalWrite(Dir3, 0);
      break;
    case 6: // afuera
      digitalWrite(Dir3, 1);
      break;  
  }

  // Movimiento simultáneo
  for (int i = 0; i < pasos; i++) {

    // --- Comprobación de fin de carrera ---
    if (direccion == 2 && digitalRead(FC1) == LOW) emergencia = true;
    if (direccion == 3 && digitalRead(FC2) == LOW) emergencia = true;
    if (direccion == 5 && digitalRead(FC3) == LOW) emergencia = true;

    if (emergencia) {
      // Aliviar tensión con 3 pasos cortos
      for (int j = 0; j < 3; j++) {
        if (direccion == 5 || direccion == 6){
          digitalWrite(Step3, HIGH);
        } else{
          digitalWrite(Step, HIGH);
          digitalWrite(Step2, HIGH);
        }
        delayMicroseconds(100);
        if (direccion == 5 || direccion == 6){
          digitalWrite(Step3, LOW);
        } else{
          digitalWrite(Step, LOW);
          digitalWrite(Step2, LOW);
        }
        delayMicroseconds(100);
      }
      break;
    }

    // --- Paso normal simultáneo ---
    if (direccion == 5 || direccion == 6){
      digitalWrite(Step3, HIGH);
    } else{
      digitalWrite(Step, HIGH);
      digitalWrite(Step2, HIGH);
    }
    delayMicroseconds(retardo);

    if (direccion == 5 || direccion == 6){
      digitalWrite(Step3, LOW);
    } else{
      digitalWrite(Step, LOW);
      digitalWrite(Step2, LOW);
    }
    delayMicroseconds(retardo);
  }

  // Deshabilitar drivers
  digitalWrite(Enable, HIGH);
  digitalWrite(Enable2, HIGH);
  digitalWrite(Enable3, HIGH); 
}
