/******************************
  Serial_switch_reader_json.ino
  ----------------------------------
  • Reads 7 hardware switches (same pins as original).
  • Sends JSON over SERIAL_OUT:

      {"fly":0,"pause":0,"activate":1,"assist":1,
       "mode":0,"load":1,"intensity":1}      ← every 250 ms

      {"pause":1}                            ← immediately on change

  No ArduinoJson library, no dynamic memory.
******************************/
// #define USE_USB_SERIAL               // COMMENT OUT IF USING TTL
#ifdef USE_USB_SERIAL
  #define SERIAL_OUT Serial
#else
  #define SERIAL_OUT Serial1
#endif

#define MSG_INTERVAL_MS 250           // 20 updates per second
#define NBR_SWITCHES 7

/* ────────── MultiSwitch (added key + printJson) ────────── */
class MultiSwitch {
  const char* key;                         // NEW – JSON field name
  int  pin1, pin2;
  int  lastState, currentState;
  unsigned long lastDebounceTime, debounceDelay;
  bool singlePinMode;

public:
  MultiSwitch(const char* k, int p1, int p2 = -1, unsigned long db = 20)
    : key(k), pin1(p1), pin2(p2), lastState(-1), currentState(-1),
      lastDebounceTime(0), debounceDelay(db), singlePinMode(p2 == -1) {}

  void begin() {
    pinMode(pin1, INPUT_PULLUP);
    if (!singlePinMode) pinMode(pin2, INPUT_PULLUP);
  }

  int getState() {
    int newState;
    if (singlePinMode)
      newState = (digitalRead(pin1) == LOW) ? 1 : 0;
    else {
      int r1 = digitalRead(pin1), r2 = digitalRead(pin2);
      newState = (r1 == LOW) ? 0 : (r2 == LOW ? 2 : 1);
    }

    if (newState != lastState) lastDebounceTime = millis();
    if (millis() - lastDebounceTime > debounceDelay) currentState = newState;
    lastState = newState;
    return currentState;
  }

  /* stream  "key":value  , add leading comma when needed */
  void printJson(Stream& out, bool& first) const {
    if (!first) out.print(',');
    out.print('"'); out.print(key); out.print("\":");
    out.print(currentState);
    first = false;
  }
};

// ----------------- Power State Machine ---------------------
enum SystemState { OFF_STATE, BOOT_REQUEST, RUNNING, SHUTDOWN_REQUEST };

class PowerStateMachine {
  const int bootPin;         // Arduino pin for boot button (from Pi GPIO3)
  const int shutdownPin;     // Arduino pin for shutdown indicator (from Pi GPIO2, via overlay)
  const int runPin;          // Arduino pin used to drive the Pi's RUN header
  const unsigned long runPulseDuration; // Duration to pulse RUN pin (in ms)

  SystemState state;
  
  // Instead of nonblocking pulse logic, we'll use a blocking delay.
  void pulseRunPin() {
    digitalWrite(runPin, LOW);
    delay(runPulseDuration); // blocking delay: e.g. 100ms
    digitalWrite(runPin, HIGH);
  }
  
public:
  PowerStateMachine(int bootPin, int shutdownPin, int runPin, unsigned long runPulseDuration = 100)
    : bootPin(bootPin), shutdownPin(shutdownPin), runPin(runPin),
      runPulseDuration(runPulseDuration), state(OFF_STATE) {}
      
  // Call update() frequently in loop()
  void update() {
    int bootVal = digitalRead(bootPin);         // LOW means button pressed
    int shutdownVal = digitalRead(shutdownPin);   // LOW indicates OS halted; HIGH indicates running/booting
    // State machine transitions:
    switch (state) {
      case OFF_STATE:
        // In current Pi behavior, the shutdown indicator is LOW when the OS is halted.
        // In a future revision where wake-on-GPIO works normally, the shutdown indicator would be HIGH.
        // Here, we conditionally pulse the RUN pin only if shutdownVal is LOW.
        if (shutdownVal == LOW) {  
          // If the button is pressed (bootVal LOW) and the shutdown indicator remains LOW,
          // pulse the RUN pin to trigger boot.
          if (bootVal == LOW) {
            //SERIAL_OUT.println("OFF_STATE: Button pressed; pulsing RUN pin (legacy behavior)");
            digitalWrite(runPin, LOW);
            delay(runPulseDuration);  // 100ms pulse
            digitalWrite(runPin, HIGH);
            state = BOOT_REQUEST;
            //SERIAL_OUT.println("Transition: OFF_STATE -> BOOT_REQUEST (RUN pulse complete)");
          }
        } else {
          // If shutdownVal is HIGH in OFF_STATE, then the Pi is already waking normally.
          state = RUNNING;
          //SERIAL_OUT.println("Transition: OFF_STATE -> RUNNING (no RUN pulse needed)");
        }
        // Also check for auto-boot if shutdown indicator is HIGH (if not already handled above).
        // (This line may be redundant now, but you can keep it for robustness.)
        // if (shutdownVal == HIGH && state == OFF_STATE) {
        //   state = RUNNING;
        //   SERIAL_OUT.println("Transition: OFF_STATE -> RUNNING (auto boot detected)");
        // }
        break;

        
      case BOOT_REQUEST:
        // In BOOT_REQUEST, wait for the shutdown indicator to become HIGH,
        // which confirms that the power management circuitry has reinitialized.
        if (shutdownVal == HIGH) {
          state = RUNNING;
          //SERIAL_OUT.println("Transition: BOOT_REQUEST -> RUNNING");
        }
        break;
        
      case RUNNING:
        // In RUNNING, shutdown indicator remains HIGH.
        // A button press (bootVal LOW) is interpreted as a shutdown request.
        if (bootVal == LOW) {
          state = SHUTDOWN_REQUEST;
          //SERIAL_OUT.println("Transition: RUNNING -> SHUTDOWN_REQUEST");
        }
        // Also, if the OS shuts down via an internal command (without a button press),
        // the shutdown indicator will go LOW.
        else if (shutdownVal == LOW) {
          state = OFF_STATE;
          //SERIAL_OUT.println("Transition: RUNNING -> OFF_STATE (OS shutdown detected)");
        }
        break;
        
      case SHUTDOWN_REQUEST:
        // In SHUTDOWN_REQUEST, wait until shutdown indicator goes LOW,
        // confirming that the OS has fully halted.
        if (shutdownVal == LOW) {
          state = OFF_STATE;
          //SERIAL_OUT.println("Transition: SHUTDOWN_REQUEST -> OFF_STATE");
        }
        break;
    }
  }
  
