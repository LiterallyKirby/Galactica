
#include "include/helpers.h"

/* clear screen */
void k_clear_screen() {
    char *vidmem = VIDEO_MEMORY;
    for(unsigned int i=0;i<SCREEN_WIDTH*SCREEN_HEIGHT;i++){
        vidmem[i*2]=' ';
        vidmem[i*2+1]=current_color;
    }
    cursor_x=0; cursor_y=0;
}

/* put char at x,y */
void k_putc(char c,unsigned int x,unsigned int y,unsigned char color){
    unsigned int pos=(y*SCREEN_WIDTH+x)*2;
    VIDEO_MEMORY[pos]=c;
    VIDEO_MEMORY[pos+1]=color;
}

/* print string with line number */
unsigned int k_printf(char *message,unsigned int line){
    cursor_y=line;
    while(*message){
        if(*message=='\n'){cursor_x=0;cursor_y++;message++;}
        else{
            k_putc(*message,cursor_x,cursor_y,current_color);
            cursor_x++; if(cursor_x>=SCREEN_WIDTH){cursor_x=0;cursor_y++;}
            message++;
        }
        if(cursor_y>=SCREEN_HEIGHT) k_scroll();
    }
    return 1;
}

/* scroll screen by 1 line */
void k_scroll(void){
    char *vidmem=VIDEO_MEMORY;
    for(unsigned int y=1;y<SCREEN_HEIGHT;y++){
        for(unsigned int x=0;x<SCREEN_WIDTH;x++){
            unsigned int from=((y*SCREEN_WIDTH)+x)*2;
            unsigned int to=(((y-1)*SCREEN_WIDTH)+x)*2;
            vidmem[to]=vidmem[from];
            vidmem[to+1]=vidmem[from+1];
        }
    }
    for(unsigned int x=0;x<SCREEN_WIDTH;x++){
        unsigned int pos=((SCREEN_HEIGHT-1)*SCREEN_WIDTH+x)*2;
        vidmem[pos]=' ';
        vidmem[pos+1]=current_color;
    }
    if(cursor_y>0) cursor_y--;
}

/* set cursor */
void k_set_cursor(unsigned int x,unsigned int y){cursor_x=x;cursor_y=y;}
/* set color */
void k_set_color(unsigned char color){current_color=color;}
/* fill rectangle */
void k_fill_rect(unsigned int x,unsigned int y,unsigned int w,unsigned int h,unsigned char color){
    for(unsigned int yy=0;yy<h;yy++)
        for(unsigned int xx=0;xx<w;xx++)
            if((x+xx<SCREEN_WIDTH)&&(y+yy<SCREEN_HEIGHT)) k_putc(' ',x+xx,y+yy,color);
}
/* print hex */
void k_print_hex(unsigned int value,unsigned int line){
    char hex[9]; hex[8]=0;
    for(int i=7;i>=0;i--){
        unsigned int n=value&0xF;
        hex[i]=(n<10)?('0'+n):('A'+n-10);
        value>>=4;
    }
    k_printf(hex,line);
}
/* print decimal */
void k_print_dec(unsigned int value,unsigned int line){
    char dec[12]; int i=0;
    if(value==0) dec[i++]='0';
    else while(value>0){dec[i++]='0'+(value%10); value/=10;}
    for(int j=0;j<i/2;j++){char tmp=dec[j]; dec[j]=dec[i-j-1]; dec[i-j-1]=tmp;}
    dec[i]=0; k_printf(dec,line);
}
