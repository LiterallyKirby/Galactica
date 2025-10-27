#include "include/shell.h"
#include "include/fat32.h"
#include "include/helpers.h"

#define SECTOR_SIZE 512
unsigned char sector[SECTOR_SIZE];
unsigned char fat_cache[SECTOR_SIZE];

typedef struct {
    unsigned short bytes_per_sector;
    unsigned char sectors_per_cluster;
    unsigned short reserved_sectors;
    unsigned char num_fats;
    unsigned short root_entries;
    unsigned int fat_size32;
    unsigned int root_cluster;
    unsigned int first_data_sector;
    unsigned int total_sectors;
} fat32_info_t;

static fat32_info_t fs_info;
static int fs_initialized = 0;

// Format 8.3 filename
static void format_name(const char* name, unsigned char* out){
    for(int i=0;i<11;i++) out[i]=' ';
    int i=0,j=0;
    while(name[i] && name[i]!='.' && j<8){ 
        out[j++] = (name[i]>='a' && name[i]<='z') ? name[i]-32 : name[i]; 
        i++; 
    }
    if(name[i]=='.'){ 
        i++; 
        j=8; 
        int k=0; 
        while(name[i] && k<3){ 
            out[j+k] = (name[i]>='a' && name[i]<='z') ? name[i]-32 : name[i]; 
            i++; 
            k++; 
        } 
    }
}

// Initialize filesystem
void fat32_init(){
    if(fs_initialized) return;
    
    read_sector(0, 0, sector);
    
    // Check for FAT32 signature
    unsigned short bytes_per_sector = *(unsigned short*)&sector[11];
    unsigned char sectors_per_cluster = sector[13];
    unsigned short reserved_sectors = *(unsigned short*)&sector[14];
    unsigned char num_fats = sector[16];
    unsigned short root_entries = *(unsigned short*)&sector[17];
    unsigned short total_sectors_16 = *(unsigned short*)&sector[19];
    unsigned short fat_size_16 = *(unsigned short*)&sector[22];
    unsigned int total_sectors_32 = *(unsigned int*)&sector[32];
    unsigned int fat_size_32 = *(unsigned int*)&sector[36];
    unsigned int root_cluster = *(unsigned int*)&sector[44];
    
    fs_info.bytes_per_sector = bytes_per_sector;
    fs_info.sectors_per_cluster = sectors_per_cluster;
    fs_info.reserved_sectors = reserved_sectors;
    fs_info.num_fats = num_fats;
    fs_info.root_entries = root_entries;
    
    // FAT32 uses extended fields
    fs_info.fat_size32 = (fat_size_16 == 0) ? fat_size_32 : fat_size_16;
    fs_info.root_cluster = (root_entries == 0) ? root_cluster : 2; // FAT32 has root cluster
    fs_info.total_sectors = (total_sectors_16 == 0) ? total_sectors_32 : total_sectors_16;
    
    // Calculate first data sector
    unsigned int root_dir_sectors = ((root_entries * 32) + (bytes_per_sector - 1)) / bytes_per_sector;
    fs_info.first_data_sector = reserved_sectors + (num_fats * fs_info.fat_size32) + root_dir_sectors;
    
    fs_initialized = 1;
}

// Read FAT entry
static unsigned int fat32_read_fat_entry(unsigned int cluster){
    unsigned int fat_offset = cluster * 4;
    unsigned int fat_sector = fs_info.reserved_sectors + (fat_offset / SECTOR_SIZE);
    unsigned int entry_offset = fat_offset % SECTOR_SIZE;
    
    read_sector(0, fat_sector, fat_cache);
    unsigned int entry = *(unsigned int*)&fat_cache[entry_offset];
    return entry & 0x0FFFFFFF; // Mask off upper 4 bits
}

// Write FAT entry
static void fat32_write_fat_entry(unsigned int cluster, unsigned int value){
    unsigned int fat_offset = cluster * 4;
    unsigned int fat_sector = fs_info.reserved_sectors + (fat_offset / SECTOR_SIZE);
    unsigned int entry_offset = fat_offset % SECTOR_SIZE;
    
    read_sector(0, fat_sector, fat_cache);
    unsigned int old_entry = *(unsigned int*)&fat_cache[entry_offset];
    unsigned int new_entry = (old_entry & 0xF0000000) | (value & 0x0FFFFFFF);
    *(unsigned int*)&fat_cache[entry_offset] = new_entry;
    write_sector(0, fat_sector, fat_cache);
    
    // Write to second FAT
    if(fs_info.num_fats > 1){
        write_sector(0, fat_sector + fs_info.fat_size32, fat_cache);
    }
}

