
#ifndef FAT16_H
#define FAT16_H

unsigned int fat16_read_file(const char* filename, unsigned char* buffer);
unsigned int fat16_create_file(const char* filename);

#endif
