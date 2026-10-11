"""Terminal client for trying the interviewer without setting up a Discord bot.

Start the API first (uvicorn api.main_api:app), then run: python cli.py
"""
import uuid

import requests

BACKEND_URL = "http://127.0.0.1:8000/api/chat"


def main():
    user_id = f"cli-{uuid.uuid4().hex[:8]}"
    print("AI Interviewer. Name a topic to start (for example 'Python', 'ROS 2', 'computer vision').")
    print("Type 'quit' to exit.\n")
    while True:
        message = input("You: ").strip()
        if message.lower() in {"quit", "exit"}:
            break
        if not message:
            continue
        r = requests.post(BACKEND_URL, json={"user_id": user_id, "message": message}, timeout=120)
        if r.status_code != 200:
            print(f"[error {r.status_code}] {r.text}\n")
            continue
        data = r.json()
        print(f"\nInterviewer: {data['reply']}\n")
        if data["finished"]:
            print("(Report saved. Send 'restart' for a new interview, or 'quit'.)\n")


if __name__ == "__main__":
    main()
