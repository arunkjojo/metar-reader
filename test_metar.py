"""Unit tests for the METAR Reader application.

Tests cover metar_decoder.py helper functions, the full METAR parser,
and the Flask routes in app.py. External HTTP calls are replaced with
unittest.mock so no network connection is required.

Run all tests:
    python -m pytest test_metar.py -v
    # or
    python -m unittest test_metar -v
"""

import unittest
from unittest.mock import patch, MagicMock
import requests

from metar_decoder import (
    degrees_to_cardinal,
    parse_temp,
    decode_wx_token,
    decode_sky_token,
    decode_metar,
    get_weather_icon,
    generate_summary,
)
from app import app


# ---------------------------------------------------------------------------
# Mock METAR strings used across multiple test cases
# ---------------------------------------------------------------------------

METAR_KJFK  = "KJFK 051851Z 27015KT 10SM FEW060 BKN250 22/14 A2992 RMK AO2"
METAR_CALM  = "KORD 051852Z 00000KT 10SM CLR 18/10 A3005"
METAR_VRB   = "KLAX 051853Z VRB03KT 10SM SCT015 OVC025 16/12 A2998"
METAR_RAIN  = "KBOS 051854Z 18012G22KT 3SM -RA BR BKN008 OVC015 15/14 A2985"
METAR_SNOW  = "KDEN 051855Z 32018KT 1SM +SN BKN015 OVC025 M02/M07 A2965"
METAR_FOG   = "KSFO 051856Z 15008KT M1/4SM FG OVC002 12/12 A3012"
METAR_TSTM  = "KATL 051857Z 21010KT 5SM TSRA SCT025CB BKN050 28/22 A2995"
METAR_EGLL  = "EGLL 051850Z 24015KT 9999 FEW025 SCT045 18/10 Q1015"
METAR_GUST  = "KJFK 051851Z 27015G28KT 10SM CLR 22/14 A2992"
METAR_CAVOK = "YSSY 051850Z 12012KT CAVOK 24/12 Q1018"
METAR_AUTO  = "KBDL 051853Z AUTO 00000KT 10SM CLR 18/10 A3002"


# ---------------------------------------------------------------------------
# degrees_to_cardinal
# ---------------------------------------------------------------------------

class TestDegreesToCardinal(unittest.TestCase):

    def test_north(self):
        self.assertEqual(degrees_to_cardinal(0), 'North')

    def test_north_full_circle(self):
        self.assertEqual(degrees_to_cardinal(360), 'North')

    def test_east(self):
        self.assertEqual(degrees_to_cardinal(90), 'East')

    def test_south(self):
        self.assertEqual(degrees_to_cardinal(180), 'South')

    def test_west(self):
        self.assertEqual(degrees_to_cardinal(270), 'West')

    def test_northeast(self):
        self.assertEqual(degrees_to_cardinal(45), 'Northeast')

    def test_northwest(self):
        self.assertEqual(degrees_to_cardinal(315), 'Northwest')

    def test_north_northeast(self):
        self.assertEqual(degrees_to_cardinal(22), 'North-Northeast')


# ---------------------------------------------------------------------------
# parse_temp
# ---------------------------------------------------------------------------

class TestParseTemp(unittest.TestCase):

    def test_positive(self):
        self.assertEqual(parse_temp('22'), 22)

    def test_zero(self):
        self.assertEqual(parse_temp('00'), 0)

    def test_negative(self):
        self.assertEqual(parse_temp('M05'), -5)

    def test_negative_double_digit(self):
        self.assertEqual(parse_temp('M12'), -12)


# ---------------------------------------------------------------------------
# decode_wx_token
# ---------------------------------------------------------------------------

