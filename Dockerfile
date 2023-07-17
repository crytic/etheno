# syntax=docker/dockerfile:1.3
FROM ubuntu:focal AS python-wheels
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    cmake \
    curl \
    python3-dev \
    python3-pip \
    python3-setuptools

RUN --mount=type=bind,target=/etheno \
    cd /etheno && \
    pip3 install --no-cache-dir --upgrade pip setuptools && \
    pip3 wheel --no-cache-dir -w /wheels \
    .


FROM ubuntu:focal AS ganache
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    gnupg \
    lsb-release
RUN curl -fsSL https://deb.nodesource.com/setup_16.x | bash && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends nodejs
RUN npm install --omit=dev --location=global --prefix /opt/node ganache truffle


FROM ubuntu:focal AS final
LABEL org.opencontainers.image.authors="Evan Sultanik"

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    bash-completion \
    ca-certificates \
    curl \
    gpg-agent \
    libudev-dev \
    locales \
    python3 \
    python3-pip \
    software-properties-common \
    sudo \
&& rm -rf /var/lib/apt/lists/*

# NOTE: solc was removed from the below command since the echidna integration is being removed
# If the solc option is added back, --platform linux-amd64 needs to be added to the `docker build` command for M1 machines
RUN add-apt-repository -y ppa:ethereum/ethereum && \
    apt-get update && apt-get install -y --no-install-recommends \
    ethereum \
&& rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_16.x | bash && \
    apt-get install -y --no-install-recommends nodejs \
&& rm -rf /var/lib/apt/lists/*

COPY --from=ganache /opt/node /usr/local/

# BEGIN Install Etheno
RUN --mount=type=bind,target=/mnt/etheno \
    --mount=type=bind,target=/mnt/wheels,source=/wheels,from=python-wheels \
    cd /mnt/etheno && \
    pip3 install --no-cache-dir --upgrade pip setuptools && \
    pip3 install --no-cache-dir --no-index --find-links /mnt/wheels .

RUN useradd -m -G sudo etheno

# Allow passwordless sudo for etheno
RUN echo 'etheno ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers

USER etheno
ENV HOME=/home/etheno

# Use the DOCKER env variable to set hostname accordingly
ENV DOCKER=1
WORKDIR /home/etheno

# TODO: Need to copy tests and models 
CMD ["/bin/bash"]
