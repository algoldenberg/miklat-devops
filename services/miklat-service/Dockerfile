FROM python:3.12-slim

WORKDIR /app

# Системный непривилегированный пользователь — контейнер не бежит от root
# (пригодится уже в этой фазе и станет обязательным требованием в Фазе 3 / k8s).
RUN useradd --create-home --uid 10001 miklat

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/

USER miklat

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
