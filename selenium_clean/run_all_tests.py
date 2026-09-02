import subprocess
import sys

tests = [
    "test_login.py",
    "test_invalid_login.py",
    "test_admin_dashboard.py",
    "test_setup_exam.py",
    "test_upload_roster.py",
    "test_invigilator_login.py",
    "test_controlroom_login.py",
]

print("\n" + "=" * 60)
print("       InviSense Selenium Test Suite")
print("=" * 60)

failed = []

for test in tests:
    print(f"\n{'-' * 60}")
    print(f"Running: {test}")
    print(f"{'-' * 60}")

    result = subprocess.run(
        [sys.executable, test]
    )

    if result.returncode == 0:
        print(f"✅ {test} PASSED")
    else:
        print(f"❌ {test} FAILED")
        failed.append(test)

print("\n" + "=" * 60)
print("                  TEST SUMMARY")
print("=" * 60)

total = len(tests)
passed = total - len(failed)

print(f"Total tests : {total}")
print(f"Passed      : {passed}")
print(f"Failed      : {len(failed)}")

if failed:
    print("\nFailed tests:")
    for test in failed:
        print(f"  ❌ {test}")

    print("\n❌ SOME SELENIUM TESTS FAILED")
    sys.exit(1)

else:
    print("\n🎉 ALL SELENIUM TESTS PASSED!")
    print("✅ InviSense Selenium testing completed successfully.")
    sys.exit(0)