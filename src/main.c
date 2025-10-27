#include "include/helpers.h"
#include "include/shell.h"

void kmain(void){
    k_clear_screen();
    k_printf("Welcome to MyTinyOS!\n", 0);

    init_keyboard();
    shell_loop();
}

unsigned char read_sector(unsigned short drive, unsigned int lba, unsigned char* buffer){
    unsigned char status;
    asm volatile("int $0x13"
                 : "=a"(status)
                 : "a"(0x0200),
                   "d"(drive << 8 | ((lba >> 24)&0xFF)),
                   "c"((lba >> 8)&0xFF | ((lba >>16)&0xFF<<8)),
                   "b"(buffer)
                 : "memory");
    return status;
}
