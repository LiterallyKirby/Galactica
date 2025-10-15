#define _POSIX_C_SOURCE 200809L
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include <wayland-server-core.h>
#include <wlr/backend.h>
#include <wlr/render/wlr_renderer.h>
#include <wlr/types/wlr_compositor.h>
#include <wlr/types/wlr_output.h>
#include <wlr/types/wlr_output_layout.h>
#include <wlr/types/wlr_xdg_shell.h>
#include <wlr/util/log.h>

#include "xdg-shell-protocol.h"

struct view {
	struct wl_list link;
	struct wlr_xdg_surface *xdg_surface;
	struct wl_listener destroy;
};

struct output {
	struct wl_list link;
	struct server *server;
	struct wlr_output *wlr_output;
	struct wl_listener frame;
	struct wl_listener request_state;
	struct wl_listener destroy;
};

struct server {
	struct wl_display *display;
	struct wl_event_loop *event_loop;
	struct wlr_backend *backend;
	struct wlr_renderer *renderer;
	struct wlr_allocator *allocator;
	struct wlr_compositor *compositor;
	struct wlr_xdg_shell *xdg_shell;
	struct wlr_output_layout *output_layout;
	struct wl_list outputs;
	struct wl_list views;
	struct wl_listener new_output;
	struct wl_listener new_xdg_surface;
};

/* Output frame handler */
static void output_frame_handler(struct wl_listener *listener, void *data) {
	struct output *output = wl_container_of(listener, output, frame);
	struct wlr_output *wlr_output = output->wlr_output;

	struct timespec now;
	clock_gettime(CLOCK_MONOTONIC, &now);

	struct wlr_output_state state;
	wlr_output_state_init(&state);
	struct wlr_render_pass *pass = wlr_output_begin_render_pass(wlr_output, &state, NULL);

	if (!pass) {
		wlr_output_state_finish(&state);
		return;
	}

	float color[4] = {0.1, 0.1, 0.1, 1.0};
	struct wlr_render_rect_options rect_options = {
		.color = {color[0], color[1], color[2], color[3]},
	};
	wlr_render_pass_add_rect(pass, &rect_options);

	wlr_render_pass_submit(pass);
	wlr_output_state_finish(&state);
}

/* Output request state handler */
static void output_request_state_handler(struct wl_listener *listener, void *data) {
	struct output *output = wl_container_of(listener, output, request_state);
	const struct wlr_output_event_request_state *event = data;
	wlr_output_commit_state(output->wlr_output, event->state);
}

/* Output destroy handler */
static void output_destroy_handler(struct wl_listener *listener, void *data) {
	struct output *output = wl_container_of(listener, output, destroy);
	wl_list_remove(&output->frame.link);
	wl_list_remove(&output->request_state.link);
	wl_list_remove(&output->destroy.link);
	wl_list_remove(&output->link);
	free(output);
}

/* New output handler */
static void server_new_output(struct wl_listener *listener, void *data) {
	struct server *server = wl_container_of(listener, server, new_output);
	struct wlr_output *wlr_output = data;

	if (!wl_list_length(&wlr_output->modes)) {
		return;
	}

	struct wlr_output_state state;
	wlr_output_state_init(&state);
	wlr_output_state_set_enabled(&state, true);

	struct wlr_output_mode *mode = wlr_output_preferred_mode(wlr_output);
	if (mode) {
		wlr_output_state_set_mode(&state, mode);
	}

	wlr_output_commit_state(wlr_output, &state);
	wlr_output_state_finish(&state);

	struct output *output = calloc(1, sizeof(struct output));
	output->wlr_output = wlr_output;
	output->server = server;
	wl_list_insert(&server->outputs, &output->link);

	wlr_output_layout_add_auto(server->output_layout, wlr_output);

	wl_signal_add(&wlr_output->events.frame, &output->frame);
	output->frame.notify = output_frame_handler;

	wl_signal_add(&wlr_output->events.request_state, &output->request_state);
	output->request_state.notify = output_request_state_handler;

	wl_signal_add(&wlr_output->events.destroy, &output->destroy);
	output->destroy.notify = output_destroy_handler;

	wlr_log(WLR_INFO, "Output added: %s", wlr_output->name);
}

/* View destroy handler */
static void xdg_surface_destroy_handler(struct wl_listener *listener, void *data) {
	struct view *view = wl_container_of(listener, view, destroy);
	wl_list_remove(&view->link);
	free(view);
}

/* New XDG surface handler */
static void server_new_xdg_surface(struct wl_listener *listener, void *data) {
	struct server *server = wl_container_of(listener, server, new_xdg_surface);
	struct wlr_xdg_surface *xdg_surface = data;

	if (xdg_surface->role != WLR_XDG_SURFACE_ROLE_TOPLEVEL) {
		return;
	}

	struct view *view = calloc(1, sizeof(struct view));
	view->xdg_surface = xdg_surface;
	wl_list_insert(&server->views, &view->link);

	wl_signal_add(&xdg_surface->events.destroy, &view->destroy);
	view->destroy.notify = xdg_surface_destroy_handler;

	wlr_log(WLR_INFO, "New XDG toplevel surface");
}

/* Main */
int main(void) {
	wlr_log_init(WLR_DEBUG, NULL);

	struct server server = {0};
	server.display = wl_display_create();
	if (!server.display) {
		wlr_log(WLR_ERROR, "Failed to create display");
		return 1;
	}

	server.event_loop = wl_display_get_event_loop(server.display);

	server.backend = wlr_backend_autocreate(server.event_loop, NULL);
	if (!server.backend) {
		wlr_log(WLR_ERROR, "Failed to create backend");
		wl_display_destroy(server.display);
		return 1;
	}

	server.renderer = wlr_renderer_autocreate(server.backend);
	if (!server.renderer) {
		wlr_log(WLR_ERROR, "Failed to create renderer");
		wlr_backend_destroy(server.backend);
		wl_display_destroy(server.display);
		return 1;
	}

	server.compositor = wlr_compositor_create(server.display, 4, server.renderer);
	if (!server.compositor) {
		wlr_log(WLR_ERROR, "Failed to create compositor");
		return 1;
	}

	server.output_layout = wlr_output_layout_create(server.display);
	if (!server.output_layout) {
		wlr_log(WLR_ERROR, "Failed to create output layout");
		return 1;
	}

	wl_list_init(&server.outputs);
	wl_list_init(&server.views);

	server.xdg_shell = wlr_xdg_shell_create(server.display, 3);
	if (!server.xdg_shell) {
		wlr_log(WLR_ERROR, "Failed to create XDG shell");
		return 1;
	}

	/* Setup listeners */
	wl_signal_add(&server.backend->events.new_output, &server.new_output);
	server.new_output.notify = server_new_output;

	wl_signal_add(&server.xdg_shell->events.new_surface, &server.new_xdg_surface);
	server.new_xdg_surface.notify = server_new_xdg_surface;

	const char *socket = wl_display_add_socket_auto(server.display);
	if (!socket) {
		wlr_log(WLR_ERROR, "Failed to add Wayland socket");
		wlr_backend_destroy(server.backend);
		wl_display_destroy(server.display);
		return 1;
	}

	if (!wlr_backend_start(server.backend)) {
		wlr_log(WLR_ERROR, "Failed to start backend");
		wlr_backend_destroy(server.backend);
		wl_display_destroy(server.display);
		return 1;
	}

	wlr_log(WLR_INFO, "Running compositor on Wayland display '%s'", socket);
	setenv("WAYLAND_DISPLAY", socket, true);

	wl_display_run(server.display);

	wl_display_destroy(server.display);
	return 0;
}
