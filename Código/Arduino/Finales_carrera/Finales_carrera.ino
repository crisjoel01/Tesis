
// Pines para los finales de carrera (configuración Pull-Down)
const int FC1 = 9;  //  Yabajo
const int FC2 = 10;  //  Xarriba
const int FC3 = 11;  // Zdentro

void setup() {
  // Inicializar comunicación serial
  Serial.begin(9600);
  
  // Configurar pines como entradas con Pull-Down interno
  pinMode(FC1, INPUT_PULLUP);
  pinMode(FC2, INPUT_PULLUP);
  pinMode(FC3, INPUT_PULLUP);
  
  Serial.println("Iniciando prueba de finales de carrera (Pull-Down)...");
  Serial.println("Estado de los finales de carrera (1 = pulsado, 0 = libre):");
}

void loop() {
  
  Serial.println("Probando finales de carrera...");
  Serial.print("FC1: "); Serial.println(digitalRead(FC1));
  Serial.print("FC2: "); Serial.println(digitalRead(FC2));
  Serial.print("FC3: "); Serial.println(digitalRead(FC3));
  delay(1000);
}
