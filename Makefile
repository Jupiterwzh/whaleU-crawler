# Makefile — 一键测试（Python 三 Agent + Node 爬虫）
.PHONY: test test-py test-node install

test: test-py test-node

test-py:
	cd explorer-agent && python -m pytest -q
	cd query-agent && python -m pytest -q
	cd rag-manager && python -m pytest -q

test-node:
	cd crawler && node --test test/collector.test.js

install:
	pip install -r explorer-agent/requirements.txt
	pip install -r query-agent/requirements.txt
	pip install -r rag-manager/requirements.txt
