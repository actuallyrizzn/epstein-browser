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
import json
import markdown
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, abort, session, redirect, url_for, flash, make_response
from PIL import Image
import io
from dotenv import load_dotenv
from collections import defaultdict, deque
from functools import wraps

# Load environment variables from .env file
load_dotenv()

# Configuration from environment variables
def get_data_dir():
    """Get DATA_DIR from environment variable."""
    return Path(os.environ.get('DATA_DIR', 'data'))

DATA_DIR = get_data_dir()  # For backward compatibility
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

# Rate Limiter
class RateLimiter:
    def __init__(self):
        self.requests = defaultdict(lambda: defaultdict(lambda: deque()))
        self.limits = {
            'search': (60, 60),    # 60 requests per 60 seconds
            'image': (200, 60),    # 200 requests per 60 seconds  
            'stats': (300, 60),    # 300 requests per 60 seconds
            'default': (100, 60),  # 100 requests per 60 seconds
        }
    
    def is_allowed(self, ip, endpoint_type='default'):
        now = time.time()
        requests = self.requests[ip][endpoint_type]
        
        # Clean old requests outside the window
        limit, window = self.limits.get(endpoint_type, self.limits['default'])
        while requests and now - requests[0] > window:
            requests.popleft()
        
        if len(requests) >= limit:
            return False, limit, window
        
        requests.append(now)
        return True, limit, window
    
    def get_remaining(self, ip, endpoint_type='default'):
        now = time.time()
        requests = self.requests[ip][endpoint_type]
        limit, window = self.limits.get(endpoint_type, self.limits['default'])
        
        # Clean old requests
        while requests and now - requests[0] > window:
            requests.popleft()
        
        return max(0, limit - len(requests))

# Initialize rate limiter
rate_limiter = RateLimiter()

# Rate limiting decorator
def rate_limit(endpoint_type='default'):
    def decorator(f):
        def decorated_function(*args, **kwargs):
            client_ip = request.remote_addr
            allowed, limit, window = rate_limiter.is_allowed(client_ip, endpoint_type)
            
            if not allowed:
                remaining = rate_limiter.get_remaining(client_ip, endpoint_type)
                reset_time = int(time.time() + window)
                
                response = make_response(jsonify({
                    'error': 'Rate limit exceeded',
                    'message': f'Too many requests. Limit: {limit} requests per {window} seconds',
                    'retry_after': window
                }), 429)
                
                response.headers['X-RateLimit-Limit'] = str(limit)
                response.headers['X-RateLimit-Remaining'] = str(remaining)
                response.headers['X-RateLimit-Reset'] = str(reset_time)
                response.headers['Retry-After'] = str(window)
                
                return response
            
            # Add rate limit headers to successful responses
            remaining = rate_limiter.get_remaining(client_ip, endpoint_type)
            reset_time = int(time.time() + window)
            
            result = f(*args, **kwargs)
            if hasattr(result, 'headers'):
                result.headers['X-RateLimit-Limit'] = str(limit)
                result.headers['X-RateLimit-Remaining'] = str(remaining)
                result.headers['X-RateLimit-Reset'] = str(reset_time)
            
            return result
        decorated_function.__name__ = f.__name__
        return decorated_function
    return decorator

# Analytics middleware
@app.before_request
def before_request():
    request.start_time = time.time()

@app.after_request
def after_request(response):
    if hasattr(request, 'start_time'):
        response_time = time.time() - request.start_time
        try:
            track_analytics(request, response, response_time)
        except Exception as e:
            # Log analytics errors but don't fail the request
            app.logger.error(f"Analytics tracking failed: {e}")
    return response


