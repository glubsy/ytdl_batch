"""
Comprehensive test module for twitch_rename_videos.py functionality.
Tests all aspects including filename parsing, video ID extraction, 
date handling, dry-run mode, and complete rename operations.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, mock_open
from pathlib import Path
import tempfile
import sys
from datetime import datetime
import os

# Add the project root to the path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock the config file loading before importing the module
mock_config_data = """
test_user:
  directory_name: "test_dir"
  channel_id: ["test_channel_id"]
"""

with patch("builtins.open", mock_open(read_data=mock_config_data)):
    with patch("os.path.expanduser", return_value="/mock/config/path"):
        from twitch.rename_vods import (
            extract_video_id,
            identify_authors_from_files,
            identify_authors_from_directory,
            collect_files,
            index_on_video_id,
            extract_date_from_filename,
            find_matching_video,
            generate_new_filename,
            update_filenames,
            apply_title_overrides,
            parse_duration_to_seconds
        )


class TestExtractVideoId(unittest.TestCase):
    """Test the extract_video_id function with various filename patterns."""
    
    def test_extract_video_id_with_brackets_and_id(self):
        """Test extraction with the standard pattern [channel][id]."""
        filename = "20251024 14-29-04 [Streamer Name 1] yap and woof and bark and arf [pngtuber] lol [best][2600103473].mp4"
        result = extract_video_id(filename)
        self.assertEqual(result, "2600103473")
    
    def test_extract_video_id_empty_brackets(self):
        """Test extraction when brackets are empty."""
        filename = "20251025 10-21-01 [Streamer Name 1] new stream todyay [best][].mp4"
        result = extract_video_id(filename)
        self.assertIsNone(result)  # Empty brackets should return None
    
    def test_extract_video_id_multiple_ids(self):
        """Test that the function extracts the first matching ID."""
        filename = "20251024 [Streamer Name 1] test [best][1234567890] extra [9876543210].mp4"
        result = extract_video_id(filename)
        self.assertEqual(result, "1234567890")
    
    def test_extract_video_id_no_pattern_match(self):
        """Test when no pattern matches."""
        filename = "random_video_file.mp4"
        result = extract_video_id(filename)
        self.assertIsNone(result)
    
    def test_extract_video_id_nested_brackets(self):
        """Test with multiple bracket sets."""
        filename = "20251024 [Author] [Category] [Quality][1234567890].mp4"
        result = extract_video_id(filename)
        self.assertEqual(result, "1234567890")
    
    def test_extract_video_id_with_ts_extension(self):
        """Test with .ts file extension."""
        filename = "20251024 [Streamer Name 1] stream [best][9999999999].ts"
        result = extract_video_id(filename)
        self.assertEqual(result, "9999999999")


class TestIdentifyAuthorsFromFiles(unittest.TestCase):
    """Test the identify_authors_from_files function."""
    
    def setUp(self):
        """Set up test data with sample filenames."""
        self.sample_files = [
            Path("20251024 14-29-04 [Streamer Name 1] yap and woof and bark and arf [pngtuber] lol [best][2600103473].mp4"),
            Path("20251025 10-21-01 [Streamer Name 2] new stream todyay [best][].mp4"),
            Path("20251026 15-30-45 [Streamer Name 1] another stream [best][1111111111].mp4"),
            Path("20251027 09-15-22 [Different Author] different content [best][2222222222].mp4"),
            Path("random_file_without_brackets.mp4"),
            Path("20251028 [Another_Channel] test stream [best][3333333333].ts")
        ]
    
    def test_identify_authors_basic(self):
        """Test basic author identification from filenames."""
        authors = identify_authors_from_files(self.sample_files)
        expected_authors = {"Streamer Name 1", "Streamer Name 2", "Different Author", "Another_Channel"}
        self.assertEqual(authors, expected_authors)
    
    def test_identify_authors_empty_list(self):
        """Test with empty file list."""
        authors = identify_authors_from_files([])
        self.assertEqual(authors, set())
    
    def test_identify_authors_no_brackets(self):
        """Test with files that don't have brackets."""
        files_without_brackets = [
            Path("regular_video.mp4"),
            Path("another_video.ts")
        ]
        authors = identify_authors_from_files(files_without_brackets)
        self.assertEqual(authors, set())
    
    def test_identify_authors_case_sensitive(self):
        """Test that author identification is case-sensitive."""
        files = [
            Path("20251024 [Streamer Name 1] stream1 [best][111].mp4"),
            Path("20251024 [streamer name 1] stream2 [best][222].mp4"),
            Path("20251024 [STREAMER NAME 1] stream3 [best][333].mp4")
        ]
        authors = identify_authors_from_files(files)
        expected_authors = {"Streamer Name 1", "streamer name 1", "STREAMER NAME 1"}
        self.assertEqual(authors, expected_authors)


