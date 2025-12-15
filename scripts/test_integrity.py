import sys
import os

# Add root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("Checking imports...")
try:
    from modules.core.search_engine import SearchEngine
    print("✅ Module 'modules.core.search_engine' imported successfully.")
except Exception as e:
    print(f"❌ Error importing SearchEngine: {e}")
    sys.exit(1)

print("Checking initialization...")
try:
    engine = SearchEngine()
    print("✅ SearchEngine initialized successfully.")
except Exception as e:
    print(f"❌ Error initializing SearchEngine: {e}")
    sys.exit(1)

print("Checking database connection...")
try:
    from modules.database.database import get_session
    session = get_session()
    session.close()
    print("✅ Database connection successful.")
except Exception as e:
    print(f"❌ Database error: {e}")
    sys.exit(1)

print("System Integrity Check Passed.")