// Find free cluster
static unsigned int fat32_find_free_cluster(){
    for(unsigned int cluster=2; cluster<0x0FFFFFF0; cluster++){
        unsigned int entry = fat32_read_fat_entry(cluster);
        if(entry == 0) return cluster;
    }
    return 0;
}

// Calculate sector from cluster
static unsigned int cluster_to_sector(unsigned int cluster){
    return fs_info.first_data_sector + (cluster - 2) * fs_info.sectors_per_cluster;
}

// Read directory entries from cluster chain
static int find_file_in_directory(unsigned int dir_cluster, unsigned char* name, 
                                   unsigned int* out_cluster, unsigned int* out_size,
                                   unsigned int* out_entry_sector, unsigned int* out_entry_offset){
    unsigned int current_cluster = dir_cluster;
    
    while(current_cluster >= 2 && current_cluster < 0x0FFFFFF0){
        unsigned int cluster_sector = cluster_to_sector(current_cluster);
        
        for(int sec=0; sec<fs_info.sectors_per_cluster; sec++){
            read_sector(0, cluster_sector + sec, sector);
            
            for(int i=0; i<SECTOR_SIZE; i+=32){
                if(sector[i] == 0x00) return 0; // End of directory
                if(sector[i] == 0xE5) continue; // Deleted entry
                if(sector[i+11] & 0x08) continue; // Volume label
                
                int match = 1;
                for(int j=0; j<11; j++){
                    if(sector[i+j] != name[j]){ match=0; break; }
                }
                
                if(match){
                    unsigned short cluster_high = *(unsigned short*)&sector[i+20];
                    unsigned short cluster_low = *(unsigned short*)&sector[i+26];
                    *out_cluster = ((unsigned int)cluster_high << 16) | cluster_low;
                    *out_size = *(unsigned int*)&sector[i+28];
                    *out_entry_sector = cluster_sector + sec;
                    *out_entry_offset = i;
                    return 1;
                }
            }
        }
        
        current_cluster = fat32_read_fat_entry(current_cluster);
    }
    return 0;
}

// Read file
unsigned int fat32_read_file(const char* filename, unsigned char* buffer){
    if(!fs_initialized) fat32_init();
    
    unsigned char name[11];
    format_name(filename, name);
    
    unsigned int file_cluster, file_size, entry_sector, entry_offset;
    if(!find_file_in_directory(fs_info.root_cluster, name, &file_cluster, 
                                &file_size, &entry_sector, &entry_offset)){
        return 0;
    }
    
    unsigned int bytes_read = 0;
    unsigned int current_cluster = file_cluster;
    
    while(current_cluster >= 2 && current_cluster < 0x0FFFFFF0 && bytes_read < file_size){
        unsigned int cluster_sector = cluster_to_sector(current_cluster);
        
        for(int sec=0; sec<fs_info.sectors_per_cluster; sec++){
            read_sector(0, cluster_sector + sec, sector);
            unsigned int to_copy = (file_size - bytes_read > SECTOR_SIZE) ? SECTOR_SIZE : (file_size - bytes_read);
            for(unsigned int k=0; k<to_copy; k++) buffer[bytes_read+k] = sector[k];
            bytes_read += to_copy;
            if(bytes_read >= file_size) break;
        }
        
        current_cluster = fat32_read_fat_entry(current_cluster);
    }
    return bytes_read;
}

// Write file
unsigned int fat32_write_file(const char* filename, unsigned char* data, unsigned int size){
    if(!fs_initialized) fat32_init();
    
    unsigned char name[11];
    format_name(filename, name);
    
    unsigned int old_cluster, old_size, entry_sector, entry_offset;
    if(!find_file_in_directory(fs_info.root_cluster, name, &old_cluster, 
                                &old_size, &entry_sector, &entry_offset)){
        return 0; // File not found
    }
    
    // Allocate new clusters and write data
    unsigned int first_cluster = fat32_find_free_cluster();
    if(first_cluster == 0) return 0;
    
    unsigned int bytes_written = 0;
    unsigned int current_cluster = first_cluster;
    unsigned int prev_cluster = 0;
    
    while(bytes_written < size){
        unsigned int cluster_sector = cluster_to_sector(current_cluster);
        
        for(int sec=0; sec<fs_info.sectors_per_cluster && bytes_written<size; sec++){
            unsigned int to_write = (size - bytes_written > SECTOR_SIZE) ? SECTOR_SIZE : (size - bytes_written);
            for(unsigned int k=0; k<to_write; k++) sector[k] = data[bytes_written+k];
            for(unsigned int k=to_write; k<SECTOR_SIZE; k++) sector[k] = 0;
            
            write_sector(0, cluster_sector + sec, sector);
            bytes_written += to_write;
        }
        
        if(bytes_written < size){
            unsigned int next_cluster = fat32_find_free_cluster();
            if(next_cluster == 0) break;
            
            fat32_write_fat_entry(current_cluster, next_cluster);
            current_cluster = next_cluster;
        } else {
            fat32_write_fat_entry(current_cluster, 0x0FFFFFFF); // EOC marker
        }
    }
    
    // Update directory entry
    read_sector(0, entry_sector, sector);
    *(unsigned short*)&sector[entry_offset+20] = (first_cluster >> 16) & 0xFFFF; // High word
    *(unsigned short*)&sector[entry_offset+26] = first_cluster & 0xFFFF; // Low word
    *(unsigned int*)&sector[entry_offset+28] = bytes_written;
    write_sector(0, entry_sector, sector);
    
    // Free old clusters
    if(old_cluster >= 2 && old_cluster < 0x0FFFFFF0){
        unsigned int cluster = old_cluster;
        while(cluster >= 2 && cluster < 0x0FFFFFF0){
            unsigned int next = fat32_read_fat_entry(cluster);
            fat32_write_fat_entry(cluster, 0);
            cluster = next;
        }
    }
    
    return bytes_written;
}

