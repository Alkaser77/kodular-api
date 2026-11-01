FROM python:3.10

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Hugging Face لازم المنفذ 7860
ENV PORT=7860
EXPOSE 7860

CMD ["python", "app.py"]
