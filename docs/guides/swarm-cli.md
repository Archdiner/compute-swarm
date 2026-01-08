# swarm-cli Documentation

ComputeSwarm's command-line interface for submitting jobs, monitoring status, and managing compute tasks.

## Installation

The CLI is part of the ComputeSwarm package. Ensure you have the dependencies installed:

```bash
pip install httpx rich
```

## Configuration

Set your wallet credentials in `.env`:

```bash
BUYER_PRIVATE_KEY=0x...
BUYER_ADDRESS=0x...
MARKETPLACE_URL=http://localhost:8000
```

## Commands

### Submit a Job

```bash
# Submit with a model name (auto-generates inference script)
swarm submit --model meta-llama/Llama-2-7b-hf

# Submit from a script file
swarm submit --script train.py

# Submit and wait for completion
swarm submit --script train.py --wait

# Submit with custom params
swarm submit --script train.py --max-price 5.0 --timeout 7200
```

**Options:**
- `--model, -m`: Model name (auto-generates HuggingFace inference script)
- `--script, -s`: Path to Python script
- `--template, -t`: Use a predefined template
- `--data, -d`: Path to input data file
- `--wait, -w`: Wait for job completion
- `--max-price`: Maximum $/hour (default: 10.0)
- `--timeout`: Timeout in seconds (default: 3600)

### Check Job Status

```bash
swarm status <job_id>
```

### Download Results

```bash
swarm download <job_id>
swarm download <job_id> --output ./results
```

### List Available Nodes

```bash
swarm nodes
```

### Check Wallet Balance

```bash
swarm balance
```

## JSON Output (For Agents/Scripts)

Add `--json` to any command for machine-readable output:

```bash
# Get job ID for scripting
job_id=$(swarm --json submit --script train.py | jq -r '.job_id')

# Check status programmatically
swarm --json status $job_id | jq '.status'

# List nodes as JSON
swarm --json nodes
```

## Examples

### Basic Workflow

```bash
# 1. Check available compute
swarm nodes

# 2. Submit a job
swarm submit --script my_training.py --wait

# 3. Check your spending
swarm balance
```

### AI Agent Integration

```python
import subprocess
import json

# Submit job
result = subprocess.run(
    ["python", "src/cli/swarm_cli.py", "--json", "submit", "--script", "train.py"],
    capture_output=True, text=True
)
job = json.loads(result.stdout)
job_id = job["job_id"]

# Poll for completion
while True:
    result = subprocess.run(
        ["python", "src/cli/swarm_cli.py", "--json", "status", job_id],
        capture_output=True, text=True
    )
    status = json.loads(result.stdout)
    if status["status"] in ["COMPLETED", "FAILED"]:
        break
    time.sleep(5)
```

## Running the CLI

```bash
# From project root
python src/cli/swarm_cli.py --help

# Or as a module
python -m src.cli.swarm_cli --help
```
