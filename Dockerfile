# syntax=docker/dockerfile:1.3
FROM ubuntu:focal AS python-wheels
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    python3-dev \
    python3-pip \
    python3-setuptools
RUN --mount=type=bind,target=/etheno \
    cd /etheno && \
    pip3 wheel --no-cache-dir -w /wheels '.[manticore]'


FROM ubuntu:focal AS final
LABEL org.opencontainers.image.authors="Evan Sultanik"

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    bash-completion \
    sudo \
    python3 \
    software-properties-common \
    locales-all locales \
    libudev-dev \
    gpg-agent \
&& rm -rf /var/lib/apt/lists/*

RUN add-apt-repository -y ppa:ethereum/ethereum && \
    apt-get update && apt-get install -y --no-install-recommends \
    solc \
    ethereum \
&& rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_16.x | sudo -E bash - && \
    sudo apt-get install -y --no-install-recommends nodejs \
&& rm -rf /var/lib/apt/lists/*

RUN npm install --production -g ganache-cli truffle && npm --force cache clean

# BEGIN Install Echidna

COPY --from=trailofbits/echidna:latest /root/.local/bin/echidna-test /usr/local/bin/echidna-test

RUN update-locale LANG=en_US.UTF-8 && locale-gen en_US.UTF-8
ENV LANG=en_US.UTF-8 LANGUAGE=en_US:en LC_ALL=en_US.UTF-8

# END Install Echidna

# BEGIN Install Etheno
RUN --mount=type=bind,target=/etheno \
    --mount=type=bind,target=/wheels,source=/wheels,from=python-wheels \
    cd /etheno && \
    pip3 install --no-cache-dir --no-index --find-links /wheels '.[manticore]'

RUN useradd -m -G sudo etheno

# Allow passwordless sudo for etheno
RUN echo 'etheno ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers

USER etheno
ENV HOME=/home/etheno
WORKDIR /home/etheno

COPY --chown=etheno:etheno examples examples/

CMD ["/bin/bash"]
