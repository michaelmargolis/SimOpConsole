/***************************************************
  Web_Switches_json.ino
  ---------------------------------
  • Hosts the Ops‑Console web page from LittleFS.
  • Accepts POST /cmd (plain text).
  • Maintains virtual switch states and streams JSON
    instead of the old CSV packets.
***************************************************/
#include <Arduino.h>
#include <LittleFS.h>

#ifdef ARDUINO_ARCH_RP2040
  #include <WiFi.h>
  #include <WebServer.h>
#else
  #include <WiFi.h>
  #include <WebServer.h>
#endif

/************* Wi‑Fi credentials ********************/
const char* AP_SSID     = "Falcon2_switches";
const char* AP_PASSWORD = "Falcon_2";

/************* Web‑server ***************************/
WebServer server(80);

/************* Serial/packet config ****************/
#define MSG_INTERVAL_MS 50
#define NBR_SWITCHES    7                        // fly, pause, activate, assist, mode, load, intensity

/* ---------- key list in JSON order ------------- */
const char* KEY[NBR_SWITCHES] = {
  "fly","pause","activate","assist","mode","load","intensity"
};

/************* run‑time state **********************/
int  switchStates[NBR_SWITCHES]   = {0};         // current latched state
int  lastSentStates[NBR_SWITCHES] = {0};         // snapshot we last emitted
unsigned long lastMomentaryMs[2]  = {0};         // index 0 = fly, 1 = pause
const unsigned long MOMENTARY_MS  = 250;

/* ---------- helpers: JSON streaming ------------ */
void sendJson(bool deltaOnly)
{
  Serial.print('{');
  bool first = true;

  for (int i = 0; i < NBR_SWITCHES; ++i) {
    if (deltaOnly && switchStates[i] == lastSentStates[i]) continue;

    if (!first) Serial.print(',');
    Serial.print('"'); Serial.print(KEY[i]); Serial.print("\":");
    Serial.print(switchStates[i]);
    first = false;
  }
  Serial.println('}');
  memcpy(lastSentStates, switchStates, sizeof(lastSentStates));
}

/*********** command → state mapping ***************/
void applyCommand(const String& cmd)
{
  bool changed = false;

  /* --- momentary buttons --- */
  if (cmd == "FLY")   { switchStates[0] = 1; lastMomentaryMs[0] = millis(); changed = true; }
  if (cmd == "PAUSE") { switchStates[1] = 1; lastMomentaryMs[1] = millis(); changed = true; }

  /* --- toggle (activate) --- */
  if (cmd == "ACTIVATE")   { switchStates[2] = 1; changed = true; }
  if (cmd == "DEACTIVATE") { switchStates[2] = 0; changed = true; }

  /* --- three‑way groups --- */
  if (cmd == "PA_HIGH") switchStates[3] = 0, changed = true;
  if (cmd == "PA_MID")  switchStates[3] = 1, changed = true;
  if (cmd == "PA_LOW")  switchStates[3] = 2, changed = true;

  if (cmd == "FM_STANDARD") switchStates[4] = 0, changed = true;
  if (cmd == "FM_SCENIC")   switchStates[4] = 1, changed = true;
  if (cmd == "FM_CUSTOM")   switchStates[4] = 2, changed = true;

  if (cmd == "LOAD_HEAVY")    switchStates[5] = 0, changed = true;
  if (cmd == "LOAD_MODERATE") switchStates[5] = 1, changed = true;
  if (cmd == "LOAD_LIGHT")    switchStates[5] = 2, changed = true;

  if (cmd == "INT_STATIC") switchStates[6] = 0, changed = true;
  if (cmd == "INT_MILD")   switchStates[6] = 1, changed = true;
  if (cmd == "INT_FULL")   switchStates[6] = 2, changed = true;

  if (changed) sendJson(true);                      // delta packet
}

/*********** HTTP handlers *************************/
void handleRoot()
{
  File f = LittleFS.open("/index.html", "r");
  if (!f) { server.send(404, "text/plain", "index.html not found"); return; }
  server.streamFile(f, "text/html");  f.close();
}

void handleCmd()
{
  applyCommand(server.arg("plain"));
  server.send(204);                                  // No Content
}

/*********** LittleFS init *************************/
bool initLittleFS()
{
#if defined(ARDUINO_ARCH_RP2040)
  if (LittleFS.begin()) return true;
  Serial.println("LittleFS mount failed – formatting");
  LittleFS.format();
  return LittleFS.begin();
#elif defined(ARDUINO_ARCH_ESP32)
  return LittleFS.begin(true);                       // format on fail
#endif
}

/*********** setup *********************************/
void setup()
{
  Serial.begin(115200);
  delay(200);
  initLittleFS();

  /* Wi‑Fi soft‑AP */
  WiFi.softAP(AP_SSID, AP_PASSWORD);
  Serial.print("AP IP: "); Serial.println(WiFi.softAPIP());

  /* HTTP routes */
  server.on("/",   HTTP_GET,  handleRoot);
  server.on("/cmd",HTTP_POST, handleCmd);
  server.begin();
  Serial.println("HTTP server started");

  /* defaults (Moderate, Mid, Standard, Mild) */
  switchStates[5] = 1;
  switchStates[3] = 1;
  switchStates[4] = 0;
  switchStates[6] = 1;
  sendJson(false);                                   // initial full
}

/*********** main loop ******************************/
void loop()
{
  server.handleClient();

  /* auto‑reset momentary buttons */
  unsigned long now = millis();
  if (switchStates[0] && now - lastMomentaryMs[0] > MOMENTARY_MS) {
    switchStates[0] = 0; sendJson(true);
  }
  if (switchStates[1] && now - lastMomentaryMs[1] > MOMENTARY_MS) {
    switchStates[1] = 0; sendJson(true);
  }

  /* periodic heartbeat */
  static unsigned long prevMs = 0;
  if (now - prevMs >= MSG_INTERVAL_MS) {
    prevMs = now;
    bool identical = true;
    for (int i = 0; i < NBR_SWITCHES && identical; ++i)
      identical &= (switchStates[i] == lastSentStates[i]);
    if (identical) sendJson(false);                  // full snapshot
  }
}
