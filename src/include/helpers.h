#ifndef HELPERS_H
#define HELPERS_H

#define WHITE_TXT 0x0F
#define SCREEN_WIDTH 80
#define SCREEN_HEIGHT 25
#define VIDEO_MEMORY ((char *)0xb8000)

extern unsigned int cursor_x;
extern unsigned int cursor_y;
extern unsigned char current_color;

void k_clear_screen(void);
unsigned int k_printf(char *message, unsigned int line);
void k_putc(char c, unsigned int x, unsigned int y, unsigned char color);
void k_set_cursor(unsigned int x, unsigned int y);
void k_scroll(void);
void k_set_color(unsigned char color);
int strcmp(const char* a, const char* b);

void init_keyboard(void);
char get_key(void);

#endif
