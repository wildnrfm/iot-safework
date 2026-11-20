/*
  SAFEWORK AI - Firmware indikator (ESP32 DevKit)

  Tiga LED (hijau, kuning, merah) dan buzzer aktif lewat transistor NPN.
  Dikendalikan laptop lewat USB Serial, 115200 baud, satu perintah per baris:

      GREEN | YELLOW | RED | OFF | FAULT | TEST | PING

  Balasan ke laptop: READY (saat boot), OK, PONG, ERR.

  Mode aman: bila tidak ada perintah/PING selama LINK_TIMEOUT_MS, lampu kuning berkedip supaya
  lampu hijau yang lama tidak menyesatkan. Perintah valid berikutnya memulihkan sambungan; lampu
  mati sampai laptop mengirim status baru. Perintah FAULT dari laptop (mis. kamera terputus)
  menghasilkan tampilan yang sama (kuning berkedip).

  Pengkabelan (ESP32 DevKit V1):
    GPIO25 -> resistor 220-330 ohm -> anoda LED hijau,  katoda ke GND
    GPIO26 -> resistor 220-330 ohm -> anoda LED kuning, katoda ke GND
    GPIO27 -> resistor 220-330 ohm -> anoda LED merah,  katoda ke GND
    GPIO33 -> resistor 1 kohm -> basis transistor NPN (mis. 2N2222, BC547, atau S8050)
              emitor ke GND, kolektor ke kaki (-) buzzer, kaki (+) buzzer ke VIN (5V dari USB)
*/

#include <Arduino.h>
#include <ctype.h>
#include <string.h>

constexpr uint8_t PIN_GREEN = 25;
constexpr uint8_t PIN_YELLOW = 26;
constexpr uint8_t PIN_RED = 27;
constexpr uint8_t PIN_BUZZER = 33;

constexpr unsigned long LINK_TIMEOUT_MS = 5000;  // tanpa perintah selama ini => mode aman
constexpr unsigned long BLINK_MS = 500;          // kedip kuning pada mode aman
constexpr uint8_t RED_BEEPS = 3;                 // jumlah bip saat status merah
constexpr unsigned long BEEP_ON_MS = 200;
constexpr unsigned long BEEP_OFF_MS = 150;

enum Mode : uint8_t { MODE_OFF, MODE_GREEN, MODE_YELLOW, MODE_RED, MODE_FAULT };

Mode mode = MODE_OFF;
bool linkLost = false;
unsigned long lastRxMs = 0;

bool buzzerOn = false;
uint8_t beepsLeft = 0;
unsigned long buzzerChangedMs = 0;

bool blinkLit = false;          // keadaan kedip lampu kuning pada MODE_FAULT
unsigned long lastBlinkMs = 0;

char lineBuf[24];
uint8_t lineLen = 0;

void setLeds(bool green, bool yellow, bool red) {
  digitalWrite(PIN_GREEN, green ? HIGH : LOW);
  digitalWrite(PIN_YELLOW, yellow ? HIGH : LOW);
  digitalWrite(PIN_RED, red ? HIGH : LOW);
}

void setBuzzer(bool on) {
  digitalWrite(PIN_BUZZER, on ? HIGH : LOW);
  buzzerOn = on;
  buzzerChangedMs = millis();
}

// Bunyikan buzzer `count` kali tanpa menahan loop(). count = 0 membatalkan bunyi.
void startBeeps(uint8_t count) {
  beepsLeft = count;
  setBuzzer(count > 0);
}

void updateBuzzer() {
  const unsigned long now = millis();
  if (buzzerOn) {
    if (now - buzzerChangedMs >= BEEP_ON_MS) {
      setBuzzer(false);
      if (beepsLeft > 0) beepsLeft--;
    }
  } else if (beepsLeft > 0 && now - buzzerChangedMs >= BEEP_OFF_MS) {
    setBuzzer(true);
  }
}

void showLeds(Mode m) {
  switch (m) {
    case MODE_GREEN:  setLeds(true, false, false); break;
    case MODE_YELLOW: setLeds(false, true, false); break;
    case MODE_RED:    setLeds(false, false, true); break;
    default:          setLeds(false, false, false); break;  // OFF; FAULT dikedipkan di loop()
  }
}

// Perintah yang sama berulang tidak mengulang bunyi (idempoten).
void applyMode(Mode next) {
  if (next == mode) return;
  mode = next;
  showLeds(mode);
  startBeeps(mode == MODE_RED ? RED_BEEPS : 0);
  if (mode == MODE_FAULT) {  // mulai berkedip segera: fase pertama = menyala
    blinkLit = false;
    lastBlinkMs = millis() - BLINK_MS;
  }
}

// Uji: hijau, kuning, merah + bip singkat, lalu kembali ke keadaan semula (menahan loop() +-1,5 detik).
void runTest() {
  const Mode previous = mode;
  startBeeps(0);
  setLeds(true, false, false);
  delay(400);
  setLeds(false, true, false);
  delay(400);
  setLeds(false, false, true);
  setBuzzer(true);
  delay(250);
  setBuzzer(false);
  delay(400);
  showLeds(previous);
  lastRxMs = millis();
}

void handleCommand(const char *cmd) {
  lastRxMs = millis();
  if (linkLost) {  // sambungan pulih: lampu mati sampai laptop mengirim status baru
    linkLost = false;
    applyMode(MODE_OFF);
  }
  if (strcmp(cmd, "PING") == 0) {
    Serial.println("PONG");
    return;
  }
  if (strcmp(cmd, "GREEN") == 0) applyMode(MODE_GREEN);
  else if (strcmp(cmd, "YELLOW") == 0) applyMode(MODE_YELLOW);
  else if (strcmp(cmd, "RED") == 0) applyMode(MODE_RED);
  else if (strcmp(cmd, "OFF") == 0) applyMode(MODE_OFF);
  else if (strcmp(cmd, "FAULT") == 0) applyMode(MODE_FAULT);
  else if (strcmp(cmd, "TEST") == 0) runTest();
  else {
    Serial.println("ERR");
    return;
  }
  Serial.println("OK");
}

void readSerial() {
  while (Serial.available() > 0) {
    const char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      lineBuf[lineLen] = '\0';
      if (lineLen > 0) {
        for (uint8_t i = 0; i < lineLen; i++) lineBuf[i] = (char)toupper((unsigned char)lineBuf[i]);
        handleCommand(lineBuf);
      }
      lineLen = 0;
    } else if (lineLen < sizeof(lineBuf) - 1) {
      lineBuf[lineLen++] = c;
    } else {
      lineLen = 0;  // baris terlalu panjang: buang
    }
  }
}

void setup() {
  pinMode(PIN_GREEN, OUTPUT);
  pinMode(PIN_YELLOW, OUTPUT);
  pinMode(PIN_RED, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  setLeds(false, false, false);
  setBuzzer(false);
  Serial.begin(115200);
  lastRxMs = millis();
  Serial.println("READY");
}

void loop() {
  readSerial();
  updateBuzzer();

  if (!linkLost && millis() - lastRxMs > LINK_TIMEOUT_MS) {
    linkLost = true;
    applyMode(MODE_FAULT);
  }

  if (mode == MODE_FAULT && millis() - lastBlinkMs >= BLINK_MS) {  // FAULT dari laptop maupun sambungan putus
    lastBlinkMs = millis();
    blinkLit = !blinkLit;
    setLeds(false, blinkLit, false);
  }
}
