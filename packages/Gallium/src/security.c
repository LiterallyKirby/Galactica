#define _GNU_SOURCE
#include "../include/security.h"
#include <errno.h>
#include <fcntl.h>
#include <grp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

void drop_privileges(void) {
  if (geteuid() != 0) {
    return;
  }

  uid_t uid = getuid();
  gid_t gid = getgid();

  fprintf(stderr, "Dropping privileges from root to uid=%d gid=%d\n", uid, gid);

  if (setgroups(0, NULL) != 0) {
    perror("setgroups failed");
    exit(1);
  }

  if (setgid(gid) != 0) {
    perror("setgid failed");
    exit(1);
  }

  if (setuid(uid) != 0) {
    perror("setuid failed");
    exit(1);
  }

  if (setuid(0) == 0) {
    fprintf(stderr, "ERROR: Failed to drop privileges properly!\n");
    exit(1);
  }

  fprintf(stderr, "✓ Privileges dropped successfully\n");
}

bool lock_memory(void) {
  if (mlockall(MCL_CURRENT | MCL_FUTURE) != 0) {
    perror("mlockall");
    return false;
  }

  fprintf(stderr, "✓ Memory locked (no swapping)\n");
  return true;
}

int secure_random_bytes(void *buf, size_t len) {
  int fd = open("/dev/urandom", O_RDONLY | O_CLOEXEC);
  if (fd < 0) {
    perror("open /dev/urandom");
    return -1;
  }

  size_t total = 0;
  while (total < len) {
    ssize_t n = read(fd, (uint8_t *)buf + total, len - total);
    if (n <= 0) {
      if (errno == EINTR)
        continue;
      close(fd);
      return -1;
    }
    total += n;
  }

  close(fd);
  return 0;
}

void secure_zero(void *ptr, size_t len) {
  if (!ptr)
    return;

#ifdef explicit_bzero
  explicit_bzero(ptr, len);
#else
  volatile uint8_t *p = ptr;
  while (len--) {
    *p++ = 0;
  }
#endif
}

void *secure_malloc(size_t size) {
  if (size == 0 || size > SIZE_MAX / 2) {
    return NULL;
  }

  void *ptr = calloc(1, size);
  if (!ptr) {
    return NULL;
  }

  if (mlock(ptr, size) != 0) {
    perror("mlock");
    free(ptr);
    return NULL;
  }

  return ptr;
}

void secure_free(void *ptr, size_t size) {
  if (!ptr)
    return;

  secure_zero(ptr, size);
  munlock(ptr, size);
  free(ptr);
}

bool validate_client_credentials(struct wl_client *client,
                                 struct client_security *sec) {
  if (!client || !sec) {
    return false;
  }

  wl_client_get_credentials(client, &sec->pid, &sec->uid, &sec->gid);

  if (sec->pid <= 0) {
    fprintf(stderr, "Invalid client PID: %d\n", sec->pid);
    return false;
  }

  sec->is_vm = is_vm_process(sec->pid);
  sec->surface_count = 0;

  fprintf(stderr, "Client validated: PID=%d UID=%d GID=%d VM=%d\n", sec->pid,
          sec->uid, sec->gid, sec->is_vm);

  return true;
}

bool is_vm_process(pid_t pid) {
  char path[256];
  char cmdline[1024];

  snprintf(path, sizeof(path), "/proc/%d/cmdline", pid);

  int fd = open(path, O_RDONLY);
  if (fd < 0) {
    return false;
  }

  ssize_t n = read(fd, cmdline, sizeof(cmdline) - 1);
  close(fd);

  if (n <= 0) {
    return false;
  }

  cmdline[n] = '\0';

  return (strstr(cmdline, "qemu-system") != NULL ||
          strstr(cmdline, "xen") != NULL || strstr(cmdline, "xl") != NULL);
}

bool validate_geometry(int32_t x, int32_t y, uint32_t width, uint32_t height) {
  if ((int32_t)width < 0 || (int32_t)height < 0) {
    fprintf(stderr, "Invalid dimensions: %ux%u\n", width, height);
    return false;
  }

  if (width > INT32_MAX - (uint32_t)x || height > INT32_MAX - (uint32_t)y) {
    fprintf(stderr, "Integer overflow in geometry\n");
    return false;
  }

  if (width > MAX_BUFFER_WIDTH || height > MAX_BUFFER_HEIGHT) {
    fprintf(stderr, "Dimensions too large: %ux%u (max %ux%u)\n", width, height,
            MAX_BUFFER_WIDTH, MAX_BUFFER_HEIGHT);
    return false;
  }

  if (width == 0 || height == 0) {
    fprintf(stderr, "Zero dimensions not allowed\n");
    return false;
  }

  return true;
}

bool validate_buffer_size(uint32_t width, uint32_t height) {
  if (width > MAX_BUFFER_WIDTH || height > MAX_BUFFER_HEIGHT) {
    return false;
  }

  uint64_t pixels = (uint64_t)width * height;
  uint64_t bytes = pixels * 4;

  if (bytes > SIZE_MAX) {
    fprintf(stderr, "Buffer size overflow\n");
    return false;
  }

  return true;
}

bool check_surface_limit(struct client_security *client) {
  if (!client) {
    return false;
  }

  if (client->surface_count >= MAX_SURFACES_PER_CLIENT) {
    fprintf(stderr, "Client %d exceeded surface limit (%u/%u)\n", client->pid,
            client->surface_count, MAX_SURFACES_PER_CLIENT);
    return false;
  }

  return true;
}

struct security_context *security_context_create(void) {
  struct security_context *ctx = calloc(1, sizeof(*ctx));
  if (!ctx) {
    return NULL;
  }

  if (secure_random_bytes(&ctx->session_id, sizeof(ctx->session_id)) != 0) {
    free(ctx);
    return NULL;
  }

  wl_list_init(&ctx->clients);
  ctx->locked = false;

  fprintf(stderr, "✓ Security context created (session: 0x%016lx)\n",
          ctx->session_id);

  return ctx;
}

void security_context_destroy(struct security_context *ctx) {
  if (!ctx) {
    return;
  }

  struct client_security *client, *tmp;
  wl_list_for_each_safe(client, tmp, &ctx->clients, link) {
    wl_list_remove(&client->link);
    secure_free(client, sizeof(*client));
  }

  secure_zero(ctx, sizeof(*ctx));
  free(ctx);

  fprintf(stderr, "✓ Security context destroyed\n");
}
