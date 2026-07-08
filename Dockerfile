# ai-data-platform local console image
FROM python:3.12-slim AS build
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir build && python -m build --wheel --outdir /dist

FROM python:3.12-slim
RUN useradd --create-home adp
USER adp
WORKDIR /work
COPY --from=build /dist/*.whl /tmp/
RUN pip install --no-cache-dir --user /tmp/*.whl && rm /tmp/*.whl
ENV PATH="/home/adp/.local/bin:${PATH}"
EXPOSE 8765
# project directory is mounted at /work
ENTRYPOINT ["adp"]
CMD ["ui", "--host", "0.0.0.0", "--port", "8765"]