class TestDecodeWxToken(unittest.TestCase):

    def test_plain_rain(self):
        self.assertEqual(decode_wx_token('RA'), 'rain')

    def test_light_rain(self):
        self.assertEqual(decode_wx_token('-RA'), 'light rain')

    def test_heavy_rain(self):
        self.assertEqual(decode_wx_token('+RA'), 'heavy rain')

    def test_plain_snow(self):
        self.assertEqual(decode_wx_token('SN'), 'snow')

    def test_heavy_snow(self):
        self.assertEqual(decode_wx_token('+SN'), 'heavy snow')

    def test_fog(self):
        self.assertEqual(decode_wx_token('FG'), 'fog')

    def test_mist(self):
        self.assertEqual(decode_wx_token('BR'), 'mist')

    def test_thunderstorm_rain(self):
        result = decode_wx_token('TSRA')
        self.assertIn('thunderstorm', result)
        self.assertIn('rain', result)

    def test_freezing_rain(self):
        result = decode_wx_token('FZRA')
        self.assertIn('freezing', result)
        self.assertIn('rain', result)

    def test_shower_rain(self):
        result = decode_wx_token('SHRA')
        self.assertIn('shower', result)
        self.assertIn('rain', result)

    def test_vicinity_fog(self):
        result = decode_wx_token('VCFG')
        self.assertIn('nearby', result)
        self.assertIn('fog', result)


# ---------------------------------------------------------------------------
# decode_sky_token
# ---------------------------------------------------------------------------

class TestDecodeSkyToken(unittest.TestCase):

    def test_skc(self):
        result = decode_sky_token('SKC')
        self.assertEqual(result['coverage'], 'clear')

    def test_clr(self):
        result = decode_sky_token('CLR')
        self.assertEqual(result['coverage'], 'clear')

    def test_cavok(self):
        result = decode_sky_token('CAVOK')
        self.assertEqual(result['coverage'], 'clear')
        self.assertIn('Visibility OK', result['text'])

    def test_nsc(self):
        result = decode_sky_token('NSC')
        self.assertEqual(result['coverage'], 'clear')

    def test_few_height(self):
        result = decode_sky_token('FEW030')
        self.assertEqual(result['coverage'], 'few')
        self.assertEqual(result['height'], 3000)
        self.assertIn('3,000 feet', result['text'])

    def test_scattered(self):
        result = decode_sky_token('SCT045')
        self.assertEqual(result['coverage'], 'scattered')
        self.assertEqual(result['height'], 4500)

    def test_broken(self):
        result = decode_sky_token('BKN020')
        self.assertEqual(result['coverage'], 'broken')
        self.assertEqual(result['height'], 2000)

    def test_overcast(self):
        result = decode_sky_token('OVC010')
        self.assertEqual(result['coverage'], 'overcast')
        self.assertEqual(result['height'], 1000)

    def test_cumulonimbus(self):
        result = decode_sky_token('BKN030CB')
        self.assertIn('thunderstorm', result['text'])

    def test_towering_cumulus(self):
        result = decode_sky_token('SCT025TCU')
        self.assertIn('towering cumulus', result['text'])


# ---------------------------------------------------------------------------
# decode_metar — full pipeline
# ---------------------------------------------------------------------------

