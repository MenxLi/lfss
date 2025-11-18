
import subprocess
from .common import create_server_context, get_conn
from ..config import SANDBOX_DIR

server = create_server_context()

def test_init_user_creation(server):
    subprocess.check_output(['lfss-user', 'add', 'u0', 'test', "--admin"], cwd=SANDBOX_DIR)

def test_markdown_mime_type(server):
    u0 = get_conn('u0')
    u0.put('u0/readme.md', b'# Hello World\nThis is a markdown file.')
    fmeta = u0.get_fmeta('u0/readme.md')
    assert fmeta is not None, "Get file meta failed"
    assert fmeta.mime_type == 'text/markdown', f"Mime type is not correct, got {fmeta.mime_type}"

def test_json_mime_type(server):
    u0 = get_conn('u0')
    u0.put_json('u0/data.json', {'key': 'value'})
    fmeta = u0.get_fmeta('u0/data.json')
    assert fmeta is not None, "Get file meta failed"
    assert fmeta.mime_type == 'application/json', f"Mime type is not correct, got {fmeta.mime_type}"

def test_png_infer(server):
    u0 = get_conn('u0')
    png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\nIDATx\xdac\xf8\x0f\x00\x01\x01\x01\x00\x18\xdd\x8d\xe5\x00\x00\x00\x00IEND\xaeB`\x82'
    u0.put('u0/image.png', png_data)
    fmeta = u0.get_fmeta('u0/image.png')
    assert fmeta is not None, "Get file meta failed"
    assert fmeta.mime_type == 'image/png', f"Mime type is not correct, got {fmeta.mime_type}"

def test_known_extension(server):
    u0 = get_conn('u0')
    u0.put('u0/document.102ng-aah2', b'\a\r\nThis is a test document with a known extension.')
    fmeta = u0.get_fmeta('u0/document.102ng-aah2')
    assert fmeta is not None, "Get file meta failed"
    assert fmeta.mime_type == 'application/octet-stream', f"Mime type is not correct, got {fmeta.mime_type}"