class TestIdentifyAuthorsFromDirectory(unittest.TestCase):
    """Test the identify_authors_from_directory function."""
    
    def setUp(self):
        """Set up mock config data."""
        self.mock_config = {
            "streamer_name_1": {
                "directory_name": "streamer1_streams",
                "channel_id": ["streamer_name_1_id", "streamer1_alt_id"]
            },
            "another_streamer": {
                "directory_name": "other_streams",
                "channel_id": ["other_id"]
            },
            "test_streamer": {
                "directory_name": "test_dir",
                "channel_id": ["test_id_1", "test_id_2"]
            }
        }
    
    @patch('twitch.twitch_rename_videos.Path')
    def test_identify_authors_matching_directory(self, mock_path):
        """Test when current directory matches config."""
        # Mock the current directory path
        mock_current_dir = Mock()
        mock_current_dir.__str__ = Mock(
            return_value="/home/user/downloads/Streamer_streams/2024")
        mock_path.return_value.resolve.return_value = mock_current_dir
        
        authors = identify_authors_from_directory(self.mock_config)
        expected_authors = {"Streamer_id", "Streamer_alt_id"}
        self.assertEqual(authors, expected_authors)
    
    @patch('twitch.twitch_rename_videos.Path')
    def test_identify_authors_no_matching_directory(self, mock_path):
        """Test when current directory doesn't match any config."""
        # Mock a directory that doesn't match
        mock_current_dir = Mock()
        mock_current_dir.__str__ = Mock(
            return_value="/home/user/downloads/random_folder")
        mock_path.return_value.resolve.return_value = mock_current_dir
        
        authors = identify_authors_from_directory(self.mock_config)
        self.assertEqual(authors, set())
    
    @patch('twitch.twitch_rename_videos.Path')
    def test_identify_authors_multiple_matches(self, mock_path):
        """Test when directory matches multiple configs."""
        # Mock a directory that contains both matching terms
        mock_current_dir = Mock()
        mock_current_dir.__str__ = Mock(
            return_value="/home/user/Streamer_streams/other_streams")
        mock_path.return_value.resolve.return_value = mock_current_dir
        
        authors = identify_authors_from_directory(self.mock_config)
        expected_authors = {"Streamer_id", "Streamer_alt_id", "other_id"}
        self.assertEqual(authors, expected_authors)


