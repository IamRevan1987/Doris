import sys
from unittest.mock import MagicMock, patch

# Mock libraries to avoid requiring them or the servers to be running
sys.modules["langchain_ollama"] = MagicMock()
sys.modules["langchain_core.messages"] = MagicMock()
sys.modules["tts.ghost_voice"] = MagicMock()
sys.modules["tts.tts_config"] = MagicMock()
sys.modules["core.core_drivers"] = MagicMock()
sys.modules["core.core_lock"] = MagicMock()
sys.modules["core.core_memories"] = MagicMock()

# Now import the target
from brain_ops import ChatEngine

def test_integration():
    print("Initializing ChatEngine with mocks...")
    
    # Mocking external calls within ChatEngine
    with patch("brain_ops.ChatOllama") as MockLLM, \
         patch("brain_ops.GhostVoiceEngine") as MockTTS, \
         patch("brain_ops.ask_the_holocron") as MockHolocron, \
         patch("brain_ops.load_turns", return_value=[]), \
         patch("brain_ops.append_turn"):
        
        # Setup mocks
        mock_llm_instance = MockLLM.return_value
        mock_llm_instance.invoke.return_value.content = "I am the LLM."
        
        MockHolocron.return_value = "I am the Holocron."
        
        engine = ChatEngine(user_name="Tester", tts_enabled=False)
        
        test_cases = [
            ("Explain NIST framework", True, "Strict Keyword 'NIST'"),
            ("Hello friend", False, "No Keyword"),
            ("Check loopback TCP", True, "Strict Keyword 'TCP'"),
            ("check loopback tcp", False, "Lowercase 'tcp' should verify strictness"),
            ("search my notes", True, "Legacy Keyword 'search'/'my notes'")
        ]
        
        print(f"\n{'INPUT':<30} | {'ROUTE':<10} | {'STATUS':<8}")
        print("-" * 60)
        
        all_pass = True
        for text, expect_rag, note in test_cases:
            # Reset mocks
            MockHolocron.reset_mock()
            mock_llm_instance.invoke.reset_mock()
            
            response = engine.send(text)
            
            rag_called = MockHolocron.called
            llm_called = mock_llm_instance.invoke.called
            
            # Logic check
            if expect_rag:
                success = rag_called and not llm_called
                route = "RAG" if rag_called else "LLM"
            else:
                success = llm_called and not rag_called
                route = "LLM" if llm_called else "RAG" # or None
                
            status = "PASS" if success else "FAIL"
            if not success:
                all_pass = False
                
            print(f"{text:<30} | {route:<10} | {status:<8} ({note})")
            
        print("-" * 60)
        if all_pass:
            print("\nSUCCESS: Integrated routing logic verified.")
        else:
            print("\nFAILURE: Integration tests failed.")
            sys.exit(1)

if __name__ == "__main__":
    test_integration()
