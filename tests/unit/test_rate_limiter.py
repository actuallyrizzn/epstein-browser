"""
Unit tests for the rate limiter functionality.
"""
import pytest
import time
from unittest.mock import patch
from app import RateLimiter


class TestRateLimiter:
    """Test cases for the RateLimiter class."""
    
    def test_rate_limiter_initialization(self):
        """Test that rate limiter initializes with correct limits."""
        limiter = RateLimiter()
        
        assert limiter.limits['search'] == (60, 60)
        assert limiter.limits['image'] == (200, 60)
        assert limiter.limits['stats'] == (300, 60)
        assert limiter.limits['default'] == (100, 60)
        assert len(limiter.requests) == 0
    
    def test_is_allowed_within_limits(self):
        """Test that requests within limits are allowed."""
        limiter = RateLimiter()
        ip = '192.168.1.1'
        
        # Should allow requests within the limit
        for i in range(10):
            allowed, limit, window = limiter.is_allowed(ip, 'search')
            assert allowed is True
            assert limit == 60
            assert window == 60
    
    def test_is_allowed_exceeds_limits(self):
        """Test that requests exceeding limits are blocked."""
        limiter = RateLimiter()
        ip = '192.168.1.1'
        
        # Make requests up to the limit
        for i in range(60):
            allowed, limit, window = limiter.is_allowed(ip, 'search')
            assert allowed is True
        
        # Next request should be blocked
        allowed, limit, window = limiter.is_allowed(ip, 'search')
        assert allowed is False
        assert limit == 60
        assert window == 60
    
    def test_different_ips_separate_limits(self):
        """Test that different IPs have separate rate limits."""
        limiter = RateLimiter()
        ip1 = '192.168.1.1'
        ip2 = '192.168.1.2'
        
        # Exhaust limit for ip1
        for i in range(60):
            allowed, _, _ = limiter.is_allowed(ip1, 'search')
            assert allowed is True
        
        # ip1 should be blocked
        allowed, _, _ = limiter.is_allowed(ip1, 'search')
        assert allowed is False
        
        # ip2 should still be allowed
        allowed, _, _ = limiter.is_allowed(ip2, 'search')
        assert allowed is True
    
    def test_different_endpoints_separate_limits(self):
        """Test that different endpoint types have separate limits."""
        limiter = RateLimiter()
        ip = '192.168.1.1'
        
        # Exhaust search limit
        for i in range(60):
            allowed, _, _ = limiter.is_allowed(ip, 'search')
            assert allowed is True
        
        # Search should be blocked
        allowed, _, _ = limiter.is_allowed(ip, 'search')
        assert allowed is False
        
        # Image endpoint should still be allowed
        allowed, _, _ = limiter.is_allowed(ip, 'image')
        assert allowed is True
    
    def test_cleanup_old_requests(self):
        """Test that old requests are cleaned up from the sliding window."""
        limiter = RateLimiter()
        ip = '192.168.1.1'
        
        # Make some requests
        for i in range(10):
            limiter.is_allowed(ip, 'search')
        
        # Mock time to simulate passage of time
        with patch('time.time', return_value=time.time() + 70):
            # Should clean up old requests and allow new ones
            allowed, limit, window = limiter.is_allowed(ip, 'search')
            assert allowed is True
    
    def test_get_remaining_requests(self):
        """Test getting remaining request count."""
        limiter = RateLimiter()
        ip = '192.168.1.1'
        
        # Initially should have full limit
        remaining = limiter.get_remaining(ip, 'search')
        assert remaining == 60
        
        # Make some requests
        for i in range(10):
            limiter.is_allowed(ip, 'search')
        
        # Should have fewer remaining
        remaining = limiter.get_remaining(ip, 'search')
        assert remaining == 50
    
    def test_unknown_endpoint_type_defaults(self):
        """Test that unknown endpoint types use default limits."""
        limiter = RateLimiter()
        ip = '192.168.1.1'
        
        allowed, limit, window = limiter.is_allowed(ip, 'unknown_endpoint')
        assert allowed is True
        assert limit == 100  # default limit
        assert window == 60  # default window
    
    def test_rate_limiter_memory_efficiency(self):
        """Test that rate limiter doesn't accumulate memory indefinitely."""
        limiter = RateLimiter()
        ip = '192.168.1.1'
        
        # Make many requests over time
        for i in range(1000):
            with patch('time.time', return_value=time.time() + i):
                limiter.is_allowed(ip, 'search')
        
        # Should only have recent requests in memory
        requests = limiter.requests[ip]['search']
        assert len(requests) <= 60  # Should not exceed the limit
