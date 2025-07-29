from flask import Flask, request, jsonify
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'service': 'ai-processing-microservice'})

@app.route('/test', methods=['GET'])
def test_endpoint():
    return jsonify({'message': 'Test endpoint working', 'cors': 'enabled'})

@app.route('/process-document', methods=['POST'])
def process_document():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        # For now, just return a simple response
        return jsonify({
            'status': 'success',
            'message': 'Document processing endpoint reached',
            'received_data': {
                'job_id': data.get('job_id'),
                'user_id': data.get('user_id'),
                'num_pages': data.get('num_pages'),
                'file_type': data.get('file_type')
            }
        })
        
    except Exception as e:
        return jsonify({'error': f'Processing failed: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 10000))) 
