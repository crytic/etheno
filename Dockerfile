FROM ubuntu:18.04
MAINTAINER Evan Sultanik

RUN apt-get -y update

RUN apt-get install -y npm bash-completion

RUN npm install -g ganache-cli truffle

# BEGIN Requirements for Manticore:

RUN DEBIAN_FRONTEND=noninteractive apt-get -y install python3 python3-pip git

RUN apt-get install -y build-essential software-properties-common && \
    add-apt-repository -y ppa:ethereum/ethereum && \
    apt-get update && \
    apt-get install -y solc ethereum

RUN useradd -m etheno
USER etheno
WORKDIR /home/etheno
ENV HOME /home/etheno
ENV PATH $PATH:$HOME/.local/bin
ENV LANG C.UTF-8

RUN git clone https://github.com/trailofbits/manticore.git
# Etheno currently requires the dev-account-address-provider-m1 branch;
# We can remove the `git checkout` once https://github.com/trailofbits/manticore/pull/1054 is merged
RUN cd manticore && git checkout dev-account-address-provider-m1 && pip3 install --user .

# END Requirements for Manticore

RUN mkdir -p /home/etheno/etheno/etheno

COPY LICENSE /home/etheno/etheno
COPY setup.py /home/etheno/etheno

COPY etheno/*.py /home/etheno/etheno/etheno/

RUN mkdir -p /home/etheno/examples
COPY examples /home/etheno/examples/

# Comment out the requirement for manticore in setup.py because we already manually installed it
# Once the Etheno branch is merged into a Manticore release, we can get rid of this and
# just install Manticore from pip.
RUN sed -i '/manticore/s/^/#/g' /home/etheno/etheno/setup.py

RUN cd etheno && pip3 install --user .

USER root

RUN chown -R etheno:etheno /home/etheno/

USER etheno

CMD ["/bin/bash"]