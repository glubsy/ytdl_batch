"""
Test module for access token caching functionality.
"""

import unittest
import tempfile
import json
import time
from pathlib import Path
from unittest.mock import patch, Mock
import sys
import os

# Add the project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Set up environment for testing
os.environ['TWITCH_CLIENT_ID'] = 'test_id'
os.environ['TWITCH_CLIENT_SECRET'] = 'test_secret'


class TestTokenCaching(unittest.TestCase):
    """Test access token caching functionality."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary cache file for testing
        self.temp_cache = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        self.temp_cache_path = Path(self.temp_cache.name)
        self.temp_cache.close()
        
        # Patch the cache file location
        self.cache_patcher = patch('twitch.fetch_vods.TOKEN_CACHE_FILE', self.temp_cache_path)
        self.cache_patcher.start()
        
        # Import after patching
        from twitch.fetch_vods import get_access_token, clear_token_cache
        self.get_access_token = get_access_token
        self.clear_token_cache = clear_token_cache
    
    def tearDown(self):
        """Clean up test environment."""
        self.cache_patcher.stop()
        
        # Clean up temporary cache file
        if self.temp_cache_path.exists():
            self.temp_cache_path.unlink()
    
    def test_token_caching_new_token(self):
        """Test that a new token is requested and cached when no cache exists."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'access_token': 'test_token_12345',
            'expires_in': 3600
        }
        mock_response.raise_for_status.return_value = None
        
        with patch('requests.post', return_value=mock_response):
            with patch('builtins.print'):  # Suppress print statements
                token = self.get_access_token('test_id', 'test_secret')
        
        self.assertEqual(token, 'test_token_12345')
        
        # Verify cache file was created
        self.assertTrue(self.temp_cache_path.exists())
        
        # Verify cache content
        with open(self.temp_cache_path, 'r') as f:
            cache_data = json.load(f)
        
        self.assertEqual(cache_data['access_token'], 'test_token_12345')
        self.assertEqual(cache_data['expires_in'], 3600)
        self.assertIn('expires_at', cache_data)
        self.assertIn('created_at', cache_data)
    
    def test_token_caching_use_cached_token(self):
        """Test that cached token is used when still valid."""
        # Create a valid cache file
        future_time = time.time() + 7200  # 2 hours from now
        cache_data = {
            'access_token': 'cached_token_67890',
            'expires_in': 7200,
            'expires_at': future_time,
            'created_at': time.time() - 1800  # Created 30 minutes ago
        }
        
        with open(self.temp_cache_path, 'w') as f:
            json.dump(cache_data, f)
        
        with patch('builtins.print'):  # Suppress print statements
            token = self.get_access_token('test_id', 'test_secret')
        
        # Should return cached token without making API call
        self.assertEqual(token, 'cached_token_67890')
    
    def test_token_caching_refresh_expired_token(self):
        """Test that expired token is refreshed with new API call."""
        # Create an expired cache file
        past_time = time.time() - 1800  # 30 minutes ago
        cache_data = {
            'access_token': 'expired_token_11111',
            'expires_in': 3600,
            'expires_at': past_time,  # Already expired
            'created_at': time.time() - 7200  # Created 2 hours ago
        }
        
        with open(self.temp_cache_path, 'w') as f:
            json.dump(cache_data, f)
        
        # Mock new token response
        mock_response = Mock()
        mock_response.json.return_value = {
            'access_token': 'new_fresh_token_22222',
            'expires_in': 3600
        }
        mock_response.raise_for_status.return_value = None
        
        with patch('requests.post', return_value=mock_response):
            with patch('builtins.print'):  # Suppress print statements
                token = self.get_access_token('test_id', 'test_secret')
        
        # Should return new token
        self.assertEqual(token, 'new_fresh_token_22222')
        
        # Verify cache was updated
        with open(self.temp_cache_path, 'r') as f:
            new_cache_data = json.load(f)
        
        self.assertEqual(new_cache_data['access_token'], 'new_fresh_token_22222')
    
    def test_token_caching_invalid_cache_file(self):
        """Test handling of corrupted cache file."""
        # Create invalid JSON cache file
        with open(self.temp_cache_path, 'w') as f:
            f.write('invalid json content')
        
        mock_response = Mock()
        mock_response.json.return_value = {
            'access_token': 'recovery_token_33333',
            'expires_in': 3600
        }
        mock_response.raise_for_status.return_value = None
        
        with patch('requests.post', return_value=mock_response):
            with patch('builtins.print'):  # Suppress print statements
                token = self.get_access_token('test_id', 'test_secret')
        
        # Should get new token despite corrupted cache
        self.assertEqual(token, 'recovery_token_33333')
    
    def test_clear_token_cache(self):
        """Test clearing the token cache."""
        # Create a cache file
        cache_data = {
            'access_token': 'token_to_clear',
            'expires_in': 3600,
            'expires_at': time.time() + 3600,
            'created_at': time.time()
        }
        
        with open(self.temp_cache_path, 'w') as f:
            json.dump(cache_data, f)
        
        # Verify cache exists
        self.assertTrue(self.temp_cache_path.exists())
        
        # Clear cache
        with patch('builtins.print'):  # Suppress print statements
            result = self.clear_token_cache()
        
        # Verify cache was cleared
        self.assertTrue(result)
        self.assertFalse(self.temp_cache_path.exists())
    
    def test_clear_token_cache_no_cache(self):
        """Test clearing cache when no cache exists."""
        # Ensure no cache file exists
        if self.temp_cache_path.exists():
            self.temp_cache_path.unlink()
        
        with patch('builtins.print'):  # Suppress print statements
            result = self.clear_token_cache()
        
        # Should return False indicating no cache to clear
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main(verbosity=2)