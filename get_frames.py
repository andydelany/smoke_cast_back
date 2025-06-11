import requests
from PIL import Image
import imageio.v2 as imageio
import io
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
import argparse
import os
import shutil
import pytz
import json


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

def utc_to_central(utc_dt):
    # Convert naive datetime in UTC to Central Time with daylight savings handled
    utc = pytz.utc
    central = pytz.timezone("US/Central")
    utc_dt = utc.localize(utc_dt)
    central_dt = utc_dt.astimezone(central)
    return central_dt.strftime("%Y-%m-%d %H:%M %Z")

def generate_forecast_metadata(runtime, frames, domain):
    base_dt = datetime.strptime(runtime, "%Y%m%d%H")  # runtime start datetime UTC
    metadata = []
    for i in range(frames):
        frame_time_utc = base_dt + timedelta(hours=i)
        frame_time_central = utc_to_central(frame_time_utc)
        metadata.append({
            "frame_index": i,
            "time_utc": frame_time_utc.strftime("%Y-%m-%d %H:%M UTC"),
            "time_central": frame_time_central,
            "filename": f"frame_{i:03d}.png"
        })
    return metadata

def cleanup_old_runs(base_dir, domain,keep_after_date):
    for folder in os.listdir(base_dir):
        folder_path = os.path.join(base_dir, folder)
        if os.path.isdir(folder_path):
            try:
                folder_datetime = datetime.strptime(folder, f"frames_{domain}_%Y%m%d%H")
                if folder_datetime < keep_after_date:
                    print(f"Deleting old folder: {folder}")
                    shutil.rmtree(folder_path)
            except ValueError:
                # Skip folders that don't match the expected naming pattern
                continue

# Download images and create a GIF or frames
def generate_forecast(domain='NC', frames=19, output_type = "frames"):
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

    metadata = generate_forecast_metadata(runtime, frames, domain)
    output_filename = f"finishedGIFS/forecast_{domain}_{runtime}.gif"
    output_folder = f"frames/frames_{domain}_{runtime}"

    if output_type == 'gif':
        print(f"Saving GIF to {output_filename}")
        imageio.mimsave(output_filename, images, format='GIF', duration=1, loop=0)
        print("GIF generation complete.")
    elif output_type == 'frames':
        os.makedirs(output_folder, exist_ok=True)
        print(f"Saving individual frames to {output_folder}/")
        for idx, img in enumerate(images):
            img.save(os.path.join(output_folder, f"frame_{idx:03d}.png"))
        print("Frame saving complete.")
        with open(os.path.join(output_folder, "metadata.json"), "w") as f:
            json.dump(metadata, f, indent=2)
        shutil.rmtree(f"frames/latest_{domain}", ignore_errors=True)
        shutil.copytree(output_folder, f"frames/latest_{domain}")
        keep_after = datetime.now(timezone.utc) - timedelta(days=1)
        cleanup_old_runs(output_folder, domain, keep_after)
    else:
        print(f"Unknown output_type: {output_type}. Must be 'gif' or 'frames'.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate HRRR Smoke Forecast GIF")
    parser.add_argument("domain", nargs="?", default="NC", help="Domain to use (e.g., NC, full, etc.)")
    parser.add_argument("frames", nargs="?", type=int, default=19, help="Number of forecast frames (default 19)")
    parser.add_argument("--output", dest="output_type", choices=["gif", "frames"], default="frames", help="Output type: gif or frames")
    args = parser.parse_args()

    generate_forecast(domain=args.domain, frames=args.frames, output_type=args.output_type)