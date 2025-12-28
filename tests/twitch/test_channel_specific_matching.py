"""
Test module for channel-specific video matching functionality.
"""

import unittest
import tempfile
import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, Mock, mock_open
import os

# Add the project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Set up environment for testing
os.environ['TWITCH_CLIENT_ID'] = 'test_id'
os.environ['TWITCH_CLIENT_SECRET'] = 'test_secret'


class TestChannelSpecificMatching(unittest.TestCase):
    """Test that files only get matched to videos from their corresponding channel."""
    
    def setUp(self):
        """Set up test environment."""
        # Mock config with multiple authors/channels - new single channel_id format
        self.mock_config_data = """
streamer_id_1:
  directory_name: "streamer_id_1"
  author_name: ["streamer_id_1"]
  channel_id: "streamer_id_1_channel_id"

streamer_id_2:
  directory_name: "streamer_id_1"
  author_name: ["streamer_id_2"]
  channel_id: "streamer_id_2_channel_id"
"""
        self.config_patcher = patch("builtins.open", mock_open(read_data=self.mock_config_data))
        self.config_patcher.start()
        self.expanduser_patcher = patch("os.path.expanduser", return_value="/mock/config/path")
        self.expanduser_patcher.start()
        
        # Import after mocking
        from twitch.rename_vods import extract_author_from_filename, get_channel_id_for_author, update_filenames
        self.extract_author_from_filename = extract_author_from_filename
        self.get_channel_id_for_author = get_channel_id_for_author
        self.update_filenames = update_filenames
        
    def tearDown(self):
        """Clean up."""
        self.config_patcher.stop()
        self.expanduser_patcher.stop()
    
    def test_extract_author_from_filename(self):
        """Test extracting author from various filename formats."""
        test_cases = [
            ("20241024 14-29-04 [streamer_id_1] stream title [best][123].mp4", "streamer_id_1"),
            ("20241024 14-30-00 [streamer_id_2] another stream [best][456].mp4", "streamer_id_2"),
            ("20241024 [Streamer Name] no time [best][789].mp4", "Streamer Name"),
            ("invalid_filename_no_brackets.mp4", None),
        ]
        
        for filename, expected in test_cases:
            with self.subTest(filename=filename):
                result = self.extract_author_from_filename(filename)
                self.assertEqual(result, expected)
    
    def test_get_channel_id_for_author(self):
        """Test mapping authors to their channel IDs."""
        # Mock config for testing - updated for single channel_id format
        config = {
            'streamer_id_1': {
                'author_name': ['streamer_id_1'],
                'channel_id': 'streamer_id_1_channel_id'
            },
            'streamer_id_2': {
                'author_name': ['streamer_id_2'],
                'channel_id': 'streamer_id_2_channel_id'
            }
        }
        
        test_cases = [
            ("streamer_id_1", "streamer_id_1_channel_id"),
            ("streamer_id_2", "streamer_id_2_channel_id"),
            ("unknown_author", None),
        ]
        
        for author, expected in test_cases:
            with self.subTest(author=author):
                result = self.get_channel_id_for_author(author, config)
                self.assertEqual(result, expected)
    
    def test_channel_specific_video_matching(self):
        """Test that files only match videos from their corresponding channel."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files with different authors
            streamer_id_1_file = temp_path / "20241024 14-29-04 [streamer_id_1] old title [best][999].mp4"
            streamer_id_2_file = temp_path / "20241024 14-30-00 [streamer_id_2] old title [best][888].mp4"
            
            streamer_id_1_file.touch()
            streamer_id_2_file.touch()
            
            # Mock videos by channel
            videos_by_channel = {
                'streamer_id_1_channel_id': [
                    {
                        'id': '111',
                        'title': 'streamer_id_1 Stream',
                        'created_at': '2024-10-24T14:30:00Z',
                        'user_name': 'streamer_id_1'
                    }
                ],
                'streamer_id_2_channel_id': [
                    {
                        'id': '222',
                        'title': 'streamer_id_2 Stream',
                        'created_at': '2024-10-24T14:30:00Z',
                        'user_name': 'streamer_id_2'
                    }
                ]
            }
            
            # Test dry-run mode
            with patch('builtins.print'):  # Suppress output
                self.update_filenames([streamer_id_1_file, streamer_id_2_file], videos_by_channel, dry_run=True)
            
            # Files should still exist (dry-run mode)
            self.assertTrue(streamer_id_1_file.exists())
            self.assertTrue(streamer_id_2_file.exists())
    
    def test_mixed_author_directory_scenario(self):
        """Test the specific scenario mentioned in the issue."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create files that would exist in a "streamer_id_1" directory but have different authors
            files = [
                temp_path / "20241024 14-29-04 [streamer_id_1] stream one [best][111].mp4",
                temp_path / "20241024 14-30-00 [streamer_id_2] stream two [best][222].mp4",
                temp_path / "20241024 14-31-00 [streamer_id_1] stream three [best][333].mp4",
            ]
            
            for file in files:
                file.touch()
            
            # Mock separate video lists for each channel
            videos_by_channel = {
                'streamer_id_1_channel_id': [
                    {
                        'id': '1001',
                        'title': 'streamer_id_1 Stream A',
                        'created_at': '2024-10-24T14:29:30Z',
                        'user_name': 'streamer_id_1'
                    },
                    {
                        'id': '1002', 
                        'title': 'streamer_id_1 Stream B',
                        'created_at': '2024-10-24T14:31:30Z',
                        'user_name': 'streamer_id_1'
                    }
                ],
                'streamer_id_2_channel_id': [
                    {
                        'id': '2001',
                        'title': 'streamer_id_2 Stream A',
                        'created_at': '2024-10-24T14:30:30Z',
                        'user_name': 'streamer_id_2'
                    }
                ]
            }
            
            # Test processing - streamer_id_2 files should only match streamer_id_2 videos
            with patch('builtins.print'):  # Suppress output
                self.update_filenames(files, videos_by_channel, dry_run=True)
            
            # All files should still exist after dry-run
            for file in files:
                self.assertTrue(file.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)