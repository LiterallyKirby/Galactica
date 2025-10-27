
#include "include/shell.h"
#include "include/fat16.h"

#define SECTOR_SIZE 512
unsigned char sector[SECTOR_SIZE];

// format 8.3 filename
static void format_name(const char* name, unsigned char* out){
    for(int i=0;i<11;i++) out[i]=' ';
    int i=0,j=0;
    while(name[i] && name[i]!='.' && j<8){ out[j++] = name[i++]; }
    if(name[i]=='.'){ i++; j=8; int k=0; while(name[i] && k<3){ out[j+k]=name[i]; i++; k++; } }
}

unsigned int fat16_read_file(const char* filename, unsigned char* buffer){
    // read BPB
    read_sector(0,0,sector);
    unsigned short bytes_per_sector = *(unsigned short*)&sector[11];
    unsigned char sectors_per_cluster = sector[13];
    unsigned short reserved_sectors = *(unsigned short*)&sector[14];
    unsigned char num_fats = sector[16];
    unsigned short root_entries = *(unsigned short*)&sector[17];
    unsigned short fat_size = *(unsigned short*)&sector[22];

    unsigned int root_dir_sectors = ((root_entries*32)+(bytes_per_sector-1))/bytes_per_sector;
    unsigned int first_root_sector = reserved_sectors + num_fats*fat_size;

    unsigned char name[11];
    format_name(filename,name);

    for(unsigned int s=0;s<root_dir_sectors;s++){
        read_sector(0, first_root_sector+s, sector);
        for(int i=0;i<SECTOR_SIZE;i+=32){
            int match=1;
            for(int j=0;j<11;j++){
                if(sector[i+j]!=name[j]){ match=0; break; }
            }
            if(match){
                unsigned int size = *(unsigned int*)&sector[i+28];
                unsigned short cluster = *(unsigned short*)&sector[i+26];
                unsigned int bytes_read=0;
                unsigned int bytes_per_cluster = bytes_per_sector * sectors_per_cluster;

                while(bytes_read<size){
                    for(int sec=0; sec<sectors_per_cluster; sec++){
                        read_sector(0, reserved_sectors + num_fats*fat_size + (cluster-2)*sectors_per_cluster + sec, sector);
                        unsigned int to_copy = (size - bytes_read > SECTOR_SIZE)? SECTOR_SIZE : (size - bytes_read);
                        for(unsigned int k=0;k<to_copy;k++) buffer[bytes_read+k]=sector[k];
                        bytes_read+=to_copy;
                    }
                    break; // single cluster only for now
                }
                return size;
            }
        }
    }
    return 0;
}

unsigned int fat16_create_file(const char* filename){
    read_sector(0,0,sector);
    unsigned short bytes_per_sector = *(unsigned short*)&sector[11];
    unsigned char sectors_per_cluster = sector[13];
    unsigned short reserved_sectors = *(unsigned short*)&sector[14];
    unsigned char num_fats = sector[16];
    unsigned short root_entries = *(unsigned short*)&sector[17];
    unsigned short fat_size = *(unsigned short*)&sector[22];

    unsigned int root_dir_sectors = ((root_entries*32)+(bytes_per_sector-1))/bytes_per_sector;
    unsigned int first_root_sector = reserved_sectors + num_fats*fat_size;

    unsigned char name[11];
    format_name(filename,name);

    for(unsigned int s=0;s<root_dir_sectors;s++){
        read_sector(0, first_root_sector+s, sector);
        for(int i=0;i<SECTOR_SIZE;i+=32){
            if(sector[i]==0x00 || sector[i]==0xE5){
                for(int j=0;j<11;j++) sector[i+j]=name[j];
                sector[i+11]=0x20; // archive attribute
                for(int j=12;j<32;j++) sector[i+j]=0; // clear rest
                // TODO: write sector back using BIOS write
                return 1;
            }
        }
    }
    return 0;
}
