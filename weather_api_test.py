import requests

# Test MET.NO
metno_url = (
    "https://api.met.no/weatherapi/locationforecast/2.0/compact?lat=53.3&lon=-6.4"
)
metno_headers = {"User-Agent": "PhotomaticWeatherDisplay/1.0"}

try:
    print("Testing MET.NO...")
    r = requests.get(metno_url, headers=metno_headers, timeout=10)
    print("Status:", r.status_code)
    print("Response snippet:", r.text[:200])
except Exception as e:
    print("MET.NO error:", e)

# Test OPEN-METEO
openmeteo_url = "https://api.open-meteo.com/v1/forecast?latitude=53.3&longitude=-6.4&current_weather=true"

try:
    print("Testing OPEN-METEO...")
    r = requests.get(openmeteo_url, timeout=10)
    print("Status:", r.status_code)
    print("Response snippet:", r.text[:200])
except Exception as e:
    print("OPEN-METEO error:", e)
