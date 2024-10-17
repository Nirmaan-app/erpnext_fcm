import frappe
import requests
import json
from frappe import enqueue
import re
import google
from google import service_account


def user_id(doc):
    user_email = doc.for_user
    user_device_id = frappe.get_all(
        "User Device", filters={"user": user_email}, fields=["device_id"]
    )
    return user_device_id


@frappe.whitelist()
def send_notification(doc, event):
    device_ids = user_id(doc)
    for device_id in device_ids:
        enqueue(
            process_notification,
            queue="default",
            now=False,
            device_id=device_id,
            notification=doc,
        )


def convert_message(message):
    CLEANR = re.compile("<.*?>")
    cleanmessage = re.sub(CLEANR, "", message)
    # cleantitle = re.sub(CLEANR, "",title)
    return cleanmessage

def _get_access_token():
  """Retrieve a valid access token that can be used to authorize requests.

  :return: Access token.
  """
  SCOPES=("https://www.googleapis.com/auth/firebase.messaging")
  server_key = frappe.db.get_single_value("FCM Notification Settings", "server_key")
  credentials = service_account.Credentials.from_service_account_info(server_key, scopes=SCOPES)
  request = google.auth.transport.requests.Request()
  credentials.refresh(request)
  return credentials.token


def process_notification(device_id, notification):
    message = notification.email_content
    title = notification.subject
    if message:
        message = convert_message(message)
    if title:
        title = convert_message(title)
    project = frappe.db.get_single_value("FCM Notification Settings", "gcp_project_name")
    url = "https://fcm.googleapis.com/v1/projects/"+project+"/messages:send"
    body = {
        "message": {
            "token": device_id.device_id,
        "notification": {"body": message, "title": title},
        "data": {
            "doctype": notification.document_type,
            "docname": notification.document_name,
        }
        },
    }

    auth = f"Bearer "+_get_access_token()
    req = requests.post(
        url=url,
        data=json.dumps(body),
        headers={
            "Authorization": auth,
            "Content-Type": "application/json; UTF-8",
        },
    )
    frappe.log_error(req.text)
