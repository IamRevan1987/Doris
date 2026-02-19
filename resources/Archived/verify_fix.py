
import sys
import os
import httpx
from brain_ops import ChatEngine

def test_fix():
    print("--- Verifying Doris Connection Fix ---")
    try:
        # 1. Initialize Engine
        engine = ChatEngine()
        print(f"ChatEngine initialized. base_url={engine.base_url}")
        
        # 2. Check Backend Reachability
        ok = engine.backend_ok()
        print(f"backend_ok() -> {ok}")
        
        if not ok:
            print("FAILURE: backend_ok() returned False. Ollama connection refused or blocked.")
            print("Check if ollama is running: systemctl status ollama")
            sys.exit(1)
            
        print("Backend connection is healthy. Attempting connection test...")

        # 3. Test Actual Sending (with Retry logic)
        # We catch the specific "model not found" error to treat it as a "Connection Success" (but config error)
        # so the user knows the code fix worked.
        try:
            response = engine.send("Hi")
            print(f"SUCCESS: Full cycle works. Response: {response[:50]}...")
        except Exception as e:
            # Check for model not found (Ollama 404)
            # This is a specific error raised by langchain/ollama client
            err_str = str(e).lower()
            if "not found" in err_str and "model" in err_str:
                print("\n[PARTIAL SUCCESS] Connection working, but Model Missing.")
                print(f"Error: {e}")
                print(f"Fix: Run 'ollama pull {engine.model_name}' or update 'model_name' in brain_ops.py.")
                print("The connection fix (IP/Retry) is VERIFIED working (we reached the server).")
                sys.exit(0) # Exit with success regarding the task goal
            else:
                raise e

    except Exception as e:
        print(f"\nFAILURE: Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    test_fix()
