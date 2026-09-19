from dataclasses import dataclass
from pathlib import Path
import os

@dataclass
class Config:
    model: str = os.getenv('WEB_CREATION_MODEL', 'gemini-2.5-flash')
    api_key: str = os.getenv('GEMINI_API_KEY', '')
    workspace: Path = Path(os.getenv('WEB_CREATION_WORKSPACE', 'workspace'))
    max_debug_iterations: int = int(os.getenv('MAX_DEBUG_ITERATIONS', '3'))
    command_timeout: int = int(os.getenv('COMMAND_TIMEOUT', '60'))

CONFIG = Config()
CONFIG.workspace.mkdir(parents=True, exist_ok=True)
