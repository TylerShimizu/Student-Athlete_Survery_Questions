import os
from authlib.integrations.flask_client import OAuth
from google.oauth2.credentials import Credentials

oauth = OAuth()

def init_oauth(app):
    """
    Initialize and register the Google OAuth client.
    Call this from app.py after creating the Flask app.
    Returns the registered google client.
    """
    oauth.init_app(app)

    google = oauth.register(
        name="google",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        access_token_url="https://oauth2.googleapis.com/token",
        authorize_url="https://accounts.google.com/o/oauth2/auth",
        authorize_params=None,
        access_token_params=None,
        api_base_url="https://www.googleapis.com/oauth2/v1/",
        server_metadata_url=os.getenv("GOOGLE_DISCOVERY_URL"),
        userinfo_endpoint="https://www.googleapis.com/oauth2/v2/userinfo",
        client_kwargs={
            'scope': (
                'openid email profile '
                'https://www.googleapis.com/auth/documents '
                'https://www.googleapis.com/auth/drive.file'
            )
        }
    )

    return google

def get_cred(token):
    return Credentials(
        token=token["access_token"],
        refresh_token=token.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET")
    )
