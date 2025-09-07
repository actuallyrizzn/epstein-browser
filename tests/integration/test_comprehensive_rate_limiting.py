"""
Comprehensive rate limiting tests for all endpoints.
"""
import pytest
import json
import time
from unittest.mock import patch


class TestComprehensiveRateLimiting:
    """Comprehensive test cases for rate limiting on all endpoints."""
    
    @pytest.mark.rate_limit
    def test_all_endpoints_have_rate_limiting(self, client, test_db, mock_analytics, clean_rate_limiter):
        """Test that all API endpoints have rate limiting applied."""
        endpoints = [
            ('/api/search?q=test', 'search', 60),
            ('/api/stats', 'stats', 300),
            ('/api/first-image', 'stats', 300),
            ('/api/thumbnail/1', 'image', 200),
            ('/image/Prod%2001_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-001.TIF', 'image', 200),
        ]
        
        for endpoint, expected_type, expected_limit in endpoints:
            # Make a request and check headers
            response = client.get(endpoint)
            
            # Should have rate limit headers (except for 500 and 404 errors)
            if response.status_code not in [500, 404]:
                assert 'X-RateLimit-Limit' in response.headers, f"Missing rate limit headers for {endpoint}"
                assert 'X-RateLimit-Remaining' in response.headers
                assert 'X-RateLimit-Reset' in response.headers
                
                # Check limit value
                limit = int(response.headers['X-RateLimit-Limit'])
                assert limit == expected_limit, f"Wrong limit for {endpoint}: expected {expected_limit}, got {limit}"
    
    @pytest.mark.rate_limit
    def test_rate_limiting_consistency_across_endpoints(self, client, test_db, mock_analytics, clean_rate_limiter):
        """Test that rate limiting is consistent across similar endpoints."""
        # Test that image endpoints have same limits
        response1 = client.get('/api/thumbnail/1')
        response2 = client.get('/image/Prod%2001_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-001.TIF')
        
        if response1.status_code == 200 and response2.status_code == 200:
            assert response1.headers['X-RateLimit-Limit'] == response2.headers['X-RateLimit-Limit']
        
        # Test that stats endpoints have same limits
        response1 = client.get('/api/stats')
        response2 = client.get('/api/first-image')
        
        assert response1.headers['X-RateLimit-Limit'] == response2.headers['X-RateLimit-Limit']
    
    @pytest.mark.rate_limit
    def test_rate_limiting_under_load(self, client, test_db, mock_analytics, clean_rate_limiter):
        """Test rate limiting under various load conditions."""
        # Test rapid requests
        start_time = time.time()
        responses = []
        
        for i in range(100):  # More than any single limit
            response = client.get('/api/search?q=test')
            responses.append(response)
            
            if response.status_code == 429:
                break
        
        end_time = time.time()
        
        # Should hit rate limit quickly
        assert end_time - start_time < 2.0, "Rate limiting should kick in quickly"
        
        # Should have some 429 responses
        status_codes = [r.status_code for r in responses]
        assert 429 in status_codes, "Should have rate limited responses"
    
    @pytest.mark.rate_limit
    def test_rate_limiting_recovery_after_window(self, client, test_db, mock_analytics, clean_rate_limiter):
        """Test that rate limits recover after the time window."""
        # Exhaust search limit
        for i in range(60):
            response = client.get('/api/search?q=test')
            assert response.status_code == 200
        
        # Should be rate limited
        response = client.get('/api/search?q=test')
        assert response.status_code == 429
        
        # Mock time to simulate window reset
        with patch('time.time', return_value=time.time() + 70):
            # Should be allowed again
            response = client.get('/api/search?q=test')
            assert response.status_code == 200
            
            # Should have full limit again
            remaining = int(response.headers['X-RateLimit-Remaining'])
            assert remaining == 59  # One less than full limit
    
    @pytest.mark.rate_limit
    def test_rate_limiting_headers_accuracy(self, client, test_db, mock_analytics, clean_rate_limiter):
        """Test that rate limiting headers are accurate throughout the window."""
        # Track headers over multiple requests
        headers_history = []
        
        for i in range(10):
            response = client.get('/api/search?q=test')
            assert response.status_code == 200
            
            headers = {
                'limit': int(response.headers['X-RateLimit-Limit']),
                'remaining': int(response.headers['X-RateLimit-Remaining']),
                'reset': int(response.headers['X-RateLimit-Reset'])
            }
            headers_history.append(headers)
        
        # Check consistency
        for i, headers in enumerate(headers_history):
            assert headers['limit'] == 60, f"Limit should be 60, got {headers['limit']}"
            assert headers['remaining'] == 60 - i - 1, f"Remaining should decrease, got {headers['remaining']}"
            assert headers['reset'] > time.time(), "Reset time should be in the future"
    
    @pytest.mark.rate_limit
    def test_rate_limiting_error_response_quality(self, client, test_db, mock_analytics, clean_rate_limiter):
        """Test that rate limiting error responses are informative."""
        # Exhaust the limit
        for i in range(60):
            client.get('/api/search?q=test')
        
        # Get rate limited response
        response = client.get('/api/search?q=test')
        assert response.status_code == 429
        
        # Check response content
        data = json.loads(response.data)
        
        # Required fields
        assert 'error' in data
        assert 'message' in data
        assert 'retry_after' in data
        
        # Field values
        assert data['error'] == 'Rate limit exceeded'
        assert 'Too many requests' in data['message']
        assert '60 requests per 60 seconds' in data['message']
        assert isinstance(data['retry_after'], int)
        assert data['retry_after'] > 0
        
        # Headers
        assert 'Retry-After' in response.headers
        assert response.headers['Retry-After'] == str(data['retry_after'])
    
    @pytest.mark.rate_limit
    def test_rate_limiting_different_user_agents(self, client, test_db, mock_analytics, clean_rate_limiter):
        """Test that rate limiting works with different user agents."""
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)',
            'curl/7.68.0',
            'Python-requests/2.25.1'
        ]
        
        for ua in user_agents:
            response = client.get('/api/search?q=test', headers={'User-Agent': ua})
            assert response.status_code == 200
            assert 'X-RateLimit-Limit' in response.headers
    
    @pytest.mark.rate_limit
    def test_rate_limiting_concurrent_requests(self, client, test_db, mock_analytics, clean_rate_limiter):
        """Test rate limiting with concurrent-like requests."""
        # Simulate concurrent requests by making rapid requests
        responses = []
        
        # Make requests as fast as possible
        for i in range(100):
            response = client.get('/api/search?q=test')
            responses.append(response)
            
            # Stop if we hit rate limit
            if response.status_code == 429:
                break
        
        # Should have some successful and some rate limited
        success_count = sum(1 for r in responses if r.status_code == 200)
        rate_limited_count = sum(1 for r in responses if r.status_code == 429)
        
        assert success_count > 0, "Should have some successful requests"
        assert rate_limited_count > 0, "Should have some rate limited requests"
        assert success_count + rate_limited_count == len(responses), "All requests should be accounted for"
    
    @pytest.mark.rate_limit
    def test_rate_limiting_memory_efficiency(self, client, test_db, mock_analytics, clean_rate_limiter):
        """Test that rate limiter doesn't accumulate excessive memory."""
        # Make many requests over time
        for i in range(1000):
            with patch('time.time', return_value=time.time() + i):
                response = client.get('/api/search?q=test')
                
                # Should not fail due to memory issues
                assert response.status_code in [200, 429]
        
        # Rate limiter should still work
        response = client.get('/api/search?q=test')
        assert response.status_code in [200, 429]
    
    @pytest.mark.rate_limit
    def test_rate_limiting_edge_cases(self, client, test_db, mock_analytics, clean_rate_limiter):
        """Test rate limiting edge cases."""
        # Test with empty query
        response = client.get('/api/search?q=')
        assert response.status_code == 200
        assert 'X-RateLimit-Limit' in response.headers
        
        # Test with very long query
        long_query = 'a' * 1000
        response = client.get(f'/api/search?q={long_query}')
        assert response.status_code == 200
        assert 'X-RateLimit-Limit' in response.headers
        
        # Test with special characters
        special_query = 'test+query+with+special=chars&more=stuff'
        response = client.get(f'/api/search?q={special_query}')
        assert response.status_code == 200
        assert 'X-RateLimit-Limit' in response.headers
