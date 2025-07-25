import argparse
import io
import json
import os
import shutil
from datetime import datetime, timedelta, timezone

import imageio.v2 as imageio
import pytz
import requests
from bs4 import BeautifulSoup
from PIL import Image


# Generate direct image URLs for forecast frames
def generate_smoke_urls(runtime: str, domain="NC", frames=19):
    base_url = f"https://rapidrefresh.noaa.gov/hrrr/HRRRsmoke/for_web/hrrr_ncep_smoke_jet/{runtime}/{domain}"
    plot_prefix = f"trc1_{domain}_sfc"

    urls = []
    for i in range(frames):
        fcst = f"f{i:03d}"
        url = f"{base_url}/{plot_prefix}_{fcst}.png"
        urls.append(url)
    return urls


# Generate the referer URL for the forecast frame
def generate_referer_url(runtime: str, domain: str, fcst: int):
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
    soup = BeautifulSoup(response.text, "html.parser")
    select = soup.find("select", {"name": "run_time"})
    if not select:
        raise ValueError("Could not find run_time select element")

    selected_option = select.find("option", selected=True)
    if not selected_option:
        raise ValueError("Could not find selected run_time option")

    # Convert format "03 Jun 2025 - 13Z" to "2025060313"
    text = selected_option.text.strip()
    try:
        dt = datetime.strptime(text, "%d %b %Y - %HZ")
        return dt.strftime("%Y%m%d%H")
    except ValueError as e:
        raise ValueError(f"Could not parse run_time option text '{text}': {e}")


def get_latest_48hr_runtime(runtime: str) -> str:
    """
    Given a runtime string (YYYYMMDDHH), return the same runtime if it ends with 00, 06, 12, or 18,
    otherwise return the same date with the most recent lower valid hour.
    """
    valid_hours = [0, 6, 12, 18]
    hour = int(runtime[-2:])
    latest = max(h for h in valid_hours if h <= hour)
    return runtime[:-2] + f"{latest:02d}"


def utc_to_central(utc_dt):
    # Convert naive datetime in UTC to Central Time with daylight savings handled
    utc = pytz.utc
    central = pytz.timezone("US/Central")
    utc_dt = utc.localize(utc_dt)
    central_dt = utc_dt.astimezone(central)
    return central_dt.strftime("%Y-%m-%d %H:%M %Z")


def generate_forecast_metadata(runtime, frames):
    base_dt = datetime.strptime(runtime, "%Y%m%d%H")  # runtime start datetime UTC
    metadata = []
    for i in range(frames):
        frame_time_utc = base_dt + timedelta(hours=i)
        frame_time_central = utc_to_central(frame_time_utc)
        metadata.append(
            {
                "frame_index": i,
                "time_utc": frame_time_utc.strftime("%Y-%m-%d %H:%M UTC"),
                "time_central": frame_time_central,
                "filename": f"frame_{i:03d}.png",
            }
        )
    return metadata


def cleanup_old_frame_folders(base_dir, domain, keep_after_date):
    for folder in os.listdir(base_dir):
        folder_path = os.path.join(base_dir, folder)
        if os.path.isdir(folder_path):
            try:
                folder_datetime = datetime.strptime(folder, f"frames_{domain}_%Y%m%d%H")
                folder_datetime = pytz.utc.localize(folder_datetime)
                keep_after_utc = keep_after_date.astimezone(pytz.utc)
                if folder_datetime < keep_after_utc:
                    print(f"Deleting old folder: {folder}")
                    shutil.rmtree(folder_path)
            except ValueError:
                # Skip folders that don't match the expected naming pattern
                continue


def cleanup_old_gifs(base_dir, domain, keep_after_date):
    for gif in os.listdir(base_dir):
        gif_path = os.path.join(base_dir, gif)
        if os.path.isfile(gif_path):
            try:
                gif_datetime = datetime.strptime(gif, f"forecast_{domain}_%Y%m%d%H.gif")
                gif_datetime = pytz.utc.localize(gif_datetime)
                if gif_datetime < keep_after_date:
                    print(f"Deleting old GIF: {gif}")
                    os.remove(gif_path)
            except ValueError:
                # Skip files that don't match the expected naming pattern
                continue


