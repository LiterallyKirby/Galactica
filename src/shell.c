
#include "include/helpers.h"
#include "include/shell.h"

void shell_loop(void){
    char line[128];
    int idx=0;
    k_printf("myos> ", cursor_y);
    while(1){
        char c=get_key();
        if(c==0) continue;
        if(c=='\n'||c=='\r'){
            line[idx]=0;
            k_printf("\n",cursor_y);
            if(idx>0){
                if(line[0]=='h') k_printf("Hello command received!",cursor_y);
                else k_printf("Unknown command",cursor_y);
    k_printf("\n",cursor_y);
            }
            idx=0;
            k_printf("myos> ",cursor_y);
        }else{
            line[idx++]=c;
            k_putc(c,cursor_x,cursor_y,current_color);
            cursor_x++;
        }
    }
}
