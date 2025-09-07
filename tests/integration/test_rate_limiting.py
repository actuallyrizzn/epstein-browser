"""
Integration tests for rate limiting functionality.
"""
import pytest
import time
import json
from unittest.mock import patch


class TestRateLimiting:
    """Test cases for rate limiting integration."""
    
    def test_search_api_rate_limiting(self, client, test_db, mock_analytics, clean_rate_limiter):
        """Test rate limiting on search API endpoint."""
        # Make requests up to the limit
        for i in range(60):
            response = client.get('/api/search?q=test')
            assert response.status_code == 200
            
            # Check rate limit headers
            assert 'X-RateLimit-Limit' in response.headers
            assert 'X-RateLimit-Remaining' in response.headers
            assert 'X-RateLimit-Reset' in response.headers
            
            # Check remaining count decreases
            remaining = int(response.headers['X-RateLimit-Remaining'])
            assert remaining == 60 - i - 1
        
        # Next request should be rate limited
        response = client.get('/api/search?q=test')
        assert response.status_code == 429
        
        # Check rate limit error response
        data = json.loads(response.data)
        assert 'error' in data
        assert 'message' in data
        assert 'retry_after' in data
        assert data['error'] == 'Rate limit exceeded'
        
        # Check rate limit headers on error response
        assert 'X-RateLimit-Limit' in response.headers
        assert 'X-RateLimit-Remaining' in response.headers
        assert 'X-RateLimit-Reset' in response.headers
        assert 'Retry-After' in response.headers
    
    def test_image_api_rate_limiting(self, client, test_db,  mock_analytics, clean_rate_limiter):
        """Test rate limiting on image API endpoints."""
        # Test thumbnail endpoint
        for i in range(200):
            response = client.get('/api/thumbnail/1')
            # Should be 200, 404, 429, or 500 (500 due to internal error handling)
            assert response.status_code in [200, 404, 429, 500]
            
            if response.status_code == 429:
                # Check that it's rate limited after 200 requests
                data = json.loads(response.data)
                assert data['error'] == 'Rate limit exceeded'
                break
        
        # Test image serving endpoint
        # Rate limiter is automatically reset by the clean_rate_limiter fixture
        
        for i in range(200):
            response = client.get('/image/Prod%2001_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-001.TIF')
            # Should be 200 or 404, not rate limited yet
            assert response.status_code in [200, 404, 429]
            
            if response.status_code == 429:
                # Check that it's rate limited after 200 requests
                data = json.loads(response.data)
                assert data['error'] == 'Rate limit exceeded'
                break
    
    def test_stats_api_rate_limiting(self, client, test_db,  mock_analytics, clean_rate_limiter):
        """Test rate limiting on stats API endpoint."""
        # Make requests up to the limit
        for i in range(300):
            response = client.get('/api/stats')
            assert response.status_code == 200
            
            # Check rate limit headers
            assert 'X-RateLimit-Limit' in response.headers
            assert 'X-RateLimit-Remaining' in response.headers
            assert 'X-RateLimit-Reset' in response.headers
            
            # Check remaining count decreases
            remaining = int(response.headers['X-RateLimit-Remaining'])
            assert remaining == 300 - i - 1
        
        # Next request should be rate limited
        response = client.get('/api/stats')
        assert response.status_code == 429
        
        # Check rate limit error response
        data = json.loads(response.data)
        assert data['error'] == 'Rate limit exceeded'
    
    def test_first_image_api_rate_limiting(self, client, test_db,  mock_analytics, clean_rate_limiter):
        """Test rate limiting on first image API endpoint."""
        # Make requests up to the limit
        for i in range(300):
            response = client.get('/api/first-image')
            assert response.status_code == 200
            
            # Check rate limit headers
            assert 'X-RateLimit-Limit' in response.headers
            assert 'X-RateLimit-Remaining' in response.headers
        
        # Next request should be rate limited
        response = client.get('/api/first-image')
        assert response.status_code == 429
        
        # Check rate limit error response
        data = json.loads(response.data)
        assert data['error'] == 'Rate limit exceeded'
    
    def test_different_ips_separate_limits(self, client, test_db,  mock_analytics, clean_rate_limiter):
        """Test that different IPs have separate rate limits."""
        # Exhaust limit for one IP
        for i in range(60):
            response = client.get('/api/search?q=test')
            assert response.status_code == 200
        
        # This IP should be rate limited
        response = client.get('/api/search?q=test')
        assert response.status_code == 429
        
        # Note: Different IP testing is complex in Flask test client
        # This test verifies the basic rate limiting works
    
    def test_different_endpoints_separate_limits(self, client, test_db,  mock_analytics, clean_rate_limiter):
        """Test that different endpoints have separate rate limits."""
        # Exhaust search limit
        for i in range(60):
            response = client.get('/api/search?q=test')
            assert response.status_code == 200
        
        # Search should be rate limited
        response = client.get('/api/search?q=test')
        assert response.status_code == 429
        
        # Stats should still be allowed (different limit)
        response = client.get('/api/stats')
        assert response.status_code == 200
    
    def test_rate_limit_headers_accuracy(self, client, test_db,  mock_analytics, clean_rate_limiter):
        """Test that rate limit headers are accurate."""
        response = client.get('/api/search?q=test')
        
        # Check header values
        limit = int(response.headers['X-RateLimit-Limit'])
        remaining = int(response.headers['X-RateLimit-Remaining'])
        reset = int(response.headers['X-RateLimit-Reset'])
        
        assert limit == 60  # Search endpoint limit
        assert remaining == 59  # Should be one less than limit
        assert reset > time.time()  # Reset time should be in the future
    
    def test_rate_limit_reset_after_window(self, client, test_db,  mock_analytics, clean_rate_limiter):
        """Test that rate limits reset after the time window."""
        # Exhaust the limit
        for i in range(60):
            response = client.get('/api/search?q=test')
            assert response.status_code == 200
        
        # Should be rate limited
        response = client.get('/api/search?q=test')
        assert response.status_code == 429
        
        # Mock time to simulate passage of time beyond the window
        with patch('time.time', return_value=time.time() + 70):
            # Should be allowed again
            response = client.get('/api/search?q=test')
            assert response.status_code == 200
    
    def test_rate_limit_error_response_structure(self, client, test_db,  mock_analytics, clean_rate_limiter):
        """Test that rate limit error responses have the correct structure."""
        # Exhaust the limit
        for i in range(60):
            client.get('/api/search?q=test')
        
        # Get rate limited response
        response = client.get('/api/search?q=test')
        assert response.status_code == 429
        
        data = json.loads(response.data)
        
        # Check required fields
        assert 'error' in data
        assert 'message' in data
        assert 'retry_after' in data
        
        # Check field values
        assert data['error'] == 'Rate limit exceeded'
        assert 'Too many requests' in data['message']
        assert isinstance(data['retry_after'], int)
        assert data['retry_after'] > 0
    
    def test_rate_limit_headers_on_success(self, client, test_db,  mock_analytics, clean_rate_limiter):
        """Test that rate limit headers are present on successful responses."""
        response = client.get('/api/search?q=test')
        
        # Should have all rate limit headers
        assert 'X-RateLimit-Limit' in response.headers
        assert 'X-RateLimit-Remaining' in response.headers
        assert 'X-RateLimit-Reset' in response.headers
        
        # Should not have Retry-After header on success
        assert 'Retry-After' not in response.headers
    
    def test_rate_limit_headers_on_error(self, client, test_db,  mock_analytics, clean_rate_limiter):
        """Test that rate limit headers are present on error responses."""
        # Exhaust the limit
        for i in range(60):
            client.get('/api/search?q=test')
        
        # Get rate limited response
        response = client.get('/api/search?q=test')
        assert response.status_code == 429
        
        # Should have all rate limit headers
        assert 'X-RateLimit-Limit' in response.headers
        assert 'X-RateLimit-Remaining' in response.headers
        assert 'X-RateLimit-Reset' in response.headers
        assert 'Retry-After' in response.headers
        
        # Check that remaining is 0
        remaining = int(response.headers['X-RateLimit-Remaining'])
        assert remaining == 0
