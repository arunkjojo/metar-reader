import re

DESCRIPTORS = {'MI', 'PR', 'BC', 'DR', 'BL', 'SH', 'TS', 'FZ'}
PHENOMENA = {
    'DZ', 'RA', 'SN', 'SG', 'IC', 'PL', 'GR', 'GS', 'UP',
    'BR', 'FG', 'FU', 'VA', 'DU', 'SA', 'HZ', 'PY',
    'PO', 'SQ', 'FC', 'SS', 'DS'
}

WEATHER_NAMES = {
    'MI': 'shallow', 'PR': 'partial', 'BC': 'patchy', 'DR': 'drifting',
    'BL': 'blowing', 'SH': 'shower', 'TS': 'thunderstorm', 'FZ': 'freezing',
    'DZ': 'drizzle', 'RA': 'rain', 'SN': 'snow', 'SG': 'snow grains',
    'IC': 'ice crystals', 'PL': 'ice pellets', 'GR': 'hail', 'GS': 'small hail',
    'UP': 'unknown precipitation',
    'BR': 'mist', 'FG': 'fog', 'FU': 'smoke', 'VA': 'volcanic ash',
    'DU': 'dust', 'SA': 'sand', 'HZ': 'haze', 'PY': 'spray',
    'PO': 'dust whirls', 'SQ': 'squalls', 'FC': 'tornado/funnel cloud',
    'SS': 'sandstorm', 'DS': 'dust storm',
}

WX_PATTERN = re.compile(
    r'^(\+|-|VC)?(MI|PR|BC|DR|BL|SH|TS|FZ)?'
    r'(DZ|RA|SN|SG|IC|PL|GR|GS|UP|BR|FG|FU|VA|DU|SA|HZ|PY|PO|SQ|FC|SS|DS)+$'
)

SKY_PATTERN = re.compile(
    r'^(SKC|CLR|CAVOK|NSC|NCD|(FEW|SCT|BKN|OVC)\d{3}(CB|TCU)?)$'
)


def degrees_to_cardinal(deg):
    dirs = [
        'North', 'North-Northeast', 'Northeast', 'East-Northeast',
        'East', 'East-Southeast', 'Southeast', 'South-Southeast',
        'South', 'South-Southwest', 'Southwest', 'West-Southwest',
        'West', 'West-Northwest', 'Northwest', 'North-Northwest'
    ]
    return dirs[round(deg / 22.5) % 16]


def parse_temp(s):
    return -int(s[1:]) if s.startswith('M') else int(s)


def decode_wx_token(token):
    remaining = token
    intensity = ''

    if remaining.startswith('+'):
        intensity = 'heavy'
        remaining = remaining[1:]
    elif remaining.startswith('-'):
        intensity = 'light'
        remaining = remaining[1:]
    elif remaining.startswith('VC'):
        intensity = 'nearby'
        remaining = remaining[2:]

    descriptor = ''
    for d in DESCRIPTORS:
        if remaining.startswith(d):
            descriptor = WEATHER_NAMES[d]
            remaining = remaining[len(d):]
            break

    phens = []
    while remaining:
        matched = False
        for p in sorted(PHENOMENA, key=len, reverse=True):
            if remaining.startswith(p):
                phens.append(WEATHER_NAMES[p])
                remaining = remaining[len(p):]
                matched = True
                break
        if not matched:
            break

    parts = []
    if intensity:
        parts.append(intensity)
    if descriptor:
        parts.append(descriptor)
    parts.extend(phens)

    return ' '.join(parts)


def decode_sky_token(token):
    if token in ('SKC', 'CLR'):
        return {'coverage': 'clear', 'text': 'Clear skies'}
    if token == 'CAVOK':
        return {'coverage': 'clear', 'text': 'Ceiling and Visibility OK'}
    if token in ('NSC', 'NCD'):
        return {'coverage': 'clear', 'text': 'No significant clouds'}

    m = re.match(r'^(FEW|SCT|BKN|OVC)(\d{3})(CB|TCU)?$', token)
    if m:
        cov_code = m.group(1)
        height_ft = int(m.group(2)) * 100
        cloud_type = m.group(3)

        cov_map = {
            'FEW': ('A few clouds', 'few'),
            'SCT': ('Scattered clouds', 'scattered'),
            'BKN': ('Broken clouds', 'broken'),
            'OVC': ('Overcast', 'overcast'),
        }
        text, cov = cov_map[cov_code]

        extra = ''
        if cloud_type == 'CB':
            extra = ' with possible thunderstorm activity'
        elif cloud_type == 'TCU':
            extra = ' (towering cumulus)'

        return {
            'coverage': cov,
            'height': height_ft,
            'text': f"{text}{extra} at {height_ft:,} feet"
        }
    return None