class TestCollectFiles(unittest.TestCase):
    """Test the collect_files function."""
    
    def setUp(self):
        """Set up a temporary directory with test files."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # Create test files
        self.test_files = [
            "video1.mp4",
            "video2.ts", 
            "video3.mp4",
            "subtitles.srt",  # Should be ignored
            "readme.txt",     # Should be ignored
        ]
        
        # Create subdirectory with more files
        self.sub_dir = self.temp_path / "subdir"
        self.sub_dir.mkdir()
        
        # Create files in main directory
        for filename in self.test_files:
            (self.temp_path / filename).touch()
        
        # Create files in subdirectory
        (self.sub_dir / "sub_video.mp4").touch()
        (self.sub_dir / "sub_video.ts").touch()
        (self.sub_dir / "other_file.txt").touch()
    
    def tearDown(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_collect_files_recursive(self):
        """Test that collect_files finds all video files recursively."""
        files = collect_files(self.temp_path)
        
        # Should find mp4 and ts files only
        # From self.test_files: video1.mp4, video2.ts, video3.mp4
        # From subdir: sub_video.mp4, sub_video.ts
        expected_count = 5  # 3 mp4 + 1 ts in root + 1 mp4 + 1 ts in subdir = 5 total
        self.assertEqual(len(files), expected_count)
        
        # Check that all found files have correct extensions
        extensions = {f.suffix for f in files}
        self.assertEqual(extensions, {".mp4", ".ts"})
    
    def test_collect_files_empty_directory(self):
        """Test with empty directory."""
        empty_dir = self.temp_path / "empty"
        empty_dir.mkdir()
        
        files = collect_files(empty_dir)
        self.assertEqual(len(files), 0)


class TestIndexOnVideoId(unittest.TestCase):
    """Test the index_on_video_id function."""
    
    def setUp(self):
        """Set up sample video data."""
        self.sample_videos = [
            {
                'id': '2600103473',
                'title': 'yap and woof and bark and arf',
                'url': 'https://www.twitch.tv/videos/2600103473',
                'created_at': '2024-10-24T14:29:04Z'
            },
            {
                'id': '1111111111',
                'title': 'another stream',
                'url': 'https://www.twitch.tv/videos/1111111111',
                'created_at': '2024-10-26T15:30:45Z'
            },
            {
                'id': '2222222222',
                'title': 'different content',
                'url': 'https://www.twitch.tv/videos/2222222222',
                'created_at': '2024-10-27T09:15:22Z'
            }
        ]
    
    def test_index_on_video_id_basic(self):
        """Test basic indexing functionality."""
        index = index_on_video_id(self.sample_videos)
        
        self.assertEqual(len(index), 3)
        self.assertIn('2600103473', index)
        self.assertIn('1111111111', index)
        self.assertIn('2222222222', index)
        
        # Verify content is preserved
        self.assertEqual(index['2600103473']['title'], 'yap and woof and bark and arf')
        self.assertEqual(index['1111111111']['title'], 'another stream')
    
    def test_index_on_video_id_missing_id(self):
        """Test with videos that have missing or None id."""
        videos_with_missing_id = [
            {
                'id': '12345',
                'title': 'Valid video'
            },
            {
                'title': 'Video without id'
            },
            {
                'id': None,
                'title': 'Video with None id'
            },
            {
                'id': '',
                'title': 'Video with empty id'
            }
        ]
        
        index = index_on_video_id(videos_with_missing_id)
        
        # Should only contain the valid video
        self.assertEqual(len(index), 1)
        self.assertIn('12345', index)
        self.assertEqual(index['12345']['title'], 'Valid video')
    
    def test_index_on_video_id_empty_list(self):
        """Test with empty video list."""
        index = index_on_video_id([])
        self.assertEqual(index, {})
    
    def test_index_on_video_id_duplicate_ids(self):
        """Test with duplicate video IDs (last one should win)."""
        videos_with_duplicates = [
            {
                'id': '12345',
                'title': 'First video'
            },
            {
                'id': '12345',
                'title': 'Second video'
            }
        ]
        
        index = index_on_video_id(videos_with_duplicates)
        
        self.assertEqual(len(index), 1)
        self.assertEqual(index['12345']['title'], 'Second video')


class TestFilenamePatterns(unittest.TestCase):
    """Test various filename patterns that the module should handle."""
    
    def test_example_filenames_provided_by_user(self):
        """Test the specific example filenames provided in the user request."""
        filenames = [
            "20251024 14-29-04 [Streamer Name] yap and woof and bark and arf [pngtuber] lol [best][2600103473].mp4",
            "20251025 10-21-01 [Streamer] new stream todyay [best][].mp4"
        ]
        
        # Test video ID extraction
        video_id_1 = extract_video_id(filenames[0])
        video_id_2 = extract_video_id(filenames[1])
        
        self.assertEqual(video_id_1, "2600103473")
        self.assertIsNone(video_id_2)  # Empty brackets
        
        # Test author identification
        file_paths = [Path(f) for f in filenames]
        authors = identify_authors_from_files(file_paths)
        
        expected_authors = {"Streamer Name", "Streamer"}
        self.assertEqual(authors, expected_authors)
    
    def test_various_bracket_patterns(self):
        """Test different bracket and ID patterns."""
        test_cases = [
            ("video[author][12345].mp4", "12345"),
            ("video [author] content [best][67890].ts", "67890"),
            ("[author] video [quality][999].mp4", "999"),
            ("video[author][].mp4", None),  # Empty brackets
            ("video[author].mp4", None),    # No second bracket set
            ("video.mp4", None),            # No brackets at all
        ]
        
        for filename, expected_id in test_cases:
            with self.subTest(filename=filename):
                result = extract_video_id(filename)
                self.assertEqual(result, expected_id)


class TestDateExtraction(unittest.TestCase):
    """Test date extraction from filenames."""
    
    def setUp(self):
        """Import the function we need to test."""
        # Mock the config file loading before importing
        with patch("builtins.open", mock_open(read_data=mock_config_data)):
            with patch("os.path.expanduser", return_value="/mock/config/path"):
                from twitch.rename_vods import extract_date_from_filename
                self.extract_date_from_filename = extract_date_from_filename
    
    def test_extract_date_full_datetime(self):
        """Test extraction of full date and time."""
        filename = "20241024 14-29-04 [Author] title [best][123].mp4"
        result = self.extract_date_from_filename(filename)
        expected = datetime(2024, 10, 24, 14, 29, 4)
        self.assertEqual(result, expected)
    
    def test_extract_date_only(self):
        """Test extraction of date only."""
        filename = "20241024 [Author] title [best][123].mp4"
        result = self.extract_date_from_filename(filename)
        expected = datetime(2024, 10, 24)
        self.assertEqual(result, expected)
    
    def test_extract_date_no_match(self):
        """Test with filename that doesn't match pattern."""
        filename = "random_video.mp4"
        result = self.extract_date_from_filename(filename)
        self.assertIsNone(result)
    
    def test_extract_date_invalid_date(self):
        """Test with invalid date values."""
        filename = "20241332 25-99-99 [Author] title [best][123].mp4"  # Invalid month/time
        result = self.extract_date_from_filename(filename)
        self.assertIsNone(result)


