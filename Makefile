.PHONY: install
install:
	python -m venv .env
	.env/bin/pip install -r requirements.txt

.PHONY: run
run:
	.env/bin/streamlit run main.py --server.headless true -- $(ARGS)

.PHONY: format
format:
	.env/bin/black --line-length 88 *.py
	.env/bin/isort *.py
