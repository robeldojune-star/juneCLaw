#!/usr/bin/env python3
import os
from pathlib import Path
from core.kiwoom_client import KiwoomAPIClient

def test_env(env_path):
    print(f"Testing environment file: {env_path}")
    if not Path(env_path).exists():
        print("File does not exist")
        return False
    try:
        client = KiwoomAPIClient.from_env(env_path=env_path)
        # Try to issue a token (this will make a network call)
        token = client.issue_token()
        print("OAuth token obtained successfully (token hidden)")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    base = Path(__file__).resolve().parents[1]  # /home/june/trading
    mock_env = base / "envs" / "mock" / ".env"
    prod_env = base / "envs" / "prod" / ".env"
    print("=== Testing mock environment ===")
    test_env(mock_env)
    print("=== Testing prod environment ===")
    test_env(prod_env)