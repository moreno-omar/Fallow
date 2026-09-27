## Meta
- purpose: to test to preserve functionality and make more reliable


### Verify persistence:
    - [ ] Sidebar width survives restart
    - [ ] Active tab survives restart
    - [ ] Bookmarks survive file rename (hash identity)
    - [ ] Notes survive file move to new directory
    - [ ] Deleting the DB rebuilds empty, doesn't crash
    - [ ] Two PDFs of same content hash share notes (intended?)


### Database
- Never re-run schema.sql on an existing DB

PRAGMA user_version = 1

This runs on every connect if you put it in the schema file — which is fine for a fresh DB, but do not run the whole schema file on every startup. Split it: