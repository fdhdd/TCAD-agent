from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.getenv("API_KEY_NAME")

print(api_key)