import requests
import json
import re
import os

# Siti da cui scaricare i dati
BASE_URLS = [
    "https://vavoo.to",
]

OUTPUT_DIR = "m3u_files"
OUTPUT_FILE_ALL = os.path.join(OUTPUT_DIR, "channels_all.m3u8")

def clean_channel_name(name):
    """Pulisce il nome del canale rimuovendo caratteri indesiderati."""
    return re.sub(r"\s*(\|E|\|H|\(6\)|\(7\)|\.c|\.s)\s*", "", name)

def fetch_channels(base_url):
    """Scarica i dati JSON da /channels di un sito."""
    try:
        response = requests.get(f"{base_url}/channels", timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Errore durante il download da {base_url}: {e}")
        return []

def classify_channel_by_country(channel):
    """Classifica il canale per nazione."""
    return channel.get("country", "Sconosciuto")

def filter_channels(channels, base_url):
    """Filtra tutti i canali e li classifica per nazione."""
    seen = {}
    results = []
    source_map = {
        "https://vavoo.to": "V",
        "https://huhu.to": "H",
        "https://kool.to": "K",
        "https://oha.to": "O"
    }

    for ch in channels:
        if "name" in ch and "id" in ch:
            clean_name = clean_channel_name(ch["name"])
            source_tag = source_map.get(base_url, "")
            count = seen.get(clean_name, 0) + 1
            seen[clean_name] = count
            if count > 1:
                clean_name = f"{clean_name} ({source_tag}{count})"
            else:
                clean_name = f"{clean_name} ({source_tag})"
            category = classify_channel_by_country(ch)
            results.append((clean_name, f"{base_url}/play/{ch['id']}/index.m3u8", base_url, category))

    return results

def extract_user_agent(base_url):
    """Estrae il nome del sito per l'user agent."""
    match = re.search(r"https?://([^/.]+)", base_url)
    if match:
        return match.group(1).upper()
    return "DEFAULT"

def save_m3u8(channels):
    """Salva i canali in file M3U8 separati per nazione e un file con tutti i canali ordinati per nazione e alfabeticamente."""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    country_files = {}
    all_channels = []

    for name, url, base_url, category in channels:
        user_agent = extract_user_agent(base_url)
        entry = (
            f'#EXTINF:-1 tvg-id="" tvg-name="{name}" group-title="{category}" '
            f'http-user-agent="{user_agent}" http-referrer="{base_url}",{name}\n'
            f"#EXTVLCOPT:http-user-agent={user_agent}/1.0\n"
            f"#EXTVLCOPT:http-referrer={base_url}/\n"
            f'#EXTHTTP:{{"User-Agent":"{user_agent}/1.0","Referer":"{base_url}/"}}\n'
            f"{url}\n\n"
        )

        if category not in country_files:
            country_files[category] = []
        country_files[category].append(entry)
        all_channels.append((category, entry))  # Aggiungiamo la categoria per l'ordinamento

    # **Ordina i canali nei file per nazione**
    for country in country_files:
        country_files[country].sort(key=lambda entry: re.search(r'tvg-name="([^"]+)"', entry).group(1) if re.search(r'tvg-name="([^"]+)"', entry) else "")

        country_file = os.path.join(OUTPUT_DIR, f"channels_{country}.m3u8")
        with open(country_file, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n\n" + "".join(country_files[country]))

    # **Ordina il file completo prima per nazione, poi alfabeticamente**
    all_channels.sort(key=lambda item: (
        item[0],  # Ordina per categoria (nazione)
        re.search(r'tvg-name="([^"]+)"', item[1]).group(1) if re.search(r'tvg-name="([^"]+)"', item[1]) else ""
    ))

    with open(OUTPUT_FILE_ALL, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n\n" + "".join(entry for _, entry in all_channels))

def main():
    all_links = []

    for url in BASE_URLS:
        channels = fetch_channels(url)
        all_channels = filter_channels(channels, url)
        all_links.extend(all_channels)

    save_m3u8(all_links)

    print(f"File M3U8 salvati nella cartella {OUTPUT_DIR}!")

if __name__ == "__main__":
    main()
