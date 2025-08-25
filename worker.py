#!/usr/bin/env python3
"""
Celery Worker for AI Processing Microservice
Optimized for high-volume document processing (500+ pages)
Run this file to start the Celery worker process
"""

import os
import sys
from celery_config import celery_app
import tasks  # Import tasks to register them with Celery

def start_worker():
    """Start Celery worker with optimized configuration for large documents"""
    
    # Get worker configuration from environment
    concurrency = int(os.getenv('CELERY_CONCURRENCY', '4'))  # 4 concurrent workers by default
    queue_names = os.getenv('CELERY_QUEUES', 'default,page_processing,document_processing,audio_generation')
    log_level = os.getenv('CELERY_LOG_LEVEL', 'info')
    
    print(f"Starting Celery worker with {concurrency} concurrent processes")
    print(f"Monitoring queues: {queue_names}")
    print(f"Log level: {log_level}")
    
    # Worker arguments optimized for high-volume processing
    worker_args = [
        'worker',
        f'--loglevel={log_level}',
        f'--concurrency={concurrency}',
        f'--queues={queue_names}',
        '--pool=prefork',  # Use prefork pool for CPU-intensive tasks
        '--optimization=fair',  # Fair task distribution
        '--prefetch-multiplier=1',  # Process one task at a time to avoid overwhelming OpenAI
        '--max-tasks-per-child=100',  # Restart workers after 100 tasks to prevent memory leaks
        '--time-limit=10800',  # 3 hour hard timeout for large documents
        '--soft-time-limit=10500',  # 2 hour 55 minute soft timeout
        '--without-gossip',  # Disable gossip for better performance
        '--without-mingle',  # Disable mingle for faster startup
        '--without-heartbeat',  # Disable heartbeat for performance
    ]
    
    # Add autoscaling if specified
    if os.getenv('CELERY_AUTOSCALE'):
        max_workers = os.getenv('CELERY_AUTOSCALE_MAX', '8')
        min_workers = os.getenv('CELERY_AUTOSCALE_MIN', '2')
        worker_args.extend([f'--autoscale={max_workers},{min_workers}'])
        print(f"Autoscaling enabled: {min_workers}-{max_workers} workers")
    
    # Start the worker
    celery_app.worker_main(worker_args)

def start_monitor():
    """Start Celery monitor for tracking worker performance"""
    print("Starting Celery monitor...")
    celery_app.control.inspect().stats()

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'monitor':
        start_monitor()
    else:
        start_worker() 