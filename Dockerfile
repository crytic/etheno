FROM ubuntu:18.04
MAINTAINER Evan Sultanik

RUN apt-get update && apt-get install -y \
    npm \
    bash-completion \
    sudo \
&& rm -rf /var/lib/apt/lists/*

RUN npm install -g ganache-cli truffle && npm cache clean

# BEGIN Requirements for Manticore:

RUN DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    git \
    build-essential \
    software-properties-common \
&& rm -rf /var/lib/apt/lists/*

RUN add-apt-repository -y ppa:ethereum/ethereum && \
    apt-get update && \
    apt-get install -y solc ethereum \
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
RUN apt-get update && apt-get install -y \
    cmake curl wget libgmp-dev libssl-dev libbz2-dev libreadline-dev \
    software-properties-common locales-all locales libsecp256k1-dev \
    python3-setuptools \
&& rm -rf /var/lib/apt/lists/*
COPY docker/install-libff.sh .
RUN ./install-libff.sh && rm ./install-libff.sh
RUN apt-get update && \
    curl -sSL https://get.haskellstack.org/ | sh && \
    rm -rf /var/lib/apt/lists/*

USER etheno
RUN git clone https://github.com/trailofbits/echidna.git
WORKDIR /home/etheno/echidna
RUN stack upgrade && stack setup && stack install --extra-include-dirs=/usr/local/include --extra-lib-dirs=/usr/local/lib
WORKDIR /home/etheno

# END Install Echidna

USER root

# Install Parity
RUN apt-get update && \
    apt-get install -y libudev-dev && \
    rm -rf /var/lib/apt/lists/*
RUN curl https://get.parity.io -L | bash

# Allow passwordless sudo for etheno
RUN echo 'etheno ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers

RUN chown -R etheno:etheno /home/etheno/

USER etheno

RUN mkdir -p /home/etheno/etheno/etheno

COPY LICENSE /home/etheno/etheno
COPY setup.py /home/etheno/etheno

COPY etheno/*.py /home/etheno/etheno/etheno/

RUN mkdir -p /home/etheno/examples
COPY examples /home/etheno/examples/

RUN cd etheno && pip3 install --user '.[manticore]'

USER root

RUN chown -R etheno:etheno /home/etheno/etheno
RUN chown -R etheno:etheno /home/etheno/examples

USER etheno

CMD ["/bin/bash"]