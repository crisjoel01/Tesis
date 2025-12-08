// ----------------------------------------------------
// Control de motor DC con L298N (lado derecho)
// Conexiones:
//   ENB → puente colocado (velocidad máxima)
//   IN3 → pin 8
//   IN4 → pin 9
//   OUT3 y OUT4 → Motor DC
// ----------------------------------------------------

const int IN3 = 8;   // Dirección 1
const int IN4 = 9;   // Dirección 2

const unsigned long t_giro = 300;
const unsigned long t_giro1 = 800;   // 1 segundo de giro
const unsigned long t_espera = 3000; // 5 segundos de pausa

void setup() {
  Serial.begin(9600);
  pinMode(IN3, OUTPUT);
  pinMode(IN4, OUTPUT);

  detener();
  Serial.println("Sistema iniciado. Motor detenido.");
}

void loop() {
  // Giro en sentido horario
  Serial.println("Giro en sentido horario...");
  digitalWrite(IN3, HIGH);
  digitalWrite(IN4, LOW);
  delay(t_giro);

  // Detener motor y esperar
  detener();
  Serial.println("Motor detenido. Esperando 5 segundos...");
  delay(t_espera);

  // Giro en sentido antihorario
  Serial.println("Giro en sentido antihorario...");
  digitalWrite(IN3, LOW);
  digitalWrite(IN4, HIGH);
  delay(t_giro1);

    // Detener motor y esperar
  detener();
  Serial.println("Motor detenido. Esperando 5 segundos...");
  delay(t_espera);

  // Detener motor antes de repetir
  detener();
  Serial.println("Motor detenido. Reiniciando ciclo...\n");
  delay(500);
}

void detener() {
  digitalWrite(IN3, LOW);
  digitalWrite(IN4, LOW);
}
