#define _GNU_SOURCE
#include "../include/compositor.h"
#include <fcntl.h>
#include <pixman.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <wayland-server-protocol.h>

struct galium_output *output_create(struct galium_compositor *compositor,
                                    int32_t width, int32_t height) {
  fprintf(stderr, "Creating output: %dx%d\n", width, height);

  struct galium_output *output = calloc(1, sizeof(*output));
  if (!output) {
    return NULL;
  }

  output->compositor = compositor;
  output->width = width;
  output->height = height;
  output->x = 0;
  output->y = 0;

  // Allocate framebuffer (ARGB format)
  size_t fb_size = width * height * sizeof(uint32_t);
  output->fb_data = malloc(fb_size);
  if (!output->fb_data) {
    free(output);
    return NULL;
  }

  // Clear to black
  memset(output->fb_data, 0, fb_size);

  // Create pixman image from framebuffer
  output->framebuffer =
      pixman_image_create_bits(PIXMAN_a8r8g8b8, width, height, output->fb_data,
                               width * sizeof(uint32_t));

  if (!output->framebuffer) {
    free(output->fb_data);
    free(output);
    return NULL;
  }

  // Initialize damage region
  pixman_region32_init(&output->damage);

  // Add to output list
  wl_list_insert(&compositor->outputs, &output->link);

  fprintf(stderr, "✓ Output created: %dx%d @ %p\n", width, height,
          (void *)output);
  fprintf(stderr, "✓ Framebuffer: %zu bytes\n", fb_size);

  return output;
}

void output_destroy(struct galium_output *output) {
  if (!output)
    return;

  wl_list_remove(&output->link);
  pixman_region32_fini(&output->damage);

  if (output->framebuffer) {
    pixman_image_unref(output->framebuffer);
  }

  free(output->fb_data);
  free(output);
}

void output_save_framebuffer(struct galium_output *output,
                             const char *filename) {
  fprintf(stderr, "Saving framebuffer to %s...\n", filename);

  int fd = open(filename, O_WRONLY | O_CREAT | O_TRUNC, 0644);
  if (fd < 0) {
    perror("open");
    return;
  }

  // PPM header
  char header[256];
  int header_len = snprintf(header, sizeof(header), "P6\n%d %d\n255\n",
                            output->width, output->height);
  if (write(fd, header, header_len) < 0) {
    perror("write header");
    close(fd);
    return;
  }

  // Write pixels (convert ARGB to RGB)
  for (int y = 0; y < output->height; y++) {
    for (int x = 0; x < output->width; x++) {
      uint32_t pixel = output->fb_data[y * output->width + x];
      uint8_t rgb[3] = {
          (pixel >> 16) & 0xFF, // R
          (pixel >> 8) & 0xFF,  // G
          pixel & 0xFF          // B
      };
      if (write(fd, rgb, 3) < 0) {
        perror("write pixel");
        close(fd);
        return;
      }
    }
  }

  close(fd);
  fprintf(stderr, "✓ Saved to %s\n", filename);
}

// src/output.c - Update the output_repaint function

void output_repaint(struct galium_output *output) {
  static int frame_count = 0;

  fprintf(stderr, "\n═══════════════════════════════════════\n");
  fprintf(stderr, "REPAINT #%d - Output %dx%d\n", frame_count, output->width,
          output->height);
  fprintf(stderr, "═══════════════════════════════════════\n");

  // Count surfaces
  int surface_count = 0;
  struct galium_surface *s;
  wl_list_for_each(s, &output->compositor->surfaces, link) {
    surface_count++;
    fprintf(stderr, "  Surface %p: %dx%d, has_image=%d\n", (void *)s, s->width,
            s->height, (s->image != NULL));
  }
  fprintf(stderr, "  Total surfaces: %d\n\n", surface_count);

  // Render all surfaces to this output
  renderer_repaint_output(output, &output->compositor->surfaces);

  // ALWAYS save frames during testing
  char filename[256];
  snprintf(filename, sizeof(filename), "frame_%03d.ppm", frame_count);
  output_save_framebuffer(output, filename);
  frame_count++;

  fprintf(stderr, "═══════════════════════════════════════\n\n");

  // Clear damage
  pixman_region32_clear(&output->damage);
}
