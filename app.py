from flask import Flask, send_file, jsonify
from flask_cors import CORS
import requests
from PIL import Image
import imageio.v2 as imageio  # Use imageio.v2 for compatibility
import io
from datetime import datetime
from bs4 import BeautifulSoup
app = Flask(__name__)
CORS(app)

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

@app.route('/generate-gif')
def generate_gif():
    try:
        runtime = get_latest_runtime()
    except Exception as e:
        return jsonify({"error": f"Failed to fetch latest runtime: {str(e)}"}), 500

    urls = generate_smoke_urls(runtime)

    images = []
    for url in urls:
        try:
            img_response = requests.get(url)
            img_response.raise_for_status()
            img = Image.open(io.BytesIO(img_response.content)).convert("RGB")
            images.append(img)
        except Exception as e:
            print(f"Error fetching image from {url}: {e}")

    if not images:
        return jsonify({"error": "No images found."}), 500

    gif_bytes = io.BytesIO()
    imageio.mimsave(gif_bytes, images, format='GIF', duration=0.5)
    gif_bytes.seek(0)

    return send_file(gif_bytes, mimetype='image/gif', download_name='forecast.gif')

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)