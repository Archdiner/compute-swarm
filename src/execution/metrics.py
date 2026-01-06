"""
Metrics Collection for Training Jobs
Captures and stores training metrics automatically
"""

import re
from typing import Dict, List, Optional, Any
from datetime import datetime
from decimal import Decimal
import structlog

logger = structlog.get_logger()


class MetricsCollector:
    """Collects and parses training metrics from job output"""
    
    # Common metric patterns
    METRIC_PATTERNS = {
        "loss": [
            r"loss[:\s=]+([0-9]+\.[0-9]+)",
            r"Loss[:\s=]+([0-9]+\.[0-9]+)",
            r"train_loss[:\s=]+([0-9]+\.[0-9]+)",
            r"val_loss[:\s=]+([0-9]+\.[0-9]+)",
        ],
        "accuracy": [
            r"accuracy[:\s=]+([0-9]+\.[0-9]+)",
            r"Accuracy[:\s=]+([0-9]+\.[0-9]+)",
            r"acc[:\s=]+([0-9]+\.[0-9]+)",
            r"train_acc[:\s=]+([0-9]+\.[0-9]+)",
            r"val_acc[:\s=]+([0-9]+\.[0-9]+)",
        ],
        "epoch": [
            r"epoch[:\s]+([0-9]+)",
            r"Epoch[:\s]+([0-9]+)",
            r"epoch\s+([0-9]+)",
        ],
        "learning_rate": [
            r"lr[:\s=]+([0-9]+\.[0-9]+(?:[eE][+-]?[0-9]+)?)",
            r"learning_rate[:\s=]+([0-9]+\.[0-9]+(?:[eE][+-]?[0-9]+)?)",
            r"Learning Rate[:\s=]+([0-9]+\.[0-9]+(?:[eE][+-]?[0-9]+)?)",
        ],
        "f1": [
            r"f1[:\s=]+([0-9]+\.[0-9]+)",
            r"F1[:\s=]+([0-9]+\.[0-9]+)",
            r"f1_score[:\s=]+([0-9]+\.[0-9]+)",
        ],
        "step": [
            r"step[:\s]+([0-9]+)",
            r"Step[:\s]+([0-9]+)",
        ],
    }
    
    def __init__(self, job_id: str):
        """
        Initialize metrics collector for a job
        
        Args:
            job_id: Job ID
        """
        self.job_id = job_id
        self.metrics: List[Dict[str, Any]] = []
    
    def parse_output(self, output: str, stderr: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Parse metrics from job output
        
        Args:
            output: stdout content
            stderr: stderr content (optional)
            
        Returns:
            List of metric dicts with name, value, timestamp, step
        """
        combined_output = output
        if stderr:
            combined_output += "\n" + stderr
        
        parsed_metrics = []
        lines = combined_output.split("\n")
        
        for line_num, line in enumerate(lines):
            # Try to extract metrics from this line
            for metric_name, patterns in self.METRIC_PATTERNS.items():
                for pattern in patterns:
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        try:
                            value = float(match.group(1))
                            
                            # Try to extract step/epoch from the same line or nearby
                            step = None
                            epoch = None
                            
                            # Look for step in the same line
                            step_match = re.search(r"step[:\s]+([0-9]+)", line, re.IGNORECASE)
                            if step_match:
                                step = int(step_match.group(1))
                            
                            # Look for epoch in the same line
                            epoch_match = re.search(r"epoch[:\s]+([0-9]+)", line, re.IGNORECASE)
                            if epoch_match:
                                epoch = int(epoch_match.group(1))
                            
                            metric = {
                                "job_id": self.job_id,
                                "metric_name": metric_name,
                                "value": value,
                                "step": step,
                                "epoch": epoch,
                                "timestamp": datetime.utcnow().isoformat(),
                                "line_number": line_num
                            }
                            
                            parsed_metrics.append(metric)
                            logger.debug(
                                "metric_parsed",
                                job_id=self.job_id,
                                metric_name=metric_name,
                                value=value,
                                step=step
                            )
                            break  # Only match first pattern for this metric type
                        except (ValueError, IndexError):
                            continue
        
        self.metrics.extend(parsed_metrics)
        return parsed_metrics
    
    def detect_mlflow_usage(self, output: str) -> bool:
        """
        Detect if MLflow is being used
        
        Args:
            output: Job output
            
        Returns:
            True if MLflow detected
        """
        mlflow_patterns = [
            r"mlflow\.log_metric",
            r"mlflow\.log_param",
            r"MLflow",
        ]
        
        for pattern in mlflow_patterns:
            if re.search(pattern, output, re.IGNORECASE):
                logger.info("mlflow_detected", job_id=self.job_id)
                return True
        
        return False
    
    def detect_wandb_usage(self, output: str) -> bool:
        """
        Detect if Weights & Biases is being used
        
        Args:
            output: Job output
            
        Returns:
            True if W&B detected
        """
        wandb_patterns = [
            r"wandb\.log",
            r"wandb\.init",
            r"Weights & Biases",
            r"W&B",
        ]
        
        for pattern in wandb_patterns:
            if re.search(pattern, output, re.IGNORECASE):
                logger.info("wandb_detected", job_id=self.job_id)
                return True
        
        return False
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get summary of collected metrics
        
        Returns:
            Summary dict with metric names, counts, latest values
        """
        if not self.metrics:
            return {
                "total_metrics": 0,
                "metric_names": [],
                "latest_values": {}
            }
        
        metric_names = set(m["metric_name"] for m in self.metrics)
        latest_values = {}
        
        for metric_name in metric_names:
            metric_values = [m for m in self.metrics if m["metric_name"] == metric_name]
            if metric_values:
                # Get latest value (by timestamp or step)
                latest = max(metric_values, key=lambda x: x.get("step", 0) or x.get("timestamp", ""))
                latest_values[metric_name] = {
                    "value": latest["value"],
                    "step": latest.get("step"),
                    "epoch": latest.get("epoch"),
                    "timestamp": latest["timestamp"]
                }
        
        return {
            "total_metrics": len(self.metrics),
            "metric_names": sorted(metric_names),
            "latest_values": latest_values,
            "metrics_by_name": {
                name: len([m for m in self.metrics if m["metric_name"] == name])
                for name in metric_names
            }
        }
    
    def get_metrics_by_name(self, metric_name: str) -> List[Dict[str, Any]]:
        """
        Get all metrics with a specific name
        
        Args:
            metric_name: Name of metric to retrieve
            
        Returns:
            List of metric dicts
        """
        return [m for m in self.metrics if m["metric_name"] == metric_name]
    
    def get_time_series(self, metric_name: str) -> List[Dict[str, Any]]:
        """
        Get time series data for a metric
        
        Args:
            metric_name: Name of metric
            
        Returns:
            List of {step, value, timestamp} dicts sorted by step
        """
        metrics = self.get_metrics_by_name(metric_name)
        
        # Sort by step if available, otherwise by timestamp
        sorted_metrics = sorted(
            metrics,
            key=lambda x: (x.get("step") or 0, x.get("timestamp", ""))
        )
        
        return [
            {
                "step": m.get("step"),
                "epoch": m.get("epoch"),
                "value": m["value"],
                "timestamp": m["timestamp"]
            }
            for m in sorted_metrics
        ]


def create_metrics_collector(job_id: str) -> MetricsCollector:
    """
    Create a metrics collector for a job
    
    Args:
        job_id: Job ID
        
    Returns:
        MetricsCollector instance
    """
    return MetricsCollector(job_id)

