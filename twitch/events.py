"""
Listen for Twitch events such as stream online/offline using Twitch EventSub API.
This can be used to trigger actions in your application when a streamer goes live.

reference:
https://dev.twitch.tv/docs/api/reference#create-eventsub-subscription
"""

from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

CLIENT_ID = 'your_client_id'
CLIENT_SECRET = 'your_client_secret'
WEBHOOK_URL = 'https://yourdomain.com/twitch-webhook'  # Your public URL
CALLBACK_SECRET = 'your_callback_secret'

def get_access_token():
    url = 'https://id.twitch.tv/oauth2/token'
    params = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'client_credentials'
    }
    response = requests.post(url, params=params)
    return response.json()['access_token']

def subscribe_to_streams(access_token):
    url = 'https://api.twitch.tv/helix/eventsub/subscriptions'
    headers = {
        'Client-ID': CLIENT_ID,
        'Authorization': f'Bearer {access_token}'
    }
    data = {
        "type": "stream.online",
        "version": "1",
        "condition": {
            "broadcaster_user_id": "user_id"  # Replace with the Twitch user ID
        },
        "transport": {
            "method": "webhook",
            "callback": WEBHOOK_URL,
            "secret": CALLBACK_SECRET
        }
    }
    response = requests.post(url, headers=headers, json=data)
    return response.json()

@app.route('/twitch-webhook', methods=['POST'])
def twitch_webhook():
    # Verify the webhook signature here if needed

    event = request.json
    print('Received event:', event)  # Handle the event, e.g., notify your application
    return jsonify(status='success'), 200

@app.route('/twitch-webhook', methods=['GET'])
def verify_webhook():
    # This is the verification request from Twitch
    hub_mode = request.args.get('hub.mode')
    hub_challenge = request.args.get('hub.challenge')
    hub_secret = request.args.get('hub.verify_token')

    if hub_mode == 'subscribe' and hub_secret == CALLBACK_SECRET:
        return hub_challenge, 200
    return 'Verification failed', 403

if __name__ == '__main__':
    access_token = get_access_token()
    subscribe_to_streams(access_token)
    app.run(port=5000)