FROM python:3.12-slim
WORKDIR /app
COPY server.py manage.py /app/
COPY public /app/public
RUN useradd --create-home app && mkdir -p /app/data && chown -R app:app /app
USER app
ENV HOST=0.0.0.0 PORT=8000
EXPOSE 8000
CMD ["python", "server.py"]
