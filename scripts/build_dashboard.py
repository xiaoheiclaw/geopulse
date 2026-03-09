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
    
    # Read template (terminal or classic)
    mode = sys.argv[2] if len(sys.argv) > 2 else "console"
    tpl_name = {"console": "console_template.html", "terminal": "terminal_template.html", "classic": "dashboard_template.html"}.get(mode, "console_template.html")
    template_path = Path(__file__).parent / tpl_name
    with open(template_path) as f:
        html = f.read()
    
    # Load signal status
    signal_path = data / "signal_status.json"
    if signal_path.exists():
        with open(signal_path) as f:
            signals_json = f.read()
    else:
        signals_json = '{"version":0}'
    
    # Inject data
    html = html.replace("__DAG_DATA__", dag_json)
    html = html.replace("__RUN_OUTPUT__", run_json)
    html = html.replace("__SIGNALS_DATA__", signals_json)
    
    # Write output
    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        f.write(html)
    
    print(f"Dashboard written to {out_path} ({out_path.stat().st_size} bytes)")


if __name__ == "__main__":
    build()
