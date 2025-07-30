#!/usr/bin/env python3
"""
Celery Worker for AI Processing Microservice
Run this file to start the Celery worker process
"""

import os
from celery_config import celery_app

if __name__ == '__main__':
    # Start the Celery worker
    celery_app.worker_main(['worker', '--loglevel=info']) 