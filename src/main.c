#include "include/helpers.h"
#include "include/shell.h"

void kmain(void){
    k_clear_screen();
    k_set_color(0x0F);
    
    k_printf("================================\n", 0);
    k_printf("    MyTinyOS - FAT32 Edition\n", cursor_y);
    k_printf("================================\n", cursor_y);
    k_printf("\n", cursor_y);
    k_printf("Type 'help' for available commands\n", cursor_y);
    k_printf("\n", cursor_y);

    init_keyboard();
    shell_loop();
}

// Simple ATA PIO mode disk I/O for protected mode
#define ATA_PRIMARY_IO 0x1F0
#define ATA_PRIMARY_CONTROL 0x3F6

static void ata_wait_busy(){
    while(1){
        unsigned char status;
        asm volatile("inb %1, %0" : "=a"(status) : "Nd"((unsigned short)(ATA_PRIMARY_IO + 7)));
        if(!(status & 0x80)) break;
    }
}

static void ata_wait_drq(){
    while(1){
        unsigned char status;
        asm volatile("inb %1, %0" : "=a"(status) : "Nd"((unsigned short)(ATA_PRIMARY_IO + 7)));
        if(status & 0x08) break;
    }
}

unsigned char read_sector(unsigned short drive, unsigned int lba, unsigned char* buffer){
    ata_wait_busy();
    
    // Select drive and send LBA bits 24-27
    asm volatile("outb %0, %1" : : "a"((unsigned char)(0xE0 | ((lba >> 24) & 0x0F))), "Nd"((unsigned short)(ATA_PRIMARY_IO + 6)));
    
    // Send sector count (1 sector)
    asm volatile("outb %0, %1" : : "a"((unsigned char)1), "Nd"((unsigned short)(ATA_PRIMARY_IO + 2)));
    
    // Send LBA bits 0-7
    asm volatile("outb %0, %1" : : "a"((unsigned char)(lba & 0xFF)), "Nd"((unsigned short)(ATA_PRIMARY_IO + 3)));
    
    // Send LBA bits 8-15
    asm volatile("outb %0, %1" : : "a"((unsigned char)((lba >> 8) & 0xFF)), "Nd"((unsigned short)(ATA_PRIMARY_IO + 4)));
    
    // Send LBA bits 16-23
    asm volatile("outb %0, %1" : : "a"((unsigned char)((lba >> 16) & 0xFF)), "Nd"((unsigned short)(ATA_PRIMARY_IO + 5)));
    
    // Send READ SECTORS command
    asm volatile("outb %0, %1" : : "a"((unsigned char)0x20), "Nd"((unsigned short)(ATA_PRIMARY_IO + 7)));
    
    ata_wait_drq();
    
    // Read 256 words (512 bytes)
    unsigned short* buf = (unsigned short*)buffer;
    for(int i = 0; i < 256; i++){
        asm volatile("inw %1, %0" : "=a"(buf[i]) : "Nd"((unsigned short)ATA_PRIMARY_IO));
    }
    
    return 0;
}

unsigned char write_sector(unsigned short drive, unsigned int lba, unsigned char* buffer){
    ata_wait_busy();
    
    // Select drive and send LBA bits 24-27
    asm volatile("outb %0, %1" : : "a"((unsigned char)(0xE0 | ((lba >> 24) & 0x0F))), "Nd"((unsigned short)(ATA_PRIMARY_IO + 6)));
    
    // Send sector count (1 sector)
    asm volatile("outb %0, %1" : : "a"((unsigned char)1), "Nd"((unsigned short)(ATA_PRIMARY_IO + 2)));
    
    // Send LBA bits 0-7
    asm volatile("outb %0, %1" : : "a"((unsigned char)(lba & 0xFF)), "Nd"((unsigned short)(ATA_PRIMARY_IO + 3)));
    
    // Send LBA bits 8-15
    asm volatile("outb %0, %1" : : "a"((unsigned char)((lba >> 8) & 0xFF)), "Nd"((unsigned short)(ATA_PRIMARY_IO + 4)));
    
    // Send LBA bits 16-23
    asm volatile("outb %0, %1" : : "a"((unsigned char)((lba >> 16) & 0xFF)), "Nd"((unsigned short)(ATA_PRIMARY_IO + 5)));
    
    // Send WRITE SECTORS command
    asm volatile("outb %0, %1" : : "a"((unsigned char)0x30), "Nd"((unsigned short)(ATA_PRIMARY_IO + 7)));
    
    ata_wait_drq();
    
    // Write 256 words (512 bytes)
    unsigned short* buf = (unsigned short*)buffer;
    for(int i = 0; i < 256; i++){
        asm volatile("outw %0, %1" : : "a"(buf[i]), "Nd"((unsigned short)ATA_PRIMARY_IO));
    }
    
    // Flush cache
    asm volatile("outb %0, %1" : : "a"((unsigned char)0xE7), "Nd"((unsigned short)(ATA_PRIMARY_IO + 7)));
    ata_wait_busy();
    
    return 0;
}
