FROM python:3.11

WORKDIR /new_project

COPY ./app .

RUN pip install -r requirements.txt

EXPOSE 8000

CMD pytest && \
    python manage.py collectstatic --noinput && \
    python manage.py makemigrations && \
    python manage.py migrate --run-syncdb && \
    gunicorn project_orders.wsgi -b 0.0.0.0:8000