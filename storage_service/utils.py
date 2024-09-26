import urllib.parse

def encode_uri_compnents(path: str):
    """
    Encode the path components to encode the special characters, 
    also to avoid path traversal attack
    """
    path_sp = path.split("/")
    mapped = map(lambda x: urllib.parse.quote(x), path_sp)
    return "/".join(mapped)

def decode_uri_compnents(path: str):
    """
    Decode the path components to decode the special characters
    """
    path_sp = path.split("/")
    mapped = map(lambda x: urllib.parse.unquote(x), path_sp)
    return "/".join(mapped)