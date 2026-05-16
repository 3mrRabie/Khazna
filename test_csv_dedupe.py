import os
from app_logic import VaultManager

db_path = "test_vault.db"
if os.path.exists(db_path):
    os.remove(db_path)

vault = VaultManager(db_path)
vault.setup_vault("password123")
vault.unlock("password123")

# Create a dummy CSV
csv_content = """name,url,username,password
GitHub,https://github.com/,alice,pass1
GitHub,https://github.com,alice,pass1
GitHub,https://github.com,alice,pass2
"""

with open("test.csv", "w", encoding="utf-8") as f:
    f.write(csv_content)

success, skipped, errors = vault.import_csv("test.csv")
print(f"First import: success={success}, skipped={skipped}, errors={errors}")

# The first row (pass1) should be imported.
# The second row (pass1, no slash) should be skipped as duplicate.
# The third row (pass2) should be imported because it's a new password.

# Try importing again
success, skipped, errors = vault.import_csv("test.csv")
print(f"Second import: success={success}, skipped={skipped}, errors={errors}")

entries = vault.get_all_entries()
for e in entries:
    print(f"Stored: {e.url} | {e.username} | {e.password}")

if os.path.exists(db_path):
    os.remove(db_path)
if os.path.exists("test.csv"):
    os.remove("test.csv")
