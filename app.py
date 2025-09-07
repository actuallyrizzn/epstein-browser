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

# Analytics middleware
@app.before_request
def before_request():
    request.start_time = time.time()

@app.after_request
def after_request(response):
    if hasattr(request, 'start_time'):
        response_time = time.time() - request.start_time
        track_analytics(request, response, response_time)
    return response


def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_analytics_table():
    """Initialize analytics table if it doesn't exist"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
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
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_analytics_timestamp ON analytics(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_analytics_path ON analytics(path)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_analytics_ip ON analytics(ip_address)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_search_queries_timestamp ON search_queries(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_search_queries_query ON search_queries(query)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_search_queries_type ON search_queries(search_type)")
    
    conn.commit()
    conn.close()

# Initialize analytics table
init_analytics_table()


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
        'stats': dict(stats),
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
    ocr_file = DATA_DIR / file_path
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


@app.route('/api/thumbnail/<int:image_id>')
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
        full_path = DATA_DIR / file_path
        
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
    """Search images by filename and OCR text content with advanced filtering"""
    query = request.args.get('q', '').strip()
    search_type = request.args.get('type', 'all')  # all, filename, ocr
    ocr_filter = request.args.get('ocr', 'all')    # all, with-ocr, without-ocr
    sort_by = request.args.get('sort', 'relevance') # relevance, filename, id
    
    if not query:
        return jsonify({'results': []})
    
    conn = get_db_connection()
    
    try:
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
        per_page = 50
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
        
        # If searching all content or OCR only, also search OCR text
        ocr_text_results = []
        if search_type in ['all', 'ocr']:
            # Get all images with OCR text (no limit for comprehensive search)
            # Only exclude files that already matched filename search when doing 'all' search
            if search_type == 'all':
                ocr_candidates = conn.execute("""
                    SELECT id, file_name, file_path, directory_path, has_ocr_text
                    FROM images 
                    WHERE has_ocr_text = TRUE
                    AND file_name NOT LIKE ?
                    ORDER BY file_name 
                """, (f'%{query}%',)).fetchall()
            else:  # OCR only search
                ocr_candidates = conn.execute("""
                    SELECT id, file_name, file_path, directory_path, has_ocr_text
                    FROM images 
                    WHERE has_ocr_text = TRUE
                    ORDER BY file_name 
                """).fetchall()
            
            # Check OCR text content
            for row in ocr_candidates:
                try:
                    # Read the OCR text file
                    ocr_file_path = DATA_DIR / row['file_path'].replace(row['file_path'].split('.')[-1], 'txt')
                    if ocr_file_path.exists():
                        ocr_text = ocr_file_path.read_text(encoding='utf-8', errors='ignore')
                        query_lower = query.lower()
                        ocr_text_lower = ocr_text.lower()
                        
                        if query_lower in ocr_text_lower:
                            # Find the position of the match
                            match_pos = ocr_text_lower.find(query_lower)
                            
                            # Extract context around the match (100 chars before and after)
                            context_start = max(0, match_pos - 100)
                            context_end = min(len(ocr_text), match_pos + len(query) + 100)
                            excerpt = ocr_text[context_start:context_end]
                            
                            # Add ellipsis if we're not at the beginning/end
                            if context_start > 0:
                                excerpt = "..." + excerpt
                            if context_end < len(ocr_text):
                                excerpt = excerpt + "..."
                            
                            # Create result with excerpt
                            result = dict(row)
                            result['excerpt'] = excerpt
                            result['match_type'] = 'ocr'
                            result['match_position'] = match_pos
                            ocr_text_results.append(result)
                except Exception as e:
                    print(f"Error reading OCR file for {row['file_name']}: {e}")
                    continue
        
        conn.close()
        
        # Combine results based on search type
        if search_type == 'filename':
            all_results = list(filename_results)
        elif search_type == 'ocr':
            all_results = ocr_text_results
        else:  # all
            all_results = list(filename_results) + ocr_text_results
        
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
        conn.close()
        return jsonify({'error': str(e), 'results': []})


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


@app.route('/data/screenshots/<filename>')
def serve_screenshot(filename):
    """Serve screenshot files from data/screenshots directory"""
    screenshot_path = DATA_DIR / 'screenshots' / filename
    
    # Security check - ensure the file is in the screenshots directory
    if not screenshot_path.exists() or not str(screenshot_path).startswith(str(DATA_DIR / 'screenshots')):
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
    md = markdown.Markdown(extensions=['codehilite', 'fenced_code', 'tables'])
    post['html_content'] = md.convert(post['content'])
    
    return render_template('blog_post.html', post=post)


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
