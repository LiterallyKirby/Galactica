// test_client.c - Advanced Feature Test
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wayland-client.h>
#include <sys/mman.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <time.h>
#include <math.h>

// Fallback for memfd_create
#ifndef MFD_CLOEXEC
#define MFD_CLOEXEC 0x0001U
#endif

#ifndef __NR_memfd_create
#ifdef __x86_64__
#define __NR_memfd_create 319
#elif defined(__i386__)
#define __NR_memfd_create 356
#elif defined(__arm__)
#define __NR_memfd_create 385
#elif defined(__aarch64__)
#define __NR_memfd_create 279
#endif
#endif

static int my_memfd_create(const char *name, unsigned int flags) {
#ifdef __NR_memfd_create
    return syscall(__NR_memfd_create, name, flags);
#else
    errno = ENOSYS;
    return -1;
#endif
}

static int create_anonymous_file(off_t size) {
    int fd = my_memfd_create("galium-test", MFD_CLOEXEC);
    if (fd >= 0) {
        if (ftruncate(fd, size) == 0) {
            return fd;
        }
        close(fd);
    }
    
    char name[] = "/tmp/galium-XXXXXX";
    fd = mkstemp(name);
    if (fd < 0) {
        return -1;
    }
    
    unlink(name);
    
    if (ftruncate(fd, size) < 0) {
        close(fd);
        return -1;
    }
    
    return fd;
}

//==============================================================================
// GLOBALS
//==============================================================================

struct wl_compositor *compositor = NULL;
struct wl_shm *shm = NULL;

//==============================================================================
// SURFACE STRUCTURE
//==============================================================================

struct test_surface {
    struct wl_surface *surface;
    struct wl_buffer *buffer;
    void *shm_data;
    size_t shm_size;
    int width;
    int height;
    int x;
    int y;
};

//==============================================================================
// BUFFER CREATION
//==============================================================================

static struct wl_buffer* create_buffer(int width, int height, void **data_out, size_t *size_out) {
    int stride = width * 4;
    int size = stride * height;
    
    int fd = create_anonymous_file(size);
    if (fd < 0) {
        perror("create_anonymous_file");
        return NULL;
    }
    
    void *data = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (data == MAP_FAILED) {
        perror("mmap");
        close(fd);
        return NULL;
    }
    
    struct wl_shm_pool *pool = wl_shm_create_pool(shm, fd, size);
    struct wl_buffer *buffer = wl_shm_pool_create_buffer(pool, 0,
                                                          width, height,
                                                          stride,
                                                          WL_SHM_FORMAT_ARGB8888);
    wl_shm_pool_destroy(pool);
    close(fd);
    
    *data_out = data;
    *size_out = size;
    
    return buffer;
}

//==============================================================================
// DRAWING FUNCTIONS
//==============================================================================

static void draw_gradient(uint32_t *pixels, int width, int height) {
    for (int y = 0; y < height; y++) {
        for (int x = 0; x < width; x++) {
            uint8_t r = (x * 255) / width;
            uint8_t g = (y * 255) / height;
            uint8_t b = 128;
            pixels[y * width + x] = (0xFF << 24) | (r << 16) | (g << 8) | b;
        }
    }
}

static void draw_solid_color(uint32_t *pixels, int width, int height, uint32_t color) {
    for (int i = 0; i < width * height; i++) {
        pixels[i] = color;
    }
}

static void draw_checkerboard(uint32_t *pixels, int width, int height, int square_size) {
    for (int y = 0; y < height; y++) {
        for (int x = 0; x < width; x++) {
            int check = ((x / square_size) + (y / square_size)) % 2;
            uint32_t color = check ? 0xFFFFFFFF : 0xFF000000;
            pixels[y * width + x] = color;
        }
    }
}

static void draw_circle(uint32_t *pixels, int width, int height, 
                       int cx, int cy, int radius, uint32_t color) {
    for (int y = 0; y < height; y++) {
        for (int x = 0; x < width; x++) {
            int dx = x - cx;
            int dy = y - cy;
            if (dx * dx + dy * dy < radius * radius) {
                pixels[y * width + x] = color;
            }
        }
    }
}

