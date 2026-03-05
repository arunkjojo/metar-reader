"""
METAR Reader — Flask web application.

Fetches live METAR (Meteorological Aerodrome Report) data from the
Aviation Weather Center API and presents it as a plain-English weather
summary for a given ICAO airport code.
"""

from flask import Flask, render_template, request
import requests
from metar_decoder import decode_metar, generate_summary, get_weather_icon

app = Flask(__name__)

# Aviation Weather Center public METAR API endpoint
METAR_URL = "https://aviationweather.gov/api/data/metar"


@app.route('/', methods=['GET', 'POST'])
def index():
    """Render the main page and handle METAR lookup requests.

    GET:  Display the search form with no results.
    POST: Validate the submitted airport code, fetch its METAR from the
          Aviation Weather Center API, decode it, and pass the structured
          result to the template.

    Returns:
        A rendered HTML response. On success the template receives a
        ``result`` dict containing decoded weather fields, a plain-English
        ``summary``, an emoji ``icon``, and the original ``raw`` METAR
        string. On failure it receives an ``error`` message instead.
    """
    result = None
    error = None
    airport_code = ''
    raw_metar = ''

    if request.method == 'POST':
        airport_code = request.form.get('airport_code', '').strip().upper()

        # Basic validation before hitting the network
        if not airport_code:
            error = "Please enter an airport code."
        elif not airport_code.isalpha() or len(airport_code) != 4:
            error = "Airport codes are 4 letters (e.g. KJFK, KLAX, EGLL)."
        else:
            try:
                resp = requests.get(
                    METAR_URL,
                    params={'ids': airport_code},
                    timeout=10,
                    headers={'User-Agent': 'METAR-Reader/1.0'}
                )
                resp.raise_for_status()
                raw_metar = resp.text.strip()

                if not raw_metar:
                    error = (
                        f"No METAR data found for '{airport_code}'. "
                        "Please verify the airport code and try again."
                    )
                else:
                    decoded = decode_metar(raw_metar)
                    if decoded:
                        decoded['summary'] = generate_summary(decoded)
                        decoded['icon'] = get_weather_icon(decoded)
                        # Keep only the first line; some responses include extras
                        decoded['raw'] = raw_metar.split('\n')[0].strip()
                        result = decoded
                    else:
                        error = "Could not parse the METAR data. The format may be unrecognized."

            except requests.exceptions.ConnectionError:
                error = "Could not reach the weather service. Please check your internet connection."
            except requests.exceptions.Timeout:
                error = "The request timed out. Please try again."
            except requests.exceptions.HTTPError as e:
                error = f"Weather service returned an error: {e.response.status_code}"
            except Exception as e:
                error = f"An unexpected error occurred: {str(e)}"

    return render_template(
        'index.html',
        result=result,
        error=error,
        airport_code=airport_code,
        raw_metar=raw_metar
    )


if __name__ == '__main__':
    app.run(debug=True)
