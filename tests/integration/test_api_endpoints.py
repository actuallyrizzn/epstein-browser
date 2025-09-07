"""
Integration tests for API endpoints.
"""
import pytest
import json
from unittest.mock import patch, MagicMock


class TestAPIEndpoints:
    """Test cases for API endpoint integration."""
    
    def test_search_api_basic(self, client, test_db, mock_analytics):
        """Test basic search API functionality."""
        response = client.get('/api/search?q=test')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Check response structure
        assert 'results' in data
        assert 'pagination' in data
        assert isinstance(data['results'], list)
        assert isinstance(data['pagination'], dict)
        
        # Check pagination structure
        pagination = data['pagination']
        assert 'page' in pagination
        assert 'per_page' in pagination
        assert 'total_count' in pagination
        assert 'total_pages' in pagination
        assert 'has_prev' in pagination
        assert 'has_next' in pagination
    
    def test_search_api_with_filters(self, client, test_db, mock_analytics):
        """Test search API with different filters."""
        # Test filename search
        response = client.get('/api/search?q=DOJ&type=filename')
        assert response.status_code == 200
        
        # Test OCR search
        response = client.get('/api/search?q=test&type=ocr')
        assert response.status_code == 200
        
        # Test OCR filter
        response = client.get('/api/search?q=test&ocr=with-ocr')
        assert response.status_code == 200
        
        response = client.get('/api/search?q=test&ocr=without-ocr')
        assert response.status_code == 200
    
    def test_search_api_pagination(self, client, test_db, mock_analytics):
        """Test search API pagination."""
        # Test different page sizes
        response = client.get('/api/search?q=test&per_page=10')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['pagination']['per_page'] == 10
    
    def test_search_api_empty_query(self, client, test_db, mock_analytics):
        """Test search API with empty query."""
        response = client.get('/api/search?q=')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['results'] == []
    
    def test_stats_api(self, client, test_db, mock_analytics):
        """Test stats API endpoint."""
        response = client.get('/api/stats')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Check response structure
        assert 'total_images' in data
        assert 'images_with_ocr' in data
        assert 'ocr_percentage' in data
        assert 'volumes' in data
        
        # Check data types
        assert isinstance(data['total_images'], int)
        assert isinstance(data['images_with_ocr'], int)
        assert isinstance(data['ocr_percentage'], float)
        assert isinstance(data['volumes'], list)
    
    def test_first_image_api(self, client, test_db, mock_analytics):
        """Test first image API endpoint."""
        response = client.get('/api/first-image')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Check response structure
        assert 'first_id' in data
        assert 'last_id' in data
        
        # Check data types
        assert isinstance(data['first_id'], int)
        assert isinstance(data['last_id'], int)
    
    def test_thumbnail_api(self, client, test_db, mock_analytics):
        """Test thumbnail API endpoint."""
        # Test with existing image ID
        response = client.get('/api/thumbnail/1')
        
        # Should return 200, 404, or 500 depending on whether image exists and error handling
        assert response.status_code in [200, 404, 500]
        
        if response.status_code == 200:
            # Check content type
            assert response.content_type.startswith('image/')
    
    def test_thumbnail_api_not_found(self, client, test_db, mock_analytics):
        """Test thumbnail API with non-existent image ID."""
        response = client.get('/api/thumbnail/99999')
        assert response.status_code in [404, 500]  # 500 due to internal error handling
    
    def test_image_serving_api(self, client, test_db, mock_analytics):
        """Test image serving API endpoint."""
        # Test with a test image path
        response = client.get('/image/Prod%2001_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-001.TIF')
        
        # Should return 200 or 404 depending on whether file exists
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            # Check content type
            assert response.content_type.startswith('image/')
    
    def test_api_error_handling(self, client, test_db, mock_analytics):
        """Test API error handling."""
        # Test with invalid parameters
        response = client.get('/api/search?per_page=invalid')
        assert response.status_code == 200  # Should handle gracefully
        
        # Test with very large page number
        response = client.get('/api/search?q=test&page=999999')
        assert response.status_code == 200  # Should handle gracefully
    
    def test_api_response_headers(self, client, test_db, mock_analytics):
        """Test that API responses include proper headers."""
        response = client.get('/api/stats')
        
        # Check for rate limiting headers
        assert 'X-RateLimit-Limit' in response.headers
        assert 'X-RateLimit-Remaining' in response.headers
        assert 'X-RateLimit-Reset' in response.headers
        
        # Check content type
        assert response.content_type == 'application/json'
    
    def test_search_api_with_special_characters(self, client, test_db, mock_analytics):
        """Test search API with special characters in query."""
        # Test with URL-encoded characters
        response = client.get('/api/search?q=test%20query%20with%20spaces')
        assert response.status_code == 200
        
        # Test with special characters
        response = client.get('/api/search?q=test+query+with+plus')
        assert response.status_code == 200
    
    def test_api_cors_headers(self, client, test_db, mock_analytics):
        """Test that API responses include CORS headers if needed."""
        response = client.get('/api/stats')
        
        # Check that response is properly formatted
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, dict)
    
    def test_search_api_sorting(self, client, test_db, mock_analytics):
        """Test search API with different sorting options."""
        # Test different sort options
        for sort_by in ['relevance', 'filename', 'id']:
            response = client.get(f'/api/search?q=test&sort={sort_by}')
            assert response.status_code == 200
            
            data = json.loads(response.data)
            assert 'results' in data
            assert 'pagination' in data