def _get_raw_db_connection():
    """Get a raw database connection without initialization."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_db_connection():
    """Get database connection with initialization."""
    # Get a raw connection first
    conn = _get_raw_db_connection()
    # Initialize database with the same connection
    init_database(conn)
    return conn


def init_database(conn=None):
    """Initialize all database tables if they don't exist"""
    created_conn = False
    if conn is None:
        conn = _get_raw_db_connection()
        created_conn = True
    cursor = conn.cursor()
    
    # Create images table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE NOT NULL,
            file_name TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            file_type TEXT NOT NULL,
            directory_path TEXT NOT NULL,
            volume TEXT,
            subdirectory TEXT,
            file_hash TEXT,
            has_ocr_text BOOLEAN DEFAULT FALSE,
            ocr_text_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create directories table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS directories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            parent_path TEXT,
            level INTEGER NOT NULL,
            file_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create analytics table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            user_agent TEXT,
            path TEXT,
            referer TEXT,
            method TEXT,
            status_code INTEGER,
            response_time REAL,
            session_id TEXT
        )
    """)
    
    # Create search queries table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS search_queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            query TEXT NOT NULL,
            search_type TEXT DEFAULT 'all',
            results_count INTEGER DEFAULT 0,
            ip_address TEXT,
            session_id TEXT,
            user_agent TEXT
        )
    """)
    
    # Create indexes for better performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_file_path ON images(file_path)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_file_type ON images(file_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_has_ocr_text ON images(has_ocr_text)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_directories_path ON directories(path)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_analytics_timestamp ON analytics(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_analytics_path ON analytics(path)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_analytics_ip ON analytics(ip_address)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_search_queries_timestamp ON search_queries(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_search_queries_query ON search_queries(query)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_search_queries_type ON search_queries(search_type)")
    
    conn.commit()
    # Only close the connection if we created it
    if created_conn:
        conn.close()

# Database lock handling
class DatabaseLockError(Exception):
    """Custom exception for database lock situations"""
    pass


# Initialize database tables only in production
if IS_PRODUCTION:
    init_database()


# Error handlers for database lock situations
@app.errorhandler(DatabaseLockError)
def handle_database_lock(error):
    """Handle database lock errors with a user-friendly page"""
    app.logger.warning(f"Database lock detected: {error}")
    return render_template('server_busy.html'), 503


@app.errorhandler(503)
def handle_service_unavailable(error):
    """Handle 503 Service Unavailable errors"""
    return render_template('server_busy.html'), 503


