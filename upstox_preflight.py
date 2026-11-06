import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

MODE = os.getenv("UPSTOX_MODE", "").strip().lower()
TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN", "").strip()


def main():
    print("ChronosMatch - Upstox Preflight Check")
    print("-" * 40)
    print("Network requests: DISABLED")
    print("Order placement: DISABLED")

    print("Project folder exists:", BASE_DIR.is_dir())
    print(".env file exists:", (BASE_DIR / ".env").is_file())

    print("Configured mode:", MODE if MODE else "Not configured")

    token_available = bool(
        TOKEN and TOKEN != "your_sandbox_token_here"
    )
    print("Token configured:", "Yes" if token_available else "No")

    if MODE != "sandbox":
        print("Status: Sandbox mode is not configured.")
    elif not token_available:
        print("Status: Waiting for a sandbox token.")
    else:
        print("Status: Local configuration found.")
        print("Note: Token validity has NOT been verified.")

    print()
    print("No API request was sent.")
    print("No order was placed.")


if __name__ == "__main__":
    main()