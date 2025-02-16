import requests
import json
import re
import os
import time

# Siti da cui scaricare i canali IPTV
BASE_URLS = [
    "https://vavoo.to",
]

OUTPUT_DIR = "output_m3u8"
ALL_CHANNELS_FILE = os.path.join(OUTPUT_DIR, "channels_all.m3u8")

os.makedirs(OUTPUT_DIR, exist_ok=True)

def clean_channel_name(name):
    """Pulisce il nome del canale rimuovendo caratteri indesiderati."""
    return re.sub(r"\s*(\|E|\|H|\(6\)|\(7\)|\.c|\.s)\s*", "", name)

def fetch_channels(base_url, retries=3):
    """Scarica i dati JSON da /channels di un sito IPTV con retry e backoff esponenziale."""
    for attempt in range(retries):
        try:
            response = requests.get(f"{base_url}/channels", timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Errore durante il download da {base_url} (tentativo {attempt+1}): {e}")
            time.sleep(2 ** attempt)
    return []

def extract_user_agent(base_url):
    """Estrae il nome del sito senza estensione e lo converte in maiuscolo per l'user agent."""
    match = re.search(r"https?://([^/.]+)", base_url)
    return match.group(1).upper() if match else "DEFAULT"

def save_m3u8(channels_by_country):
    """Salva un file M3U8 per ogni nazione e uno generale con tutti i canali."""
    
    # File con tutti i canali
    with open(ALL_CHANNELS_FILE, "w", encoding="utf-8") as all_file:
        all_file.write("#EXTM3U\n\n")

        for country, channels in channels_by_country.items():
            country_file = os.path.join(OUTPUT_DIR, f"channels_{country.replace(' ', '_')}.m3u8")
            
            with open(country_file, "w", encoding="utf-8") as country_f:
                country_f.write("#EXTM3U\n\n")

                for name, url, base_url, user_agent in channels:
                    extinf = f'#EXTINF:-1 group-title="{country}" http-user-agent="{user_agent}/2.6" http-referrer="{base_url}", {name}\n'
                    
                    country_f.write(extinf)
                    country_f.write(f"{url}\n\n")
                    
                    all_file.write(extinf)
                    all_file.write(f"{url}\n\n")

            print(f"Creato file: {country_file}")

    print(f"Creato file generale: {ALL_CHANNELS_FILE}")

def main():
    channels_by_country = {}

    for url in BASE_URLS:
        channels = fetch_channels(url)

        for ch in channels:
            clean_name = clean_channel_name(ch["name"])
            country = ch.get("country", "Unknown").strip()

            if country not in channels_by_country:
                channels_by_country[country] = []

            if clean_name not in [c[0] for c in channels_by_country[country]]:  # Evita duplicati
                channels_by_country[country].append((clean_name, f"{url}/play/{ch['id']}/index.m3u8", url, extract_user_agent(url)))

    save_m3u8(channels_by_country)

if __name__ == "__main__":
    main()