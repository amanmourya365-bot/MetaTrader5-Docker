#!/bin/bash

mkdir -p /config/.wine/drive_c

mt5file='/config/.wine/drive_c/Program Files/MetaTrader 5/terminal64.exe'
WINEPREFIX='/config/.wine'
WINEDEBUG='-all'
wine_executable="wine"
metatrader_version="5.0.36"
mt5server_port="8001"
MT5_CMD_OPTIONS="${MT5_CMD_OPTIONS:-}"
mono_url="https://dl.winehq.org/wine/wine-mono/10.3.0/wine-mono-10.3.0-x86.msi"
python_url="https://www.python.org/ftp/python/3.9.13/python-3.9.13.exe"
mt5setup_url="https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe"

show_message() { echo "[MT5] $1"; }

sleep 3

if [ ! -f "/config/.wine/system.reg" ]; then
    show_message "Initializing Wine prefix..."
    wineboot --init 2>/dev/null
    sleep 5
fi

if [ ! -d "/config/.wine/drive_c/windows/mono" ]; then
    show_message "[1/7] Installing Mono..."
    curl -L -o /tmp/mono.msi $mono_url
    WINEDLLOVERRIDES=mscoree=d $wine_executable msiexec /i /tmp/mono.msi /qn
    rm -f /tmp/mono.msi
    show_message "[1/7] Mono installed."
else
    show_message "[1/7] Mono already installed."
fi

if [ -e "$mt5file" ]; then
    show_message "[2/7] MT5 already installed."
else
    show_message "[2/7] Downloading MT5..."
    $wine_executable reg add "HKEY_CURRENT_USER\\Software\\Wine" /v Version /t REG_SZ /d "win10" /f
    curl -L -o /tmp/mt5setup.exe $mt5setup_url
    show_message "[3/7] Installing MT5..."
    $wine_executable "/tmp/mt5setup.exe" "/auto" &
    wait
    rm -f /tmp/mt5setup.exe
fi

if [ -e "$mt5file" ]; then
    show_message "[4/7] Starting MT5..."
    $wine_executable "$mt5file" $MT5_CMD_OPTIONS &
else
    show_message "[4/7] MT5 not installed. Check logs."
fi

if ! $wine_executable python --version 2>/dev/null; then
    show_message "[5/7] Installing Python in Wine..."
    curl -L $python_url -o /tmp/python-installer.exe
    $wine_executable /tmp/python-installer.exe /quiet InstallAllUsers=1 PrependPath=1
    rm -f /tmp/python-installer.exe
    show_message "[5/7] Python installed."
fi

show_message "[6/7] Installing Python libraries..."
$wine_executable python -m pip install --upgrade --no-cache-dir pip 2>/dev/null
$wine_executable python -m pip install --no-cache-dir MetaTrader5==$metatrader_version 2>/dev/null
$wine_executable python -m pip install --no-cache-dir "mt5linux>=0.1.9" python-dateutil 2>/dev/null
pip install --break-system-packages --no-cache-dir --no-deps mt5linux 2>/dev/null
pip install --break-system-packages --no-cache-dir rpyc plumbum numpy pyxdg 2>/dev/null

show_message "[7/7] Starting mt5linux server..."
python3 -m mt5linux --host 0.0.0.0 -p $mt5server_port -w $wine_executable python.exe &

sleep 5
if ss -tuln | grep ":$mt5server_port" > /dev/null; then
    show_message "[7/7] mt5linux server running on port $mt5server_port"
else
    show_message "[7/7] mt5linux server failed to start"
fi

tail -f /dev/null
