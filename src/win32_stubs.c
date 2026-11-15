/* Minimal Windows shims for symbols reached by Mesa's generic pan_kmod
 * and non-virtio paths.  The kbase/vdrm path never calls the DRM fallbacks.
 * SPDX-License-Identifier: MIT
 */
#include <errno.h>
#include <stddef.h>
#include <stdint.h>

#include "xf86drm.h"
#include "sys/mman.h"

#ifndef MAP_FAILED
#define MAP_FAILED ((void *)(uintptr_t)~0ull)
#endif

void *mmap(void *addr, size_t len, int prot, int flags, int fd, off_t off)
{
   (void)addr; (void)len; (void)prot; (void)flags; (void)fd; (void)off;
   errno = ENOSYS;
   return MAP_FAILED;
}

int munmap(void *addr, size_t len)
{
   (void)addr; (void)len;
   errno = ENOSYS;
   return -1;
}

drmVersionPtr drmGetVersion(int fd)
{
   (void)fd;
   errno = ENOSYS;
   return NULL;
}

void drmFreeVersion(drmVersionPtr v)
{
   (void)v;
}

int drmPrimeFDToHandle(int fd, int prime_fd, uint32_t *handle)
{
   (void)fd; (void)prime_fd; (void)handle;
   errno = ENOSYS;
   return -1;
}

int drmCloseBufferHandle(int fd, uint32_t handle)
{
   (void)fd; (void)handle;
   errno = ENOSYS;
   return -1;
}
