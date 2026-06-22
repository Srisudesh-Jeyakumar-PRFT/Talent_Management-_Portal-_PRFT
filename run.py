import os
from dotenv import load_dotenv

# Load .env before anything else so SECRET_KEY and DATABASE_URL are available
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

from app import create_app, db

app = create_app("development")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, host="0.0.0.0", port=5000)
