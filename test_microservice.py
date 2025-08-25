import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
BASE_URL = "http://localhost:5000"  # Change this to your deployed URL
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

def test_health_check():
    """Test the health check endpoint"""
    print("** Testing Health Check **")
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_process_document():
    """Test the document processing endpoint"""
    print("\n** Testing Document Processing **")
    
    # Test data - you'll need to replace these with actual values
    test_data = {
        "job_id": "test_job_123",
        "user_id": "test_user_456",
        "image_urls": [
            "test_image_1.jpg",  # Replace with actual image URLs from Supabase
            "test_image_2.jpg"
        ],
        "num_pages": 2,
        "file_type": "PDF",
        "fallback_text": "This is a test document for processing."
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/process-document",
            json=test_data,
            headers={'Content-Type': 'application/json'}
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_with_real_data():
    """Test with real data from your Supabase storage"""
    print("\n** Testing with Real Data **")
    
    # You'll need to replace these with actual values from your system
    real_data = {
        "job_id": "real_job_789",
        "user_id": "real_user_101",
        "image_urls": [
            # Add actual image URLs from your Supabase storage
            # Example: "user_uploads/user_101/document_1_page_1.jpg"
        ],
        "num_pages": 1,
        "file_type": "PDF",
        "fallback_text": "Real document content here."
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/process-document",
            json=real_data,
            headers={'Content-Type': 'application/json'}
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

def check_environment():
    """Check if required environment variables are set"""
    print("** Checking Environment Variables **")
    required_vars = ['SUPABASE_URL', 'SUPABASE_SERVICE_ROLE_KEY', 'OPENAI_API_KEY']
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"✓ {var}: Set (length: {len(value)})")
        else:
            print(f"✗ {var}: Not set")
    
    return all(os.getenv(var) for var in required_vars)

if __name__ == "__main__":
    print("=== AI Processing Microservice Test Suite ===\n")
    
    # Check environment
    env_ok = check_environment()
    if not env_ok:
        print("\n⚠️  Warning: Some environment variables are missing!")
        print("Please set SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, and OPENAI_API_KEY")
    
    # Test health check
    health_ok = test_health_check()
    
    if health_ok:
        # Test document processing
        process_ok = test_process_document()
        
        # Uncomment the line below to test with real data
        # real_ok = test_with_real_data()
    
    print("\n=== Test Summary ===")
    print(f"Environment: {'✓' if env_ok else '✗'}")
    print(f"Health Check: {'✓' if health_ok else '✗'}")
    if health_ok:
        print(f"Document Processing: {'✓' if process_ok else '✗'}") 