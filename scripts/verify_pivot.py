"""
Verification Script for Pivot Architecture
Validates:
1. LoRA Template with Gradient Accumulation
2. SweepManager Pipeline
3. Basic components existence
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.templates import get_template, list_templates
from src.execution.pipeline import SweepConfig, SweepManager

def test_lora_template():
    print("Testing LoRA Template...")
    template = get_template("lora_finetune")
    if not template:
        print("❌ LoRA template not found!")
        return False
    
    if "gradient_accumulation_steps" not in template.script and "Gradient Accumulation" not in template.description:
         print("❌ LoRA template missing Gradient Accumulation updates!")
         return False
         
    print("✅ LoRA template valid (Optimized for Swarm).")
    return True

def test_sweep_manager():
    print("\nTesting Sweep Manager...")
    manager = SweepManager()
    
    config = SweepConfig(
        template_name="lora_finetune",
        base_params={
            "base_model": "llama-2-7b",
            "dataset_name": "wikitext",
            "epochs": 1
        },
        search_space={
            "lora_r": [8, 16],
            "batch_size": [1, 2]
        }
    )
    
    jobs = manager.generate_sweep(config)
    
    if len(jobs) != 4:
        print(f"❌ Expected 4 jobs, got {len(jobs)}")
        return False
        
    print(f"✅ Generated {len(jobs)} jobs from sweep config.")
    
    # Check first job content
    first_job = jobs[0]
    print(f"   Job 1: {first_job.name}")
    if "LORA_R = 8" not in first_job.script_content:
         print("❌ Parameter substitution failed!")
         return False
         
    print("✅ Parameter substitution successful.")
    return True

def test_components_exist():
    print("\nChecking Components...")
    
    tunnel_path = Path("src/networking/tunnel.py")
    dashboard_path = Path("src/seller/dashboard/index.html")
    server_path = Path("src/seller/dashboard/server.py")
    
    if not tunnel_path.exists():
        print("❌ Tunnel module missing")
        return False
    if not dashboard_path.exists():
        print("❌ Dashboard frontend missing")
        return False
    if not server_path.exists():
        print("❌ Dashboard backend missing")
        return False
        
    print("✅ All new components present.")
    return True

def main():
    print("=== SWARM PIVOT VERIFICATION ===\n")
    
    results = [
        test_lora_template(),
        test_sweep_manager(),
        test_components_exist()
    ]
    
    if all(results):
        print("\n🎉 SUCCESS: System Pivot Verified!")
        sys.exit(0)
    else:
        print("\n💥 FAILURE: Verification failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
