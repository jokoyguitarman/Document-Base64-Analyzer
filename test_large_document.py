#!/usr/bin/env python3
"""
Test Script for Large Document Processing (500+ pages)
Tests the Redis queue system and batch processing capabilities
"""

import requests
import time
import json
import base64
from PIL import Image
import io
import uuid
import os
from dotenv import load_dotenv

load_dotenv()

class LargeDocumentTester:
    def __init__(self, microservice_url=None):
        self.microservice_url = microservice_url or os.getenv('AI_PROCESSING_MICROSERVICE_URL', 'http://localhost:10000')
        self.test_job_id = None
        
    def create_test_images(self, num_pages=500):
        """Create test base64 images for simulation"""
        print(f"Creating {num_pages} test images...")
        
        images = []
        for i in range(num_pages):
            # Create a simple test image with page number
            img = Image.new('RGB', (800, 600), color='white')
            
            # Convert to base64
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            images.append(img_base64)
            
            if (i + 1) % 50 == 0:
                print(f"  Created {i + 1}/{num_pages} images...")
        
        print(f"✅ Created {len(images)} test images")
        return images
    
    def test_health_check(self):
        """Test microservice health"""
        print("🔍 Testing microservice health...")
        
        try:
            response = requests.get(f"{self.microservice_url}/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Microservice healthy: {data.get('celery_workers', 0)} workers active")
                return True
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Health check error: {str(e)}")
            return False
    
    def test_batch_stats(self):
        """Test batch statistics endpoint"""
        print("📊 Testing batch statistics...")
        
        try:
            response = requests.get(f"{self.microservice_url}/batch-stats", timeout=10)
            if response.status_code == 200:
                stats = response.json()
                print(f"✅ Batch stats retrieved:")
                print(f"   Workers: {stats.get('workers', {}).get('total', 0)}")
                print(f"   Active tasks: {stats.get('tasks', {}).get('active', 0)}")
                return True
            else:
                print(f"❌ Batch stats failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Batch stats error: {str(e)}")
            return False
    
    def submit_large_document(self, num_pages=500):
        """Submit a large document for processing"""
        print(f"📤 Submitting large document ({num_pages} pages)...")
        
        # Create test images
        images = self.create_test_images(num_pages)
        
        # Create job data
        self.test_job_id = str(uuid.uuid4())
        
        job_data = {
            'job_id': self.test_job_id,
            'user_id': str(uuid.uuid4()),
            'images_base64': images,
            'num_pages': num_pages,
            'file_type': 'PDF'
        }
        
        try:
            print(f"🚀 Submitting job {self.test_job_id}...")
            response = requests.post(
                f"{self.microservice_url}/process-large-document",
                json=job_data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Job submitted successfully:")
                print(f"   Job ID: {result.get('job_id')}")
                print(f"   Strategy: {result.get('processing_strategy')}")
                print(f"   Estimated batches: {result.get('estimated_batches')}")
                print(f"   Estimated time: {result.get('estimated_completion_minutes')} minutes")
                return True
            else:
                print(f"❌ Job submission failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Job submission error: {str(e)}")
            return False
    
    def monitor_job_progress(self, timeout_minutes=60):
        """Monitor job progress until completion"""
        if not self.test_job_id:
            print("❌ No job ID to monitor")
            return False
        
        print(f"👀 Monitoring job {self.test_job_id}...")
        
        start_time = time.time()
        timeout_seconds = timeout_minutes * 60
        
        while time.time() - start_time < timeout_seconds:
            try:
                response = requests.get(
                    f"{self.microservice_url}/batch-status/{self.test_job_id}",
                    timeout=10
                )
                
                if response.status_code == 200:
                    status = response.json()
                    
                    print(f"📈 Progress: {status.get('progress', 0):.1f}% "
                          f"({status.get('current_page', 0)}/{status.get('total_pages', 0)} pages)")
                    
                    if status.get('status') == 'completed':
                        print(f"✅ Job completed successfully!")
                        print(f"   Processing time: {status.get('processing_time', 0):.1f} seconds")
                        return True
                    elif status.get('status') == 'failed':
                        print(f"❌ Job failed: {status.get('error', 'Unknown error')}")
                        return False
                    
                    # Show batch progress
                    batches = status.get('batches', {})
                    if batches:
                        print(f"   Batches - Completed: {batches.get('completed', 0)}, "
                              f"Active: {batches.get('active', 0)}, "
                              f"Failed: {batches.get('failed', 0)}")
                    
                    # Show time estimate
                    if status.get('estimated_seconds_remaining'):
                        remaining_min = status['estimated_seconds_remaining'] / 60
                        print(f"   Estimated time remaining: {remaining_min:.1f} minutes")
                
                else:
                    print(f"⚠️ Status check failed: {response.status_code}")
                
            except Exception as e:
                print(f"⚠️ Status check error: {str(e)}")
            
            time.sleep(30)  # Check every 30 seconds
        
        print(f"⏰ Monitoring timeout after {timeout_minutes} minutes")
        return False
    
    def test_job_cancellation(self):
        """Test job cancellation functionality"""
        if not self.test_job_id:
            print("❌ No job ID to cancel")
            return False
        
        print(f"🛑 Testing job cancellation for {self.test_job_id}...")
        
        try:
            response = requests.post(
                f"{self.microservice_url}/cancel-job/{self.test_job_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Job cancelled successfully:")
                print(f"   Cancelled tasks: {result.get('cancelled_tasks', 0)}")
                return True
            else:
                print(f"❌ Job cancellation failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Job cancellation error: {str(e)}")
            return False
    
    def run_full_test(self, num_pages=500, monitor=True):
        """Run complete test suite"""
        print(f"🧪 Starting Large Document Processing Test ({num_pages} pages)")
        print("=" * 60)
        
        # Test 1: Health check
        if not self.test_health_check():
            print("❌ Test failed at health check")
            return False
        
        # Test 2: Batch stats
        if not self.test_batch_stats():
            print("❌ Test failed at batch stats")
            return False
        
        # Test 3: Submit large document
        if not self.submit_large_document(num_pages):
            print("❌ Test failed at document submission")
            return False
        
        if monitor:
            # Test 4: Monitor progress
            if not self.monitor_job_progress():
                print("❌ Test failed during monitoring")
                # Try to cancel the job
                self.test_job_cancellation()
                return False
        else:
            print("⏭️ Skipping monitoring (monitor=False)")
            # Test cancellation instead
            time.sleep(10)  # Let job start
            self.test_job_cancellation()
        
        print("✅ All tests completed successfully!")
        return True

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Test large document processing system')
    parser.add_argument('--pages', type=int, default=500, help='Number of pages to test (default: 500)')
    parser.add_argument('--url', type=str, help='Microservice URL (default: from env or localhost)')
    parser.add_argument('--no-monitor', action='store_true', help='Skip monitoring, just test submission')
    parser.add_argument('--quick', action='store_true', help='Quick test with 100 pages')
    
    args = parser.parse_args()
    
    if args.quick:
        args.pages = 100
        args.no_monitor = True
    
    tester = LargeDocumentTester(args.url)
    success = tester.run_full_test(args.pages, monitor=not args.no_monitor)
    
    if success:
        print(f"\n🎉 Test completed successfully!")
        print(f"System can handle {args.pages}-page documents with batch processing")
    else:
        print(f"\n💥 Test failed!")
        print(f"Check system configuration and try again")
    
    return 0 if success else 1

if __name__ == '__main__':
    exit(main())
