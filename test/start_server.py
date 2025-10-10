import subprocess, time
from .config import SANDBOX_DIR, SERVER_PORT
import requests
from lfss.api import Client

def start_server_thread(cwd, port):
    return subprocess.Popen(['lfss-serve', '--workers', '4', '--port', str(port)], cwd=cwd)

class Server:
    def __init__(self):
        ...
    
    def start(self, cwd: str = str(SANDBOX_DIR), port: int = SERVER_PORT):
        self._s = start_server_thread(cwd, port)
        print("[server] Server started")
        while True:
            self._c = Client(f"http://localhost:{SERVER_PORT}", token='_wrong_token_')
            try:
                self._c.whoami()
            except Exception as e:
                if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 401:
                    print("[server] Server is up")
                    break
                if isinstance(e, KeyboardInterrupt):
                    raise e
                time.sleep(0.1)
                continue
            break
    
    def stop(self):
        self._s.terminate()
        print("[server] Server stopped")

if __name__ == '__main__':
    s = Server()
    s.start()
    time.sleep(2)
    s.stop()
    time.sleep(2)
    print("Done")