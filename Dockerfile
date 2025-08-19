FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN mkdir -p /data
EXPOSE 8000
ENV DB_URL=sqlite:////data/app.db
CMD ["uvicorn","app.main:api","--host","0.0.0.0","--port","8000"]
