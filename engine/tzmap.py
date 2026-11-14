"""Timezone resolution helpers for jetlag-forge.

Resolves airport codes, city names and explicit IANA zones into IANA
timezone identifiers. No network access, no API keys.
"""

AIRPORT_TZ = {
    # North America - US East
    "JFK": "America/New_York", "LGA": "America/New_York", "EWR": "America/New_York",
    "BOS": "America/New_York", "PHL": "America/New_York", "IAD": "America/New_York",
    "DCA": "America/New_York", "ATL": "America/New_York", "MIA": "America/New_York",
    "FLL": "America/New_York", "CLT": "America/New_York", "RDU": "America/New_York",
    "MCO": "America/New_York", "TPA": "America/New_York", "DTW": "America/New_York",
    "CLE": "America/New_York", "PIT": "America/New_York", "BUF": "America/New_York",
    "ROC": "America/New_York", "BDL": "America/New_York", "PVD": "America/New_York",
    "SDF": "America/New_York", "RIC": "America/New_York", "JAX": "America/New_York",
    "CHS": "America/New_York", "CAE": "America/New_York", "SAV": "America/New_York",
    "ALB": "America/New_York", "SYR": "America/New_York", "RIC": "America/New_York",
    "ORF": "America/New_York", "BHM": "America/Chicago",
    # North America - US Central
    "ORD": "America/Chicago", "MDW": "America/Chicago", "DFW": "America/Chicago",
    "AUS": "America/Chicago", "SAT": "America/Chicago", "IAH": "America/Chicago",
    "HOU": "America/Chicago", "MSY": "America/Chicago", "STL": "America/Chicago",
    "MCI": "America/Chicago", "MSP": "America/Chicago", "MEM": "America/Chicago",
    "OKC": "America/Chicago", "TUL": "America/Chicago", "IND": "America/Chicago",
    "MKE": "America/Chicago", "BNA": "America/Chicago", "OMA": "America/Chicago",
    "MSY": "America/Chicago", "DSM": "America/Chicago", "MSN": "America/Chicago",
    # North America - US Mountain
    "DEN": "America/Denver", "SLC": "America/Denver", "ABQ": "America/Denver",
    "COS": "America/Denver", "ELP": "America/Denver", "BOI": "America/Denver",
    "BIL": "America/Denver", "CYS": "America/Denver",
    # North America - US Pacific
    "LAX": "America/Los_Angeles", "SFO": "America/Los_Angeles", "SAN": "America/Los_Angeles",
    "SJC": "America/Los_Angeles", "OAK": "America/Los_Angeles", "SMF": "America/Los_Angeles",
    "LAX": "America/Los_Angeles", "BUR": "America/Los_Angeles", "LGB": "America/Los_Angeles",
    "SEA": "America/Los_Angeles", "PDX": "America/Los_Angeles", "LAS": "America/Los_Angeles",
    "RNO": "America/Los_Angeles", "SBA": "America/Los_Angeles", "PSP": "America/Los_Angeles",
    "MFR": "America/Los_Angeles", "RDD": "America/Los_Angeles", "GEG": "America/Los_Angeles",
    "ANC": "America/Anchorage", "HNL": "Pacific/Honolulu", "OGG": "Pacific/Honolulu",
    # Canada
    "YYZ": "America/Toronto", "YUL": "America/Toronto", "YOW": "America/Toronto",
    "YYC": "America/Edmonton", "YEG": "America/Edmonton", "YVR": "America/Vancouver",
    "YWG": "America/Winnipeg", "YHZ": "America/Halifax", "YQB": "America/Toronto",
    # Mexico / Caribbean
    "MEX": "America/Mexico_City", "GDL": "America/Mexico_City", "MTY": "America/Monterrey",
    "CUN": "America/Cancun", "SJD": "America/Mazatlan", "PVR": "America/Mexico_City",
    "HAV": "America/Havana", "PUJ": "America/Santo_Domingo", "SJU": "America/Puerto_Rico",
    # Europe - UK / Ireland
    "LHR": "Europe/London", "LGW": "Europe/London", "STN": "Europe/London",
    "LTN": "Europe/London", "LCY": "Europe/London", "EMA": "Europe/London",
    "EDI": "Europe/London", "BHX": "Europe/London", "MAN": "Europe/London",
    "DUB": "Europe/Dublin", "ORK": "Europe/Dublin",
    # Europe - West
    "CDG": "Europe/Paris", "ORY": "Europe/Paris", "NCE": "Europe/Paris",
    "MRS": "Europe/Paris", "LYS": "Europe/Paris", "TLS": "Europe/Paris",
    "AMS": "Europe/Amsterdam", "EIN": "Europe/Amsterdam", "BRU": "Europe/Brussels",
    "LUX": "Europe/Luxembourg",
    # Europe - Central
    "FRA": "Europe/Berlin", "MUC": "Europe/Berlin", "BER": "Europe/Berlin",
    "DUS": "Europe/Berlin", "HAM": "Europe/Berlin", "STR": "Europe/Berlin",
    "CGN": "Europe/Berlin", "HAJ": "Europe/Berlin", "NUE": "Europe/Berlin",
    "VIE": "Europe/Vienna", "PRG": "Europe/Prague", "WAW": "Europe/Warsaw",
    "KRK": "Europe/Warsaw", "BUD": "Europe/Budapest", "OTP": "Europe/Bucharest",
    "SOF": "Europe/Sofia", "BEG": "Europe/Belgrade", "ZAG": "Europe/Zagreb",
    "LJU": "Europe/Ljubljana", "SJJ": "Europe/Sarajevo", "SKP": "Europe/Skopje",
    "TIA": "Europe/Tirane", "ZRH": "Europe/Zurich", "GVA": "Europe/Zurich",
    "SZG": "Europe/Zurich", "BRN": "Europe/Zurich",
    # Europe - South
    "LIS": "Europe/Lisbon", "OPO": "Europe/Lisbon", "FAO": "Europe/Lisbon",
    "MAD": "Europe/Madrid", "BCN": "Europe/Madrid", "AGP": "Europe/Madrid",
    "PMI": "Europe/Madrid", "VLC": "Europe/Madrid", "SVQ": "Europe/Madrid",
    "FCO": "Europe/Rome", "MXP": "Europe/Rome", "LIN": "Europe/Rome",
    "BLQ": "Europe/Rome", "NAP": "Europe/Rome", "VCE": "Europe/Rome",
    "ATH": "Europe/Athens", "SKG": "Europe/Athens", "HER": "Europe/Athens",
    "IST": "Europe/Istanbul", "SAW": "Europe/Istanbul", "AYT": "Europe/Istanbul",
    "ADB": "Europe/Istanbul", "ESB": "Europe/Istanbul",
    # Europe - North
    "CPH": "Europe/Copenhagen", "ARN": "Europe/Stockholm", "OSL": "Europe/Oslo",
    "HEL": "Europe/Helsinki", "TLL": "Europe/Tallinn", "RIX": "Europe/Riga",
    "VNO": "Europe/Vilnius", "KEF": "Atlantic/Reykjavik", "TOS": "Atlantic/Reykjavik",
    # Middle East / Central Asia
    "TLV": "Asia/Jerusalem", "AMM": "Asia/Amman", "BEY": "Asia/Beirut",
    "DXB": "Asia/Dubai", "AUH": "Asia/Dubai", "SHJ": "Asia/Dubai",
    "DOH": "Asia/Qatar", "RUH": "Asia/Riyadh", "JED": "Asia/Riyadh",
    "DMM": "Asia/Riyadh", "KWI": "Asia/Kuwait", "BAH": "Asia/Bahrain",
    "MCT": "Asia/Muscat", "IKA": "Asia/Tehran", "ALA": "Asia/Almaty",
    "TAS": "Asia/Tashkent", "GYD": "Asia/Tashkent", "EVN": "Asia/Yerevan",
    "TBS": "Asia/Tbilisi", "BAK": "Asia/Baku", "LED": "Europe/Moscow",
    "SVO": "Europe/Moscow", "DME": "Europe/Moscow", "VKO": "Europe/Moscow",
    # Asia - East
    "PEK": "Asia/Shanghai", "PKX": "Asia/Shanghai", "PVG": "Asia/Shanghai",
    "SHA": "Asia/Shanghai", "CAN": "Asia/Shanghai", "SZX": "Asia/Shanghai",
    "CTU": "Asia/Shanghai", "HKG": "Asia/Hong_Kong", "MFM": "Asia/Macau",
    "TPE": "Asia/Taipei", "TSA": "Asia/Taipei", "KHH": "Asia/Taipei",
    "ICN": "Asia/Seoul", "GMP": "Asia/Seoul", "CJU": "Asia/Jeju",
    "NRT": "Asia/Tokyo", "HND": "Asia/Tokyo", "KIX": "Asia/Tokyo",
    "ITM": "Asia/Tokyo", "FUK": "Asia/Tokyo", "CTS": "Asia/Tokyo",
    "NGO": "Asia/Tokyo", "OKA": "Asia/Tokyo",
    # Asia - Southeast
    "SIN": "Asia/Singapore", "BKK": "Asia/Bangkok", "DMK": "Asia/Bangkok",
    "HKT": "Asia/Bangkok", "CNX": "Asia/Bangkok", "KUL": "Asia/Kuala_Lumpur",
    "PEN": "Asia/Kuala_Lumpur", "CGK": "Asia/Jakarta", "DPS": "Asia/Makassar",
    "MNL": "Asia/Manila", "CEB": "Asia/Manila", "SGN": "Asia/Ho_Chi_Minh",
    "HAN": "Asia/Ho_Chi_Minh", "DAD": "Asia/Ho_Chi_Minh", "PNH": "Asia/Phnom_Penh",
    "VTE": "Asia/Vientiane", "RGN": "Asia/Yangon",
    # Asia - South
    "DEL": "Asia/Kolkata", "BOM": "Asia/Kolkata", "MAA": "Asia/Kolkata",
    "BLR": "Asia/Kolkata", "HYD": "Asia/Kolkata", "CCU": "Asia/Kolkata",
    "COK": "Asia/Kolkata", "GOI": "Asia/Kolkata", "AMD": "Asia/Kolkata",
    "DAC": "Asia/Dhaka", "KTM": "Asia/Kathmandu", "CMB": "Asia/Colombo",
    "MLE": "Indian/Maldives",
    # Oceania
    "SYD": "Australia/Sydney", "MEL": "Australia/Melbourne", "BNE": "Australia/Brisbane",
    "PER": "Australia/Perth", "ADL": "Australia/Adelaide", "CBR": "Australia/Sydney",
    "CNS": "Australia/Brisbane", "OOL": "Australia/Brisbane", "HBA": "Australia/Hobart",
    "AKL": "Pacific/Auckland", "CHC": "Pacific/Auckland", "WLG": "Pacific/Auckland",
    "ZQN": "Pacific/Auckland", "NAN": "Pacific/Fiji", "PPT": "Pacific/Tahiti",
    "GUM": "Pacific/Guam", "NOU": "Pacific/Noumea", "POM": "Pacific/Port_Moresby",
    # South America / Africa
    "GRU": "America/Sao_Paulo", "GIG": "America/Sao_Paulo", "BSB": "America/Sao_Paulo",
    "CNF": "America/Sao_Paulo", "POA": "America/Sao_Paulo", "REC": "America/Recife",
    "EZE": "America/Argentina/Buenos_Aires", "AEP": "America/Argentina/Buenos_Aires",
    "SCL": "America/Santiago", "LIM": "America/Lima", "BOG": "America/Bogota",
    "MVD": "America/Montevideo", "ASU": "America/Asuncion", "PTY": "America/Panama",
    "CAI": "Africa/Cairo", "JNB": "Africa/Johannesburg", "CPT": "Africa/Johannesburg",
    "NBO": "Africa/Nairobi", "ADD": "Africa/Addis_Ababa", "CMN": "Africa/Casablanca",
    "LOS": "Africa/Lagos", "ACC": "Africa/Accra", "DAR": "Africa/Dar_es_Salaam",
    "ZNZ": "Africa/Nairobi", "TNR": "Indian/Antananarivo",
}

