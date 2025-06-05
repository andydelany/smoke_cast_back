# HRRR Smoke Forecast GIF Generator

Generates animated GIFs from NOAA HRRR smoke forecast data.

## Quick Start

1. **Install Python** and ensure it's in your PATH
2. **Clone this repository** and navigate to the directory
3. **Set up environment:**
   ```powershell
   python -m venv env
   env\Scripts\activate.ps1
   pip install -r requirements.txt
   ```
4. **Run the generator:**
   ```powershell
   python gif_generator.py [domain] [frames]
   ```

## Usage Examples

```powershell
# Generate NC domain forecast (default: 19 frames)
python gif_generator.py

# Generate specific domain with custom frame count
python gif_generator.py full 24
```

## Troubleshooting

- **PowerShell execution policy errors:** Run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
- **Linux/Mac:** Use `source env/bin/activate` instead of `env\Scripts\activate.ps1`