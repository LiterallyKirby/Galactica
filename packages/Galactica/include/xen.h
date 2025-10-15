/* xen.h - Xen hypervisor integration */
#ifndef GALLIUM_XEN_H
#define GALLIUM_XEN_H

#include <xenctrl.h>
#include <xen-tools/libs/util/domain.h>
#include <wl_list.h>

struct xen_vm {
	struct wl_list link;
	uint32_t domid;
	char name[256];
	int running;
	uint32_t memory;  /* KB */
	uint32_t vcpus;
};

struct xen_state {
	xc_interface *xch;
	xc_evtchn *xce;
	int xen_ready;
	struct wl_list vms;
};

/* Initialize Xen connection */
struct xen_state *xen_init(void);

/* Cleanup Xen connection */
void xen_destroy(struct xen_state *xen);

/* Enumerate running VMs */
int xen_enumerate_vms(struct xen_state *xen);

/* Get VM by domain ID */
struct xen_vm *xen_get_vm(struct xen_state *xen, uint32_t domid);

/* Monitor for VM changes (for event loop) */
int xen_get_monitor_fd(struct xen_state *xen);

/* Handle Xen events */
int xen_handle_events(struct xen_state *xen);

#endif
