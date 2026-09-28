"""Static lookup: Singapore postal sector (first 2 digits of a 6-digit postal
code) -> (district number, district area name).

This is public, stable reference data (URA's well-known 28-district postal
sector table), not something derived from OneMap, so it's hardcoded rather
than fetched.
"""

# sector (str, zero-padded 2 digits) -> (district_number, area_name)
SECTOR_TO_DISTRICT: dict[str, tuple[int, str]] = {
    "01": (1, "Raffles Place, Cecil, Marina, People's Park"),
    "02": (1, "Raffles Place, Cecil, Marina, People's Park"),
    "03": (1, "Raffles Place, Cecil, Marina, People's Park"),
    "04": (1, "Raffles Place, Cecil, Marina, People's Park"),
    "05": (1, "Raffles Place, Cecil, Marina, People's Park"),
    "06": (1, "Raffles Place, Cecil, Marina, People's Park"),
    "07": (2, "Anson, Tanjong Pagar"),
    "08": (2, "Anson, Tanjong Pagar"),
    "14": (3, "Queenstown, Tiong Bahru"),
    "15": (3, "Queenstown, Tiong Bahru"),
    "16": (3, "Queenstown, Tiong Bahru"),
    "09": (4, "Telok Blangah, Harbourfront"),
    "10": (4, "Telok Blangah, Harbourfront"),
    "11": (5, "Pasir Panjang, Hong Leong Garden, Clementi New Town"),
    "12": (5, "Pasir Panjang, Hong Leong Garden, Clementi New Town"),
    "13": (5, "Pasir Panjang, Hong Leong Garden, Clementi New Town"),
    "17": (6, "High Street, Beach Road (City Hall)"),
    "18": (7, "Middle Road, Golden Mile"),
    "19": (7, "Middle Road, Golden Mile"),
    "20": (8, "Little India, Farrer Park"),
    "21": (8, "Little India, Farrer Park"),
    "22": (9, "Orchard, Cairnhill, River Valley"),
    "23": (9, "Orchard, Cairnhill, River Valley"),
    "24": (10, "Ardmore, Bukit Timah, Holland Road, Tanglin"),
    "25": (10, "Ardmore, Bukit Timah, Holland Road, Tanglin"),
    "26": (10, "Ardmore, Bukit Timah, Holland Road, Tanglin"),
    "27": (10, "Ardmore, Bukit Timah, Holland Road, Tanglin"),
    "28": (11, "Watten Estate, Novena, Thomson"),
    "29": (11, "Watten Estate, Novena, Thomson"),
    "30": (11, "Watten Estate, Novena, Thomson"),
    "31": (12, "Balestier, Toa Payoh, Serangoon"),
    "32": (12, "Balestier, Toa Payoh, Serangoon"),
    "33": (12, "Balestier, Toa Payoh, Serangoon"),
    "34": (13, "Macpherson, Braddell"),
    "35": (13, "Macpherson, Braddell"),
    "36": (13, "Macpherson, Braddell"),
    "37": (13, "Macpherson, Braddell"),
    "38": (14, "Geylang, Eunos"),
    "39": (14, "Geylang, Eunos"),
    "40": (14, "Geylang, Eunos"),
    "41": (14, "Geylang, Eunos"),
    "42": (15, "Katong, Joo Chiat, Amber Road"),
    "43": (15, "Katong, Joo Chiat, Amber Road"),
    "44": (15, "Katong, Joo Chiat, Amber Road"),
    "45": (15, "Katong, Joo Chiat, Amber Road"),
    "46": (16, "Bedok, Upper East Coast, Eastwood, Kew Drive"),
    "47": (16, "Bedok, Upper East Coast, Eastwood, Kew Drive"),
    "48": (16, "Bedok, Upper East Coast, Eastwood, Kew Drive"),
    "49": (17, "Loyang, Changi"),
    "50": (17, "Loyang, Changi"),
    "81": (17, "Loyang, Changi"),
    "51": (18, "Tampines, Pasir Ris"),
    "52": (18, "Tampines, Pasir Ris"),
    "53": (19, "Serangoon Garden, Hougang, Punggol"),
    "54": (19, "Serangoon Garden, Hougang, Punggol"),
    "55": (19, "Serangoon Garden, Hougang, Punggol"),
    "82": (19, "Serangoon Garden, Hougang, Punggol"),
    "56": (20, "Bishan, Ang Mo Kio"),
    "57": (20, "Bishan, Ang Mo Kio"),
    "58": (21, "Upper Bukit Timah, Clementi Park, Ulu Pandan"),
    "59": (21, "Upper Bukit Timah, Clementi Park, Ulu Pandan"),
    "60": (22, "Jurong"),
    "61": (22, "Jurong"),
    "62": (22, "Jurong"),
    "63": (22, "Jurong"),
    "64": (22, "Jurong"),
    "65": (23, "Hillview, Dairy Farm, Bukit Panjang, Choa Chu Kang"),
    "66": (23, "Hillview, Dairy Farm, Bukit Panjang, Choa Chu Kang"),
    "67": (23, "Hillview, Dairy Farm, Bukit Panjang, Choa Chu Kang"),
    "68": (23, "Hillview, Dairy Farm, Bukit Panjang, Choa Chu Kang"),
    "69": (24, "Lim Chu Kang, Tengah"),
    "70": (24, "Lim Chu Kang, Tengah"),
    "71": (24, "Lim Chu Kang, Tengah"),
    "72": (25, "Kranji, Woodgrove"),
    "73": (25, "Kranji, Woodgrove"),
    "77": (26, "Upper Thomson, Springleaf"),
    "78": (26, "Upper Thomson, Springleaf"),
    "75": (27, "Yishun, Sembawang"),
    "76": (27, "Yishun, Sembawang"),
    "79": (28, "Seletar"),
    "80": (28, "Seletar"),
}


def sector_to_label(sector: str) -> str:
    """Format a district lookup as e.g. 'D16 - Bedok, Upper East Coast, Eastwood, Kew Drive'."""
    entry = SECTOR_TO_DISTRICT.get(sector)
    if entry is None:
        return "Unknown"
    number, name = entry
    return f"D{number:02d} - {name}"
