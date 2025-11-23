import os
import glob

def print_tree(startpath, depth=2):
    print(f"\n# --- Tree for {os.path.basename(os.path.abspath(startpath))} --- #\n")
    for root, dirs, files in os.walk(startpath):
        level = root.replace(startpath, '').count(os.sep)
        if level > depth: continue
        
        indent = ' ' * 4 * level
        print(f"{indent}{os.path.basename(root)}/")
        
        subindent = ' ' * 4 * (level + 1)
        for f in files:
            if f.endswith('.pyc') or f.startswith('.'): continue
            print(f"{subindent}{f}")
            
        # Remove hidden/venv dirs to keep it clean
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('venv', 'node_modules', '__pycache__')]

def print_latest_progress():
    progress_file = "docs/curr_progress.md"
    print(f"\n\n### [Current Progress] (Latest Entry) ###\n")
    
    if not os.path.exists(progress_file):
        print("No progress file found.")
        return

    with open(progress_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Find the index of the last line starting with "## "
    last_header_index = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("## "):
            last_header_index = i
    
    # Print from the last header to the end
    if last_header_index != -1:
        print("".join(lines[last_header_index:]))
    else:
        # if no header is found, print whole file
        print("".join(lines))


def print_schema_status():
    print(f"\n\n### [Schema Status] ###\n")
    schema_dir = "api/app/schemas"
    if not os.path.exists(schema_dir):
        print("No schema directory found.")
        return

    print(f"Listing of '{os.path.abspath(schema_dir)}':\n")
    files = glob.glob(os.path.join(schema_dir, "*.py"))
    for file_path in sorted(files):
        filename = os.path.basename(file_path)
        if filename == "__init__.py": continue
        
        print(f"--- File: {filename} ---")
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # Print first 15 lines as summary
            print("".join(lines[:15]))
            print("...\n")

if __name__ == "__main__":
    # 1. Project Tree
    print("### [Project Tree] ###")
    target_dirs = ["api/app", "frontend/src", "dashboard", "docs", "scripts"]
    for d in target_dirs:
        if os.path.exists(d):
            print_tree(d, depth=1)
    
    # 2. Latest Progress
    print_latest_progress()
    
    # 3. Schema Status
    print_schema_status()