class TestDecodeMetar(unittest.TestCase):

    # --- Station and metadata ---

    def test_station_id_parsed(self):
        result = decode_metar(METAR_KJFK)
        self.assertEqual(result['station'], 'KJFK')

    def test_metar_prefix_skipped(self):
        result = decode_metar('METAR ' + METAR_KJFK)
        self.assertEqual(result['station'], 'KJFK')

    def test_auto_flag_detected(self):
        result = decode_metar(METAR_AUTO)
        self.assertTrue(result.get('automated'))

    def test_observation_time_parsed(self):
        result = decode_metar(METAR_KJFK)
        self.assertEqual(result['time'], '18:51 UTC')

    # --- Wind ---

    def test_wind_direction_and_speed(self):
        result = decode_metar(METAR_KJFK)
        self.assertEqual(result['wind']['degrees'], 270)
        self.assertEqual(result['wind']['speed_mph'], round(15 * 1.15078))

    def test_calm_wind(self):
        result = decode_metar(METAR_CALM)
        self.assertTrue(result['wind'].get('calm'))
        self.assertEqual(result['wind']['speed_mph'], 0)

    def test_variable_wind(self):
        result = decode_metar(METAR_VRB)
        self.assertIn('Variable', result['wind']['text'])

    def test_gust_parsed(self):
        result = decode_metar(METAR_GUST)
        self.assertIsNotNone(result['wind'].get('gust_mph'))
        self.assertEqual(result['wind']['gust_mph'], round(28 * 1.15078))

    # --- Visibility ---

    def test_visibility_statute_miles(self):
        result = decode_metar(METAR_KJFK)
        self.assertEqual(result['visibility']['miles'], 10)

    def test_visibility_below_quarter_mile(self):
        result = decode_metar(METAR_FOG)
        self.assertLess(result['visibility']['miles'], 0.5)

    def test_visibility_metric_meters(self):
        # 9999 m converts to roughly 6.2 miles
        result = decode_metar(METAR_EGLL)
        self.assertGreater(result['visibility']['miles'], 5)

    # --- Sky conditions ---

    def test_sky_layers_parsed(self):
        result = decode_metar(METAR_KJFK)
        coverages = [layer['coverage'] for layer in result['sky']]
        self.assertIn('few', coverages)

    def test_cavok_sets_sky_and_visibility(self):
        result = decode_metar(METAR_CAVOK)
        self.assertEqual(result['sky'][0]['coverage'], 'clear')
        self.assertGreaterEqual(result['visibility']['miles'], 10)

    # --- Weather phenomena ---

    def test_rain_phenomenon(self):
        result = decode_metar(METAR_RAIN)
        self.assertTrue(any('rain' in w for w in result['weather']))

    def test_heavy_snow_phenomenon(self):
        result = decode_metar(METAR_SNOW)
        self.assertTrue(any('snow' in w for w in result['weather']))

    def test_thunderstorm_phenomenon(self):
        result = decode_metar(METAR_TSTM)
        self.assertTrue(any('thunderstorm' in w for w in result['weather']))

    # --- Temperature and dew point ---

    def test_temperature_positive_celsius(self):
        result = decode_metar(METAR_KJFK)
        self.assertEqual(result['temperature']['celsius'], 22)
        self.assertEqual(result['temperature']['fahrenheit'], round(22 * 9 / 5 + 32))

    def test_temperature_negative_celsius(self):
        result = decode_metar(METAR_SNOW)
        self.assertEqual(result['temperature']['celsius'], -2)

    def test_dewpoint_parsed(self):
        result = decode_metar(METAR_KJFK)
        self.assertEqual(result['dewpoint']['celsius'], 14)

    # --- Altimeter ---

    def test_altimeter_inhg(self):
        result = decode_metar(METAR_KJFK)
        self.assertAlmostEqual(result['altimeter']['value'], 29.92, places=1)

    def test_altimeter_hpa(self):
        result = decode_metar(METAR_EGLL)
        self.assertEqual(result['altimeter']['value'], 1015)

    # --- Remarks stripping ---

    def test_remarks_section_stripped(self):
        result = decode_metar(METAR_KJFK)
        # 'AO2' is in the RMK section and must not appear in decoded output
        self.assertNotIn('AO2', str(result))

    # --- Edge cases ---

    def test_empty_string_returns_none(self):
        self.assertIsNone(decode_metar(''))

    def test_whitespace_only_returns_none(self):
        self.assertIsNone(decode_metar('   \n  '))


# ---------------------------------------------------------------------------
# get_weather_icon
# ---------------------------------------------------------------------------

class TestGetWeatherIcon(unittest.TestCase):

    def test_thunderstorm_icon(self):
        self.assertEqual(get_weather_icon({'weather': ['thunderstorm rain']}), '⛈️')

    def test_tornado_icon(self):
        self.assertEqual(get_weather_icon({'weather': ['tornado/funnel cloud']}), '🌪️')

    def test_snow_icon(self):
        self.assertEqual(get_weather_icon({'weather': ['heavy snow']}), '🌨️')

    def test_rain_icon(self):
        self.assertEqual(get_weather_icon({'weather': ['light rain']}), '🌧️')

    def test_fog_icon(self):
        self.assertEqual(get_weather_icon({'weather': ['fog']}), '🌫️')

    def test_mist_icon(self):
        self.assertEqual(get_weather_icon({'weather': ['mist']}), '🌫️')

    def test_clear_sky_icon(self):
        icon = get_weather_icon({'weather': [], 'sky': [{'coverage': 'clear'}]})
        self.assertEqual(icon, '☀️')

    def test_overcast_icon(self):
        icon = get_weather_icon({'weather': [], 'sky': [{'coverage': 'overcast'}]})
        self.assertEqual(icon, '☁️')

    def test_broken_icon(self):
        icon = get_weather_icon({'weather': [], 'sky': [{'coverage': 'broken'}]})
        self.assertEqual(icon, '🌥️')

    def test_scattered_icon(self):
        icon = get_weather_icon({'weather': [], 'sky': [{'coverage': 'scattered'}]})
        self.assertEqual(icon, '⛅')

    def test_few_icon(self):
        icon = get_weather_icon({'weather': [], 'sky': [{'coverage': 'few'}]})
        self.assertEqual(icon, '🌤️')

    def test_no_data_fallback_icon(self):
        self.assertEqual(get_weather_icon({}), '🌡️')


