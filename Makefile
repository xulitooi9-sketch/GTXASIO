CC ?= cc
CFLAGS ?= -O2 -Wall -Wextra -Wpedantic -std=c11
all: build/gtxasio-engine
build/gtxasio-engine: native/engine.c common/protocol.h
	@mkdir -p build
	$(CC) $(CFLAGS) -o $@ native/engine.c -ldl -pthread -lm
check: all
	python3 -m unittest discover -s tests -v
clean:
	rm -f build/gtxasio-engine
.PHONY: all check clean
