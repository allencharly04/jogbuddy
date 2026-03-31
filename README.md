# 🏃 JogBuddy

> *An audiobook companion for indoor joggers. Plays when you move. Pauses when you stop. Tracks your distance without GPS, without measuring your room, without any setup.*

**Built with:** Python · HTML/CSS/JS · Web Accelerometer API · LibriVox API · Internet Archive

---

## What it does

You jog back and forth in your room. JogBuddy:
- Streams a free audiobook from LibriVox directly to your phone
- **Automatically pauses** the audio when you stop moving
- **Automatically resumes** when you start again
- Tracks your steps, distance, pace, cadence, and stride length in real time
- Announces milestones (1 km, 2 km... 5 km) via text-to-speech, briefly pausing the audiobook to do so

No GPS needed. No app to install. Just open a link in Chrome on your phone.

---

## The Science — How does it know how far you've run?

This is the interesting part. Most people assume you need GPS for distance tracking. You don't.

### Step 1 — Three axes become one number

Your phone's accelerometer measures movement in three directions simultaneously: X (left-right), Y (forward-back), Z (up-down). JogBuddy reads all three 100 times per second and collapses them into a single scalar magnitude using Pythagoras in 3D:

```
magnitude = √(x² + y² + z²)
```

This makes the algorithm completely orientation-independent — it doesn't matter how you hold your phone.

### Step 2 — Step detection

Every footfall creates a characteristic acceleration spike. JogBuddy watches for peaks in the magnitude signal above a configurable threshold, with a 250ms cooldown between detections (no human being takes more than 4 steps per second).

### Step 3 — The Weinberg Adaptive Stride Formula ✨

A fixed stride length doesn't work — you walk differently at the start than you do at kilometre 4 when your legs are tired. In 2002, Harvey Weinberg at Analog Devices published a formula that solves this elegantly:

```
step_length = K × ⁴√(a_max − a_min)
```

Where:
- **a_max** = peak acceleration magnitude during the step
- **a_min** = trough acceleration magnitude during that same step
- **K** = a scaling constant (~0.4–0.5 for jogging)
- **⁴√** = fourth root (raise to the power of 0.25)

The insight: **the harder you push off the ground, the bigger the gap between peak and trough, and therefore the longer your stride.** The fourth root captures the nonlinear biomechanics of human gait — stride doesn't scale linearly with effort.

Every single step gets its own stride length estimate. Sprint, slow down, fatigue — the formula adapts automatically.

### Step 4 — Self-calibrating K

K starts at 0.45 (the standard value for hand-held phone jogging). JogBuddy continuously self-calibrates it using your cadence (steps per minute) as a proxy:

```
K_new = K_old × (1 − 0.06) + K_corrected × 0.06
```

The 0.06 learning rate is slow enough not to overcorrect on a single weird step, fast enough to adapt over your first few hundred metres.

### Step 5 — Distance

```
total_distance += step_length / 1000   (metres → kilometres)
```

No GPS. No room measurements. No calibration walk. Just the phone's accelerometer and a 20-year-old formula from an Analog Devices application note.

---

## Motion-driven play/pause

JogBuddy uses the browser's **DeviceMotion API** to access the accelerometer in real time. When the acceleration magnitude drops below the step detection threshold for more than 3 seconds (configurable), the audiobook pauses. The moment you start moving again, it resumes. This is the core motivation mechanic — stopping means losing your place in the story.

---

## LibriVox Integration

JogBuddy has a built-in book browser powered by the **Internet Archive search API**:

```
https://archive.org/advancedsearch.php?q=title:(query)+collection:librivoxaudio
```

Search results → select book → select chapter → play. No copy-pasting URLs needed.

Audio is streamed through a local Python proxy to bypass browser CORS restrictions:

```
Phone → /proxy?url=... → Python server → archive.org → back to phone
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Server | Python `http.server` with SSL (local) |
| Frontend | Vanilla HTML/CSS/JS — no frameworks |
| Step detection | Web DeviceMotion API + peak detection |
| Distance | Weinberg adaptive stride formula (2002) |
| Book search | Internet Archive advancedsearch API |
| Audio | HTML5 `<audio>` + Python streaming proxy |
| Deployment | Render (cloud) / local HTTPS server |

---

## Running Locally

```bash
# Install dependency
pip install cryptography

# Run
cd "path/to/jogbuddy"
python app.py
```

First run auto-generates a self-signed SSL certificate (`cert.pem`, `key.pem`).

Find your PC's local IP:
```bash
ipconfig   # Windows — look for IPv4 Address under Wi-Fi
```

Open on your phone (same WiFi):
```
https://192.168.x.x:8501
```

Tap **Advanced → Proceed** past the self-signed cert warning — it's safe, it's your own PC.

**Android Chrome:** Go to Site settings → Motion sensors → Allow before starting a session.

---

## Deployment (Render)

On Render: New Web Service → connect repo → Build: `pip install -r requirements.txt` → Start: `python app.py` → Free tier → Deploy.

The app detects the `RENDER` environment variable and skips SSL generation (Render handles HTTPS automatically).

---

## Free Audiobook Sources

| Source | Library size | Login needed |
|--------|-------------|-------------|
| **LibriVox via archive.org** | 20,000+ classics | No |
| **Loyal Books** | 7,000+ books | No |
| **Open Culture** | 1,000 curated titles | No |
| **Spotify** (use separately) | Modern titles | Free account |

Best for jogging: Sherlock Holmes dramatic reading (full cast) — search "adventures sherlock holmes" in the Books tab.

---

## References

- Weinberg, H. (2002). *Using the ADXL202 in Pedometer and Personal Navigation Applications*. Analog Devices AN-602.
- Scarlett et al. (2016). *Step-Detection and Adaptive Step-Length Estimation for Pedestrian Dead-Reckoning at Various Walking Speeds Using a Smartphone*. MDPI Sensors 16(9), 1423.
- Han et al. (2017). *Step Detection Algorithm for Accurate Distance Estimation Using Dynamic Step Length*. IEEE MDM 2017.
