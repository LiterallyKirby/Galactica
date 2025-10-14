#define _GNU_SOURCE
#define _POSIX_C_SOURCE 200809L
#include "../include/compositor.h"
#include <pixman.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
#include <wayland-server-core.h>
#include <wayland-server-protocol.h>

// Forward declaration - wl_shm_pool is opaque
struct wl_shm_pool;

struct galium_shm_buffer {
  struct wl_resource *resource;
  struct wl_shm_buffer *shm_buffer;
  int32_t width;
  int32_t height;
};

static void buffer_destroy(struct wl_client *client __attribute__((unused)),
                           struct wl_resource *resource) {
  wl_resource_destroy(resource);
}

static const struct wl_buffer_interface buffer_implementation = {
    .destroy = buffer_destroy,
};

static void buffer_resource_destroy(struct wl_resource *resource) {
  struct galium_shm_buffer *buffer = wl_resource_get_user_data(resource);
  free(buffer);
}

static void shm_pool_create_buffer(struct wl_client *client,
                                   struct wl_resource *resource, uint32_t id,
                                   int32_t offset, int32_t width,
                                   int32_t height, int32_t stride,
                                   uint32_t format) {
  struct wl_shm_pool *pool = wl_resource_get_user_data(resource);

  fprintf(stderr, "Creating buffer: %dx%d offset=%d stride=%d format=%u\n",
          width, height, offset, stride, format);

  if (!validate_buffer_size(width, height)) {
    wl_resource_post_error(resource, WL_SHM_ERROR_INVALID_STRIDE,
                           "buffer dimensions too large");
    return;
  }

  if (format != WL_SHM_FORMAT_ARGB8888 && format != WL_SHM_FORMAT_XRGB8888) {
    wl_resource_post_error(resource, WL_SHM_ERROR_INVALID_FORMAT,
                           "unsupported pixel format");
    return;
  }

  struct galium_shm_buffer *buffer = calloc(1, sizeof(*buffer));
  if (!buffer) {
    wl_client_post_no_memory(client);
    return;
  }

  buffer->width = width;
  buffer->height = height;

  buffer->resource = wl_resource_create(client, &wl_buffer_interface, 1, id);
  if (!buffer->resource) {
    free(buffer);
    wl_client_post_no_memory(client);
    return;
  }

  wl_resource_set_implementation(buffer->resource, &buffer_implementation,
                                 buffer, buffer_resource_destroy);

  buffer->shm_buffer = wl_shm_buffer_get(buffer->resource);

  fprintf(stderr, "✓ Buffer created: %dx%d\n", width, height);

  (void)pool;
  (void)offset;
  (void)stride;
}

static void shm_pool_destroy(struct wl_client *client __attribute__((unused)),
                             struct wl_resource *resource) {
  wl_resource_destroy(resource);
}

static void shm_pool_resize(struct wl_client *client __attribute__((unused)),
                            struct wl_resource *resource
                            __attribute__((unused)),
                            int32_t size) {
  fprintf(stderr, "shm_pool_resize: size=%d (stub)\n", size);
}

static const struct wl_shm_pool_interface shm_pool_implementation = {
    .create_buffer = shm_pool_create_buffer,
    .destroy = shm_pool_destroy,
    .resize = shm_pool_resize,
};

static void shm_pool_resource_destroy(struct wl_resource *resource) {
  struct {
    void *data;
    int32_t size;
    int fd;
  } *pool = wl_resource_get_user_data(resource);

  if (pool) {
    if (pool->data) {
      munmap(pool->data, pool->size);
    }
    if (pool->fd >= 0) {
      close(pool->fd);
    }
    free(pool);
  }
}
static void shm_create_pool(struct wl_client *client,
                            struct wl_resource *resource, uint32_t id,
                            int32_t fd, int32_t size) {
  fprintf(stderr, "Creating shm pool: fd=%d size=%d\n", fd, size);

  // Map the file descriptor
  void *data = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
  if (data == MAP_FAILED) {
    wl_resource_post_error(resource, WL_SHM_ERROR_INVALID_FD,
                           "failed to mmap shm pool");
    close(fd);
    return;
  }

  // Create the pool resource
  struct wl_resource *pool_resource = wl_resource_create(
      client, &wl_shm_pool_interface, wl_resource_get_version(resource), id);
  if (!pool_resource) {
    munmap(data, size);
    close(fd);
    wl_client_post_no_memory(client);
    return;
  }

  // For our simple implementation, we just store the data pointer
  // In production, you'd use wl_shm_pool but we'll use our own struct
  struct {
    void *data;
    int32_t size;
    int fd;
  } *pool_data = malloc(sizeof(*pool_data));

  if (!pool_data) {
    munmap(data, size);
    close(fd);
    wl_resource_destroy(pool_resource);
    wl_client_post_no_memory(client);
    return;
  }

  pool_data->data = data;
  pool_data->size = size;
  pool_data->fd = fd;

  wl_resource_set_implementation(pool_resource, &shm_pool_implementation,
                                 pool_data, shm_pool_resource_destroy);

  fprintf(stderr, "✓ SHM pool created\n");
}

static const struct wl_shm_interface shm_implementation = {
    .create_pool = shm_create_pool,
};

static void shm_bind(struct wl_client *client, void *data, uint32_t version,
                     uint32_t id) {
  fprintf(stderr, "Client binding to wl_shm version=%u id=%u\n", version, id);

  struct wl_resource *resource =
      wl_resource_create(client, &wl_shm_interface, version, id);
  if (!resource) {
    wl_client_post_no_memory(client);
    return;
  }

  wl_resource_set_implementation(resource, &shm_implementation, data, NULL);

  wl_shm_send_format(resource, WL_SHM_FORMAT_ARGB8888);
  wl_shm_send_format(resource, WL_SHM_FORMAT_XRGB8888);

  fprintf(stderr, "✓ wl_shm bound\n");
}

bool shm_init(struct galium_compositor *compositor) {
  compositor->shm_global = wl_global_create(
      compositor->display, &wl_shm_interface, 1, compositor, shm_bind);
  if (!compositor->shm_global) {
    fprintf(stderr, "Failed to create wl_shm global\n");
    return false;
  }

  fprintf(stderr, "✓ wl_shm global created\n");
  return true;
}

void shm_destroy(struct galium_compositor *compositor) {
  if (compositor->shm_global) {
    wl_global_destroy(compositor->shm_global);
  }
}

pixman_image_t *shm_buffer_get_image(struct wl_resource *buffer_resource) {
  struct wl_shm_buffer *shm_buffer = wl_shm_buffer_get(buffer_resource);
  if (!shm_buffer) {
    return NULL;
  }

  wl_shm_buffer_begin_access(shm_buffer);

  void *data = wl_shm_buffer_get_data(shm_buffer);
  int32_t width = wl_shm_buffer_get_width(shm_buffer);
  int32_t height = wl_shm_buffer_get_height(shm_buffer);
  int32_t stride = wl_shm_buffer_get_stride(shm_buffer);
  uint32_t format = wl_shm_buffer_get_format(shm_buffer);

  pixman_format_code_t pixman_format;
  switch (format) {
  case WL_SHM_FORMAT_ARGB8888:
    pixman_format = PIXMAN_a8r8g8b8;
    break;
  case WL_SHM_FORMAT_XRGB8888:
    pixman_format = PIXMAN_x8r8g8b8;
    break;
  default:
    wl_shm_buffer_end_access(shm_buffer);
    return NULL;
  }

  pixman_image_t *image =
      pixman_image_create_bits(pixman_format, width, height, data, stride);

  wl_shm_buffer_end_access(shm_buffer);

  return image;
}
