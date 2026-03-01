import os
import json
from file_modifier import execute_python_code

# The credentials provided by the user
creds = """
{
  "type": "service_account",
  "project_id": "dummy-project-id",
  "private_key_id": "dummy-key-id",
  "private_key": "-----BEGIN PRIVATE KEY-----\\nfake_key_data\\n-----END PRIVATE KEY-----\\n",
  "client_email": "dummy@dummy.iam.gserviceaccount.com",
  "client_id": "1234567890",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/dummy%40dummy.iam.gserviceaccount.com",
  "universe_domain": "googleapis.com"
}
"""
os.environ["GOOGLE_CREDENTIALS_JSON"] = creds

code = """
import gspread
import traceback

try:
    print("Testing inside sandbox...")
    print(dir(gspread_client))
    # This shouldn't fail since we pre-injected gspread_client in file_modifier
except Exception as e:
    print(traceback.format_exc())
"""

r, f, e = execute_python_code(code)
print("ERROR:" , e)
