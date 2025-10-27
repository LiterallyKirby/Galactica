#include "include/helpers.h"
#include "include/shell.h"

/* Globals */
unsigned int cursor_x = 0;
unsigned int cursor_y = 0;
unsigned char current_color = WHITE_TXT;

void kmain(void) {
    k_clear_screen();
    k_printf("Welcome to MyTinyOS!\n", 0);

    init_keyboard();
    shell_loop(); // enter shell
}
