# GPU notebook image: CUDA 12 user-space libraries + PyTorch, from Jupyter docker-stacks.
# Build from deploy/images:  docker build -f gpu/Dockerfile -t cyberai/notebook-gpu .
# The host only needs the NVIDIA driver + NVIDIA Container Toolkit; CUDA lives in the image.
FROM quay.io/jupyter/pytorch-notebook:cuda12-latest

RUN pip install --no-cache-dir \
      "jupyterhub==5.2.1" \
      "otter-grader==7.0.0" \
      torchvision torchaudio \
      scikit-learn pandas matplotlib seaborn \
      transformers datasets

# TensorFlow instead of PyTorch: use  FROM quay.io/jupyter/tensorflow-notebook:cuda-latest

COPY common/jupyter_server_config.py /etc/jupyter/jupyter_server_config.py
# JupyterLab defaults: save every 30 seconds (Submit hands in the saved file), no "Jupyter news" pop-up
COPY common/overrides.json /opt/conda/share/jupyter/lab/settings/overrides.json
COPY common/00-gpu-memory-cap.py /opt/cyberai/00-gpu-memory-cap.py
# Run the VRAM cap in every kernel (system-wide IPython config; the home dir is a volume)
USER root
RUN mkdir -p /etc/ipython && \
    echo "c.InteractiveShellApp.exec_files = ['/opt/cyberai/00-gpu-memory-cap.py']" \
      > /etc/ipython/ipython_kernel_config.py
USER ${NB_UID}
