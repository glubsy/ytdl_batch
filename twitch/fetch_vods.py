"""
This script fetches and displays videos from a specified Twitch channel using the Twitch API.

reference:
https://dev.twitch.tv/docs/authentication/getting-tokens-oauth
"""

import requests
import json
import time
import logging
from pathlib import Path
from os import environ
from sys import argv

CLIENT_ID = environ['TWITCH_CLIENT_ID']
CLIENT_SECRET = environ['TWITCH_CLIENT_SECRET']

# Set up logger - use same parent as rename_vods for consistent formatting
log = logging.getLogger("rename.fetch_vods")
log.setLevel(logging.INFO)

# Cache file location
TOKEN_CACHE_FILE = Path('/tmp/twitch_access_token_cache.json')


def get_access_token(client_id: str, client_secret: str) -> str:
    """Get access token with caching to avoid unnecessary API calls."""
    # Check if cached token exists and is still valid
    if TOKEN_CACHE_FILE.exists():
        try:
            with open(TOKEN_CACHE_FILE, 'r') as f:
                cache_data = json.load(f)
            
            # Check if token is still valid (expires_in is typically 5184000 seconds = ~60 days)
            # We'll refresh if less than 1 hour remains to be safe
            time_remaining = cache_data['expires_at'] - time.time()
            if time_remaining > 3600:  # More than 1 hour remaining
                log.info(
                    "Using cached access token (expires in %.1f hours)", 
                    time_remaining/3600
                )
                return cache_data['access_token']
            else:
                log.info("Cached token expired or expires soon, refreshing...")
        except (json.JSONDecodeError, KeyError, FileNotFoundError):
            log.warning("Invalid cache file, requesting new token...")
    
    # Request new token
    log.info("Requesting new access token from Twitch API...")
    url = 'https://id.twitch.tv/oauth2/token'
    params = {
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'client_credentials'
    }
    response = requests.post(url, params=params)
    response.raise_for_status()  # Raise exception for HTTP errors
    
    token_data = response.json()
    access_token = token_data['access_token']
    expires_in = token_data.get('expires_in', 5184000)  # Default to 60 days if not provided
    
    # Cache the token
    cache_data = {
        'access_token': access_token,
        'expires_in': expires_in,
        'expires_at': time.time() + expires_in,
        'created_at': time.time()
    }
    
    try:
        with open(TOKEN_CACHE_FILE, 'w') as f:
            json.dump(cache_data, f, indent=2)
        log.info(
            "Token cached to %s (expires in %.1f hours)",
            TOKEN_CACHE_FILE, expires_in/3600)
    except Exception as exc:
        log.warning(
            "Could not cache token to %s: %s", TOKEN_CACHE_FILE, exc)
    
    return access_token


def clear_token_cache() -> bool:
    """Clear the cached access token. Returns True if cache was cleared, False if no cache existed."""
    if TOKEN_CACHE_FILE.exists():
        try:
            TOKEN_CACHE_FILE.unlink()
            log.info("Token cache cleared: %s", TOKEN_CACHE_FILE)
            return True
        except Exception as exc:
            log.error("Error clearing token cache: %s", exc)
            return False
    else:
        log.info("No token cache to clear")
        return False


def fetch_videos(channel_name: str, access_token: str) -> list:
    url = f'https://api.twitch.tv/helix/videos'
    headers = {
        'Client-ID': CLIENT_ID,
        'Authorization': f'Bearer {access_token}'
    }
    params = {
        'user_id': get_user_id(channel_name, access_token),
        'type': 'archive',
    }
    
    all_videos = []
    cursor = None
    
    while True:
        if cursor:
            params['after'] = cursor
        elif 'after' in params:
            del params['after']
            
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        
        # Add videos from current page to our collection
        videos = data.get('data', [])
        all_videos.extend(videos)
        
        # Check if there's a next page
        pagination = data.get('pagination', {})
        cursor = pagination.get('cursor')
        
        # If no cursor, we've reached the end
        if not cursor:
            break
    
    return all_videos


def get_user_id(channel_name: str, access_token: str) -> str:
    url = 'https://api.twitch.tv/helix/users'
    headers = {
        'Client-ID': CLIENT_ID,
        'Authorization': f'Bearer {access_token}'
    }
    params = {
        'login': channel_name
    }
    response = requests.get(url, headers=headers, params=params)
    
    if not (data := response.json().get('data', [])):
        raise ValueError(f"Channel '{channel_name}' not found")
    
    if not (id := data[0].get('id')):
        raise ValueError(f"User ID not found for channel '{channel_name}'")
    
    return id


def main(args: list[str]) -> None:
    access_token = get_access_token(CLIENT_ID, CLIENT_SECRET)
    channel_name = args[1]
    videos = fetch_videos(channel_name, access_token)

    if not videos:
        print("No videos found for this channel.")
        return
    print(f"Fetched {len(videos)} videos from channel '{channel_name}':")

    for video in videos:
        print(
            f"Title: {video['title']}, URL: {video['url']}, "
            f"Created At: {video['created_at']}, "
            f"Duration: {video['duration']}, "
            f"Muted Segments: {video.get('muted_segments', 'N/A')}"
        )


if __name__ == '__main__':
    main(argv)