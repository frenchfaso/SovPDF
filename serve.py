#! /usr/bin/env python

import http.server
import socketserver
import os

class CORSHTTPHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Required security headers for PyScript
        self.send_header('Cross-Origin-Opener-Policy', 'same-origin')
        self.send_header('Cross-Origin-Embedder-Policy', 'require-corp')
        self.send_header('Cross-Origin-Resource-Policy', 'cross-origin')
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

if __name__ == "__main__":
    port = 8000
    os.chdir("./src/")
    # Using "localhost" instead of empty string or "0.0.0.0" ensures PyScript works properly
    with socketserver.TCPServer(("localhost", port), CORSHTTPHandler) as httpd:
        print(f"Serving HTTP on localhost port {port} (http://localhost:{port}/)...")
        httpd.serve_forever()

