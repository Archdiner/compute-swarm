"""
Pipeline Execution Module
Handles complex job coordination including Hyperparameter Sweeps and Workflows
(Track A: Core Engine Refactor)
"""

import itertools
import copy
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import structlog
from src.templates import get_template, render_template

logger = structlog.get_logger()

@dataclass
class SweepConfig:
    """Configuration for a Hyperparameter Sweep"""
    template_name: str
    base_params: Dict[str, Any]
    search_space: Dict[str, List[Any]]
    max_jobs: Optional[int] = None
    strategy: str = "grid"  # grid, random (future)

@dataclass
class JobRequest:
    """A generated job request"""
    template_name: str
    params: Dict[str, Any]
    script_content: str
    name: str

class SweepManager:
    """
    Manages Hyperparameter Sweeps.
    Generates multiple JobRequests based on a search space.
    """
    
    def __init__(self):
        pass

    def generate_sweep(self, config: SweepConfig) -> List[JobRequest]:
        """
        Generate a list of jobs for a sweep
        
        Args:
            config: Sweep configuration
            
        Returns:
            List of fully rendered JobRequests
        """
        template = get_template(config.template_name)
        if not template:
            raise ValueError(f"Template {config.template_name} not found")

        keys = list(config.search_space.keys())
        values = list(config.search_space.values())
        
        # Grid Search Implementation
        combinations = list(itertools.product(*values))
        
        job_requests = []
        
        for i, combo in enumerate(combinations):
            if config.max_jobs and i >= config.max_jobs:
                break
                
            # Construct params for this specific job
            current_params = copy.deepcopy(config.base_params)
            param_str_parts = []
            
            for key, value in zip(keys, combo):
                current_params[key] = value
                param_str_parts.append(f"{key}={value}")
            
            # Render script
            try:
                script = render_template(config.template_name, **current_params)
            except ValueError as e:
                logger.error("template_render_failed", error=str(e), template=config.template_name)
                continue
                
            # Create Job Name
            job_name = f"sweep_{config.template_name}_{'_'.join(param_str_parts)}"
            
            job_requests.append(JobRequest(
                template_name=config.template_name,
                params=current_params,
                script_content=script,
                name=job_name
            ))
            
        logger.info(
            "sweep_generated", 
            template=config.template_name, 
            jobs_count=len(job_requests),
            strategy=config.strategy
        )
        
        return job_requests

    def validate_search_space(self, template_name: str, search_space: Dict[str, List[Any]]) -> bool:
        """Validate that search parameters exist in template"""
        template = get_template(template_name)
        if not template:
            return False
            
        if not template.parameters:
            return False
            
        valid_params = set(template.parameters.keys())
        search_params = set(search_space.keys())
        
        return search_params.issubset(valid_params)
