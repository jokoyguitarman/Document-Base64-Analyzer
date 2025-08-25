web: gunicorn main:app --bind 0.0.0.0:$PORT --timeout 120 --workers 2 --worker-class sync --max-requests 1000 --max-requests-jitter 100
worker: python worker.py
page_worker: CELERY_QUEUES=page_processing,batch_processing CELERY_CONCURRENCY=6 python worker.py
audio_worker: CELERY_QUEUES=audio_generation CELERY_CONCURRENCY=2 python worker.py
orchestrator: CELERY_QUEUES=document_orchestration CELERY_CONCURRENCY=2 python worker.py
