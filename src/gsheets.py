import json
import os
from datetime import datetime

import pandas as pd
import pytz
from google.oauth2 import service_account
from googleapiclient.discovery import build

from src.auth import GetAwsSecret

GSHEET_SECRET_NAME = "whoosh-service-gcloud_service_account_secret"
REGION_NAME = "eu-west-1"
GOOGLE_SHEET_ID = "1pk6WUhH0_eYCE00BmhsyOAv0HAZyBE2FjYQavGN1toI"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class GoogleSheets:
    def __init__(self) -> None:
        self.gsheet_secret = GetAwsSecret(
            GSHEET_SECRET_NAME, REGION_NAME
        ).get_aws_secret()
        self.service = GoogleSheets.get_google_service(
            self, self.gsheet_secret, scopes=SCOPES
        )

    def get_google_service(self, service_secret: str, scopes: list = SCOPES):
        credentials = service_account.Credentials.from_service_account_info(
            service_secret, scopes=scopes
        )
        service = build("sheets", "v4", credentials=credentials, cache_discovery=False)

        return service

    def get_authenticated_users(self, sheet_id: str = GOOGLE_SHEET_ID, forced=False):

        values = (
            self.service.spreadsheets()
            .values()
            .get(
                spreadsheetId=sheet_id,
                range="Участники!D:E",
            )
            .execute()
        )
        values = values["values"][1:]

        return values

    def get_results(self, sheet_id: str = GOOGLE_SHEET_ID):

        values = (
            self.service.spreadsheets()
            .values()
            .get(
                spreadsheetId=sheet_id,
                range="Ответы участников!A:E",
            )
            .execute()
        )
        values = values["values"][1:]

        return values

    def df_to_spreadsheets(
        self, google_df: pd.DataFrame, sheet_id: str = GOOGLE_SHEET_ID
    ) -> bool:

        if not hasattr(self.service, "spreadsheets"):
            raise AttributeError("Service has no attribute 'spreadsheets'.")

        self.service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range="Ответы участников!A:D",
            body={"majorDimension": "ROWS", "values": google_df.values.tolist()},
            valueInputOption="USER_ENTERED",
        ).execute()

        return True
