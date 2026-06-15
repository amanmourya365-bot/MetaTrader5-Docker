FROM debian:bookworm-slim

ENV TITLE=Metatrader5
ENV WINEPREFIX=/root/.wine
ENV WINEDEBUG=-all
ENV DISPLAY=:1
ENV DEBIAN_FRONTEND=noninteractive

# Install system deps + Wine + VNC
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 python3-pip wget curl gnupg2 \
        software-properties-common ca-certificates \
        xvfb x11vnc openbox novnc websockify \
        xterm net-tools iproute2 supervisor procps \
    && mkdir -pm755 /etc/apt/keyrings \
    && wget -O /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key \
    && wget -NP /etc/apt/sources.list.d/ https://dl.winehq.org/wine-builds/debian/dists/bookworm/winehq-bookworm.sources \
    && dpkg --add-architecture i386 \
    && apt-get update \
    && apt-get install --install-recommends -y winehq-stable \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install MT5 during build inside Xvfb
RUN Xvfb :99 -screen 0 1024x768x24 & \
    export DISPLAY=:99 && \
    sleep 3 && \
    wineboot --init && \
    sleep 5 && \
    curl -L -o /tmp/mt5setup.exe https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe && \
    wine /tmp/mt5setup.exe /auto && \
    sleep 30 && \
    rm -f /tmp/mt5setup.exe && \
    pkill Xvfb || true

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY ./Metatrader/start.sh /start.sh
RUN chmod +x /start.sh

EXPOSE 8080

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