static void draw_border(uint32_t *pixels, int width, int height, 
                       int border_width, uint32_t color) {
    // Top and bottom
    for (int y = 0; y < border_width; y++) {
        for (int x = 0; x < width; x++) {
            pixels[y * width + x] = color;
            pixels[(height - 1 - y) * width + x] = color;
        }
    }
    
    // Left and right
    for (int y = 0; y < height; y++) {
        for (int x = 0; x < border_width; x++) {
            pixels[y * width + x] = color;
            pixels[y * width + (width - 1 - x)] = color;
        }
    }
}

static void draw_animated_wave(uint32_t *pixels, int width, int height, float time) {
    for (int y = 0; y < height; y++) {
        for (int x = 0; x < width; x++) {
            float wave = sin(x * 0.05 + time) * 0.5 + 0.5;
            uint8_t intensity = (uint8_t)(wave * 255);
            pixels[y * width + x] = (0xFF << 24) | (intensity << 16) | (0 << 8) | intensity;
        }
    }
}

static void draw_text_pattern(uint32_t *pixels, int width, int height, const char *text) {
    // Simple text rendering using a pattern
    uint32_t bg_color = 0xFF1E1E1E;  // Dark gray
    uint32_t fg_color = 0xFF00FF00;  // Green
    
    // Fill background
    draw_solid_color(pixels, width, height, bg_color);
    
    // Draw simple pattern based on text
    int text_len = strlen(text);
    for (int i = 0; i < text_len && i < 10; i++) {
        int x = (width / 2) + (i - text_len / 2) * 30;
        int y = height / 2;
        draw_circle(pixels, width, height, x, y, 10 + (text[i] % 10), fg_color);
    }
}

//==============================================================================
// SURFACE MANAGEMENT
//==============================================================================

static struct test_surface* create_test_surface(int width, int height) {
    struct test_surface *surf = calloc(1, sizeof(*surf));
    if (!surf) {
        return NULL;
    }
    
    surf->width = width;
    surf->height = height;
    surf->surface = wl_compositor_create_surface(compositor);
    if (!surf->surface) {
        free(surf);
        return NULL;
    }
    
    surf->buffer = create_buffer(width, height, &surf->shm_data, &surf->shm_size);
    if (!surf->buffer) {
        wl_surface_destroy(surf->surface);
        free(surf);
        return NULL;
    }
    
    return surf;
}

static void destroy_test_surface(struct test_surface *surf) {
    if (!surf) return;
    
    if (surf->buffer) {
        wl_buffer_destroy(surf->buffer);
    }
    if (surf->shm_data) {
        munmap(surf->shm_data, surf->shm_size);
    }
    if (surf->surface) {
        wl_surface_destroy(surf->surface);
    }
    free(surf);
}

static void commit_surface(struct test_surface *surf) {
    wl_surface_attach(surf->surface, surf->buffer, 0, 0);
    wl_surface_damage(surf->surface, 0, 0, surf->width, surf->height);
    wl_surface_commit(surf->surface);
}

//==============================================================================
// REGISTRY LISTENER
//==============================================================================

static void registry_global(void *data, struct wl_registry *registry,
                           uint32_t name, const char *interface, uint32_t version) {
    if (strcmp(interface, "wl_compositor") == 0) {
        compositor = wl_registry_bind(registry, name, &wl_compositor_interface, 1);
        printf("✓ Found wl_compositor\n");
    } else if (strcmp(interface, "wl_shm") == 0) {
        shm = wl_registry_bind(registry, name, &wl_shm_interface, 1);
        printf("✓ Found wl_shm\n");
    }
    
    (void)data;
    (void)version;
}

static void registry_global_remove(void *data, struct wl_registry *registry, uint32_t name) {
    (void)data;
    (void)registry;
    (void)name;
}

static const struct wl_registry_listener registry_listener = {
    .global = registry_global,
    .global_remove = registry_global_remove,
};

//==============================================================================
// TEST SCENARIOS
//==============================================================================

static void test_single_gradient(void) {
    printf("\n=== Test 1: Single Gradient Surface ===\n");
    
    struct test_surface *surf = create_test_surface(400, 300);
    if (!surf) {
        fprintf(stderr, "Failed to create surface\n");
        return;
    }
    
    draw_gradient(surf->shm_data, surf->width, surf->height);
    commit_surface(surf);
    
    printf("✓ Created 400x300 gradient surface\n");
    printf("  Press Enter to continue...\n");
    getchar();
    
    destroy_test_surface(surf);
}

