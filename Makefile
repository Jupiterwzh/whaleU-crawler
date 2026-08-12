# Makefile — 一键测试
.PHONY: test install

test:
	cd explorer-agent && python -m pytest -q

install:
	pip install -r explorer-agent/requirements.txt
