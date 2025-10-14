#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wayland-server-core.h>
#include <wayland-server-protocol.h>
#include "../include/compositor.h"
#include "../include/security.h"

static void surface_destroy(struct wl_client *client __attribute__((unused)),
                            struct wl_resource *resource) {
    wl_resource_destroy(resource);
}

static void surface_attach(struct wl_client *client __attribute__((unused)),
                           struct wl_resource *resource,
                           struct wl_resource *buffer_resource,
                           int32_t x, int32_t y) {
    struct galium_surface *surface = wl_resource_get_user_data(resource);
    
    fprintf(stderr, "surface_attach: buffer=%p x=%d y=%d\n", 
            (void*)buffer_resource, x, y);
    
    if (!surface->client_sec) {
        fprintf(stderr, "Surface has no client security context!\n");
        return;
    }
    
    surface->buffer_resource = buffer_resource;
    
    if (buffer_resource) {
        if (surface->image) {
            pixman_image_unref(surface->image);
        }
        
        surface->image = shm_buffer_get_image(buffer_resource);
        if (surface->image) {
            surface->width = pixman_image_get_width(surface->image);
            surface->height = pixman_image_get_height(surface->image);
            fprintf(stderr, "  Got image: %dx%d\n", surface->width, surface->height);
        }
    }
}

static void surface_damage(struct wl_client *client __attribute__((unused)),
                          struct wl_resource *resource,
                          int32_t x, int32_t y,
                          int32_t width, int32_t height) {
    struct galium_surface *surface = wl_resource_get_user_data(resource);
    
    if (!validate_geometry(x, y, width, height)) {
        fprintf(stderr, "Invalid damage geometry rejected\n");
        return;
    }
    
    fprintf(stderr, "surface_damage: x=%d y=%d w=%d h=%d\n", x, y, width, height);
    
    pixman_region32_union_rect(&surface->damage, &surface->damage,
                               x, y, width, height);
}

static void surface_frame(struct wl_client *client,
                         struct wl_resource *resource __attribute__((unused)),
                         uint32_t callback) {
    struct wl_resource *callback_resource;
    
    callback_resource = wl_resource_create(client, &wl_callback_interface, 1, callback);
    (void)callback_resource;
    
    fprintf(stderr, "surface_frame: callback=%u\n", callback);
}

static void surface_commit(struct wl_client *client __attribute__((unused)),
                          struct wl_resource *resource) {
    struct galium_surface *surface = wl_resource_get_user_data(resource);
    
    fprintf(stderr, "surface_commit: surface=%p\n", (void*)surface);
    
    struct galium_output *output;
    wl_list_for_each(output, &surface->compositor->outputs, link) {
        output_repaint(output);
    }
}

static const struct wl_surface_interface surface_implementation = {
    .destroy = surface_destroy,
    .attach = surface_attach,
    .damage = surface_damage,
    .frame = surface_frame,
    .commit = surface_commit,
};

static void surface_resource_destroy(struct wl_resource *resource) {
    struct galium_surface *surface = wl_resource_get_user_data(resource);
    
    fprintf(stderr, "Destroying surface %p\n", (void*)surface);
    
    wl_list_remove(&surface->link);
    pixman_region32_fini(&surface->damage);
    
    if (surface->image) {
        pixman_image_unref(surface->image);
    }
    
    free(surface);
}

static void compositor_create_surface(struct wl_client *client,
                                      struct wl_resource *resource,
                                      uint32_t id) {
    struct galium_compositor *compositor = wl_resource_get_user_data(resource);
    
    fprintf(stderr, "Creating surface id=%u\n", id);
    
    struct galium_surface *surface = calloc(1, sizeof(*surface));
    if (!surface) {
        wl_client_post_no_memory(client);
        return;
    }
    
    surface->compositor = compositor;
    
    surface->resource = wl_resource_create(client, &wl_surface_interface,
                                           wl_resource_get_version(resource), id);
    if (!surface->resource) {
        free(surface);
        wl_client_post_no_memory(client);
        return;
    }
    
    wl_resource_set_implementation(surface->resource, &surface_implementation,
                                    surface, surface_resource_destroy);
    
    pixman_region32_init(&surface->damage);
    
    surface->client_sec = calloc(1, sizeof(*surface->client_sec));
    if (surface->client_sec) {
        validate_client_credentials(client, surface->client_sec);
        wl_list_insert(&compositor->sec_ctx->clients, &surface->client_sec->link);
    }
    
    wl_list_insert(&compositor->surfaces, &surface->link);
    
    fprintf(stderr, "✓ Surface created: %p\n", (void*)surface);
}

static void compositor_create_region(struct wl_client *client __attribute__((unused)),
                                     struct wl_resource *resource __attribute__((unused)),
                                     uint32_t id) {
    fprintf(stderr, "create_region: id=%u (stub)\n", id);
}

static const struct wl_compositor_interface compositor_implementation = {
    .create_surface = compositor_create_surface,
    .create_region = compositor_create_region,
};

static void compositor_bind(struct wl_client *client, void *data,
                           uint32_t version, uint32_t id) {
    struct galium_compositor *compositor = data;
    
    fprintf(stderr, "Client binding to wl_compositor version=%u id=%u\n", version, id);
    
    struct wl_resource *resource = wl_resource_create(client,
                                                       &wl_compositor_interface,
                                                       version, id);
    if (!resource) {
        wl_client_post_no_memory(client);
        return;
    }
    
    wl_resource_set_implementation(resource, &compositor_implementation,
                                    compositor, NULL);
}

bool compositor_init_globals(struct galium_compositor *compositor) {
    wl_list_init(&compositor->surfaces);
    
    compositor->compositor_global = wl_global_create(compositor->display,
                                                      &wl_compositor_interface,
                                                      4, compositor,
                                                      compositor_bind);
    if (!compositor->compositor_global) {
        fprintf(stderr, "Failed to create wl_compositor global\n");
        return false;
    }
    
    fprintf(stderr, "✓ wl_compositor global created\n");
    
    return true;
}

void compositor_destroy_globals(struct galium_compositor *compositor) {
    if (compositor->compositor_global) {
        wl_global_destroy(compositor->compositor_global);
    }
    
    struct galium_surface *surface, *tmp;
    wl_list_for_each_safe(surface, tmp, &compositor->surfaces, link) {
        wl_resource_destroy(surface->resource);
    }
}
