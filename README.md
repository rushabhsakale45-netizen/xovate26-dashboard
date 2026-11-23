# Rane Materials Shock Response Engine

This is a portable copy of the interactive dashboard. It includes cleaned runtime CSVs and forecast outputs; it does not include the raw source workbooks.

## First-time setup (Windows)

1. Install Python 3.12 and make sure the Python launcher (`py`) is available.
2. Open PowerShell in this unzipped folder.
3. Install the app libraries once: `py -3.12 -m pip install -r requirements.txt`
4. Start the dashboard: double-click `run_dashboard.bat`, or run `powershell -ExecutionPolicy Bypass -File .\run_app.ps1`.
5. The app opens in a browser at `http://127.0.0.1:8501`. If it does not open automatically, visit that address.

The one-time library install needs internet access. After installation, the dashboard reads only this folder and works without live data feeds or an account. Its sliders, presets, forecasts, cost chain, inventory view and action matrix remain interactive on the partner's computer.

## Important limits

The financial baseline is the hackathon handout's modelled FY25 case. Division mixes, suppliers, duty rates, lead times, inventory cover, payload and action economics are editable illustrative assumptions, not verified Rane operating data. Resin is a generic proxy; natural rubber is annual through FY2024–25; freight dates are approximate; FX ends 30 June 2026. Use the tool for the hackathon demonstration, not for purchasing or safety-critical operating decisions.
