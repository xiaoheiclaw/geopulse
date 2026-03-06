#!/usr/bin/env python3
"""Build v7.4 dashboard HTML by embedding RunOutput + DAG data."""
import json
import sys
from pathlib import Path

def build(data_dir: str = "data", output: str = "docs/index.html"):
    data = Path(data_dir)
    
    # Load DAG
    from geopulse.storage import DAGStorage
    dag = DAGStorage(data_dir=data).load()
    dag_json = dag.model_dump_json()
    
    # Load latest RunOutput
    from geopulse.run_storage import RunOutputStorage
    store = RunOutputStorage(data_dir=data)
    latest = store.latest()
    if not latest:
        print("No RunOutput found")
        sys.exit(1)
    run_json = latest.model_dump_json()
    
    # Read template
    template_path = Path(__file__).parent / "dashboard_template.html"
    with open(template_path) as f:
        html = f.read()
    
    # Inject data
    html = html.replace("__DAG_DATA__", dag_json)
    html = html.replace("__RUN_OUTPUT__", run_json)
    
    # Write output
    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        f.write(html)
    
    print(f"Dashboard written to {out_path} ({out_path.stat().st_size} bytes)")


if __name__ == "__main__":
    build()