static void test_multiple_surfaces(void) {
    printf("\n=== Test 2: Multiple Colored Surfaces ===\n");
    
    struct test_surface *surfaces[4];
    uint32_t colors[] = {
        0xFFFF0000,  // Red
        0xFF00FF00,  // Green
        0xFF0000FF,  // Blue
        0xFFFFFF00,  // Yellow
    };
    
    for (int i = 0; i < 4; i++) {
        surfaces[i] = create_test_surface(200, 150);
        if (!surfaces[i]) {
            fprintf(stderr, "Failed to create surface %d\n", i);
            continue;
        }
        
        draw_solid_color(surfaces[i]->shm_data, surfaces[i]->width, 
                        surfaces[i]->height, colors[i]);
        draw_border(surfaces[i]->shm_data, surfaces[i]->width, 
                   surfaces[i]->height, 5, 0xFF000000);
        
        commit_surface(surfaces[i]);
        
        printf("✓ Created surface %d: 200x150 (color: 0x%08X)\n", i, colors[i]);
    }
    
    printf("  Press Enter to continue...\n");
    getchar();
    
    for (int i = 0; i < 4; i++) {
        destroy_test_surface(surfaces[i]);
    }
}

static void test_checkerboard(void) {
    printf("\n=== Test 3: Checkerboard Pattern ===\n");
    
    struct test_surface *surf = create_test_surface(400, 400);
    if (!surf) {
        fprintf(stderr, "Failed to create surface\n");
        return;
    }
    
    draw_checkerboard(surf->shm_data, surf->width, surf->height, 50);
    commit_surface(surf);
    
    printf("✓ Created 400x400 checkerboard\n");
    printf("  Press Enter to continue...\n");
    getchar();
    
    destroy_test_surface(surf);
}

static void test_circles(void) {
    printf("\n=== Test 4: Overlapping Circles ===\n");
    
    struct test_surface *surf = create_test_surface(500, 500);
    if (!surf) {
        fprintf(stderr, "Failed to create surface\n");
        return;
    }
    
    // Black background
    draw_solid_color(surf->shm_data, surf->width, surf->height, 0xFF000000);
    
    // Draw overlapping circles
    draw_circle(surf->shm_data, surf->width, surf->height, 150, 150, 80, 0xFFFF0000);
    draw_circle(surf->shm_data, surf->width, surf->height, 250, 150, 80, 0xFF00FF00);
    draw_circle(surf->shm_data, surf->width, surf->height, 200, 250, 80, 0xFF0000FF);
    
    commit_surface(surf);
    
    printf("✓ Created 500x500 with overlapping circles\n");
    printf("  Press Enter to continue...\n");
    getchar();
    
    destroy_test_surface(surf);
}

static void test_text_pattern(void) {
    printf("\n=== Test 5: Text Pattern ===\n");
    
    struct test_surface *surf = create_test_surface(600, 200);
    if (!surf) {
        fprintf(stderr, "Failed to create surface\n");
        return;
    }
    
    draw_text_pattern(surf->shm_data, surf->width, surf->height, "GALACTICA");
    commit_surface(surf);
    
    printf("✓ Created 600x200 text pattern\n");
    printf("  Press Enter to continue...\n");
    getchar();
    
    destroy_test_surface(surf);
}

static void test_animation(struct wl_display *display) {
    printf("\n=== Test 6: Animated Wave ===\n");
    printf("  Animating for 5 seconds...\n");
    
    struct test_surface *surf = create_test_surface(400, 300);
    if (!surf) {
        fprintf(stderr, "Failed to create surface\n");
        return;
    }
    
    time_t start = time(NULL);
    int frame = 0;
    
    while (time(NULL) - start < 5) {
        float t = (float)frame * 0.1;
        
        draw_animated_wave(surf->shm_data, surf->width, surf->height, t);
        commit_surface(surf);
        
        wl_display_roundtrip(display);
        
        usleep(33000);  // ~30 FPS
        frame++;
    }
    
    printf("✓ Animated %d frames\n", frame);
    printf("  Press Enter to continue...\n");
    getchar();
    
    destroy_test_surface(surf);
}

