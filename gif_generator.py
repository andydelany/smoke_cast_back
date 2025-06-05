import requests
from PIL import Image
import imageio.v2 as imageio
import io
from datetime import datetime
from bs4 import BeautifulSoup
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

# Generate the referer URL for the forecast frame
def generate_referer_url(runtime: str, domain:str, fcst:int):
    fcst_str = f"{fcst:03d}"
    referer = (
        f"https://rapidrefresh.noaa.gov/hrrr/HRRRsmoke/displayMapUpdated.cgi?"
        f"keys=hrrr_ncep_smoke_jet:&runtime={runtime}"
        f"&plot_type=trc1_{domain}_sfc&fcst={fcst_str}&time_inc=60&num_times=49&model=hrrr"
        f"&ptitle=HRRR-Smoke%20Graphics&maxFcstLen=48&fcstStrLen=-1&domain={domain}&adtfn=1"
    )
    return referer

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

    # Create a session to maintain cookies and state
    session = requests.Session()
    
    images = []
    for i, url in enumerate(urls):
        referer = generate_referer_url(runtime, domain=domain, fcst=i)
        headers = {
            "Referer": referer, 
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        try:
            # First, visit the referer page to establish session
            print(f"Establishing session with referer: {referer}")
            session.get(referer, headers=headers)
            
            print(f"Downloading: {url}")
            response = session.get(url, headers=headers)
            if response.status_code != 200:
                print(f"Error: Got status code {response.status_code} for {url}")
                break
            content_type = response.headers.get("Content-Type", "")
            if "image" not in content_type:
                print(f"Unexpected content type for {url}: {content_type}")
                break
            try:
                img = Image.open(io.BytesIO(response.content)).convert("RGB")
                images.append(img)
            except Exception as img_err:
                print(f"Error decoding image from {url}: {img_err}")
                break
        except Exception as e:
            print(f"Error fetching image from {url}: {e}")
            break

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