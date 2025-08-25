#!/usr/bin/env python3
"""
Test script to verify Celery system components work together
Run this to test the complete background processing flow
"""

import requests
import json
import time
import base64
from PIL import Image
import io

# Configuration
import os
BASE_URL = os.getenv('TEST_BASE_URL', "https://document-base64-analyzer.onrender.com")  # Set TEST_BASE_URL env var for production
TEST_IMAGE_SIZE = (100, 100)  # Small test image

def create_test_image():
    """Create a simple test image and convert to base64"""
    # Create a simple test image
    img = Image.new('RGB', TEST_IMAGE_SIZE, color='white')
    
    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    return img_base64

def test_health_check():
    """Test the health endpoint"""
    print("🔍 Testing health check...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check passed: {data}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {str(e)}")
        return False

def test_document_processing():
    """Test the complete document processing flow"""
    print("\n📄 Testing document processing...")
    
    # Create test data
    test_image = create_test_image()
    test_data = {
        "job_id": f"test_job_{int(time.time())}",
        "user_id": "test_user_123",
        "images_base64": [test_image],
        "num_pages": 1,
        "file_type": "PDF",
        "fallback_text": ""
    }
    
    try:
        # Submit document for processing
        print("📤 Submitting document...")
        response = requests.post(f"{BASE_URL}/process-document", 
                               json=test_data,
                               headers={'Content-Type': 'application/json'})
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Document submitted: {result}")
            
            task_id = result.get('task_id')
            if task_id:
                print(f"📋 Task ID: {task_id}")
                return task_id
            else:
                print("❌ No task_id returned")
                return None
        else:
            print(f"❌ Document submission failed: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Document submission error: {str(e)}")
        return None

def test_task_status(task_id):
    """Test task status monitoring"""
    print(f"\n📊 Testing task status for: {task_id}")
    
    max_attempts = 30  # Wait up to 5 minutes
    attempt = 0
    
    while attempt < max_attempts:
        try:
            response = requests.get(f"{BASE_URL}/task-status/{task_id}")
            
            if response.status_code == 200:
                status_data = response.json()
                state = status_data.get('state', 'UNKNOWN')
                
                print(f"📈 Status (attempt {attempt + 1}): {state}")
                
                if state == 'SUCCESS':
                    print("✅ Task completed successfully!")
                    print(f"📋 Result: {json.dumps(status_data.get('result', {}), indent=2)}")
                    return True
                elif state == 'FAILURE':
                    print(f"❌ Task failed: {status_data.get('error', 'Unknown error')}")
                    return False
                elif state == 'PROGRESS':
                    progress = status_data.get('progress', 0)
                    current = status_data.get('current', 0)
                    total = status_data.get('total', 0)
                    print(f"🔄 Progress: {progress}% ({current}/{total})")
                
            else:
                print(f"❌ Status check failed: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Status check error: {str(e)}")
        
        attempt += 1
        time.sleep(10)  # Wait 10 seconds between checks
    
    print("⏰ Timeout waiting for task completion")
    return False

def test_fallback_text():
    """Test fallback text processing"""
    print("\n📝 Testing fallback text processing...")
    
    test_data = {
        "job_id": f"test_fallback_{int(time.time())}",
        "user_id": "test_user_123",
        "images_base64": [],
        "num_pages": 1,
        "file_type": "TEXT",
        "fallback_text": "This is a test document for analysis. It contains important information about testing."
    }
    
    try:
        response = requests.post(f"{BASE_URL}/process-document", 
                               json=test_data,
                               headers={'Content-Type': 'application/json'})
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Fallback text processing successful")
            print(f"📋 Result: {json.dumps(result, indent=2)}")
            return True
        else:
            print(f"❌ Fallback text processing failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Fallback text processing error: {str(e)}")
        return False

def main():
    """Run all tests"""
    print("🚀 Starting Celery System Test Suite")
    print("=" * 50)
    
    # Test 1: Health Check
    if not test_health_check():
        print("❌ Health check failed. Stopping tests.")
        return
    
    # Test 2: Fallback Text Processing
    test_fallback_text()
    
    # Test 3: Background Document Processing
    task_id = test_document_processing()
    if task_id:
        test_task_status(task_id)
    
    print("\n" + "=" * 50)
    print("🏁 Test suite completed!")

if __name__ == "__main__":
    main() 