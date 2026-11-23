$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$env:PYTHONPATH = "$projectRoot\src"
$env:STREAMLIT_BROWSER_GATHER_USAGE_STATS = "false"
$env:STREAMLIT_CONFIG_DIR = "$projectRoot\app\.streamlit"
python -m streamlit run "$projectRoot\app\app.py" --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false
