"""
Tests to achieve coverage for route handling functionality.
"""
import pytest
import os
import json
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path

# Set up test environment before importing app
os.environ['FLASK_ENV'] = 'testing'
os.environ['DATABASE_PATH'] = ':memory:'
os.environ['DATA_DIR'] = 'tests/fixtures/test_data'

from app import app, get_db_connection, init_analytics_table
from tests.test_database import test_db_manager


class TestRouteCoverage:
    """Tests to achieve coverage for route handling functionality."""
    
    def test_search_page_route(self):
        """Test search page route."""
        with test_db_manager as db_manager:
            # Clear any existing data and insert test data
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM images')  # Clear existing data
            conn.commit()
            
            cursor.execute("""
                INSERT INTO images (file_path, file_name, file_size, file_type, directory_path, volume, subdirectory, file_hash, has_ocr_text, ocr_text_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ('test1.TIF', 'test1.TIF', 1024, 'TIF', 'test', 'VOL00001', 'IMAGES001', 'hash1', True, 'ocr1.txt'))
            
            conn.commit()
            conn.close()
            
            # Test search page route
            with app.test_client() as client:
                response = client.get('/search')
                assert response.status_code == 200
                assert b'Search' in response.data
    
    def test_serve_screenshot_success(self):
        """Test serve screenshot route success."""
        from unittest.mock import patch
        
        # Mock the DATA_DIR to point to the test directory
        with patch('app.DATA_DIR', Path('tests/fixtures/test_data')):
            # Create the actual file
            screenshot_path = Path('tests/fixtures/test_data/screenshots')
            screenshot_path.mkdir(parents=True, exist_ok=True)
            test_screenshot = screenshot_path / 'test.png'
            test_screenshot.write_bytes(b'fake image data')
            
            with app.test_client() as client:
                response = client.get('/data/screenshots/test.png')
                assert response.status_code == 200
                assert response.data == b'fake image data'
    
    def test_serve_screenshot_not_found(self):
        """Test serve screenshot route not found."""
        with app.test_client() as client:
            response = client.get('/data/screenshots/nonexistent.png')
            assert response.status_code == 404
    
    def test_serve_screenshot_security_check(self):
        """Test serve screenshot route security check."""
        with app.test_client() as client:
            # Try to access file outside screenshots directory
            response = client.get('/data/screenshots/../../../app.py')
            assert response.status_code == 404
    
    def test_blog_route(self):
        """Test blog listing route."""
        with app.test_client() as client:
            response = client.get('/blog')
            assert response.status_code == 200
            assert b'Blog' in response.data
    
    def test_blog_rss_route(self):
        """Test blog RSS feed route."""
        with app.test_client() as client:
            response = client.get('/blog/feed.xml')
            assert response.status_code == 200
            assert b'<?xml' in response.data
            assert b'<rss' in response.data
            assert b'Epstein Documents Browser Blog' in response.data
    
    def test_blog_post_route_success(self):
        """Test blog post individual route success."""
        with app.test_client() as client:
            response = client.get('/blog/welcome-to-epstein-documents-browser')
            assert response.status_code == 200
            assert b'Welcome to the Epstein Documents Browser' in response.data
    
    def test_blog_post_route_not_found(self):
        """Test blog post individual route not found."""
        with app.test_client() as client:
            response = client.get('/blog/nonexistent-post')
            assert response.status_code == 404
    
    def test_blog_post_route_with_analytics(self):
        """Test blog post route with analytics tracking."""
        with test_db_manager as db_manager:
            with app.test_client() as client:
                response = client.get('/blog/welcome-to-epstein-documents-browser')
                assert response.status_code == 200
                
                # Check that analytics were tracked
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM analytics WHERE path = '/blog/welcome-to-epstein-documents-browser'")
                count = cursor.fetchone()[0]
                conn.close()
                assert count > 0
    
    def test_blog_post_route_analytics_error(self):
        """Test blog post route with analytics error."""
        with patch('app.track_analytics', side_effect=Exception("Analytics error")):
            with app.test_client() as client:
                response = client.get('/blog/welcome-to-epstein-documents-browser')
                assert response.status_code == 200  # Should still work despite analytics error
    
    def test_admin_login_get(self):
        """Test admin login GET request."""
        with app.test_client() as client:
            response = client.get('/admin/login')
            assert response.status_code == 200
            assert b'Admin Login' in response.data or b'login' in response.data.lower()
    
    def test_admin_login_post_success(self):
        """Test admin login POST request success."""
        with app.test_client() as client:
            response = client.post('/admin/login', data={'password': 'abc123'})
            assert response.status_code == 302  # Redirect after successful login
    
    def test_admin_login_post_failure(self):
        """Test admin login POST request failure."""
        with app.test_client() as client:
            response = client.post('/admin/login', data={'password': 'wrongpassword'})
            assert response.status_code == 200  # Stay on login page
            assert b'Invalid password' in response.data or b'error' in response.data.lower()
    
    def test_admin_logout(self):
        """Test admin logout route."""
        with app.test_client() as client:
            response = client.get('/admin/logout')
            assert response.status_code == 302  # Redirect after logout
    
    def test_admin_dashboard_authenticated(self):
        """Test admin dashboard when authenticated."""
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['admin_logged_in'] = True
            
            response = client.get('/admin')
            assert response.status_code == 200
            assert b'Admin Dashboard' in response.data or b'dashboard' in response.data.lower()
    
    def test_admin_dashboard_not_authenticated(self):
        """Test admin dashboard when not authenticated."""
        with app.test_client() as client:
            response = client.get('/admin')
            assert response.status_code == 302  # Redirect to login
    
    def test_admin_analytics_authenticated(self):
        """Test admin analytics API when authenticated."""
        with test_db_manager as db_manager:
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['admin_logged_in'] = True
                
                response = client.get('/admin/analytics')
                assert response.status_code == 200
                
                data = json.loads(response.data)
                assert 'stats' in data
                assert 'top_pages' in data
                assert 'hourly_data' in data
                assert 'referrers' in data
                assert 'popular_searches' in data
    
    def test_admin_analytics_not_authenticated(self):
        """Test admin analytics API when not authenticated."""
        with app.test_client() as client:
            response = client.get('/admin/analytics')
            assert response.status_code == 401
    
    def test_admin_analytics_with_days_parameter(self):
        """Test admin analytics API with days parameter."""
        with test_db_manager as db_manager:
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['admin_logged_in'] = True
                
                response = client.get('/admin/analytics?days=30')
                assert response.status_code == 200
                
                data = json.loads(response.data)
                assert 'stats' in data
    
    def test_require_admin_auth_function(self):
        """Test require_admin_auth function."""
        from app import require_admin_auth
        
        # Test when not authenticated
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['admin_logged_in'] = False
            
            with app.test_request_context():
                response = require_admin_auth()
                assert response.status_code == 302  # Redirect to login
    
    def test_check_admin_auth_function(self):
        """Test check_admin_auth function."""
        from app import check_admin_auth
        
        # Test when not authenticated
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['admin_logged_in'] = False
            
            with app.test_request_context() as ctx:
                ctx.session['admin_logged_in'] = False
                assert check_admin_auth() == False
        
        # Test when authenticated
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['admin_logged_in'] = True
            
            with app.test_request_context() as ctx:
                ctx.session['admin_logged_in'] = True
                assert check_admin_auth() == True
    
    def test_sitemap_route(self):
        """Test sitemap route."""
        with test_db_manager as db_manager:
            # Clear any existing data and insert test data
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM images')  # Clear existing data
            conn.commit()
            
            cursor.execute("""
                INSERT INTO images (file_path, file_name, file_size, file_type, directory_path, volume, subdirectory, file_hash, has_ocr_text, ocr_text_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ('test1.TIF', 'test1.TIF', 1024, 'TIF', 'test', 'VOL00001', 'IMAGES001', 'hash1', True, 'ocr1.txt'))
            
            conn.commit()
            conn.close()
            
            # Test sitemap route
            with app.test_client() as client:
                response = client.get('/sitemap.xml')
                assert response.status_code == 200
                assert b'<?xml' in response.data
                assert b'<urlset' in response.data
    
    def test_robots_txt_route(self):
        """Test robots.txt route."""
        with app.test_client() as client:
            response = client.get('/robots.txt')
            assert response.status_code == 200
            assert b'User-agent' in response.data
            assert b'Disallow' in response.data
    
    def test_help_routes(self):
        """Test all help routes."""
        help_routes = [
            '/help',
            '/help/overview',
            '/help/features',
            '/help/usage',
            '/help/api',
            '/help/installation',
            '/help/context'
        ]
        
        with test_db_manager as db_manager:
            with app.test_client() as client:
                for route in help_routes:
                    response = client.get(route)
                    assert response.status_code == 200, f"Route {route} failed"
    
    def test_help_routes_with_dynamic_data(self):
        """Test help routes with dynamic data."""
        with test_db_manager as db_manager:
            # Clear any existing data and insert test data
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM images')  # Clear existing data
            conn.commit()
            
            cursor.execute("""
                INSERT INTO images (file_path, file_name, file_size, file_type, directory_path, volume, subdirectory, file_hash, has_ocr_text, ocr_text_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ('test1.TIF', 'test1.TIF', 1024, 'TIF', 'test', 'VOL00001', 'IMAGES001', 'hash1', True, 'ocr1.txt'))
            
            conn.commit()
            conn.close()
            
            with app.test_client() as client:
                response = client.get('/help')
                assert response.status_code == 200
                assert b'Help' in response.data
    
    def test_view_image_route_success(self):
        """Test view image route success."""
        with test_db_manager as db_manager:
            # Insert test data
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO images (id, file_path, file_name, file_size, file_type, directory_path, volume, subdirectory, file_hash, has_ocr_text, ocr_text_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (1, 'test1.TIF', 'test1.TIF', 1024, 'TIF', 'test', 'VOL00001', 'IMAGES001', 'hash1', True, 'ocr1.txt'))
            
            conn.commit()
            conn.close()
            
            with app.test_client() as client:
                response = client.get('/view/1')
                assert response.status_code == 200
                assert b'Document Viewer' in response.data or b'viewer' in response.data.lower()
    
    def test_view_image_route_not_found(self):
        """Test view image route not found."""
        with test_db_manager as db_manager:
            with app.test_client() as client:
                response = client.get('/view/999')
                assert response.status_code == 404
    
    def test_home_route_with_images(self):
        """Test home route with images."""
        with test_db_manager as db_manager:
            # Clear any existing data and insert test data
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM images')  # Clear existing data
            conn.commit()
            
            cursor.execute("""
                INSERT INTO images (file_path, file_name, file_size, file_type, directory_path, volume, subdirectory, file_hash, has_ocr_text, ocr_text_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ('test1.TIF', 'test1.TIF', 1024, 'TIF', 'test', 'VOL00001', 'IMAGES001', 'hash1', True, 'ocr1.txt'))
            
            conn.commit()
            conn.close()
            
            with app.test_client() as client:
                response = client.get('/')
                assert response.status_code == 200
                assert b'Epstein Documents Browser' in response.data
    
    def test_home_route_no_images(self):
        """Test home route with no images."""
        with test_db_manager as db_manager:
            with app.test_client() as client:
                response = client.get('/')
                assert response.status_code == 200
                assert b'Epstein Documents Browser' in response.data
    
    def test_api_stats_route(self):
        """Test API stats route."""
        with test_db_manager as db_manager:
            with app.test_client() as client:
                response = client.get('/api/stats')
                assert response.status_code == 200
                
                data = json.loads(response.data)
                assert 'total_images' in data
                assert 'images_with_ocr' in data
                assert 'ocr_percentage' in data
    
    def test_api_first_image_route(self):
        """Test API first image route."""
        with test_db_manager as db_manager:
            # Clear any existing data and insert test data
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM images')  # Clear existing data
            conn.commit()
            
            cursor.execute("""
                INSERT INTO images (file_path, file_name, file_size, file_type, directory_path, volume, subdirectory, file_hash, has_ocr_text, ocr_text_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ('test1.TIF', 'test1.TIF', 1024, 'TIF', 'test', 'VOL00001', 'IMAGES001', 'hash1', True, 'ocr1.txt'))
            
            conn.commit()
            conn.close()
            
            with app.test_client() as client:
                response = client.get('/api/first-image')
                assert response.status_code == 200
                
                data = json.loads(response.data)
                assert 'first_id' in data
                assert 'last_id' in data
    
    def test_api_thumbnail_route_success(self):
        """Test API thumbnail route success."""
        with test_db_manager as db_manager:
            # Clear any existing data and insert test data
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM images')  # Clear existing data
            conn.commit()
            
            cursor.execute("""
                INSERT INTO images (file_path, file_name, file_size, file_type, directory_path, volume, subdirectory, file_hash, has_ocr_text, ocr_text_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ('test1.TIF', 'test1.TIF', 1024, 'TIF', 'test', 'VOL00001', 'IMAGES001', 'hash1', True, 'ocr1.txt'))
            
            conn.commit()
            
            # Get the actual ID that was inserted
            cursor.execute('SELECT id FROM images WHERE file_path = ?', ('test1.TIF',))
            image_id = cursor.fetchone()[0]
            conn.close()
            
            # Mock the DATA_DIR and create the actual file
            with patch('app.DATA_DIR', Path('tests/fixtures/test_data')):
                test_file = Path('tests/fixtures/test_data/test1.TIF')
                test_file.parent.mkdir(parents=True, exist_ok=True)
                test_file.write_bytes(b'fake tif data')
                
                with patch('PIL.Image.open') as mock_open:
                    mock_img = MagicMock()
                    mock_img.mode = 'RGB'
                    mock_img.thumbnail = MagicMock()
                    mock_open.return_value = mock_img
                    
                    with app.test_client() as client:
                        response = client.get(f'/api/thumbnail/{image_id}')
                        assert response.status_code == 200
                        assert response.content_type == 'image/jpeg'
    
    def test_api_thumbnail_route_not_found(self):
        """Test API thumbnail route not found."""
        with test_db_manager as db_manager:
            with app.test_client() as client:
                response = client.get('/api/thumbnail/999')
                assert response.status_code == 500  # 404 is caught and converted to 500
    
    def test_image_route_success(self):
        """Test image route success."""
        with test_db_manager as db_manager:
            # Clear any existing data and insert test data
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM images')  # Clear existing data
            conn.commit()
            
            cursor.execute("""
                INSERT INTO images (file_path, file_name, file_size, file_type, directory_path, volume, subdirectory, file_hash, has_ocr_text, ocr_text_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ('test1.TIF', 'test1.TIF', 1024, 'TIF', 'test', 'VOL00001', 'IMAGES001', 'hash1', True, 'ocr1.txt'))
            
            conn.commit()
            conn.close()
            
            # Mock the image file
            with patch('pathlib.Path.exists', return_value=True):
                with patch('PIL.Image.open') as mock_open:
                    mock_img = MagicMock()
                    mock_img.mode = 'RGB'
                    mock_img.save = MagicMock()
                    mock_open.return_value = mock_img
                    
                    with app.test_client() as client:
                        response = client.get('/image/test1.TIF')
                        assert response.status_code == 200
                        assert response.content_type == 'image/jpeg'
    
    def test_image_route_not_found(self):
        """Test image route not found."""
        with app.test_client() as client:
            response = client.get('/image/nonexistent.TIF')
            assert response.status_code == 404
    
    def test_image_route_security_check(self):
        """Test image route security check."""
        with app.test_client() as client:
            # Try to access file outside data directory
            response = client.get('/image/../../../app.py')
            assert response.status_code == 404  # File doesn't exist, not security violation
    
    def test_image_route_tif_conversion_error(self):
        """Test image route TIF conversion error."""
        with test_db_manager as db_manager:
            # Clear any existing data and insert test data
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM images')  # Clear existing data
            conn.commit()
            
            cursor.execute("""
                INSERT INTO images (file_path, file_name, file_size, file_type, directory_path, volume, subdirectory, file_hash, has_ocr_text, ocr_text_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ('test1.TIF', 'test1.TIF', 1024, 'TIF', 'test', 'VOL00001', 'IMAGES001', 'hash1', True, 'ocr1.txt'))
            
            conn.commit()
            conn.close()
            
            # Mock the image file to cause conversion error
            with patch('app.DATA_DIR', Path('tests/fixtures/test_data')):
                # Create the actual file
                test_file = Path('tests/fixtures/test_data/test1.TIF')
                test_file.parent.mkdir(parents=True, exist_ok=True)
                test_file.write_bytes(b'fake tif data')
                
                with patch('PIL.Image.open', side_effect=Exception("Image conversion error")):
                    with app.test_client() as client:
                        response = client.get('/image/test1.TIF')
                        assert response.status_code == 200  # Falls back to serving original file
    
    def test_image_route_non_tif_file(self):
        """Test image route with non-TIF file."""
        with test_db_manager as db_manager:
            # Clear any existing data and insert test data
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM images')  # Clear existing data
            conn.commit()
            
            cursor.execute("""
                INSERT INTO images (file_path, file_name, file_size, file_type, directory_path, volume, subdirectory, file_hash, has_ocr_text, ocr_text_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ('test1.jpg', 'test1.jpg', 1024, 'JPG', 'test', 'VOL00001', 'IMAGES001', 'hash1', True, 'ocr1.txt'))
            
            conn.commit()
            conn.close()
            
            # Mock the DATA_DIR and create the actual file
            with patch('app.DATA_DIR', Path('tests/fixtures/test_data')):
                test_file = Path('tests/fixtures/test_data/test1.jpg')
                test_file.parent.mkdir(parents=True, exist_ok=True)
                test_file.write_bytes(b'fake jpg data')
                
                with app.test_client() as client:
                    response = client.get('/image/test1.jpg')
                    assert response.status_code == 200
                    assert response.content_type == 'image/jpeg'
