#ifndef HELPERS_H
#define HELPERS_H

#define WHITE_TXT 0x07
#define SCREEN_WIDTH 80
#define SCREEN_HEIGHT 25
#define VIDEO_MEMORY ((char *)0xb8000)

/* Globals */
extern unsigned int cursor_x;
extern unsigned int cursor_y;
extern unsigned char current_color;

/* Screen / output */
void k_clear_screen(void);
unsigned int k_printf(char *message, unsigned int line);
void k_putc(char c, unsigned int x, unsigned int y, unsigned char color);
void k_set_cursor(unsigned int x, unsigned int y);
void k_scroll(void);
void k_set_color(unsigned char color);
void k_fill_rect(unsigned int x, unsigned int y, unsigned int width, unsigned int height, unsigned char color);
void k_print_hex(unsigned int value, unsigned int line);
void k_print_dec(unsigned int value, unsigned int line);

/* Keyboard */
void init_keyboard(void);
char get_key(void);

#endif
