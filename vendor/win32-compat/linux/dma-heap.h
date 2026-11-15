#pragma once
#include <stdint.h>
#include <sys/ioctl.h>
struct dma_heap_allocation_data {
   uint64_t len;
   uint32_t fd;
   uint32_t fd_flags;
   uint64_t heap_flags;
};
#ifndef DMA_HEAP_IOCTL_ALLOC
#define DMA_HEAP_IOCTL_ALLOC _IOWR('H', 0, struct dma_heap_allocation_data)
#endif
