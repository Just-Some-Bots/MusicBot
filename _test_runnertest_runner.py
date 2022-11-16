import unittest
import _test_runnertest_suite
import os
import json
from time import sleep

suite = unittest.TestLoader().loadTestsFromTestCase(
  _test_runnertest_suite.UnitTests)
f = open(os.devnull,"w")
test_res = unittest.TextTestRunner(stream=f).run(suite)

# Merge errors and failures and normalize to {name, stack}
failures = [
    {
        "name": r[0]._testMethodName,
        "stack": r[1],
    } for r in test_res.errors + test_res.failures
]
print()
print('__UNIT_TEST_RESULT_START__')
sleep(1)
print(json.dumps({
    "passed": test_res.wasSuccessful(),
    "failures": failures,
}))
print()
print('__UNIT_TEST_RESULT_END__');