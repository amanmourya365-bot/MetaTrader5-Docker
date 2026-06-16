FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV WINEPREFIX=/root/.wine
ENV WINEDEBUG=-all
ENV DISPLAY=:99

# Install Wine from Ubuntu repos (more stable than WineHQ on builders)
RUN apt-get update && apt-get install -y \
        wine wine64 wine32 \
        python3 python3-pip curl wget \
        xvfb x11vnc openbox novnc websockify \
        net-tools iproute2 supervisor procps \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install MT5 during build
RUN Xvfb :99 -screen 0 1024x768x24 & \
    sleep 3 && \
    echo "=== Init Wine ===" && \
    DISPLAY=:99 wineboot --init && \
    sleep 15 && \
    echo "=== Download MT5 ===" && \
    curl -L -o /tmp/mt5setup.exe "https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe" && \
    echo "=== Install MT5 ===" && \
    DISPLAY=:99 wine /tmp/mt5setup.exe /auto && \
    sleep 120 && \
    echo "=== Verify ===" && \
    find /root/.wine -name "terminal64.exe" 2>/dev/null && \
    rm -f /tmp/mt5setup.exe && \
    pkill Xvfb || true

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

EXPOSE 8080

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
