# System Architecture

## 1. Design goals

| Goal | How it is achieved |
|------|--------------------|
| **Interoperability** | Heterogeneous nodes (Raspberry Pi, ESP32, Arduino) integrated over Wi-Fi, HTTP/REST and Blynk IoT |
| **Low latency, offline resilience** | Automation rules run on the edge hub. The cloud is only used for remote access |
| **Security** | Token-authenticated API, TLS transports, secret isolation, least exposure (see [security-model.md](security-model.md)) |
| **Scalability** | Modular Python package: each sensor or actuator is an independent module behind a common HAL and config |
| **Cost** | Commodity sensors, all under USD 5 each, and open-source software |

## 2. Layered view

```mermaid
flowchart TB
    A["Presentation<br/>Web dashboard, Blynk app, Tk GUIs, TM1637, e-mail"]
    B["Application<br/>Flask API, automation rules, alerting, weather service"]
    C["Data<br/>SQLite event store: motion_data, led_data, climate_data"]
    D["Hardware abstraction<br/>homeauto.hal.gpio: RPi.GPIO | emulator | mock"]
    E["Physical<br/>PIR, DHT11, HC-SR04, LDR, relays, TRIAC, LEDs"]
    A --> B --> C
    B --> D --> E
```

## 3. Data-flow diagrams

### 3.1 Core functions
```mermaid
flowchart TB
    START(["Start system"]) --> INIT["Initialise GPIO, sensors, web server"]
    INIT --> PIR["PIR motion detection"]
    INIT --> DHT["DHT11 temperature & humidity"]
    INIT --> WEB["User accesses Flask web interface"]
    PIR -- "motion and mode=auto" --> LEDON["LED ON + log + optional e-mail"]
    PIR -- "no motion" --> MON["Continue monitoring"]
    DHT --> WEBV["Show on web dashboard"]
    DHT --> SEG["Show on TM1637 as TT:HH"]
    WEB -- "POST /api/led" --> GPIO["Set LED state via GPIO"]
```

### 3.2 Additional sensor functions
```mermaid
flowchart TB
    SYS(["System initialised"]) --> US["Ultrasonic distance (median of 3)"]
    SYS --> DIM["AC dimmer control"]
    SYS --> WX["Fetch weather / AQI via API"]
    US -- "distance < threshold" --> BUZ["Buzzer ON"]
    US -- "else" --> NOP["Buzzer OFF"]
    DIM --> TRIAC["Fire TRIAC after zero-cross delay"]
    WX --> GUI["Tkinter dashboard + Folium map + voice"]
```

### 3.3 Light automation and notifications
```mermaid
flowchart TB
    SYS(["System initialised"]) --> LDR["LDR light level"]
    SYS --> EVT["Event triggered"]
    LDR -- "dark" --> ON["Relay: light ON"]
    LDR -- "daylight" --> OFF["Relay: light OFF"]
    EVT --> RL{"Cooldown elapsed?"}
    RL -- "yes" --> MAIL["Send e-mail over SMTPS"]
    RL -- "no" --> DROP["Suppress duplicate"]
```

## 4. ESP32 / Blynk control loop

```mermaid
sequenceDiagram
    participant User as Blynk web / app
    participant Cloud as Blynk Cloud
    participant ESP as ESP32
    participant LED
    User->>Cloud: Switch V0 = 1
    Cloud->>ESP: BLYNK_WRITE(V0) over TLS
    ESP->>ESP: validate value in {0,1}
    ESP->>LED: digitalWrite(HIGH)
    ESP->>Cloud: virtualWrite(V1, 1)
    Cloud-->>User: LED widget shows ON
    Note over ESP,Cloud: Watchdog every 10 s, Wi-Fi and cloud reconnect,<br/>BLYNK_CONNECTED re-syncs V0
```

## 5. Data model (SQLite)

| Table | Columns | Written by |
|-------|---------|------------|
| `motion_data` | `id, timestamp, motion_detected` | web app, desktop GUI (rising edges only) |
| `led_data` | `id, timestamp, led_state, source` (`api` / `pir` / `gui`) | web app, desktop GUI |
| `climate_data` | `id, timestamp, temperature_c, humidity_pct` | web app climate sampler |

The schema is simple enough to query in natural language (e.g. *"How many times was the light on today?"*), which the LLM database assistant on the roadmap relies on.

## 6. Concurrency model

- **Web app:** Flask threaded server, plus two daemon threads (motion loop at 5 Hz, climate loop every `SENSOR_POLL_SECONDS`). Shared state is guarded by a `threading.Lock`. E-mail sending runs in its own short-lived thread so SMTP latency never stalls sensing.
- **Desktop GUI:** a worker thread only reads GPIO and pushes to a `queue.Queue`. The Tk main thread drains the queue with `root.after(100, ...)`.
- **SQLite:** a single connection with `check_same_thread=False`, serialised with a lock.
