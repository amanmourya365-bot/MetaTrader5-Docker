FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV WINEARCH=win32
ENV WINEPREFIX=/root/.wine
ENV WINEDEBUG=-all

# Install deps + Wine
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip wget curl gnupg2 ca-certificates \
        xvfb x11vnc openbox novnc websockify \
        net-tools iproute2 supervisor procps \
    && mkdir -pm755 /etc/apt/keyrings \
    && wget -O /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key \
    && wget -NP /etc/apt/sources.list.d/ https://dl.winehq.org/wine-builds/debian/dists/bookworm/winehq-bookworm.sources \
    && dpkg --add-architecture i386 \
    && apt-get update \
    && apt-get install --install-recommends -y winehq-stable \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install MT5 during build with verification
RUN Xvfb :99 -screen 0 1024x768x24 & \
    export DISPLAY=:99 && \
    sleep 3 && \
    echo "=== Initializing Wine ===" && \
    WINEARCH=win32 WINEPREFIX=/root/.wine wineboot --init && \
    sleep 10 && \
    echo "=== Downloading MT5 ===" && \
    curl -L -o /tmp/mt5setup.exe https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe && \
    ls -la /tmp/mt5setup.exe && \
    echo "=== Installing MT5 ===" && \
    DISPLAY=:99 WINEPREFIX=/root/.wine wine /tmp/mt5setup.exe /auto && \
    echo "=== Waiting for MT5 to finish ===" && \
    sleep 120 && \
    echo "=== Verifying MT5 installation ===" && \
    find /root/.wine -name "terminal64.exe" 2>/dev/null && \
    ls "/root/.wine/drive_c/Program Files/" && \
    rm -f /tmp/mt5setup.exe && \
    pkill Xvfb || true

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

EXPOSE 8080

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
