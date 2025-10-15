/* xen.c - Xen hypervisor integration */
#define _GNU_SOURCE
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <sys/types.h>
#include <wlr/util/log.h>
#include "../include/xen.h"

struct xen_state *xen_init(void) {
	struct xen_state *xen = calloc(1, sizeof(struct xen_state));
	if (!xen) {
		wlr_log(WLR_ERROR, "Failed to allocate xen_state");
		return NULL;
	}

	/* Open Xen control interface */
	xen->xch = xc_interface_open(0, 0, 0);
	if (!xen->xch) {
		wlr_log(WLR_ERROR, "Failed to open Xen control interface");
		wlr_log(WLR_ERROR, "Are you running as root? Is xenctrl installed?");
		free(xen);
		return NULL;
	}

	/* Open Xen event channel interface */
	xen->xce = xc_evtchn_open(NULL, 0);
	if (!xen->xce) {
		wlr_log(WLR_ERROR, "Failed to open Xen event channel interface");
		xc_interface_close(xen->xch);
		free(xen);
		return NULL;
	}

	wl_list_init(&xen->vms);
	xen->xen_ready = 1;

	wlr_log(WLR_INFO, "Xen initialized successfully");

	return xen;
}

void xen_destroy(struct xen_state *xen) {
	if (!xen) {
		return;
	}

	/* Free VM list */
	struct xen_vm *vm, *tmp;
	wl_list_for_each_safe(vm, tmp, &xen->vms, link) {
		wl_list_remove(&vm->link);
		free(vm);
	}

	if (xen->xce) {
		xc_evtchn_close(xen->xce);
	}

	if (xen->xch) {
		xc_interface_close(xen->xch);
	}

	free(xen);
	wlr_log(WLR_INFO, "Xen destroyed");
}

int xen_enumerate_vms(struct xen_state *xen) {
	if (!xen || !xen->xen_ready) {
		return -1;
	}

	/* Get list of all domains */
	xc_dominfo_t *info = NULL;
	int num_domains = xc_domain_getinfo(xen->xch, 0, 1024, &info);

	if (num_domains < 0) {
		wlr_log(WLR_ERROR, "Failed to get domain info");
		return -1;
	}

	/* Clear existing VM list */
	struct xen_vm *vm, *tmp;
	wl_list_for_each_safe(vm, tmp, &xen->vms, link) {
		wl_list_remove(&vm->link);
		free(vm);
	}

	/* Add new VMs to list */
	for (int i = 0; i < num_domains; i++) {
		xc_dominfo_t *dom = &info[i];

		/* Skip Dom0 (domid 0) - we're running in it */
		if (dom->domid == 0) {
			continue;
		}

		struct xen_vm *new_vm = calloc(1, sizeof(struct xen_vm));
		if (!new_vm) {
			continue;
		}

		new_vm->domid = dom->domid;
		new_vm->running = dom->running;
		new_vm->memory = dom->tot_pages * 4;  /* Pages to KB (4KB pages) */
		new_vm->vcpus = dom->max_vcpu_id + 1;

		/* Get domain name */
		char *name = xc_domain_getinfo_single(xen->xch, dom->domid, &info[i]);
		if (name) {
			strncpy(new_vm->name, name, sizeof(new_vm->name) - 1);
			free(name);
		} else {
			snprintf(new_vm->name, sizeof(new_vm->name), "Domain-%u", dom->domid);
		}

		wl_list_insert(&xen->vms, &new_vm->link);

		wlr_log(WLR_INFO, "VM found: %s (domid=%u, running=%d, memory=%uKB)",
			new_vm->name, new_vm->domid, new_vm->running, new_vm->memory);
	}

	free(info);
	return num_domains;
}

struct xen_vm *xen_get_vm(struct xen_state *xen, uint32_t domid) {
	if (!xen) {
		return NULL;
	}

	struct xen_vm *vm;
	wl_list_for_each(vm, &xen->vms, link) {
		if (vm->domid == domid) {
			return vm;
		}
	}

	return NULL;
}

int xen_get_monitor_fd(struct xen_state *xen) {
	if (!xen || !xen->xce) {
		return -1;
	}

	return xc_evtchn_fd(xen->xce);
}

int xen_handle_events(struct xen_state *xen) {
	if (!xen || !xen->xce) {
		return -1;
	}

	evtchn_port_or_error_t port = xc_evtchn_pending(xen->xce);
	if (port >= 0) {
		xc_evtchn_unmask(xen->xce, port);
		return port;
	}

	return -1;
}
