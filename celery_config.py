import os
from celery import Celery
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Celery
celery_app = Celery('ai_processing')

# Celery configuration
celery_app.conf.update(
    broker_url=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    result_backend=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=900,  # 15 minutes
    task_soft_time_limit=840,  # 14 minutes
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=1000,
    broker_connection_retry_on_startup=True,
    include=['tasks']  # Include the tasks module
) 