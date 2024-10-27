FROM archlinux:latest

# Initialize pacaman keyring
RUN pacman-key --init && pacman-key --populate

RUN pacman --sync --refresh --noconfirm python-setproctitle python-yaml git devtools python-requests

WORKDIR /work
# COPY . .

# CMD ["./gen-deps.sh"]