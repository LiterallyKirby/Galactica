#include "include/helpers.h"
#include "include/shell.h"
#include "include/fat16.h"

void shell_loop(void){
    char line[128];
    int idx=0;
    k_printf("myos> ", cursor_y);

    while(1){
        char c = get_key();
        if(c==0) continue;

        if(c=='\n'||c=='\r'){
            line[idx]=0;
            k_printf("\n",cursor_y);

            if(idx>0){
                char cmd[16]={0}, arg[112]={0};
                int i=0,j=0;
                while(line[i] && line[i]!=' ' && i<15){ cmd[i]=line[i]; i++; }
                if(line[i]==' ') i++;
                while(line[i] && j<111){ arg[j++] = line[i++]; }
                arg[j]=0;

                if(strcmp(cmd,"cat")==1){
                    unsigned char buf[512];
                    unsigned int size = fat16_read_file(arg, buf);
                    if(size>0){
                        buf[size]=0;
                        k_printf((char*)buf, cursor_y);
                        k_printf("\n", cursor_y);
                    } else k_printf("File not found\n", cursor_y);
                } else if(strcmp(cmd,"touch")==1){
                    if(fat16_create_file(arg))
                        k_printf("File created\n", cursor_y);
                    else
                        k_printf("Error creating file\n", cursor_y);
                } else if(strcmp(cmd,"hello")==1){
                    k_printf("Hello command received!\n", cursor_y);
                } else k_printf("Unknown command\n", cursor_y);
            }

            idx=0;
            k_printf("myos> ", cursor_y);
        } else {
            line[idx++] = c;
            k_putc(c, cursor_x, cursor_y, current_color);
            cursor_x++;
        }
    }
}