class TestFilenameSanitization(unittest.TestCase):
    """Test filename sanitization functionality."""
    
    def setUp(self):
        """Import the function we need to test."""
        with patch("builtins.open", mock_open(read_data=mock_config_data)):
            with patch("os.path.expanduser", return_value="/mock/config/path"):
                from twitch.rename_vods import sanitize_filename
                self.sanitize_filename = sanitize_filename
    
    def test_sanitize_invalid_characters(self):
        """Test removal of invalid filename characters."""
        title = 'Test: "Special" <Game> /Part 1\\'
        result = self.sanitize_filename(title)
        expected = 'Test_ _Special_ _Game_ _Part 1_'
        self.assertEqual(result, expected)
    
    def test_sanitize_whitespace(self):
        """Test whitespace normalization."""
        title = 'Title   with    extra     spaces'
        result = self.sanitize_filename(title)
        expected = 'Title with extra spaces'
        self.assertEqual(result, expected)
    
    def test_sanitize_length_limit(self):
        """Test length limitation."""
        title = 'A' * 150  # Very long title
        result = self.sanitize_filename(title)
        self.assertLessEqual(len(result), 100)
    
    def test_sanitize_normal_title(self):
        """Test with normal, clean title."""
        title = 'Normal Stream Title'
        result = self.sanitize_filename(title)
        self.assertEqual(result, title)


class TestNewFilenameGeneration(unittest.TestCase):
    """Test new filename generation."""
    
    def setUp(self):
        """Import the function we need to test."""
        with patch("builtins.open", mock_open(read_data=mock_config_data)):
            with patch("os.path.expanduser", return_value="/mock/config/path"):
                from twitch.rename_vods import generate_new_filename
                self.generate_new_filename = generate_new_filename
    
    def test_generate_new_filename_basic(self):
        """Test basic filename generation."""
        file_path = Path("20241024 14-29-04 [Author] old title [best][123].mp4")
        video = {
            'id': '456',
            'title': 'New Amazing Title',
            'user_name': 'author'
        }
        
        result = self.generate_new_filename(file_path, video)
        expected = "20241024 14-29-04 [Author] New Amazing Title [best][456].mp4"
        self.assertEqual(result, expected)
    
    def test_generate_new_filename_different_extension(self):
        """Test with .ts extension."""
        file_path = Path("20241024 14-29-04 [Author] old title [best][123].ts")
        video = {
            'id': '789',
            'title': 'Stream Title',
            'user_name': 'author'
        }
        
        result = self.generate_new_filename(file_path, video)
        expected = "20241024 14-29-04 [Author] Stream Title [best][789].ts"
        self.assertEqual(result, expected)
    
    def test_generate_new_filename_special_characters(self):
        """Test with title containing special characters."""
        file_path = Path("20241024 14-29-04 [Author] old title [best][123].mp4")
        video = {
            'id': '999',
            'title': 'Title: "Special" <Content>',
            'user_name': 'author'
        }
        
        result = self.generate_new_filename(file_path, video)
        expected = "20241024 14-29-04 [Author] Title_ _Special_ _Content_ [best][999].mp4"
        self.assertEqual(result, expected)


