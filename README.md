# Cameron Institute Survey Maker

This web application is meant to be used by the Cameron Institute to help measure the success of Student‑Athletes at Cal by collecting survey data. Staff can log in, browse previously used questions, assemble surveys, and export completed surveys.

## Key functions
- Gather historical questions
  - Loads all questions the Cameron Institute has used in prior years via the Google Workspace APIs and consolidates them into a pandas DataFrame for easy browsing and filtering.
- Staff authentication
  - Staff log in using Google OAuth to gain access to the application and protected endpoints.
- Search & filter question bank
  - Search the question DataFrame using a free-text query and refine results with filters (category, sub‑category, level, etc.).
- Build surveys
  - Add selected questions to a temporary cart, review the cart, and compose surveys from chosen items.
- Export
  - Export composed surveys to Google Docs / Drive (uses Google API credentials for authorized staff).

## Project layout (important files)
- api/app.py — Flask application and routes (UI + JS endpoints).
- api/oauth.py — Google OAuth initialization and helpers.
- api/decorators.py — authentication and token decorators used by routes.
- api/googleSheet.py — code that reads data from Google Sheets / Workspace and constructs the DataFrame.
- api/models.py — database models (User, CartItem, etc.).
- run.py — application entrypoint that runs initialization (DB + loading question DataFrame) and starts the server.