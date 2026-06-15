FROM debian:bookworm-slim

ARG BUILD_DATE
ARG VERSION
LABEL build_version="Metatrader Docker:- ${VERSION} Build-date:- ${BUILD_DATE}"
LABEL maintainer="gmartin"

ENV TITLE=Metatrader5
ENV WINEPREFIX=/config/.wine
ENV WINEDEBUG=-all
ENV DISPLAY=:1
ENV VNC_PORT=3000
ENV RESOLUTION=1280x800
ENV PUID=1000
ENV PGID=1000

RUN mkdir -p /config/.wine

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-venv \
        wget \
        curl \
        gnupg2 \
        software-properties-common \
        ca-certificates \
        xvfb \
        x11vnc \
        openbox \
        novnc \
        websockify \
        xterm \
        net-tools \
        iproute2 \
        supervisor \
    && mkdir -pm755 /etc/apt/keyrings \
    && wget -O /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key \
    && wget -NP /etc/apt/sources.list.d/ https://dl.winehq.org/wine-builds/debian/dists/bookworm/winehq-bookworm.sources \
    && dpkg --add-architecture i386 \
    && apt-get update \
    && apt-get install --install-recommends -y winehq-stable \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* /etc/apt/keyrings/winehq-archive.key

COPY ./Metatrader /Metatrader
RUN chmod +x /Metatrader/start.sh

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

EXPOSE 3000 8001

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