class TestVideoMatching(unittest.TestCase):
    """Test video matching based on date proximity."""
    
    def setUp(self):
        """Import the function we need to test."""
        with patch("builtins.open", mock_open(read_data=mock_config_data)):
            with patch("os.path.expanduser", return_value="/mock/config/path"):
                from twitch.rename_vods import find_matching_video
                self.find_matching_video = find_matching_video
    
    def test_find_exact_match(self):
        """Test finding exact date match."""
        file_path = Path("20241024 14-29-04 [Author] title [best][123].mp4")
        videos = [{
            'id': '456',
            'title': 'Stream Title',
            'created_at': '2024-10-24T14:29:04Z'
        }]
        
        result = self.find_matching_video(file_path, videos)
        self.assertIsNotNone(result)
        self.assertEqual(result['id'], '456')
    
    def test_find_closest_match(self):
        """Test finding closest date match."""
        file_path = Path("20241024 14-29-04 [Author] title [best][123].mp4")
        videos = [
            {
                'id': '111',
                'title': 'Far Stream',
                'created_at': '2024-10-20T10:00:00Z'  # 4+ days away
            },
            {
                'id': '222',
                'title': 'Close Stream',
                'created_at': '2024-10-24T15:00:00Z'  # ~30 minutes away
            },
            {
                'id': '333',
                'title': 'Very Far Stream',
                'created_at': '2024-10-30T10:00:00Z'  # 6+ days away
            }
        ]
        
        result = self.find_matching_video(file_path, videos)
        self.assertIsNotNone(result)
        self.assertEqual(result['id'], '222')  # Should pick the closest one
    
    def test_find_no_match_too_far(self):
        """Test when no video is within 24 hours."""
        file_path = Path("20241024 14-29-04 [Author] title [best][123].mp4")
        videos = [{
            'id': '456',
            'title': 'Stream Title',
            'created_at': '2024-10-20T14:29:04Z'  # 4 days away
        }]
        
        result = self.find_matching_video(file_path, videos)
        self.assertIsNone(result)
    
    def test_find_no_match_no_date(self):
        """Test when filename has no extractable date."""
        file_path = Path("random_video.mp4")
        videos = [{
            'id': '456',
            'title': 'Stream Title',
            'created_at': '2024-10-24T14:29:04Z'
        }]
        
        result = self.find_matching_video(file_path, videos)
        self.assertIsNone(result)


class TestTitleOverrides(unittest.TestCase):
    """Test suite for title override functionality."""

    def test_simple_text_removal(self):
        """Test simple substring removal (case-insensitive)."""
        title = "Amazing Stream with friends"
        overrides = ["Stream"]
        result = apply_title_overrides(title, overrides)
        self.assertEqual(result, "Amazing with friends")

    def test_simple_regex_pattern(self):
        """Test basic regex pattern with {{ }} syntax."""
        title = "Amazing Stream day 59 with friends"
        overrides = ["Stream", "day {{ \\d+ }}"]
        result = apply_title_overrides(title, overrides)
        self.assertEqual(result, "Amazing with friends")

    def test_multiple_regex_patterns(self):
        """Test multiple regex patterns in single override."""
        title = "Episode 42 - Part III - Some content here"
        overrides = ["Episode {{ \\d+ }} - Part {{ [IV]+ }} -"]
        result = apply_title_overrides(title, overrides)
        self.assertEqual(result, "Some content here")

    def test_complex_pattern_with_special_chars(self):
        """Test complex pattern with special characters and literal text."""
        title = "Math AND Geometry! - A test for who's the best? moving on... (day 60)"
        overrides = ["- A test for who's the best? moving on... (day {{ \\d+ }})"]
        result = apply_title_overrides(title, overrides)
        self.assertEqual(result, "Math AND Geometry!")

    def test_dreamyriko_social_links_removal(self):
        """Test removal of social media links from dreamyriko streams."""
        title = "*meow* I DONOTHON DAY... IDK I !uwumarket !commission !links !discord +18"
        overrides = ["I !uwumarket !commission !links !discord +18"]
        result = apply_title_overrides(title, overrides)
        self.assertEqual(result, "*meow* I DONOTHON DAY... IDK")

    def test_parentheses_removal_regex(self):
        """Test removing content in parentheses using regex."""
        title = "Gaming session (commentary) with friends"
        overrides = ["{{ \\([^)]*\\) }}"]
        result = apply_title_overrides(title, overrides)
        self.assertEqual(result, "Gaming session with friends")

    def test_multiple_overrides_applied(self):
        """Test multiple override patterns applied sequentially."""
        title = "【GENSHIN IMPACT】Stream Episode 123 - day 5"
        overrides = ["【GENSHIN IMPACT】", "Episode {{ \\d+ }} -", "day {{ \\d+ }}"]
        result = apply_title_overrides(title, overrides)
        self.assertEqual(result, "Stream")

    def test_case_insensitive_matching(self):
        """Test that matching is case-insensitive."""
        title = "AMAZING STREAM with friends"
        overrides = ["stream"]
        result = apply_title_overrides(title, overrides)
        self.assertEqual(result, "AMAZING with friends")

    def test_no_overrides(self):
        """Test that title is unchanged when no overrides provided."""
        title = "Original Title Here"
        overrides = []
        result = apply_title_overrides(title, overrides)
        self.assertEqual(result, "Original Title Here")

    def test_override_not_found(self):
        """Test that title is unchanged when override pattern not found."""
        title = "Original Title Here"
        overrides = ["NotInTitle"]
        result = apply_title_overrides(title, overrides)
        self.assertEqual(result, "Original Title Here")

    def test_whitespace_cleanup(self):
        """Test that extra whitespace is properly cleaned up."""
        title = "Title with    multiple    spaces"
        overrides = ["with"]
        result = apply_title_overrides(title, overrides)
        # Multiple spaces should be collapsed to single space
        self.assertEqual(result, "Title multiple spaces")


