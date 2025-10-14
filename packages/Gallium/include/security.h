#ifndef GALIUM_SECURITY_H
#define GALIUM_SECURITY_H

#include <stdint.h>
#include <stdbool.h>
#include <sys/types.h>
#include <wayland-server-core.h>

#define MAX_SURFACES_PER_CLIENT 100
#define MAX_BUFFER_WIDTH 3840
#define MAX_BUFFER_HEIGHT 2160

struct security_context {
    uint64_t session_id;
    struct wl_list clients;
    bool locked;
};

struct client_security {
    pid_t pid;
    uid_t uid;
    gid_t gid;
    bool is_vm;
    uint64_t vm_id;
    uint32_t surface_count;
    struct wl_list link;
};

// Initialization
struct security_context* security_context_create(void);
void security_context_destroy(struct security_context *ctx);

// Privilege management
void drop_privileges(void);
bool lock_memory(void);

// Random number generation
int secure_random_bytes(void *buf, size_t len);

// Memory operations
void* secure_malloc(size_t size);
void secure_free(void *ptr, size_t size);
void secure_zero(void *ptr, size_t len);

// Client validation
bool validate_client_credentials(struct wl_client *client, 
                                  struct client_security *sec);
bool is_vm_process(pid_t pid);

// Input validation
bool validate_geometry(int32_t x, int32_t y, uint32_t width, uint32_t height);
bool validate_buffer_size(uint32_t width, uint32_t height);

// Resource limits
bool check_surface_limit(struct client_security *client);

#endif
