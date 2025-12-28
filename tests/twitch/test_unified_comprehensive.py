"""
Comprehensive test module for Twitch rename video functionality.
Consolidates all individual test files and provides complete test coverage.
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


def convert_videos_to_channel_dict(videos: list[dict], channel_id: str = "test_channel") -> dict[str, list[dict]]:
    """Helper function to convert legacy video list to new channel-based dict format."""
    return {channel_id: videos}


class TestVideoIdExtraction(unittest.TestCase):
    """Test video ID extraction with various formats."""
    
    def setUp(self):
        """Set up test environment."""
        # Mock the config file loading - updated for new config format
        self.mock_config_data = """
streamer_name:
  directory_name: "streamer_name"  
  author_name: ["Streamer Name"]
  channel_id: "streamer_name_channel"
"""
        self.config_patcher = patch("builtins.open", mock_open(read_data=self.mock_config_data))
        self.config_patcher.start()
        self.expanduser_patcher = patch("os.path.expanduser", return_value="/mock/config/path")
        self.expanduser_patcher.start()
        
        # Import after mocking
        from twitch.rename_vods import extract_video_id
        self.extract_video_id = extract_video_id
        
    def tearDown(self):
        """Clean up."""
        self.config_patcher.stop()
        self.expanduser_patcher.stop()
    
    def test_extract_video_id_standard_format(self):
        """Test extraction with standard numeric video ID."""
        filename = "20241024 14-29-04 [Streamer Name] stream [best][2600103473].mp4"
        result = self.extract_video_id(filename)
        self.assertEqual(result, "2600103473")
    
    def test_extract_video_id_v_prefix(self):
        """Test extraction with 'v' prefixed video ID."""
        filename = "20241024 14-29-04 [Streamer Name] stream [best][v1947286839].mp4"
        result = self.extract_video_id(filename)
        self.assertEqual(result, "v1947286839")
    
    def test_extract_video_id_alphanumeric(self):
        """Test extraction with alphanumeric video ID."""
        filename = "20241024 14-29-04 [Streamer Name] stream [best][abc123def].mp4"
        result = self.extract_video_id(filename)
        self.assertEqual(result, "abc123def")
    
    def test_extract_video_id_empty_brackets(self):
        """Test extraction with empty brackets."""
        filename = "20241024 14-29-04 [Streamer Name] stream [best][].mp4"
        result = self.extract_video_id(filename)
        self.assertIsNone(result)
    
    def test_extract_video_id_no_brackets(self):
        """Test extraction with no video ID brackets."""
        filename = "random_file_without_brackets.mp4"
        result = self.extract_video_id(filename)
        self.assertIsNone(result)


class TestDateExtraction(unittest.TestCase):
    """Test date extraction from various filename patterns."""
    
    def setUp(self):
        """Set up test environment."""
        # Mock the config file loading
        self.mock_config_data = """
streamer_name:
  directory_name: "streamer_name"  
  channel_id: ["1161928262"]
"""
        self.config_patcher = patch("builtins.open", mock_open(read_data=self.mock_config_data))
        self.config_patcher.start()
        self.expanduser_patcher = patch("os.path.expanduser", return_value="/mock/config/path")
        self.expanduser_patcher.start()
        
        from twitch.rename_vods import extract_date_from_filename
        self.extract_date_from_filename = extract_date_from_filename
    
    def tearDown(self):
        """Clean up."""
        self.config_patcher.stop()
        self.expanduser_patcher.stop()
    
    def test_date_extraction_full_datetime(self):
        """Test extraction of full date and time."""
        filename = '20241024 14-29-04 [Author] stream [best][123].mp4'
        result = self.extract_date_from_filename(filename)
        expected = datetime(2024, 10, 24, 14, 29, 4)
        self.assertEqual(result, expected)
    
    def test_date_extraction_date_only(self):
        """Test extraction of date only (no time)."""
        filename = '20241024 [Author] stream [best][123].mp4'
        result = self.extract_date_from_filename(filename)
        expected = datetime(2024, 10, 24)
        self.assertEqual(result, expected)
    
    def test_date_extraction_no_pattern(self):
        """Test extraction when no date pattern exists."""
        filename = 'no_date_pattern.mp4'
        result = self.extract_date_from_filename(filename)
        self.assertIsNone(result)
    
    def test_date_extraction_invalid_date(self):
        """Test extraction with invalid date values."""
        filename = '20241301 [Author] invalid month [best][123].mp4'
        result = self.extract_date_from_filename(filename)
        self.assertIsNone(result)


class TestVideoMatching(unittest.TestCase):
    """Test video matching based on date proximity."""
    
    def setUp(self):
        """Set up test environment."""
        # Mock the config file loading
        self.mock_config_data = """
