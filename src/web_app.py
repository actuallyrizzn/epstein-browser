"""
Flask Web Application for Epstein Documents OCR Progress Tracking

Public-facing web interface for tracking OCR processing progress and browsing
extracted text data.

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

import os
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

from flask import Flask, render_template, jsonify, request, send_file, abort
from werkzeug.exceptions import NotFound

from progress_tracker import ProgressTracker
from web_database import WebDatabase

# Initialize Flask app with proper template directory
template_dir = Path(__file__).parent.parent / "templates"
app = Flask(__name__, template_folder=str(template_dir))
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Initialize progress tracker and web database
progress_tracker = ProgressTracker()
web_database = WebDatabase()

# Configuration
DATA_DIR = Path("data")
OCR_OUTPUT_DIR = Path("data/ocr_output")
MAX_SEARCH_RESULTS = 100


@app.route('/')
def index():
    """Main dashboard page"""
    stats = progress_tracker.get_statistics()
    recent_activity = progress_tracker.get_recent_activity(limit=10)
    
    # Calculate ETA
    if stats['processed_count'] > 0 and stats['avg_processing_time'] > 0:
        remaining_files = stats['total_files'] - stats['processed_count']
        eta_seconds = remaining_files * stats['avg_processing_time']
        eta = datetime.now() + timedelta(seconds=eta_seconds)
        eta_str = eta.strftime("%Y-%m-%d %H:%M:%S")
    else:
        eta_str = "Calculating..."
    
    return render_template('index.html', 
                         stats=stats, 
                         recent_activity=recent_activity,
                         eta=eta_str,
                         current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))


@app.route('/api/stats')
def api_stats():
    """API endpoint for real-time statistics"""
    stats = progress_tracker.get_statistics()
    return jsonify(stats)


@app.route('/api/recent')
def api_recent():
    """API endpoint for recent activity"""
    limit = request.args.get('limit', 10, type=int)
    recent_activity = progress_tracker.get_recent_activity(limit=limit)
    return jsonify(recent_activity)


@app.route('/search')
def search():
    """Search interface page"""
    query = request.args.get('q', '')
    results = []
    
    if query:
        results = search_extracted_text(query)
    
    return render_template('search.html', query=query, results=results)


@app.route('/api/search')
def api_search():
    """API endpoint for text search"""
    query = request.args.get('q', '')
    limit = request.args.get('limit', MAX_SEARCH_RESULTS, type=int)
    
    if not query:
        return jsonify({'error': 'Query parameter required'}), 400
    
    results = search_extracted_text(query, limit=limit)
    return jsonify({'query': query, 'results': results, 'count': len(results)})


@app.route('/browse')
def browse():
    """Browse documents by status, volume, or directory"""
    status = request.args.get('status', 'all')
    volume = request.args.get('volume', None)
    directory = request.args.get('directory', None)
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    # Get files based on filter
    if directory:
        # Browse by directory
        files, total = web_database.get_files_by_directory(directory, page, per_page)
    elif volume:
        # Browse by volume
        files, total = web_database.get_files_by_volume(volume, page, per_page)
    else:
        # Get all files with pagination
        files, total = web_database.get_all_files(page, per_page)
    
    # Calculate pagination info
    total_pages = (total + per_page - 1) // per_page
    has_prev = page > 1
    has_next = page < total_pages
    
    # Get available volumes and directories for navigation
    stats = web_database.get_statistics()
    volumes = [vol['volume'] for vol in stats['volumes']]
    directories = web_database.get_directory_tree()
    
    return render_template('browse.html', 
                         files=files,
                         status=status,
                         volume=volume,
                         directory=directory,
                         volumes=volumes,
                         directories=directories,
                         page=page,
                         total_pages=total_pages,
                         has_prev=has_prev,
                         has_next=has_next,
                         total=total)


@app.route('/document/<path:file_path>')
def view_document(file_path):
    """View individual document and its extracted text"""
    # Security check - ensure file is within data directory
    full_path = DATA_DIR / file_path
    if not str(full_path).startswith(str(DATA_DIR)):
        abort(403)
    
    if not full_path.exists():
        abort(404)
    
    # Get document info from web database
    doc_info = web_database.get_file_by_path(file_path)
    if not doc_info:
        # Fallback to basic info if not in database
        doc_info = {
            'file_name': full_path.name,
            'file_size': full_path.stat().st_size,
            'file_type': full_path.suffix.lower(),
            'directory_path': str(full_path.parent.relative_to(DATA_DIR)),
            'volume': None,
            'has_ocr_text': False,
            'ocr_status': 'pending'
        }
    
    # Get extracted text if available
    extracted_text = get_extracted_text(file_path)
    
    # Check if this is an image file
    is_image = full_path.suffix.lower() in {'.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp', '.webp'}
    
    return render_template('document.html', 
                         doc_info=doc_info,
                         extracted_text=extracted_text,
                         file_path=file_path,
                         is_image=is_image,
                         image_url=f"/static/{file_path}" if is_image else None)


@app.route('/download/<path:file_path>')
def download_text(file_path):
    """Download extracted text file"""
    # Security check
    full_path = DATA_DIR / file_path
    if not str(full_path).startswith(str(DATA_DIR)):
        abort(403)
    
    # Look for corresponding text file
    text_file = find_text_file(file_path)
    if not text_file or not text_file.exists():
        abort(404)
    
    return send_file(text_file, as_attachment=True)


@app.route('/static/<path:file_path>')
def serve_static(file_path):
    """Serve static files (images) from the data directory"""
    # Security check - ensure file is within data directory
    full_path = DATA_DIR / file_path
    if not str(full_path).startswith(str(DATA_DIR)):
        abort(403)
    
    if not full_path.exists():
        abort(404)
    
    return send_file(full_path)

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'database': 'connected' if progress_tracker else 'disconnected'
    })


def search_extracted_text(query: str, limit: int = MAX_SEARCH_RESULTS) -> List[Dict[str, Any]]:
    """Search through extracted text files"""
    results = []
    query_lower = query.lower()
    
    # Search through text files in OCR output directory
    if not OCR_OUTPUT_DIR.exists():
        return results
    
    for text_file in OCR_OUTPUT_DIR.rglob("*.txt"):
        try:
            with open(text_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if query_lower in content.lower():
                # Find the original image file
                original_file = find_original_image(text_file)
                
                results.append({
                    'text_file': str(text_file.relative_to(DATA_DIR)),
                    'original_file': str(original_file.relative_to(DATA_DIR)) if original_file else None,
                    'content_preview': get_content_preview(content, query_lower),
                    'file_size': text_file.stat().st_size,
                    'modified': datetime.fromtimestamp(text_file.stat().st_mtime).isoformat()
                })
                
                if len(results) >= limit:
                    break
                    
        except Exception as e:
            print(f"Error reading {text_file}: {e}")
            continue
    
    return results


def get_content_preview(content: str, query: str, context: int = 100) -> str:
    """Get a preview of content around the search query"""
    query_pos = content.lower().find(query)
    if query_pos == -1:
        return content[:200] + "..." if len(content) > 200 else content
    
    start = max(0, query_pos - context)
    end = min(len(content), query_pos + len(query) + context)
    
    preview = content[start:end]
    if start > 0:
        preview = "..." + preview
    if end < len(content):
        preview = preview + "..."
    
    return preview


def find_original_image(text_file: Path) -> Optional[Path]:
    """Find the original image file corresponding to a text file"""
    # Remove .txt extension and try common image extensions
    base_name = text_file.with_suffix('')
    
    for ext in ['.jpg', '.jpeg', '.tif', '.tiff', '.png']:
        original = base_name.with_suffix(ext)
        if original.exists():
            return original
    
    return None


def find_text_file(image_file: str) -> Optional[Path]:
    """Find the text file corresponding to an image file"""
    image_path = DATA_DIR / image_file
    if not image_path.exists():
        return None
    
    # Try to find corresponding text file
    base_name = image_path.with_suffix('')
    text_file = base_name.with_suffix('.txt')
    
    return text_file if text_file.exists() else None


def get_document_info(file_path: str) -> Dict[str, Any]:
    """Get information about a document"""
    full_path = DATA_DIR / file_path
    
    if not full_path.exists():
        return {}
    
    stat = full_path.stat()
    
    return {
        'file_path': file_path,
        'file_name': full_path.name,
        'file_size': stat.st_size,
        'file_type': full_path.suffix.lower(),
        'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
        'created': datetime.fromtimestamp(stat.st_ctime).isoformat()
    }


def get_extracted_text(file_path: str) -> Optional[str]:
    """Get extracted text for a document"""
    text_file = find_text_file(file_path)
    if not text_file or not text_file.exists():
        return None
    
    try:
        with open(text_file, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading text file {text_file}: {e}")
        return None


def get_all_files() -> List[Dict[str, Any]]:
    """Get all files from the database"""
    return progress_tracker.get_all_files()


def get_completed_files() -> List[Dict[str, Any]]:
    """Get completed files from the database"""
    return progress_tracker.get_completed_files()


def get_pending_files() -> List[Dict[str, Any]]:
    """Get pending files from the database"""
    return progress_tracker.get_pending_files()


def get_failed_files() -> List[Dict[str, Any]]:
    """Get failed files from the database"""
    return progress_tracker.get_failed_files()


def get_files_by_volume(volume: str) -> List[Dict[str, Any]]:
    """Get files from a specific volume"""
    volume_path = DATA_DIR / volume
    if not volume_path.exists():
        return []
    
    files = []
    for ext in ['.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp', '.webp']:
        pattern = f"**/*{ext}"
        found_files = list(volume_path.glob(pattern))
        for file_path in found_files:
            files.append({
                'file_path': str(file_path.relative_to(DATA_DIR)),
                'file_name': file_path.name,
                'file_size': file_path.stat().st_size,
                'status': 'completed' if (file_path.with_suffix('.txt')).exists() else 'pending'
            })
    
    return sorted(files, key=lambda x: x['file_name'])


def get_available_volumes() -> List[str]:
    """Get list of available volumes"""
    volumes = []
    for item in DATA_DIR.iterdir():
        if item.is_dir() and item.name.startswith('VOL'):
            volumes.append(item.name)
    return sorted(volumes)


if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    templates_dir = Path("templates")
    templates_dir.mkdir(exist_ok=True)
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=5000, debug=True)
