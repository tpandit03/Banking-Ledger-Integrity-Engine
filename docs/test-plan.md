# Test plan

Automated tests cover:
- Health endpoint
- Rejecting unbalanced journals
- Posting a balanced journal
- Integrity verification
- Idempotent retry of the same request
- Rejecting reuse of an idempotency key with a different payload
- Unknown-account rejection without partial posting
- Account balance calculation
- Cross-currency journal rejection

Recommended additions:
- Concurrent idempotency requests
- Negative and excessive decimal precision
- Very large journal payloads
- Database lock/retry behavior
- Reversal/compensating journal workflows
- Authorization and audit retention tests
- Property-based tests for accounting invariants
