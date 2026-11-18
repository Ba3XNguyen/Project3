"""Start a local server, check health and root HTTP, and stop that process."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

folder=Path(__file__).resolve().parent
command=[sys.executable,'-m','streamlit','run',str(folder/'app.py'),
         '--server.address','127.0.0.1','--server.port','8507','--server.headless','true',
         '--browser.gatherUsageStats','false']
kwargs={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
with (folder/'server_check.log').open('w',encoding='utf-8') as log:
    process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,**kwargs)
    try:
        for _ in range(90):
            if process.poll() is not None:
                raise RuntimeError('Streamlit exited; see server_check.log')
            try:
                with urllib.request.urlopen('http://127.0.0.1:8507/_stcore/health',timeout=2) as response:
                    assert response.status==200
                    body=response.read().decode()
                break
            except OSError:
                time.sleep(.5)
        else:
            raise RuntimeError('Streamlit startup timeout')
        with urllib.request.urlopen('http://127.0.0.1:8507/',timeout=5) as response:
            assert response.status==200 and b'<html' in response.read().lower()
        (folder/'server_check.json').write_text(json.dumps({'status':'PASS','health':body,'root_http':200,
            'address':'127.0.0.1:8507','note':'Server stopped after test; no browser visual inspection.'},indent=2),encoding='utf-8')
        print('PASS: local Streamlit health and root HTTP 200')
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