# ---------------------------------------------------------------------------
# generate_summary
# ---------------------------------------------------------------------------

class TestGenerateSummary(unittest.TestCase):

    def test_contains_station_name(self):
        data = decode_metar(METAR_KJFK)
        self.assertIn('KJFK', generate_summary(data))

    def test_mild_temperature_feel(self):
        # 22°C / 72°F falls in the 65–74°F "mild" band
        data = decode_metar(METAR_KJFK)
        self.assertIn('mild', generate_summary(data))

    def test_below_freezing_feel(self):
        # -2°C / 28°F => "below freezing"
        data = decode_metar(METAR_SNOW)
        self.assertIn('freezing', generate_summary(data))

    def test_calm_winds_mentioned(self):
        data = decode_metar(METAR_CALM)
        self.assertIn('calm', generate_summary(data).lower())

    def test_good_visibility_mentioned(self):
        data = decode_metar(METAR_KJFK)
        self.assertIn('good', generate_summary(data).lower())

    def test_poor_visibility_mentioned(self):
        data = decode_metar(METAR_FOG)
        self.assertIn('poor', generate_summary(data).lower())


# ---------------------------------------------------------------------------
# Flask routes
# ---------------------------------------------------------------------------

class TestFlaskApp(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()

    # --- GET ---

    def test_get_returns_200(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_get_renders_search_form(self):
        response = self.client.get('/')
        self.assertIn(b'airport_code', response.data)

    # --- POST validation ---

    def test_post_empty_code_shows_error(self):
        response = self.client.post('/', data={'airport_code': ''})
        self.assertIn(b'enter an airport code', response.data)

    def test_post_three_letter_code_shows_error(self):
        response = self.client.post('/', data={'airport_code': 'JFK'})
        self.assertIn(b'4 letters', response.data)

    def test_post_numeric_code_shows_error(self):
        response = self.client.post('/', data={'airport_code': '1234'})
        self.assertIn(b'4 letters', response.data)

    def test_post_five_letter_code_shows_error(self):
        response = self.client.post('/', data={'airport_code': 'KJFKX'})
        self.assertIn(b'4 letters', response.data)

    # --- POST with mocked API responses ---

    @patch('app.requests.get')
    def test_post_valid_code_shows_decoded_result(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = METAR_KJFK
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        response = self.client.post('/', data={'airport_code': 'KJFK'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'KJFK', response.data)

    @patch('app.requests.get')
    def test_post_empty_api_response_shows_error(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = ''
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        response = self.client.post('/', data={'airport_code': 'ZZZZ'})
        self.assertIn(b'No METAR data found', response.data)

    @patch('app.requests.get')
    def test_post_connection_error_shows_message(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError()
        response = self.client.post('/', data={'airport_code': 'KJFK'})
        self.assertIn(b'internet connection', response.data)

    @patch('app.requests.get')
    def test_post_timeout_shows_message(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout()
        response = self.client.post('/', data={'airport_code': 'KJFK'})
        self.assertIn(b'timed out', response.data)

    @patch('app.requests.get')
    def test_post_http_error_shows_status_code(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_get.side_effect = requests.exceptions.HTTPError(response=mock_resp)
        response = self.client.post('/', data={'airport_code': 'KJFK'})
        self.assertIn(b'Weather service returned an error', response.data)

    @patch('app.requests.get')
    def test_post_sends_correct_airport_code_to_api(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = METAR_KJFK
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        self.client.post('/', data={'airport_code': 'kjfk'})  # lowercase input
        call_kwargs = mock_get.call_args
        self.assertEqual(call_kwargs.kwargs['params']['ids'], 'KJFK')


if __name__ == '__main__':
    unittest.main(verbosity=2)