class TestFilenameGenerationWithOverrides(unittest.TestCase):
    """Test suite for filename generation with title overrides."""

    def test_dreamyriko_filename_transformation(self):
        """Test complete filename transformation for dreamyriko stream."""
        original_filename = "20251121 19-01-20 [dreamyriko] *meow* I DONOTHON DAY... IDK I !uwumarket !commission !links !discord +18 [best][315185271522].mp4"
        
        mock_video = {
            'id': '2624396721',
            'title': '*meow* I DONOTHON DAY... IDK I !uwumarket !commission !links !discord +18'
        }
        
        channel_config = {
            'title_overrides': ["I !uwumarket !commission !links !discord +18"]
        }
        
        mock_file = Path(original_filename)
        result = generate_new_filename(mock_file, mock_video, channel_config)
        
        # Note: * is sanitized to _ for filesystem compatibility
        expected = "20251121 19-01-20 [dreamyriko] _meow_ I DONOTHON DAY... IDK [best][2624396721].mp4"
        self.assertEqual(result, expected)

    def test_filename_with_complex_regex_override(self):
        """Test filename generation with complex regex override."""
        original_filename = "20241124 14-30-00 [TestStreamer] old title [best][999].mp4"
        
        mock_video = {
            'id': '1234567890',
            'title': 'Math AND Geometry! - A test for who\'s the best? moving on... (day 60)'
        }
        
        channel_config = {
            'title_overrides': ["- A test for who's the best? moving on... (day {{ \\d+ }})"]
        }
        
        mock_file = Path(original_filename)
        result = generate_new_filename(mock_file, mock_video, channel_config)
        
        expected = "20241124 14-30-00 [TestStreamer] Math AND Geometry! [best][1234567890].mp4"
        self.assertEqual(result, expected)

    def test_filename_without_overrides(self):
        """Test filename generation without any overrides."""
        original_filename = "20241124 14-30-00 [TestStreamer] old title [best][999].mp4"
        
        mock_video = {
            'id': '1234567890',
            'title': 'New Stream Title'
        }
        
        mock_file = Path(original_filename)
        result = generate_new_filename(mock_file, mock_video, None)
        
        expected = "20241124 14-30-00 [TestStreamer] New Stream Title [best][1234567890].mp4"
        self.assertEqual(result, expected)


