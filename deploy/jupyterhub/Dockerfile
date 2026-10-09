# JupyterHub control plane (no student code runs here)
FROM quay.io/jupyterhub/jupyterhub:5.2.1

RUN pip install --no-cache-dir \
      "dockerspawner==13.*" \
      "oauthenticator==17.*" \
      "jupyterhub-idle-culler==1.*"

COPY jupyterhub_config.py /srv/jupyterhub/jupyterhub_config.py
WORKDIR /srv/jupyterhub
CMD ["jupyterhub", "-f", "/srv/jupyterhub/jupyterhub_config.py"]
