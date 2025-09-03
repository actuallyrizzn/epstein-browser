#!/usr/bin/env python3
"""
Startup script for the Epstein Documents OCR Web Application

Copyright (C) 2025 Epstein Documents Analysis Team

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import sys
import os
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from web_app import app

if __name__ == '__main__':
    print("🚀 Starting Epstein Documents OCR Web Application...")
    print("📊 Dashboard: http://localhost:8080")
    print("🔍 Search: http://localhost:8080/search")
    print("📁 Browse: http://localhost:8080/browse")
    print("❤️  Health: http://localhost:8080/api/health")
    print("\nPress Ctrl+C to stop the server")
    
    # Run the Flask app
    app.run(
        host='0.0.0.0',  # Allow external connections
        port=8080,
        debug=True,      # Enable debug mode for development
        threaded=True    # Enable threading for better performance
    )
