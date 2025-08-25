#!/usr/bin/env python3
"""
Batch Processing Monitor for Large Document Processing
Provides real-time monitoring and progress tracking for 500+ page documents
"""

import os
import time
import json
from datetime import datetime
from celery_config import celery_app
from celery.result import AsyncResult

class BatchProcessingMonitor:
    """Monitor for batch processing jobs with detailed progress tracking"""
    
    def __init__(self):
        self.app = celery_app
        
    def get_job_progress(self, job_id):
        """Get detailed progress for a document processing job"""
        try:
            # Check if this is a batch processing job
            inspect = self.app.control.inspect()
            active_tasks = inspect.active()
            scheduled_tasks = inspect.scheduled()
            
            job_info = {
                'job_id': job_id,
                'status': 'unknown',
                'progress': 0,
                'current_page': 0,
                'total_pages': 0,
                'batches': {
                    'total': 0,
                    'completed': 0,
                    'active': 0,
                    'failed': 0
                },
                'processing_time': 0,
                'estimated_completion': None,
                'error': None
            }
            
            # Scan all active tasks for this job
            all_tasks = []
            if active_tasks:
                for worker, tasks in active_tasks.items():
                    all_tasks.extend(tasks)
            
            if scheduled_tasks:
                for worker, tasks in scheduled_tasks.items():
                    all_tasks.extend(tasks)
            
            # Find tasks related to this job
            job_tasks = []
            for task in all_tasks:
                if job_id in str(task.get('args', [])) or job_id in str(task.get('kwargs', {})):
                    job_tasks.append(task)
            
            if job_tasks:
                job_info['status'] = 'processing'
                job_info['batches']['active'] = len(job_tasks)
                
                # Calculate progress based on task states
                total_progress = 0
                for task in job_tasks:
                    task_id = task.get('id')
                    if task_id:
                        result = AsyncResult(task_id, app=self.app)
                        if result.state == 'PROGRESS' and result.info:
                            current = result.info.get('current', 0)
                            total = result.info.get('total', 1)
                            if total > 0:
                                total_progress += (current / total) * 100
                
                job_info['progress'] = total_progress / len(job_tasks) if job_tasks else 0
            
            return job_info
            
        except Exception as e:
            return {
                'job_id': job_id,
                'status': 'error',
                'error': str(e),
                'progress': 0
            }
    
    def get_batch_statistics(self):
        """Get overall batch processing statistics"""
        try:
            inspect = self.app.control.inspect()
            stats = inspect.stats()
            active_tasks = inspect.active()
            
            batch_stats = {
                'workers': {
                    'total': len(stats) if stats else 0,
                    'active': 0,
                    'by_queue': {}
                },
                'tasks': {
                    'active': 0,
                    'page_processing': 0,
                    'document_processing': 0
                },
                'system': {
                    'memory_usage': {},
                    'cpu_usage': {},
                    'uptime': {}
                }
            }
            
            # Count active workers and tasks
            if active_tasks:
                for worker, tasks in active_tasks.items():
                    if tasks:
                        batch_stats['workers']['active'] += 1
                        batch_stats['tasks']['active'] += len(tasks)
                        
                        # Count tasks by type
                        for task in tasks:
                            task_name = task.get('name', '')
                            if 'analyze_page' in task_name:
                                batch_stats['tasks']['page_processing'] += 1
                            elif 'process_document_job' in task_name:
                                batch_stats['tasks']['document_processing'] += 1
            
            # Get worker statistics
            if stats:
                for worker, worker_stats in stats.items():
                    pool = worker_stats.get('pool', {})
                    batch_stats['workers']['by_queue'][worker] = {
                        'processes': pool.get('processes', 0),
                        'max_concurrency': pool.get('max-concurrency', 0),
                        'total_tasks': worker_stats.get('total', 0)
                    }
            
            return batch_stats
            
        except Exception as e:
            return {
                'error': str(e),
                'workers': {'total': 0},
                'tasks': {'active': 0}
            }
    
    def estimate_completion_time(self, job_id, pages_remaining):
        """Estimate completion time for sequential document processing"""
        try:
            # Get average processing time per page from recent tasks
            # This is a simplified estimation - in production you'd track historical data
            avg_time_per_page = 30  # seconds (conservative estimate)
            
            # Sequential processing with 1-second delays between pages
            delay_per_page = 1  # seconds
            total_time_per_page = avg_time_per_page + delay_per_page
            
            estimated_seconds = pages_remaining * total_time_per_page
            
            completion_time = datetime.now().timestamp() + estimated_seconds
            
            return {
                'estimated_seconds_remaining': int(estimated_seconds),
                'estimated_completion_timestamp': completion_time,
                'estimated_completion_iso': datetime.fromtimestamp(completion_time).isoformat()
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def cancel_job(self, job_id):
        """Cancel all tasks associated with a job"""
        try:
            inspect = self.app.control.inspect()
            active_tasks = inspect.active()
            
            cancelled_tasks = []
            
            if active_tasks:
                for worker, tasks in active_tasks.items():
                    for task in tasks:
                        if job_id in str(task.get('args', [])) or job_id in str(task.get('kwargs', {})):
                            task_id = task.get('id')
                            if task_id:
                                self.app.control.revoke(task_id, terminate=True)
                                cancelled_tasks.append(task_id)
            
            return {
                'job_id': job_id,
                'cancelled_tasks': len(cancelled_tasks),
                'task_ids': cancelled_tasks
            }
            
        except Exception as e:
            return {
                'job_id': job_id,
                'error': str(e),
                'cancelled_tasks': 0
            }

# CLI interface
if __name__ == '__main__':
    import sys
    
    monitor = BatchProcessingMonitor()
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python batch_monitor.py stats          - Show system statistics")
        print("  python batch_monitor.py job <job_id>   - Show job progress")
        print("  python batch_monitor.py cancel <job_id> - Cancel job")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'stats':
        stats = monitor.get_batch_statistics()
        print(json.dumps(stats, indent=2))
        
    elif command == 'job' and len(sys.argv) > 2:
        job_id = sys.argv[2]
        progress = monitor.get_job_progress(job_id)
        print(json.dumps(progress, indent=2))
        
    elif command == 'cancel' and len(sys.argv) > 2:
        job_id = sys.argv[2]
        result = monitor.cancel_job(job_id)
        print(json.dumps(result, indent=2))
        
    else:
        print("Invalid command or missing arguments")
        sys.exit(1)
