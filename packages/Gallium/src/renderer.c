#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pixman.h>
#include "../include/compositor.h"

void renderer_repaint_output(struct galium_output *output,
                              struct wl_list *surfaces) {
    fprintf(stderr, "Software rendering frame...\n");
    
    // Clear framebuffer to background color (dark gray)
    pixman_color_t bg_color = {
        .red = 0x2000,
        .green = 0x2000,
        .blue = 0x2000,
        .alpha = 0xffff
    };
    
    pixman_image_t *bg = pixman_image_create_solid_fill(&bg_color);
    
    pixman_image_composite32(
        PIXMAN_OP_SRC,
        bg,
        NULL,
        output->framebuffer,
        0, 0,
        0, 0,
        0, 0,
        output->width,
        output->height
    );
    
    pixman_image_unref(bg);
    
    // Count surfaces for reporting
    int surface_count = 0;
    
    // Render each surface
    struct galium_surface *surface;
    wl_list_for_each(surface, surfaces, link) {
        if (!surface->image) {
            continue;
        }
        
        fprintf(stderr, "  Rendering surface %p at (%d,%d) size %dx%d\n",
                (void*)surface, surface->x, surface->y,
                surface->width, surface->height);
        
        // Composite surface onto framebuffer
        pixman_image_composite32(
            PIXMAN_OP_OVER,
            surface->image,
            NULL,
            output->framebuffer,
            0, 0,
            0, 0,
            surface->x,
            surface->y,
            surface->width,
            surface->height
        );
        
        surface_count++;
    }
    
    fprintf(stderr, "✓ Frame rendered (%d surfaces)\n", surface_count);
}
