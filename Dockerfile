FROM debian:bookworm-slim

ARG UID=1000
ARG GID=1000

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        build-essential \
        make \
        gcc-riscv64-unknown-elf \
        binutils-riscv64-unknown-elf \
        picolibc-riscv64-unknown-elf \
        git \
        ca-certificates \
        libc-bin \
    && rm -rf /var/lib/apt/lists/*

RUN (getent group ${GID} > /dev/null || groupadd -g ${GID} dev) \
    && useradd -m -u ${UID} -g ${GID} -s /bin/bash dev
USER dev
WORKDIR /work

CMD ["bash"]
