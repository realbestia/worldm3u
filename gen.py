import requests
import json
import re
import os
import gzip
import lzma
import io
import time
import xml.etree.ElementTree as ET
from fuzzywuzzy import fuzz

# Siti da cui scaricare i canali IPTV
BASE_URLS = [
    "https://vavoo.to",
]

# URL dei file EPG (XML normali e compressi)
EPG_URLS = [
    "https://www.epgitalia.tv/gzip",
    "https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz",
    "https://www.open-epg.com/files/italy1.xml",
    "https://www.open-epg.com/files/italy2.xml"
]

OUTPUT_DIR = "m3u8_files"
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

def download_epg(epg_url):
    """Scarica e decomprime un file EPG XML o compresso (GZIP/XZ)."""
    try:
        response = requests.get(epg_url, timeout=10)
        response.raise_for_status()
        
        file_signature = response.content[:2]

        if file_signature.startswith(b'\x1f\x8b'):  # GZIP
            with gzip.GzipFile(fileobj=io.BytesIO(response.content)) as gz_file:
                xml_content = gz_file.read()
        elif file_signature.startswith(b'\xfd7z'):  # XZ
            with lzma.LZMAFile(fileobj=io.BytesIO(response.content)) as xz_file:
                xml_content = xz_file.read()
        else:
            xml_content = response.content

        return ET.ElementTree(ET.fromstring(xml_content)).getroot()

    except (requests.RequestException, gzip.BadGzipFile, lzma.LZMAError, ET.ParseError) as e:
        print(f"Errore durante il download/parsing dell'EPG da {epg_url}: {e}")
        return None

def get_tvg_id_from_epg(tvg_name, epg_data):
    """Cerca il tvg-id nel file EPG usando fuzzy matching più preciso."""
    best_match = None
    best_score = 0

    for epg_root in epg_data:
        for channel in epg_root.findall("channel"):
            epg_channel_name = channel.find("display-name").text
            if not epg_channel_name:
                continue  

            cleaned_tvg_name = re.sub(r"\s+", " ", tvg_name.strip().lower())
            cleaned_epg_name = re.sub(r"\s+", " ", epg_channel_name.strip().lower())

            similarity = fuzz.token_sort_ratio(cleaned_tvg_name, cleaned_epg_name)

            if similarity > best_score:
                best_score = similarity
                best_match = channel.get("id")

            if best_score >= 98:
                return best_match

    return best_match if best_score >= 80 else ""

def save_m3u8(channels_by_country, epg_urls, epg_data):
    """Salva un file M3U8 per ogni nazione e uno generale con tutti i canali."""
    
    # File con tutti i canali
    with open(ALL_CHANNELS_FILE, "w", encoding="utf-8") as all_file:
        all_file.write(f'#EXTM3U x-tvg-url="{", ".join(epg_urls)}"\n\n')

        for country, channels in channels_by_country.items():
            country_file = os.path.join(OUTPUT_DIR, f"channels_{country.replace(' ', '_')}.m3u8")
            
            with open(country_file, "w", encoding="utf-8") as country_f:
                country_f.write(f'#EXTM3U x-tvg-url="{", ".join(epg_urls)}"\n\n')

                for name, url, base_url, user_agent in channels:
                    tvg_id = get_tvg_id_from_epg(name, epg_data)
                    extinf = f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{name}" group-title="{country}" http-user-agent="{user_agent}/2.6" http-referrer="{base_url}", {name}\n'
                    
                    country_f.write(extinf)
                    country_f.write(f"{url}\n\n")
                    
                    all_file.write(extinf)
                    all_file.write(f"{url}\n\n")

            print(f"Creato file: {country_file}")

    print(f"Creato file generale: {ALL_CHANNELS_FILE}")

def main():
    epg_data = [download_epg(url) for url in EPG_URLS if (data := download_epg(url))]

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

    save_m3u8(channels_by_country, EPG_URLS, epg_data)

if __name__ == "__main__":
    main()