CITY_TZ = {
    "NEW YORK": "America/New_York", "NYC": "America/New_York", "MANHATTAN": "America/New_York",
    "BOSTON": "America/New_York", "PHILADELPHIA": "America/New_York", "WASHINGTON": "America/New_York",
    "WASHINGTON DC": "America/New_York", "ATLANTA": "America/New_York", "MIAMI": "America/New_York",
    "MIAMI BEACH": "America/New_York", "SEATTLE": "America/Los_Angeles", "PORTLAND": "America/Los_Angeles",
    "SAN FRANCISCO": "America/Los_Angeles", "LOS ANGELES": "America/Los_Angeles",
    "SAN DIEGO": "America/Los_Angeles", "SAN JOSE": "America/Los_Angeles",
    "LAS VEGAS": "America/Los_Angeles", "PHOENIX": "America/Phoenix", "DENVER": "America/Denver",
    "SALT LAKE CITY": "America/Denver", "ALBUQUERQUE": "America/Denver", "AUSTIN": "America/Chicago",
    "DALLAS": "America/Chicago", "HOUSTON": "America/Chicago", "CHICAGO": "America/Chicago",
    "ST LOUIS": "America/Chicago", "MINNEAPOLIS": "America/Chicago", "NEW ORLEANS": "America/Chicago",
    "NASHVILLE": "America/Chicago", "TORONTO": "America/Toronto", "MONTREAL": "America/Toronto",
    "VANCOUVER": "America/Vancouver", "CALGARY": "America/Edmonton", "MEXICO CITY": "America/Mexico_City",
    "LONDON": "Europe/London", "MANCHESTER": "Europe/London", "EDINBURGH": "Europe/London",
    "DUBLIN": "Europe/Dublin", "PARIS": "Europe/Paris", "LYON": "Europe/Paris",
    "BRUSSELS": "Europe/Brussels", "AMSTERDAM": "Europe/Amsterdam", "BERLIN": "Europe/Berlin",
    "MUNICH": "Europe/Berlin", "HAMBURG": "Europe/Berlin", "FRANKFURT": "Europe/Berlin",
    "BERNE": "Europe/Zurich", "ZURICH": "Europe/Zurich", "GENEVA": "Europe/Zurich",
    "VIENNA": "Europe/Vienna", "PRAGUE": "Europe/Prague", "WARSAW": "Europe/Warsaw",
    "BUDAPEST": "Europe/Budapest", "BUCHAREST": "Europe/Bucharest", "ATHENS": "Europe/Athens",
    "ROME": "Europe/Rome", "MILAN": "Europe/Rome", "VENICE": "Europe/Rome",
    "NAPLES": "Europe/Rome", "FLORENCE": "Europe/Rome", "MADRID": "Europe/Madrid",
    "BARCELONA": "Europe/Madrid", "SEVILLE": "Europe/Madrid", "LISBON": "Europe/Lisbon",
    "PORTO": "Europe/Lisbon", "COPENHAGEN": "Europe/Copenhagen", "STOCKHOLM": "Europe/Stockholm",
    "OSLO": "Europe/Oslo", "HELSINKI": "Europe/Helsinki", "REYKJAVIK": "Atlantic/Reykjavik",
    "ISTANBUL": "Europe/Istanbul", "MOSCOW": "Europe/Moscow", "TEL AVIV": "Asia/Jerusalem",
    "DUBAI": "Asia/Dubai", "ABU DHABI": "Asia/Dubai", "DOHA": "Asia/Qatar",
    "RIYADH": "Asia/Riyadh", "JEDDAH": "Asia/Riyadh", "DOHA": "Asia/Qatar",
    "TOKYO": "Asia/Tokyo", "OSAKA": "Asia/Tokyo", "KYOTO": "Asia/Tokyo",
    "NAGOYA": "Asia/Tokyo", "SAPPORO": "Asia/Tokyo", "FUKUOKA": "Asia/Tokyo",
    "SEOUL": "Asia/Seoul", "BEIJING": "Asia/Shanghai", "SHANGHAI": "Asia/Shanghai",
    "GUANGZHOU": "Asia/Shanghai", "SHENZHEN": "Asia/Shanghai", "HONG KONG": "Asia/Hong_Kong",
    "TAIPEI": "Asia/Taipei", "SINGAPORE": "Asia/Singapore", "BANGKOK": "Asia/Bangkok",
    "KUALA LUMPUR": "Asia/Kuala_Lumpur", "JAKARTA": "Asia/Jakarta",
    "BALI": "Asia/Makassar", "MANILA": "Asia/Manila", "PHNOM PENH": "Asia/Phnom_Penh",
    "HO CHI MINH CITY": "Asia/Ho_Chi_Minh", "DELHI": "Asia/Kolkata", "NEW DELHI": "Asia/Kolkata",
    "MUMBAI": "Asia/Kolkata", "BENGALURU": "Asia/Kolkata", "BANGALORE": "Asia/Kolkata",
    "HYDERABAD": "Asia/Kolkata", "CHENNAI": "Asia/Kolkata", "KATHMANDU": "Asia/Kathmandu",
    "COLOMBO": "Asia/Colombo", "SYDNEY": "Australia/Sydney", "MELBOURNE": "Australia/Melbourne",
    "BRISBANE": "Australia/Brisbane", "PERTH": "Australia/Perth", "ADELAIDE": "Australia/Adelaide",
    "AUCKLAND": "Pacific/Auckland", "WELLINGTON": "Pacific/Auckland",
    "CHRISTCHURCH": "Pacific/Auckland", "SAO PAULO": "America/Sao_Paulo",
    "RIO DE JANEIRO": "America/Sao_Paulo", "BRASILIA": "America/Sao_Paulo",
    "BUENOS AIRES": "America/Argentina/Buenos_Aires", "SANTIAGO": "America/Santiago",
    "LIMA": "America/Lima", "BOGOTA": "America/Bogota", "CAIRO": "Africa/Cairo",
    "JOHANNESBURG": "Africa/Johannesburg", "CAPE TOWN": "Africa/Johannesburg",
    "NAIROBI": "Africa/Nairobi", "LAGOS": "Africa/Lagos", "CASABLANCA": "Africa/Casablanca",
    "ACCRA": "Africa/Accra", "ADDIS ABABA": "Africa/Addis_Ababa",
}


def resolve(token):
    """Resolve a place token into (iana_tz, kind, display_name).

    Accepts IANA zones ("Asia/Tokyo"), airport codes ("NRT"), city names
    ("Tokyo") and explicit overrides ("NRT(Asia/Tokyo)").
    Returns (None, "unknown", token) when the token cannot be resolved.
    """
    if not token:
        return None, "unknown", ""
    raw = str(token).strip()
    if not raw:
        return None, "unknown", ""

    display = raw
    override = None
    if "(" in raw and raw.endswith(")"):
        head, _, tail = raw.partition("(")
        override = tail[:-1].strip()
        raw = head.strip()
        display = head.strip()

    if override:
        return override, "explicit", display

    if "/" in raw:
        return raw, "iana", raw

    upper = raw.upper()
    if len(upper) == 3 and upper in AIRPORT_TZ:
        return AIRPORT_TZ[upper], "airport", upper
    if upper in CITY_TZ:
        return CITY_TZ[upper], "city", raw

    # Fall back to a city whose name contains the token (e.g. "TOKYO JAPAN").
    for name, tz in sorted(CITY_TZ.items(), key=lambda kv: -len(kv[0])):
        if name in upper:
            return tz, "city", raw
    return None, "unknown", display
