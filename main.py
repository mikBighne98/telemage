import base64
import os

import requests
from deta import Drive
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Template

app = FastAPI()
app.mount("/public", StaticFiles(directory="public"), name="public")

photos = Drive("generations")

BOT_KEY = os.getenv("TELEGRAM")
OPEN_AI_KEY = os.getenv("OPEN_AI")
BOT_URL = f"https://api.telegram.org/bot{BOT_KEY}/"
OPEN_AI_URL = "https://api.openai.com/v1/images/generations"


def get_image_from_prompt(prompt):
    open_ai_data = {
        "prompt": prompt,
        "n": 1,
        "size": "512x512",
        "response_format": "b64_json",
    }
    auth_header = f"Bearer {OPEN_AI_KEY}"
    headers = {"Content-Type": "application/json", "Authorization": auth_header}
    response = requests.post(OPEN_AI_URL, json=open_ai_data, headers=headers).json()
    if "error" not in response:
        return {
            "b64img": response["data"][0]["b64_json"],
            "created": response["created"],
        }
    return {"error": response["error"]["message"]}


def save_and_send_img(b64img, chat_id, prompt, timestamp):
    image_data = base64.b64decode(b64img)
    filename = f"{timestamp} - {prompt}.png"
    photos.put(filename, image_data)
    photo_payload = {"photo": image_data}
    message_url = f"{BOT_URL}sendPhoto?chat_id={chat_id}&caption={prompt}"
    requests.post(message_url, files=photo_payload).json()
    return {"chat_id": chat_id, "caption": prompt}


def send_error(chat_id, error_message):
    message_url = f"{BOT_URL}sendMessage"
    payload = {"text": error_message, "chat_id": chat_id}
    return requests.post(message_url, json=payload).json()


def get_webhook_info():
    message_url = f"{BOT_URL}getWebhookInfo"
    return requests.get(message_url).json()


@app.get("/")
def home():
    home_template = Template((open("index.html").read()))
    if BOT_KEY == "enter your key" or OPEN_AI_KEY == "enter your key":
        return HTMLResponse(home_template.render(status="SETUP_ENVS"))
    response = get_webhook_info()
    if response and "result" in response and not response["result"]["url"]:
        return HTMLResponse(home_template.render(status="SETUP_WEBHOOK"))
    if response and "result" in response and "url" in response["result"]:
        return HTMLResponse(home_template.render(status="READY"))
    return HTMLResponse(home_template.render(status="ERROR"))


@app.get("/ping")
def ping():
    payload = {"text": "pong"}
    message_url = f"{BOT_URL}sendMessage"
    requests.post(message_url, json=payload).json()


@app.post("/open")
async def http_handler(request: Request):
    incoming_data = await request.json()
    if "message" not in incoming_data:
        print(incoming_data)
        return send_error(None, "Unknown error, lol, handling coming soon")
    prompt = incoming_data["message"]["text"]
    user_identity = incoming_data["message"]["chat"]["id"]

    if prompt == "/start":
        response_text = (
            "Welcome to Telemage. To generate an image with AI, simply"
            " send me a prompt or phrase and I'll create something amazing!"
        )
        payload = {"text": response_text, "chat_id": user_identity}
        message_url = f"{BOT_URL}sendMessage"
        requests.post(message_url, json=payload).json()
        return

    if prompt == "/help":
        response_text = (
            "To generate an image, simply send me a prompt or phrase and I'll do my"
            " best to create something amazing!"
        )
        payload = {"text": response_text, "chat_id": user_identity}
        message_url = f"{BOT_URL}sendMessage"
        requests.post(message_url, json=payload).json()
        return

    open_ai_resp = get_image_from_prompt(prompt)
    if "b64img" in open_ai_resp:
        return save_and_send_img(
            open_ai_resp["b64img"], user_identity, prompt, open_ai_resp["created"]
        )

    if "error" in open_ai_resp:
        return send_error(user_identity, open_ai_resp["error"])
    return send_error(user_identity, "Unknown error, lol, handling coming soon")


@app.get("/set_webhook")
def url_setter():
    PROG_URL = os.getenv("DETA_SPACE_APP_HOSTNAME")
    set_url = f"{BOT_URL}setWebHook?url=https://{PROG_URL}/open"
    resp = requests.get(set_url)
    return resp.json()
