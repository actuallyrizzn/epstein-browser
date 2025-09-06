#!/usr/bin/env python3
"""
Epstein Documents Browser

Simple Archive.org-style document browser for congressional records.
Uses the SQLite database created by index_images.py.

Copyright (C) 2025 Epstein Documents OCR Project

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import sqlite3
import os
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, abort
from PIL import Image
import io
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration from environment variables
DATA_DIR = Path(os.environ.get('DATA_DIR', 'data'))
DB_PATH = os.environ.get('DATABASE_PATH', 'images.db')

# Environment detection
IS_PRODUCTION = os.environ.get('FLASK_ENV') == 'production'

# Initialize Flask app
app = Flask(__name__)

# Environment-based configuration
if IS_PRODUCTION:
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'prod-secret-key-change-me')
    app.config['DEBUG'] = os.environ.get('DEBUG', 'False').lower() == 'true'
    app.config['TESTING'] = os.environ.get('TESTING', 'False').lower() == 'true'
    HOST = os.environ.get('HOST', '127.0.0.1')  # localhost only for nginx proxy
    PORT = int(os.environ.get('PORT', '8080'))
    DEBUG_MODE = app.config['DEBUG']
    ENV_NAME = "Production"
else:
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
    app.config['DEBUG'] = os.environ.get('DEBUG', 'True').lower() == 'true'
    app.config['TESTING'] = os.environ.get('TESTING', 'False').lower() == 'true'
    HOST = os.environ.get('HOST', '0.0.0.0')  # accessible from any IP
    PORT = int(os.environ.get('PORT', '8080'))
    DEBUG_MODE = app.config['DEBUG']
    ENV_NAME = "Development"


def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_image_by_id(image_id):
    """Get image by ID"""
    conn = get_db_connection()
    image = conn.execute(
        'SELECT * FROM images WHERE id = ?', (image_id,)
    ).fetchone()
    conn.close()
    return image


def get_image_by_path(file_path):
    """Get image by file path"""
    conn = get_db_connection()
    image = conn.execute(
        'SELECT * FROM images WHERE file_path = ?', (file_path,)
    ).fetchone()
    conn.close()
    return image


def get_total_images():
    """Get total number of images"""
    conn = get_db_connection()
    total = conn.execute('SELECT COUNT(*) FROM images').fetchone()[0]
    conn.close()
    return total


def get_ocr_text(file_path):
    """Get OCR text for an image"""
    # Convert backslashes to forward slashes for cross-platform compatibility
    file_path = file_path.replace('\\', '/')
    ocr_file = DATA_DIR / file_path.replace(file_path.split('.')[-1], 'txt')
    if ocr_file.exists():
        try:
            return ocr_file.read_text(encoding='utf-8')
        except:
            return None
    return None


@app.route('/')
def index():
    """Homepage - show first image"""
    total_images = get_total_images()
    if total_images == 0:
        return render_template('index.html', total_images=0)
    
    # Get first available image ID
    conn = get_db_connection()
    first_id = conn.execute('SELECT MIN(id) FROM images').fetchone()[0]
    conn.close()
    
    # Get first image
    first_image = get_image_by_id(first_id)
    return render_template('index.html', 
                         total_images=total_images,
                         first_image=first_image)


@app.route('/view/<int:image_id>')
def view_image(image_id):
    """View a specific image"""
    image = get_image_by_id(image_id)
    if not image:
        abort(404)
    
    total_images = get_total_images()
    
    # Get previous and next image IDs
    prev_id = image_id - 1 if image_id > 1 else None
    next_id = image_id + 1 if image_id < total_images else None
    
    # Get OCR text if available
    ocr_text = None
    if image['has_ocr_text']:
        ocr_text = get_ocr_text(image['file_path'])
    
    # Calculate progress
    progress_percent = (image_id / total_images * 100) if total_images > 0 else 0
    
    return render_template('viewer.html',
                         image=image,
                         image_id=image_id,
                         total_images=total_images,
                         prev_id=prev_id,
                         next_id=next_id,
                         ocr_text=ocr_text,
                         progress_percent=progress_percent)


@app.route('/image/<path:file_path>')
def serve_image(file_path):
    """Serve image files"""
    # Convert URL-encoded backslashes back to forward slashes for cross-platform compatibility
    file_path = file_path.replace('%5C', '/').replace('\\', '/')
    full_path = DATA_DIR / file_path
    if not str(full_path).startswith(str(DATA_DIR)):
        abort(403)
    
    if not full_path.exists():
        abort(404)
    
    # Check if it's a TIF file that needs conversion
    if full_path.suffix.lower() in ['.tif', '.tiff']:
        try:
            # Open the TIF file and convert to JPEG
            with Image.open(full_path) as img:
                # Convert to RGB if necessary (TIF files might be in different color modes)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Create a BytesIO buffer to hold the JPEG data
                img_buffer = io.BytesIO()
                img.save(img_buffer, format='JPEG', quality=85, optimize=True)
                img_buffer.seek(0)
                
                # Return the JPEG data
                return send_file(
                    img_buffer,
                    mimetype='image/jpeg',
                    as_attachment=False,
                    download_name=full_path.stem + '.jpg'
                )
        except Exception as e:
            # If conversion fails, try to serve the original file
            print(f"TIF conversion failed for {full_path}: {e}")
            return send_file(full_path)
    
    # For other formats (JPG, PNG, etc.), serve directly
    return send_file(full_path)


@app.route('/api/stats')
def api_stats():
    """Get statistics"""
    conn = get_db_connection()
    
    # Total images
    total_images = conn.execute('SELECT COUNT(*) FROM images').fetchone()[0]
    
    # Images with OCR
    images_with_ocr = conn.execute(
        'SELECT COUNT(*) FROM images WHERE has_ocr_text = TRUE'
    ).fetchone()[0]
    
    # Volume breakdown
    volumes = conn.execute("""
        SELECT volume, COUNT(*) as count 
        FROM images 
        WHERE volume IS NOT NULL 
        GROUP BY volume 
        ORDER BY volume
    """).fetchall()
    
    conn.close()
    
    return jsonify({
        'total_images': total_images,
        'images_with_ocr': images_with_ocr,
        'ocr_percentage': (images_with_ocr / total_images * 100) if total_images > 0 else 0,
        'volumes': [{'volume': vol[0], 'count': vol[1]} for vol in volumes]
    })


@app.route('/api/search')
def api_search():
    """Search images by filename"""
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'results': []})
    
    conn = get_db_connection()
    results = conn.execute("""
        SELECT id, file_name, file_path, directory_path, has_ocr_text
        FROM images 
        WHERE file_name LIKE ? 
        ORDER BY file_name 
        LIMIT 50
    """, (f'%{query}%',)).fetchall()
    
    conn.close()
    
    return jsonify({
        'results': [dict(row) for row in results]
    })


@app.route('/api/first-image')
def api_first_image():
    """Get the first available image ID"""
    conn = get_db_connection()
    first_id = conn.execute('SELECT MIN(id) FROM images').fetchone()[0]
    last_id = conn.execute('SELECT MAX(id) FROM images').fetchone()[0]
    conn.close()
    
    return jsonify({
        'first_id': first_id,
        'last_id': last_id
    })


@app.route('/help')
def help_page():
    """Help and documentation page"""
    return render_template('help.html')


if __name__ == '__main__':
    print(f"🚀 Starting Epstein Documents Browser ({ENV_NAME})...")
    print(f"📖 Browse: http://localhost:8080")
    print(f"📊 Stats: http://localhost:8080/api/stats")
    if not IS_PRODUCTION:
        print(f"🌐 Accessible from: http://0.0.0.0:8080")
    print("\nPress Ctrl+C to stop the server")
    
    app.run(
        host=HOST,
        port=PORT,
        debug=DEBUG_MODE,
        threaded=True
    )
