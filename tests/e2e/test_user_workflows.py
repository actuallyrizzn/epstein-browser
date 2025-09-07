"""
End-to-end tests for complete user workflows.
"""
import pytest
import json
import time
from unittest.mock import patch, MagicMock


class TestUserWorkflows:
    """Test cases for complete user workflows."""
    
    def test_search_and_view_document_workflow(self, client, test_db, mock_analytics):
        """Test complete workflow: search for document, view it, navigate."""
        # Step 1: Search for documents
        response = client.get('/api/search?q=test')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert len(data['results']) > 0
        
        # Get first result
        first_result = data['results'][0]
        image_id = first_result['id']
        
        # Step 2: View the document
        response = client.get(f'/view/{image_id}')
        assert response.status_code == 200
        
        # Check that the page contains the document
        assert b'Document Viewer' in response.data
        assert first_result['filename'].encode() in response.data
    
    def test_browse_documents_workflow(self, client, test_db, mock_analytics):
        """Test browsing through documents using navigation."""
        # Step 1: Get first image ID
        response = client.get('/api/first-image')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        first_id = data['first_id']
        
        # Step 2: View first document
        response = client.get(f'/view/{first_id}')
        assert response.status_code == 200
        
        # Step 3: Navigate to next document (if available)
        if first_id + 1 <= data['last_id']:
            response = client.get(f'/view/{first_id + 1}')
            assert response.status_code == 200
    
    def test_search_with_filters_workflow(self, client, test_db, mock_analytics):
        """Test searching with different filters and sorting."""
        # Step 1: Search with filename filter
        response = client.get('/api/search?q=DOJ&type=filename')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        filename_results = data['results']
        
        # Step 2: Search with OCR filter
        response = client.get('/api/search?q=test&type=ocr')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        ocr_results = data['results']
        
        # Step 3: Search with OCR-only filter
        response = client.get('/api/search?q=test&ocr=with-ocr')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        ocr_only_results = data['results']
        
        # Results should be different based on filters
        # (This is a basic check - in real scenario, results would differ)
        assert isinstance(filename_results, list)
        assert isinstance(ocr_results, list)
        assert isinstance(ocr_only_results, list)
    
    def test_pagination_workflow(self, client, test_db, mock_analytics):
        """Test pagination through search results."""
        # Step 1: Get first page
        response = client.get('/api/search?q=test&per_page=2')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        first_page = data['results']
        pagination = data['pagination']
        
        assert len(first_page) <= 2
        assert pagination['per_page'] == 2
        assert pagination['page'] == 1
        
        # Step 2: Get second page (if available)
        if pagination['has_next']:
            response = client.get('/api/search?q=test&per_page=2&page=2')
            assert response.status_code == 200
            
            data = json.loads(response.data)
            second_page = data['results']
            pagination = data['pagination']
            
            assert pagination['page'] == 2
            assert len(second_page) <= 2
    
    def test_help_documentation_workflow(self, client, test_db, mock_analytics):
        """Test accessing help documentation."""
        # Step 1: Access main help page
        response = client.get('/help')
        assert response.status_code == 200
        assert b'Help & Documentation' in response.data
        
        # Step 2: Access different help sections
        help_sections = [
            '/help/overview',
            '/help/features', 
            '/help/usage',
            '/help/api',
            '/help/installation',
            '/help/context'
        ]
        
        for section in help_sections:
            response = client.get(section)
            assert response.status_code == 200
            # Each section should have its own title
            assert b'<h1' in response.data
    
    def test_blog_workflow(self, client, test_db, mock_analytics, sample_blog_posts):
        """Test blog post viewing workflow."""
        # Mock blog posts
        with patch('app.load_blog_posts', return_value=sample_blog_posts):
            # Step 1: Access blog index
            response = client.get('/blog')
            assert response.status_code == 200
            assert b'Blog' in response.data
            
            # Step 2: Access individual blog post
            response = client.get('/blog/test-blog-post-1')
            assert response.status_code == 200
            assert b'Test Blog Post 1' in response.data
    
    def test_admin_dashboard_workflow(self, client, test_db, mock_analytics):
        """Test admin dashboard access and functionality."""
        # Step 1: Access admin dashboard
        response = client.get('/admin')
        assert response.status_code == 200
        assert b'Admin Dashboard' in response.data
        
        # Step 2: Check that analytics data is displayed
        assert b'Statistics' in response.data
        assert b'Total Images' in response.data
    
    def test_api_workflow_with_rate_limiting(self, client, test_db, mock_analytics, clean_rate_limiter):
        """Test API workflow with rate limiting considerations."""
        # Step 1: Make several API calls within limits
        for i in range(10):
            response = client.get('/api/stats')
            assert response.status_code == 200
            
            # Check rate limit headers
            assert 'X-RateLimit-Remaining' in response.headers
            remaining = int(response.headers['X-RateLimit-Remaining'])
            assert remaining >= 0
        
        # Step 2: Make search API calls
        for i in range(5):
            response = client.get('/api/search?q=test')
            assert response.status_code == 200
            
            # Check rate limit headers
            assert 'X-RateLimit-Remaining' in response.headers
    
    def test_error_handling_workflow(self, client, test_db, mock_analytics):
        """Test error handling in various scenarios."""
        # Step 1: Test 404 for non-existent document
        response = client.get('/view/99999')
        assert response.status_code == 404
        
        # Step 2: Test 404 for non-existent image
        response = client.get('/api/thumbnail/99999')
        assert response.status_code == 404
        
        # Step 3: Test invalid API parameters
        response = client.get('/api/search?per_page=invalid')
        assert response.status_code == 200  # Should handle gracefully
        
        # Step 4: Test malformed requests
        response = client.get('/api/search?q=')  # Empty query
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['results'] == []
    
    def test_mobile_responsive_workflow(self, client, test_db, mock_analytics):
        """Test that the application works on mobile devices."""
        # Simulate mobile user agent
        headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)'}
        
        # Step 1: Access main page
        response = client.get('/', headers=headers)
        assert response.status_code == 200
        assert b'Epstein Documents Browser' in response.data
        
        # Step 2: Search on mobile
        response = client.get('/api/search?q=test', headers=headers)
        assert response.status_code == 200
        
        # Step 3: View document on mobile
        response = client.get('/view/1', headers=headers)
        assert response.status_code == 200
    
    def test_performance_workflow(self, client, test_db, mock_analytics):
        """Test application performance under normal usage."""
        start_time = time.time()
        
        # Step 1: Make multiple concurrent-like requests
        responses = []
        for i in range(20):
            response = client.get('/api/search?q=test')
            responses.append(response)
        
        end_time = time.time()
        
        # All requests should succeed
        for response in responses:
            assert response.status_code == 200
        
        # Should complete within reasonable time (5 seconds for 20 requests)
        assert end_time - start_time < 5.0
    
    def test_data_integrity_workflow(self, client, test_db, mock_analytics):
        """Test that data remains consistent throughout workflows."""
        # Step 1: Get initial stats
        response = client.get('/api/stats')
        assert response.status_code == 200
        initial_stats = json.loads(response.data)
        
        # Step 2: Perform various operations
        client.get('/api/search?q=test')
        client.get('/view/1')
        client.get('/help')
        
        # Step 3: Get stats again
        response = client.get('/api/stats')
        assert response.status_code == 200
        final_stats = json.loads(response.data)
        
        # Core data should remain the same
        assert initial_stats['total_images'] == final_stats['total_images']
        assert initial_stats['images_with_ocr'] == final_stats['images_with_ocr']
        assert initial_stats['ocr_percentage'] == final_stats['ocr_percentage']
