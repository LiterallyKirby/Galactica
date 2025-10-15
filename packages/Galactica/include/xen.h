#ifndef XEN_H
#define XEN_H

#include <stdint.h>
#include <xenctrl.h>
#include <xenevtchn.h>
#include <wayland-server-core.h>

struct xen_vm {
    uint32_t domid;
    char name[256];
    int running;
    uint32_t memory;  // KB
    uint32_t vcpus;
    struct wl_list link;
};

struct xen_state {
    xc_interface *xch;
    xenevtchn_handle *xce;  // Changed from xc_evtchn
    struct wl_list vms;
    int xen_ready;
};

struct xen_state *xen_init(void);
void xen_destroy(struct xen_state *xen);
int xen_enumerate_vms(struct xen_state *xen);
struct xen_vm *xen_get_vm(struct xen_state *xen, uint32_t domid);
int xen_get_monitor_fd(struct xen_state *xen);
int xen_handle_events(struct xen_state *xen);

#endif
