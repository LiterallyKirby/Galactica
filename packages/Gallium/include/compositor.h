#ifndef GALIUM_COMPOSITOR_H
#define GALIUM_COMPOSITOR_H

#include <wayland-server-core.h>
#include <pixman.h>
#include "security.h"

struct galium_output;
struct galium_surface;

struct galium_compositor {
    struct wl_display *display;
    struct wl_event_loop *event_loop;
    struct security_context *sec_ctx;
    
    // Wayland globals
    struct wl_global *compositor_global;
    struct wl_global *subcompositor_global;
    struct wl_global *shm_global;
    
    // Output list (monitors)
    struct wl_list outputs;
    
    // Surface list (windows)
    struct wl_list surfaces;
    
    bool running;
};

struct galium_output {
    struct galium_compositor *compositor;
    struct wl_list link;
    
    // Output properties
    int32_t x, y;
    int32_t width, height;
    
    // Software rendering
    pixman_image_t *framebuffer;
    uint32_t *fb_data;
    
    // Damage tracking
    pixman_region32_t damage;
    
    // Wayland protocol
    struct wl_global *global;
};

struct galium_surface {
    struct galium_compositor *compositor;
    struct wl_resource *resource;
    struct wl_list link;
    
    // Surface state
    int32_t x, y;
    int32_t width, height;
    
    // Buffer
    struct wl_resource *buffer_resource;
    pixman_image_t *image;
    
    // Damage
    pixman_region32_t damage;
    
    // Security
    struct client_security *client_sec;
};

// Compositor lifecycle
bool compositor_init_globals(struct galium_compositor *compositor);
void compositor_destroy_globals(struct galium_compositor *compositor);

// Output management
struct galium_output* output_create(struct galium_compositor *compositor,
                                     int32_t width, int32_t height);
void output_destroy(struct galium_output *output);
void output_repaint(struct galium_output *output);
void output_save_framebuffer(struct galium_output *output, const char *filename);

// Renderer
void renderer_repaint_output(struct galium_output *output,
                              struct wl_list *surfaces);

// SHM support
bool shm_init(struct galium_compositor *compositor);
void shm_destroy(struct galium_compositor *compositor);
pixman_image_t* shm_buffer_get_image(struct wl_resource *buffer_resource);

#endif
