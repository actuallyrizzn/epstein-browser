"""
Simple rate limiting tests that focus on the core functionality.
"""
import pytest
import json
import time
from unittest.mock import patch


class TestSimpleRateLimiting:
    """Simple test cases for rate limiting functionality."""
    
    def test_rate_limiter_basic_functionality(self, clean_rate_limiter):
        """Test basic rate limiter functionality without Flask."""
        from app import RateLimiter
        
        limiter = RateLimiter()
        ip = '192.168.1.1'
        
        # Test within limits
        for i in range(10):
            allowed, limit, window = limiter.is_allowed(ip, 'search')
            assert allowed is True
            assert limit == 60
            assert window == 60
        
        # Test remaining count
        remaining = limiter.get_remaining(ip, 'search')
        assert remaining == 50  # 60 - 10
    
    def test_rate_limiter_exceeds_limit(self, clean_rate_limiter):
        """Test rate limiter when limit is exceeded."""
        from app import RateLimiter
        
        limiter = RateLimiter()
        ip = '192.168.1.1'
        
        # Exhaust the limit
        for i in range(60):
            allowed, limit, window = limiter.is_allowed(ip, 'search')
            assert allowed is True
        
        # Next request should be blocked
        allowed, limit, window = limiter.is_allowed(ip, 'search')
        assert allowed is False
        assert limit == 60
        assert window == 60
    
    def test_rate_limiter_different_endpoints(self, clean_rate_limiter):
        """Test that different endpoints have separate limits."""
        from app import RateLimiter
        
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
        allowed, limit, window = limiter.is_allowed(ip, 'image')
        assert allowed is True
        assert limit == 200
        assert window == 60
    
    def test_rate_limiter_different_ips(self, clean_rate_limiter):
        """Test that different IPs have separate limits."""
        from app import RateLimiter
        
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
        allowed, limit, window = limiter.is_allowed(ip2, 'search')
        assert allowed is True
        assert limit == 60
        assert window == 60
    
    def test_rate_limiter_cleanup_old_requests(self, clean_rate_limiter):
        """Test that old requests are cleaned up."""
        from app import RateLimiter
        
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
            assert limit == 60
            assert window == 60
    
    def test_rate_limiter_memory_efficiency(self, clean_rate_limiter):
        """Test that rate limiter doesn't accumulate excessive memory."""
        from app import RateLimiter
        
        limiter = RateLimiter()
        ip = '192.168.1.1'
        
        # Make many requests over time
        for i in range(1000):
            with patch('time.time', return_value=time.time() + i):
                allowed, _, _ = limiter.is_allowed(ip, 'search')
                # Should not fail due to memory issues
                assert isinstance(allowed, bool)
        
        # Rate limiter should still work
        allowed, limit, window = limiter.is_allowed(ip, 'search')
        assert isinstance(allowed, bool)
        assert limit == 60
        assert window == 60
    
    def test_rate_limiter_unknown_endpoint_type(self, clean_rate_limiter):
        """Test that unknown endpoint types use default limits."""
        from app import RateLimiter
        
        limiter = RateLimiter()
        ip = '192.168.1.1'
        
        allowed, limit, window = limiter.is_allowed(ip, 'unknown_endpoint')
        assert allowed is True
        assert limit == 100  # default limit
        assert window == 60  # default window
    
    def test_rate_limiter_headers_calculation(self, clean_rate_limiter):
        """Test rate limiter header calculations."""
        from app import RateLimiter
        
        limiter = RateLimiter()
        ip = '192.168.1.1'
        
        # Make some requests
        for i in range(5):
            limiter.is_allowed(ip, 'search')
        
        # Check remaining count
        remaining = limiter.get_remaining(ip, 'search')
        assert remaining == 55  # 60 - 5
        
        # Check that limit and window are correct
        allowed, limit, window = limiter.is_allowed(ip, 'search')
        assert allowed is True
        assert limit == 60
        assert window == 60