static void test_stress(struct wl_display *display) {
    printf("\n=== Test 7: Stress Test (Many Surfaces) ===\n");
    
    #define NUM_STRESS_SURFACES 10
    struct test_surface *surfaces[NUM_STRESS_SURFACES];
    
    for (int i = 0; i < NUM_STRESS_SURFACES; i++) {
        surfaces[i] = create_test_surface(100, 100);
        if (!surfaces[i]) {
            fprintf(stderr, "Failed to create surface %d\n", i);
            continue;
        }
        
        // Each surface gets a unique color
        uint32_t color = 0xFF000000 | 
                        ((i * 25) << 16) | 
                        ((i * 50) << 8) | 
                        (255 - i * 25);
        
        draw_solid_color(surfaces[i]->shm_data, surfaces[i]->width, 
                        surfaces[i]->height, color);
        draw_border(surfaces[i]->shm_data, surfaces[i]->width, 
                   surfaces[i]->height, 2, 0xFFFFFFFF);
        
        commit_surface(surfaces[i]);
        
        wl_display_roundtrip(display);
    }
    
    printf("✓ Created %d surfaces\n", NUM_STRESS_SURFACES);
    printf("  Press Enter to continue...\n");
    getchar();
    
    for (int i = 0; i < NUM_STRESS_SURFACES; i++) {
        destroy_test_surface(surfaces[i]);
    }
}

static void test_large_surface(void) {
    printf("\n=== Test 8: Large Surface ===\n");
    
    struct test_surface *surf = create_test_surface(800, 600);
    if (!surf) {
        fprintf(stderr, "Failed to create large surface\n");
        return;
    }
    
    // Draw gradient
    draw_gradient(surf->shm_data, surf->width, surf->height);
    
    // Add some circles
    draw_circle(surf->shm_data, surf->width, surf->height, 200, 150, 50, 0xFFFF0000);
    draw_circle(surf->shm_data, surf->width, surf->height, 600, 150, 50, 0xFF00FF00);
    draw_circle(surf->shm_data, surf->width, surf->height, 400, 450, 50, 0xFF0000FF);
    
    commit_surface(surf);
    
    printf("✓ Created 800x600 large surface\n");
    printf("  Press Enter to continue...\n");
    getchar();
    
    destroy_test_surface(surf);
}

//==============================================================================
// MAIN
//==============================================================================

int main(void) {
    printf("╔════════════════════════════════════════╗\n");
    printf("║  Galium Compositor Test Suite         ║\n");
    printf("║  Feature Testing & Validation          ║\n");
    printf("╚════════════════════════════════════════╝\n\n");
    
    // Connect to compositor
    printf("Connecting to Wayland compositor...\n");
    struct wl_display *display = wl_display_connect(NULL);
    if (!display) {
        fprintf(stderr, "❌ Failed to connect to Wayland display\n");
        fprintf(stderr, "   Make sure the compositor is running and\n");
        fprintf(stderr, "   WAYLAND_DISPLAY is set correctly.\n");
        return 1;
    }
    printf("✓ Connected to display\n");
    
    // Get globals
    struct wl_registry *registry = wl_display_get_registry(display);
    wl_registry_add_listener(registry, &registry_listener, NULL);
    wl_display_roundtrip(display);
    
    if (!compositor || !shm) {
        fprintf(stderr, "❌ Missing required interfaces\n");
        wl_display_disconnect(display);
        return 1;
    }
    
    printf("\n✓ All required interfaces found\n");
    printf("\nStarting test suite...\n");
    printf("(Press Enter after each test to continue)\n");
    getchar();
    
    // Run tests
    test_single_gradient();
    test_multiple_surfaces();
    test_checkerboard();
    test_circles();
    test_text_pattern();
    test_animation(display);
    test_stress(display);
    test_large_surface();
    
    printf("\n╔════════════════════════════════════════╗\n");
    printf("║  All Tests Complete!                   ║\n");
    printf("╚════════════════════════════════════════╝\n\n");
    printf("Check the frame_*.ppm files to see rendered output.\n");
    printf("You can convert them: convert frame_000.ppm frame_000.png\n\n");
    
    wl_display_disconnect(display);
    
    return 0;
}
