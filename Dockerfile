FROM python:3.11-slim
RUN apt-get update && apt-get install -y autossh socat sshpass curl
WORKDIR /app
COPY start.sh .
RUN chmod +x start.sh
CMD ["./start.sh"]
