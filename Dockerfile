FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV WINEARCH=win32
ENV WINEPREFIX=/root/.wine
ENV WINEDEBUG=-all
ENV DISPLAY=:99

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

# Init Wine32 prefix and install MT5 during build
RUN Xvfb :99 -screen 0 1024x768x24 & \
    sleep 3 && \
    WINEARCH=win32 WINEPREFIX=/root/.wine wineboot --init && \
    sleep 10 && \
    curl -L -o /tmp/mt5setup.exe https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe && \
    DISPLAY=:99 WINEPREFIX=/root/.wine wine /tmp/mt5setup.exe /auto && \
    sleep 30 && \
    rm -f /tmp/mt5setup.exe && \
    pkill Xvfb || true

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

EXPOSE 8080

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
