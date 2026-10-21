FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY crop_advisor ./crop_advisor
COPY server.py .
EXPOSE 8000
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8000", "--timeout", "30", "server:app"]
