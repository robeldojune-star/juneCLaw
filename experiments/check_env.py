import os
from dotenv import load_dotenv

load_dotenv()  # loads .env if present

def getv(key, default="❌ NOT SET"):
    return os.getenv(key, default)

print("=== Kiwoom API Environment Check ===")
print("TRADING_ENV   :", getv("TRADING_ENV"))
print("-------------- MOCK --------------")
print("KIWOOM_REST_API_KEY_MOCK :", getv("KIWOOM_REST_API_KEY_MOCK"))
print("KIWOOM_REST_API_SECRET_MOCK:", getv("KIWOOM_REST_API_SECRET_MOCK"))
print("KIWOOM_ACCOUNT_NO_MOCK   :", getv("KIWOOM_ACCOUNT_NO_MOCK"))
print("-------------- PROD --------------")
print("KIWOOM_REST_API_KEY_PROD :", getv("KIWOOM_REST_API_KEY_PROD"))
print("KIWOOM_REST_API_SECRET_PROD:", getv("KIWOOM_REST_API_SECRET_PROD"))
print("KIWOOM_ACCOUNT_NO_PROD   :", getv("KIWOOM_ACCOUNT_NO_PROD"))
print("-------------- FALLBACK (no suffix) --------------")
print("KIWOOM_REST_API_KEY :", getv("KIWOOM_REST_API_KEY"))
print("KIWOOM_REST_API_SECRET:", getv("KIWOOM_REST_API_SECRET"))
print("KIWOOM_ACCOUNT_NO   :", getv("KIWOOM_ACCOUNT_NO"))
print("==================================")