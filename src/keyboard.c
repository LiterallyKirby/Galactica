
#include "include/helpers.h"

#define KBD_DATA 0x60
#define KBD_STATUS 0x64

static char keymap[128] = {
  0,27,'1','2','3','4','5','6','7','8','9','0','-','=',0,  //0-14
  '\t','q','w','e','r','t','y','u','i','o','p','[',']','\n',0,'a', //15-30
  's','d','f','g','h','j','k','l',';','\'','`',0,'\\','z','x','c','v','b','n','m',',','.','/',0,'*',0,' ', //31-63
};

void init_keyboard(void){
    // nothing fancy for now
}

char get_key(void){
    unsigned char status;
    while(1){
        asm volatile("inb %1, %0":"=a"(status):"Nd"(KBD_STATUS));
        if(status & 1) break;
    }
    unsigned char scancode;
    asm volatile("inb %1, %0":"=a"(scancode):"Nd"(KBD_DATA));
    if(scancode>127) return 0;
    return keymap[scancode];
}
