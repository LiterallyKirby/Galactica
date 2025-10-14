#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <wayland-server-core.h>
#include "../include/security.h"
#include "../include/compositor.h"

static struct galium_compositor *g_compositor = NULL;

static void signal_handler(int signum) {
    if (g_compositor) {
        fprintf(stderr, "\nReceived signal %d, shutting down...\n", signum);
        g_compositor->running = false;
        wl_display_terminate(g_compositor->display);
    }
}

static void setup_signal_handlers(void) {
    struct sigaction sa = {0};
    sa.sa_handler = signal_handler;
    sigemptyset(&sa.sa_mask);
    
    sigaction(SIGINT, &sa, NULL);
    sigaction(SIGTERM, &sa, NULL);
}

int main(void) {
    fprintf(stderr, "=================================\n");
    fprintf(stderr, "  Galium-Vanilla Compositor\n");
    fprintf(stderr, "  Software Rendering Edition\n");
    fprintf(stderr, "=================================\n\n");
    
    // 1. SECURITY: Drop privileges if running as root
    if (geteuid() == 0) {
        fprintf(stderr, "⚠️  Running as root, dropping privileges...\n");
        drop_privileges();
    }
    
    // 2. SECURITY: Lock memory to prevent swapping
    if (!lock_memory()) {
        fprintf(stderr, "⚠️  Warning: Could not lock memory\n");
    }
    
    // 3. Create security context
    struct security_context *sec_ctx = security_context_create();
    if (!sec_ctx) {
        fprintf(stderr, "❌ Failed to create security context\n");
        return 1;
    }
    
    // 4. Create Wayland display
    struct wl_display *display = wl_display_create();
    if (!display) {
        fprintf(stderr, "❌ Failed to create Wayland display\n");
        security_context_destroy(sec_ctx);
        return 1;
    }
    
    // 5. Add Wayland socket
    const char *socket = wl_display_add_socket_auto(display);
    if (!socket) {
        fprintf(stderr, "❌ Failed to create Wayland socket\n");
        wl_display_destroy(display);
        security_context_destroy(sec_ctx);
        return 1;
    }
    
    fprintf(stderr, "✓ Wayland socket: %s\n", socket);
    fprintf(stderr, "✓ Set WAYLAND_DISPLAY=%s to connect\n\n", socket);
    
    // 6. Set up compositor
    struct galium_compositor compositor = {0};
    compositor.display = display;
    compositor.event_loop = wl_display_get_event_loop(display);
    compositor.sec_ctx = sec_ctx;
    compositor.running = true;
    
    wl_list_init(&compositor.outputs);
    
    g_compositor = &compositor;
    
    // 7. Initialize compositor globals
    if (!compositor_init_globals(&compositor)) {
        fprintf(stderr, "❌ Failed to initialize compositor\n");
        wl_display_destroy(display);
        security_context_destroy(sec_ctx);
        return 1;
    }
    
    // 8. Initialize SHM (shared memory support)
    if (!shm_init(&compositor)) {
        fprintf(stderr, "❌ Failed to initialize SHM\n");
        compositor_destroy_globals(&compositor);
        wl_display_destroy(display);
        security_context_destroy(sec_ctx);
        return 1;
    }
    
    // 9. Create a virtual output (800x600 for testing)
    struct galium_output *output = output_create(&compositor, 800, 600);
    if (!output) {
        fprintf(stderr, "❌ Failed to create output\n");
        shm_destroy(&compositor);
        compositor_destroy_globals(&compositor);
        wl_display_destroy(display);
        security_context_destroy(sec_ctx);
        return 1;
    }
    
    // 10. Set up signal handlers
    setup_signal_handlers();
    
    fprintf(stderr, "\n🚀 Compositor running...\n");
    fprintf(stderr, "   WAYLAND_DISPLAY=%s\n", socket);
    fprintf(stderr, "   Resolution: %dx%d (software rendered)\n",
            output->width, output->height);
    fprintf(stderr, "   Press Ctrl+C to stop\n\n");
    
    // 11. Run the compositor
    wl_display_run(display);
    
    // 12. Cleanup
    fprintf(stderr, "\n🛑 Shutting down...\n");
    output_destroy(output);
    shm_destroy(&compositor);
    compositor_destroy_globals(&compositor);
    wl_display_destroy(display);
    security_context_destroy(sec_ctx);
    
    fprintf(stderr, "✓ Cleanup complete\n");
    return 0;
}
