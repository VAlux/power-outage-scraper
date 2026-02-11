#!/bin/bash

docker buildx build --platform linux/arm64 -t alvo/poweroutage-scraper:1.0  .
# docker buildx build --platform linux/amd64 -t alvo/poweroutage-scraper:1.0  .
