#ifndef SHELL_H
#define SHELL_H

void shell_loop(void);
char get_key(void);
unsigned char read_sector(unsigned short drive, unsigned int lba, unsigned char* buffer);
unsigned char write_sector(unsigned short drive, unsigned int lba, unsigned char* buffer);

#endif
