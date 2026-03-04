import os
import shutil

for root, dirs, files in os.walk("."):
    for d in dirs:
        if d == "__pycache__":
            shutil.rmtree(os.path.join(root, d))
            print(f"Removed: {os.path.join(root, d)}")

    for f in files:
        if f.endswith(".pyc"):
            os.remove(os.path.join(root, f))
            print(f"Deleted: {os.path.join(root, f)}")

print("Cleanup complete.")