#!/usr/bin/env python3

"""
Run script for the Card Counter application
"""

from app import app

if __name__ == "__main__":
    print("Starting Card Counter application...")
    print("Open your browser to http://localhost:5000")
    print("Press Ctrl+C to stop the server")
    print()

    app.run(debug=True, host="0.0.0.0", port=5000)
