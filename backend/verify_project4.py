#!/usr/bin/env python
"""
Project 4 Test Verification Script

Runs all tests and generates report showing:
1. Unit test results (memory window service)
2. Integration test results (chat pipeline)
3. Test coverage
4. Output examples

Run: python verify_project4.py
"""

import subprocess
import sys
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent


def run_tests():
    """Execute pytest and capture results."""
    print("=" * 70)
    print("PROJECT 4: MEMORY WINDOW - TEST VERIFICATION")
    print("=" * 70)
    print()
    
    # Test 1: Unit tests for MemoryWindowService
    print("📋 UNIT TESTS: Memory Window Service")
    print("-" * 70)
    
    unit_test_cmd = [
        sys.executable, "-m", "pytest",
        "app/ai/memory/test_memory_window.py",
        "-v", "--tb=short", "--color=yes"
    ]
    
    try:
        result = subprocess.run(unit_test_cmd, cwd=PROJECT_ROOT, capture_output=False)
        unit_tests_passed = result.returncode == 0
    except Exception as e:
        print(f"❌ Error running unit tests: {e}")
        unit_tests_passed = False
    
    print()
    
    # Test 2: Integration tests for chat pipeline
    print("📋 INTEGRATION TESTS: Chat Pipeline with Memory")
    print("-" * 70)
    
    integration_test_cmd = [
        sys.executable, "-m", "pytest",
        "app/services/test_project4_integration.py",
        "-v", "--tb=short", "--color=yes"
    ]
    
    try:
        result = subprocess.run(integration_test_cmd, cwd=PROJECT_ROOT, capture_output=False)
        integration_tests_passed = result.returncode == 0
    except Exception as e:
        print(f"❌ Error running integration tests: {e}")
        integration_tests_passed = False
    
    print()
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"✅ Unit Tests:        {'PASSED' if unit_tests_passed else 'FAILED'}")
    print(f"✅ Integration Tests: {'PASSED' if integration_tests_passed else 'FAILED'}")
    print()
    
    if unit_tests_passed and integration_tests_passed:
        print("🎉 ALL TESTS PASSED - PROJECT 4 READY FOR DEPLOYMENT")
        return True
    else:
        print("❌ SOME TESTS FAILED - REVIEW OUTPUT ABOVE")
        return False


def verify_code_exists():
    """Verify that all Project 4 code files exist."""
    print("🔍 CODE VERIFICATION")
    print("-" * 70)
    
    files_to_check = [
        "backend/app/ai/memory/__init__.py",
        "backend/app/ai/memory/memory_window_service.py",
        "backend/app/ai/memory/test_memory_window.py",
        "backend/app/services/chat_service.py",
        "backend/app/services/test_project4_integration.py",
    ]
    
    base_path = Path("c:/Users/Baluch/Documents/amzur-chatbot")
    all_exist = True
    
    for file_path in files_to_check:
        full_path = base_path / file_path
        exists = full_path.exists()
        status = "✅" if exists else "❌"
        print(f"{status} {file_path}")
        if not exists:
            all_exist = False
    
    print()
    return all_exist


def show_code_example():
    """Display example of memory window in action."""
    print("📝 EXAMPLE: Memory Window in Action")
    print("-" * 70)
    
    example = """
SCENARIO: User sends 3 messages to bot

Message 1:
  User: "What is machine learning?"
  Bot: "Machine learning is a subset of AI..."
  [Memory: 0 prior conversations - no context injected]

Message 2:
  User: "Can you give me an example?"
  Bot: [Receives injected context from Message 1]
       "Based on what I explained, here's an example..."
  [Memory: 1 prior conversation - context includes Message 1]

Message 3:
  User: "How does it relate to deep learning?"
  Bot: [Receives injected context from Messages 1-2]
       "Drawing from our earlier discussion..."
  [Memory: 2 prior conversations - full context includes Messages 1-2]

INTERNALLY - What Gets Injected:
─────────────────────────────────
CONVERSATION MEMORY:

(Last 2 exchange(s) in this thread)

Exchange 1:
User: What is machine learning?
Assistant: Machine learning is a subset of AI that focuses on...

Exchange 2:
User: Can you give me an example?
Assistant: Sure! Here's an example: A spam filter learns...

=== END CONTEXT ===

Now continue the conversation naturally based on the history above.
─────────────────────────────────

AFTER 5+ CONVERSATIONS:
- Bot remembers exactly last 5 exchanges
- Context window slides forward
- Messages 1-5 remembered, message 6 causes message 1 to be forgotten
- Prevents token budget explosion
- Ensures fresh context stays relevant
"""
    
    print(example)
    print()


def main():
    """Main verification flow."""
    print()
    
    # Step 1: Verify code exists
    code_exists = verify_code_exists()
    print()
    
    if not code_exists:
        print("❌ Some code files are missing. Check paths above.")
        return False
    
    # Step 2: Show example
    show_code_example()
    
    # Step 3: Run tests
    tests_passed = run_tests()
    
    print()
    print("=" * 70)
    print("DEPLOYMENT STATUS")
    print("=" * 70)
    
    if code_exists and tests_passed:
        print("✅ PROJECT 4 IS READY FOR DEPLOYMENT")
        print()
        print("NEXT STEPS:")
        print("1. Backend server: uvicorn app.main:app --reload --host 127.0.0.1 --port 8000")
        print("2. Frontend: npm run dev")
        print("3. Test chat: Send multiple messages and verify bot remembers context")
        print()
        return True
    else:
        print("❌ PROJECT 4 HAS ISSUES - FIX BEFORE DEPLOYMENT")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
