FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# No secrets baked in: AI_PROVIDER / AI_API_KEY / AI_MODEL come from the
# deployment environment. Without them the API still runs — every
# suggestion is answered by the rule-based engine (source=rule_based).
ENV APP_ENV=production
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
