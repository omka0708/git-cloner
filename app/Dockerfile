FROM python:3.10.4
VOLUME ["/repos"]
WORKDIR .
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt
COPY . .