import os
import json
import gspread

from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets"
]

credentials_dict = json.loads(
    os.environ["GOOGLE_CREDENTIALS_JSON"]
)

creds = Credentials.from_service_account_info(
    credentials_dict,
    scopes=SCOPES
)

client = gspread.authorize(creds)

sheet = client.open_by_key(
    "1YIH_rfIlLCmWPG4-Zn_4RlsNsEvxRWdc8_6LiIOhCPc"
)


def test_connection():
    worksheet = sheet.worksheet("Importaciones")

    worksheet.append_row([
        "TEST",
        "CONEXION OK"
    ])

    return True