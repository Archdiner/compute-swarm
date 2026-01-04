"""
Container Image Validator
Validates Docker images against allowed registries and security policies
"""

import re
from typing import Optional, List, Tuple
from dataclasses import dataclass

import structlog

logger = structlog.get_logger()


@dataclass
class ValidationResult:
    """Result of container image validation"""
    valid: bool
    image: str
    registry: Optional[str]
    repository: str
    tag: str
    error: Optional[str] = None


class ContainerValidator:
    """
    Validates Docker container images for security
    
    Features:
    - Registry whitelist
    - Image name pattern validation
    - Tag policy enforcement
    - Blocked image detection
    """
    
    # Default allowed registries
    DEFAULT_ALLOWED_REGISTRIES = [
        "docker.io",
        "ghcr.io",
        "gcr.io",
        "quay.io",
        "registry.hub.docker.com",
        "computeswarm",
    ]
    
    # Blocked images (security concerns)
    BLOCKED_IMAGES = [
        "docker",  # Docker-in-Docker security risk
        "docker:dind",
        "rancher/rancher",
        "portainer/portainer",
    ]
    
    # Pattern for valid image names
    IMAGE_PATTERN = re.compile(
        r'^'
        r'(?:(?P<registry>[a-zA-Z0-9][-a-zA-Z0-9.]*[a-zA-Z0-9](?::\d+)?)/)?'
        r'(?P<repository>[a-z0-9](?:[-._/a-z0-9]*[a-z0-9])?)'
        r'(?::(?P<tag>[a-zA-Z0-9][-._a-zA-Z0-9]*[a-zA-Z0-9]))?'
        r'(?:@(?P<digest>sha256:[a-f0-9]{64}))?'
        r'$'
    )
    
    def __init__(
        self,
        allowed_registries: Optional[List[str]] = None,
        allow_latest_tag: bool = True,
        require_digest: bool = False
    ):
        """
        Initialize container validator
        
        Args:
            allowed_registries: List of allowed Docker registries
            allow_latest_tag: Whether to allow 'latest' tag
            require_digest: Whether to require image digest
        """
        self.allowed_registries = allowed_registries or self.DEFAULT_ALLOWED_REGISTRIES
        self.allow_latest_tag = allow_latest_tag
        self.require_digest = require_digest
    
    def parse_image(self, image: str) -> Tuple[Optional[str], str, str]:
        """
        Parse a Docker image reference into components
        
        Args:
            image: Docker image reference (e.g., "registry/repo:tag")
            
        Returns:
            Tuple of (registry, repository, tag)
        """
        match = self.IMAGE_PATTERN.match(image)
        
        if not match:
            return None, image, "latest"
        
        registry = match.group("registry")
        repository = match.group("repository")
        tag = match.group("tag") or "latest"
        
        return registry, repository, tag
    
    def validate(self, image: str) -> ValidationResult:
        """
        Validate a Docker image reference
        
        Args:
            image: Docker image reference to validate
            
        Returns:
            ValidationResult with validation status
        """
        # Parse image
        registry, repository, tag = self.parse_image(image)
        
        # Check against blocked list
        full_image = f"{registry}/{repository}" if registry else repository
        for blocked in self.BLOCKED_IMAGES:
            if blocked in image.lower():
                logger.warning("blocked_image_rejected", image=image)
                return ValidationResult(
                    valid=False,
                    image=image,
                    registry=registry,
                    repository=repository,
                    tag=tag,
                    error=f"Image is blocked for security reasons: {blocked}"
                )
        
        # Check registry whitelist
        if registry:
            if not any(registry.startswith(allowed) for allowed in self.allowed_registries):
                logger.warning("registry_not_allowed", image=image, registry=registry)
                return ValidationResult(
                    valid=False,
                    image=image,
                    registry=registry,
                    repository=repository,
                    tag=tag,
                    error=f"Registry not allowed: {registry}. Allowed: {', '.join(self.allowed_registries)}"
                )
        else:
            # Official Docker Hub images (no registry specified)
            # These are allowed if docker.io is in allowed registries
            if "docker.io" not in self.allowed_registries:
                return ValidationResult(
                    valid=False,
                    image=image,
                    registry=registry,
                    repository=repository,
                    tag=tag,
                    error="Docker Hub images require docker.io in allowed registries"
                )
        
        # Check latest tag policy
        if tag == "latest" and not self.allow_latest_tag:
            return ValidationResult(
                valid=False,
                image=image,
                registry=registry,
                repository=repository,
                tag=tag,
                error="'latest' tag is not allowed. Please specify a version."
            )
        
        # Check digest requirement
        if self.require_digest and "@sha256:" not in image:
            return ValidationResult(
                valid=False,
                image=image,
                registry=registry,
                repository=repository,
                tag=tag,
                error="Image digest is required for security"
            )
        
        logger.debug("image_validated", image=image, registry=registry, tag=tag)
        
        return ValidationResult(
            valid=True,
            image=image,
            registry=registry,
            repository=repository,
            tag=tag
        )
    
    def normalize_image(self, image: str) -> str:
        """
        Normalize a Docker image reference to full form
        
        Args:
            image: Docker image reference
            
        Returns:
            Normalized image reference
        """
        registry, repository, tag = self.parse_image(image)
        
        if not registry:
            # Add docker.io for official images
            if "/" not in repository:
                registry = "docker.io/library"
            else:
                registry = "docker.io"
        
        return f"{registry}/{repository}:{tag}"
    
    def is_official_image(self, image: str) -> bool:
        """Check if image is an official Docker Hub image"""
        registry, repository, _ = self.parse_image(image)
        return registry is None and "/" not in repository
    
    def get_recommended_images(self) -> List[dict]:
        """Get list of recommended pre-built images"""
        return [
            {
                "image": "jupyter/pytorch-notebook:latest",
                "description": "JupyterLab with PyTorch (public image)",
                "gpu": True
            },
            {
                "image": "pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime",
                "description": "Official PyTorch with CUDA",
                "gpu": True
            },
            {
                "image": "tensorflow/tensorflow:2.14.0-gpu",
                "description": "TensorFlow with GPU support",
                "gpu": True
            },
            {
                "image": "huggingface/transformers-pytorch-gpu:latest",
                "description": "Hugging Face Transformers",
                "gpu": True
            },
            {
                "image": "python:3.11-slim",
                "description": "Minimal Python environment",
                "gpu": False
            },
            {
                "image": "continuumio/anaconda3:latest",
                "description": "Anaconda with common data science packages",
                "gpu": False
            }
        ]


# Default validator instance
_validator: Optional[ContainerValidator] = None


def get_container_validator(
    allowed_registries: Optional[List[str]] = None
) -> ContainerValidator:
    """Get or create container validator"""
    global _validator
    
    if _validator is None or allowed_registries:
        _validator = ContainerValidator(allowed_registries=allowed_registries)
    
    return _validator

