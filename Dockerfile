FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --no-deps pykrx==1.2.4 && \
    pip install --no-cache-dir $(grep -v '^pykrx' requirements.txt)

COPY . .

EXPOSE 8080

CMD ["gunicorn", "-c", "gunicorn.conf.py", "app:create_app()"]
