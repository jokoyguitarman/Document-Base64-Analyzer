#!/usr/bin/env python3
"""
Simple HTTP server to serve the test page locally
"""

import http.server
import socketserver
import webbrowser
import os
from pathlib import Path

PORT = 8080

class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Add CORS headers to allow cross-origin requests
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

def main():
    # Change to the directory containing this script
    os.chdir(Path(__file__).parent)
    
    # Create server
    with socketserver.TCPServer(("", PORT), MyHTTPRequestHandler) as httpd:
        print(f"🚀 Test server running at http://localhost:{PORT}")
        print(f"📄 Test page available at http://localhost:{PORT}/test_page.html")
        print("🌐 Press Ctrl+C to stop the server")
        
        # Open the test page in the default browser
        try:
            webbrowser.open(f'http://localhost:{PORT}/test_page.html')
        except:
            print("Could not open browser automatically. Please open manually.")
        
        # Start the server
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 Server stopped by user")
            httpd.shutdown()

if __name__ == "__main__":
    main() 