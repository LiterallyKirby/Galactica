#ifndef FAT32_H
#define FAT32_H

typedef struct {
    char name[12];
    unsigned int size;
    unsigned char attribute;
    unsigned short cluster_high;
    unsigned short cluster_low;
} file_entry_t;

void fat32_init(void);
unsigned int fat32_read_file(const char* filename, unsigned char* buffer);
unsigned int fat32_write_file(const char* filename, unsigned char* data, unsigned int size);
unsigned int fat32_create_file(const char* filename);
unsigned int fat32_delete_file(const char* filename);
void fat32_list_files(file_entry_t* entries, unsigned int* count);

#endif
