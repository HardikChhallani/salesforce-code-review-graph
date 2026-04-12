import subprocess
import json
import os

def parse_apex_file(file_path):
    script_path = os.path.join(
        os.path.dirname(__file__),
        "../apex_parser/parse_apex.js"
    )

    result = subprocess.run(
        ["node", script_path, file_path],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise Exception(f"Apex parser error: {result.stderr}")

    return json.loads(result.stdout)