# Makefile
CC = gcc
CFLAGS = -Wall -Wextra -D_GNU_SOURCE -lm
LDFLAGS = -lwayland-client

test_client: test_client.c
	$(CC) -o test_client test_client.c $(CFLAGS) $(LDFLAGS)

clean:
	rm -f test_client frame_*.ppm

.PHONY: clean
