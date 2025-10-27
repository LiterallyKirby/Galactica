#include "include/helpers.h"

unsigned int cursor_x = 0;
unsigned int cursor_y = 0;
unsigned char current_color = WHITE_TXT;

void k_clear_screen()
{
    char* vidmem = VIDEO_MEMORY;
    for(unsigned int i = 0; i < SCREEN_WIDTH * SCREEN_HEIGHT; i++){
        vidmem[i*2] = ' ';
        vidmem[i*2 + 1] = current_color;
    }
    cursor_x = cursor_y = 0;
}

void k_putc(char c, unsigned int x, unsigned int y, unsigned char color)
{
    unsigned int pos = (y * SCREEN_WIDTH + x) * 2;
    VIDEO_MEMORY[pos] = c;
    VIDEO_MEMORY[pos+1] = color;
}

unsigned int k_printf(char* message, unsigned int line)
{
    cursor_y = line;
    while(*message){
        if(*message == '\n'){
            cursor_x = 0;
            cursor_y++;
            message++;
        } else {
            k_putc(*message, cursor_x, cursor_y, current_color);
            cursor_x++;
            if(cursor_x >= SCREEN_WIDTH){ cursor_x=0; cursor_y++; }
            message++;
        }
        if(cursor_y >= SCREEN_HEIGHT) k_scroll();
    }
    return 1;
}

void k_scroll()
{
    char* vidmem = VIDEO_MEMORY;
    for(unsigned int y = 1; y < SCREEN_HEIGHT; y++){
        for(unsigned int x = 0; x < SCREEN_WIDTH; x++){
            unsigned int from = ((y*SCREEN_WIDTH)+x)*2;
            unsigned int to = (((y-1)*SCREEN_WIDTH)+x)*2;
            vidmem[to] = vidmem[from];
            vidmem[to+1] = vidmem[from+1];
        }
    }
    // clear last line
    for(unsigned int x=0; x<SCREEN_WIDTH; x++){
        unsigned int pos = ((SCREEN_HEIGHT-1)*SCREEN_WIDTH + x)*2;
        vidmem[pos]=' ';
        vidmem[pos+1]=current_color;
    }
    if(cursor_y>0) cursor_y--;
}

void k_set_cursor(unsigned int x, unsigned int y){ cursor_x=x; cursor_y=y; }
void k_set_color(unsigned char color){ current_color=color; }

int strcmp(const char* a, const char* b){
    while(*a && *b){ if(*a != *b) return 0; a++; b++; }
    return (*a==0 && *b==0);
}