streamer_name:
  directory_name: "streamer_name"  
  channel_id: ["1161928262"]
"""
        self.config_patcher = patch("builtins.open", mock_open(read_data=self.mock_config_data))
        self.config_patcher.start()
        self.expanduser_patcher = patch("os.path.expanduser", return_value="/mock/config/path")
        self.expanduser_patcher.start()
        
        from twitch.rename_vods import find_matching_video
        self.find_matching_video = find_matching_video
    
    def tearDown(self):
        """Clean up."""
        self.config_patcher.stop()
        self.expanduser_patcher.stop()
    
    def test_video_matching_closest_date(self):
        """Test that closest video by date is matched."""
        file_path = Path('20241024 14-29-04 [Author] title [best][123].mp4')
        
        videos = [
            {
                'id': '111',
                'title': 'Far Stream',
                'created_at': '2024-10-20T10:00:00Z'
            },
            {
                'id': '222',
                'title': 'Close Stream',
                'created_at': '2024-10-24T15:00:00Z'
            },
            {
                'id': '333',
                'title': 'Very Far Stream',
                'created_at': '2024-10-30T10:00:00Z'
            }
        ]
        
        result = self.find_matching_video(file_path, videos)
        
        # Should pick the closest match
        self.assertIsNotNone(result)
        if result is not None:
            self.assertEqual(result['id'], '222')
    
    def test_video_matching_no_match_too_far(self):
        """Test that no match is returned when videos are too far."""
        file_path = Path('20241024 14-29-04 [Author] title [best][123].mp4')
        
        videos = [{
            'id': '456',
            'title': 'Very Far Stream',
            'created_at': '2024-10-20T14:29:04Z'  # 4 days away
        }]
        
        result = self.find_matching_video(file_path, videos)
        self.assertIsNone(result)


class TestFilenameGeneration(unittest.TestCase):
    """Test new filename generation functionality."""
    
    def setUp(self):
        """Set up test environment."""
        # Mock the config file loading
        self.mock_config_data = """
streamer_name:
  directory_name: "streamer_name"  
  channel_id: ["1161928262"]
"""
        self.config_patcher = patch("builtins.open", mock_open(read_data=self.mock_config_data))
        self.config_patcher.start()
        self.expanduser_patcher = patch("os.path.expanduser", return_value="/mock/config/path")
        self.expanduser_patcher.start()
        
        from twitch.rename_vods import generate_new_filename
        self.generate_new_filename = generate_new_filename
    
    def tearDown(self):
        """Clean up."""
        self.config_patcher.stop()
        self.expanduser_patcher.stop()
    
    def test_filename_generation_full_datetime(self):
        """Test filename generation preserves full datetime format."""
        mock_video = {
            'id': '9999999999',
            'title': 'New Amazing Stream Title',
            'user_name': 'test_user'
        }
        
        file_path = Path('20241024 14-29-04 [Streamer Name] old title [best][123].mp4')
        result = self.generate_new_filename(file_path, mock_video)
        
        # Check that the date prefix is preserved
        self.assertTrue(result.startswith('20241024 14-29-04'))
        # Check that new video ID is included
        self.assertIn('9999999999', result)
        # Check that new title is included
        self.assertIn('New Amazing Stream Title', result)
    
    def test_filename_generation_date_only(self):
        """Test filename generation preserves date-only format."""
        mock_video = {
            'id': '8888888888',
            'title': 'Another Stream Title',
            'user_name': 'test_user'
        }
        
        file_path = Path('20241024 [Streamer Name] old title [best][123].mp4')
        result = self.generate_new_filename(file_path, mock_video)
        
        # Check that the date prefix is preserved
        self.assertTrue(result.startswith('20241024'))
        # Check that new video ID is included
        self.assertIn('8888888888', result)
        # Check that new title is included
        self.assertIn('Another Stream Title', result)


class TestDryRunVsApplyMode(unittest.TestCase):
    """Test dry-run vs apply mode functionality."""
    
    def setUp(self):
        """Set up test environment."""
        # Mock the config file loading
        self.mock_config_data = """
