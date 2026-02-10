import sys
from brain_ops import should_trigger_rag

def test_rag_logic():
    test_cases = [
        # --- LEGACY KWs (Case Insensitive, Word Boundary) ---
        ("tell me about python", True, "Legacy: python"),
        ("search for jedi", True, "Legacy: search"),
        ("how to code", True, "Legacy: code"),
        ("encoding something", False, "Legacy Boundary: 'code' inside 'encoding'"), 
        ("rag time", True, "Legacy: rag"),
        
        # --- FRAMEWORKS (Strict > 3 UPPER) ---
        ("compliance with NIST", True, "Strict: NIST"),
        ("nist compliance", False, "Strict Fail: nist (lowercase)"),
        ("MITRE ATT&CK framework", True, "Strict: MITRE ATT&CK"),
        
        # --- PROTOCOLS (Strict > 3 UPPER) ---
        ("check TCP connection", True, "Strict: TCP"),
        ("tcp connection", False, "Strict Fail: tcp (lowercase)"),
        ("SQLi attack", True, "Strict: SQLi (S, Q, L = 3 caps)"), 
        # Wait, SQLi has S,Q,L (3 caps). So strict. "sqli" should fail.
        ("prevent sqli", False, "Strict Fail: sqli (lowercase)"),
        
        # --- AI/RAG (Mixed) ---
        ("using BM25 algo", True, "Loose: BM25 (2 caps)"),
        ("bm25 algo", True, "Loose: bm25 (lowercased match)"),
        ("GraphRAG implementation", True, "Strict: GraphRAG (G,R,A,G = 4 caps)"),
        ("graphrag implementation", False, "Strict Fail: graphrag"),
        
        # --- EXAMS ---
        ("study for SY0-701", True, "Strict: SY0-701"),
        ("sy0-701 study", True, "Loose: SY0-701 (<3 caps, so case-insensitive per rule)"),
        ("CompTIA exam", True, "Strict: CompTIA (4 caps)"),
        ("comptia exam", False, "Strict Fail: comptia"),
        
        # --- NEGATIVE CONTROLS ---
        ("hello world", False, "Control: hello world"),
        ("just a chat", False, "Control: chat"),
        ("aptitude test", False, "Boundary: apt vs aptitude (if apt was a keyword)"),
    ]

    print(f"{'STATUS':<8} | {'INPUT':<30} | {'EXPECTED':<8} | {'ACTUAL':<8} | {'NOTE'}")
    print("-" * 100)
    
    all_pass = True
    for text, expected, note in test_cases:
        result = should_trigger_rag(text)
        status = "PASS" if result == expected else "FAIL"
        if result != expected:
            all_pass = False
        
        # Truncate input for display
        disp_text = (text[:27] + '...') if len(text) > 27 else text
        print(f"{status:<8} | {disp_text:<30} | {str(expected):<8} | {str(result):<8} | {note}")

    print("-" * 100)
    if all_pass:
        print("\nSUCCESS: All RAG trigger rules verified.")
    else:
        print("\nFAILURE: Some rules failed.")
        sys.exit(1)

if __name__ == "__main__":
    test_rag_logic()
