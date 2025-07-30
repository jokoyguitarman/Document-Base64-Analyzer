web: gunicorn main:app --bind 0.0.0.0:$PORT --timeout 30 --workers 1 --worker-class sync
worker: python worker.py
