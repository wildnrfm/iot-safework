// Uji rakitan SAFEWORK AI (tanpa aplikasi). Sesuaikan pin dengan rakitanmu.
const int PIN_HIJAU  = 25;
const int PIN_KUNING = 26;
const int PIN_MERAH  = 27;
const int PIN_BUZZER = 14;   // lewat transistor NPN: HIGH = bunyi

const int LED_PIN[] = {PIN_HIJAU, PIN_KUNING, PIN_MERAH};
const char* LED_NAMA[] = {"hijau", "kuning", "merah"};

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < 3; i++) {
    pinMode(LED_PIN[i], OUTPUT);
    digitalWrite(LED_PIN[i], LOW);
  }
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_BUZZER, LOW);
  Serial.println("Uji rakitan dimulai");
}

void loop() {
  for (int i = 0; i < 3; i++) {
    Serial.printf("LED %s menyala\n", LED_NAMA[i]);
    digitalWrite(LED_PIN[i], HIGH);
    delay(1000);
    digitalWrite(LED_PIN[i], LOW);
    delay(300);
  }
  Serial.println("Buzzer berbunyi 3 kali");
  for (int i = 0; i < 3; i++) {
    digitalWrite(PIN_BUZZER, HIGH);
    delay(200);
    digitalWrite(PIN_BUZZER, LOW);
    delay(200);
  }
  delay(1500);
}
