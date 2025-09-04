# utils/auth.py
import os
from dotenv import load_dotenv

load_dotenv()

def check_credentials(username: str, password: str) -> bool:
    login = os.getenv("LOGIN")
    pwd = os.getenv("PASSWORD")
    return username == login and password == pwd
