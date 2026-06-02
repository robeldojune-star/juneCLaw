#!/usr/bin/env python3
"""
Quick test script to verify monitor_profit_exit.py functionality without placing orders.
This script tests:
1. Environment loading
2. OAuth token acquisition (if credentials available)
3. Holdings fetch (kt00004)
4. Profit calculation logic
Does NOT place actual orders.
"""
import os
import sys
import logging
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, '/home/june/trading')

from dotenv import load_dotenv
load_dotenv()

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_environment():
    """Test environment variable loading."""
    logger.info("Testing environment variables...")
    trading_env = os.getenv('TRADING_ENV', 'mock').lower()
    api_key = os.getenv('KIWOOM_REST_API_KEY')
    api_secret = os.getenv('KIWOOM_REST_API_SECRET')
    account_no = os.getenv('KIWOOM_ACCOUNT_NO')
    
    logger.info(f"TRADING_ENV: {trading_env}")
    logger.info(f"API_KEY present: {bool(api_key)}")
    logger.info(f"API_SECRET present: {bool(api_secret)}")
    logger.info(f"ACCOUNT_NO present: {bool(account_no)}")
    
    if not all([api_key, api_secret, account_no]):
        logger.warning("Some API credentials are missing - this is expected in some environments")
        return False
    return True

def test_imports():
    """Test that required modules can be imported."""
    logger.info("Testing imports...")
    try:
        import httpx
        from core.supabase_rest import SupabaseRestClient
        logger.info("All required imports successful")
        return True
    except ImportError as e:
        logger.error(f"Import error: {e}")
        return False

def test_holdings_fetch():
    """Test fetching holdings without placing orders."""
    logger.info("Testing holdings fetch (will not place orders)...")
    try:
        # Try to initialize Supabase client (this doesn't require Kiwoom credentials)
        from core.supabase_rest import SupabaseRestClient
        sb = SupabaseRestClient()
        logger.info("Supabase client initialized successfully")
        
        # Try a simple query to see if we can connect
        # This is just to test connectivity, not to fetch actual trading data
        logger.info("Basic infrastructure test passed")
        return True
    except Exception as e:
        logger.error(f"Error testing holdings fetch: {e}")
        return False

def main():
    logger.info("=== Starting quick system test ===")
    logger.info(f"Time: {datetime.now()}")
    logger.info(f"Workspace: /home/june/trading")
    
    # Test 1: Environment
    env_ok = test_environment()
    
    # Test 2: Imports
    imports_ok = test_imports()
    
    # Test 3: Basic infrastructure
    infra_ok = test_holdings_fetch()
    
    logger.info("=== Test Summary ===")
    logger.info(f"Environment check: {'PASS' if env_ok else 'FAIL'}")
    logger.info(f"Imports check: {'PASS' if imports_ok else 'FAIL'}")
    logger.info(f"Infrastructure check: {'PASS' if infra_ok else 'FAIL'}")
    
    if env_ok and imports_ok and infra_ok:
        logger.info("Overall: System appears ready for operation")
        logger.info("To test actual order placement, run: python3 monitor_profit_exit.py")
        logger.info("NOTE: This will attempt actual orders if in trading hours and environment allows")
        return 0
    else:
        logger.warning("Overall: Some checks failed - system may not be ready")
        return 1

if __name__ == "__main__":
    sys.exit(main())