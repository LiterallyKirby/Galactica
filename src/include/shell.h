#ifndef SHELL_H
#define SHELL_H

void shell_loop(void);
char get_key(void);
unsigned char read_sector(unsigned short drive, unsigned int lba, unsigned char* buffer);

// FAT16 stubs
unsigned int fat16_read_file(const char* filename, unsigned char* buffer);
unsigned int fat16_create_file(const char* filename);

#endif
