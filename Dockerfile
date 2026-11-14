FROM python:3.12-slim

WORKDIR /app

# Створюємо папку data з правами на запис (важливо для Hugging Face!)
RUN mkdir -p /app/data && chmod 777 /app/data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Hugging Face використовує порт 7860
ENV PORT=7860
EXPOSE 7860

CMD ["python", "run.py"]