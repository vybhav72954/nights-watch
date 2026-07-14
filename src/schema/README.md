# src/schema — the report contract (shared, FREEZE FIRST)

The one interface between Detect and Link/Prove. Implement `report.py` as a `pydantic`
`Report` model matching `docs/REPORT_SCHEMA.md`, plus normalisation helpers (UPI/phone/IFSC)
and validation. All three workstreams import this — do not fork it.

Owner: shared. Blocking dependency for everyone.
