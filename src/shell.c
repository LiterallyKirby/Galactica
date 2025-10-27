#include "include/helpers.h"
#include "include/shell.h"
#include "include/fat32.h"

static void print_file_entry(char* name){
    char display[13];
    int j=0;
    for(int i=0; i<8 && name[i]!=' '; i++) display[j++] = name[i];
    
    int has_ext = 0;
    for(int i=8; i<11; i++){
        if(name[i] != ' '){ has_ext=1; break; }
    }
    
    if(has_ext){
        display[j++] = '.';
        for(int i=8; i<11 && name[i]!=' '; i++) display[j++] = name[i];
    }
    display[j] = 0;
    
    k_printf(display, cursor_y);
    k_printf("  ", cursor_y);
}

static void print_number(unsigned int num){
    char buf[16];
    int idx = 0;
    if(num == 0){ buf[idx++] = '0'; }
    else {
        char temp[16];
        int t = 0;
        while(num > 0){
            temp[t++] = '0' + (num % 10);
            num /= 10;
        }
        for(int j=t-1; j>=0; j--) buf[idx++] = temp[j];
    }
    buf[idx] = 0;
    k_printf(buf, cursor_y);
}

static void cmd_ls(){
    file_entry_t entries[64];
    unsigned int count;
    
    fat32_list_files(entries, &count);
    
    if(count == 0){
        k_printf("No files found\n", cursor_y);
        return;
    }
    
    for(unsigned int i=0; i<count; i++){
        print_file_entry(entries[i].name);
        print_number(entries[i].size);
        k_printf(" bytes\n", cursor_y);
    }
}

static void cmd_cat(char* arg){
    unsigned char buf[8192];
    unsigned int size = fat32_read_file(arg, buf);
    if(size > 0){
        if(size > 8191) size = 8191;
        buf[size] = 0;
        k_printf((char*)buf, cursor_y);
        k_printf("\n", cursor_y);
    } else {
        k_printf("File not found\n", cursor_y);
    }
}

static void cmd_echo(char* arg, char* filename){
    unsigned int len = 0;
    while(arg[len]) len++;
    
    if(fat32_write_file(filename, (unsigned char*)arg, len)){
        k_printf("Written to ", cursor_y);
        k_printf(filename, cursor_y);
        k_printf("\n", cursor_y);
    } else {
        k_printf("Error writing file\n", cursor_y);
    }
}

static void cmd_rm(char* arg){
    if(fat32_delete_file(arg)){
        k_printf("File deleted\n", cursor_y);
    } else {
        k_printf("Error deleting file\n", cursor_y);
    }
}

static void cmd_help(){
    k_printf("Available commands:\n", cursor_y);
    k_printf("  ls            - List files\n", cursor_y);
    k_printf("  cat FILE      - Display file contents\n", cursor_y);
    k_printf("  touch FILE    - Create empty file\n", cursor_y);
    k_printf("  echo TEXT > FILE - Write text to file\n", cursor_y);
    k_printf("  rm FILE       - Delete file\n", cursor_y);
    k_printf("  clear         - Clear screen\n", cursor_y);
    k_printf("  help          - Show this help\n", cursor_y);
    k_printf("  sysinfo       - System information\n", cursor_y);
}

static void cmd_sysinfo(){
    k_printf("MyTinyOS v1.0 - FAT32 Edition\n", cursor_y);
    k_printf("Architecture: x86 Protected Mode\n", cursor_y);
    k_printf("Filesystem: FAT32\n", cursor_y);
}

void shell_loop(void){
    char line[128];
    int idx = 0;
    
    fat32_init();
    k_printf("myos> ", cursor_y);

    while(1){
        char c = get_key();
        if(c == 0) continue;

        if(c == '\n' || c == '\r'){
            line[idx] = 0;
            k_printf("\n", cursor_y);

            if(idx > 0){
                char cmd[16] = {0};
                char arg[112] = {0};
                int i = 0, j = 0;
                
                while(line[i] && line[i] != ' ' && i < 15){ 
                    cmd[i] = line[i]; 
                    i++; 
                }
                if(line[i] == ' ') i++;
                while(line[i] && j < 111){ 
                    arg[j++] = line[i++]; 
                }
                arg[j] = 0;

                if(strcmp(cmd, "ls") == 1){
                    cmd_ls();
                } else if(strcmp(cmd, "cat") == 1){
                    cmd_cat(arg);
                } else if(strcmp(cmd, "touch") == 1){
                    unsigned int result = fat32_create_file(arg);
                    if(result == 1) k_printf("File created\n", cursor_y);
                    else if(result == 2) k_printf("File already exists\n", cursor_y);
                    else k_printf("Error creating file\n", cursor_y);
                } else if(strcmp(cmd, "rm") == 1){
                    cmd_rm(arg);
                } else if(strcmp(cmd, "echo") == 1){
                    char text[64] = {0};
                    char file[32] = {0};
                    int k = 0, mode = 0;
                    
                    for(int p = 0; arg[p] && k < 63; p++){
                        if(arg[p] == '>' && arg[p+1] == ' '){
                            mode = 1;
                            p += 2;
                            text[k] = 0;
                            k = 0;
                        }
                        if(mode == 0) text[k++] = arg[p];
                        else if(mode == 1 && k < 31) file[k++] = arg[p];
                    }
                    
                    if(mode == 1 && k > 0){
                        file[k] = 0;
                        int t = 0;
                        while(text[t]) t++;
                        if(t > 0 && text[t-1] == ' ') text[t-1] = 0;
                        cmd_echo(text, file);
                    } else {
                        k_printf(arg, cursor_y);
                        k_printf("\n", cursor_y);
                    }
                } else if(strcmp(cmd, "clear") == 1){
                    k_clear_screen();
                } else if(strcmp(cmd, "help") == 1){
                    cmd_help();
                } else if(strcmp(cmd, "sysinfo") == 1){
                    cmd_sysinfo();
                } else {
                    k_printf("Unknown command. Type 'help' for commands.\n", cursor_y);
                }
            }

            idx = 0;
            k_printf("myos> ", cursor_y);
        } else if(c == 8 || c == 127){
            if(idx > 0){
                idx--;
                if(cursor_x > 0) cursor_x--;
                k_putc(' ', cursor_x, cursor_y, current_color);
            }
        } else if(idx < 127){
            line[idx++] = c;
            k_putc(c, cursor_x, cursor_y, current_color);
            cursor_x++;
            if(cursor_x >= SCREEN_WIDTH){
                cursor_x = 0;
                cursor_y++;
            }
        }
    }
}
