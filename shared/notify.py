# shared/notify.py
import subprocess
import logging

logger = logging.getLogger(__name__)

def send_telegram(message: str):
    """
    Send a message to Telegram using the Hermes CLI.
    Assumes `hermes` is in PATH and configured with a default telegram target.
    """
    try:
        # Using hermes send --to telegram "<message>"
        result = subprocess.run(
            ["hermes", "send", "--to", "telegram", message],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            logger.info(f"Telegram message sent: {message[:50]}...")
        else:
            logger.error(f"Failed to send telegram: {result.stderr}")
    except Exception as e:
        logger.exception(f"Exception while sending telegram: {e}")