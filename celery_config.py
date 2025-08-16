import os
from celery import Celery
from kombu import Queue
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Celery
celery_app = Celery('ai_processing')

# High-volume document processing configuration
celery_app.conf.update(
    # Redis Configuration
    broker_url=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    result_backend=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    
    # Serialization
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    
    # Timezone
    timezone='UTC',
    enable_utc=True,
    
    # Task tracking
    task_track_started=True,
    
    # Timeout settings optimized for large documents
    task_time_limit=1800,  # 30 minutes for large documents
    task_soft_time_limit=1680,  # 28 minutes soft limit
    
    # Worker settings optimized for parallel processing
    worker_prefetch_multiplier=4,  # Allow workers to prefetch more tasks
    task_acks_late=True,  # Acknowledge tasks after completion
    worker_max_tasks_per_child=100,  # Restart workers more frequently to prevent memory leaks
    
    # Connection settings
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    
    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour
    result_persistent=True,  # Persist results to Redis
    
    # Routing for different queue priorities
    task_routes={
        'tasks.analyze_page': {'queue': 'page_processing'},
        'tasks.process_document_job': {'queue': 'document_orchestration'},
        'tasks.process_document_batch': {'queue': 'batch_processing'},
        'tasks.generate_audio_job': {'queue': 'audio_generation'},
        'tasks.generate_reading_audio_job': {'queue': 'audio_generation'},
    },
    
    # Define multiple queues for different types of work
    task_default_queue='default',
    task_queues=(
        Queue('default', routing_key='default'),
        Queue('page_processing', routing_key='page_processing'),
        Queue('document_orchestration', routing_key='document_orchestration'),
        Queue('batch_processing', routing_key='batch_processing'),
        Queue('audio_generation', routing_key='audio_generation'),
    ),
    
    # Enable task batching for efficiency
    task_always_eager=False,  # Never run tasks synchronously
    task_eager_propagates=False,
    
    # Include the tasks module
    include=['tasks'],
    
    # Redis connection pool settings for high concurrency
    broker_transport_options={
        'master_name': 'mymaster',
        'visibility_timeout': 3600,
        'retry_on_timeout': True,
        'connection_pool_options': {
            'max_connections': 50,  # Support more concurrent connections
        }
    },
    
    # Memory and performance optimizations
    worker_disable_rate_limits=True,  # Disable rate limiting for maximum throughput
    task_compression='gzip',  # Compress task payloads
    result_compression='gzip',  # Compress results
) 