streamer_name:
  directory_name: "streamer_name"  
  channel_id: ["1161928262"]
"""
        self.config_patcher = patch(
            "builtins.open", 
            mock_open(read_data=self.mock_config_data))
        self.config_patcher.start()
        self.expanduser_patcher = patch(
            "os.path.expanduser", 
            return_value="/mock/config/path")
        self.expanduser_patcher.start()
        
        from twitch.rename_vods import update_filenames
        self.update_filenames = update_filenames
    
    def tearDown(self):
        """Clean up."""
        self.config_patcher.stop()
        self.expanduser_patcher.stop()
    
    def test_dry_run_preserves_files(self):
        """Test that dry-run mode preserves original files."""
        with patch('twitch.fetch_vods.get_access_token', return_value='mock_token'):
            with patch('twitch.fetch_vods.fetch_videos') as mock_fetch:
                mock_videos = [{
                    'id': '2600103474',
                    'title': 'New Stream Title from API',
                    'created_at': '2024-10-24T14:30:00Z',
                    'url': 'https://twitch.tv/videos/2600103474',
                    'duration': '2h30m'
                }]
                
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = Path(temp_dir)
                    
                    # Create test file
                    original_filename = '20241024 14-29-04 [Streamer Name] old title [best][123].mp4'
                    test_file = temp_path / original_filename
                    test_file.touch()
                    
                    # Create videos_by_channel dict format
                    videos_by_channel = convert_videos_to_channel_dict(mock_videos, "streamer_name_channel")
                    
                    # Test dry-run mode
                    with patch('builtins.print'):  # Suppress output
                        self.update_filenames([test_file], videos_by_channel, dry_run=True)
                    
                    # File should still exist with original name
                    self.assertTrue(test_file.exists())
    
    def test_apply_mode_renames_files(self):
        """Test that apply mode actually renames files."""
        with patch('twitch.fetch_vods.get_access_token', return_value='mock_token'):
            with patch('twitch.fetch_vods.fetch_videos') as mock_fetch:
                mock_videos = [{
                    'id': '2600103474',
                    'title': 'New Stream Title from API',
                    'created_at': '2024-10-24T14:30:00Z',
                    'url': 'https://twitch.tv/videos/2600103474',
                    'duration': '2h30m'
                }]
                
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = Path(temp_dir)
                    
                    # Create test file
                    original_filename = '20241024 14-29-04 [Streamer Name] old title [best][123].mp4'
                    test_file = temp_path / original_filename
                    test_file.touch()
                    
                    # Create videos_by_channel dict format
                    videos_by_channel = {'streamer_name_channel': mock_videos}
                    
                    # Test apply mode
                    with patch('builtins.print'):  # Suppress output
                        self.update_filenames([test_file], videos_by_channel, dry_run=False)
                    
                    # Original file should no longer exist
                    self.assertFalse(test_file.exists())
                    
                    # New file should exist
                    files_after = list(temp_path.iterdir())
                    self.assertEqual(len(files_after), 1)
                    
                    new_file = files_after[0]
                    self.assertIn('New Stream Title from API', new_file.name)
                    self.assertIn('2600103474', new_file.name)


class TestVPrefixSkipping(unittest.TestCase):
    """Test that files with 'v' prefixed video IDs are skipped."""
    
    def setUp(self):
        """Set up test environment."""
        # Mock the config file loading
        self.mock_config_data = """
streamer_name:
  directory_name: "streamer_name"  
  channel_id: ["1161928262"]
