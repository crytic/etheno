FROM ubuntu:18.04
MAINTAINER Evan Sultanik

RUN apt-get update && apt-get install -y --no-install-recommends \
    npm \
    ca-certificates \
    bash-completion \
    sudo \
&& rm -rf /var/lib/apt/lists/*

RUN npm install --production -g ganache-cli truffle && npm cache clean

# BEGIN Requirements for Manticore:

RUN DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    libpython3-dev \
    python3-pip \
    git \
    build-essential \
    software-properties-common \
&& rm -rf /var/lib/apt/lists/*

RUN add-apt-repository -y ppa:ethereum/ethereum && \
    apt-get update && \
    apt-get install -y --no-install-recommends solc ethereum \
&& rm -rf /var/lib/apt/lists/*

# END Requirements for Manticore

RUN useradd -m etheno
RUN usermod -aG sudo etheno
USER etheno
WORKDIR /home/etheno
ENV HOME /home/etheno
ENV PATH $PATH:$HOME/.local/bin
ENV LANG C.UTF-8


# BEGIN Install Echidna

USER root
WORKDIR /root
RUN apt-get update && apt-get install -y --no-install-recommends \
    cmake curl wget libgmp-dev libssl1.0-dev libbz2-dev libreadline-dev \
    software-properties-common locales-all locales libsecp256k1-dev \
    python3-setuptools \
&& rm -rf /var/lib/apt/lists/*
COPY docker/install-libff.sh .
RUN ./install-libff.sh && rm ./install-libff.sh
RUN apt-get update && \
    curl -sSL https://get.haskellstack.org/ | sh && \
    rm -rf /var/lib/apt/lists/*

USER etheno
WORKDIR /home/etheno
RUN git clone https://github.com/trailofbits/echidna.git && \
    cd echidna && \
    stack upgrade && \
    stack setup && \
    stack install --extra-include-dirs=/usr/local/include --extra-lib-dirs=/usr/local/lib && \
    stack purge && \
    cd .. && \
    rm -rf .stack echidna

# END Install Echidna

USER root
WORKDIR /root

# Install Parity
RUN apt-get update && \
    apt-get install -y --no-install-recommends libudev-dev && \
    rm -rf /var/lib/apt/lists/*
RUN curl https://get.parity.io -L | bash

# Allow passwordless sudo for etheno
RUN echo 'etheno ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers

USER etheno
WORKDIR /home/etheno

COPY --chown=etheno:etheno LICENSE setup.py etheno/
COPY --chown=etheno:etheno etheno/*.py etheno/etheno/
RUN cd etheno && \
    pip3 install --no-cache-dir --user '.[manticore]' && \
    cd .. && \
    rm -rf etheno

COPY --chown=etheno:etheno examples examples/

CMD ["/bin/bash"]
