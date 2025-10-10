
from .bundle import *
from .connector import Client

# Backward compatibility
class Connector(Client): ...

__all__ = [
    "upload_file", "upload_directory",
    "download_file", "download_directory", 
    "Client", "Connector",
]