def handle_db_operations(max_retries=3, retry_delay=0.1, timeout=30.0):
    """
    Decorator to handle database operations with retry logic and lock detection.
    
    Args:
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds
        timeout: Maximum time to wait for database operations
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            
            for attempt in range(max_retries + 1):
                try:
                    # Set a timeout for the database operation
                    start_time = time.time()
                    
                    # Execute the function with timeout monitoring
                    result = func(*args, **kwargs)
                    
                    # Check if operation took too long
                    elapsed = time.time() - start_time
                    if elapsed > timeout:
                        raise DatabaseLockError(f"Database operation timed out after {elapsed:.2f}s")
                    
                    return result
                    
                except sqlite3.OperationalError as e:
                    last_error = e
                    error_msg = str(e).lower()
                    
                    # Check for specific lock-related errors
                    if any(keyword in error_msg for keyword in ['database is locked', 'database locked', 'busy']):
                        if attempt < max_retries:
                            app.logger.warning(f"Database locked on attempt {attempt + 1}, retrying in {retry_delay}s...")
                            time.sleep(retry_delay)
                            continue
                        else:
                            app.logger.error(f"Database locked after {max_retries} retries: {e}")
                            raise DatabaseLockError("Database is currently busy. Please try again in a moment.")
                    else:
                        # Other database errors - don't retry
                        raise e
                        
                except Exception as e:
                    # Non-database errors - don't retry
                    raise e
            
            # If we get here, all retries failed
            raise last_error
            
        return wrapper
    return decorator


def get_db_connection_with_retry():
    """Get database connection with retry logic for lock situations."""
    return handle_db_operations()(get_db_connection)()


def track_analytics(request, response, response_time):
    """Track analytics data for a request"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get or create session ID
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())
        
        cursor.execute("""
            INSERT INTO analytics 
            (ip_address, user_agent, path, referer, method, status_code, response_time, session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            request.remote_addr,
            request.headers.get('User-Agent', ''),
            request.path,
            request.headers.get('Referer', ''),
            request.method,
            response.status_code,
            response_time,
            session['session_id']
        ))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Analytics tracking error: {e}")


def track_search_query(query, search_type, results_count, request):
    """Track search query for analytics"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get or create session ID
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())
        
        cursor.execute("""
            INSERT INTO search_queries 
            (query, search_type, results_count, ip_address, session_id, user_agent)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            query,
            search_type,
            results_count,
            request.remote_addr,
            session['session_id'],
            request.headers.get('User-Agent', '')
        ))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Search tracking error: {e}")


def get_analytics_data(days=7):
    """Get analytics data for the specified number of days"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get basic stats
    cursor.execute("""
        SELECT 
            COUNT(*) as total_requests,
            COUNT(DISTINCT session_id) as unique_visitors,
            COUNT(DISTINCT session_id) as unique_sessions,
            AVG(response_time) as avg_response_time
        FROM analytics 
        WHERE timestamp >= datetime('now', '-{} days')
    """.format(days))
    
    stats = cursor.fetchone()
    stats_columns = [col[0] for col in cursor.description] if cursor.description else []
    
    # Get top pages
    cursor.execute("""
        SELECT path, COUNT(*) as views
        FROM analytics 
        WHERE timestamp >= datetime('now', '-{} days')
        GROUP BY path
        ORDER BY views DESC
        LIMIT 10
    """.format(days))
    
    top_pages = cursor.fetchall()
    
    # Get hourly distribution
    cursor.execute("""
        SELECT strftime('%H', timestamp) as hour, COUNT(*) as requests
        FROM analytics 
        WHERE timestamp >= datetime('now', '-{} days')
        GROUP BY hour
        ORDER BY hour
    """.format(days))
    
    hourly_data = cursor.fetchall()
    
    # Get referrers
    cursor.execute("""
        SELECT referer, COUNT(*) as visits
        FROM analytics 
        WHERE timestamp >= datetime('now', '-{} days')
        AND referer != ''
        GROUP BY referer
        ORDER BY visits DESC
        LIMIT 10
    """.format(days))
    
    referrers = cursor.fetchall()
    
    # Get popular searches
    cursor.execute("""
        SELECT query, search_type, COUNT(*) as search_count, AVG(results_count) as avg_results
        FROM search_queries 
        WHERE timestamp >= datetime('now', '-{} days')
        AND query != ''
        GROUP BY query, search_type
        ORDER BY search_count DESC
        LIMIT 20
    """.format(days))
    
    popular_searches = cursor.fetchall()
    
    conn.close()
    
    return {
        'stats': dict(zip(stats_columns, stats)) if stats else {},
        'top_pages': [dict(row) for row in top_pages],
        'hourly_data': [dict(row) for row in hourly_data],
        'referrers': [dict(row) for row in referrers],
        'popular_searches': [dict(row) for row in popular_searches]
    }


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
    
    # Create the OCR text file path by replacing the extension with .txt
    ocr_file = get_data_dir() / file_path
    ocr_file = ocr_file.with_suffix('.txt')
    
    if ocr_file.exists():
        try:
            return ocr_file.read_text(encoding='utf-8')
        except:
            return None
    return None


def load_blog_posts():
    """Load blog posts from JSON file"""
    try:
        with open('blog_posts.json', 'r', encoding='utf-8') as f:
            posts = json.load(f)
        # Sort by date (newest first)
        posts.sort(key=lambda x: x['date'], reverse=True)
        return posts
    except FileNotFoundError:
        return []
    except Exception as e:
        print(f"Error loading blog posts: {e}")
        return []


def get_blog_post(slug):
    """Get a specific blog post by slug"""
    posts = load_blog_posts()
    for post in posts:
        if post['slug'] == slug:
            return post
    return None


@app.route('/')
@handle_db_operations()
def index():
    """Homepage - show first image"""
    total_images = get_total_images()
    if total_images == 0:
        return render_template('index.html', total_images=0, first_image=None)
    
    # Get first available image ID
    conn = get_db_connection()
    first_result = conn.execute('SELECT MIN(id) FROM images').fetchone()
    conn.close()
    
    if not first_result or not first_result[0]:
        return render_template('index.html', total_images=0, first_image=None)
    
    first_id = first_result[0]
    
    # Get first image
    first_image = get_image_by_id(first_id)
    if not first_image:
        return render_template('index.html', total_images=0, first_image=None)
    
    return render_template('index.html', 
                         total_images=total_images,
                         first_image=first_image)


@app.route('/view/<int:image_id>')
@handle_db_operations()
def view_image(image_id):
    """View a specific image"""
    image = get_image_by_id(image_id)
    if not image:
        abort(404)
    
    total_images = get_total_images()
    
    # Get previous and next image IDs using actual database queries
    conn = get_db_connection()
    
    # Get previous image ID (highest ID less than current)
    prev_result = conn.execute('SELECT id FROM images WHERE id < ? ORDER BY id DESC LIMIT 1', (image_id,)).fetchone()
    prev_id = prev_result[0] if prev_result else None
    
    # Get next image ID (lowest ID greater than current)
    next_result = conn.execute('SELECT id FROM images WHERE id > ? ORDER BY id ASC LIMIT 1', (image_id,)).fetchone()
    next_id = next_result[0] if next_result else None
    
    # Get first and last image IDs for progress calculation
    first_result = conn.execute('SELECT MIN(id) FROM images').fetchone()
    last_result = conn.execute('SELECT MAX(id) FROM images').fetchone()
    first_id = first_result[0] if first_result else image_id
    last_id = last_result[0] if last_result else image_id
    
    conn.close()
    
    # Get OCR text if available
    ocr_text = None
    if image['has_ocr_text']:
        ocr_text = get_ocr_text(image['file_path'])
    
    # Calculate progress based on position in the actual ID range
    if last_id > first_id:
        progress_percent = ((image_id - first_id) / (last_id - first_id) * 100)
    else:
        progress_percent = 100.0  # Only one image
    
    return render_template('viewer.html',
                         image=image,
                         image_id=image_id,
                         total_images=total_images,
                         prev_id=prev_id,
                         next_id=next_id,
                         ocr_text=ocr_text,
                         progress_percent=progress_percent)


@app.route('/image/<path:file_path>')
@rate_limit('image')
def serve_image(file_path):
    """Serve image files"""
    # Convert URL-encoded backslashes back to forward slashes for cross-platform compatibility
    file_path = file_path.replace('%5C', '/').replace('\\', '/')
    full_path = get_data_dir() / file_path
    if not str(full_path).startswith(str(get_data_dir())):
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


@app.route('/api/thumbnail/<int:image_id>')
@rate_limit('image')
def serve_thumbnail(image_id):
    """Serve thumbnail images for search results"""
    try:
        conn = get_db_connection()
        image = conn.execute(
            'SELECT file_path FROM images WHERE id = ?', (image_id,)
        ).fetchone()
        conn.close()
        
        if not image:
            abort(404)
        
        # Construct full path
        file_path = image[0].replace('%5C', '/').replace('\\', '/')
        full_path = get_data_dir() / file_path
        
        # Check if file exists
        if not full_path.exists():
            abort(404)
        
        # Create thumbnail
        try:
            with Image.open(full_path) as img:
                # Convert to RGB if necessary
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Create thumbnail (300x200 max, maintaining aspect ratio)
                img.thumbnail((300, 200), Image.Resampling.LANCZOS)
                
                # Create in-memory JPEG
                img_io = io.BytesIO()
                img.save(img_io, format='JPEG', quality=80, optimize=True)
                img_io.seek(0)
                
                # Return JPEG thumbnail
                return send_file(img_io, mimetype='image/jpeg')
        except Exception as e:
            app.logger.error(f"Error creating thumbnail: {e}")
            abort(500)
    
    except Exception as e:
        app.logger.error(f"Error serving thumbnail: {e}")
        abort(500)


@app.route('/api/stats')
@rate_limit('stats')
@handle_db_operations()
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
@rate_limit('search')
@handle_db_operations()
def api_search():
    """Search images by filename and OCR text content with advanced filtering"""
    query = request.args.get('q', '').strip()
    search_type = request.args.get('type', 'all')  # all, filename, ocr
    ocr_filter = request.args.get('ocr', 'all')    # all, with-ocr, without-ocr
    sort_by = request.args.get('sort', 'relevance') # relevance, filename, id
    
    if not query:
        return jsonify({'results': []})
    
    try:
        conn = get_db_connection()
        # Build base query with filters
        where_conditions = []
        params = []
        
        # OCR filter
        if ocr_filter == 'with-ocr':
            where_conditions.append('has_ocr_text = TRUE')
        elif ocr_filter == 'without-ocr':
            where_conditions.append('has_ocr_text = FALSE')
        
        # Search type and query
        if search_type == 'filename':
            where_conditions.append('file_name LIKE ?')
            params.append(f'%{query}%')
        elif search_type == 'ocr':
            where_conditions.append('has_ocr_text = TRUE')
            # We'll filter OCR results later
        else:  # all
            where_conditions.append('file_name LIKE ?')
            params.append(f'%{query}%')
        
        # Build the query
        where_clause = ' AND '.join(where_conditions) if where_conditions else '1=1'
        
        # Calculate pagination
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        offset = (page - 1) * per_page
        
        # Create params for main query
        main_params = params.copy()
        
        # Sort order
        if sort_by == 'filename':
            order_clause = 'ORDER BY file_name'
        elif sort_by == 'id':
            order_clause = 'ORDER BY id'
        else:  # relevance
            order_clause = 'ORDER BY CASE WHEN file_name LIKE ? THEN 1 ELSE 2 END, file_name'
            main_params.insert(0, f'{query}%')
        
        filename_results = conn.execute(f"""
            SELECT id, file_name, file_path, directory_path, has_ocr_text, 'filename' as match_type
            FROM images 
            WHERE {where_clause}
            {order_clause}
            LIMIT ? OFFSET ?
        """, main_params + [per_page, offset]).fetchall()
        
        # If searching all content or OCR only, also search OCR text using database
        ocr_text_results = []
        if search_type in ['all', 'ocr']:
            try:
                # Use database search for OCR content (faster than file I/O)
                if search_type == 'all':
                    # Exclude files that already matched filename search
                    filename_paths = [row['file_path'] for row in filename_results]
                    if filename_paths:
                        placeholders = ','.join('?' for _ in filename_paths)
                        ocr_query = f"""
                            SELECT i.id, i.file_name, i.file_path, i.directory_path, i.has_ocr_text,
                                   'ocr' as match_type,
                                   SUBSTR(oc.content, 
                                          MAX(1, INSTR(LOWER(oc.content), LOWER(?)) - 50),
                                          100) as excerpt
                            FROM images i
                            JOIN ocr_content oc ON i.id = oc.image_id
                            WHERE i.has_ocr_text = TRUE 
                            AND LOWER(oc.content) LIKE LOWER(?)
                            AND i.file_path NOT IN ({placeholders})
                            ORDER BY i.file_name
                        """
                        ocr_params = [query, f'%{query}%'] + filename_paths
                    else:
                        ocr_query = """
                            SELECT i.id, i.file_name, i.file_path, i.directory_path, i.has_ocr_text,
                                   'ocr' as match_type,
                                   SUBSTR(oc.content, 
                                          MAX(1, INSTR(LOWER(oc.content), LOWER(?)) - 50),
                                          100) as excerpt
                            FROM images i
                            JOIN ocr_content oc ON i.id = oc.image_id
                            WHERE i.has_ocr_text = TRUE 
                            AND LOWER(oc.content) LIKE LOWER(?)
                            ORDER BY i.file_name
                        """
                        ocr_params = [query, f'%{query}%']
                else:  # OCR only search
                    ocr_query = """
                        SELECT i.id, i.file_name, i.file_path, i.directory_path, i.has_ocr_text,
                               'ocr' as match_type,
                               SUBSTR(oc.content, 
                                      MAX(1, INSTR(LOWER(oc.content), LOWER(?)) - 50),
                                      100) as excerpt
                        FROM images i
                        JOIN ocr_content oc ON i.id = oc.image_id
                        WHERE i.has_ocr_text = TRUE 
                        AND LOWER(oc.content) LIKE LOWER(?)
                        ORDER BY i.file_name
                    """
                    ocr_params = [query, f'%{query}%']
                
                ocr_cursor = conn.execute(ocr_query, ocr_params)
                ocr_text_results = [dict(row) for row in ocr_cursor.fetchall()]
                
            except Exception as e:
                # Fallback to old method if database search fails
                app.logger.warning(f"Database OCR search failed, falling back to file-based search: {e}")
                ocr_text_results = []
        
        conn.close()
        
        # Combine results based on search type
        if search_type == 'filename':
            all_results = [dict(row) for row in filename_results]
        elif search_type == 'ocr':
            all_results = ocr_text_results
        else:  # all
            all_results = [dict(row) for row in filename_results] + ocr_text_results
        
        # Sort combined results if needed
        if sort_by == 'relevance' and search_type == 'all':
            # Filename matches first, then OCR matches
            pass  # Already ordered correctly
        elif sort_by == 'filename':
            all_results.sort(key=lambda x: x['file_name'])
        elif sort_by == 'id':
            all_results.sort(key=lambda x: x['id'])
        
        # Apply pagination to combined results
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_results = all_results[start_idx:end_idx]
        
        # Calculate pagination metadata based on actual combined results
        total_count = len(all_results)
        total_pages = max(1, (total_count + per_page - 1) // per_page) if total_count > 0 else 1
        has_next = page < total_pages
        has_prev = page > 1
        
        response_data = {
            'results': paginated_results,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_count': total_count,
                'total_pages': total_pages,
                'has_next': has_next,
                'has_prev': has_prev
            }
        }
        
        # Track the search query for analytics
        track_search_query(query, search_type, total_count, request)
        
        return jsonify(response_data)
        
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return jsonify({'error': str(e), 'results': []})


@app.route('/api/document/<int:doc_id>')
@rate_limit('stats')
@handle_db_operations()
def api_document(doc_id):
    """Get document by ID with OCR text"""
    conn = get_db_connection()
    image = conn.execute(
        'SELECT * FROM images WHERE id = ?', (doc_id,)
    ).fetchone()
    conn.close()
    
    if not image:
        return jsonify({'error': 'Document not found'}), 404
    
    # Get OCR text if available
    ocr_text = None
    if image['has_ocr_text']:
        ocr_text = get_ocr_text(image['file_path'])
    
    return jsonify({
        'id': image['id'],
        'file_path': image['file_path'],
        'filename': image['file_name'],
        'has_ocr_text': bool(image['has_ocr_text']),
        'ocr_text': ocr_text,
        'file_size': image['file_size'],
        'created_at': image['created_at']
    })


@app.route('/api/first-image')
@rate_limit('stats')
@handle_db_operations()
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


@app.route('/search')
def search_page():
    """Advanced search page"""
    conn = get_db_connection()
    total_images = conn.execute('SELECT COUNT(*) FROM images').fetchone()[0]
    conn.close()
    
    query = request.args.get('q', '')
    return render_template('search.html', total_images=total_images, query=query)

@app.route('/help')
def help_page():
    """Help and documentation index page"""
    conn = get_db_connection()
    total_images = conn.execute('SELECT COUNT(*) FROM images').fetchone()[0]
    images_with_ocr = conn.execute('SELECT COUNT(*) FROM images WHERE has_ocr_text = TRUE').fetchone()[0]
    conn.close()
    
    return render_template('help/index.html', 
                         total_images=total_images,
                         images_with_ocr=images_with_ocr,
                         ocr_percentage=(images_with_ocr / total_images * 100) if total_images > 0 else 0)


@app.route('/help/overview')
def help_overview():
    """Help overview page"""
    conn = get_db_connection()
    total_images = conn.execute('SELECT COUNT(*) FROM images').fetchone()[0]
    images_with_ocr = conn.execute('SELECT COUNT(*) FROM images WHERE has_ocr_text = TRUE').fetchone()[0]
    conn.close()
    
    return render_template('help/overview.html', 
                         total_images=total_images,
                         images_with_ocr=images_with_ocr,
                         ocr_percentage=(images_with_ocr / total_images * 100) if total_images > 0 else 0)


@app.route('/help/features')
def help_features():
    """Help features page"""
    return render_template('help/features.html')


@app.route('/help/usage')
def help_usage():
    """Help usage guide page"""
    return render_template('help/usage.html')


@app.route('/help/api')
def help_api():
    """Help API guide page"""
    return render_template('help/api.html')

@app.route('/help/installation')
def help_installation():
    """Help installation guide page"""
    return render_template('help/installation.html')

@app.route('/help/context')
def help_context():
    """Help context and official sources page"""
    conn = get_db_connection()
    total_images = conn.execute('SELECT COUNT(*) FROM images').fetchone()[0]
    conn.close()
    
    # Load blog posts for timeline
    blog_posts = load_blog_posts()
    
    return render_template('help/context.html', total_images=total_images, blog_posts=blog_posts)


@app.route('/data/screenshots/<filename>')
def serve_screenshot(filename):
    """Serve screenshot files from data/screenshots directory"""
    screenshot_path = get_data_dir() / 'screenshots' / filename
    
    # Security check - ensure the file is in the screenshots directory
    if not screenshot_path.exists() or not str(screenshot_path).startswith(str(get_data_dir() / 'screenshots')):
        abort(404)
    
    return send_file(screenshot_path)


@app.route('/blog')
def blog():
    """Blog listing page"""
    posts = load_blog_posts()
    return render_template('blog.html', posts=posts)


@app.route('/blog/feed.xml')
def blog_rss():
    """RSS feed for blog posts"""
    posts = load_blog_posts()
    
    # Generate RSS XML
    base_url = request.url_root.rstrip('/')
    rss_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
    <channel>
        <title>Epstein Documents Browser Blog</title>
        <link>{base_url}/blog</link>
        <description>Updates and insights about the Epstein Documents Browser - an open-source document management system for congressional records.</description>
        <language>en-us</language>
        <lastBuildDate>{datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')}</lastBuildDate>
        <atom:link href="{base_url}/blog/feed.xml" rel="self" type="application/rss+xml"/>
        <generator>Epstein Documents Browser</generator>
        <managingEditor>mark@rizzn.net (Mark Rizzn Hopkins)</managingEditor>
        <webMaster>mark@rizzn.net (Mark Rizzn Hopkins)</webMaster>
'''
    
    for post in posts:
        # Convert date to RFC 2822 format
        post_date = datetime.strptime(post['date'], '%Y-%m-%d').strftime('%a, %d %b %Y 00:00:00 GMT')
        
        # Clean content for RSS (remove markdown, basic HTML)
        content = post['content']
        # Convert markdown headers to HTML
        content = content.replace('## ', '<h2>').replace('\n\n', '</h2>\n\n')
        content = content.replace('### ', '<h3>').replace('\n\n', '</h3>\n\n')
        content = content.replace('**', '<strong>').replace('**', '</strong>')
        content = content.replace('*', '<em>').replace('*', '</em>')
        content = content.replace('\n', '<br/>\n')
        
        rss_xml += f'''
        <item>
            <title>{post['title']}</title>
            <link>{base_url}/blog/{post['slug']}</link>
            <description><![CDATA[{post['excerpt']}]]></description>
            <pubDate>{post_date}</pubDate>
            <guid isPermaLink="true">{base_url}/blog/{post['slug']}</guid>
            <author>mark@rizzn.net (Mark Rizzn Hopkins)</author>
        </item>'''
    
    rss_xml += '''
    </channel>
</rss>'''
    
    response = make_response(rss_xml)
    response.headers['Content-Type'] = 'application/rss+xml; charset=utf-8'
    return response


@app.route('/blog/<slug>')
def blog_post(slug):
    """Individual blog post page"""
    post = get_blog_post(slug)
    if not post:
        abort(404)
    
    # Process Markdown content
    md = markdown.Markdown(extensions=['codehilite', 'fenced_code', 'tables', 'toc', 'nl2br'])
    post['html_content'] = md.convert(post['content'])
    
    return render_template('blog_post.html', post=post)


@app.route('/test-db-lock')
def test_db_lock():
    """Test route to simulate database lock (for testing only)"""
    if not app.config['DEBUG']:
        abort(404)
    
    # Simulate a database lock by creating a long-running transaction
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Start a transaction and hold it open
    cursor.execute('BEGIN IMMEDIATE')
    cursor.execute('SELECT COUNT(*) FROM images')
    
    # Sleep for a few seconds to simulate lock
    time.sleep(3)
    
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Database lock test completed'})


@app.route('/sitemap.xml')
def sitemap():
    """Generate sitemap.xml for search engines"""
    from datetime import datetime
    
    # Get some sample document data for sitemap
    conn = get_db_connection()
    sample_docs = conn.execute('''
        SELECT id, file_path, file_name 
        FROM images 
        ORDER BY id 
        LIMIT 100
    ''').fetchall()
    conn.close()
    
    # Prepare data for template
    image_paths = [doc['file_path'] for doc in sample_docs]
    image_names = [doc['file_name'] for doc in sample_docs]
    total_images = get_total_images()
    
    return render_template('sitemap.xml', 
                         moment=lambda: datetime.now(),
                         image_paths=image_paths,
                         image_names=image_names,
                         total_images=total_images), 200, {'Content-Type': 'application/xml'}


@app.route('/robots.txt')
def robots():
    """Generate robots.txt for search engines"""
    return render_template('robots.txt'), 200, {'Content-Type': 'text/plain'}


# Admin authentication
def check_admin_auth():
    """Check if user is authenticated as admin"""
    return session.get('admin_logged_in', False)


def require_admin_auth():
    """Require admin authentication for protected routes"""
    if not check_admin_auth():
        flash('Admin authentication required', 'error')
        return redirect(url_for('admin_login'))


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    if request.method == 'POST':
        password = request.form.get('password', '')
        admin_password = os.environ.get('ADMIN_PASSWORD', 'abc123')
        
        if password == admin_password:
            session['admin_logged_in'] = True
            flash('Successfully logged in as admin', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid password', 'error')
    
    return render_template('admin_login.html')


@app.route('/admin/logout')
def admin_logout():
    """Admin logout"""
    session.pop('admin_logged_in', None)
    flash('Successfully logged out', 'info')
    return redirect(url_for('admin_login'))


@app.route('/admin')
def admin_dashboard():
    """Admin dashboard with analytics"""
    if not check_admin_auth():
        return redirect(url_for('admin_login'))
    
    days = request.args.get('days', 7, type=int)
    analytics_data = get_analytics_data(days)
    
    return render_template('admin_dashboard.html', 
                         analytics=analytics_data, 
                         days=days)


@app.route('/admin/analytics')
def admin_analytics():
    """Raw analytics data API for admin"""
    if not check_admin_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    
    days = request.args.get('days', 7, type=int)
    analytics_data = get_analytics_data(days)
    
    return jsonify(analytics_data)


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
