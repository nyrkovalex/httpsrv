SRC_PATH = httpsrv

TEST_PATH = test
TEST_PATTERN = *_test.py
TEST_CMD = make tests
DOCS_PATH = docs
DOCS_CMD = $(MAKE) -C $(DOCS_PATH) html

ifndef VERBOSE
	MAKEFLAGS += --no-print-directory
endif

tests:
	python -m unittest discover -s $(TEST_PATH) -p $(TEST_PATTERN)

watch:
	watchmedo shell-command --patterns='*.py' --ignore-directories --recursive --command="$(TEST_CMD)" -W $(SRC_PATH) $(TEST_PATH)

watch-docs:
	watchmedo shell-command --patterns='*.rst;*.py' --ignore-directories --recursive --command="$(DOCS_CMD)" -W .

docs:
	$(DOCS_CMD)

upload-test:
	python setup.py bdist_wheel upload -r https://testpypi.python.org/pypi

upload:
	python setup.py bdist_wheel upload
