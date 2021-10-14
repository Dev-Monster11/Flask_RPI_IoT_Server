#mv /var/log/flask.log /var/log/flask.log.bak 2>/dev/null
FLASK_APP=application.py FLASK_ENV=development flask run --host=0.0.0.0 --with-threads
