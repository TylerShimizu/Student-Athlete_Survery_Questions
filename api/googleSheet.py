import os
import json

from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import Flow
import pandas as pd
from datetime import datetime
from api.models import Question, db

from collections import defaultdict
from dotenv import load_dotenv
load_dotenv()

spreadsheet_id = os.getenv("GOOGLE_SPEADSHEET")
range_name = ['Career Development!A2:Z', 'Community Engagement!A1:Z', 'Student-Athlete Performance!A1:Z', 'Personal Development, Misc.!A1:Z']
DISCOVERY_DOC = "https://forms.googleapis.com/$discovery/rest?version=v1"

API_KEY = os.getenv("GOOGLE_API_KEY")
CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

flow = Flow.from_client_config(
    {
        "web": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uris": ["http://localhost:5000/callback", "https://dreamproj.onrender.com/callback", "https://dreamproj-7098.onrender.com/callback"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token"
        }
    },
    scopes=[
        "https://www.googleapis.com/auth/documents",
        "https://www.googleapis.com/auth/drive.file"
    ]
)

def main():
    try:
        data = {}
        id_and_questions = {}
        master_df = pd.DataFrame()
        for spread in range_name:
            service = build("sheets", "v4", developerKey=API_KEY)
            sheet = service.spreadsheets() # Call the Sheets API
            result = (
                sheet.values()
                .get(spreadsheetId=spreadsheet_id, range=spread)
                .execute()
            )   
            values = result.get("values", [])
            if not values:
                print(f"No data found for {spread}")
                continue
            df = pd.DataFrame(values)

            # First sheet: set headers
            if master_df.empty:
                df.columns = df.iloc[0]
                df = df[1:]
            else:
                df.columns = master_df.columns[:-1]  # match existing columns

            # Add category (cleaner)
            category_name = spread[:-5]  # assuming consistent format (how can we generalize this?)
            df["Category"] = category_name
            master_df = pd.concat([master_df, df], ignore_index=True) # Append WITHOUT dropping rows again

            #Making each entry in values to be a Questions object
            category = spread[:len(spread) - 5]
            sub_categories = defaultdict(list)
            for i in range(len(values)):
                temp = values[i]
                temp[4] = temp[4].split("->")
                if len(temp) < 2:
                    sub = temp[4][0]
                else:
                    sub = ""

                q = Question.query.filter_by(level=temp[0], category=category, sub_category=sub, stem=temp[5], anchor=temp[7], method=temp[6]).first()
                if not q: # Create a new Question object
                    new = Question(
                        level = temp[0], 
                        category = category, 
                        sub_category = temp[4][0], 
                        stem = temp[5], 
                        anchor = temp[7], 
                        method = temp[6]
                    )
                    db.session.add(new)
                db.session.commit()
            data[category] = sub_categories #Adding sheet into data dictionary with its sheet name as keys

        # Reset index of the final DataFrame for cleaner data
        master_df.reset_index(drop=True, inplace=True)
        master_df['id'] = master_df.index
        master_df['Sub-Category'] = master_df['Sub-Category'].str.split('->').str[0]
        return data, id_and_questions, master_df

    except HttpError as err:
        print(err)

def create_doc(questions, creds, docId):
    try:
        service = build("docs", "v1", credentials=creds)
        if docId is None: # If no docId, create a new document
            title = {
                "title": "Sample Survey"
            }
            doc = service.documents().create(body=title).execute()
            docId = doc.get("documentId")
        else:
            doc = service.documents().get(documentId=docId).execute() # Get the current document to find its length (needed for clearing)
            content = doc.get("body", {}).get("content", [])
            content_length = content[-1].get("endIndex", 1) if content else 1

            # Clear existing content (from index 1 to end)
            clear_request = [{
                "deleteContentRange": {
                    "range": {
                        "startIndex": 1,
                        "endIndex": content_length - 1
                    }
                }
            }]
            service.documents().batchUpdate(documentId=docId, body={"requests": clear_request}).execute()

        requests = []
        current_index = 1

        for _, question in questions.iterrows(): # Insert the question text
            if question is not None:
                requests.append({
                    "insertText": {
                        "location": {
                            "index": current_index
                        },
                        "text": question["Item Stem"] + "\n"
                    }
                })
                current_index += len(question["Item Stem"]) + 1
                anchors = question["Anchors"].split(";")
                if len(anchors) > 0:
                    for choice in anchors:
                        requests.append({
                            "insertText": {
                                "location": {
                                    "index": current_index
                                },
                                "text": "\t" + choice + "\n"
                            }
                        })
                        current_index += len(choice) + 2
        requests.append({
            'createParagraphBullets': {
                'range': {
                    'startIndex': 1,
                    'endIndex': current_index
                },
                'bulletPreset': 'NUMBERED_DECIMAL_ALPHA_ROMAN_PARENS',
            }
        })
        service.documents().batchUpdate(documentId=docId, body={"requests": requests}).execute()
        return docId

    except HttpError as err:
        print(f"An error occurred: {err}")
    except Exception as err:
        print(f"Unexpected error: {err}")


if __name__ == "__main__":
  main()