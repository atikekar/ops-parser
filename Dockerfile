FROM python:3.13-slim

RUN apt-get update && apt-get install -y poppler-utils

WORKDIR /app
COPY . /app

RUN pip install -r requirements.txt

EXPOSE 8501

CMD ["streamlit", "run", "parser.py"]