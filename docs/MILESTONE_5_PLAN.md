# Milestone 5 Implementation Plan

## M4 Acceptance Record (Preserved)

See `docs/MILESTONE_4_ACCEPTANCE.md` for the full M4 acceptance record.

**Key limitations to address in M5:**
- Checkpoint recovery NOT end-to-end tested
- Database uniqueness constraints NOT tested against real DB
- Retry-after-failure scenarios NOT tested
- Concurrent create attempts NOT tested

## M5 Scope

### Priority 1: End-to-End Checkpoint Recovery

**Goal:** Demonstrate that workflows can be interrupted, persisted, and resumed.

**Test Scenario:**
```python
async def test_checkpoint_recovery_after_interruption():
    # 1. Start workflow with real SQLite checkpoint
    # 2. Inject state to pause at 'review' node
    # 3. Save checkpoint
    # 4. Simulate interruption (close saver, clear state)
    # 5. Reopen checkpointer
    # 6. Resume from checkpoint
    # 7. Verify:
    #    - State restored correctly
    #    - Execution continues from 'review' (not re-runs validate/draft)
    #    - No duplicate side effects
```

**Implementation:**
- Use `langgraph-checkpoint-sqlite` with real SQLite file
- Create helper to interrupt workflow (custom exception or state check)
- Test recovery by reloading from same checkpoint file

### Priority 2: Database-Backed Idempotency

**Goal:** Verify idempotency against real database with uniqueness constraints.

**Implementation:**
1. Add UNIQUE constraint to `applications` table: `(job_id, profile_id)`
2. Add UNIQUE constraint to `documents`: `(application_id, document_type, version)`
3. Test concurrent creation attempts
4. Test retry after failure

**Test Scenario:**
```python
async def test_concurrent_create_attempts():
    # Simulate two parallel workflow invocations
    # Both should get same application_id (idempotent)
    # Second should not create duplicate
```

### Priority 3: Application Workflow Integration

**Goal:** Connect all components into coherent workflow.

**Flow:**
```
Job Discovery → Job Matching → Document Generation → Quality Review → 
Approval Validation → Application Ready
```

**Integration Tests:**
- End-to-end successful execution
- Failure handling at each stage
- Approval validation before submission

### Priority 4: Real Database Tests

**Goal:** Replace mock-based tests with real SQLite database.

**Changes:**
- Use `sqlite+aiosqlite:///:memory:` for tests
- Create tables before each test
- Test actual SQL operations
- Verify foreign key constraints

## Files to Modify/Create

| File | Action | Purpose |
|------|--------|---------|
| `backend/app/models/application.py` | Modify | Add UNIQUE constraints |
| `backend/app/repositories/application.py` | Modify | Add concurrency handling |
| `backend/tests/test_m5_integration.py` | Create | End-to-end integration tests |
| `backend/tests/test_checkpoint_recovery.py` | Create | Recovery tests |
| `backend/tests/test_idempotency.py` | Create | Idempotency tests |

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| SQLite concurrency limits | Single-threaded test execution |
| Checkpoint serialization issues | Use Pydantic v2 (already tested) |
| Test flakiness | Use isolated in-memory databases per test |
| Migration complexity | Keep backward compatible |

## Timeline Estimate

| Component | Effort |
|-----------|--------|
| Checkpoint recovery tests | 3 hours |
| Database constraints | 1 hour |
| Integration tests | 4 hours |
| Real DB tests | 2 hours |
| Documentation | 1 hour |
| **Total** | **~11 hours** |
