"""Migration: add trust columns to contacts table."""
import sqlalchemy as sa
import sys
sys.path.insert(0, '.')

from app.database.session import engine

with engine.connect() as conn:
    inspector = sa.inspect(engine)
    cols = [c['name'] for c in inspector.get_columns('contacts')]
    print('Existing columns:', cols)
    
    if 'trust_level' not in cols:
        conn.execute(sa.text("ALTER TABLE contacts ADD COLUMN trust_level VARCHAR(20) NOT NULL DEFAULT 'high'"))
        print('Added trust_level')
    else:
        print('trust_level already exists')

    if 'trust_flagged_by_call_id' not in cols:
        conn.execute(sa.text('ALTER TABLE contacts ADD COLUMN trust_flagged_by_call_id VARCHAR(36)'))
        print('Added trust_flagged_by_call_id')
    else:
        print('trust_flagged_by_call_id already exists')

    if 'trust_flagged_at' not in cols:
        conn.execute(sa.text('ALTER TABLE contacts ADD COLUMN trust_flagged_at DATETIME'))
        print('Added trust_flagged_at')
    else:
        print('trust_flagged_at already exists')

    conn.commit()
    print('Migration complete!')
