
// Pines Nema 17 eje Z
#define Step 27    // Define el Pin de STEP para Motor de eje z
#define Dir 26    // Define el Pin de DIR  para Motor de eje z
#define Enable 25    // Define el Pin de ENABLE  para Motor de eje z

//Pines Nema 17 eje x
#define Step2 5    // Define el Pin de STEP para Motor de eje x
#define Dir2 18    // Define el Pin de DIR  para Motor de eje x
#define Enable2 19    // Define el Pin de ENABLE  para Motor de eje x

int retardo = 800;   // Menor numero el giro es mas rapido
int pasos = 1000;   // 100pasos==1mm

void setup() {
//Inicializaciòn de motores Nema
pinMode(Step, OUTPUT); pinMode(Dir, OUTPUT); pinMode(Enable, OUTPUT);
pinMode(Step2, OUTPUT); pinMode(Dir2, OUTPUT); pinMode(Enable2, OUTPUT);     
}    

void loop() {
  giro(Step,Dir,Enable,1);
  giro(Step2,Dir2,Enable2,1);
  delay(1000);
  giro(Step,Dir,Enable,0);
  giro(Step2,Dir2,Enable2,0);
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
  digitalWrite(habi_, HIGH);   // quita la habilitacion del Driver

}