FROM ubuntu:18.04
MAINTAINER Evan Sultanik

RUN apt-get -y update

RUN apt-get install -y npm bash-completion sudo

RUN npm install -g ganache-cli truffle

# BEGIN Requirements for Manticore:

RUN DEBIAN_FRONTEND=noninteractive apt-get -y install python3 python3-pip git

RUN apt-get install -y build-essential software-properties-common && \
    add-apt-repository -y ppa:ethereum/ethereum && \
    apt-get update && \
    apt-get install -y solc ethereum

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
RUN apt-get install -y libgmp-dev libbz2-dev libreadline-dev curl libsecp256k1-dev software-properties-common locales-all locales zlib1g-dev
RUN curl -sSL https://get.haskellstack.org/ | sh
USER etheno
RUN git clone https://github.com/trailofbits/echidna.git
WORKDIR /home/etheno/echidna
# Etheno currently requires the dev-etheno branch;
RUN git checkout dev-etheno
RUN stack upgrade
RUN stack setup
RUN stack install
WORKDIR /home/etheno

# END Install Echidna

USER root

# Install Parity
RUN apt-get install -y cmake libudev-dev
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