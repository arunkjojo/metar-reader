# METAR Reader

A Flask web application that translates raw METAR (Meteorological Aerodrome Report) aviation weather data into plain English.

Enter any 4-letter ICAO airport code (e.g. `KJFK`, `EGLL`, `YSSY`) and get a human-readable weather summary including temperature, wind, visibility, sky conditions, and atmospheric pressure — all fetched live from the [Aviation Weather Center](https://aviationweather.gov/).

## Features

- Live METAR data fetched directly from the FAA/NOAA Aviation Weather Center API
- Plain-English summary of current conditions
- Decoded fields: temperature & dew point, wind speed/direction, visibility, sky layers, weather phenomena, altimeter setting
- Both US customary (°F, mph, inHg) and metric (°C, m, hPa) units displayed
- Emoji weather icon that reflects current conditions
- Collapsible raw METAR string for reference
- Mobile-friendly, responsive design

## Requirements

- Python 3.9+
- pip

## Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/arunkjojo/metar-reader.git
   cd metar-reader
   ```

2. **Create and activate a virtual environment**

   ```bash
   python -m venv .venv

   # Linux / macOS
   source .venv/bin/activate

   # Windows (PowerShell)
   .venv\Scripts\Activate.ps1

   # Windows (Git Bash / cmd)
   source .venv/Scripts/activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

## Running the App

```bash
python app.py
```

Then open your browser and go to `http://127.0.0.1:5000`.

> **Note:** `debug=True` is set for local development. Before deploying to a public server, set `debug=False` and use a production WSGI server such as [Gunicorn](https://gunicorn.org/).

## Usage

1. Type a 4-letter ICAO airport code into the search box.
2. Click **Get Weather** (or click one of the example links).
3. Read the plain-English weather report.

### Example airport codes

| Code | Airport |
|------|---------|
| KJFK | New York JFK |
| KLAX | Los Angeles |
| KORD | Chicago O'Hare |
| EGLL | London Heathrow |
| YSSY | Sydney Kingsford Smith |

## Running the Tests

The test suite uses Python's built-in `unittest` module — no extra packages required. All external HTTP calls are mocked, so no network connection is needed.

```bash
python -m unittest test_metar -v
```

Or with pytest if you have it installed:

```bash
pip install pytest
pytest test_metar.py -v
```

### Test coverage

| Test class | What is tested |
|---|---|
| `TestDegreesToCardinal` | Wind degree-to-cardinal conversion (N, S, E, W, intercardinals) |
| `TestParseTemp` | Positive, zero, and `M`-prefixed negative temperatures |
| `TestDecodeWxToken` | Weather phenomena tokens — intensity (`-`/`+`/`VC`), descriptors (`TS`, `FZ`, `SH`), phenomena (`RA`, `SN`, `FG`, …) |
| `TestDecodeSkyToken` | Sky condition tokens — `SKC`, `CLR`, `CAVOK`, `NSC`, `FEW`/`SCT`/`BKN`/`OVC` with heights, `CB` and `TCU` modifiers |
| `TestDecodeMetar` | Full METAR parser — station, timestamp, `AUTO` flag, wind (calm/variable/gust), visibility (statute miles and metres), sky layers, weather phenomena, temperature/dewpoint, altimeter (inHg and hPa), remarks stripping, edge cases |
| `TestGetWeatherIcon` | Emoji icon selection for all weather branches and the fallback |
| `TestGenerateSummary` | Plain-English summary — temperature feel, wind description, visibility description |
| `TestFlaskApp` | Flask routes — GET, POST input validation, mocked API success / empty response / connection error / timeout / HTTP error, input uppercasing |

**87 tests, 0 failures.**

## Project Structure

```
metar-reader/
├── app.py              # Flask application and route handler
├── metar_decoder.py    # METAR parsing and decoding logic
├── test_metar.py       # Unit tests (no network required)
├── templates/
│   └── index.html      # Jinja2 HTML template
└── requirements.txt    # Python dependencies
```

## Data Source

Weather data is provided by the [Aviation Weather Center](https://aviationweather.gov/) (NOAA/FAA) public API. No API key is required.

## License

MIT
