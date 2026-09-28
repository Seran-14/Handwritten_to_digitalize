import os
import requests
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

api_key = os.environ.get("GROQ_API_KEY")

if not api_key:
    print("Error: GROQ_API_KEY is not set in your .env file.")
    exit(1)

url = "https://api.groq.com/openai/v1/models"
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

response = requests.get(url, headers=headers)
data = response.json()

if "data" in data:
    print("--- Available Groq Models ---")
    for model in data["data"]:
        print(f"- {model['id']} (Owner: {model.get('owned_by', 'N/A')})")
else:
    print(data)
