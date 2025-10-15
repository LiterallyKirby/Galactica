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
    xen->xch = xc_interface_open(NULL, NULL, 0);
    if (!xen->xch) {
        wlr_log(WLR_ERROR, "Failed to open Xen control interface");
        wlr_log(WLR_ERROR, "Are you running as root? Is xenctrl installed?");
        free(xen);
        return NULL;
    }

    /* Open Xen event channel interface - NEW API */
    xen->xce = xenevtchn_open(NULL, 0);
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
        xenevtchn_close(xen->xce);
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

    /* Get list of all domains - NEW API */
    xc_domaininfo_t info;
    int num_domains = 0;
    uint32_t domid = 0;

    /* Clear existing VM list */
    struct xen_vm *vm, *tmp;
    wl_list_for_each_safe(vm, tmp, &xen->vms, link) {
        wl_list_remove(&vm->link);
        free(vm);
    }

    /* Iterate through all domains */
    while (1) {
        int ret = xc_domain_getinfo_single(xen->xch, domid, &info);
        if (ret != 0) {
            break;  // No more domains
        }

        /* Skip Dom0 (domid 0) - we're running in it */
        if (info.domain != 0) {
            struct xen_vm *new_vm = calloc(1, sizeof(struct xen_vm));
            if (!new_vm) {
                continue;
            }

            new_vm->domid = info.domain;
            new_vm->running = (info.flags & XEN_DOMINF_running) ? 1 : 0;
            new_vm->memory = info.tot_pages * 4;  /* Pages to KB (4KB pages) */
            new_vm->vcpus = info.max_vcpu_id + 1;

            /* Generate name */
            snprintf(new_vm->name, sizeof(new_vm->name), "Domain-%u", info.domain);

            wl_list_insert(&xen->vms, &new_vm->link);
            wlr_log(WLR_INFO, "VM found: %s (domid=%u, running=%d, memory=%uKB)",
                new_vm->name, new_vm->domid, new_vm->running, new_vm->memory);

            num_domains++;
        }

        /* Move to next domain */
        domid = info.domain + 1;
        if (domid > 1024) break;  // Safety limit
    }

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
    return xenevtchn_fd(xen->xce);
}

int xen_handle_events(struct xen_state *xen) {
    if (!xen || !xen->xce) {
        return -1;
    }

    xenevtchn_port_or_error_t port = xenevtchn_pending(xen->xce);
    if (port >= 0) {
        xenevtchn_unmask(xen->xce, port);
        return port;
    }

    return -1;
}
