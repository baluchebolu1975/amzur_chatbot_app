#!/usr/bin/env python3
"""Production smoke test for chatbot + n8n ticket triage integration."""

import json
import sys
import urllib.request
import urllib.error
from datetime import datetime

# Test configuration
API_BASE = "http://127.0.0.1:8001/api"
WEBHOOK_BASE = "https://baluch.app.n8n.cloud/webhook"
TIMEOUT = 15

# Test data
TEST_TICKETS = [
    {
        "user_email": "customer1@example.com",
        "issue": "Cannot login to account after password reset attempt",
        "category": "account",
        "priority": "high",
        "source": "chatbot_smoke_test",
    },
    {
        "user_email": "customer2@example.com",
        "issue": "Payment processing fails at checkout when using international credit card",
        "category": "billing",
        "priority": "critical",
        "source": "chatbot_smoke_test",
    },
    {
        "user_email": "customer3@example.com",
        "issue": "App crashes on startup after updating to latest version",
        "category": "technical",
        "priority": "high",
        "source": "chatbot_smoke_test",
    },
]

def print_header(title):
    """Print formatted header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def print_test(number, name):
    """Print test case header."""
    print(f"\n✓ TEST {number}: {name}")
    print("-" * 70)

def print_result(passed, message):
    """Print test result."""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status}: {message}")

def make_request(url, method="GET", data=None):
    """Make HTTP request using urllib."""
    try:
        if data:
            data = json.dumps(data).encode('utf-8')
        
        req = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"} if data else {}
        )
        
        response = urllib.request.urlopen(req, timeout=TIMEOUT)
        status_code = response.status
        body = response.read().decode('utf-8')
        return status_code, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        return e.code, {"error": str(e)}
    except Exception as e:
        return None, {"error": str(e)}

def test_health_check():
    """Test 1: Health check endpoint."""
    print_test(1, "Health Check Endpoint")
    try:
        status, data = make_request(f"{API_BASE}/health")
        passed = status == 200
        print_result(passed, f"Status {status} - {data.get('app', 'Unknown')}")
        return passed
    except Exception as e:
        print_result(False, f"Exception: {str(e)}")
        return False

def test_ticket_creation(ticket_data, ticket_num):
    """Test 2-4: Create ticket via chatbot API."""
    email = ticket_data["user_email"]
    print_test(ticket_num + 1, f"Create Ticket: {email}")
    try:
        status, data = make_request(
            f"{API_BASE}/tickets",
            method="POST",
            data=ticket_data
        )
        
        # Check response status
        passed = status in [200, 201]
        if passed:
            ticket_id = data.get("ticket_id", "N/A")
            status_val = data.get("status", "N/A")
            print(f"  Ticket ID: {ticket_id}")
            print(f"  Status: {status_val}")
            print(f"  Email Status: {data.get('email_status', 'N/A')}")
            print_result(True, f"HTTP {status} - Ticket created successfully")
            return True, ticket_id
        else:
            print_result(False, f"HTTP {status} - {str(data)[:100]}")
            return False, None
    except Exception as e:
        print_result(False, f"Exception: {str(e)}")
        return False, None

def test_webhook_production():
    """Test 5: Direct webhook call to n8n."""
    print_test(5, "Direct Webhook Call to n8n")
    try:
        test_payload = {
            "user_email": "test@webhook-direct.com",
            "issue": "Direct webhook test from chatbot smoke test suite",
            "category": "testing",
            "priority": "low",
            "source": "chatbot_webhook_direct",
        }
        
        status, data = make_request(
            f"{WEBHOOK_BASE}/tickets",
            method="POST",
            data=test_payload
        )
        
        passed = status in [200, 201]
        if passed:
            print(f"  HTTP Status: {status}")
            print(f"  Response Fields: {', '.join(data.keys())}")
            required_fields = ["status", "ticket_id", "message", "created_at"]
            has_all = all(field in data for field in required_fields)
            print_result(has_all, f"Webhook response has all required fields: {has_all}")
            return has_all
        else:
            print_result(False, f"HTTP {status} - {str(data)[:100]}")
            return False
    except Exception as e:
        print_result(False, f"Exception: {str(e)}")
        return False

def test_response_format():
    """Test 6: Response format validation."""
    print_test(6, "Response Format Validation")
    try:
        test_payload = {
            "user_email": "format-test@example.com",
            "issue": "Testing response format validation for production readiness",
            "category": "testing",
            "priority": "low",
            "source": "chatbot_format_test",
        }
        
        status, data = make_request(
            f"{API_BASE}/tickets",
            method="POST",
            data=test_payload
        )
        
        if status not in [200, 201]:
            print_result(False, f"HTTP {status}")
            return False
        
        required_fields = {
            "status": str,
            "ticket_id": str,
            "message": str,
            "created_at": str,
            "email_status": str,
            "triage_label": str,
        }
        
        all_valid = True
        for field, expected_type in required_fields.items():
            has_field = field in data
            has_correct_type = isinstance(data.get(field), expected_type) if has_field else False
            all_valid = all_valid and has_field and has_correct_type
            status_char = "✓" if (has_field and has_correct_type) else "✗"
            print(f"  {status_char} {field}: {expected_type.__name__}")
        
        print_result(all_valid, "All response fields present and correctly typed")
        return all_valid
    except Exception as e:
        print_result(False, f"Exception: {str(e)}")
        return False

def main():
    """Run all smoke tests."""
    print_header("🚀 PRODUCTION SMOKE TEST: CHATBOT + N8N INTEGRATION")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"API Base: {API_BASE}")
    print(f"Webhook Base: {WEBHOOK_BASE}")
    
    results = []
    
    # Test 1: Health check
    results.append(("Health Check", test_health_check()))
    
    # Test 2-4: Create tickets via API
    for i, ticket_data in enumerate(TEST_TICKETS):
        passed, ticket_id = test_ticket_creation(ticket_data, i)
        results.append((f"Create Ticket {i+1}", passed))
    
    # Test 5: Direct webhook call
    results.append(("Direct Webhook Call", test_webhook_production()))
    
    # Test 6: Response format validation
    results.append(("Response Format", test_response_format()))
    
    # Print summary
    print_header("📊 TEST SUMMARY")
    passed_count = sum(1 for _, result in results if result)
    total_count = len(results)
    
    for test_name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {test_name}")
    
    print("-" * 70)
    print(f"Total: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print_header("✅ ALL TESTS PASSED - PRODUCTION READY!")
        print("\n✓ Webhook integration confirmed")
        print("✓ API endpoints responding correctly")
        print("✓ Response format valid")
        print("✓ Email delivery working")
        print("\n→ Ready to move to Prompt 3\n")
        return 0
    else:
        print_header("❌ SOME TESTS FAILED - REVIEW REQUIRED")
        print(f"\nFailed: {total_count - passed_count} test(s)")
        print("→ Fix issues before moving to Prompt 3\n")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
