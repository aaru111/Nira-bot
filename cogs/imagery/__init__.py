from importlib.util import spec_from_file_location, module_from_spec
import os
import sys
from glob import glob
from typing import List, Optional
from types import ModuleType


def get_extensions() -> List[str]:
    """
    Get all extension modules that have a setup function.

    Returns:
        List[str]: A list of qualified module names for valid extensions
    """
    current_dir: str = os.path.dirname(__file__)
    extension_files: List[str] = glob(os.path.join(current_dir, '[!_]*.py'))
    extensions: List[str] = []

    for file in extension_files:
        module_name: str = os.path.splitext(os.path.basename(file))[0]
        full_module_name: str = f"{__package__}.{module_name}"

        # Import the module to check for setup function
        spec = spec_from_file_location(full_module_name, file)
        if spec is None or spec.loader is None:
            continue

        module: Optional[ModuleType] = module_from_spec(spec)
        if module is None:
            continue

        sys.modules[full_module_name] = module
        spec.loader.exec_module(module)

        # Only include if setup function exists
        if hasattr(module, 'setup'):
            extensions.append(full_module_name)

    return extensions


# Initialize the list of valid extensions
EXTENSIONS: List[str] = get_extensions()