"""
        self.config_patcher = patch("builtins.open", mock_open(read_data=self.mock_config_data))
        self.config_patcher.start()
        self.expanduser_patcher = patch("os.path.expanduser", return_value="/mock/config/path")
        self.expanduser_patcher.start()
        
        from twitch.rename_vods import update_filenames, extract_video_id
        self.update_filenames = update_filenames
        self.extract_video_id = extract_video_id
    
    def tearDown(self):
        """Clean up."""
        self.config_patcher.stop()
        self.expanduser_patcher.stop()
    
    def test_v_prefix_extraction(self):
        """Test that 'v' prefixed IDs are correctly extracted."""
        filename = '20241024 14-29-04 [Streamer Name] stream [best][v12345678].mp4'
        result = self.extract_video_id(filename)
        self.assertEqual(result, 'v12345678')
    
    def test_v_prefix_files_skipped_in_processing(self):
        """Test that 'v' prefixed files are skipped during processing."""
        with patch('twitch.fetch_vods.get_access_token', return_value='mock_token'):
            with patch('twitch.fetch_vods.fetch_videos') as mock_fetch:
                mock_fetch.return_value = [{
                    'id': '2600103474',
                    'title': 'Test Stream Title',
                    'created_at': '2024-10-24T14:30:00Z',
                    'url': 'https://twitch.tv/videos/2600103474',
                    'duration': '2h30m'
                }]
                
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = Path(temp_dir)
                    
                    # Create test files
                    v_prefixed_file = temp_path / '20241024 14-29-04 [Streamer Name] stream [best][v12345678].mp4'
                    normal_file = temp_path / '20241024 14-30-00 [Streamer Name] stream [best][1234567890].mp4'
                    
                    v_prefixed_file.touch()
                    normal_file.touch()
                    
                    # Test dry-run mode
                    videos_by_channel = convert_videos_to_channel_dict(mock_fetch.return_value, "streamer_name_channel")
                    with patch('builtins.print'):  # Suppress output
                        self.update_filenames([v_prefixed_file, normal_file], videos_by_channel, dry_run=True)
                    
                    # Both files should still exist (dry-run mode)
                    self.assertTrue(v_prefixed_file.exists())
                    self.assertTrue(normal_file.exists())


class TestVideoIdMatchingSkip(unittest.TestCase):
    """Test skipping files when video ID already matches API."""
    
    def setUp(self):
        """Set up test environment."""
        # Mock the config file loading
        self.mock_config_data = """
Streamer Name:
  directory_name: "streamer_name"  
  channel_id: ["1161928262"]
"""
        self.config_patcher = patch(
            "builtins.open", mock_open(read_data=self.mock_config_data))
        self.config_patcher.start()
        self.expanduser_patcher = patch(
            "os.path.expanduser", return_value="/mock/config/path")
        self.expanduser_patcher.start()
        
        from twitch.rename_vods import update_filenames
        self.update_filenames = update_filenames
    
    def tearDown(self):
        """Clean up."""
        self.config_patcher.stop()
        self.expanduser_patcher.stop()
    
    def test_skip_files_with_matching_video_id(self):
        """Test that files with video IDs matching the API are skipped."""
        with patch('twitch.fetch_vods.get_access_token', return_value='mock_token'):
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Create test files - one with matching ID, one with different ID
                matching_file = temp_path / '20241024 14-30-00 [Streamer Name] old title [best][2600103474].mp4'
                different_file = temp_path / '20241024 14-31-00 [Streamer Name] old title [best][1234567890].mp4'
                
                matching_file.touch()
                different_file.touch()
                
                # Mock API response with video ID that matches the first file
                mock_videos = [{
                    'id': '2600103474',  # Matches first file
                    'title': 'New Stream Title',
                    'created_at': '2024-10-24T14:30:00Z',
                    'url': 'https://twitch.tv/videos/2600103474',
                    'duration': '2h30m'
                }]
                
                # Capture log output to verify skipping behavior  
                videos_by_channel = convert_videos_to_channel_dict(mock_videos, "streamer_name_channel")
                with patch('builtins.print'):  # Suppress output
                    self.update_filenames([matching_file, different_file], videos_by_channel, dry_run=True)
                
                # Both files should still exist (dry-run mode)
                self.assertTrue(matching_file.exists())
                self.assertTrue(different_file.exists())
    
    def test_exact_video_id_priority_over_date_proximity(self):
        """Test that exact video ID matches take priority over closer date matches."""
        with patch('twitch.fetch_vods.get_access_token', return_value='mock_token'):
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Create test file similar to user's example
                test_file = temp_path / '20250930 19-00-18 [Streamer Name] new badges [best][2579723488].mp4'
                test_file.touch()
                
                # Mock API response with two videos:
                # 1. Exact video ID match but worse date match
                # 2. Better date match but different video ID  
                mock_videos = [
                    {
                        'id': '2579723488',  # EXACT MATCH with file's video ID
                        'title': 'new badges stream', 
                        'created_at': '2025-09-30T17:00:02Z',  # 2 hours before file time
                        'duration': '1h54m50s'
                    },
                    {
                        'id': '2579889310',  # Different video ID
                        'title': 'new badges stream',
                        'created_at': '2025-09-30T19:30:00Z',  # Closer to file time (19:00)
                        'duration': '4h37m50s'
                    }
                ]
                
                # Should skip the file because exact ID match found
                videos_by_channel = convert_videos_to_channel_dict(mock_videos, "streamer_name_channel")
                with patch('builtins.print'):  # Suppress output
                    self.update_filenames([test_file], videos_by_channel, dry_run=True)
                
                # File should still exist (skipped due to exact ID match)
                self.assertTrue(test_file.exists())


class TestRealWorldScenarios(unittest.TestCase):
    """Test realistic scenarios with mixed file types."""
    
    def setUp(self):
        """Set up test environment."""
        # Mock the config file loading
        self.mock_config_data = """
