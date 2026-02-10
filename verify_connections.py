import httpx
import sys
import os

# Ensure we can import from current directory
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

try:
    from brain_ops import should_trigger_rag
except ImportError as e:
    print(f"[ERROR] Could not import brain_ops: {e}")
    sys.exit(1)

def test_ollama_connection():
    print("\n[TEST] Testing Ollama Connection...")
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
        if r.status_code == 200:
            print("[PASS] Ollama is reachable.")
            return True
        else:
            print(f"[FAIL] Ollama returned status {r.status_code}")
            return False
    except Exception as e:
        print(f"[FAIL] Ollama connection failed: {e}")
        return False

def test_holocron_connection():
    print("\n[TEST] Testing Ancient_Holocron Connection...")
    try:
        # Simple health check or query
        r = httpx.post(
            "http://localhost:8000/query",
            json={"question": "ping"},
            timeout=30.0
        )
        if r.status_code == 200:
            print("[PASS] Ancient_Holocron is reachable.")
            return True
        else:
            print(f"[FAIL] Ancient_Holocron returned status {r.status_code}")
            return False
    except Exception as e:
        print(f"[FAIL] Ancient_Holocron connection failed: {e}")
        print("       (Is the Holocron API running? Try ./start_holocron.sh)")
        return False

def test_rag_keywords():
    print("\n[TEST] Testing RAG Trigger Logic...")
    
    test_cases = [
        ("What are my python notes?", True, "LEGACY: python"),
        ("Tell me about NIST SP 800-61", True, "FRAMEWORK: NIST SP 800-61"),
        ("I need to study for SY0-701", True, "EXAM: SY0-701"),
        ("Explain TCP/UDP", True, "PROTOCOL: TCP/UDP"),
        ("What is GraphRAG?", True, "AI_RAG: GraphRAG"),
        ("I took a course on Coursera", True, "SOURCE: Coursera"),
        ("nist is a standard", False, "Lowercase 'nist' should NOT trigger (needs 3+ upper to be case-sensitive match?)"), 
        # Wait, the rule is: "Treat tokens with 3+ uppercase letters as 'Case-Sensitive Exact Matches'"
        # So "NIST" (4 chars, all upper) -> Case Sensitive. "nist" in text != "NIST". Should be False.
        # But wait, checking the logic in brain_ops.py...
        # "NIST" is in FRAMEWORKS. upper_count=4 >= 3.
        # re.search(r'\bNIST\b', "nist is a standard") -> False.
        # Correct.
        
        ("I love nesting birds", False, "Partial match 'nest' should not trigger (if 'nest' was a keyword)"),
    ]
    
    all_pass = True
    for text, expected, reason in test_cases:
        result = should_trigger_rag(text)
        status = "PASS" if result == expected else "FAIL"
        if result != expected: all_pass = False
        print(f"[{status}] Text: '{text}' -> Got: {result}, Expected: {expected} ({reason})")
        
    return all_pass

if __name__ == "__main__":
    t1 = test_ollama_connection()
    t2 = test_rag_keywords()
    t3 = test_holocron_connection() # Will fail if not running yet
    
    print("\n[SUMMARY]")
    print(f"Ollama: {'PASS' if t1 else 'FAIL'}")
    print(f"RAG Logic: {'PASS' if t2 else 'FAIL'}")
    print(f"Holocron: {'PASS' if t3 else 'FAIL'}")
