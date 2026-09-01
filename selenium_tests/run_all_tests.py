import subprocess
import sys

tests = [
    "test_login.py",
    "test_invalid_login.py",
    "test_admin_dashboard.py",
    "test_setup_exam.py",
    "test_upload_roster.py"
]

print("=" * 50)
print("       INVISENSE SELENIUM TEST SUITE")
print("=" * 50)

passed = 0
failed = 0

for test in tests:
    print(f"\nRunning: {test}")
    print("-" * 50)

    result = subprocess.run(
        [sys.executable, test]
    )

    if result.returncode == 0:
        print(f"✅ {test} PASSED")
        passed += 1
    else:
        print(f"❌ {test} FAILED")
        failed += 1

print("\n" + "=" * 50)
print("             TEST SUMMARY")
print("=" * 50)

print(f"Total tests : {len(tests)}")
print(f"Passed      : {passed}")
print(f"Failed      : {failed}")

if failed == 0:
    print("\n🎉 ALL SELENIUM TESTS PASSED!")
else:
    print("\n⚠️ SOME TESTS FAILED")