# Test results (model: gemini / gemini-3.1-flash-lite)

| Version | Runs | Overall pass | Fix verified | Declined invalid | Valid JSON | Avg latency (s) |
|---|---|---|---|---|---|---|
| v1 | 14 | 12/14 | 11/12 | 1/2 | n/a | 5.9 |
| v2 | 14 | 13/14 | 11/12 | 2/2 | 14/14 | 2.5 |
| v3 | 14 | 14/14 | 12/12 | 2/2 | 14/14 | 4.7 |
| v4 | 14 | 14/14 | 12/12 | 2/2 | 14/14 | 4.6 |

## Per-test results (Pass/Fail and reason)

 1 Normal  | v1: PASS | v2: PASS | v3: PASS | v4: PASS
 2 Normal  | v1: PASS | v2: PASS | v3: PASS | v4: PASS
 3 Normal  | v1: PASS | v2: PASS | v3: PASS | v4: PASS
 4 Normal  | v1: PASS | v2: PASS | v3: PASS | v4: PASS
 5 Normal  | v1: PASS | v2: PASS | v3: PASS | v4: PASS
 6 Normal  | v1: PASS | v2: PASS | v3: PASS | v4: PASS
 7 Normal  | v1: PASS | v2: PASS | v3: PASS | v4: PASS
 8 Normal  | v1: PASS | v2: PASS | v3: PASS | v4: PASS
 9 Edge    | v1: PASS | v2: PASS | v3: PASS | v4: PASS
10 Edge    | v1: PASS | v2: PASS | v3: PASS | v4: PASS
11 Edge    | v1: FAIL | v2: FAIL | v3: PASS | v4: PASS
12 Edge    | v1: PASS | v2: PASS | v3: PASS | v4: PASS
13 Invalid | v1: FAIL | v2: PASS | v3: PASS | v4: PASS
14 Invalid | v1: PASS | v2: PASS | v3: PASS | v4: PASS

Good before/after candidates for the reel (v1 failed, v4 passed): test 11, test 13