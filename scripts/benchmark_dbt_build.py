import json
import platform
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


command = [
    "dbt",
    "build",
    "--project-dir",
    "dbt",
    "--profiles-dir",
    "dbt",
]

print("benchmark=local_dbt_build")
print("command=" + " ".join(command))

started = time.perf_counter()
result = subprocess.run(command)
elapsed = time.perf_counter() - started

if result.returncode != 0:
    print("benchmark=FAILED")
    sys.exit(result.returncode)

run_results_path = Path("dbt/target/run_results.json")
manifest_path = Path("dbt/target/manifest.json")

run_results = json.loads(run_results_path.read_text())
manifest = json.loads(manifest_path.read_text())

status_counts = Counter()
resource_counts = Counter()

for item in run_results.get("results", []):
    status_counts[item.get("status", "unknown")] += 1

    unique_id = item.get("unique_id")

    node = (
        manifest.get("nodes", {}).get(unique_id)
        or manifest.get("sources", {}).get(unique_id)
        or {}
    )

    resource_counts[
        node.get("resource_type", "unknown")
    ] += 1

record = {
    "benchmark": "local_dbt_build",
    "timestamp_utc": datetime.now(
        timezone.utc
    ).isoformat(),
    "elapsed_seconds": round(elapsed, 3),
    "python_version": platform.python_version(),
    "platform": platform.platform(),
    "result_count": len(
        run_results.get("results", [])
    ),
    "status_counts": dict(status_counts),
    "resource_type_counts": dict(resource_counts),
    "environment_note": (
        "Local WSL2 development benchmark; "
        "not a production or distributed benchmark."
    ),
}

output = Path(
    "docs/benchmarks/dbt_build_local.json"
)
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(
    json.dumps(record, indent=2) + "\n"
)

print()
print(json.dumps(record, indent=2))
print()
print(f"saved={output}")
print("benchmark=PASS")
