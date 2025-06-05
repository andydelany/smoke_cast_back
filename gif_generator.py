import requests
from PIL import Image
import imageio.v2 as imageio
import io
from datetime import datetime
from bs4 import BeautifulSoup
import os
import argparse

# Generate direct image URLs for forecast frames
def generate_smoke_urls(runtime: str, domain='NC', frames=19):
    base_url = f"https://rapidrefresh.noaa.gov/hrrr/HRRRsmoke/for_web/hrrr_ncep_smoke_jet/{runtime}/{domain}"
    plot_prefix = f"trc1_{domain}_sfc"

    urls = []
    for i in range(frames):
        fcst = f"f{i:03d}"
        url = f"{base_url}/{plot_prefix}_{fcst}.png"
        urls.append(url)
    return urls

# Scrape the latest available runtime from the welcome page and convert to required format
def get_latest_runtime():
    url = "https://rapidrefresh.noaa.gov/hrrr/HRRRsmoke/Welcome.cgi"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    select = soup.find('select', {'name': 'run_time'})
    if not select:
        raise ValueError("Could not find run_time select element")

    selected_option = select.find('option', selected=True)
    if not selected_option:
        raise ValueError("Could not find selected run_time option")

    # Convert format "03 Jun 2025 - 13Z" to "2025060313"
    text = selected_option.text.strip()
    try:
        dt = datetime.strptime(text, "%d %b %Y - %HZ")
        return dt.strftime("%Y%m%d%H")
    except ValueError as e:
        raise ValueError(f"Could not parse run_time option text '{text}': {e}")

# Download images and create a GIF
def generate_forecast_gif(domain='NC', frames=19):
    print("Fetching latest available runtime...")
    runtime = get_latest_runtime()
    print(f"Latest runtime: {runtime}")

    urls = generate_smoke_urls(runtime, domain=domain, frames=frames)

    images = []
    for url in urls:
        try:
            print(f"Downloading: {url}")
            response = requests.get(url)
            response.raise_for_status()
            img = Image.open(io.BytesIO(response.content)).convert("RGB")
            images.append(img)
        except Exception as e:
            print(f"Error fetching image from {url}: {e}")

    if not images:
        print("No images were downloaded. Aborting GIF generation.")
        return

    output_filename = f"forecast_{domain}_{runtime}.gif"
    print(f"Saving GIF to {output_filename}")
    imageio.mimsave(output_filename, images, format='GIF', duration=0.5)
    print("GIF generation complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate HRRR Smoke Forecast GIF")
    parser.add_argument("domain", nargs="?", default="NC", help="Domain to use (e.g., NC, full, etc.)")
    parser.add_argument("frames", nargs="?", type=int, default=19, help="Number of forecast frames (default 19)")
    args = parser.parse_args()

    generate_forecast_gif(domain=args.domain, frames=args.frames)