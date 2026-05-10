import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-3-pro-preview")
try:
    print("Calling Gemini 3 Pro with simple prompt...")
    res = model.generate_content("Hi, are you there?")
    print(f"Response: {res.text}")
    print("[SUCCESS] Auth confirmed for Gemini 3 Pro.")
except Exception as e:
    print(f"[ERROR] {e}")
