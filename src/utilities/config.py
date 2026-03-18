"""Configuration loading from home directory"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv, set_key, dotenv_values
from . import console_helper
import logging

_config_logger = logging.getLogger("ado_copilot_agent.utilities.config")


def _load_env_file(env_path: Path, override: bool = True):
    """Load a .env file and copy non-empty values into process environment."""
    if not env_path.exists():
        return

    load_dotenv(env_path, override=override)
    env_values = dotenv_values(env_path)
    for key, value in env_values.items():
        if value:
            os.environ[key] = value


def load_env_from_home():
    """Load configuration with project .env taking precedence over home .env."""
    home = Path.home()

    if sys.platform == "win32":
        # Windows: C:\Users\{username}\.ado-copilot-agent\.env
        env_path = home / ".ado-copilot-agent" / ".env"
        config_dir = home / ".ado-copilot-agent"
    else:
        # Unix/Linux/Mac: ~/.ado-copilot-agent/.env
        env_path = home / ".ado-copilot-agent" / ".env"
        config_dir = home / ".ado-copilot-agent"

    project_env_path = Path.cwd() / ".env"

    # Create config directory if it doesn't exist
    config_dir.mkdir(parents=True, exist_ok=True)

    # Fallback order: home .env first, then project .env overrides when present.
    _load_env_file(env_path, override=False)

    active_env = env_path
    if project_env_path.exists():
        _load_env_file(project_env_path, override=True)
        active_env = project_env_path

    print(f"Loading config from: {active_env}")
    _config_logger.debug("Active env file: %s", active_env)
    
    return config_dir, env_path


def get_env_variable(var_name: str, prompt_text: str = None, password: bool = True) -> str:
    """Get environment variable from .env file, prompt if missing, and save to file
    
    Args:
        var_name: Name of the environment variable
        prompt_text: Custom prompt text (optional)
        password: Whether to hide input when prompting
    
    Returns:
        The environment variable value
    """
    env_path = get_env_path()
    
    # Load current values from .env file
    env_values = dotenv_values(env_path) if env_path.exists() else {}
    
    # Check if variable exists in .env file or already in process environment
    value = env_values.get(var_name) or os.environ.get(var_name)
    
    if value:
        # Set in current process environment if not already there
        if var_name not in os.environ:
            os.environ[var_name] = value
        return value
    
    # Variable not found, prompt user
    if not prompt_text:
        prompt_text = f"{var_name} not found. Please enter your value:"
    
    value = console_helper.prompt(prompt_text, password=password)
    
    # Ensure .env file exists
    if not env_path.exists():
        env_path.touch()
    
    # Save to .env file
    set_key(env_path, var_name, value)
    
    # Set in current process environment
    os.environ[var_name] = value
    
    console_helper.show_success(f"{var_name} saved to {env_path}")
    
    return value


def get_config_dir() -> Path:
    """Get the config directory path"""
    home = Path.home()
    return home / ".ado-copilot-agent"


def get_env_path() -> Path:
    """Get the .env file path, preferring project-local .env when present."""
    project_env = Path.cwd() / ".env"
    if project_env.exists():
        return project_env

    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / ".env"
