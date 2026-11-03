"""Optional cloud compiler. Deploy only after explicit publication authorization."""

from pathlib import Path
import modal

ROOT=Path(__file__).resolve().parent
image=(modal.Image.debian_slim(python_version='3.13')
       .add_local_dir(ROOT/'exitforge',remote_path='/root/exitforge',ignore=['__pycache__'])
       .add_local_file(ROOT/'static/runtime.js',remote_path='/root/static/runtime.js')
       .add_local_file(ROOT/'static/workspace.js',remote_path='/root/static/workspace.js')
       .add_local_file(ROOT/'static/process.js',remote_path='/root/static/process.js')
       .add_local_file(ROOT/'static/process-ui.js',remote_path='/root/static/process-ui.js')
       .add_local_file(ROOT/'static/process-records.js',remote_path='/root/static/process-records.js')
       .add_local_file(ROOT/'static/process-record-form.js',remote_path='/root/static/process-record-form.js')
       .add_local_file(ROOT/'static/handoff.js',remote_path='/root/static/handoff.js')
       .add_local_file(ROOT/'static/handoff-view.js',remote_path='/root/static/handoff-view.js')
       .add_local_file(ROOT/'static/style.css',remote_path='/root/static/style.css'))
app=modal.App('exitforge-compiler',image=image)


@app.function(timeout=60,cpu=1,memory=512,max_containers=1,scaledown_window=2,retries=0)
def package_workspace(project:dict)->str:
    from exitforge.compiler import compile_application
    return compile_application(project)
