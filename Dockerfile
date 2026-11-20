FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    autossh \
    sshpass \
    socat \
    expect \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY start.sh .
RUN chmod +x start.sh
CMD ["./start.sh"]