  SystemState getState() const {
    return state;
  }
};

#define BOOT_PIN     19
#define SHUTDOWN_PIN 18
#define RUN_PIN      0
PowerStateMachine powerSM(BOOT_PIN, SHUTDOWN_PIN, RUN_PIN);

/* ────────── Switch table (same pins, now with keys) ────────── */
MultiSwitch switches[NBR_SWITCHES] = {
  /* index / meaning / key string / pins  */
  /* 0 */ MultiSwitch("fly",       20),
  /* 1 */ MultiSwitch("pause",     21),
  /* 2 */ MultiSwitch("activate",  17),
  /* 3 */ MultiSwitch("assist",     3, 2),   // Experience rocker
  /* 4 */ MultiSwitch("mode",      10,11),   // Flight rocker
  /* 5 */ MultiSwitch("load",      14,15),
  /* 6 */ MultiSwitch("intensity", 23,22)
};

int  switchStates[NBR_SWITCHES];
int  lastSent[NBR_SWITCHES] = { -1,-1,-1,-1,-1,-1,-1 };

/* ────────── JSON transmitters ────────── */
void sendFull() {
  SERIAL_OUT.print('{');
  bool first = true;
  for (auto& sw : switches) sw.printJson(SERIAL_OUT, first);
  SERIAL_OUT.println('}');
  memcpy(lastSent, switchStates, sizeof(lastSent));
}

void sendDelta() {
  SERIAL_OUT.print('{');
  bool first = true;
  for (int i = 0; i < NBR_SWITCHES; ++i) {
    if (switchStates[i] != lastSent[i]) {
      switches[i].printJson(SERIAL_OUT, first);
      lastSent[i] = switchStates[i];
    }
  }
  SERIAL_OUT.println('}');
}

/* ────────── Helpers (unchanged logic) ────────── */
void updateSwitchStates() {
  for (int i = 0; i < NBR_SWITCHES; ++i)
    switchStates[i] = switches[i].getState();
}

/* ────────── Setup ────────── */
void setup() {
#ifdef SERIAL1_TX_ONLY
  SERIAL_OUT.setRX(7);                  // if TTL version is used
#endif
  SERIAL_OUT.begin(115200);

  pinMode(BOOT_PIN, INPUT_PULLUP);
  pinMode(SHUTDOWN_PIN, INPUT_PULLUP);
  pinMode(RUN_PIN, OUTPUT);  digitalWrite(RUN_PIN, HIGH);
  pinMode(LED_BUILTIN, OUTPUT);

  for (auto& sw : switches) sw.begin();

  updateSwitchStates();     // prime arrays
  sendFull();               // initial snapshot
  SERIAL_OUT.println(F("Switch reader (JSON) started"));
}

/* ────────── Main loop ────────── */
void loop() {
  static unsigned long prevMs = 0;

  powerSM.update();                           // unchanged behaviour
  digitalWrite(LED_BUILTIN,
               powerSM.getState()==OFF_STATE ? LOW : HIGH);

  updateSwitchStates();

  bool changed = false;
  for (int i = 0; i < NBR_SWITCHES; ++i)
    if (switchStates[i] != lastSent[i]) { changed = true; break; }

  if (changed) {
    sendDelta();                              // immediate delta
  } else {
    unsigned long now = millis();
    if (now - prevMs >= MSG_INTERVAL_MS) {
      prevMs = now;
      sendFull();                             // 50 ms heartbeat
    }
  }
}
