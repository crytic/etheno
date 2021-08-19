FROM ubuntu:bionic
MAINTAINER Evan Sultanik

RUN DEBIAN_FRONTEND=noninteractive \
    apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    bash-completion \
    sudo \
    python3 \
    libpython3-dev \
    python3-pip \
    python3-setuptools \
    git \
    build-essential \
    software-properties-common \
    locales-all locales \
    libudev-dev \
    gpg-agent \
&& apt-get clean \
&& rm -rf /var/lib/apt/lists/*

RUN DEBIAN_FRONTEND=noninteractive add-apt-repository -y ppa:ethereum/ethereum && \
    apt-get update && apt-get install -y --no-install-recommends \
    solc \
    ethereum \
&& apt-get clean \
&& rm -rf /var/lib/apt/lists/*

RUN curl -sL https://deb.nodesource.com/setup_12.x | sudo -E bash - && sudo apt-get install -y --no-install-recommends nodejs && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN npm install --production -g ganache-cli truffle && npm --force cache clean

# BEGIN Install Echidna

COPY --from=trailofbits/echidna:latest /root/.local/bin/echidna-test /usr/local/bin/echidna-test

RUN update-locale LANG=en_US.UTF-8 && locale-gen en_US.UTF-8
ENV LANG=en_US.UTF-8 LANGUAGE=en_US:en LC_ALL=en_US.UTF-8

# END Install Echidna

RUN useradd -m etheno
RUN usermod -aG sudo etheno
USER etheno
WORKDIR /home/etheno
USER root
WORKDIR /root

# Install Parity
RUN curl https://get.parity.io -L | bash

# Allow passwordless sudo for etheno
RUN echo 'etheno ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers

USER etheno
ENV HOME=/home/etheno PATH=$PATH:/home/etheno/.local/bin
WORKDIR /home/etheno

COPY --chown=etheno:etheno LICENSE setup.py etheno/
COPY --chown=etheno:etheno etheno/*.py etheno/etheno/
RUN cd etheno && \
    pip3 install --no-cache-dir --user '.[manticore]' && \
    cd .. && \
    rm -rf etheno

COPY --chown=etheno:etheno examples examples/

CMD ["/bin/bash"]