def create_symlink(source, link_name):
    # Always try to remove existing path (rmdir will handle it gracefully if nothing exists)
    print(f"Ensuring clean path for: {link_name}")
    os.system(f'rmdir /S /Q "{link_name}" 2>nul')

    # Create new junction point
    result = os.system(f'mklink /J "{link_name}" "{source}"')
    if result == 0:
        print(f"Created symlink: {link_name} -> {source}")
    else:
        print(f"Failed to create symlink: {link_name} -> {source}")


# Download images and create a GIF or frames
def fetch_images(domain, frames, runtime):
    """Core function to fetch images from URLs"""
    urls = generate_smoke_urls(runtime, domain=domain, frames=frames)

    # Create a session to maintain cookies and state
    session = requests.Session()

    images = []
    for i, url in enumerate(urls):
        referer = generate_referer_url(runtime, domain=domain, fcst=i)
        headers = {
            "Referer": referer,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
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
        print("No images were downloaded.")
        return None

    return images


def generate_gif(domain, frames, runtime):
    """Generate GIF from fetched images"""
    gif_filename = f"finishedGIFS/forecast_{domain}_{runtime}.gif"

    # Check if output already exists
    if os.path.exists(gif_filename):
        print(f"GIF already exists: {gif_filename}")
        return gif_filename

    images = fetch_images(domain, frames, runtime)
    if images is None:
        return None

    print(f"Saving GIF to {gif_filename}")
    imageio.mimsave(gif_filename, images, format="GIF", duration=1, loop=0)
    print("GIF generation complete.")
    return gif_filename


def generate_frames(domain, frames, runtime):
    """Generate frames from fetched images"""
    frames_folder = f"frames/frames_{domain}_{runtime}"

    # Check if output already exists
    if os.path.exists(frames_folder):
        print(f"Frames folder already exists: {frames_folder}")
        return frames_folder

    images = fetch_images(domain, frames, runtime)
    if images is None:
        return None

    metadata = generate_forecast_metadata(runtime, frames)

    os.makedirs(frames_folder, exist_ok=True)
    for idx, img in enumerate(images):
        img.save(os.path.join(frames_folder, f"frame_{idx:03d}.png"))
    print("Frame saving complete.")

    with open(os.path.join(frames_folder, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    return frames_folder


def generate_forecast(domain="NC", output_type="frames"):
    print("Fetching latest available runtime...")
    runtime = get_latest_runtime()
    print(f"Latest runtime: {runtime}")

    latest_48hr_runtime = get_latest_48hr_runtime(runtime)
    latest_is_48hr = runtime == latest_48hr_runtime
    frames = 49 if latest_is_48hr else 19

    if output_type == "gif":
        generate_gif(domain, frames, runtime)
    elif output_type == "frames":
        frames_folder = generate_frames(domain, frames, runtime)
        latest_link = f"frames/latest_{domain}"
        create_symlink(frames_folder, latest_link)
        latest_48_link = f"frames/latest_{domain}_48hr"
        if latest_is_48hr:
            create_symlink(frames_folder, latest_48_link)
        else:
            frames_48_folder = generate_frames(domain, 49, latest_48hr_runtime)
            create_symlink(frames_48_folder, latest_48_link)
    else:
        print(f"Unknown output_type: {output_type}. Must be 'gif' or 'frames'.")
        return None

    # Clean up old GIFs and frames
    keep_after = datetime.now(timezone.utc) - timedelta(days=1)
    cleanup_old_gifs("finishedGIFS", domain, keep_after)
    cleanup_old_frame_folders("frames", domain, keep_after)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate HRRR Smoke Forecast GIF")
    parser.add_argument(
        "domain", nargs="?", default="NC", help="Domain to use (e.g., NC, full, etc.)"
    )
    parser.add_argument(
        "frames",
        nargs="?",
        type=int,
        default=19,
        help="Number of forecast frames (default 19)",
    )
    parser.add_argument(
        "--output",
        dest="output_type",
        choices=["gif", "frames"],
        default="frames",
        help="Output type: gif or frames",
    )
    parser.add_argument("--runtime", dest="runtime", help="Runtime to use (YYYYMMDDHH)")
    args = parser.parse_args()

    generate_forecast(
        domain=args.domain,
        output_type=args.output_type,
    )
