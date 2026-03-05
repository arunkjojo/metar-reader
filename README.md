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

## Project Structure

```
metar-reader/
├── app.py              # Flask application and route handler
├── metar_decoder.py    # METAR parsing and decoding logic
├── templates/
│   └── index.html      # Jinja2 HTML template
└── requirements.txt    # Python dependencies
```

## Data Source

Weather data is provided by the [Aviation Weather Center](https://aviationweather.gov/) (NOAA/FAA) public API. No API key is required.

## License

MIT