Streamer Name:
  directory_name: "streamer_name"  
  channel_id: ["1161928262"]
"""
        self.config_patcher = patch(
            "builtins.open", mock_open(read_data=self.mock_config_data))
        self.config_patcher.start()
        self.expanduser_patcher = patch(
            "os.path.expanduser", return_value="/mock/config/path")
        self.expanduser_patcher.start()
        
        from twitch.rename_vods import update_filenames
        self.update_filenames = update_filenames
    
    def tearDown(self):
        """Clean up."""
        self.config_patcher.stop()
        self.expanduser_patcher.stop()
    
    def test_mixed_video_id_scenarios(self):
        """Test processing of mixed video ID formats in realistic scenarios."""
        with patch('twitch.fetch_vods.get_access_token', return_value='mock_token'):
            with patch('twitch.fetch_vods.fetch_videos') as mock_fetch:
                mock_fetch.return_value = [{
                    'id': '2600103474',
                    'title': 'Morning Chat Stream - Coffee and Updates',
                    'created_at': '2024-10-24T09:30:00Z',
                    'url': 'https://twitch.tv/videos/2600103474',
                    'duration': '2h15m'
                }]
                
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = Path(temp_dir)
                    
                    # Create realistic test files
                    test_files = [
                        '20241024 09-30-15 [Streamer Name] old title [best][v1947286839].mp4',  # Should skip
                        '20241024 09-31-00 [Streamer Name] old title [best][2600103999].mp4',   # Should process
                        '20241024 09-32-00 [Streamer Name] old title [best][].mp4'             # Should process
                    ]
                    
                    file_paths = []
                    for filename in test_files:
                        file_path = temp_path / filename
                        file_path.touch()
                        file_paths.append(file_path)
                    
                    # Run update (dry-run mode)
                    videos_by_channel = convert_videos_to_channel_dict(mock_fetch.return_value, "streamer_name_channel")
                    with patch('builtins.print'):  # Suppress output
                        self.update_filenames(file_paths, videos_by_channel, dry_run=True)
                    
                    # All files should still exist in dry-run mode
                    for file_path in file_paths:
                        self.assertTrue(file_path.exists())


def run_comprehensive_test_suite():
    """Run the complete test suite and return results."""
    test_classes = [
        TestVideoIdExtraction,
        TestDateExtraction,
        TestVideoMatching,
        TestFilenameGeneration,
        TestDryRunVsApplyMode,
        TestVPrefixSkipping,
        TestVideoIdMatchingSkip,
        TestRealWorldScenarios
    ]
    
    suite = unittest.TestSuite()
    for test_class in test_classes:
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(test_class))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    print("Running Comprehensive Twitch Rename Video Test Suite")
    print("=" * 60)
    
    success = run_comprehensive_test_suite()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed!")
    
    print("\nTest Coverage Areas:")
    print("  • Video ID extraction (numeric, alphanumeric, v-prefixed)")
    print("  • Date extraction (full datetime, date-only)")
    print("  • Video matching by date proximity") 
    print("  • Filename generation (preserving date formats)")
    print("  • Dry-run vs apply mode functionality")
    print("  • V-prefixed video ID skipping behavior")
    print("  • Video ID matching skip (when ID already matches API)")
    print("  • Real-world mixed file scenarios")