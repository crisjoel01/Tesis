// --- Pines asignados para Arduino Mega ---
#define S0 30
#define S1 31
#define S2 32
#define S3 33
#define OUT_PIN 34

// --- Variables para frecuencias ---
unsigned long redFreq, greenFreq, blueFreq;

// --- Variables para conteo ---
int redCount = 0;
int greenCount = 0;
int blueCount = 0;

void setup() {
  Serial.begin(9600);

  pinMode(S0, OUTPUT);
  pinMode(S1, OUTPUT);
  pinMode(S2, OUTPUT);
  pinMode(S3, OUTPUT);
  pinMode(OUT_PIN, INPUT);

  // Escala de frecuencia al 20%
  digitalWrite(S0, HIGH);
  digitalWrite(S1, LOW);

  Serial.println("Sensor TCS230 listo");
}

void loop() {
  redCount = greenCount = blueCount = 0; // reinicia los contadores

  Serial.println("\n--- Iniciando grupo de 5 lecturas ---");

  for (int i = 1; i <= 5; i++) {
    // --- Medir ROJO ---
    digitalWrite(S2, LOW);
    digitalWrite(S3, LOW);
    redFreq = pulseIn(OUT_PIN, LOW);

    // --- Medir VERDE ---
    digitalWrite(S2, HIGH);
    digitalWrite(S3, HIGH);
    greenFreq = pulseIn(OUT_PIN, LOW);

    // --- Medir AZUL ---
    digitalWrite(S2, LOW);
    digitalWrite(S3, HIGH);
    blueFreq = pulseIn(OUT_PIN, LOW);

    // Mostrar lectura actual
    Serial.print("Lectura ");
    Serial.print(i);
    Serial.print(" -> R:");
    Serial.print(redFreq);
    Serial.print("  G:");
    Serial.print(greenFreq);
    Serial.print("  B:");
    Serial.println(blueFreq);

    // Determinar color dominante en esta lectura
    String colorLeido;
    if (redFreq < greenFreq && redFreq < blueFreq) {
      colorLeido = "ROJO";
      redCount++;
    } else if (greenFreq < redFreq && greenFreq < blueFreq) {
      colorLeido = "VERDE";
      greenCount++;
    } else if (blueFreq < redFreq && blueFreq < greenFreq) {
      colorLeido = "AZUL";
      blueCount++;
    } else {
      colorLeido = "INDEFINIDO";
    }

    Serial.print("Color detectado: ");
    Serial.println(colorLeido);
    delay(500); // pequeño retardo entre lecturas
  }

  // --- Evaluar cuál color predominó ---
  Serial.println("\nResultado del grupo de 5 lecturas:");
  Serial.print("ROJO: "); Serial.println(redCount);
  Serial.print("VERDE: "); Serial.println(greenCount);
  Serial.print("AZUL: "); Serial.println(blueCount);

  if (redCount > greenCount && redCount > blueCount) {
    Serial.println("Color final detectado: ROJO");
  } else if (greenCount > redCount && greenCount > blueCount) {
    Serial.println("Color final detectado: VERDE");
  } else if (blueCount > redCount && blueCount > greenCount) {
    Serial.println("Color final detectado: AZUL");
  } else {
    Serial.println("Color final: INDEFINIDO o MEZCLA");
  }

  Serial.println("----------------------------");

  // Espera 5 segundos antes del siguiente grupo de lecturas
  delay(5000);
}