// Create file
unsigned int fat32_create_file(const char* filename){
    if(!fs_initialized) fat32_init();
    
    unsigned char name[11];
    format_name(filename, name);
    
    // Check if file already exists
    unsigned int dummy_cluster, dummy_size, dummy_sector, dummy_offset;
    if(find_file_in_directory(fs_info.root_cluster, name, &dummy_cluster, 
                              &dummy_size, &dummy_sector, &dummy_offset)){
        return 2; // File exists
    }
    
    // Find free entry in root directory
    unsigned int current_cluster = fs_info.root_cluster;
    
    while(current_cluster >= 2 && current_cluster < 0x0FFFFFF0){
        unsigned int cluster_sector = cluster_to_sector(current_cluster);
        
        for(int sec=0; sec<fs_info.sectors_per_cluster; sec++){
            read_sector(0, cluster_sector + sec, sector);
            
            for(int i=0; i<SECTOR_SIZE; i+=32){
                if(sector[i] == 0x00 || sector[i] == 0xE5){
                    for(int j=0; j<11; j++) sector[i+j] = name[j];
                    sector[i+11] = 0x20; // Archive attribute
                    for(int j=12; j<32; j++) sector[i+j] = 0;
                    write_sector(0, cluster_sector + sec, sector);
                    return 1;
                }
            }
        }
        
        current_cluster = fat32_read_fat_entry(current_cluster);
    }
    return 0;
}

// Delete file
unsigned int fat32_delete_file(const char* filename){
    if(!fs_initialized) fat32_init();
    
    unsigned char name[11];
    format_name(filename, name);
    
    unsigned int file_cluster, file_size, entry_sector, entry_offset;
    if(!find_file_in_directory(fs_info.root_cluster, name, &file_cluster, 
                                &file_size, &entry_sector, &entry_offset)){
        return 0;
    }
    
    // Free clusters
    unsigned int cluster = file_cluster;
    while(cluster >= 2 && cluster < 0x0FFFFFF0){
        unsigned int next = fat32_read_fat_entry(cluster);
        fat32_write_fat_entry(cluster, 0);
        cluster = next;
    }
    
    // Mark entry as deleted
    read_sector(0, entry_sector, sector);
    sector[entry_offset] = 0xE5;
    write_sector(0, entry_sector, sector);
    return 1;
}

// List files
void fat32_list_files(file_entry_t* entries, unsigned int* count){
    if(!fs_initialized) fat32_init();
    
    *count = 0;
    unsigned int current_cluster = fs_info.root_cluster;
    
    while(current_cluster >= 2 && current_cluster < 0x0FFFFFF0 && *count < 64){
        unsigned int cluster_sector = cluster_to_sector(current_cluster);
        
        for(int sec=0; sec<fs_info.sectors_per_cluster; sec++){
            read_sector(0, cluster_sector + sec, sector);
            
            for(int i=0; i<SECTOR_SIZE; i+=32){
                if(sector[i] == 0x00) return;
                if(sector[i] == 0xE5) continue;
                if(sector[i+11] & 0x08) continue; // Volume label
                if(sector[i+11] & 0x10) continue; // Directory
                
                for(int j=0; j<11; j++){
                    entries[*count].name[j] = sector[i+j];
                }
                entries[*count].name[11] = 0;
                entries[*count].size = *(unsigned int*)&sector[i+28];
                entries[*count].attribute = sector[i+11];
                entries[*count].cluster_high = *(unsigned short*)&sector[i+20];
                entries[*count].cluster_low = *(unsigned short*)&sector[i+26];
                
                (*count)++;
                if(*count >= 64) return;
            }
        }
        
        current_cluster = fat32_read_fat_entry(current_cluster);
    }
}
