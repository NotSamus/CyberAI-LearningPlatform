# CPU notebook image. Build from deploy/images:  docker build -f cpu/Dockerfile -t cyberai/notebook-cpu .
# Pin a dated tag from https://quay.io/repository/jupyter/scipy-notebook for reproducible builds.
FROM quay.io/jupyter/scipy-notebook:latest

# otter-grader: students run the checks in autograded notebooks with it (`grader.check("q1")`), and
# submissions are graded in a container of this same image (see grader/).
RUN pip install --no-cache-dir "jupyterhub==5.2.1" "otter-grader==7.0.0"

COPY common/jupyter_server_config.py /etc/jupyter/jupyter_server_config.py
# JupyterLab defaults: save every 30 seconds (Submit hands in the saved file), no "Jupyter news" pop-up
COPY common/overrides.json /opt/conda/share/jupyter/lab/settings/overrides.json
