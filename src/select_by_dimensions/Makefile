BLENDER_EXE = "/Applications/Blender/Blender 4.5 LTS.app/Contents/MacOS/Blender"
file ?=

.PHONY: help build validate test

help:
	@echo "Usage:"
	@echo "  make build"
	@echo "  make validate"
	@echo "  make validate file=add-on-package.zip"
	@echo "  make test"

build:
	$(BLENDER_EXE) --command extension build

validate:
	$(BLENDER_EXE) --command extension validate $(file)

test:
	$(BLENDER_EXE) --background --factory-startup --python ../../tests/test_select_by_dimensions.py