def decode_metar(raw):
    # Take first non-empty line
    line = next((l.strip() for l in raw.split('\n') if l.strip()), '')
    if not line:
        return None

    # Remove remarks section and trend indicators
    for marker in [' RMK ', ' NOSIG', ' TEMPO ', ' BECMG ']:
        if marker in line:
            line = line[:line.index(marker)]

    tokens = line.split()
    result = {}
    i = 0

    # Skip leading report type keyword if present (some APIs prepend it)
    if i < len(tokens) and tokens[i] in ('METAR', 'SPECI'):
        i += 1

    # Station ID (4-letter ICAO code)
    if i < len(tokens):
        result['station'] = tokens[i]
        i += 1

    # Date/Time: DDHHMMz
    if i < len(tokens) and re.match(r'^\d{6}Z$', tokens[i]):
        t = tokens[i]
        result['time'] = f"{t[2:4]}:{t[4:6]} UTC"
        i += 1

    # Report type modifiers — appear after the timestamp in standard METAR format
    while i < len(tokens) and tokens[i] in ('AUTO', 'COR', 'SPECI'):
        if tokens[i] == 'AUTO':
            result['automated'] = True
        i += 1

    # Wind
    if i < len(tokens):
        wm = re.match(r'^(VRB|\d{3})(\d{2,3})(G(\d{2,3}))?(KT|MPS)$', tokens[i])
        if wm:
            raw_dir = wm.group(1)
            raw_spd = int(wm.group(2))
            raw_gust = wm.group(4)
            unit = wm.group(5)

            factor = 1.15078 if unit == 'KT' else 2.23694
            speed_mph = round(raw_spd * factor)
            gust_mph = round(int(raw_gust) * factor) if raw_gust else None

            if raw_spd == 0:
                result['wind'] = {'calm': True, 'text': 'Calm', 'speed_mph': 0}
            elif raw_dir == 'VRB':
                t = f"Variable direction at {speed_mph} mph"
                if gust_mph:
                    t += f", gusting to {gust_mph} mph"
                result['wind'] = {'text': t, 'speed_mph': speed_mph, 'gust_mph': gust_mph}
            else:
                deg = int(raw_dir)
                card = degrees_to_cardinal(deg)
                t = f"From the {card} at {speed_mph} mph"
                if gust_mph:
                    t += f", gusting to {gust_mph} mph"
                result['wind'] = {
                    'text': t, 'speed_mph': speed_mph, 'gust_mph': gust_mph,
                    'direction': card, 'degrees': deg
                }
            i += 1

    # Variable wind direction
    if i < len(tokens) and re.match(r'^\d{3}V\d{3}$', tokens[i]):
        m = re.match(r'^(\d{3})V(\d{3})$', tokens[i])
        d1 = degrees_to_cardinal(int(m.group(1)))
        d2 = degrees_to_cardinal(int(m.group(2)))
        result['wind_variable'] = f"Variable between {d1} and {d2}"
        i += 1

    # Visibility
    if i < len(tokens):
        vis = tokens[i]
        if vis == 'CAVOK':
            result['visibility'] = {'text': '10+ miles (excellent)', 'miles': 10}
            result['sky'] = [{'coverage': 'clear', 'text': 'Ceiling and Visibility OK'}]
            i += 1
        elif vis == 'M1/4SM':
            result['visibility'] = {'text': 'Less than 1/4 mile', 'miles': 0.2}
            i += 1
        elif re.match(r'^\d+SM$', vis):
            miles = int(vis[:-2])
            result['visibility'] = {
                'text': f"{miles} mile{'s' if miles != 1 else ''}",
                'miles': miles
            }
            i += 1
        elif re.match(r'^\d/\dSM$', vis):
            num, den = vis[:-2].split('/')
            miles = int(num) / int(den)
            result['visibility'] = {'text': f"{vis[:-2]} mile", 'miles': miles}
            i += 1
        elif re.match(r'^\d+$', vis) and i + 1 < len(tokens) and re.match(r'^\d/\dSM$', tokens[i + 1]):
            whole = int(vis)
            frac_tok = tokens[i + 1]
            num, den = frac_tok[:-2].split('/')
            miles = whole + int(num) / int(den)
            result['visibility'] = {'text': f"{whole} {frac_tok[:-2]} miles", 'miles': miles}
            i += 2
        elif re.match(r'^\d{4}$', vis):
            # Meters (European/ICAO format)
            meters = int(vis)
            miles = round(meters / 1609.34, 1)
            result['visibility'] = {'text': f"{meters}m (~{miles} miles)", 'miles': miles}
            i += 1

    # Weather phenomena
    weather = []
    while i < len(tokens) and WX_PATTERN.match(tokens[i]):
        w = decode_wx_token(tokens[i])
        if w:
            weather.append(w)
        i += 1
    if weather:
        result['weather'] = weather

    # Sky conditions
    if 'sky' not in result:
        sky = []
        while i < len(tokens) and SKY_PATTERN.match(tokens[i]):
            s = decode_sky_token(tokens[i])
            if s:
                sky.append(s)
            i += 1
        if sky:
            result['sky'] = sky

    # Temperature/Dewpoint
    if i < len(tokens):
        m = re.match(r'^(M?\d+)/(M?\d+)$', tokens[i])
        if m:
            tc = parse_temp(m.group(1))
            dc = parse_temp(m.group(2))
            tf = round(tc * 9 / 5 + 32)
            df = round(dc * 9 / 5 + 32)
            result['temperature'] = {'celsius': tc, 'fahrenheit': tf, 'text': f"{tf}°F ({tc}°C)"}
            result['dewpoint'] = {'celsius': dc, 'fahrenheit': df, 'text': f"{df}°F ({dc}°C)"}
            i += 1

    # Altimeter
    if i < len(tokens):
        am = re.match(r'^A(\d{4})$', tokens[i])
        if am:
            inhg = int(am.group(1)) / 100
            result['altimeter'] = {'text': f"{inhg:.2f} inHg", 'value': inhg}
            i += 1
        elif re.match(r'^Q(\d{4})$', tokens[i]):
            qm = re.match(r'^Q(\d{4})$', tokens[i])
            hpa = int(qm.group(1))
            result['altimeter'] = {'text': f"{hpa} hPa", 'value': hpa}
            i += 1

    return result


