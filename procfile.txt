web:python manage.py runserver
web: gunicorn your-app-name.wsgi --log-file -
heroku ps:scale web=1