class TestFindMatchingVideoRegression(unittest.TestCase):
    """Test cases to prevent regression in video matching logic."""
    
    def test_file_with_video_id_no_match_returns_none(self):
        """
        REGRESSION TEST: Files with existing video IDs that don't match API
        should return None to avoid false matches.
        
        This prevents Part 1 of a split stream (with deleted VOD) from being
        incorrectly matched to Part 2 based on timestamp proximity.
        """
        file_path = Path("20251105 18-39-15 [author] title part 1 [best][2610549917].mp4")
        
        # API only has Part 2 (the original Part 1 VOD was deleted)
        videos = [
            {
                'id': '2610552434',
                'stream_id': 2610552434,
                'title': 'title part 2',
                'created_at': '2025-11-05T18:40:00Z',
                'duration': '2h30m15s'
            }
        ]
        
        result = find_matching_video(file_path, videos)
        
        # Should return None because file has video ID 2610549917 but API doesn't have it
        self.assertIsNone(result, 
            "File with video ID not found in API should return None to avoid false match")
    
    def test_file_without_video_id_matches_by_date(self):
        """
        Files without video IDs (empty brackets) should use date-based matching.
        """
        file_path = Path("20251222 07-00-35 [author]  [best][].mp4")
        
        videos = [
            {
                'id': '2650137308',
                'stream_id': 2650137308,
                'title': 'some title',
                'created_at': '2025-12-22T06:00:30Z',  # ~1 hour before file timestamp
                'duration': '5h46m12s'
            },
            {
                'id': '2648840961',
                'stream_id': 2648840961,
                'title': 'Different title',
                'created_at': '2025-12-20T18:56:22Z',  # Much earlier
                'duration': '33m50s'
            }
        ]
        
        result = find_matching_video(file_path, videos)
        
        self.assertIsNotNone(result, "File without video ID should match by date")
        self.assertEqual(result['id'], '2650137308', 
            "Should match closest VOD within time threshold")
    
    def test_timezone_offset_within_threshold(self):
        """
        Test that timezone differences (up to 1 hour 5 min) are handled correctly.
        Files timestamped in local time should match VODs in UTC time.
        """
        file_path = Path("20251226 06-58-59 [author]  [best][].mp4")
        
        # VOD created at 05:58:56 UTC, file at 06:58:59 local = exactly 1 hour + 3 seconds diff
        videos = [
            {
                'id': '2653193045',
                'stream_id': 2653193045,
                'title': 'title here',
                'created_at': '2025-12-26T05:58:56Z',
                'duration': '3h45m27s'
            }
        ]
        
        result = find_matching_video(file_path, videos)
        
        self.assertIsNotNone(result, 
            "Should match VOD with ~1 hour timezone difference")
        self.assertEqual(result['id'], '2653193045')
    
    def test_time_threshold_boundary_exact(self):
        """
        Test boundary condition: exactly at 1 hour 5 minutes (3900 seconds).
        """
        file_path = Path("20251222 07-00-00 [test]  [best][].mp4")
        
        # VOD exactly 3900 seconds (65 minutes) before file
        videos = [
            {
                'id': '2650000001',
                'stream_id': 2650000001,
                'title': 'Boundary test',
                'created_at': '2025-12-22T05:55:00Z',  # 65 minutes before file
                'duration': '2h00m00s'
            }
        ]
        
        result = find_matching_video(file_path, videos)
        
        self.assertIsNotNone(result, 
            "Should match VOD exactly at threshold (3900 seconds)")
    
    def test_time_threshold_just_over(self):
        """
        Test boundary condition: just over 1 hour 5 minutes should not match.
        """
        file_path = Path("20251222 07-00-00 [test]  [best][].mp4")
        
        # VOD 3901 seconds (just over threshold) before file
        videos = [
            {
                'id': '2650000002',
                'stream_id': 2650000002,
                'title': 'Over threshold',
                'created_at': '2025-12-22T05:54:59Z',  # 65min 1sec before
                'duration': '2h00m00s'
            }
        ]
        
        result = find_matching_video(file_path, videos)
        
        self.assertIsNone(result, 
            "Should not match VOD over threshold (>3900 seconds)")
    
    def test_filters_out_short_vods(self):
        """
        VODs shorter than 10 seconds should be filtered out.
        These are typically stub VODs or test streams.
        """
        file_path = Path("20251224 07-00-00 [test]  [best][].mp4")
        
        videos = [
            {
                'id': '2651000001',
                'stream_id': 2651000001,
                'title': 'Short stub VOD',
                'created_at': '2025-12-24T07:00:01Z',  # Perfect time match
                'duration': '5s'  # But too short
            },
            {
                'id': '2651000002',
                'stream_id': 2651000002,
                'title': 'Valid VOD',
                'created_at': '2025-12-24T06:58:00Z',  # 2 min before
                'duration': '2h30m00s'
            }
        ]
        
        result = find_matching_video(file_path, videos)
        
        self.assertIsNotNone(result, "Should find a match after filtering short VODs")
        self.assertEqual(result['id'], '2651000002', 
            "Should match longer VOD, not the 5-second stub")
    
    def test_matches_by_stream_id_priority(self):
        """
        Test that stream_id matching takes priority over date matching.
        """
        file_path = Path("20251105 18-39-15 [author] stream [best][2610549917].mp4")
        
        videos = [
            {
                'id': 'v9999999',
                'stream_id': 2610549917,  # Matches file's video ID
                'title': 'Correct stream by stream_id',
                'created_at': '2025-11-03T10:00:00Z',  # Date way off
                'duration': '3h00m00s'
            },
            {
                'id': '2610550000',
                'stream_id': 2610550000,
                'title': 'Different stream',
                'created_at': '2025-11-05T18:39:20Z',  # Perfect date match
                'duration': '2h15m00s'
            }
        ]
        
        result = find_matching_video(file_path, videos)
        
        self.assertIsNotNone(result, "Should match by stream_id")
        self.assertEqual(result['id'], 'v9999999', 
            "Should prioritize stream_id match over date match")
    
    def test_prefers_earlier_vod_when_close(self):
        """
        When multiple VODs are within 30 seconds time difference,
        prefer the one that started before the file timestamp.
        """
        file_path = Path("20251225 07-00-00 [test]  [best][].mp4")
        
        videos = [
            {
                'id': '2652000001',
                'stream_id': 2652000001,
                'title': 'Started before file',
                'created_at': '2025-12-25T06:59:50Z',  # 10 sec before file (negative offset)
                'duration': '2h00m00s'
            },
            {
                'id': '2652000002',
                'stream_id': 2652000002,
                'title': 'Started after file',
                'created_at': '2025-12-25T07:00:05Z',  # 5 sec after file (positive offset)
                'duration': '2h00m00s'
            }
        ]
        
        result = find_matching_video(file_path, videos)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['id'], '2652000001', 
            "Should prefer VOD that started before file timestamp when both are close")