def get_weather_icon(data):
    weather = data.get('weather', [])
    sky = data.get('sky', [])

    wx_str = ' '.join(weather).lower()

    if 'thunderstorm' in wx_str:
        return '⛈️'
    if 'tornado' in wx_str or 'funnel' in wx_str:
        return '🌪️'
    if 'snow' in wx_str or 'ice pellets' in wx_str or 'ice crystals' in wx_str:
        return '🌨️'
    if 'freezing' in wx_str:
        return '🌧️'
    if 'rain' in wx_str or 'drizzle' in wx_str:
        return '🌧️'
    if 'fog' in wx_str:
        return '🌫️'
    if 'mist' in wx_str:
        return '🌫️'
    if 'haze' in wx_str or 'smoke' in wx_str or 'dust' in wx_str or 'sand' in wx_str:
        return '🌁'

    if sky:
        cov = sky[-1].get('coverage', 'clear')
        if cov == 'overcast':
            return '☁️'
        if cov == 'broken':
            return '🌥️'
        if cov == 'scattered':
            return '⛅'
        if cov == 'few':
            return '🌤️'
        if cov == 'clear':
            return '☀️'

    return '🌡️'


def generate_summary(data):
    sentences = []

    station = data.get('station', 'the airport')

    # Temperature lead
    temp = data.get('temperature', {})
    tf = temp.get('fahrenheit')
    tc = temp.get('celsius')

    if tf is not None:
        if tf >= 95:
            feel = "extremely hot"
        elif tf >= 85:
            feel = "hot"
        elif tf >= 75:
            feel = "warm"
        elif tf >= 65:
            feel = "mild"
        elif tf >= 55:
            feel = "cool"
        elif tf >= 40:
            feel = "cold"
        elif tf >= 32:
            feel = "near freezing"
        else:
            feel = "below freezing"
        sentences.append(f"At {station}, temperatures are {feel} at {tf}°F ({tc}°C).")

    # Sky and weather conditions
    weather = data.get('weather', [])
    sky = data.get('sky', [])

    if weather:
        wx = ', '.join(weather)
        sentences.append(f"Current weather includes {wx}.")
    elif sky:
        top_cov = sky[-1].get('coverage', 'clear')
        sky_desc = {
            'clear': 'The skies are clear.',
            'few': 'There are just a few clouds in the sky.',
            'scattered': 'Clouds are scattered across the sky.',
            'broken': 'The sky has broken cloud cover.',
            'overcast': 'The sky is completely overcast.',
        }.get(top_cov, '')
        if sky_desc:
            sentences.append(sky_desc)

    # Wind
    wind = data.get('wind', {})
    if wind:
        spd = wind.get('speed_mph', 0)
        if spd == 0:
            sentences.append("Winds are calm.")
        elif spd < 10:
            sentences.append(f"There is a light breeze — winds {wind['text'].lower()}.")
        elif spd < 25:
            sentences.append(f"Winds are moderate — {wind['text'].lower()}.")
        else:
            sentences.append(f"Winds are strong — {wind['text'].lower()}.")

    # Visibility
    vis = data.get('visibility', {})
    miles = vis.get('miles', 10)
    if miles <= 0.5:
        sentences.append("Visibility is extremely poor — dangerous flying conditions.")
    elif miles < 1:
        sentences.append(f"Visibility is very low at {vis.get('text', '')}.")
    elif miles < 3:
        sentences.append(f"Visibility is reduced to {vis.get('text', '')}.")
    elif miles < 7:
        sentences.append(f"Visibility is moderate at {vis.get('text', '')}.")
    else:
        sentences.append(f"Visibility is good at {vis.get('text', '10+ miles')}.")

    # Humidity feel via dewpoint spread
    dew = data.get('dewpoint', {})
    df = dew.get('fahrenheit')
    if df is not None and tf is not None:
        spread = tf - df
        if spread < 5:
            sentences.append("The air feels very humid.")
        elif df >= 65 and spread < 15:
            sentences.append("Humidity is noticeable.")

    return ' '.join(sentences)
