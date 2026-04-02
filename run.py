import os
from dotenv import load_dotenv
import pandas as pd

# import the app module so we can attach runtime objects onto it
import api.app as app_module
from api.models import db
import api.googleSheet as google_api

# load .env at project root
load_dotenv(dotenv_path=os.path.abspath(os.path.join(os.path.dirname(__file__), '.env')))

def initialize_app():
    with app_module.app.app_context():
        # ensure database tables exist
        db.create_all()

        # attempt to load sheets/df; fall back to empty DataFrame on error
        try:
            _, _, df = google_api.main()
        except Exception as e:
            print("Warning: google_api.main() failed:", e)
            df = pd.DataFrame()

        # attach objects back onto api.app so routes can reference them
        app_module.df = df

        CATEGORIES = sorted(df["Category"].unique()) if not df.empty else []
        app_module.CATEGORIES = CATEGORIES
        app_module.CATEGORY_MAP = {
            cat: sorted(df[df["Category"] == cat]["Sub-Category"].unique())
            for cat in CATEGORIES
        }

        LEVELS = {"Levels": []}
        if not df.empty:
            LEVELS["Levels"].extend(
                sorted(df[df["Levels"].str.startswith("Level")]["Levels"].unique())
            )
            for other in sorted(df[~df["Levels"].str.startswith("Level")]["Levels"].unique()):
                LEVELS[other] = [other]
        app_module.LEVELS = LEVELS

if __name__ == "__main__":
    initialize_app()
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "1") == "1"
    app_module.app.run(host="0.0.0.0", port=port, debug=debug)