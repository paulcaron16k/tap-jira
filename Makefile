
.PHONY: local_setup venv venv_deps compile pylint test run
local_setup:
	pip install --upgrade pip
	pip install -U pre-commit
	pre-commit install

venv: venv/tap-jira

venv/tap-jira:
	@if [ -z "$$(which mysql)" ]; then \
	    sudo apt-get install -y libmysqlclient-dev; \
	fi;
	@if [ ! -d venv ]; then mkdir venv; fi;
	@python3 -m venv venv/tap-jira; \
	. ./venv/tap-jira/bin/activate ; \
	python3 -m pip install --upgrade pip; \
	pip install --upgrade setuptools; \
	pip install --upgrade wheel; \
	echo "Linking ./tap_jira source into venv": \
	echo "which tap-jira executable will be ./venv/tap-jira/bin/tap-jira"; \
	echo "Note, the use of --use-pep517 is for legacy install/setup"; \
	pip install -e . --use-pep517;
	@echo "Virtual environment ready: venv/tap-jira";
	@echo "Use \"make run\" or manually activate venv and test tap-jira manually";

venv_deps:
	. ./venv/tap-jira/bin/activate ; \
	echo "pip install singer_sdk"; \
	pip install -r requirements-dev.txt; \
	pip install pylint;

compile: venv
	. ./venv/tap-jira/bin/activate; \
	python3 -m compileall tap_jira; \
	python3 -m compileall tests;

pylint: venv
	. ./venv/tap-jira/bin/activate; \
	pylint --rcfile .pylintrc app/

test: venv
	. ./venv/tap-jira/bin/activate; \
	python -m unittest

run: venv
	@if [ ! -f tap_config.json ]; then \
		echo "Copy tap_config.json.template to tap_config.json and ediit"; \
		false; \
		return; \
	fi;
	@ . ./venv/tap-jira/bin/activate; \
	if [ ! -f catalog.json ]; then \
	    echo "Running discovery to obtain the stream catalog"; \
		echo "Add selected=true in stream and stream.<property>.metadata to extract"; \
	    ./venv/tap-jira/bin/tap-jira --config tap_config.json --discover > catalog-file.json; \
	else \
		echo "Using existing catalog-file.json with streams selected"; \
	fi; \
	echo "Running in sync mode to fetch records. Edit catalog.json to select streams and fields"; \
	./venv/tap-jira/bin/tap-jira --config tap_config.json --properties catalog-file.json;
	@echo "Expect output SCHEMA, RECORD, STATE, and METRIC messages"; 