class TestExtractVideoIdEdgeCases(unittest.TestCase):
    """Test edge cases in video ID extraction."""
    
    def test_empty_brackets_returns_none(self):
        """Empty brackets [best][] should return None."""
        filename = "20251222 07-00-35 [author]  [best][].mp4"
        result = extract_video_id(filename)
        self.assertIsNone(result)
    
    def test_whitespace_only_in_brackets_returns_none(self):
        """Brackets with only whitespace should return None."""
        filename = "20251222 07-00-35 [author]  [best][   ].mp4"
        result = extract_video_id(filename)
        self.assertIsNone(result)
    
    def test_valid_video_id_extracted(self):
        """Valid video ID should be extracted correctly."""
        filename = "20251105 18-39-15 [author] stream [best][2610549917].mp4"
        result = extract_video_id(filename)
        self.assertEqual(result, "2610549917")
    
    def test_video_id_starting_with_v(self):
        """Video IDs starting with 'v' should be extracted."""
        filename = "20251105 18-39-15 [author] stream [best][v1234567890].mp4"
        result = extract_video_id(filename)
        self.assertEqual(result, "v1234567890")


class TestExtractDateFromFilenameEdgeCases(unittest.TestCase):
    """Test date extraction edge cases and boundary conditions."""
    
    def test_extract_full_datetime(self):
        """Extract full datetime YYYYMMDD HH-MM-SS."""
        filename = "20251222 07-00-35 [author]  [best][].mp4"
        result = extract_date_from_filename(filename)
        expected = datetime(2025, 12, 22, 7, 0, 35)
        self.assertEqual(result, expected)
    
    def test_extract_date_only(self):
        """Extract date only YYYYMMDD."""
        filename = "20251222 [author]  [best][].mp4"
        result = extract_date_from_filename(filename)
        expected = datetime(2025, 12, 22, 0, 0, 0)
        self.assertEqual(result, expected)
    
    def test_invalid_time_components(self):
        """Invalid time components fall back to date-only extraction."""
        # Hour >= 24 - should fall back to extracting just the date
        filename = "20251222 25-00-00 [test] stream.mp4"
        result = extract_date_from_filename(filename)
        # Falls back to date-only pattern, so should get the date with time 00:00:00
        self.assertEqual(result, datetime(2025, 12, 22, 0, 0, 0))
        
        # Minute >= 60 - should fall back to date-only
        filename = "20251222 07-61-00 [test] stream.mp4"
        result = extract_date_from_filename(filename)
        self.assertEqual(result, datetime(2025, 12, 22, 0, 0, 0))
        
        # Second >= 60 - should fall back to date-only
        filename = "20251222 07-00-61 [test] stream.mp4"
        result = extract_date_from_filename(filename)
        self.assertEqual(result, datetime(2025, 12, 22, 0, 0, 0))
    
    def test_no_date_in_filename(self):
        """Filename without date should return None."""
        filename = "[author] stream [best][123].mp4"
        result = extract_date_from_filename(filename)
        self.assertIsNone(result)


class TestParseDurationToSeconds(unittest.TestCase):
    """Test duration string parsing."""
    
    def test_parse_hours_minutes_seconds(self):
        """Parse full duration with hours, minutes, and seconds."""
        self.assertEqual(parse_duration_to_seconds("2h46m14s"), 9974)
        self.assertEqual(parse_duration_to_seconds("5h46m12s"), 20772)
    
    def test_parse_minutes_seconds(self):
        """Parse duration with only minutes and seconds."""
        self.assertEqual(parse_duration_to_seconds("4m40s"), 280)
        self.assertEqual(parse_duration_to_seconds("33m50s"), 2030)
    
    def test_parse_seconds_only(self):
        """Parse duration with only seconds."""
        self.assertEqual(parse_duration_to_seconds("10s"), 10)
        self.assertEqual(parse_duration_to_seconds("5s"), 5)
    
    def test_parse_hours_only(self):
        """Parse duration with only hours."""
        self.assertEqual(parse_duration_to_seconds("2h"), 7200)
    
    def test_parse_empty_string(self):
        """Empty string should return 0."""
        self.assertEqual(parse_duration_to_seconds(""), 0)
    
    def test_parse_no_match(self):
        """String with no duration pattern should return 0."""
        self.assertEqual(parse_duration_to_seconds("invalid"), 0)


if __name__ == '__main__':
    unittest.main()