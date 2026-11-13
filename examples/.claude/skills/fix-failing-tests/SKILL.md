---
name: fix-failing-tests
description: Use when tests fail. A step-by-step routine for finding and fixing the cause.
---

# Fixing failing tests

1. Run the full test suite once and note every failing test.
2. Read the first failing test and the code it calls before changing anything.
3. Decide whether the test or the code is wrong. Never weaken a test just to make it pass.
4. Make the smallest fix, then run that one test again.
5. Run the whole suite again to check nothing else broke.
